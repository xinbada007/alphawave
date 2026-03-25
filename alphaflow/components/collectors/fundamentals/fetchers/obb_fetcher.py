"""
OBB Fetcher - 纯 OpenBB 抓取器
支持指定 provider (yfinance, fmp, sec 等)

基于 ACL 防腐层设计，所有财务数据通过 ACLFinancialRecord 模型输出。
"""
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from openbb import obb
import pandas as pd

from .base import BaseFetcher
from alphaflow.core.acl.core_adapter import DynamicFinancialAdapter
from alphaflow.core.utils import ReportPeriod
from alphaflow.core.acl.transformers import _tx_filter_insider_trading

# 全局绕过 Mypy 检查
obb_any: Any = obb


class OBBFetcher(BaseFetcher):
    """纯 OpenBB 抓取器 - 只管 OpenBB，无 fallback"""
    
    name = "OpenBB"
    is_cumulative = False  # 美股/OpenBB 默认离散制
    
    # 类级别信号量：全局最多 3 个并发
    _semaphore = asyncio.Semaphore(3)
    
    # 任务配置字典：标准任务名 -> OpenBB 函数映射
    TASK_CONFIG: Dict[str, Dict[str, Any]] = {
        "profile": {"func": obb_any.equity.profile},
        "estimates": {"func": obb_any.equity.estimates.consensus},
        "share_stats": {"func": obb_any.equity.ownership.share_statistics},
        "management": {"func": obb_any.equity.fundamental.management},
        # 🗑️ dividends 移至专用分支（需动态时间窗口）
        "insider_trading": {
            "func": obb_any.equity.ownership.insider_trading,
            "sort_key": "transaction_date",
            "provider": "sec",
            "filter_fn": _tx_filter_insider_trading  # 🚀 新增：声明式行级过滤器
        },
    }
    
    def __init__(self, provider: str = "yfinance"):
        """
        初始化
        
        Args:
            provider: 默认 provider (yfinance, fmp, sec 等)
        """
        self.default_provider = provider
        self.adapter = DynamicFinancialAdapter(provider_id="obb")
    
    async def _fetch_raw(self, task_name: str, symbol: str, **kwargs) -> List[Dict]:
        """任务翻译官：将标准化任务名翻译为 OpenBB 调用"""
        limit_a = kwargs.get("limit_a", 2)
        limit_q = kwargs.get("limit_q", 5)
        # DEFAULT_EARNINGS_LIMIT 默认提取 8 份财报（匹配 2 年季度/4 年半年度回溯基准）
        DEFAULT_EARNINGS_LIMIT = 8
        limit = kwargs.get("limit", DEFAULT_EARNINGS_LIMIT)
        
        # 1. 字典映射的简单任务
        if task_name in self.TASK_CONFIG:
            config = self.TASK_CONFIG[task_name]
            func = config["func"]
            # 🚨 优先使用 Config 中的 provider (如 insider_trading 锁死 sec)，否则使用 default_provider
            target_provider = config.get("provider", self.default_provider)
            return await self._exec_obb_task(
                func, symbol, task_name,
                provider=target_provider,
                sort_key=config.get("sort_key"),
                filter_fn=config.get("filter_fn"),  # 🚀 新增参数传递
                # 必须在 kwargs 解包中屏蔽这四个内部键
                **{k: v for k, v in config.items() if k not in ("func", "sort_key", "provider", "filter_fn")}
            )
        
        # 2. 特殊任务 - 使用 default_provider
        elif task_name == "earnings_cal":
            return await self._fetch_earnings_cal(symbol, self.default_provider, limit)
        
        elif task_name == "major_holders":
            return await self._fetch_major_holders(symbol, self.default_provider)
        
        elif task_name == "splits":
            return await self._fetch_splits(symbol, self.default_provider)
        
        # 🚀 新增：dividends 升级为特殊任务（动态时间窗口）
        elif task_name == "dividends":
            return await self._fetch_dividends(symbol, self.default_provider)
        
        # 3. 财务报表任务 (动态映射：a_income, q_balance 等)
        elif "_" in task_name:
            parts = task_name.split("_")
            if len(parts) >= 2 and parts[1] in ("income", "balance", "cash"):
                stmt_key = parts[1]
                period = "annual" if "a_" in task_name else "quarter"
                limit = limit_a if period == "annual" else limit_q
                
                if hasattr(obb_any.equity.fundamental, stmt_key):
                    func = getattr(obb_any.equity.fundamental, stmt_key)
                    return await self._exec_obb_task(
                        func, symbol, task_name,
                        period=period, limit=limit
                    )
        
        # 不支持的任务
        raise ValueError(f"{self.name} does not support task: {task_name}")
    
    async def _exec_obb_task(
        self,
        func: Callable,
        symbol: str,
        name: str,
        provider: Optional[str] = None,
        sort_key: Optional[str] = None,
        filter_symbol: bool = False,
        filter_fn: Optional[Callable] = None,  # 🚀 扩充契约
        **kwargs
    ) -> List[Dict]:
        """执行 OpenBB 任务"""
        target_provider = provider if provider else self.default_provider
        
        async with self._semaphore:
            try:
                res = await asyncio.to_thread(
                    func,
                    symbol=symbol,
                    provider=target_provider,
                    **kwargs
                )
                
                # 提取数据
                data = []
                raw_results = []
                
                if res:
                    if hasattr(res, 'results') and res.results:
                        raw_results = res.results
                    elif isinstance(res, list):
                        raw_results = res
                
                for item in raw_results:
                    if hasattr(item, "model_dump"):
                        data.append(item.model_dump())
                    elif hasattr(item, "dict"):
                        data.append(item.dict())
                    elif isinstance(item, dict):
                        data.append(item)
                
                # 过滤 Symbol
                if filter_symbol and data:
                    data = [x for x in data if str(x.get("symbol", "")).upper() == symbol.upper()]
                
                # 🚀 新增：执行行级特征过滤 (先过滤，后排序，提升性能)
                if filter_fn and data:
                    data = [x for x in data if filter_fn(x)]
                
                # 排序
                if sort_key and data:
                    data.sort(key=lambda x: str(x.get(sort_key, "")), reverse=True)
                
                return data if data else []
                
            except Exception as e:
                raise Exception(f"{self.name} _exec_obb_task({name}) failed: {e}")
    
    async def _fetch_earnings_cal(self, symbol: str, provider: str, limit: int = 8) -> List[Dict]:
        """获取财报日历 (包含历史 EPS 预期与实际值)"""
        
        # 1. 检查 Provider 白名单 (文档明确只支持这些)
        supported_providers = {'fmp', 'nasdaq', 'seeking_alpha', 'tmx'}
        if provider not in supported_providers:
            # 静默失败，触发责任链 Fallback (交给 NativeYFinance)
            raise ValueError(f"Provider '{provider}' not supported for earnings_cal")

        try:
            # 2. 计算时间窗口 (关键修复)
            # 默认回溯 3 年 (确保在动态 limit 请求下能覆盖绝大多数场景)
            # 往后推 1 个月 (涵盖即将发布的一次财报)
            now = datetime.now()
            start_date = (now - pd.Timedelta(days=3 * 365)).strftime("%Y-%m-%d")
            end_date = (now + pd.Timedelta(days=180)).strftime("%Y-%m-%d")

            # 3. 调用 OpenBB
            data = await self._exec_obb_task(
                obb_any.equity.calendar.earnings,
                symbol, "earnings_cal",
                provider=provider,
                # 显式传递时间窗口
                start_date=start_date,
                end_date=end_date,
                # 防御性编程：强制过滤 Symbol，防止 nasdaq 等返回全市场数据
                filter_symbol=True  
            )
            
            if data:
                # 4. 排序与截断
                # 按日期倒序 (最新在前)
                data.sort(key=lambda x: str(x.get("report_date", x.get("date", ""))), reverse=True)
                return data[:limit]
                
        except Exception as e:
            raise Exception(f"{self.name} earnings_cal failed: {e}")
        
        raise Exception(f"{self.name} earnings_cal unavailable")
    
    async def _fetch_major_holders(self, symbol: str, provider: str) -> List[Dict]:
        """获取大股东信息"""
        try:
            data = await self._exec_obb_task(
                obb_any.equity.ownership.major_holders,
                symbol, "major_holders",
                provider=provider
            )
            if data:
                return data
        except Exception as e:
            raise Exception(f"{self.name} major_holders failed: {e}")
        
        raise Exception(f"{self.name} major_holders unavailable")
    
    async def _fetch_splits(self, symbol: str, provider: str) -> List[Dict]:
        """获取拆股历史 (硬性截断最近 5 年，保护 LLM 视区)"""
        try:
            now = datetime.now()
            # 动态计算 5 年的物理时间窗口
            start_date = (now - pd.Timedelta(days=5 * 365)).strftime("%Y-%m-%d")
            
            data = await self._exec_obb_task(
                obb_any.equity.calendar.splits,
                symbol, "splits",
                provider=provider,
                sort_key="date",
                start_date=start_date  # 🚀 从 API 请求源头掐断远古数据
            )
            if data:
                return data
        except Exception as e:
            raise Exception(f"{self.name} splits failed: {e}")
        
        raise Exception(f"{self.name} splits unavailable")
    
    async def _fetch_dividends(self, symbol: str, provider: str) -> List[Dict]:
        """获取历史分红数据 (动态限制最近 7 年，防止抓取过多噪音)"""
        try:
            now = datetime.now()
            # 动态计算 7 年的时间窗口
            start_date = (now - pd.Timedelta(days=7 * 365)).strftime("%Y-%m-%d")
            
            data = await self._exec_obb_task(
                obb_any.equity.fundamental.dividends,
                symbol, "dividends",
                provider=provider,
                sort_key="ex_dividend_date",
                start_date=start_date  # 🚀 透传给 OpenBB 底层
            )
            if data:
                return data
        except Exception as e:
            raise Exception(f"{self.name} dividends failed: {e}")
        
        raise Exception(f"{self.name} dividends unavailable")

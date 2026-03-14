"""
AkShare CN Fetcher - 纯 AkShare A 股抓取器
负责 A 股的财务数据抓取

基于 ACL 防腐层设计，所有财务数据通过 ACLFinancialRecord 模型输出。
"""
import asyncio
from typing import List, Dict, Any
import pandas as pd
import akshare as ak  # type: ignore

from .base import BaseFetcher
from alphaflow.core.utils import ReportPeriod
from alphaflow.core.acl.core_adapter import DynamicFinancialAdapter


class AkShareCNFetcher(BaseFetcher):
    """纯 AkShare A 股抓取器 - A 股/沪深"""
    
    name = "AkShareCN"
    is_cumulative = True  # A 股累积制
    
    # 类级别信号量：全局最多 2 个并发，防止触发 WAF
    _semaphore = asyncio.Semaphore(2)
    
    def __init__(self):
        """初始化 Adapter"""
        self.adapter = DynamicFinancialAdapter(provider_id="akshare")
    
    async def _fetch_raw(self, task_name: str, symbol: str, **kwargs) -> List[Dict]:
        """任务翻译官：将标准化任务名翻译为 AkShare API"""
        limit_a = kwargs.get("limit_a", 2)
        limit_q = kwargs.get("limit_q", 5)
        
        # 解析任务名
        if task_name.endswith("_income"):
            # a_income -> 年度/利润表
            period = "年度" if task_name.startswith("a_") else "报告期"
            limit = limit_a if task_name.startswith("a_") else limit_q
            return await self._fetch_rep(symbol, "利润表", period, limit)
        
        elif task_name.endswith("_balance"):
            period = "年度" if task_name.startswith("a_") else "报告期"
            limit = limit_a if task_name.startswith("a_") else limit_q
            return await self._fetch_rep(symbol, "资产负债表", period, limit)
        
        elif task_name.endswith("_cash"):
            period = "年度" if task_name.startswith("a_") else "报告期"
            limit = limit_a if task_name.startswith("a_") else limit_q
            return await self._fetch_rep(symbol, "现金流量表", period, limit)
        
        elif task_name == "a_analysis":
            return await self._fetch_ana(symbol, "年度", limit_a)
        
        elif task_name == "q_analysis":
            return await self._fetch_ana(symbol, "报告期", limit_q)
        
        elif task_name == "dividends":
            return await self._fetch_cn_dividends(symbol)
        
        elif task_name == "profile":
            return await self._fetch_profile(symbol)
        
        # 不支持的任务，抛出异常
        raise ValueError(f"{self.name} does not support task: {task_name}")
    
    async def _fetch_rep(
        self, symbol: str, tbl: str, p_type: str, lim: int
    ) -> List[Dict]:
        """抓取财务报表"""
        # A 股 symbol 处理：600519.SH -> 600519
        code = symbol.split(".")[0]
        
        async with self._semaphore:
            try:
                df = await asyncio.to_thread(
                    ak.stock_financial_report_sina,
                    stock=code,
                    symbol=tbl,
                )
                if df.empty:
                    return []
                
                # 透视表
                tdf = (
                    df.pivot_table(
                        index="REPORT_DATE",
                        columns="ITEM_NAME",
                        values="VALUE",
                        aggfunc="first",
                    )
                    .sort_index(ascending=False)
                    .head(lim)
                )
                
                tdf.index = pd.to_datetime(tdf.index).strftime("%Y-%m-%d")
                tdf.index.name = "period_ending"
                raw_records: List[Dict[str, Any]] = tdf.reset_index().to_dict(orient="records")  # type: ignore
                
                # 返回原始数据，由基类 fetch() 方法统一进行路由和清洗
                return raw_records
                
            except Exception as e:
                raise Exception(f"{self.name} _fetch_rep({tbl}) failed: {e}")
    
    async def _fetch_ana(self, symbol: str, p_type: str, lim: int) -> List[Dict]:
        """抓取分析指标"""
        code = symbol.split(".")[0]
        
        async with self._semaphore:
            try:
                # A 股分析指标
                df = await asyncio.to_thread(
                    ak.stock_financial_analysis_indicator,
                    symbol=code,
                    start_year=p_type,
                )
                if df.empty:
                    return []
                df = df.sort_values("REPORT_DATE", ascending=False).head(lim)
                df["period_ending"] = pd.to_datetime(df["REPORT_DATE"]).dt.strftime("%Y-%m-%d")
                return df.to_dict(orient="records")
                
            except Exception as e:
                raise Exception(f"{self.name} _fetch_ana({p_type}) failed: {e}")
    
    async def _fetch_cn_dividends(self, symbol: str) -> List[Dict]:
        """
        抓取 A 股分红派息
        
        护栏3: 彻底放下屠刀 - Fetcher 变成"傻瓜"
        不再做任何 rename 映射，直接把包含中文列名的 Raw DataFrame to_dict 送出去
        相信并依赖外层的 Adapter 会把它洗干净
        
        Zero Divs 修复：数值型字段空值转为 None，避免 Pydantic 验证异常
        """
        code = symbol.split(".")[0]
        
        async with self._semaphore:
            try:
                df = await asyncio.to_thread(
                    ak.stock_dividend_cn,
                    symbol=code
                )
                if df.empty:
                    return []
                
                # 日期格式化 - 只处理日期列，不做字段映射
                date_cols = ["除净日", "ex_dividend_date", "最新公告日期", "announce_date", "发放日", "payment_date"]
                for col in date_cols:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")
                
                # Zero Divs 修复：数值型字段空值转为 None，让 Pydantic 优雅处理 Optional[float]
                # 日期列之外的列，尝试转换为数值，失败则置为 None
                for col in df.columns:
                    if col not in date_cols:
                        # 先尝试转换为数值类型
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                    # 将 NaN 转为 None (包括日期列和数值列)
                    # 使用 mask + fillna 组合，避免类型提示问题
                    df[col] = df[col].mask(df[col].isna()).astype(object).fillna(None)
                
                # 按除净日排序
                sort_col = None
                for c in ["除净日", "ex_dividend_date"]:
                    if c in df.columns:
                        sort_col = c
                        break
                if sort_col:
                    df = df.sort_values(sort_col, ascending=False)
                
                # 直接返回原始数据，交给 Adapter 清洗
                return df.to_dict(orient="records")
                
            except Exception as e:
                raise Exception(f"{self.name} _fetch_cn_dividends failed: {e}")
    
    async def _fetch_profile(self, symbol: str) -> List[Dict]:
        """抓取公司 profile (扁平化修复版)"""
        code = symbol.split(".")[0]
        
        try:
            p_df = await asyncio.to_thread(ak.stock_profile_cn, symbol=code)
            
            flat_profile = {}
            if not p_df.empty:
                flat_profile.update({str(k).strip(): v for k, v in p_df.iloc[0].to_dict().items()})
                
            return [flat_profile] if flat_profile else []
            
        except Exception as e:
            raise Exception(f"{self.name} _fetch_profile failed: {e}")
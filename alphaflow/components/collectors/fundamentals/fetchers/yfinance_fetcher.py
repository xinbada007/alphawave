"""
YFinance Fetcher - 纯原生 yfinance 抓取器
用于 OpenBB 失败时的兜底抓取

基于 ACL 防腐层设计，所有财务数据通过 ACLFinancialRecord 模型输出。
"""
import asyncio
from typing import List, Dict, Any
from fractions import Fraction
import pandas as pd
import yfinance as yf

from .base import BaseFetcher
from alphaflow.core.acl.core_adapter import DynamicFinancialAdapter
from alphaflow.core.utils import ReportPeriod


class YFinanceFetcher(BaseFetcher):
    """纯原生 yfinance 抓取器 - 只管原生 yf，无 fallback"""
    
    name = "NativeYFinance"
    is_cumulative = False  # 美股/原生 yfinance 默认离散制
    
    # 类级别信号量：全局最多 3 个并发
    _semaphore = asyncio.Semaphore(3)
    
    def __init__(self):
        """初始化 Adapter"""
        self.adapter = DynamicFinancialAdapter(provider_id="obb")
    
    async def _fetch_raw(self, task_name: str, symbol: str, **kwargs) -> List[Dict]:
        """任务翻译官：将标准化任务名翻译为 yfinance 调用"""
        limit = kwargs.get("limit", 8)  # 默认 8 条，与旧架构一致
        
        if task_name == "splits":
            return await self._fetch_splits(symbol)
        
        elif task_name == "major_holders":
            return await self._fetch_major_holders(symbol)
        
        elif task_name == "earnings_cal":
            return await self._fetch_earnings_cal(symbol, limit)
        
        # 不支持的任务
        raise ValueError(f"{self.name} does not support task: {task_name}")
    
    async def _fetch_splits(self, symbol: str) -> List[Dict]:
        """获取拆股历史 (兜底专用，硬性截断最近 5 年)"""
        
        async with self._semaphore:
            try:
                def _sync_fetch():
                    ticker = yf.Ticker(symbol)
                    splits = ticker.splits
                    if splits is None or splits.empty:
                        return []
                    
                    df = splits.reset_index()
                    df.columns = ['date', 'ratio_float']
                    
                    # 🚀 核心过滤：物理截断 5 年前的数据
                    # 移除 tz 时区以便与 Timestamp.now() 进行纯净比对
                    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
                    cutoff = pd.Timestamp.now() - pd.DateOffset(years=5)
                    df = df[df['date'] >= cutoff]
                    
                    if df.empty:
                        return []
                    
                    # 格式化日期为字符串
                    df['date'] = df['date'].dt.strftime("%Y-%m-%d")
                    
                    # 浮点数转拆股比例字符串 (如 0.25 -> 1:4)
                    def _float_to_ratio(x: float) -> str:
                        f = Fraction(x).limit_denominator(1000)
                        return f"{f.numerator}:{f.denominator}"
                    
                    df['ratio'] = df['ratio_float'].apply(_float_to_ratio)
                    df = df.sort_values("date", ascending=False)
                    return df[['date', 'ratio']].to_dict("records")
                
                return await asyncio.to_thread(_sync_fetch)
                
            except Exception as e:
                raise Exception(f"{self.name} splits failed: {e}")
    
    async def _fetch_major_holders(self, symbol: str) -> List[Dict]:
        """
        获取大股东与机构持仓信息 (架构级优化版)
        策略：语义保留 + Token截断 + JSON安全净化，放弃脆弱的强制 Float 转换。
        """
        async with self._semaphore:
            try:
                def _sync_fetch():
                    import numpy as np  # 确保能处理 np.nan
                    ticker = yf.Ticker(symbol)
                    holders_data =[]

                    # ---------------------------------------------------------
                    # 环节 1：API 故障隔离
                    # ---------------------------------------------------------
                    try:
                        mh = ticker.major_holders
                    except Exception as e:
                        print(f"  [NativeYFinance] {symbol} major_holders fetch failed: {e}")
                        mh = None

                    try:
                        ih = ticker.institutional_holders
                    except Exception as e:
                        print(f"  [NativeYFinance] {symbol} institutional_holders fetch failed: {e}")
                        ih = None

                    # ---------------------------------------------------------
                    # 环节 2：Major Holders (大股东结构概览) 清洗
                    # ---------------------------------------------------------
                    if mh is not None and isinstance(mh, pd.DataFrame) and not mh.empty:
                        # 核心防线1：释放隐藏在 Index 中的语义描述
                        # yfinance 经常把 "PROMOTERS", "INSTITUTIONS" 等关键描述放在 Index 里
                        mh_clean = mh.reset_index()
                        
                        # 核心防线2：JSON 序列化安全
                        # 替换所有 Pandas 专属的 NaN 为 Python 原生的 None
                        mh_clean = mh_clean.replace({np.nan: None, np.inf: None, -np.inf: None})
                        
                        holders_data.append({
                            "type": "major_ownership_breakdown",
                            "data": mh_clean.to_dict(orient="records")
                        })

                    # ---------------------------------------------------------
                    # 环节 3：Institutional Holders (机构明细) 清洗与截断
                    # ---------------------------------------------------------
                    if ih is not None and isinstance(ih, pd.DataFrame) and not ih.empty:
                        # 核心防线3：Token 物理截断 (Token Optimization)
                        # 严格只取前 10 大机构，抛弃尾部碎股股东，保卫大模型上下文视区
                        ih_clean = ih.head(10).copy()
                        
                        # JSON 序列化安全：处理 NaN
                        ih_clean = ih_clean.replace({np.nan: None, np.inf: None, -np.inf: None})
                        
                        # 核心防线4：时间戳类型安全
                        # yfinance 可能返回带时区的 Datetime 格式，JSON 无法直接 dump
                        for col in ih_clean.select_dtypes(include=['datetime64', 'datetimetz']).columns:
                            ih_clean[col] = ih_clean[col].dt.strftime('%Y-%m-%d')
                            
                        holders_data.append({
                            "type": "top_institutions",
                            "data": ih_clean.to_dict(orient="records")
                        })

                    return holders_data

                return await asyncio.to_thread(_sync_fetch)
                
            except Exception as e:
                raise Exception(f"{self.name} major_holders failed: {e}")
    
    async def _fetch_earnings_cal(self, symbol: str, limit: int = 8) -> List[Dict]:
        """获取财报日历"""
        
        async with self._semaphore:
            try:
                def _sync_fetch():
                    ticker = yf.Ticker(symbol)
                    ed = ticker.earnings_dates
                    
                    if ed is None or ed.empty:
                        return []
                    
                    df = ed.reset_index()
                    df.rename(columns={'Earnings Date': 'report_date'}, inplace=True)
                    df['report_date'] = pd.to_datetime(df['report_date']).dt.tz_localize(None).dt.strftime("%Y-%m-%d")
                    df = df.head(limit)  # 限制获取条数
                    import numpy as np
                    df = df.replace({np.nan: None})
                    return df.to_dict("records")
                
                return await asyncio.to_thread(_sync_fetch)
                
            except Exception as e:
                raise Exception(f"{self.name} earnings_cal failed: {e}")
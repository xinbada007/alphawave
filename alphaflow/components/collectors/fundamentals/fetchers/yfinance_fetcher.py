"""
YFinance Fetcher - 纯原生 yfinance 抓取器
用于 OpenBB 失败时的兜底抓取
"""
import asyncio
from typing import List, Dict, Any
from fractions import Fraction
import pandas as pd
import yfinance as yf

from .base import BaseFetcher


class YFinanceFetcher(BaseFetcher):
    """纯原生 yfinance 抓取器 - 只管原生 yf，无 fallback"""
    
    name = "NativeYFinance"
    
    # 类级别信号量：全局最多 3 个并发
    _semaphore = asyncio.Semaphore(3)
    
    async def fetch(self, task_name: str, symbol: str, **kwargs) -> List[Dict]:
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
        """获取拆股历史"""
        
        async with self._semaphore:
            try:
                def _sync_fetch():
                    ticker = yf.Ticker(symbol)
                    splits = ticker.splits
                    if splits is None or splits.empty:
                        return []
                    
                    df = splits.reset_index()
                    df.columns = ['date', 'ratio_float']
                    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).dt.strftime("%Y-%m-%d")
                    
                    # 浮点数转拆股比例字符串
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
        """获取大股东信息"""
        
        async with self._semaphore:
            try:
                def _sync_fetch():
                    ticker = yf.Ticker(symbol)
                    mh = ticker.major_holders
                    ih = ticker.institutional_holders
                    
                    holders_data = []
                    if mh is not None and not mh.empty:
                        holders_data.append({"type": "major_ownership_breakdown", "data": mh.to_dict(orient="records")})
                    
                    if ih is not None and not ih.empty:
                        top_inst = ih.head(10).to_dict(orient="records")
                        holders_data.append({"type": "top_institutions", "data": top_inst})
                    
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
                    df = df.fillna("N/A")
                    return df.to_dict("records")
                
                return await asyncio.to_thread(_sync_fetch)
                
            except Exception as e:
                raise Exception(f"{self.name} earnings_cal failed: {e}")

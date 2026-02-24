"""
OpenBB/YFinance Fetcher - 通用市场抓取器
职责：作为美股主力，以及港股/A股的兜底
"""
import asyncio
import os
import pandas as pd
from typing import Dict, Any, Any
from datetime import datetime
from openbb import obb # type: ignore

from .base import BaseMarketFetcher
from alphaflow.utils.api_rotator import get_api_key

# 全局绕过 Mypy
obb_any: Any = obb

class OBBFetcher(BaseMarketFetcher):
    """OpenBB (YFinance) 适配器"""
    
    name = "OpenBB"
    _semaphore = asyncio.Semaphore(5)
    
    def __init__(self, provider: str = "yfinance"):
        self.provider = provider
        self.name = f"OpenBB_{provider}"

    async def fetch_price(self, symbol: str, days: int) -> pd.DataFrame:
        start_date = (datetime.now() - pd.Timedelta(days=int(days * 1.6))).strftime("%Y-%m-%d")
        
        # 注入 API Key
        api_key = get_api_key(self.provider) if self.provider in ["polygon", "fmp", "alpha_vantage"] else None
        if api_key:
            os.environ[f"{self.provider.upper()}_API_KEY"] = api_key

        async with self._semaphore:
            try:
                res = await asyncio.to_thread(
                    obb_any.equity.price.historical,
                    symbol=symbol,
                    provider=self.provider,
                    start_date=start_date,
                )
                
                if not res or not res.results:
                    return pd.DataFrame()
                
                df = pd.DataFrame([it.dict() for it in res.results])
                
                # 脏活：OpenBB 可能返回 dividends/splits 列，需要移除
                cols_to_remove = ["dividends", "stock_splits", "dividend", "split_ratio", "capital_gains"]
                df = df.drop(columns=[c for c in cols_to_remove if c in df.columns])
                
                # 调用基类清洗逻辑 (无需重命名，OBB 默认就是英文)
                return self._clean_dataframe(df, {})
                
            except Exception as e:
                print(f"  [{self.name}] fetch_price failed for {symbol}: {e}")
                return pd.DataFrame()

    async def fetch_metrics(self, symbol: str) -> Dict[str, Any]:
        async with self._semaphore:
            try:
                res = await asyncio.to_thread(
                    obb_any.equity.fundamental.metrics,
                    symbol=symbol, 
                    provider=self.provider,
                )
                
                if not res or not res.results:
                    return {}
                
                data = res.results[0].dict() if hasattr(res.results[0], 'dict') else vars(res.results[0])
                
                # 字段映射
                metrics = self._map_standard_metrics(data)
                
                # 脏活：处理 YFinance 特有的百分比问题
                # 对齐原版逻辑：同时处理标准化字段名和原始字段名
                if self.provider == "yfinance":
                    # 处理标准化字段名
                    pct_fix_keys = ["dividendYieldTtm", "debtToEquity"]
                    for k in pct_fix_keys:
                        if k in metrics and metrics[k] is not None:
                            try:
                                metrics[k] = round(float(metrics[k]) / 100, 6)
                            except (ValueError, TypeError):
                                pass
                    # 处理原始字段名 (raw_openbb)
                    if "dividend_yield" in data and data["dividend_yield"] is not None:
                        try:
                            data["dividend_yield"] = round(float(data["dividend_yield"]) / 100, 6)
                        except (ValueError, TypeError):
                            pass
                    if "debt_to_equity" in data and data["debt_to_equity"] is not None:
                        try:
                            data["debt_to_equity"] = round(float(data["debt_to_equity"]) / 100, 6)
                        except (ValueError, TypeError):
                            pass

                metrics["raw_openbb"] = data
                metrics["_source"] = self.provider
                return metrics
                
            except Exception as e:
                print(f"  [{self.name}] fetch_metrics failed for {symbol}: {e}")
                return {}

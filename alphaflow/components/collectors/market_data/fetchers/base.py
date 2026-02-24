"""
Base Market Fetcher - 市场数据抓取器基类
定义统一契约，提供通用字段映射工具
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from alphaflow.core.data_utils import (
    MARKET_FIELD_CHAINS,
    FINANCIAL_FIELD_CHAINS,
    get_field_value,
)

# 全局 AkShare 防并发风暴锁
AKSHARE_SEMAPHORE = asyncio.Semaphore(5)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=False
)
async def _safe_akshare_call(func: Callable, *args, **kwargs) -> Any:
    """安全的 AkShare 调用封装：加锁 + 重试"""
    async with AKSHARE_SEMAPHORE:
        return await asyncio.to_thread(func, *args, **kwargs)

class BaseMarketFetcher(ABC):
    """原子抓取器基类：只负责抓取 Price 和 Metrics"""
    
    name: str = "BaseMarketFetcher"

    # 字段名映射表：将 API 返回的各种 Alias 映射为标准字段名
    FIELD_ALIAS_MAP = {
        # Market 字段
        "MCAP": "marketCap",
        "MCAP_HK": "marketCapHk",
        "PE": "trailingPE",
        "PB": "priceToBook",
        "PS": "priceToSales",
        "PCF": "priceToCashFlow",
        "DIVIDEND_YIELD": "dividendYieldTtm",
        "EPS": "trailingEps",
        "BPS": "bookValue",
        "OCPS": "operatingCashFlowPerShare",
        "DPS": "dividendPerShare",
        "SHARES": "sharesOutstanding",
        "SHARES_H": "sharesH",
        "AUTHORIZED_SHARES": "authorizedShares",
        "LOT_SIZE": "lotSize",
        "PAYOUT_RATIO": "payoutRatio",
        # Financial 字段
        "REV": "totalRevenue",
        "NI": "netProfit",
        "OI": "operatingIncome",
        "GP": "grossProfit",
        "OCF": "operatingCashFlow",
        "ASSETS": "totalAssets",
        "LIAB": "totalLiabilities",
        "EQUITY": "totalEquity",
        # 百分比字段
        "ROE": "roe",
        "ROA": "roa",
        "NET_MARGIN": "netMargin",
        "GROSS_MARGIN": "grossMargin",
        "REV_GROWTH_QOQ": "revGrowthQoq",
        "NI_GROWTH_QOQ": "niGrowthQoq",
        "REV_GROWTH_YOY": "revGrowthYoy",
        "NI_GROWTH_YOY": "niGrowthYoy",
    }

    @abstractmethod
    async def fetch_price(self, symbol: str, days: int) -> pd.DataFrame:
        """
        抓取历史价格 (OHLCV)
        必须返回: index=DatetimeIndex(naive), columns=[open, high, low, close, volume]
        """
        pass

    @abstractmethod
    async def fetch_metrics(self, symbol: str) -> Dict[str, Any]:
        """
        抓取实时估值指标
        必须返回: 标准化的字典 key
        """
        pass

    def _map_standard_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """通用工具：仅做 Key 的映射，不做数值修改"""
        metrics = {}
        
        # 1. 提取 Market 字段
        for alias_key in MARKET_FIELD_CHAINS.keys():
            val = get_field_value(data, alias_key, MARKET_FIELD_CHAINS)
            if val is not None:
                key = self.FIELD_ALIAS_MAP.get(alias_key, alias_key.lower())
                metrics[key] = val
        
        # 2. 提取 Financial 字段
        for alias_key in FINANCIAL_FIELD_CHAINS.keys():
            val = get_field_value(data, alias_key, FINANCIAL_FIELD_CHAINS)
            if val is not None:
                key = self.FIELD_ALIAS_MAP.get(alias_key, alias_key.lower())
                metrics[key] = val
                
        return metrics
    
    def _clean_dataframe(self, df: pd.DataFrame, rename_map: Dict[str, str]) -> pd.DataFrame:
        """通用工具：DataFrame 标准化清洗 (重命名 -> 时区 -> 排序 -> 类型)"""
        if df.empty:
            return pd.DataFrame()

        # 1. 重命名
        df = df.rename(columns=rename_map)
        
        # 2. 索引处理 (去重 + 时区剥离)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.drop_duplicates(subset=["date"], keep='last')
            df.set_index("date", inplace=True)
        
        # 🌟 关键：强制剥离时区，确保下游计算无误
        if isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.index.name = "date"
        
        # 3. 排序 (防止 API 倒序返回)
        df.sort_index(ascending=True, inplace=True)
        
        # 4. 类型强制转换
        numeric_cols = ["open", "high", "low", "close", "volume", 
                       "amount", "turnover_rate", "amplitude", "pct_change", "change_amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 5. 衍生指标
        if "high" in df.columns and "low" in df.columns and "close" in df.columns:
            df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3
        
        if "vwap" not in df.columns:
            if "amount" in df.columns and "volume" in df.columns:
                df["vwap"] = (df["amount"] / df["volume"]).fillna(df["close"])
            else:
                df["vwap"] = None
                
        return df

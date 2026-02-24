"""
Base Market Strategy - 市场策略基类
实现双轨并发责任链 (Price Chain + Metrics Chain)
"""
import asyncio
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any
import pandas as pd

from ..fetchers.base import BaseMarketFetcher

class BaseMarketStrategy(ABC):
    """双轨并发策略基类"""

    @abstractmethod
    def get_price_chain(self) -> List[BaseMarketFetcher]:
        """定义价格抓取的责任链"""
        pass

    @abstractmethod
    def get_metrics_chain(self) -> List[BaseMarketFetcher]:
        """定义指标抓取的责任链"""
        pass

    async def execute(self, symbol: str, days: int) -> Tuple[pd.DataFrame, Dict[str, Any], str]:
        """
        并发执行价格与指标抓取
        Returns: (price_df, metrics, used_provider_name)
        """
        
        # 1. 价格兜底链执行器
        async def fetch_price_with_fallback() -> Tuple[pd.DataFrame, str]:
            chain = self.get_price_chain()
            for fetcher in chain:
                try:
                    df = await fetcher.fetch_price(symbol, days)
                    if not df.empty:
                        return df, fetcher.name
                except Exception as e:
                    # 静默失败，继续尝试下一个
                    print(f"  [Fallback Warning] {fetcher.name} price failed: {str(e)[:60]}")
                    continue
            return pd.DataFrame(), "none"

        # 2. 指标兜底链执行器
        async def fetch_metrics_with_fallback() -> Dict[str, Any]:
            chain = self.get_metrics_chain()
            for fetcher in chain:
                try:
                    metrics = await fetcher.fetch_metrics(symbol)
                    if metrics:
                        return metrics
                except Exception as e:
                    print(f"  [Fallback Warning] {fetcher.name} metrics failed: {str(e)[:60]}")
                    continue
            return {}

        # 🚀 并发执行双链
        (price_df, used_provider), metrics = await asyncio.gather(
            fetch_price_with_fallback(),
            fetch_metrics_with_fallback()
        )
        
        return price_df, metrics, used_provider

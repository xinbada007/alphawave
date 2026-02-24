"""HK Market Strategy - 港股编排"""
from typing import List
from .base import BaseMarketStrategy
from ..fetchers.base import BaseMarketFetcher
from ..fetchers.akshare_hk_fetcher import AkShareHKFetcher
from ..fetchers.obb_fetcher import OBBFetcher

class HKMarketStrategy(BaseMarketStrategy):
    def __init__(self):
        self.ak = AkShareHKFetcher()
        self.obb = OBBFetcher(provider="yfinance")

    def get_price_chain(self) -> List[BaseMarketFetcher]:
        # 价格：优先 AkShare，失败用 YF
        return [self.ak, self.obb]

    def get_metrics_chain(self) -> List[BaseMarketFetcher]:
        # 指标：优先 AkShare，失败用 YF
        return [self.ak, self.obb]

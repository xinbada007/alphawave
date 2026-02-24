"""CN Market Strategy - A股编排 (业务占位)"""
import pandas as pd
from typing import List, Tuple, Dict, Any

from .base import BaseMarketStrategy
from ..fetchers.base import BaseMarketFetcher
from ..fetchers.akshare_cn_fetcher import AkShareCNFetcher
from ..fetchers.obb_fetcher import OBBFetcher

class CNMarketStrategy(BaseMarketStrategy):
    """
    A股策略
    目前作为业务占位符，虽然实例化了 Fetcher，但 execute 中暂不执行实际逻辑。
    待 A 股业务就绪后，只需删除 execute 的覆盖即可启用默认行为。
    """
    
    def __init__(self):
        self.ak = AkShareCNFetcher()
        self.obb = OBBFetcher(provider="yfinance")

    def get_price_chain(self) -> List[BaseMarketFetcher]:
        return [self.ak, self.obb]

    def get_metrics_chain(self) -> List[BaseMarketFetcher]:
        return [self.obb] # A股指标 AkShare 暂不支持，直接走 OBB

    async def execute(self, symbol: str, days: int) -> Tuple[pd.DataFrame, Dict[str, Any], str]:
        """
        🚨 业务阻断：目前 A 股业务暂未上线
        """
        print(f"  [CN Strategy] Business logic for A-share {symbol} is pending implementation. Skipping fetch.")
        # 直接返回空结果，不发起网络请求
        return pd.DataFrame(), {}, "none"

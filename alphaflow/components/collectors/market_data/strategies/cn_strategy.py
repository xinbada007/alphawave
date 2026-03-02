"""CN Market Strategy - A股编排"""
import pandas as pd
from typing import List, Tuple, Dict, Any

from .base import BaseMarketStrategy
from ..fetchers.base import BaseMarketFetcher
from ..fetchers.akshare_cn_fetcher import AkShareCNFetcher
from ..fetchers.obb_fetcher import OBBFetcher


class CNMarketStrategy(BaseMarketStrategy):
    """
    A股策略
    使用 AkShare 获取价格数据，OBB 获取指标数据（降级）
    """
    
    def __init__(self):
        self.ak = AkShareCNFetcher()
        self.obb = OBBFetcher(provider="yfinance")

    def get_price_chain(self) -> List[BaseMarketFetcher]:
        return [self.ak, self.obb]

    def get_metrics_chain(self) -> List[BaseMarketFetcher]:
        return [self.obb]  # A股指标 AkShare 暂不支持，直接走 OBB

    async def execute(self, symbol: str, days: int) -> Tuple[pd.DataFrame, Dict[str, Any], str]:
        """
        A股策略执行：技术面 + 基本面
        
        流程：
        1. 尝试 AkShare 获取价格数据
        2. 失败则降级到 OBB
        3. 获取指标数据（OBB 降级）
        """
        price_df = pd.DataFrame()
        metrics = {}
        used_provider = "none"

        # Step 1: 获取价格数据 (AkShare 优先)
        try:
            price_df = await self.ak.fetch_price(symbol, days)
            if not price_df.empty:
                used_provider = "akshare_cn"
                print(f"  [CN Strategy] Price fetched via AkShare ({len(price_df)} bars)")
            else:
                raise ValueError("AkShare returned empty DataFrame")
        except Exception as e:
            print(f"  [CN Strategy] AkShare failed: {e}")
            # 降级到 OBB
            try:
                price_df = await self.obb.fetch_price(symbol, days)
                if not price_df.empty:
                    used_provider = "obb"
                    print(f"  [CN Strategy] Price fetched via OBB fallback ({len(price_df)} bars)")
            except Exception as e2:
                print(f"  [CN Strategy] OBB fallback also failed: {e2}")
                return pd.DataFrame(), {}, "none"

        # Step 2: 获取指标数据 (OBB 降级)
        try:
            metrics = await self.obb.fetch_metrics(symbol)
            if metrics:
                print(f"  [CN Strategy] Metrics fetched: {list(metrics.keys())}")
        except Exception as e:
            print(f"  [CN Strategy] Metrics fetch failed (non-critical): {e}")

        return price_df, metrics, used_provider

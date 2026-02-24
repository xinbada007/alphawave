"""US Market Strategy - 美股编排"""
from typing import List, Dict, Any, Optional
from .base import BaseMarketStrategy
from ..fetchers.base import BaseMarketFetcher
from ..fetchers.obb_fetcher import OBBFetcher

class USMarketStrategy(BaseMarketStrategy):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        provider = config.get("provider", "yfinance") if config else "yfinance"
        self.obb = OBBFetcher(provider=provider)
        # 备用：强制使用 yfinance 兜底（如果主 provider 是 polygon 等）
        self.yf_backup = OBBFetcher(provider="yfinance")

    def get_price_chain(self) -> List[BaseMarketFetcher]:
        return [self.obb, self.yf_backup]

    def get_metrics_chain(self) -> List[BaseMarketFetcher]:
        return [self.obb, self.yf_backup]

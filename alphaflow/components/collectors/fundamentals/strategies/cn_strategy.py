"""
CN Market Strategy - A股市场策略
A股：纯 AkShare
"""
from typing import Dict, List

from .base import BaseMarketStrategy
from ..fetchers.akshare_cn_fetcher import AkShareCNFetcher


class CNMarketStrategy(BaseMarketStrategy):
    """A股编排策略：待实现 AkShareCNFetcher"""
    
    def __init__(self):
        self.ak = AkShareCNFetcher()
    
    def build_routing_table(self) -> Dict[str, List]:
        """A股路由表 - 暂不支持，待 AkShareCNFetcher 实现后填充"""
        print("[CN] A股策略待实现: 需实现 AkShareCNFetcher")
        # 返回空路由表
        return {}

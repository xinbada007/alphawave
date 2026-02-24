"""
CN Market Strategy - A股市场策略
A股：纯 AkShare
"""
from typing import Dict, List

from .base import BaseMarketStrategy
from ..fetchers.akshare_fetcher import AkShareFetcher


class CNMarketStrategy(BaseMarketStrategy):
    """A股编排策略：待实现 AkShareCNFetcher"""
    
    def __init__(self):
        # TODO: 等 AkShareCNFetcher 实现后替换
        pass
    
    def build_routing_table(self) -> Dict[str, List]:
        """A股路由表 - 暂不支持，待添加 AkShareCNFetcher"""
        print("[CN] A股策略待实现: 需添加 AkShareCNFetcher")
        # 返回空路由表
        return {}

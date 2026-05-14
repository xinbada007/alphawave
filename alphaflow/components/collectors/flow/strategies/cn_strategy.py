"""CN Flow Strategy — block_trade + lhb 双子源。"""
from __future__ import annotations

from typing import List

from ..fetchers.akshare_block_trade import AkShareBlockTradeFetcher
from ..fetchers.akshare_lhb import AkShareLHBFetcher
from ..fetchers.base import BaseFlowFetcher
from .base import BaseFlowStrategy


class CNFlowStrategy(BaseFlowStrategy):
    def __init__(self):
        self._block = AkShareBlockTradeFetcher()
        self._lhb = AkShareLHBFetcher()

    def get_fetchers(self) -> List[BaseFlowFetcher]:
        return [self._block, self._lhb]

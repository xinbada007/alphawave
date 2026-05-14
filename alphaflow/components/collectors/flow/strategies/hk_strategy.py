"""HK Flow Strategy — 仅 southbound（第一版占位，无历史接口）。"""
from __future__ import annotations

from typing import List

from ..fetchers.akshare_southbound import AkShareSouthboundFetcher
from ..fetchers.base import BaseFlowFetcher
from .base import BaseFlowStrategy


class HKFlowStrategy(BaseFlowStrategy):
    def __init__(self):
        self._sb = AkShareSouthboundFetcher()

    def get_fetchers(self) -> List[BaseFlowFetcher]:
        return [self._sb]

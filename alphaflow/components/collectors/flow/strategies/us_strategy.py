"""US Flow Strategy — 第一版无可用资金流子源，显式占位。"""
from __future__ import annotations

from typing import List

from ..fetchers.base import BaseFlowFetcher
from .base import BaseFlowStrategy


class USFlowStrategy(BaseFlowStrategy):
    """美股第一版无 flow source；保留类以维持市场清单完整 + 显式留痕。"""

    def get_fetchers(self) -> List[BaseFlowFetcher]:
        return []

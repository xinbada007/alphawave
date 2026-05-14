"""
DistributionPatternAnalyzer — 装饰器注册的薄壳
==============================================
仅做两件事：
  1. 通过 @TechnicalAnalyzerRegistry.register 注册到全局 registry
  2. 桥接到 DistributionPatternProfiler（真正的业务编排器）

设计原则：与 VolumeAnomalyAnalyzer 同构。
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

import pandas as pd

from alphaflow.core.schema import ResearchPack
from alphaflow.core.utils import get_market_type

from ...base import BaseTechnicalAnalyzer
from ...registry import TechnicalAnalyzerRegistry
from .profiler import DistributionPatternProfiler


@TechnicalAnalyzerRegistry.register
class DistributionPatternAnalyzer(BaseTechnicalAnalyzer):
    """派发型价格形态 — CLV / VWAP-deviation / Amihud illiquidity。"""

    namespace = "distribution_pattern_profile"
    depends_on = ()
    # close/high/low 是必备列；vwap/amount/volume 由 profiler 自适应 fallback
    required_columns = ("close", "high", "low")

    def __init__(self, config=None):
        super().__init__(config)
        self._profiler = DistributionPatternProfiler(self.config.get("distribution_pattern"))

    def compute(
        self,
        df: pd.DataFrame,
        pack: ResearchPack,
        upstream: Mapping[str, Any],
    ) -> Dict[str, Any]:
        market_type = get_market_type(pack.symbol) if pack and pack.symbol else None
        return self._profiler.analyze(df, market_type=market_type)

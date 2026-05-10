"""
VolumeAnomalyAnalyzer — 装饰器注册的薄壳
==========================================
仅做两件事：
  1. 通过 @TechnicalAnalyzerRegistry.register 注册到全局 registry
  2. 桥接到 VolumeAnomalyProfiler（真正的业务编排器）

设计原则：
  - 单一职责：本文件只是"集成层"，业务逻辑全在 profiler.py
  - 低耦合：profiler 不知 registry / BaseTechnicalAnalyzer 的存在
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

import pandas as pd

from alphaflow.core.schema import ResearchPack
from alphaflow.core.utils import get_market_type

from ...base import BaseTechnicalAnalyzer
from ...registry import TechnicalAnalyzerRegistry
from .profiler import VolumeAnomalyProfiler


@TechnicalAnalyzerRegistry.register
class VolumeAnomalyAnalyzer(BaseTechnicalAnalyzer):
    """量价异常剖面 — 多周期 + 多维度（volume / amount / turnover_rate，市场感知）。"""

    namespace = "volume_anomaly_profile"
    depends_on = ()
    required_columns = ("close",)  # 量纲列由 DimensionResolver 自适应

    def __init__(self, config=None):
        super().__init__(config)
        self._profiler = VolumeAnomalyProfiler(self.config.get("volume_anomaly"))

    def compute(
        self,
        df: pd.DataFrame,
        pack: ResearchPack,
        upstream: Mapping[str, Any],
    ) -> Dict[str, Any]:
        market_type = get_market_type(pack.symbol) if pack and pack.symbol else None
        return self._profiler.analyze(df, market_type=market_type)

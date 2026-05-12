"""
MarketPressureTimelineAnalyzer — registry thin shell.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

import pandas as pd

from alphaflow.core.schema import ResearchPack
from alphaflow.core.utils import get_market_type

from ...base import BaseTechnicalAnalyzer
from ...registry import TechnicalAnalyzerRegistry
from .profiler import MarketPressureTimelineProfiler


@TechnicalAnalyzerRegistry.register
class MarketPressureTimelineAnalyzer(BaseTechnicalAnalyzer):
    """Objective market-pressure event timeline from OHLCV and optional benchmark data."""

    namespace = "market_pressure_timeline_profile"
    depends_on = ()
    required_columns = ("close", "high", "low")

    def __init__(self, config=None):
        super().__init__(config)
        self._profiler = MarketPressureTimelineProfiler(self.config.get("market_pressure_timeline"))

    def compute(
        self,
        df: pd.DataFrame,
        pack: ResearchPack,
        upstream: Mapping[str, Any],
    ) -> Dict[str, Any]:
        benchmark_df = (
            pack.benchmark_data.to_df()
            if pack and pack.benchmark_data is not None
            else None
        )
        benchmark_meta = pack.benchmark_meta if pack else None
        market_type = get_market_type(pack.symbol) if pack and pack.symbol else None
        return self._profiler.analyze(
            stock_df=df,
            benchmark_df=benchmark_df,
            benchmark_meta=benchmark_meta,
            market_type=market_type,
        )

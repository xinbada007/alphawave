"""
MarketRelativeAnomalyAnalyzer — 装饰器注册的薄壳
=================================================
@TechnicalAnalyzerRegistry.register 注册到全局 registry；
桥接到 MarketRelativeAnomalyProfiler；从 ResearchPack 提取 benchmark_data / benchmark_meta。
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

import pandas as pd

from alphaflow.core.schema import ResearchPack
from alphaflow.core.utils import get_market_type

from ...base import BaseTechnicalAnalyzer
from ...registry import TechnicalAnalyzerRegistry
from .profiler import MarketRelativeAnomalyProfiler


@TechnicalAnalyzerRegistry.register
class MarketRelativeAnomalyAnalyzer(BaseTechnicalAnalyzer):
    """市场相对异常 — rel_volume / rel_return / index_anomalous。"""

    namespace = "market_relative_anomaly_profile"
    depends_on = ()
    required_columns = ("close", "volume")

    def __init__(self, config=None):
        super().__init__(config)
        self._profiler = MarketRelativeAnomalyProfiler(self.config.get("market_relative_anomaly"))

    def compute(
        self,
        df: pd.DataFrame,
        pack: ResearchPack,
        upstream: Mapping[str, Any],
    ) -> Dict[str, Any]:
        # 从 ResearchPack 取 benchmark；缺失时 profiler 自动 Null Object 降级
        benchmark_df = (pack.benchmark_data.to_df()
                        if pack and pack.benchmark_data is not None else None)
        benchmark_meta = pack.benchmark_meta if pack else None
        market_type = get_market_type(pack.symbol) if pack and pack.symbol else None

        return self._profiler.analyze(
            stock_df=df,
            benchmark_df=benchmark_df,
            benchmark_meta=benchmark_meta,
            market_type=market_type,
        )

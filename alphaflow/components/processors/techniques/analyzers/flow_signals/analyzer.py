"""
FlowSignalsAnalyzer — 装饰器注册的薄壳
=========================================
@TechnicalAnalyzerRegistry.register；从 pack.flow_data + flow_meta 取数。
namespace 与 Phase 6 中 cfg.UPSTREAM_NAMESPACES[COMPONENT_FLOW] 完全对齐
("flow_signals_profile")，Phase 6 升级即生效。
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

import pandas as pd

from alphaflow.core.schema import ResearchPack
from alphaflow.core.utils import get_market_type

from ...base import BaseTechnicalAnalyzer
from ...registry import TechnicalAnalyzerRegistry
from .profiler import FlowSignalsProfiler


@TechnicalAnalyzerRegistry.register
class FlowSignalsAnalyzer(BaseTechnicalAnalyzer):
    """资金流剖面 — block_trade / lhb / southbound 三子源（按市场可用性降级）。"""

    namespace = "flow_signals_profile"
    depends_on = ()
    required_columns = ()  # 不依赖 OHLCV，独立子树

    def __init__(self, config=None):
        super().__init__(config)
        self._profiler = FlowSignalsProfiler(self.config.get("flow_signals"))

    def compute(
        self,
        df: pd.DataFrame,
        pack: ResearchPack,
        upstream: Mapping[str, Any],
    ) -> Dict[str, Any]:
        flow_data_models = pack.flow_data if pack else None
        # DataFrameModel → pandas.DataFrame
        flow_data = (
            {k: v.to_df() for k, v in flow_data_models.items()}
            if flow_data_models else None
        )
        flow_meta = pack.flow_meta if pack else None
        market_type_str = (
            get_market_type(pack.symbol).value if pack and pack.symbol else None
        )
        return self._profiler.analyze(
            flow_data=flow_data,
            flow_meta=flow_meta,
            market_type=market_type_str,
        )

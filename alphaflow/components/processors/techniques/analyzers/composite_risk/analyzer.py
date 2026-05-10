"""
CompositeRiskAnalyzer — 装饰器注册的薄壳
==========================================
@TechnicalAnalyzerRegistry.register 注册到全局 registry。
通过 depends_on 声明对三个上游 profile 的依赖，registry 拓扑排序保证执行序。
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

import pandas as pd

from alphaflow.core.schema import ResearchPack

from ...base import BaseTechnicalAnalyzer
from ...registry import TechnicalAnalyzerRegistry
from . import config as cfg
from .scorer import CompositeRiskScorer


@TechnicalAnalyzerRegistry.register
class CompositeRiskAnalyzer(BaseTechnicalAnalyzer):
    """
    综合派发风险评分（4 子分加权 + 4 道闸门）。

    通过 depends_on 拿到上游 profile payload；上游缺席（namespace 不在 upstream）时
    .get() 容错，scorer 内部走重分配。完美抗漂移。
    """

    namespace = "composite_risk_profile"
    depends_on = (
        cfg.UPSTREAM_NAMESPACES[cfg.COMPONENT_VOLUME],
        cfg.UPSTREAM_NAMESPACES[cfg.COMPONENT_DISTRIBUTION],
        cfg.UPSTREAM_NAMESPACES[cfg.COMPONENT_MARKET_REL],
        cfg.UPSTREAM_NAMESPACES[cfg.COMPONENT_FLOW],  # Phase 7
    )
    # M3：composite_risk 的 compute() 完全不读 df，仅读 upstream profiles。
    # 不声明列依赖 → 未来"无 OHLCV 但有 flow_data"的量化场景下，
    # 不会被 _meets_prerequisites 错杀降级。
    required_columns = ()

    def __init__(self, config=None):
        super().__init__(config)
        self._scorer = CompositeRiskScorer()

    def compute(
        self,
        df: pd.DataFrame,
        pack: ResearchPack,
        upstream: Mapping[str, Any],
    ) -> Dict[str, Any]:
        return self._scorer.score(
            volume_anomaly       = upstream.get(cfg.UPSTREAM_NAMESPACES[cfg.COMPONENT_VOLUME]),
            distribution_pattern = upstream.get(cfg.UPSTREAM_NAMESPACES[cfg.COMPONENT_DISTRIBUTION]),
            market_relative      = upstream.get(cfg.UPSTREAM_NAMESPACES[cfg.COMPONENT_MARKET_REL]),
            flow_signals         = upstream.get(cfg.UPSTREAM_NAMESPACES[cfg.COMPONENT_FLOW]),
        )

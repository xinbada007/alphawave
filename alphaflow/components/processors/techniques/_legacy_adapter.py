"""
Legacy Market Analyzer Adapter
================================
保护 market_analyzer.py 字节级零侵入的同时，将其纳入 TechnicalAnalyzerRegistry。

设计模式：Adapter
  - 不修改 MultiTimeframeMarketAnalyzer 任何一行
  - 仅做接口转换：BaseTechnicalAnalyzer.compute() ↔ MultiTimeframeMarketAnalyzer.analyze()
  - 输出剥掉外层 "technical_and_sentiment" 包装，作为顶层合并（namespace=""）

为什么 namespace=""？
  原版 analyze() 返回 {market_summary, timeframes, liquidity_and_volume} 三个顶层 key，
  都直接挂在 distilled_features.technical 下。沿用这一布局保证 LLM view byte-level 不变。
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

import pandas as pd

from alphaflow.core.schema import ResearchPack

from .base import BaseTechnicalAnalyzer
from .market_analyzer import MultiTimeframeMarketAnalyzer
from .registry import TechnicalAnalyzerRegistry


@TechnicalAnalyzerRegistry.register
class LegacyMarketAnalyzer(BaseTechnicalAnalyzer):
    """适配老 MultiTimeframeMarketAnalyzer 进入新 registry 体系。"""

    namespace = ""              # 顶层合并：market_summary / timeframes / liquidity_and_volume
    depends_on = ()
    # 不声明 required_columns：让老 analyzer 自己处理列缺失情况（保持原行为）

    def __init__(self, config=None):
        super().__init__(config)
        self._inner = MultiTimeframeMarketAnalyzer(self.config)

    def compute(
        self,
        df: pd.DataFrame,           # 未使用：老 analyzer 直接从 pack.market_data 读
        pack: ResearchPack,
        upstream: Mapping[str, Any],
    ) -> Dict[str, Any]:
        result = self._inner.analyze(pack)
        return result.get("technical_and_sentiment", {}) if result else {}

"""
Market Relative Anomaly Analyzer (Phase 5)
============================================
个股相对大盘的异常剖面：rel_volume / rel_return / index_anomalous。

模块边界（与 volume_anomaly / distribution_pattern 同构）：
- config    : tier 阈值 / 滚动窗口 / [BRACKET] tag 常量
- metrics   : 纯函数算子（alignment / compute / classify / aggregate）
- profiler  : 编排器，组装 data_quality + latest_day + rolling + summary
- analyzer  : 薄壳，@register 装饰，桥接到 profiler
"""
from __future__ import annotations

from .analyzer import MarketRelativeAnomalyAnalyzer  # noqa: F401  触发装饰器注册
from .profiler import MarketRelativeAnomalyProfiler  # noqa: F401

__all__ = ["MarketRelativeAnomalyAnalyzer", "MarketRelativeAnomalyProfiler"]

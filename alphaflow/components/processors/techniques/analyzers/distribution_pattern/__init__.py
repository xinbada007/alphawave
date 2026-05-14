"""
Distribution Pattern Analyzer (Phase 4)
========================================
派发型价格形态：CLV / VWAP-deviation / Amihud illiquidity。

模块边界（与 volume_anomaly 同构）：
- config    : 阈值表 / 窗口 / source 标签 (纯数据)
- metrics   : 纯函数算子 + VWAP / dollar_volume 来源解析 (Strategy/Null Object)
- profiler  : 编排器，组装 data_quality + 三个指标子树 + summary
- analyzer  : 薄壳，@TechnicalAnalyzerRegistry.register 装饰，桥接到 profiler
"""
from __future__ import annotations

# 触发装饰器注册（导入即注册到 TechnicalAnalyzerRegistry）
from .analyzer import DistributionPatternAnalyzer  # noqa: F401
from .profiler import DistributionPatternProfiler  # noqa: F401

__all__ = ["DistributionPatternAnalyzer", "DistributionPatternProfiler"]

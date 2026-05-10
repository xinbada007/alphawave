"""
Volume Anomaly factor analyzer
================================
单股、多周期的量价异常剖面引擎，作为 TechnicalAnalyzerRegistry 中的一个 analyzer。

模块边界（高内聚）：
- config       : 阈值、lookback 窗口、维度→列名映射 (纯数据)
- metrics      : 纯函数式数学算子（baseline / classification / aggregation / data_quality 四区段）
- profiler     : 单维度编排器（接受 config 注入，不 import 常量 → 低耦合）
- analyzer     : 薄壳，@TechnicalAnalyzerRegistry.register 装饰，桥接到 profiler

设计原则验证：
- 高内聚：每模块单一职责
- 低耦合：profiler 不依赖 ResearchPack；analyzer 不直接做数学
- 开闭原则：加新阈值改 config；加新维度改 DIMENSIONS 元组
- 审美一致：与 MetricEngine 的装饰器注册风格对称
"""
# 触发装饰器注册（导入即注册到 TechnicalAnalyzerRegistry）
from .analyzer import VolumeAnomalyAnalyzer  # noqa: F401
from .profiler import VolumeAnomalyProfiler  # noqa: F401

__all__ = ["VolumeAnomalyAnalyzer", "VolumeAnomalyProfiler"]

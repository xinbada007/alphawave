"""
技术面分析子模块 (Techniques)
=============================
专注于市场数据的量化分析，包括多时间框架技术指标计算与语义降维。

V4 架构：引入 TechnicalAnalyzerRegistry，与基本面 MetricEngine 哲学对称。
新增技术因子 = 在 analyzers/ 下建子目录 + @register 装饰，pipeline 永不再动。
"""

from alphaflow.components.processors.techniques.market_analyzer import (
    MultiTimeframeMarketAnalyzer,
)
from alphaflow.components.processors.techniques.base import (
    AnalyzerResult,
    BaseTechnicalAnalyzer,
)
from alphaflow.components.processors.techniques.registry import (
    TechnicalAnalyzerRegistry,
)

__all__ = [
    "MultiTimeframeMarketAnalyzer",
    "BaseTechnicalAnalyzer",
    "AnalyzerResult",
    "TechnicalAnalyzerRegistry",
]

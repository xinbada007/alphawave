"""
技术面分析子模块 (Techniques)
=============================
专注于市场数据的量化分析，包括多时间框架技术指标计算与语义降维。

使用 pandas-ta-openbb 作为底层计算引擎，实现零手写公式的优雅架构。
"""

from alphaflow.components.processors.techniques.market_analyzer import (
    MultiTimeframeMarketAnalyzer,
)

__all__ = [
    "MultiTimeframeMarketAnalyzer",
]

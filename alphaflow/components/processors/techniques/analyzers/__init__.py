"""
Technical Analyzers Registration Hub
=====================================
导入所有 analyzer 子模块，触发 @TechnicalAnalyzerRegistry.register 装饰器副作用。

模式来源：alphaflow.components.processors.metrics.__init__
  那里用同样的 `from . import xxx  # noqa: F401` 触发 @MetricEngine.fundamental_metric
  本文件与之严格对称。

新增 analyzer 时只需在此加一行 import。
"""
from . import volume_anomaly  # noqa: F401
from . import distribution_pattern  # noqa: F401  # Phase 4
from . import market_relative_anomaly  # noqa: F401  # Phase 5
from . import flow_signals  # noqa: F401  # Phase 7（必须在 composite_risk 之前注册以使其依赖可见）
from . import market_pressure_timeline  # noqa: F401  # Phase 9 objective event timeline
from . import composite_risk  # noqa: F401  # Phase 6 (depends_on three upstream profiles)

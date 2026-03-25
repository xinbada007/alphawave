"""
声明式指标注册入口 (Metric Registration Hub)
=============================================
导入所有域模块，触发 @MetricEngine.fundamental_metric 装饰器注册。
新增域文件时只需在此加一行 import。
"""

from . import profitability  # noqa: F401
from . import solvency       # noqa: F401
from . import efficiency     # noqa: F401
from . import quality        # noqa: F401
from . import growth         # noqa: F401
from . import valuation      # noqa: F401
from . import cash_flow      # noqa: F401

"""
AlphaFlow Fundamentals Module - 财务数据采集模块
===========================================

双层架构：
- Fetchers (数据源层): AkShare, OpenBB, YFinance 原生
- Strategies (编排层): US/CN/HK 市场策略 + 声明式路由责任链

使用示例:
    from alphaflow.components.collectors.fundamentals import FundamentalCollector
    
    collector = FundamentalCollector("fundamental")
    result = await collector.fetch_data(context)
"""
from .collector import FundamentalCollector
from .helpers import get_fx_rate, audit_currency_context

# 导出主要类
__all__ = [
    "FundamentalCollector",
    "get_fx_rate",
    "audit_currency_context",
]

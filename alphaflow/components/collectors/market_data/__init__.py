"""
Market Data Collector Module - 市场数据采集模块
===========================================

架构：
- Fetchers (原子层): AkShareHK, AkShareCN, OpenBB (YFinance)
- Strategies (编排层): HK/CN/US 市场策略 + 双轨并发责任链

使用示例:
    from alphaflow.components.collectors.market_data import MarketDataCollector
    
    collector = MarketDataCollector("market_data")
    result = await collector.fetch_data(context)
"""

from .collector import MarketDataCollector

__all__ = ["MarketDataCollector"]

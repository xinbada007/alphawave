"""
Benchmark Collector Package
============================
大盘指数采集（Phase 5）。第一版支持 HK→^HSI / CN→沪深300 / US→SPY。

模块边界：
- fetchers/    : 每个 provider × 每个指数一个 fetcher
- strategies/  : 按市场路由 + Chain of Responsibility
- collector.py : 调度入口，注入 pack.benchmark_data / benchmark_meta，缓存复用
"""
from .collector import BenchmarkCollector

__all__ = ["BenchmarkCollector"]

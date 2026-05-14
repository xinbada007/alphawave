"""
BenchmarkCollector — 大盘指数采集枢纽
=====================================
按 symbol 推断市场，路由到对应 BenchmarkStrategy；执行链式 fallback；
将 OHLCV 注入 `pack.benchmark_data`，元信息注入 `pack.benchmark_meta`。

同 run 内复用：通过 GlobalContext 字典 `BENCHMARK_CACHE`，key=(market, days)。
设计与 MarketDataCollector 严格同构（审美一致 / 抗漂移）。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from alphaflow.core.base import BaseCollector
from alphaflow.core.context import GlobalContext
from alphaflow.core.schema import (
    AnalysisContext,
    ComponentOutput,
    DataFrameModel,
    ResearchPack,
)
from alphaflow.core.utils import MarketType, get_market_type

from .strategies.cn_strategy import CNBenchmarkStrategy
from .strategies.hk_strategy import HKBenchmarkStrategy
from .strategies.us_strategy import USBenchmarkStrategy

_CACHE_KEY = "BENCHMARK_CACHE"


class BenchmarkCollector(BaseCollector):
    """大盘指数采集器（HK→^HSI / CN→沪深300 / US→SPY）。"""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.strategies = {
            MarketType.HK: HKBenchmarkStrategy(),
            MarketType.CN: CNBenchmarkStrategy(),
            MarketType.US: USBenchmarkStrategy(),
        }

    @staticmethod
    def _cache_get(market: MarketType, days: int):
        ctx = GlobalContext()
        cache = ctx.get(_CACHE_KEY) or {}
        return cache.get((market, days))

    @staticmethod
    def _cache_put(market: MarketType, days: int, payload):
        ctx = GlobalContext()
        cache = ctx.get(_CACHE_KEY) or {}
        cache[(market, days)] = payload
        ctx.set(_CACHE_KEY, cache)

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        pack = self._unpack_pack(context, kwargs)

        target_days = context.metadata.get("days", 250)
        market_type = get_market_type(pack.symbol)

        cached = self._cache_get(market_type, target_days)
        if cached is not None:
            df, used_provider, bench_symbol = cached
            print(f"  [Benchmark] {market_type.name} cache hit "
                  f"({bench_symbol} via {used_provider}, {len(df)} bars)")
        else:
            strategy = self.strategies.get(market_type)
            if strategy is None:
                pack.benchmark_meta = self._unavailable_meta(market_type, "unsupported_market")
                print(f"  [Benchmark] market {market_type.name} not supported, skipped")
                return ComponentOutput(success=True, payload=pack)

            print(f"  [Benchmark] Fetching {market_type.name} index...")
            df, used_provider, bench_symbol = await strategy.execute(target_days)
            # B1 守卫：仅缓存成功结果；空 DF 不缓存 → 下次自动重试，避免失败毒化整个进程
            if df is not None and not df.empty:
                self._cache_put(market_type, target_days, (df, used_provider, bench_symbol))

        if df is None or df.empty:
            pack.benchmark_meta = self._unavailable_meta(market_type, "fetch_failed")
            print(f"  [Benchmark] {market_type.name} unavailable (all fetchers failed)")
            return ComponentOutput(success=True, payload=pack)

        df = df.sort_values("date", kind="mergesort").tail(target_days).reset_index(drop=True)
        pack.benchmark_data = DataFrameModel.from_df(df)
        pack.benchmark_meta = {
            "status": "ok",
            "benchmark_symbol": bench_symbol,
            "source": used_provider,
            "market_type": market_type.value,
            "rows": len(df),
            "columns": df.columns.tolist(),
        }
        print(f"  [Benchmark] {market_type.name} {bench_symbol} via {used_provider} ({len(df)} bars) ✓")
        return ComponentOutput(success=True, payload=pack)

    @staticmethod
    def _unavailable_meta(market_type: MarketType, reason: str) -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "benchmark_symbol": "",
            "source": "none",
            "market_type": market_type.value,
            "reason": reason,
            "rows": 0,
            "columns": [],
        }

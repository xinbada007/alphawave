"""CN Benchmark Strategy — 沪深 300."""
from __future__ import annotations

from typing import List

from ..fetchers.akshare_hs300 import AkShareHS300Fetcher
from ..fetchers.base import BaseBenchmarkFetcher
from ..fetchers.obb_index import OBBIndexFetcher
from .base import BaseBenchmarkStrategy


class CNBenchmarkStrategy(BaseBenchmarkStrategy):
    def __init__(self):
        self.ak = AkShareHS300Fetcher()
        self.obb = OBBIndexFetcher(benchmark_symbol="000300.SS", provider="yfinance")

    def get_index_chain(self) -> List[BaseBenchmarkFetcher]:
        return [self.ak, self.obb]

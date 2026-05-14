"""US Benchmark Strategy — SPY."""
from __future__ import annotations

from typing import List

from ..fetchers.base import BaseBenchmarkFetcher
from ..fetchers.obb_index import OBBIndexFetcher
from .base import BaseBenchmarkStrategy


class USBenchmarkStrategy(BaseBenchmarkStrategy):
    def __init__(self):
        self.spy = OBBIndexFetcher(benchmark_symbol="SPY", provider="yfinance")

    def get_index_chain(self) -> List[BaseBenchmarkFetcher]:
        return [self.spy]

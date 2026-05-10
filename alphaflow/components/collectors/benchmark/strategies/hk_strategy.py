"""HK Benchmark Strategy — ^HSI.

Chain 顺序设计（按"字段完整性"优先，"实时性"次之）：
  1. sina (T-1, 含 volume)  ← market_relative_anomaly 需要 volume，主力
  2. em   (T+0, 无 volume)  ← sina 失效时兜底；OHLC 保住，市场相对分析自动 Null Object 降级
  3. obb  (yfinance)        ← akshare 整体失效时的最终兜底
"""
from __future__ import annotations

from typing import List

from ..fetchers.akshare_hsi import AkShareHSIFetcher
from ..fetchers.akshare_hsi_sina import AkShareHSISinaFetcher
from ..fetchers.base import BaseBenchmarkFetcher
from ..fetchers.obb_index import OBBIndexFetcher
from .base import BaseBenchmarkStrategy


class HKBenchmarkStrategy(BaseBenchmarkStrategy):
    def __init__(self):
        self.sina = AkShareHSISinaFetcher()
        self.em = AkShareHSIFetcher()
        self.obb = OBBIndexFetcher(benchmark_symbol="^HSI", provider="yfinance")

    def get_index_chain(self) -> List[BaseBenchmarkFetcher]:
        return [self.sina, self.em, self.obb]

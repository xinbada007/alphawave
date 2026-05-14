"""AkShareHSIFetcher — 港股恒指 ^HSI（akshare EM 接口）。

数据特性：
- 频率：daily
- 实时性：T+0（当日）
- 字段：date, open, high, low, latest（无 volume）
- 历史长度：约 35 年（1991+）

在 HKBenchmarkStrategy chain 中作为 sina 的 fallback：sina 失效时 OHLC 仍可保住，
market_relative_anomaly 自动 Null Object 降级。
"""
from __future__ import annotations

import akshare as ak  # type: ignore
import pandas as pd

from .akshare_base import AkShareIndexFetcher


class AkShareHSIFetcher(AkShareIndexFetcher):
    name = "AkShare_HSI"
    benchmark_symbol = "^HSI"
    rename_map = {
        "latest": "close",
        "Open": "open", "High": "high", "Low": "low", "Close": "close",
        "Volume": "volume",
    }

    def _ak_call(self) -> pd.DataFrame:
        return ak.stock_hk_index_daily_em(symbol="HSI")

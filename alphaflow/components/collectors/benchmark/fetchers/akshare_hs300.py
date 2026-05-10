"""AkShareHS300Fetcher — A 股沪深 300（akshare EM 接口）。

数据特性：
- 频率：daily
- 实时性：T+0
- 字段：date, open, close, high, low, volume, amount（含 volume）
- 历史长度：约 20 年
"""
from __future__ import annotations

import akshare as ak  # type: ignore
import pandas as pd

from .akshare_base import AkShareIndexFetcher


class AkShareHS300Fetcher(AkShareIndexFetcher):
    name = "AkShare_HS300"
    benchmark_symbol = "000300"
    rename_map = {
        "Date": "date", "Open": "open", "High": "high",
        "Low": "low", "Close": "close", "Volume": "volume",
    }

    def _ak_call(self) -> pd.DataFrame:
        return ak.stock_zh_index_daily_em(symbol="sh000300")

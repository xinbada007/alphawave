"""AkShareHSISinaFetcher — 港股恒指 ^HSI（akshare sina 接口，含 volume）。

数据特性：
- 频率：daily
- 实时性：T-1（滞后 1 个交易日）
- 字段：date, open, high, low, close, volume（6 列完整）
- 历史长度：约 13 年（2013-08+）

被 HKBenchmarkStrategy chain 优先使用，因 EM 接口不返 volume，
量价异常分析（market_relative_anomaly）需要相对量比。
"""
from __future__ import annotations

import akshare as ak  # type: ignore
import pandas as pd

from .akshare_base import AkShareIndexFetcher


class AkShareHSISinaFetcher(AkShareIndexFetcher):
    name = "AkShare_HSI_Sina"
    benchmark_symbol = "^HSI"
    rename_map = {}  # sina 接口列名已是标准小写

    def _ak_call(self) -> pd.DataFrame:
        return ak.stock_hk_index_daily_sina(symbol="HSI")

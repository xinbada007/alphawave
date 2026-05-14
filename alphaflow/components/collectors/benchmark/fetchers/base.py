"""
Base Benchmark Fetcher
=======================
指数行情抓取器的抽象基类。

设计与 BaseMarketFetcher **不继承**：
- 指数没有 PE/PB 等估值快照 → fetch_metrics 契约对指数无意义
- 指数没有 amount 字段 → MarketFetcher 的 vwap enricher 是 dead code path
- 单一职责：本基类只关心 OHLCV 拉取与统一清洗
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional

import pandas as pd

from alphaflow.core.utils import (
    normalize_date_column,
    coerce_numeric_columns,
    dedupe_and_sort_by_date,
)


class BaseBenchmarkFetcher(ABC):
    """指数行情抓取器基类。"""

    name: str = "BaseBenchmarkFetcher"
    benchmark_symbol: str = ""

    @abstractmethod
    async def fetch_index(self, days: int) -> pd.DataFrame:
        """拉取指数 OHLCV，按 date 升序返回；失败返回空 DF（不抛异常）。"""
        raise NotImplementedError

    def _clean_index_df(
        self,
        df: pd.DataFrame,
        rename_map: Optional[Dict[str, str]] = None,
    ) -> pd.DataFrame:
        """
        指数语义：保留 NaN（不像 market_data 回填 0.0），便于上游识别"接口缺列"。
        """
        if df is None or df.empty:
            return pd.DataFrame()

        if rename_map:
            df = df.rename(columns=rename_map)

        df = normalize_date_column(df)
        df = coerce_numeric_columns(
            df,
            columns=("open", "high", "low", "close", "volume"),
            fill_na=None,
        )
        return dedupe_and_sort_by_date(df)

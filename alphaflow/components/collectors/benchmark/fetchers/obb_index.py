"""OBBIndexFetcher — 通用 OpenBB(yfinance) 指数抓取器。"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pandas as pd
from openbb import obb  # type: ignore

from .base import BaseBenchmarkFetcher

obb_any: Any = obb


class OBBIndexFetcher(BaseBenchmarkFetcher):
    _semaphore = asyncio.Semaphore(3)

    def __init__(self, benchmark_symbol: str, provider: str = "yfinance"):
        self.benchmark_symbol = benchmark_symbol
        self.provider = provider
        self.name = f"OBB_{provider}_{benchmark_symbol}"

    async def fetch_index(self, days: int) -> pd.DataFrame:
        start_date = (datetime.now() - pd.Timedelta(days=int(days * 1.6))).strftime("%Y-%m-%d")
        async with self._semaphore:
            try:
                res = await asyncio.to_thread(
                    obb_any.equity.price.historical,
                    symbol=self.benchmark_symbol,
                    provider=self.provider,
                    start_date=start_date,
                )
            except Exception as e:
                print(f"  [{self.name}] fetch_index failed: {str(e)[:80]}")
                return pd.DataFrame()

            if not res or not getattr(res, "results", None):
                return pd.DataFrame()

            df = pd.DataFrame([it.dict() if hasattr(it, "dict") else vars(it)
                               for it in res.results])
            for c in ("dividends", "stock_splits", "dividend", "split_ratio",
                      "capital_gains", "vwap"):
                if c in df.columns:
                    df = df.drop(columns=[c])
            return self._clean_index_df(df, rename_map={})

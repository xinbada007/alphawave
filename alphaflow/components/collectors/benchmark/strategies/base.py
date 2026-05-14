"""
Base Benchmark Strategy
========================
按市场路由 + Chain of Responsibility 兜底链。
设计与 BaseMarketStrategy 同构（审美一致），但只有 index chain（无 metrics chain）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple

import pandas as pd

from ..fetchers.base import BaseBenchmarkFetcher


class BaseBenchmarkStrategy(ABC):
    """指数抓取策略基类（chain fallback）。"""

    @abstractmethod
    def get_index_chain(self) -> List[BaseBenchmarkFetcher]:
        """定义指数抓取的责任链（按优先级排列）。"""
        raise NotImplementedError

    async def execute(self, days: int) -> Tuple[pd.DataFrame, str, str]:
        """Returns: (index_df, used_provider_name, benchmark_symbol)。失败时三元组为 (空 DF, 'none', '')。"""
        chain = self.get_index_chain()
        for fetcher in chain:
            try:
                df = await fetcher.fetch_index(days)
                if df is not None and not df.empty:
                    return df, fetcher.name, fetcher.benchmark_symbol
            except Exception as e:
                print(f"  [Benchmark Fallback] {fetcher.name} failed: {str(e)[:60]}")
                continue
        return pd.DataFrame(), "none", ""

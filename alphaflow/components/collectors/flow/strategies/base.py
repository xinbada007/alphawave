"""
Base Flow Strategy
===================
按市场路由到一组 FlowFetcher（每子源一个）。
与 BaseBenchmarkStrategy 同构，但本策略**真正并行**执行多个子源
（asyncio.gather + return_exceptions=True，每子源独立异常隔离 → 异构 dict 装配）。
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

import pandas as pd

from ..fetchers.base import BaseFlowFetcher


class BaseFlowStrategy(ABC):
    """资金流策略基类。"""

    @abstractmethod
    def get_fetchers(self) -> List[BaseFlowFetcher]:
        """该市场支持的所有资金流子源 fetcher。"""
        raise NotImplementedError

    async def execute(self, symbol: str, days: int) -> Tuple[Dict[str, pd.DataFrame], Dict[str, dict]]:
        """
        Returns:
          - data: {source_key: DataFrame}（仅含非空 DF）
          - status: {source_key: {"status": "ok"|"unavailable", ...}}

        实现：所有子源 fetcher 通过 asyncio.gather 并行执行；任一子源
        异常被 return_exceptions=True 捕获，不影响其他子源。
        """
        fetchers = self.get_fetchers()
        if not fetchers:
            return {}, {}

        results = await asyncio.gather(
            *(fetcher.fetch(symbol, days) for fetcher in fetchers),
            return_exceptions=True,
        )

        data: Dict[str, pd.DataFrame] = {}
        status: Dict[str, dict] = {}
        for fetcher, result in zip(fetchers, results):
            key = fetcher.source_key
            if isinstance(result, BaseException):
                status[key] = {
                    "status": "unavailable", "source": fetcher.name,
                    "reason": f"{type(result).__name__}: {str(result)[:60]}",
                }
                continue

            df = result
            if df is None or df.empty:
                status[key] = {
                    "status": "unavailable", "source": fetcher.name,
                    "reason": "no_data",
                }
                continue

            data[key] = df
            status[key] = {
                "status": "ok", "source": fetcher.name,
                "rows": len(df), "columns": df.columns.tolist(),
            }
        return data, status

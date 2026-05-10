"""
Base Flow Fetcher
==================
资金流子源抓取器抽象基类。

设计与 BaseBenchmarkFetcher 同构（不继承 BaseMarketFetcher）：
- 资金流子源不是 OHLCV，没有 vwap / amount 概念
- 不同子源结构异构（南向是日级聚合，大宗是逐笔，龙虎榜是事件）
- 单一职责：本基类只声明 fetch 契约，不做清洗（清洗放在子类中视形态而定）

每个 fetcher 返回的 DF 应至少包含 'date' 列（统一时间锚点），其余字段由子源决定。
失败时返回空 DF，不抛异常。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from alphaflow.core.utils import normalize_date_column


class BaseFlowFetcher(ABC):
    """资金流子源抓取器基类。"""

    name: str = "BaseFlowFetcher"
    source_key: str = ""  # 写入 flow_data dict 的 key（如 "block_trade" / "lhb" / "southbound"）

    @abstractmethod
    async def fetch(self, symbol: str, days: int) -> pd.DataFrame:
        """
        按 symbol 拉取该子源最近 `days` 天的数据。

        统一约定：
        - 必须含 'date' 列（datetime64）
        - 字段名小写英文（与项目其他 fetcher 一致）
        - 失败 / 无数据 → 返回空 DataFrame，**不**抛异常
        """
        raise NotImplementedError

    @staticmethod
    def _ensure_date_col(
        df: pd.DataFrame,
        candidates=("date", "Date", "DATE", "交易日期", "上榜日", "日期"),
    ) -> pd.DataFrame:
        """flow 子源 date 列归一（薄包装，保留方法以维持子类调用兼容）。"""
        return normalize_date_column(df, candidates=candidates)

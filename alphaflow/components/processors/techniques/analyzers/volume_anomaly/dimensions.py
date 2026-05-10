"""
Volume Anomaly · Dimension Resolver
====================================
单一职责：决定本次量价异常剖面用**哪些维度**、**哪个为主信号**。

设计哲学
--------
- **表驱动**：market → primary_dimension 的映射、fallback chain 全在 config.py 的常量表
  里，加新市场/新维度不改本文件。
- **纯函数**：本模块仅依赖 columns 集合 + market_type 枚举；不知 DataFrame、不知 metrics、
  不知 ResearchPack。无 IO，无副作用，无异常。
- **降级有序**：首选维度若在该 symbol 上不可得，按 fallback chain 逐级降级，最终保证
  至少返回 'volume'（任何 OHLCV 数据源都有 volume）。
- **零侵入**：profiler 的对外签名仍向后兼容（market_type=None 等价于旧"按 DIMENSIONS 顺序"
  行为）。

抗漂移说明
----------
本文件是 Phase 5 (市场相对归一化) / Phase 6 (综合派发风险评分) 的**共用入口**：
后续阶段判断"该 symbol 哪些维度可用 / 主信号是什么"必须复用 DimensionResolver，
绝不可在 metrics.py / profiler.py / 别的 analyzer 里出现第二份"if market == HK"。
"""
from __future__ import annotations

from typing import Iterable, List, Mapping, Optional, Tuple

from alphaflow.core.acl.mappings.enums import MarketType

from .config import (
    DIMENSIONS,
    MARKET_DIMENSION_FALLBACK,
    MARKET_PRIMARY_DIMENSION,
)


class DimensionResolver:
    """
    决定 (active_dimensions, primary_dimension_key, market_type_label) 三元组。

    用法
    ----
    >>> active, primary, mlabel = DimensionResolver.resolve(
    ...     available_columns={"close", "volume", "amount", "turnover_rate"},
    ...     market_type=MarketType.HK,
    ... )
    >>> primary
    'amount'

    约定
    ----
    - active_dimensions: list[Mapping]，元素结构与 DIMENSIONS 相同 ({"key": ..., "column": ...})
      仅保留 column 在 available_columns 中存在的项；保留全表的相对顺序。
    - primary_dimension_key: str。按 MARKET_PRIMARY_DIMENSION[market_type] 选首选；
      若首选 column 缺失，沿 MARKET_DIMENSION_FALLBACK[market_type] 逐项降级；
      最终至少返回 'volume'。
    - market_type_label: str — MarketType.value (e.g. "hk"/"cn"/"us"/"unknown")。
    - market_type=None / MarketType.UNKNOWN: 退化为"按 DIMENSIONS 表序首个可得维度"，
      保持与 Phase 1 完全一致的行为（向后兼容）。
    """

    @staticmethod
    def resolve(
        available_columns: Iterable[str],
        market_type: Optional[MarketType] = None,
        all_dimensions: Tuple[Mapping[str, str], ...] = DIMENSIONS,
    ) -> Tuple[List[Mapping[str, str]], str, str]:
        cols = set(available_columns)

        # 1) 过滤可用维度，保留 DIMENSIONS 相对顺序
        active: List[Mapping[str, str]] = [
            dict(d) for d in all_dimensions if d.get("column") in cols
        ]

        # 2) 选 primary_dimension_key
        primary = DimensionResolver._select_primary(active, market_type)

        # 3) market_type label（统一字符串）
        mlabel = (market_type.value if isinstance(market_type, MarketType)
                  else MarketType.UNKNOWN.value)

        return active, primary, mlabel

    # -------------------------------------------------------------- internal
    @staticmethod
    def _select_primary(
        active: List[Mapping[str, str]],
        market_type: Optional[MarketType],
    ) -> str:
        """按 market policy + fallback chain 选 primary。"""
        active_keys = [d["key"] for d in active]
        if not active_keys:
            # 没有任何可用维度 — 上游 profiler 会再降级到 data_quality-only
            return ""

        # market 未知 → 退化为表序首个（向后兼容 Phase 1 行为）
        if market_type is None or market_type == MarketType.UNKNOWN:
            return active_keys[0]

        # 首选
        preferred = MARKET_PRIMARY_DIMENSION.get(market_type)
        if preferred and preferred in active_keys:
            return preferred

        # fallback chain
        for candidate in MARKET_DIMENSION_FALLBACK.get(market_type, ()):
            if candidate in active_keys:
                return candidate

        # 最终兜底
        return active_keys[0]


__all__ = ["DimensionResolver"]

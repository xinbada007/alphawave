"""
Enricher Registry - 默认派生列计算器注册表
============================================
顺序约定：依赖者必须排在被依赖者之后。

使用 tuple（而非 list）以防止运行时意外变异；如需扩展请在子类
fetcher 中通过 ClassVar 覆写 enrichers 类变量。
"""
from __future__ import annotations

from typing import Tuple

from .base import DerivedColumnEnricher
from .vwap import VwapFromAmountEnricher

#: 默认 enricher 列表。BaseMarketFetcher.enrichers 默认指向此元组。
DEFAULT_ENRICHERS: Tuple[DerivedColumnEnricher, ...] = (
    VwapFromAmountEnricher(),
)

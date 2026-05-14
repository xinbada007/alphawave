"""
AkShareSouthboundFetcher — 港股南向资金（占位实现）
=====================================================
诚实交代：Phase 0 探针使用的 `stock_hk_ggt_components_em` 是 **当前快照**
（598 只成份股的当下持仓），无法回溯历史；本 fetcher 第一版返回空 DF，
让上层走 graceful 降级。

未来若发现可用的 by-symbol 历史接口（akshare 仍在演进），只需在此填充实现，
analyzer / scorer / collector 全部不动。
"""
from __future__ import annotations

import pandas as pd

from .base import BaseFlowFetcher


class AkShareSouthboundFetcher(BaseFlowFetcher):
    name = "AkShare_Southbound"
    source_key = "southbound"

    async def fetch(self, symbol: str, days: int) -> pd.DataFrame:
        # 第一版无可靠的 by-symbol 历史接口；显式返回空，依赖上层 Null Object 降级
        return pd.DataFrame()

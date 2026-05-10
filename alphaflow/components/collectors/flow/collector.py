"""
FlowCollector — 资金流采集枢纽
================================
按 symbol 推断市场，路由到对应 FlowStrategy；并行执行多个子源 fetcher；
将结果注入 `pack.flow_data` (Dict[str, DataFrameModel]) 与 `pack.flow_meta`。

主链路不阻塞：永远 success=True；任一 / 全部子源失败时由 meta 留痕。
设计与 BenchmarkCollector 严格同构（审美一致 / 抗漂移）。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import (
    AnalysisContext,
    ComponentOutput,
    DataFrameModel,
    ResearchPack,
)
from alphaflow.core.utils import MarketType, get_market_type

from .strategies.cn_strategy import CNFlowStrategy
from .strategies.hk_strategy import HKFlowStrategy
from .strategies.us_strategy import USFlowStrategy


class FlowCollector(BaseCollector):
    """资金流采集器（HK→southbound; CN→block_trade+lhb; US→none）。"""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.strategies = {
            MarketType.HK: HKFlowStrategy(),
            MarketType.CN: CNFlowStrategy(),
            MarketType.US: USFlowStrategy(),
        }

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        pack = self._unpack_pack(context, kwargs)

        target_days = context.metadata.get("days", 30)
        market_type = get_market_type(pack.symbol)
        strategy = self.strategies.get(market_type)

        if strategy is None or not strategy.get_fetchers():
            pack.flow_meta = self._unavailable_meta(market_type, "unsupported_market")
            print(f"  [Flow] market {market_type.name}: no flow sources configured")
            return ComponentOutput(success=True, payload=pack)

        print(f"  [Flow] Fetching {market_type.name} flow signals for {pack.symbol}...")
        data, status = await strategy.execute(pack.symbol, target_days)

        if data:
            pack.flow_data = {k: DataFrameModel.from_df(v) for k, v in data.items()}

        ok_sources = [k for k, v in status.items() if v.get("status") == "ok"]
        primary_source = ok_sources[0] if ok_sources else ""
        pack.flow_meta = {
            "status": "ok" if ok_sources else "unavailable",
            "market_type": market_type.value,
            "primary_source": primary_source,
            "sources": status,
        }
        n_ok = len(ok_sources)
        n_total = len(status)
        print(f"  [Flow] {market_type.name} {pack.symbol}: {n_ok}/{n_total} sources ok"
              f"{' (' + ', '.join(ok_sources) + ')' if ok_sources else ''}")
        return ComponentOutput(success=True, payload=pack)

    @staticmethod
    def _unavailable_meta(market_type: MarketType, reason: str) -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "market_type": market_type.value,
            "primary_source": "",
            "sources": {},
            "reason": reason,
        }

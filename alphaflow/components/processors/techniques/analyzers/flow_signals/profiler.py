"""
FlowSignalsProfiler — 编排器
=============================
3 子源 → 各自 metrics 计算 → 装配 + 顶层 summary 聚合。
Null Object 降级：所有子源缺失时仅返回 data_quality 子树，sufficient_for_profile=False。

输出形态（与三兄弟同形）：
  {
    "data_quality": {...},
    "block_trade":  {"rolling": {...}, "summary": {...}},
    "lhb":          {"rolling": {...}, "summary": {...}},
    /* southbound 第一版无数据 → 不输出该键 */
    "summary": {"pressure_signals": [...], "neutral_signals": [...]}
  }
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import pandas as pd

from . import config as cfg
from . import metrics


# 子源 key → metrics 函数映射（开闭：加新子源就加一行）
_SOURCE_FN_MAP = {
    "block_trade": metrics.compute_block_trade_summary,
    "lhb":         metrics.compute_lhb_summary,
    "southbound":  metrics.compute_southbound_summary,
}


class FlowSignalsProfiler:
    """无状态。重复调用 analyze 安全。"""

    def __init__(self, config: Optional[Mapping[str, Any]] = None):
        self.config = dict(config or {})

    # -------------------------------------------------------------------------
    def analyze(
        self,
        flow_data: Optional[Dict[str, pd.DataFrame]],
        flow_meta: Optional[Mapping[str, Any]],
        market_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        meta = dict(flow_meta or {})
        sources_meta = dict(meta.get("sources") or {})
        market = market_type or meta.get("market_type") or "unknown"
        primary = meta.get("primary_source") or ""

        # 没有任何 flow_data → Null Object 降级
        if not flow_data:
            return {
                "data_quality": {
                    "market_type":            market,
                    "sources_available":      [],
                    "sources_missing":        list(sources_meta.keys()),
                    "primary_source":         "",
                    "sufficient_for_profile": False,
                    "reason":                 meta.get("reason") or "no_flow_data",
                }
            }

        # 逐子源算 summary
        per_source: Dict[str, Dict[str, Any]] = {}
        all_pressure = []
        all_neutral = []
        sources_available = []
        for key, df in flow_data.items():
            fn = _SOURCE_FN_MAP.get(key)
            if fn is None:
                continue
            block = fn(df)
            if not block.get("rolling"):
                continue  # 子源虽给了 DF 但内容为空
            sources_available.append(key)
            per_source[key] = {
                "rolling": block["rolling"],
                "summary": {
                    "pressure_signals": block["pressure_signals"],
                    "neutral_signals":  block["neutral_signals"],
                },
            }
            all_pressure.extend(block["pressure_signals"])
            all_neutral.extend(block["neutral_signals"])

        sufficient = len(sources_available) >= cfg.MIN_SOURCES_FOR_PROFILE
        sources_missing = [k for k in sources_meta if k not in sources_available]

        out: Dict[str, Any] = {
            "data_quality": {
                "market_type":            market,
                "sources_available":      sources_available,
                "sources_missing":        sources_missing,
                "primary_source":         primary,
                "sufficient_for_profile": sufficient,
            },
        }
        if not sufficient:
            return out

        # 子源块顶层化（与 distribution_pattern_profile 子树形态对齐）
        out.update(per_source)
        out["summary"] = {
            "pressure_signals": all_pressure,
            "neutral_signals":  all_neutral,
        }
        return out

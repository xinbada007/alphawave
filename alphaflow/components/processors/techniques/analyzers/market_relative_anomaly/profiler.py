"""
MarketRelativeAnomalyProfiler
==============================
单股相对大盘的异常剖面：相对量比 + 相对收益 + 大盘共振异常。

输入：
  stock_df       : 个股 OHLCV
  benchmark_df   : 大盘指数 OHLCV（已与个股对齐前提下）
  benchmark_meta : 来自 pack.benchmark_meta（status / benchmark_symbol / source / ...）
  market_type    : MarketType 枚举或 None

输出层级与 volume_anomaly_profile / distribution_pattern_profile 严格对仗：
{
  "data_quality": {
    "benchmark_status": "ok|unavailable",
    "benchmark_symbol": "^HSI",
    "benchmark_source": "AkShare_HSI",
    "lookback_actual_days": 240,
    "alignment_dropped_days": 5,
    "sufficient_for_profile": true,
    "market_type": "hk"
  },
  "latest_day": {
    "rel_volume":         1.32,
    "rel_volume_tier":    "ELEVATED",
    "rel_return":         -0.03,
    "rel_return_tier":    "MILD_UNDERPERFORM",
    "index_anomalous":    true
  },
  "rolling": {
    "5d_avg_rel_volume":  1.05,
    "20d_avg_rel_volume": 1.10,
    "60d_avg_rel_volume": 0.98,
    "20d_pct_underperform": 0.45
  },
  "summary": {
    "pressure_signals": ["[REL_VOLUME_SPIKE]", "[UNDERPERFORM_INDEX_60PCT_20D]"],
    "neutral_signals":  ["[INDEX_CO_ANOMALY]"]
  }
}
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

import pandas as pd

from alphaflow.core.acl.mappings.enums import MarketType

from . import metrics
from .config import (
    BENCH_STATUS_OK,
    BENCH_STATUS_UNAVAILABLE,
    INDEX_ANOMALOUS_RATIO,
    MIN_DAYS_FOR_PROFILE,
    OUTPACE_AVG_THRESHOLD,
    REL_VOLUME_BASELINE_WINDOW,
    ROLLING_PCT_UNDERPERFORM_WINDOW,
    ROLLING_WINDOWS,
    TAG_INDEX_CO_ANOMALY,
    TAG_PCT_UNDERPERFORM_20D,
    TAG_REL_RETURN_LATEST,
    TAG_REL_VOLUME_LATEST,
    TAG_STOCK_OUTPACES_INDEX,
    UNDERPERFORM_PCT_THRESHOLD,
)


class MarketRelativeAnomalyProfiler:
    """单股相对大盘异常剖面编排器。"""

    @property
    def target_slot(self) -> str:
        return "technical"

    def __init__(self, config: Optional[Mapping[str, Any]] = None) -> None:
        self.config = dict(config or {})
        self.windows = tuple(self.config.get("rolling_windows", ROLLING_WINDOWS))
        self.baseline_window = int(self.config.get("baseline_window",
                                                   REL_VOLUME_BASELINE_WINDOW))

    # =====================================================================
    def analyze(
        self,
        stock_df: pd.DataFrame,
        benchmark_df: Optional[pd.DataFrame],
        benchmark_meta: Optional[Mapping[str, Any]] = None,
        market_type: Optional[MarketType] = None,
    ) -> Dict[str, Any]:
        meta = dict(benchmark_meta or {})
        market_label = (market_type.value if isinstance(market_type, MarketType)
                        else MarketType.UNKNOWN.value)

        # ---------- benchmark 不可用：Null Object 沉默降级
        if (benchmark_df is None or benchmark_df.empty
                or meta.get("status") != BENCH_STATUS_OK):
            return {"data_quality": self._unavailable_dq(meta, market_label,
                                                         reason="benchmark_unavailable")}

        # ---------- 必备列：volume / close 都需要在两侧
        for need in ("volume", "close"):
            if need not in stock_df.columns or need not in benchmark_df.columns:
                return {"data_quality": self._unavailable_dq(meta, market_label,
                                                             reason=f"missing_column:{need}")}

        # ---------- 对齐
        s, i, dropped = metrics.align_by_date(stock_df, benchmark_df)
        n = len(s)
        sufficient = bool(n >= MIN_DAYS_FOR_PROFILE)

        dq = {
            "benchmark_status": meta.get("status", BENCH_STATUS_UNAVAILABLE),
            "benchmark_symbol": meta.get("benchmark_symbol", ""),
            "benchmark_source": meta.get("source", ""),
            "lookback_actual_days": int(n),
            "alignment_dropped_days": int(dropped),
            "sufficient_for_profile": sufficient,
            "market_type": market_label,
        }
        if not sufficient:
            return {"data_quality": dq}

        # ---------- 计算三组序列
        rel_vol = metrics.compute_rel_volume_series(s["volume"], i["volume"],
                                                    window=self.baseline_window)
        rel_ret = metrics.compute_rel_return_series(s["close"], i["close"])
        idx_anom = metrics.compute_index_anomalous_series(i["volume"],
                                                          window=self.baseline_window,
                                                          threshold=INDEX_ANOMALOUS_RATIO)

        latest_block, summary_pressure, summary_neutral = self._build_latest_and_summary(
            rel_vol, rel_ret, idx_anom,
        )
        rolling_block = self._build_rolling(rel_vol, rel_ret)

        # 趋势级 summary tags
        avg20 = rolling_block.get("20d_avg_rel_volume")
        if avg20 is not None and avg20 >= OUTPACE_AVG_THRESHOLD:
            summary_pressure.append(TAG_STOCK_OUTPACES_INDEX)
        pct_under = rolling_block.get("20d_pct_underperform")
        if pct_under is not None and pct_under >= UNDERPERFORM_PCT_THRESHOLD:
            summary_pressure.append(TAG_PCT_UNDERPERFORM_20D)

        return {
            "data_quality": dq,
            "latest_day": latest_block,
            "rolling": rolling_block,
            "summary": {
                "pressure_signals": summary_pressure,
                "neutral_signals":  summary_neutral,
            },
        }

    # =====================================================================
    def _build_latest_and_summary(
        self,
        rel_vol: pd.Series,
        rel_ret: pd.Series,
        idx_anom: pd.Series,
    ):
        latest_vol = rel_vol.dropna().iloc[-1] if rel_vol.notna().any() else None
        latest_ret = rel_ret.dropna().iloc[-1] if rel_ret.notna().any() else None
        latest_idx_anom = bool(idx_anom.iloc[-1]) if len(idx_anom) > 0 else False

        rv_tier = metrics.classify_rel_volume(latest_vol)
        rr_tier = metrics.classify_rel_return(latest_ret)

        block = {
            "rel_volume":      metrics._safe_round(latest_vol, 4),
            "rel_volume_tier": rv_tier,
            "rel_return":      metrics._safe_round(latest_ret, 4),
            "rel_return_tier": rr_tier,
            "index_anomalous": latest_idx_anom,
        }

        pressure: List[str] = []
        neutral: List[str] = []

        rv_tag = TAG_REL_VOLUME_LATEST.get(rv_tier)
        if rv_tag:
            (pressure if rv_tier in ("SPIKE", "HISTORIC") else neutral).append(rv_tag)

        rr_tag = TAG_REL_RETURN_LATEST.get(rr_tier)
        if rr_tag:
            (pressure if rr_tier in ("STRONG_UNDERPERFORM", "MILD_UNDERPERFORM")
             else neutral).append(rr_tag)

        if latest_idx_anom:
            neutral.append(TAG_INDEX_CO_ANOMALY)

        return block, pressure, neutral

    def _build_rolling(self, rel_vol: pd.Series, rel_ret: pd.Series) -> Dict[str, Any]:
        block: Dict[str, Any] = {}
        for w in self.windows:
            block[f"{w}d_avg_rel_volume"] = metrics._safe_round(
                metrics.rolling_avg(rel_vol, w), 4,
            )
        block[f"{ROLLING_PCT_UNDERPERFORM_WINDOW}d_pct_underperform"] = metrics._safe_round(
            metrics.rolling_pct_below(rel_ret, ROLLING_PCT_UNDERPERFORM_WINDOW, threshold=0.0),
            4,
        )
        return block

    @staticmethod
    def _unavailable_dq(meta: Mapping[str, Any], market_label: str, reason: str) -> Dict[str, Any]:
        return {
            "benchmark_status": meta.get("status", BENCH_STATUS_UNAVAILABLE),
            "benchmark_symbol": meta.get("benchmark_symbol", ""),
            "benchmark_source": meta.get("source", "none"),
            "lookback_actual_days": 0,
            "alignment_dropped_days": 0,
            "sufficient_for_profile": False,
            "market_type": market_label,
            "reason": reason,
        }

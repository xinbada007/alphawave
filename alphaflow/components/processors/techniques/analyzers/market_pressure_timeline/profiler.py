"""
Market Pressure Timeline Profiler
=================================
Builds an objective event timeline from OHLCV and optional benchmark data.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import pandas as pd

from alphaflow.core.acl.mappings.enums import MarketType

from . import config as cfg
from . import metrics
from .segmenter import segment_events
from .signal import build_market_pressure_signal


class MarketPressureTimelineProfiler:
    """Objective market-pressure timeline orchestrator."""

    @property
    def target_slot(self) -> str:
        return "technical"

    def __init__(self, config: Optional[Mapping[str, Any]] = None) -> None:
        self.config = dict(config or {})
        self.max_lookback_days = int(self.config.get("max_lookback_days", cfg.MAX_LOOKBACK_DAYS))
        self.min_days = int(self.config.get("min_days_for_timeline", cfg.MIN_DAYS_FOR_TIMELINE))
        self.daily_points_max = int(self.config.get("daily_points_max", cfg.DAILY_POINTS_MAX))
        self.trigger_score = int(self.config.get("event_trigger_score", cfg.EVENT_TRIGGER_SCORE))
        self.merge_gap_days = int(self.config.get("event_merge_gap_days", cfg.EVENT_MERGE_GAP_DAYS))
        self.confirm_quiet_days = int(self.config.get("event_confirm_quiet_days", cfg.EVENT_CONFIRM_QUIET_DAYS))

    def analyze(
        self,
        stock_df: pd.DataFrame,
        benchmark_df: Optional[pd.DataFrame] = None,
        benchmark_meta: Optional[Mapping[str, Any]] = None,
        market_type: Optional[MarketType] = None,
    ) -> Dict[str, Any]:
        market_label = (
            market_type.value if isinstance(market_type, MarketType)
            else MarketType.UNKNOWN.value
        )
        meta = dict(benchmark_meta or {})

        if stock_df is None or stock_df.empty:
            return self._empty_result(market_label, meta, reason="empty_stock_data")

        stock = metrics.ensure_sorted(stock_df).tail(self.max_lookback_days).reset_index(drop=True)
        if stock.empty:
            return self._empty_result(market_label, meta, reason="empty_stock_data")

        benchmark_ok = (
            benchmark_df is not None
            and not benchmark_df.empty
            and meta.get("status") == "ok"
        )
        if benchmark_ok:
            prepared, bench_diag = metrics.attach_benchmark_columns(stock, benchmark_df)
        else:
            prepared, bench_diag = stock, {
                "benchmark_available": False,
                "alignment_missing_days": len(stock),
            }

        dq = self._base_dq(
            stock=stock,
            prepared=prepared,
            market_label=market_label,
            meta=meta,
            benchmark_diag=bench_diag,
        )

        if len(stock) < self.min_days:
            dq["reason"] = "insufficient_history"
            return {
                "data_quality": dq,
                "summary": self._empty_summary(stock),
                "market_pressure_signal": build_market_pressure_signal(
                    [],
                    benchmark_available=bool(dq.get("benchmark_available", False)),
                ),
                "events": [],
                "daily_points": [],
                "interpretation_note": cfg.INTERPRETATION_NOTE,
            }

        points = metrics.compute_daily_evidence_points(prepared)
        events = segment_events(
            points,
            trigger_score=self.trigger_score,
            merge_gap_days=self.merge_gap_days,
            confirm_quiet_days=self.confirm_quiet_days,
        )
        daily_points, total_evidence_days, truncated = metrics.select_daily_points(
            points,
            max_points=self.daily_points_max,
        )
        dq["daily_points_returned"] = int(len(daily_points))
        dq["daily_points_total_evidence"] = int(total_evidence_days)
        dq["daily_points_truncated"] = bool(truncated)

        return {
            "data_quality": dq,
            "summary": self._summary(events, stock, total_evidence_days),
            "market_pressure_signal": build_market_pressure_signal(
                events,
                benchmark_available=bool(dq.get("benchmark_available", False)),
            ),
            "events": events,
            "daily_points": daily_points,
            "interpretation_note": cfg.INTERPRETATION_NOTE,
        }

    def _base_dq(
        self,
        *,
        stock: pd.DataFrame,
        prepared: pd.DataFrame,
        market_label: str,
        meta: Mapping[str, Any],
        benchmark_diag: Mapping[str, Any],
    ) -> Dict[str, Any]:
        fields = [c for c in ("open", "high", "low", "close", "volume", "amount") if c in stock.columns]
        return {
            "lookback_actual_days": int(len(stock)),
            "lookback_config_days": int(self.max_lookback_days),
            "sufficient_for_timeline": bool(len(stock) >= self.min_days),
            "market_type": market_label,
            "fields_available": fields,
            "benchmark_available": bool(benchmark_diag.get("benchmark_available", False)),
            "benchmark_status": meta.get("status", "unavailable"),
            "benchmark_symbol": meta.get("benchmark_symbol", ""),
            "benchmark_source": meta.get("source", ""),
            "benchmark_alignment_missing_days": int(benchmark_diag.get("alignment_missing_days", len(prepared))),
            "event_trigger_score": int(self.trigger_score),
        }

    def _empty_result(self, market_label: str, meta: Mapping[str, Any], reason: str) -> Dict[str, Any]:
        return {
            "data_quality": {
                "lookback_actual_days": 0,
                "lookback_config_days": int(self.max_lookback_days),
                "sufficient_for_timeline": False,
                "market_type": market_label,
                "fields_available": [],
                "benchmark_available": False,
                "benchmark_status": meta.get("status", "unavailable"),
                "benchmark_symbol": meta.get("benchmark_symbol", ""),
                "benchmark_source": meta.get("source", ""),
                "benchmark_alignment_missing_days": 0,
                "event_trigger_score": int(self.trigger_score),
                "reason": reason,
            },
            "summary": self._empty_summary(pd.DataFrame()),
            "market_pressure_signal": build_market_pressure_signal(
                [],
                benchmark_available=False,
            ),
            "events": [],
            "daily_points": [],
            "interpretation_note": cfg.INTERPRETATION_NOTE,
        }

    @staticmethod
    def _empty_summary(stock: pd.DataFrame) -> Dict[str, Any]:
        start = ""
        end = ""
        if stock is not None and not stock.empty and "date" in stock.columns:
            start = metrics.format_date(stock["date"].iloc[0], 0)
            end = metrics.format_date(stock["date"].iloc[-1], len(stock) - 1)
        return {
            "event_count": 0,
            "high_intensity_event_count": 0,
            "active_event": False,
            "latest_event_status": "",
            "latest_event_id": "",
            "max_event_intensity": "",
            "total_evidence_days": 0,
            "observation_window_start": start,
            "observation_window_end": end,
        }

    def _summary(
        self,
        events: list[Dict[str, Any]],
        stock: pd.DataFrame,
        total_evidence_days: int,
    ) -> Dict[str, Any]:
        if not events:
            out = self._empty_summary(stock)
            out["total_evidence_days"] = int(total_evidence_days)
            return out

        tier_rank = {"NONE": 0, "WATCH": 1, "MODERATE": 2, "ELEVATED": 3, "HIGH": 4}
        latest = events[-1]
        max_event = max(events, key=lambda e: tier_rank.get(str(e.get("intensity", "")), 0))
        return {
            "event_count": int(len(events)),
            "high_intensity_event_count": int(sum(1 for e in events if e.get("intensity") == "HIGH")),
            "active_event": bool(latest.get("status") == "active"),
            "latest_event_status": str(latest.get("status", "")),
            "latest_event_id": str(latest.get("event_id", "")),
            "max_event_intensity": str(max_event.get("intensity", "")),
            "total_evidence_days": int(total_evidence_days),
            "observation_window_start": metrics.format_date(stock["date"].iloc[0], 0) if "date" in stock.columns else "",
            "observation_window_end": metrics.format_date(stock["date"].iloc[-1], len(stock) - 1) if "date" in stock.columns else "",
        }

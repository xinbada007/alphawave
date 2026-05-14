#!/usr/bin/env python3
"""
audit_market_pressure_timeline.py
=================================
Regression audit for `market_pressure_timeline_profile`.

Sample set
----------
- Reuses the 100 tickers × 4 anchors random baseline fixture.
- Evaluates 6 checkpoints per valid anchor: 0/5/10/20/40/60 trading days.
- Product input at each checkpoint uses only data up to that checkpoint.
- ProxyTruth still uses the anchor's future 60d path, only as an audit proxy.

Interpretation
--------------
This script evaluates whether the timeline can capture objective market-pressure
events while the ProxyTruth path unfolds.  Anchor-day recall is expected to be
lower than detection-window recall because many labels are defined by future
path behavior that may not yet be observable on the anchor date.
"""
from __future__ import annotations

import csv
import os
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.audit_random_baseline import (  # noqa: E402
    ANCHORS_CSV,
    BASE_DIR,
    load_benchmark,
    load_price,
    actual_anchor,
    safe_float,
)
from scripts.proxy_truth import evaluate as proxy_evaluate  # noqa: E402
from alphaflow.components.processors.techniques.analyzers.market_pressure_timeline import (  # noqa: E402
    MarketPressureTimelineProfiler,
)
from alphaflow.components.processors.techniques.analyzers.market_pressure_timeline import config as signal_cfg  # noqa: E402
from alphaflow.core.acl.mappings.enums import MarketType  # noqa: E402


CHECKPOINTS = (0, 5, 10, 20, 40, 60)
RECENT_EVENT_DAYS = 20
EVENT_SCORE_THRESHOLD = 35

OUT_CSV = os.path.join(BASE_DIR, "timeline_audit_results.csv")
OUT_REPORT = os.path.join(BASE_DIR, "timeline_audit_report.txt")

MARKET_TYPE = {
    "US": MarketType.US,
    "HK": MarketType.HK,
    "CN": MarketType.CN,
}


@dataclass
class TimelineAuditRow:
    market: str
    ticker: str
    anchor_requested: str
    anchor_actual: str
    source: str
    proxy_positive: bool
    proxy_intensity: str
    proxy_pattern: str
    abs_dd_60d: Optional[float]
    excess_dd: Optional[float]
    anchor_detected: bool
    window_detected: bool
    first_detect_dt: Optional[int]
    peak_event_score: Optional[int]
    peak_event_intensity: Optional[str]
    peak_event_status: Optional[str]
    peak_event_behaviors: str
    signal_detected: bool
    first_signal_dt: Optional[int]
    peak_signal_score: Optional[int]
    peak_signal_state: Optional[str]
    peak_signal_confidence: Optional[str]
    peak_signal_source_event_id: Optional[str]
    peak_signal_reason_codes: str
    anchor_signal_state: Optional[str]
    anchor_event_count_500d: Optional[int]
    anchor_total_evidence_days: Optional[int]
    checkpoint_snapshots: int
    status: str
    note: str


def fmt_pct(x: float) -> str:
    return f"{x:.1%}"


def _status_ok(row: TimelineAuditRow) -> bool:
    return row.status == "OK"


def confusion(rows: Iterable[TimelineAuditRow], *, window: bool) -> Dict[str, int]:
    tp = fp = tn = fn = 0
    for r in rows:
        if not _status_ok(r):
            continue
        pred = r.window_detected if window else r.anchor_detected
        truth = r.proxy_positive
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif not pred and not truth:
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def metrics(c: Dict[str, int]) -> Dict[str, float]:
    tp, fp, tn, fn = c["tp"], c["fp"], c["tn"], c["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
    }


def confusion_for_pred(rows: Iterable[TimelineAuditRow], pred_by_row: Dict[int, bool]) -> Dict[str, int]:
    tp = fp = tn = fn = 0
    for i, r in enumerate(rows):
        if not _status_ok(r):
            continue
        pred = pred_by_row.get(i, False)
        truth = r.proxy_positive
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif not pred and not truth:
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def prediction_variants(rows: List[TimelineAuditRow]) -> List[tuple[str, Dict[str, int], float]]:
    variants = []
    for name, predicate in (
        ("broad_recent_event", lambda r: r.window_detected),
        ("signal_attention", lambda r: r.peak_signal_state in {
            signal_cfg.SIGNAL_STATE_ACTIVE_HIGH,
            signal_cfg.SIGNAL_STATE_FAILED_RECOVERY,
            signal_cfg.SIGNAL_STATE_ACTIVE,
            signal_cfg.SIGNAL_STATE_COOLING,
        }),
        ("signal_strong", lambda r: r.signal_detected),
        ("signal_active_high", lambda r: r.peak_signal_state == signal_cfg.SIGNAL_STATE_ACTIVE_HIGH),
        ("signal_failed_recovery", lambda r: r.peak_signal_state == signal_cfg.SIGNAL_STATE_FAILED_RECOVERY),
        ("score>=70", lambda r: (r.peak_event_score or 0) >= 70),
        ("score>=83", lambda r: (r.peak_event_score or 0) >= 83),
        ("unresolved_event", lambda r: r.peak_event_status in {"active", "cooling", "failed_recovery"}),
        ("unresolved_HIGH", lambda r: (
            r.peak_event_status in {"active", "cooling", "failed_recovery"}
            and r.peak_event_intensity == "HIGH"
        )),
        ("active_HIGH", lambda r: (
            r.peak_event_status == "active"
            and r.peak_event_intensity == "HIGH"
        )),
        ("active_or_failed_HIGH", lambda r: (
            r.peak_event_status in {"active", "failed_recovery"}
            and r.peak_event_intensity == "HIGH"
        )),
    ):
        pred = {i: bool(predicate(r)) for i, r in enumerate(rows)}
        c = confusion_for_pred(rows, pred)
        strong = [r for r in rows if r.status == "OK" and r.proxy_intensity == "STRONG"]
        strong_recall = (
            sum(pred.get(i, False) for i, r in enumerate(rows)
                if r.status == "OK" and r.proxy_intensity == "STRONG") / len(strong)
            if strong else 0.0
        )
        variants.append((name, c, strong_recall))
    return variants


def _is_strong_signal(signal: Mapping[str, Any]) -> bool:
    return signal.get("state") in {
        signal_cfg.SIGNAL_STATE_ACTIVE_HIGH,
        signal_cfg.SIGNAL_STATE_FAILED_RECOVERY,
    }


def _signal_rank(signal: Mapping[str, Any]) -> tuple[int, int]:
    state = str(signal.get("state", ""))
    state_rank = {
        signal_cfg.SIGNAL_STATE_ACTIVE_HIGH: 800,
        signal_cfg.SIGNAL_STATE_FAILED_RECOVERY: 760,
        signal_cfg.SIGNAL_STATE_ACTIVE: 650,
        signal_cfg.SIGNAL_STATE_COOLING: 600,
        signal_cfg.SIGNAL_STATE_RECENT_RESOLVED: 420,
        signal_cfg.SIGNAL_STATE_WATCH: 250,
        signal_cfg.SIGNAL_STATE_HISTORICAL_ONLY: 120,
        signal_cfg.SIGNAL_STATE_NO_RECENT: 0,
    }.get(state, 0)
    return (state_rank, _safe_int(signal.get("score")) or 0)


def _date_index(df: pd.DataFrame) -> Dict[str, int]:
    return {
        pd.Timestamp(row["date"]).date().isoformat(): int(i)
        for i, row in df.reset_index(drop=True).iterrows()
    }


def _recent_event(profile: Dict[str, Any], hist: pd.DataFrame) -> Optional[Dict[str, Any]]:
    events = profile.get("events") or []
    if not events:
        return None

    index_by_date = _date_index(hist)
    latest_idx = len(hist) - 1
    best: Optional[Dict[str, Any]] = None
    for event in events:
        score = event.get("peak_pressure_score")
        try:
            score_i = int(score)
        except (TypeError, ValueError):
            continue
        if score_i < EVENT_SCORE_THRESHOLD:
            continue

        last_date = event.get("last_evidence_date") or event.get("peak_date")
        last_idx = index_by_date.get(str(last_date))
        if last_idx is None:
            continue
        if latest_idx - last_idx > RECENT_EVENT_DAYS:
            continue
        if best is None or score_i > int(best.get("peak_pressure_score", 0)):
            best = event
    return best


def _run_timeline(
    profiler: MarketPressureTimelineProfiler,
    stock_hist: pd.DataFrame,
    bench_hist: pd.DataFrame,
    market: str,
) -> Dict[str, Any]:
    return profiler.analyze(
        stock_df=stock_hist,
        benchmark_df=bench_hist,
        benchmark_meta={
            "status": "ok",
            "benchmark_symbol": {"US": "SPY", "HK": "^HSI", "CN": "000300.SS"}[market],
            "source": "random_baseline_benchmark_fixture",
        },
        market_type=MARKET_TYPE.get(market, MarketType.UNKNOWN),
    )


def evaluate_one(
    row: Dict[str, str],
    benchmarks: Dict[str, pd.DataFrame],
    profiler: MarketPressureTimelineProfiler,
) -> TimelineAuditRow:
    market = row["market"]
    ticker = row["ticker"]
    anchor_req = row["anchor"]
    source = row["source"]

    try:
        df = load_price(ticker)
    except Exception as exc:
        return _error_row(market, ticker, anchor_req, "", source, "LOAD_ERROR", exc)

    anchor = actual_anchor(df, anchor_req)
    if anchor is None:
        return _error_row(
            market, ticker, anchor_req, "", source, "NO_ANCHOR",
            "no trading day <= requested anchor",
        )

    anchor_idx_candidates = df.index[df["date"] <= anchor]
    if len(anchor_idx_candidates) == 0:
        return _error_row(market, ticker, anchor_req, "", source, "NO_ANCHOR", "no anchor index")
    anchor_idx = int(anchor_idx_candidates[-1])

    hist_anchor = df.iloc[: anchor_idx + 1].reset_index(drop=True)
    if len(hist_anchor) < 80:
        return _error_row(
            market, ticker, anchor_req, anchor.date().isoformat(), source,
            "SHORT_HISTORY", f"only {len(hist_anchor)} rows before anchor",
        )

    try:
        proxy = proxy_evaluate(stock=df, benchmark=benchmarks[market], base_day=anchor)
        ev = proxy.evidence or {}
    except Exception as exc:
        return _error_row(
            market, ticker, anchor_req, anchor.date().isoformat(), source, "PROXY_ERROR", exc,
        )

    anchor_detected = False
    window_detected = False
    first_detect_dt: Optional[int] = None
    peak_event_score: Optional[int] = None
    peak_event_intensity: Optional[str] = None
    peak_event_status: Optional[str] = None
    peak_event_behaviors = ""
    signal_detected = False
    first_signal_dt: Optional[int] = None
    best_signal: Optional[Dict[str, Any]] = None
    peak_signal_score: Optional[int] = None
    peak_signal_state: Optional[str] = None
    peak_signal_confidence: Optional[str] = None
    peak_signal_source_event_id: Optional[str] = None
    peak_signal_reason_codes = ""
    anchor_signal_state: Optional[str] = None
    anchor_event_count: Optional[int] = None
    anchor_total_evidence_days: Optional[int] = None
    snapshots = 0

    try:
        for dt in CHECKPOINTS:
            i = min(anchor_idx + dt, len(df) - 1)
            hist = df.iloc[: i + 1].reset_index(drop=True)
            if len(hist) < 80:
                continue
            day = pd.Timestamp(hist.iloc[-1]["date"])
            bench_hist = benchmarks[market][benchmarks[market]["date"] <= day].reset_index(drop=True)
            profile = _run_timeline(profiler, hist, bench_hist, market)
            snapshots += 1
            summary = profile.get("summary") or {}
            if dt == 0:
                anchor_event_count = _safe_int(summary.get("event_count"))
                anchor_total_evidence_days = _safe_int(summary.get("total_evidence_days"))
                anchor_signal_state = (profile.get("market_pressure_signal") or {}).get("state")

            event = _recent_event(profile, hist)
            detected = event is not None
            if dt == 0:
                anchor_detected = detected
            if detected:
                window_detected = True
                if first_detect_dt is None:
                    first_detect_dt = dt
                score = int(event.get("peak_pressure_score", 0))
                if peak_event_score is None or score > peak_event_score:
                    peak_event_score = score
                    peak_event_intensity = str(event.get("intensity", ""))
                    peak_event_status = str(event.get("status", ""))
                    peak_event_behaviors = "|".join(event.get("observed_behaviors", [])[:6])
            signal = profile.get("market_pressure_signal") or {}
            if _is_strong_signal(signal):
                signal_detected = True
                if first_signal_dt is None:
                    first_signal_dt = dt
            if best_signal is None or _signal_rank(signal) > _signal_rank(best_signal):
                best_signal = dict(signal)
                peak_signal_score = _safe_int(signal.get("score"))
                peak_signal_state = signal.get("state")
                peak_signal_confidence = signal.get("confidence")
                peak_signal_source_event_id = signal.get("source_event_id")
                peak_signal_reason_codes = "|".join(signal.get("reason_codes", [])[:8])
    except Exception as exc:
        return _error_row(
            market, ticker, anchor_req, anchor.date().isoformat(), source, "TIMELINE_ERROR", exc,
            proxy_positive=bool(proxy.is_distribution),
            proxy_intensity=proxy.intensity,
            proxy_pattern=proxy.pattern,
            abs_dd_60d=safe_float(ev.get("abs_dd_60d")),
            excess_dd=safe_float(ev.get("excess_dd")),
        )

    return TimelineAuditRow(
        market=market,
        ticker=ticker,
        anchor_requested=anchor_req,
        anchor_actual=anchor.date().isoformat(),
        source=source,
        proxy_positive=bool(proxy.is_distribution),
        proxy_intensity=proxy.intensity,
        proxy_pattern=proxy.pattern,
        abs_dd_60d=safe_float(ev.get("abs_dd_60d")),
        excess_dd=safe_float(ev.get("excess_dd")),
        anchor_detected=anchor_detected,
        window_detected=window_detected,
        first_detect_dt=first_detect_dt,
        peak_event_score=peak_event_score,
        peak_event_intensity=peak_event_intensity,
        peak_event_status=peak_event_status,
        peak_event_behaviors=peak_event_behaviors,
        signal_detected=signal_detected,
        first_signal_dt=first_signal_dt,
        peak_signal_score=peak_signal_score,
        peak_signal_state=peak_signal_state,
        peak_signal_confidence=peak_signal_confidence,
        peak_signal_source_event_id=peak_signal_source_event_id,
        peak_signal_reason_codes=peak_signal_reason_codes,
        anchor_signal_state=anchor_signal_state,
        anchor_event_count_500d=anchor_event_count,
        anchor_total_evidence_days=anchor_total_evidence_days,
        checkpoint_snapshots=snapshots,
        status="OK",
        note="",
    )


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return int(value)
    except Exception:
        return None


def _error_row(
    market: str,
    ticker: str,
    anchor_req: str,
    anchor_actual: str,
    source: str,
    status: str,
    exc: Any,
    *,
    proxy_positive: bool = False,
    proxy_intensity: str = "NONE",
    proxy_pattern: str = "flat",
    abs_dd_60d: Optional[float] = None,
    excess_dd: Optional[float] = None,
) -> TimelineAuditRow:
    note = str(exc) if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
    return TimelineAuditRow(
        market=market,
        ticker=ticker,
        anchor_requested=anchor_req,
        anchor_actual=anchor_actual,
        source=source,
        proxy_positive=proxy_positive,
        proxy_intensity=proxy_intensity,
        proxy_pattern=proxy_pattern,
        abs_dd_60d=abs_dd_60d,
        excess_dd=excess_dd,
        anchor_detected=False,
        window_detected=False,
        first_detect_dt=None,
        peak_event_score=None,
        peak_event_intensity=None,
        peak_event_status=None,
        peak_event_behaviors="",
        signal_detected=False,
        first_signal_dt=None,
        peak_signal_score=None,
        peak_signal_state=None,
        peak_signal_confidence=None,
        peak_signal_source_event_id=None,
        peak_signal_reason_codes="",
        anchor_signal_state=None,
        anchor_event_count_500d=None,
        anchor_total_evidence_days=None,
        checkpoint_snapshots=0,
        status=status,
        note=note,
    )


def write_results(rows: List[TimelineAuditRow]) -> None:
    fields = list(TimelineAuditRow.__dataclass_fields__.keys())
    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field) for field in fields})


def build_report(rows: List[TimelineAuditRow]) -> str:
    ok = [r for r in rows if r.status == "OK"]
    status_counts = Counter(r.status for r in rows)
    truth_counts = Counter(r.proxy_intensity for r in ok)
    source_counts = Counter(r.source for r in ok)

    c_anchor = confusion(ok, window=False)
    m_anchor = metrics(c_anchor)
    c_window = confusion(ok, window=True)
    m_window = metrics(c_window)

    strong = [r for r in ok if r.proxy_intensity == "STRONG"]
    mild = [r for r in ok if r.proxy_intensity == "MILD"]
    none = [r for r in ok if r.proxy_intensity == "NONE"]

    lines: List[str] = []
    lines.append("=" * 120)
    lines.append("Market Pressure Timeline Audit — 400 anchors × checkpoints 0/5/10/20/40/60d")
    lines.append("=" * 120)
    lines.append(f"Total rows: {len(rows)}  OK: {len(ok)}  Status: {dict(status_counts)}")
    lines.append(f"Checkpoint snapshots evaluated: {sum(r.checkpoint_snapshots for r in ok)}")
    lines.append(f"ProxyTruth intensity counts: {dict(truth_counts)}")
    lines.append(f"Anchor source counts: {dict(source_counts)}")
    lines.append("")
    lines.append("Prediction rule:")
    lines.append(
        f"  recent event = peak_pressure_score >= {EVENT_SCORE_THRESHOLD} and "
        f"last_evidence_date within {RECENT_EVENT_DAYS} trading days of checkpoint"
    )
    lines.append("  anchor_detected = recent event at dt=0")
    lines.append("  window_detected = recent event at any dt in {0,5,10,20,40,60}")
    lines.append("")
    lines.append("Confusion — anchor day")
    lines.append(f"  TP={c_anchor['tp']} FP={c_anchor['fp']} TN={c_anchor['tn']} FN={c_anchor['fn']}")
    lines.append(
        "  precision={precision} recall={recall} specificity={specificity} f1={f1}".format(
            **{k: fmt_pct(v) for k, v in m_anchor.items()}
        )
    )
    lines.append("")
    lines.append("Confusion — detection window")
    lines.append(f"  TP={c_window['tp']} FP={c_window['fp']} TN={c_window['tn']} FN={c_window['fn']}")
    lines.append(
        "  precision={precision} recall={recall} specificity={specificity} f1={f1}".format(
            **{k: fmt_pct(v) for k, v in m_window.items()}
        )
    )
    lines.append("")
    lines.append("Decision-rule variants using timeline fields")
    lines.append("  rule                    TP  FP  TN  FN   precision recall specificity strong_recall")
    for name, c, strong_recall in prediction_variants(ok):
        m = metrics(c)
        lines.append(
            f"  {name:<22} {c['tp']:3} {c['fp']:3} {c['tn']:3} {c['fn']:3} "
            f"{m['precision']:10.1%} {m['recall']:6.1%} {m['specificity']:11.1%} {strong_recall:13.1%}"
        )
    lines.append("")
    c_signal = confusion_for_pred(ok, {i: bool(r.signal_detected) for i, r in enumerate(ok)})
    m_signal = metrics(c_signal)
    lines.append("Confusion — stable market_pressure_signal strong states")
    lines.append("  positive states: ACTIVE_HIGH_PRESSURE or FAILED_RECOVERY_PRESSURE")
    lines.append(f"  TP={c_signal['tp']} FP={c_signal['fp']} TN={c_signal['tn']} FN={c_signal['fn']}")
    lines.append(
        "  precision={precision} recall={recall} specificity={specificity} f1={f1}".format(
            **{k: fmt_pct(v) for k, v in m_signal.items()}
        )
    )
    lines.append("")
    lines.append("Recall by ProxyTruth intensity — broad recent event")
    lines.append(f"  STRONG: {sum(r.window_detected for r in strong)}/{len(strong)} = {fmt_pct(_ratio(sum(r.window_detected for r in strong), len(strong)))}")
    lines.append(f"  MILD:   {sum(r.window_detected for r in mild)}/{len(mild)} = {fmt_pct(_ratio(sum(r.window_detected for r in mild), len(mild)))}")
    lines.append(f"  NONE false-positive rate: {sum(r.window_detected for r in none)}/{len(none)} = {fmt_pct(_ratio(sum(r.window_detected for r in none), len(none)))}")
    lines.append("")
    lines.append("Recall by ProxyTruth intensity — strong headline signal")
    lines.append(f"  STRONG: {sum(r.signal_detected for r in strong)}/{len(strong)} = {fmt_pct(_ratio(sum(r.signal_detected for r in strong), len(strong)))}")
    lines.append(f"  MILD:   {sum(r.signal_detected for r in mild)}/{len(mild)} = {fmt_pct(_ratio(sum(r.signal_detected for r in mild), len(mild)))}")
    lines.append(f"  NONE false-positive rate: {sum(r.signal_detected for r in none)}/{len(none)} = {fmt_pct(_ratio(sum(r.signal_detected for r in none), len(none)))}")
    lines.append("")
    lines.append("First detection dt distribution (window_detected TRUE only):")
    lines.append(str(pd.Series([r.first_detect_dt for r in ok if r.window_detected]).value_counts().sort_index().to_dict()))
    lines.append("First signal dt distribution (signal_detected TRUE only):")
    lines.append(str(pd.Series([r.first_signal_dt for r in ok if r.signal_detected]).value_counts().sort_index().to_dict()))
    lines.append("")
    lines.append("Peak stable signal state distribution:")
    lines.append(str(pd.Series([r.peak_signal_state for r in ok]).value_counts().to_dict()))
    lines.append("")
    lines.append("By market — detection window")
    lines.append("  market   n   truth+  pred+   precision recall specificity")
    for market in ("US", "HK", "CN"):
        sub = [r for r in ok if r.market == market]
        c = confusion(sub, window=True)
        m = metrics(c)
        lines.append(
            f"  {market:<6} {len(sub):3} {c['tp'] + c['fn']:7} {c['tp'] + c['fp']:6} "
            f"{m['precision']:9.1%} {m['recall']:6.1%} {m['specificity']:11.1%}"
        )
    lines.append("")
    lines.append("By source — detection window")
    lines.append("  source       n   truth+  pred+   precision recall specificity")
    for source in sorted(source_counts):
        sub = [r for r in ok if r.source == source]
        c = confusion(sub, window=True)
        m = metrics(c)
        lines.append(
            f"  {source:<11} {len(sub):3} {c['tp'] + c['fn']:7} {c['tp'] + c['fp']:6} "
            f"{m['precision']:9.1%} {m['recall']:6.1%} {m['specificity']:11.1%}"
        )

    if ok:
        avg_events_pos = _avg([r.anchor_event_count_500d for r in ok if r.proxy_positive])
        avg_events_neg = _avg([r.anchor_event_count_500d for r in ok if not r.proxy_positive])
        avg_evd_pos = _avg([r.anchor_total_evidence_days for r in ok if r.proxy_positive])
        avg_evd_neg = _avg([r.anchor_total_evidence_days for r in ok if not r.proxy_positive])
        lines.append("")
        lines.append("Anchor-day 500d timeline burden")
        lines.append(f"  truth+ avg_event_count={avg_events_pos:.2f} avg_evidence_days={avg_evd_pos:.2f}")
        lines.append(f"  truth- avg_event_count={avg_events_neg:.2f} avg_evidence_days={avg_evd_neg:.2f}")

    fn = sorted(
        [r for r in ok if r.proxy_positive and not r.window_detected],
        key=lambda r: (r.proxy_intensity != "STRONG", r.abs_dd_60d or 0),
    )
    fp = sorted(
        [r for r in ok if (not r.proxy_positive) and r.window_detected],
        key=lambda r: -(r.peak_event_score or 0),
    )
    lines.append("")
    lines.append("Top false negatives (ProxyTruth TRUE, no recent timeline event in window)")
    lines.append("  ticker anchor market src truth abs_dd excess_dd pattern")
    for r in fn[:25]:
        lines.append(
            f"  {r.ticker:<8} {r.anchor_actual:<10} {r.market:<2} {r.source:<11} "
            f"{r.proxy_intensity:<6} {(r.abs_dd_60d or 0):+.1%} {(r.excess_dd or 0):+.1%} {r.proxy_pattern}"
        )

    lines.append("")
    lines.append("Top false positives (ProxyTruth FALSE, timeline recent event in window)")
    lines.append("  ticker anchor market src score intensity status first_dt behaviors")
    for r in fp[:25]:
        lines.append(
            f"  {r.ticker:<8} {r.anchor_actual:<10} {r.market:<2} {r.source:<11} "
            f"{str(r.peak_event_score):<5} {str(r.peak_event_intensity):<9} "
            f"{str(r.peak_event_status):<15} {str(r.first_detect_dt):<3} {r.peak_event_behaviors}"
        )

    sig_fn = sorted(
        [r for r in ok if r.proxy_positive and not r.signal_detected],
        key=lambda r: (r.proxy_intensity != "STRONG", r.abs_dd_60d or 0),
    )
    sig_fp = sorted(
        [r for r in ok if (not r.proxy_positive) and r.signal_detected],
        key=lambda r: -(r.peak_signal_score or 0),
    )
    lines.append("")
    lines.append("Top signal false negatives (ProxyTruth TRUE, no strong headline signal)")
    lines.append("  ticker anchor market src truth abs_dd excess_dd peak_state peak_score")
    for r in sig_fn[:25]:
        lines.append(
            f"  {r.ticker:<8} {r.anchor_actual:<10} {r.market:<2} {r.source:<11} "
            f"{r.proxy_intensity:<6} {(r.abs_dd_60d or 0):+.1%} {(r.excess_dd or 0):+.1%} "
            f"{str(r.peak_signal_state):<24} {str(r.peak_signal_score):<5}"
        )

    lines.append("")
    lines.append("Top signal false positives (ProxyTruth FALSE, strong headline signal)")
    lines.append("  ticker anchor market src state score confidence first_dt reasons")
    for r in sig_fp[:25]:
        lines.append(
            f"  {r.ticker:<8} {r.anchor_actual:<10} {r.market:<2} {r.source:<11} "
            f"{str(r.peak_signal_state):<24} {str(r.peak_signal_score):<5} "
            f"{str(r.peak_signal_confidence):<6} {str(r.first_signal_dt):<3} {r.peak_signal_reason_codes}"
        )

    lines.append("")
    lines.append("LLM judgment hook:")
    lines.append("  Use anchor-day metrics to assess pre-existing pressure visibility.")
    lines.append("  Use detection-window metrics to assess whether unfolding objective market-pressure behavior is captured.")
    lines.append("  High recall with materially lower specificity would mean the timeline is useful for LLM evidence context,")
    lines.append("  but should not be used alone as a binary distribution classifier.")
    lines.append("")
    lines.append(f"CSV: {OUT_CSV}")
    lines.append(f"Report: {OUT_REPORT}")
    lines.append("=" * 120)
    return "\n".join(lines)


def _ratio(num: int, den: int) -> float:
    return num / den if den else 0.0


def _avg(values: Iterable[Optional[int]]) -> float:
    clean = [float(v) for v in values if v is not None]
    return sum(clean) / len(clean) if clean else 0.0


def main() -> int:
    if not os.path.exists(ANCHORS_CSV):
        print(f"ERROR: missing {ANCHORS_CSV}. Run sample_random_baseline.py first.")
        return 2

    benchmarks = {market: load_benchmark(market) for market in ("US", "HK", "CN")}
    with open(ANCHORS_CSV) as f:
        anchor_rows = list(csv.DictReader(f))

    profiler = MarketPressureTimelineProfiler()
    rows: List[TimelineAuditRow] = []
    total = len(anchor_rows)
    for i, row in enumerate(anchor_rows, 1):
        result = evaluate_one(row, benchmarks, profiler)
        rows.append(result)
        if i % 25 == 0 or i == total:
            print(f"  [{i:3}/{total}] processed; last={result.ticker} {result.anchor_requested} {result.status}")

    write_results(rows)
    report = build_report(rows)
    with open(OUT_REPORT, "w") as f:
        f.write(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

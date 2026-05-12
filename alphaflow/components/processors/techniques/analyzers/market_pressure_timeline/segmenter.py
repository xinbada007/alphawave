"""
Market Pressure Event Segmenter
===============================
Groups daily objective evidence points into lifecycle events.

The segmenter does not infer investor identity or intent.  It only converts
adjacent objective evidence days into market-pressure intervals.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from . import config as cfg
from .metrics import DailyEvidencePoint, ordered_behaviors, safe_round


def segment_events(
    points: Sequence[DailyEvidencePoint],
    *,
    trigger_score: int = cfg.EVENT_TRIGGER_SCORE,
    merge_gap_days: int = cfg.EVENT_MERGE_GAP_DAYS,
    confirm_quiet_days: int = cfg.EVENT_CONFIRM_QUIET_DAYS,
) -> List[Dict[str, Any]]:
    if not points:
        return []

    evidence = [p for p in points if p.score >= trigger_score]
    if not evidence:
        return []

    clusters: List[List[DailyEvidencePoint]] = []
    current: List[DailyEvidencePoint] = []
    for point in evidence:
        if not current:
            current = [point]
            continue
        gap = point.idx - current[-1].idx - 1
        if gap <= merge_gap_days:
            current.append(point)
        else:
            clusters.append(current)
            current = [point]
    if current:
        clusters.append(current)

    point_by_idx = {p.idx: p for p in points}
    last_idx = max(p.idx for p in points)
    events: List[Dict[str, Any]] = []
    for seq, cluster in enumerate(clusters, start=1):
        events.append(_build_event(
            seq=seq,
            cluster=cluster,
            point_by_idx=point_by_idx,
            last_idx=last_idx,
            confirm_quiet_days=confirm_quiet_days,
        ))
    return events


def _build_event(
    *,
    seq: int,
    cluster: Sequence[DailyEvidencePoint],
    point_by_idx: Dict[int, DailyEvidencePoint],
    last_idx: int,
    confirm_quiet_days: int,
) -> Dict[str, Any]:
    start_idx = cluster[0].idx
    last_evidence_idx = cluster[-1].idx
    quiet_days_after = max(0, last_idx - last_evidence_idx)
    confirmed_end_idx = min(last_idx, last_evidence_idx + confirm_quiet_days)

    price_span_end = confirmed_end_idx if quiet_days_after >= confirm_quiet_days else last_idx
    price_metrics = _event_price_metrics(point_by_idx, start_idx, price_span_end)

    if last_evidence_idx >= last_idx:
        status = "active"
        end_date: Optional[str] = None
    elif quiet_days_after < confirm_quiet_days:
        status = "cooling"
        end_date = None
    elif _safe_recovery(price_metrics.get("recovery_ratio")) < cfg.RESOLVED_RECOVERY_RATIO_MIN:
        status = "failed_recovery"
        end_date = point_by_idx[confirmed_end_idx].date
    else:
        status = "resolved"
        end_date = point_by_idx[confirmed_end_idx].date

    peak = max(cluster, key=lambda p: (p.score, p.idx))
    behaviors = ordered_behaviors(b for p in cluster for b in p.observed_behaviors)
    event_metrics = _aggregate_event_metrics(cluster, price_metrics, quiet_days_after)

    duration_end_idx = confirmed_end_idx if end_date else last_idx
    return {
        "event_id": f"mpe_{seq:03d}",
        "start_date": cluster[0].date,
        "peak_date": peak.date,
        "last_evidence_date": cluster[-1].date,
        "end_date": end_date,
        "status": status,
        "duration_days": int(max(1, duration_end_idx - start_idx + 1)),
        "evidence_days": int(len(cluster)),
        "peak_pressure_score": int(peak.score),
        "intensity": peak.tier,
        "observed_behaviors": list(behaviors),
        "metrics": event_metrics,
    }


def _event_price_metrics(
    point_by_idx: Dict[int, DailyEvidencePoint],
    start_idx: int,
    end_idx: int,
) -> Dict[str, Optional[float]]:
    closes = []
    for idx in range(start_idx, end_idx + 1):
        p = point_by_idx.get(idx)
        if p is None or p.close is None:
            continue
        closes.append((idx, float(p.close)))

    if len(closes) < 2:
        return {"max_drawdown": None, "recovery_ratio": None, "price_return": None}

    values = np.array([v for _, v in closes], dtype=float)
    running_peak = np.maximum.accumulate(values)
    safe_peak = np.where(running_peak > 0, running_peak, np.nan)
    dd = (values - safe_peak) / safe_peak
    max_dd = float(np.nanmin(dd)) if np.isfinite(dd).any() else np.nan

    peak_pos = int(np.argmax(values))
    trough_pos = int(np.argmin(values))
    peak = float(values[peak_pos])
    trough = float(values[trough_pos])
    latest = float(values[-1])
    if peak_pos < trough_pos and peak > trough:
        recovery_ratio = (latest - trough) / (peak - trough)
    else:
        recovery_ratio = 1.0

    first = float(values[0])
    price_return = (latest - first) / first if first > 0 else np.nan
    return {
        "max_drawdown": safe_round(max_dd, 4),
        "recovery_ratio": safe_round(recovery_ratio, 4),
        "price_return": safe_round(price_return, 4),
    }


def _aggregate_event_metrics(
    cluster: Sequence[DailyEvidencePoint],
    price_metrics: Dict[str, Optional[float]],
    quiet_days_after: int,
) -> Dict[str, Any]:
    down_volume_share = _max_metric(cluster, ("down_volume_share_60d", "down_volume_share_20d"))
    relative_under = _min_metric(cluster, ("relative_underperformance_60d", "relative_underperformance_20d"))
    abnormal_days = sum(
        1 for p in cluster
        if cfg.BEHAVIOR_DOWN_DAY_ABNORMAL_VOLUME in p.observed_behaviors
        or cfg.BEHAVIOR_ABNORMAL_VOLUME in p.observed_behaviors
    )

    return {
        "max_drawdown": price_metrics.get("max_drawdown"),
        "down_day_volume_share": safe_round(down_volume_share, 4),
        "relative_underperformance": safe_round(relative_under, 4),
        "recovery_ratio": price_metrics.get("recovery_ratio"),
        "price_return": price_metrics.get("price_return"),
        "abnormal_volume_days": int(abnormal_days),
        "quiet_days_after": int(quiet_days_after),
    }


def _max_metric(points: Sequence[DailyEvidencePoint], keys: Sequence[str]) -> Optional[float]:
    values: List[float] = []
    for p in points:
        for key in keys:
            value = p.metrics.get(key)
            if value is not None:
                values.append(float(value))
                break
    return max(values) if values else None


def _min_metric(points: Sequence[DailyEvidencePoint], keys: Sequence[str]) -> Optional[float]:
    values: List[float] = []
    for p in points:
        for key in keys:
            value = p.metrics.get(key)
            if value is not None:
                values.append(float(value))
                break
    return min(values) if values else None


def _safe_recovery(value: Any) -> float:
    if value is None:
        return 1.0
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 1.0
    return f if np.isfinite(f) else 1.0

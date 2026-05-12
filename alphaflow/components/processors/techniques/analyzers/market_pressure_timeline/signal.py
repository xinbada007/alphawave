"""
Market Pressure Headline Signal
===============================
Deterministic state machine + monotonic scorecard for compressing the event
timeline into one LLM-friendly signal.

The signal is intentionally not a supervised prediction model.  It summarizes
observable market-pressure evidence and always keeps `source_event_id` so the
raw event can be audited.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from . import config as cfg


def build_market_pressure_signal(
    events: Sequence[Mapping[str, Any]],
    *,
    benchmark_available: bool,
) -> Dict[str, Any]:
    """Return a stable headline signal for the current timeline."""
    if not events:
        return _empty_signal(cfg.SIGNAL_STATE_NO_RECENT, ["no_pressure_events"])

    primary = _select_primary_event(events)
    if primary is None:
        return _empty_signal(cfg.SIGNAL_STATE_NO_RECENT, ["no_selectable_pressure_event"])

    facts = _event_facts(primary, benchmark_available=benchmark_available)
    score, score_reasons = _score_event(primary, facts)
    state = _state_for_event(primary, facts, score)
    confidence = _confidence_for_event(facts)
    current_relevance = _current_relevance(primary, facts)
    reason_codes = _reason_codes(primary, facts, score_reasons)

    return {
        "state": state,
        "score": int(score),
        "severity": str(primary.get("intensity", "NONE") or "NONE"),
        "current_relevance": current_relevance,
        "confidence": confidence,
        "source_event_id": primary.get("event_id"),
        "source_event_status": primary.get("status"),
        "source_event_last_evidence_date": primary.get("last_evidence_date"),
        "reason_codes": reason_codes,
        "evidence_breadth": int(facts["core_count"]),
        "auxiliary_evidence_breadth": int(facts["auxiliary_count"]),
        "metric_confirmations": facts["metric_confirmations"],
        "interpretation_note": cfg.SIGNAL_NOTE,
    }


def _empty_signal(state: str, reason_codes: Sequence[str]) -> Dict[str, Any]:
    return {
        "state": state,
        "score": 0,
        "severity": "NONE",
        "current_relevance": "NONE",
        "confidence": "LOW",
        "source_event_id": None,
        "source_event_status": None,
        "source_event_last_evidence_date": None,
        "reason_codes": list(reason_codes),
        "evidence_breadth": 0,
        "auxiliary_evidence_breadth": 0,
        "metric_confirmations": {
            "drawdown_confirmed": False,
            "down_volume_confirmed": False,
            "relative_underperformance_confirmed": False,
            "failed_recovery_confirmed": False,
        },
        "interpretation_note": cfg.SIGNAL_NOTE,
    }


def _select_primary_event(events: Sequence[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    candidates = [e for e in events if isinstance(e, Mapping)]
    if not candidates:
        return None
    return max(candidates, key=_event_rank)


def _event_rank(event: Mapping[str, Any]) -> Tuple[int, int, int, int, int]:
    status = str(event.get("status", ""))
    intensity = str(event.get("intensity", "NONE") or "NONE")
    severity = _severity_rank(intensity)
    recent = _is_recent_event(event)
    core_count = _core_count(event)
    peak_score = _safe_int(event.get("peak_pressure_score"), default=0)
    duration = _safe_int(event.get("duration_days"), default=0)

    if status == "active" and intensity == "HIGH":
        base = 900
    elif status == "failed_recovery" and intensity == "HIGH":
        base = 850
    elif status == "cooling" and intensity == "HIGH":
        base = 800
    elif status == "active" and intensity == "ELEVATED":
        base = 750
    elif status == "failed_recovery" and intensity == "ELEVATED":
        base = 700
    elif status == "cooling" and intensity == "ELEVATED":
        base = 650
    elif status == "active":
        base = 600
    elif status == "failed_recovery":
        base = 560
    elif status == "cooling":
        base = 530
    elif status == "resolved" and recent and intensity == "HIGH":
        base = 500
    elif status == "resolved" and recent:
        base = 400 + severity * 20
    else:
        base = 100 + severity * 20

    quiet_days = _quiet_days(event)
    recency = -quiet_days if quiet_days is not None else -9999
    return (base, peak_score, core_count, recency, duration)


def _event_facts(event: Mapping[str, Any], *, benchmark_available: bool) -> Dict[str, Any]:
    behaviors = tuple(str(b) for b in event.get("observed_behaviors", []) if b)
    core = tuple(b for b in behaviors if b in cfg.CORE_BEHAVIORS)
    aux = tuple(b for b in behaviors if b in cfg.AUXILIARY_BEHAVIORS)
    confirmations = _metric_confirmations(event, benchmark_available=benchmark_available)
    metric_count = sum(1 for v in confirmations.values() if v)
    recent = _is_recent_event(event)
    return {
        "behaviors": behaviors,
        "core_behaviors": core,
        "auxiliary_behaviors": aux,
        "core_count": len(core),
        "auxiliary_count": len(aux),
        "metric_confirmations": confirmations,
        "metric_confirmation_count": metric_count,
        "benchmark_available": bool(benchmark_available),
        "recent": recent,
        "historical": str(event.get("status")) == "resolved" and not recent,
    }


def _metric_confirmations(
    event: Mapping[str, Any],
    *,
    benchmark_available: bool,
) -> Dict[str, bool]:
    m = event.get("metrics") or {}
    max_dd = _safe_float(m.get("max_drawdown"))
    down_share = _safe_float(m.get("down_day_volume_share"))
    rel_under = _safe_float(m.get("relative_underperformance"))
    recovery = _safe_float(m.get("recovery_ratio"))

    drawdown = max_dd is not None and max_dd <= cfg.FAILED_RECOVERY_DD_THRESHOLD
    return {
        "drawdown_confirmed": bool(drawdown),
        "down_volume_confirmed": bool(
            down_share is not None
            and down_share >= cfg.DOWN_VOLUME_SHARE_THRESHOLD
        ),
        "relative_underperformance_confirmed": bool(
            benchmark_available
            and rel_under is not None
            and rel_under <= cfg.REL_UNDERPERFORM_20D_THRESHOLD
        ),
        "failed_recovery_confirmed": bool(
            drawdown
            and recovery is not None
            and recovery <= cfg.FAILED_RECOVERY_RATIO_MAX
        ),
    }


def _score_event(event: Mapping[str, Any], facts: Mapping[str, Any]) -> Tuple[int, List[str]]:
    status = str(event.get("status", ""))
    intensity = str(event.get("intensity", "NONE") or "NONE")
    lifecycle_key = "historical_resolved" if facts["historical"] else (
        "recent_resolved" if status == "resolved" else status
    )
    score = cfg.SIGNAL_LIFECYCLE_BASE.get(lifecycle_key, 0)
    score += cfg.SIGNAL_SEVERITY_BASE.get(intensity, 0)
    score += min(
        int(facts["core_count"]) * cfg.SIGNAL_CORE_BEHAVIOR_BONUS,
        cfg.SIGNAL_CORE_BEHAVIOR_BONUS_CAP,
    )

    confirmations = facts["metric_confirmations"]
    reasons: List[str] = []
    if confirmations["drawdown_confirmed"]:
        score += cfg.SIGNAL_DRAWDOWN_CONFIRM_BONUS
        reasons.append("drawdown_confirmed")
    if confirmations["down_volume_confirmed"]:
        score += cfg.SIGNAL_DOWN_VOLUME_CONFIRM_BONUS
        reasons.append("down_volume_confirmed")
    if confirmations["relative_underperformance_confirmed"]:
        score += cfg.SIGNAL_RELATIVE_CONFIRM_BONUS
        reasons.append("relative_underperformance_confirmed")
    if confirmations["failed_recovery_confirmed"]:
        score += cfg.SIGNAL_FAILED_RECOVERY_CONFIRM_BONUS
        reasons.append("failed_recovery_confirmed")

    if facts["historical"]:
        score = min(score, cfg.SIGNAL_HISTORICAL_SCORE_CAP)
        reasons.append("historical_score_cap")
    if int(facts["core_count"]) <= 1:
        score = min(score, cfg.SIGNAL_SINGLE_CORE_SCORE_CAP)
        reasons.append("single_core_evidence_cap")

    return min(100, int(score)), reasons


def _state_for_event(
    event: Mapping[str, Any],
    facts: Mapping[str, Any],
    score: int,
) -> str:
    status = str(event.get("status", ""))
    intensity = str(event.get("intensity", "NONE") or "NONE")
    core_count = int(facts["core_count"])
    aux_count = int(facts["auxiliary_count"])
    confirmations = facts["metric_confirmations"]

    if facts["historical"]:
        return cfg.SIGNAL_STATE_HISTORICAL_ONLY
    if core_count == 0 and aux_count < 2:
        return cfg.SIGNAL_STATE_WATCH
    if status == "failed_recovery" and confirmations["failed_recovery_confirmed"] and core_count >= 2:
        return cfg.SIGNAL_STATE_FAILED_RECOVERY
    if status == "active" and intensity == "HIGH" and core_count >= 3:
        return cfg.SIGNAL_STATE_ACTIVE_HIGH
    if status == "active" and core_count >= 2:
        return cfg.SIGNAL_STATE_ACTIVE
    if status == "cooling" and core_count >= 2:
        return cfg.SIGNAL_STATE_COOLING
    if status == "resolved" and facts["recent"] and intensity in {"HIGH", "ELEVATED"} and core_count >= 2:
        return cfg.SIGNAL_STATE_RECENT_RESOLVED
    if score > 0:
        return cfg.SIGNAL_STATE_WATCH
    return cfg.SIGNAL_STATE_NO_RECENT


def _confidence_for_event(facts: Mapping[str, Any]) -> str:
    core_count = int(facts["core_count"])
    metric_count = int(facts["metric_confirmation_count"])
    benchmark_available = bool(facts["benchmark_available"])

    if benchmark_available and core_count >= 3 and metric_count >= 3:
        return "HIGH"
    if core_count >= 2 and metric_count >= 2:
        return "MEDIUM"
    return "LOW"


def _current_relevance(event: Mapping[str, Any], facts: Mapping[str, Any]) -> str:
    status = str(event.get("status", ""))
    if facts["historical"]:
        return "HISTORICAL"
    return {
        "active": "ACTIVE",
        "cooling": "COOLING",
        "failed_recovery": "FAILED_RECOVERY",
        "resolved": "RECENT_RESOLVED",
    }.get(status, "WATCH")


def _reason_codes(
    event: Mapping[str, Any],
    facts: Mapping[str, Any],
    score_reasons: Iterable[str],
) -> List[str]:
    reasons: List[str] = []
    status = str(event.get("status", ""))
    intensity = str(event.get("intensity", "NONE") or "NONE")

    if facts["historical"]:
        reasons.append("historical_resolved_event")
    elif status:
        reasons.append(f"{status}_event")
    if intensity in {"HIGH", "ELEVATED"}:
        reasons.append(f"{intensity.lower()}_intensity")
    if int(facts["core_count"]) >= 2:
        reasons.append("multi_behavior_confirmation")
    for behavior in facts["core_behaviors"]:
        reasons.append(str(behavior))
    if not facts["benchmark_available"]:
        reasons.append("benchmark_unavailable")
    reasons.extend(score_reasons)
    return _dedupe(reasons)


def _is_recent_event(event: Mapping[str, Any]) -> bool:
    status = str(event.get("status", ""))
    if status in {"active", "cooling", "failed_recovery"}:
        return True
    quiet_days = _quiet_days(event)
    return quiet_days is not None and quiet_days <= cfg.SIGNAL_RECENT_EVENT_DAYS


def _quiet_days(event: Mapping[str, Any]) -> Optional[int]:
    metrics = event.get("metrics") or {}
    value = metrics.get("quiet_days_after")
    return _safe_int(value, default=None)


def _core_count(event: Mapping[str, Any]) -> int:
    behaviors = event.get("observed_behaviors") or []
    return sum(1 for b in behaviors if b in cfg.CORE_BEHAVIORS)


def _severity_rank(intensity: str) -> int:
    return {"NONE": 0, "WATCH": 1, "MODERATE": 2, "ELEVATED": 3, "HIGH": 4}.get(intensity, 0)


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f


def _safe_int(value: Any, default: Optional[int] = 0) -> Optional[int]:
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _dedupe(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out

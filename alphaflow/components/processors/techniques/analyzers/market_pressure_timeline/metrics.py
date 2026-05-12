"""
Market Pressure Timeline Metrics
================================
Pure, past-only OHLCV / benchmark-relative evidence computation.

Daily evidence points never use future rows.  Historical event status is added
later by segmenter.py, where future quiet days may confirm that an older event
has ended.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import config as cfg


@dataclass(frozen=True)
class DailyEvidencePoint:
    idx: int
    date: str
    score: int
    tier: str
    observed_behaviors: Tuple[str, ...]
    metrics: Mapping[str, Any]
    close: Optional[float] = None

    @property
    def is_event_evidence(self) -> bool:
        return self.score >= cfg.EVENT_TRIGGER_SCORE

    def to_output(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "pressure_score": int(self.score),
            "tier": self.tier,
            "observed_behaviors": list(self.observed_behaviors),
            "metrics": dict(self.metrics),
        }


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------
def safe_round(value: Any, ndigits: int = 4) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(f):
        return None
    return round(f, ndigits)


def _safe_bool(value: Any) -> bool:
    try:
        return bool(value)
    except Exception:
        return False


def _as_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([np.nan] * len(df), index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").astype("float64")


def ensure_sorted(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    if "date" in df.columns:
        out = df.copy()
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["date"])
        return out.sort_values("date", kind="mergesort").reset_index(drop=True)
    return df.reset_index(drop=True)


def format_date(value: Any, fallback_idx: int) -> str:
    try:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.notna(ts):
            return ts.strftime("%Y-%m-%d")
    except Exception:
        pass
    return str(fallback_idx)


def classify_pressure_score(score: int) -> str:
    for threshold, label in cfg.PRESSURE_TIER_THRESHOLDS:
        if score >= threshold:
            return label
    return "NONE"


def ordered_behaviors(behaviors: Sequence[str]) -> Tuple[str, ...]:
    seen = set()
    unique = [b for b in behaviors if not (b in seen or seen.add(b))]
    priority = {label: i for i, label in enumerate(cfg.BEHAVIOR_PRIORITY)}
    return tuple(sorted(unique, key=lambda b: priority.get(b, len(priority))))


def _rolling_pct_rank(series: pd.Series, window: int) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").astype("float64")

    def _rank(values: np.ndarray) -> float:
        if len(values) < 2:
            return np.nan
        today = values[-1]
        past = values[:-1]
        if not np.isfinite(today):
            return np.nan
        past = past[np.isfinite(past)]
        if past.size == 0:
            return np.nan
        below = (past < today).sum()
        equal = (past == today).sum()
        return float((below + 0.5 * equal) / past.size * 100.0)

    return s.rolling(window + 1, min_periods=max(6, window // 4)).apply(_rank, raw=True)


def _rolling_window_return(close: pd.Series, window: int) -> pd.Series:
    c = pd.to_numeric(close, errors="coerce").astype("float64")
    first = c.shift(window - 1)
    return ((c - first) / first.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)


def _rolling_max_drawdown(close: pd.Series, window: int) -> pd.Series:
    c = pd.to_numeric(close, errors="coerce").astype("float64")

    def _mdd(values: np.ndarray) -> float:
        values = values[np.isfinite(values)]
        if values.size < 2:
            return np.nan
        running_peak = np.maximum.accumulate(values)
        safe_peak = np.where(running_peak > 0, running_peak, np.nan)
        dd = (values - safe_peak) / safe_peak
        return float(np.nanmin(dd)) if np.isfinite(dd).any() else np.nan

    return c.rolling(window, min_periods=max(5, window // 4)).apply(_mdd, raw=True)


def _recovery_ratio_series(close: pd.Series, window: int) -> pd.Series:
    c = pd.to_numeric(close, errors="coerce").astype("float64")
    values: List[float] = []
    for i in range(len(c)):
        start = max(0, i - window + 1)
        win = c.iloc[start:i + 1].dropna()
        if len(win) < 5:
            values.append(np.nan)
            continue
        peak_pos = int(np.argmax(win.to_numpy(dtype=float)))
        trough_pos = int(np.argmin(win.to_numpy(dtype=float)))
        peak = float(win.iloc[peak_pos])
        trough = float(win.iloc[trough_pos])
        latest = float(win.iloc[-1])
        if peak_pos < trough_pos and peak > trough:
            values.append((latest - trough) / (peak - trough))
        else:
            values.append(1.0)
    return pd.Series(values, index=c.index, dtype="float64")


def _close_location_value(df: pd.DataFrame) -> pd.Series:
    high = _as_numeric(df, "high")
    low = _as_numeric(df, "low")
    close = _as_numeric(df, "close")
    rng = (high - low).where((high - low) > 0, np.nan)
    return (2.0 * (close - low) / rng - 1.0).astype("float64")


# ---------------------------------------------------------------------------
# Benchmark handling
# ---------------------------------------------------------------------------
def attach_benchmark_columns(
    stock_df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Left-join benchmark close/volume to stock dates.

    The stock timeline is preserved.  Missing benchmark rows become NaN and are
    treated as unavailable for relative evidence on those dates.
    """
    stock = ensure_sorted(stock_df)
    if benchmark_df is None or benchmark_df.empty or "date" not in stock.columns:
        return stock, {"benchmark_available": False, "alignment_missing_days": len(stock)}

    if "date" not in benchmark_df.columns or "close" not in benchmark_df.columns:
        return stock, {"benchmark_available": False, "alignment_missing_days": len(stock)}

    bench = ensure_sorted(benchmark_df)
    keep = ["date", "close"]
    if "volume" in bench.columns:
        keep.append("volume")
    bench = bench[keep].copy()
    bench = bench.rename(columns={"close": "benchmark_close", "volume": "benchmark_volume"})

    merged = stock.merge(bench, on="date", how="left", sort=False)
    available = int(pd.to_numeric(merged.get("benchmark_close"), errors="coerce").notna().sum())
    missing = max(0, len(stock) - available)
    return merged, {
        "benchmark_available": bool(available >= cfg.MIN_DAYS_FOR_TIMELINE // 2),
        "alignment_missing_days": int(missing),
    }


# ---------------------------------------------------------------------------
# Daily evidence computation
# ---------------------------------------------------------------------------
def compute_daily_evidence_points(df: pd.DataFrame) -> List[DailyEvidencePoint]:
    """
    Compute past-only daily objective pressure evidence.

    Expects stock OHLCV columns and optionally `benchmark_close` already aligned
    by date.  All rolling baselines are shifted or trailing-only.
    """
    if df is None or df.empty or "close" not in df.columns:
        return []

    data = ensure_sorted(df)
    close = _as_numeric(data, "close")
    volume = _as_numeric(data, "volume")
    ret = close.pct_change()
    clv = _close_location_value(data)

    vol_baseline = volume.shift(1).rolling(
        cfg.VOLUME_BASELINE_WINDOW,
        min_periods=max(10, cfg.VOLUME_BASELINE_WINDOW // 4),
    ).mean()
    vol_ratio = (volume / vol_baseline.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    vol_pct = _rolling_pct_rank(volume, cfg.VOLUME_BASELINE_WINDOW)

    roll: Dict[str, pd.Series] = {}
    for window in cfg.EVIDENCE_WINDOWS:
        key = f"{window}d"
        roll[f"return_{key}"] = _rolling_window_return(close, window)
        peak = close.rolling(window, min_periods=max(5, window // 4)).max()
        roll[f"drawdown_{key}"] = ((close - peak) / peak.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        roll[f"max_drawdown_{key}"] = _rolling_max_drawdown(close, window)

        valid_ret_count = ret.rolling(window, min_periods=max(5, window // 4)).count()
        down_count = (ret < 0).astype(float).rolling(window, min_periods=max(5, window // 4)).sum()
        roll[f"neg_day_ratio_{key}"] = (down_count / valid_ret_count.replace(0, np.nan)).astype("float64")

        total_vol = volume.rolling(window, min_periods=max(5, window // 4)).sum()
        down_vol = volume.where(ret < 0, 0.0).rolling(window, min_periods=max(5, window // 4)).sum()
        up_vol = volume.where(ret > 0, 0.0).rolling(window, min_periods=max(5, window // 4)).sum()
        up_count = (ret > 0).astype(float).rolling(window, min_periods=max(5, window // 4)).sum()
        down_avg = down_vol / down_count.replace(0, np.nan)
        up_avg = up_vol / up_count.replace(0, np.nan)
        roll[f"down_volume_share_{key}"] = (down_vol / total_vol.replace(0, np.nan)).astype("float64")
        roll[f"down_up_volume_ratio_{key}"] = (down_avg / up_avg.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        roll[f"recovery_ratio_{key}"] = _recovery_ratio_series(close, window)

    if "benchmark_close" in data.columns:
        benchmark_close = _as_numeric(data, "benchmark_close")
        rel_ret = ret - benchmark_close.pct_change()
        for window in cfg.EVIDENCE_WINDOWS:
            key = f"{window}d"
            stock_win = _rolling_window_return(close, window)
            bench_win = _rolling_window_return(benchmark_close, window)
            roll[f"relative_underperformance_{key}"] = (stock_win - bench_win).replace([np.inf, -np.inf], np.nan)
        roll["underperform_day_ratio_20d"] = (rel_ret < 0).astype(float).rolling(
            20, min_periods=5,
        ).mean()
    else:
        rel_ret = pd.Series([np.nan] * len(data), index=data.index, dtype="float64")
        roll["relative_underperformance_20d"] = pd.Series([np.nan] * len(data), index=data.index)
        roll["relative_underperformance_60d"] = pd.Series([np.nan] * len(data), index=data.index)
        roll["underperform_day_ratio_20d"] = pd.Series([np.nan] * len(data), index=data.index)

    points: List[DailyEvidencePoint] = []
    for i in range(len(data)):
        metrics = _metrics_for_idx(
            i=i,
            ret=ret,
            clv=clv,
            vol_ratio=vol_ratio,
            vol_pct=vol_pct,
            roll=roll,
        )
        score, behaviors = _score_metrics(metrics)
        date = format_date(data["date"].iloc[i], i) if "date" in data.columns else str(i)
        points.append(DailyEvidencePoint(
            idx=i,
            date=date,
            score=score,
            tier=classify_pressure_score(score),
            observed_behaviors=behaviors,
            metrics=metrics,
            close=safe_round(close.iloc[i], 6),
        ))
    return points


def _metrics_for_idx(
    i: int,
    ret: pd.Series,
    clv: pd.Series,
    vol_ratio: pd.Series,
    vol_pct: pd.Series,
    roll: Mapping[str, pd.Series],
) -> Dict[str, Any]:
    return {
        "daily_return": safe_round(ret.iloc[i], 4),
        "volume_ratio_60d": safe_round(vol_ratio.iloc[i], 4),
        "volume_percentile_60d": safe_round(vol_pct.iloc[i], 2),
        "close_location_value": safe_round(clv.iloc[i], 4),
        "return_20d": safe_round(roll["return_20d"].iloc[i], 4),
        "return_60d": safe_round(roll["return_60d"].iloc[i], 4),
        "drawdown_20d": safe_round(roll["drawdown_20d"].iloc[i], 4),
        "drawdown_60d": safe_round(roll["drawdown_60d"].iloc[i], 4),
        "max_drawdown_60d": safe_round(roll["max_drawdown_60d"].iloc[i], 4),
        "neg_day_ratio_20d": safe_round(roll["neg_day_ratio_20d"].iloc[i], 4),
        "neg_day_ratio_60d": safe_round(roll["neg_day_ratio_60d"].iloc[i], 4),
        "down_volume_share_20d": safe_round(roll["down_volume_share_20d"].iloc[i], 4),
        "down_volume_share_60d": safe_round(roll["down_volume_share_60d"].iloc[i], 4),
        "down_up_volume_ratio_20d": safe_round(roll["down_up_volume_ratio_20d"].iloc[i], 4),
        "down_up_volume_ratio_60d": safe_round(roll["down_up_volume_ratio_60d"].iloc[i], 4),
        "recovery_ratio_60d": safe_round(roll["recovery_ratio_60d"].iloc[i], 4),
        "relative_underperformance_20d": safe_round(roll["relative_underperformance_20d"].iloc[i], 4),
        "relative_underperformance_60d": safe_round(roll["relative_underperformance_60d"].iloc[i], 4),
        "underperform_day_ratio_20d": safe_round(roll["underperform_day_ratio_20d"].iloc[i], 4),
    }


def _score_metrics(metrics: Mapping[str, Any]) -> Tuple[int, Tuple[str, ...]]:
    score = 0
    behaviors: List[str] = []

    daily_return = metrics.get("daily_return")
    vol_ratio = metrics.get("volume_ratio_60d")
    vol_pct = metrics.get("volume_percentile_60d")
    clv = metrics.get("close_location_value")
    dd20 = metrics.get("drawdown_20d")
    dd60 = metrics.get("drawdown_60d")
    max_dd60 = metrics.get("max_drawdown_60d")
    neg20 = metrics.get("neg_day_ratio_20d")
    neg60 = metrics.get("neg_day_ratio_60d")
    down_share20 = metrics.get("down_volume_share_20d")
    down_share60 = metrics.get("down_volume_share_60d")
    down_up20 = metrics.get("down_up_volume_ratio_20d")
    down_up60 = metrics.get("down_up_volume_ratio_60d")
    recovery60 = metrics.get("recovery_ratio_60d")
    rel20 = metrics.get("relative_underperformance_20d")
    rel60 = metrics.get("relative_underperformance_60d")
    under_ratio20 = metrics.get("underperform_day_ratio_20d")

    elevated_volume = _gte(vol_ratio, cfg.VOLUME_RATIO_ELEVATED) and _gte(vol_pct, cfg.VOLUME_PERCENTILE_ELEVATED)
    spike_volume = _gte(vol_ratio, cfg.VOLUME_RATIO_SPIKE) and _gte(vol_pct, cfg.VOLUME_PERCENTILE_SPIKE)
    down_day = _lte(daily_return, cfg.DOWN_DAY_RETURN_THRESHOLD)
    if down_day and elevated_volume:
        score += cfg.BEHAVIOR_WEIGHTS[cfg.BEHAVIOR_DOWN_DAY_ABNORMAL_VOLUME] + (6 if spike_volume else 0)
        behaviors.append(cfg.BEHAVIOR_DOWN_DAY_ABNORMAL_VOLUME)
    elif elevated_volume:
        score += cfg.BEHAVIOR_WEIGHTS[cfg.BEHAVIOR_ABNORMAL_VOLUME]
        behaviors.append(cfg.BEHAVIOR_ABNORMAL_VOLUME)

    down_concentration = (
        _gte(down_share60, cfg.DOWN_VOLUME_SHARE_THRESHOLD)
        and _gte(down_up60, cfg.DOWN_UP_VOLUME_RATIO_THRESHOLD)
        and _gte(neg60, cfg.NEG_DAY_RATIO_THRESHOLD)
    ) or (
        _gte(down_share20, cfg.DOWN_VOLUME_SHARE_THRESHOLD + 0.03)
        and _gte(down_up20, cfg.DOWN_UP_VOLUME_RATIO_THRESHOLD + 0.10)
        and _gte(neg20, cfg.NEG_DAY_RATIO_THRESHOLD)
    )
    if down_concentration:
        score += cfg.BEHAVIOR_WEIGHTS[cfg.BEHAVIOR_DOWN_DAY_VOLUME_CONCENTRATION]
        behaviors.append(cfg.BEHAVIOR_DOWN_DAY_VOLUME_CONCENTRATION)

    price_drawdown = (
        _lte(dd20, cfg.DRAWDOWN_20D_THRESHOLD)
        or _lte(dd60, cfg.DRAWDOWN_60D_THRESHOLD)
        or _lte(max_dd60, cfg.MAX_DRAWDOWN_60D_THRESHOLD)
    )
    if price_drawdown:
        score += cfg.BEHAVIOR_WEIGHTS[cfg.BEHAVIOR_PRICE_DRAWDOWN_FROM_PEAK]
        behaviors.append(cfg.BEHAVIOR_PRICE_DRAWDOWN_FROM_PEAK)

    if _gte(neg60, cfg.NEG_DAY_RATIO_THRESHOLD + 0.03) or _gte(neg20, cfg.NEG_DAY_RATIO_THRESHOLD + 0.08):
        score += cfg.BEHAVIOR_WEIGHTS[cfg.BEHAVIOR_PERSISTENT_DOWN_DAYS]
        behaviors.append(cfg.BEHAVIOR_PERSISTENT_DOWN_DAYS)

    relative_under = (
        _lte(rel20, cfg.REL_UNDERPERFORM_20D_THRESHOLD)
        or _lte(rel60, cfg.REL_UNDERPERFORM_60D_THRESHOLD)
        or (
            _gte(under_ratio20, cfg.UNDERPERFORM_DAY_RATIO_THRESHOLD)
            and (_lte(rel20, cfg.REL_UNDERPERFORM_20D_THRESHOLD / 2.0)
                 or _lte(rel60, cfg.REL_UNDERPERFORM_60D_THRESHOLD / 2.0))
        )
    )
    if relative_under:
        score += cfg.BEHAVIOR_WEIGHTS[cfg.BEHAVIOR_RELATIVE_UNDERPERFORMANCE]
        behaviors.append(cfg.BEHAVIOR_RELATIVE_UNDERPERFORMANCE)

    failed_recovery = (
        _lte(max_dd60, cfg.FAILED_RECOVERY_DD_THRESHOLD)
        and recovery60 is not None
        and _lte(recovery60, cfg.FAILED_RECOVERY_RATIO_MAX)
    )
    if failed_recovery:
        score += cfg.BEHAVIOR_WEIGHTS[cfg.BEHAVIOR_FAILED_RECOVERY]
        behaviors.append(cfg.BEHAVIOR_FAILED_RECOVERY)

    if _lte(clv, cfg.WEAK_CLV_THRESHOLD):
        score += cfg.BEHAVIOR_WEIGHTS[cfg.BEHAVIOR_WEAK_CLOSE_LOCATION]
        behaviors.append(cfg.BEHAVIOR_WEAK_CLOSE_LOCATION)

    material_single_day_pressure = (
        down_day
        and spike_volume
        and _lte(daily_return, cfg.DRAWDOWN_20D_THRESHOLD / 2.0)
    )
    if not (price_drawdown or failed_recovery or material_single_day_pressure):
        score = min(score, cfg.EVENT_TRIGGER_SCORE - 1)

    return min(100, int(score)), ordered_behaviors(behaviors)


def _gte(value: Any, threshold: float) -> bool:
    return value is not None and _safe_bool(float(value) >= threshold)


def _lte(value: Any, threshold: float) -> bool:
    return value is not None and _safe_bool(float(value) <= threshold)


def select_daily_points(
    points: Sequence[DailyEvidencePoint],
    max_points: int = cfg.DAILY_POINTS_MAX,
) -> Tuple[List[Dict[str, Any]], int, bool]:
    evidence = [p for p in points if p.is_event_evidence]
    truncated = len(evidence) > max_points
    selected = evidence[-max_points:] if truncated else evidence
    return [p.to_output() for p in selected], len(evidence), truncated

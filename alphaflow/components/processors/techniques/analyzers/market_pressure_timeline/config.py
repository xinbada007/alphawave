"""
Market Pressure Timeline Configuration
======================================
Objective market-behavior thresholds for the market pressure timeline.

This module intentionally contains no event/corporate-action concepts.  All
labels describe observable OHLCV / benchmark-relative behavior only.
"""
from __future__ import annotations

from typing import Final, Mapping, Tuple


# ---------------------------------------------------------------------------
# Window / lifecycle parameters
# ---------------------------------------------------------------------------
MAX_LOOKBACK_DAYS: Final[int] = 500
MIN_DAYS_FOR_TIMELINE: Final[int] = 80

VOLUME_BASELINE_WINDOW: Final[int] = 60
EVIDENCE_WINDOWS: Final[Tuple[int, ...]] = (20, 60)

DAILY_POINTS_MAX: Final[int] = 80
EVENT_TRIGGER_SCORE: Final[int] = 35
EVENT_MERGE_GAP_DAYS: Final[int] = 3
EVENT_CONFIRM_QUIET_DAYS: Final[int] = 5


# ---------------------------------------------------------------------------
# Objective evidence thresholds
# ---------------------------------------------------------------------------
VOLUME_RATIO_ELEVATED: Final[float] = 1.6
VOLUME_RATIO_SPIKE: Final[float] = 2.2
VOLUME_PERCENTILE_ELEVATED: Final[float] = 85.0
VOLUME_PERCENTILE_SPIKE: Final[float] = 93.0

DOWN_DAY_RETURN_THRESHOLD: Final[float] = -0.002
WEAK_CLV_THRESHOLD: Final[float] = -0.20

DRAWDOWN_20D_THRESHOLD: Final[float] = -0.08
DRAWDOWN_60D_THRESHOLD: Final[float] = -0.14
MAX_DRAWDOWN_60D_THRESHOLD: Final[float] = -0.18

NEG_DAY_RATIO_THRESHOLD: Final[float] = 0.52
DOWN_VOLUME_SHARE_THRESHOLD: Final[float] = 0.55
DOWN_UP_VOLUME_RATIO_THRESHOLD: Final[float] = 1.15

REL_UNDERPERFORM_20D_THRESHOLD: Final[float] = -0.04
REL_UNDERPERFORM_60D_THRESHOLD: Final[float] = -0.08
UNDERPERFORM_DAY_RATIO_THRESHOLD: Final[float] = 0.55

FAILED_RECOVERY_DD_THRESHOLD: Final[float] = -0.10
FAILED_RECOVERY_RATIO_MAX: Final[float] = 0.50
RESOLVED_RECOVERY_RATIO_MIN: Final[float] = 0.50


# ---------------------------------------------------------------------------
# Score tiers
# ---------------------------------------------------------------------------
PRESSURE_TIER_THRESHOLDS: Final[Tuple[Tuple[int, str], ...]] = (
    (70, "HIGH"),
    (50, "ELEVATED"),
    (35, "MODERATE"),
    (20, "WATCH"),
    (0,  "NONE"),
)


# ---------------------------------------------------------------------------
# Observable behavior labels
# ---------------------------------------------------------------------------
BEHAVIOR_ABNORMAL_VOLUME: Final[str] = "abnormal_volume"
BEHAVIOR_DOWN_DAY_ABNORMAL_VOLUME: Final[str] = "down_day_abnormal_volume"
BEHAVIOR_DOWN_DAY_VOLUME_CONCENTRATION: Final[str] = "down_day_volume_concentration"
BEHAVIOR_PRICE_DRAWDOWN_FROM_PEAK: Final[str] = "price_drawdown_from_peak"
BEHAVIOR_PERSISTENT_DOWN_DAYS: Final[str] = "persistent_down_days"
BEHAVIOR_RELATIVE_UNDERPERFORMANCE: Final[str] = "relative_underperformance"
BEHAVIOR_FAILED_RECOVERY: Final[str] = "failed_recovery"
BEHAVIOR_WEAK_CLOSE_LOCATION: Final[str] = "weak_close_location"

BEHAVIOR_PRIORITY: Final[Tuple[str, ...]] = (
    BEHAVIOR_DOWN_DAY_ABNORMAL_VOLUME,
    BEHAVIOR_DOWN_DAY_VOLUME_CONCENTRATION,
    BEHAVIOR_PRICE_DRAWDOWN_FROM_PEAK,
    BEHAVIOR_RELATIVE_UNDERPERFORMANCE,
    BEHAVIOR_FAILED_RECOVERY,
    BEHAVIOR_PERSISTENT_DOWN_DAYS,
    BEHAVIOR_ABNORMAL_VOLUME,
    BEHAVIOR_WEAK_CLOSE_LOCATION,
)

BEHAVIOR_WEIGHTS: Final[Mapping[str, int]] = {
    BEHAVIOR_DOWN_DAY_ABNORMAL_VOLUME: 22,
    BEHAVIOR_ABNORMAL_VOLUME: 8,
    BEHAVIOR_DOWN_DAY_VOLUME_CONCENTRATION: 18,
    BEHAVIOR_PRICE_DRAWDOWN_FROM_PEAK: 20,
    BEHAVIOR_PERSISTENT_DOWN_DAYS: 8,
    BEHAVIOR_RELATIVE_UNDERPERFORMANCE: 20,
    BEHAVIOR_FAILED_RECOVERY: 12,
    BEHAVIOR_WEAK_CLOSE_LOCATION: 5,
}


INTERPRETATION_NOTE: Final[str] = (
    "Events describe observable market pressure patterns only; they do not "
    "assert investor identity, intent, or hidden cause."
)


# ---------------------------------------------------------------------------
# Headline signal state machine
# ---------------------------------------------------------------------------
SIGNAL_STATE_NO_RECENT: Final[str] = "NO_RECENT_PRESSURE"
SIGNAL_STATE_HISTORICAL_ONLY: Final[str] = "HISTORICAL_PRESSURE_ONLY"
SIGNAL_STATE_RECENT_RESOLVED: Final[str] = "RECENT_RESOLVED_PRESSURE"
SIGNAL_STATE_WATCH: Final[str] = "WATCH_PRESSURE"
SIGNAL_STATE_COOLING: Final[str] = "COOLING_PRESSURE"
SIGNAL_STATE_ACTIVE: Final[str] = "ACTIVE_PRESSURE"
SIGNAL_STATE_ACTIVE_HIGH: Final[str] = "ACTIVE_HIGH_PRESSURE"
SIGNAL_STATE_FAILED_RECOVERY: Final[str] = "FAILED_RECOVERY_PRESSURE"

SIGNAL_RECENT_EVENT_DAYS: Final[int] = 20

CORE_BEHAVIORS: Final[Tuple[str, ...]] = (
    BEHAVIOR_PRICE_DRAWDOWN_FROM_PEAK,
    BEHAVIOR_DOWN_DAY_VOLUME_CONCENTRATION,
    BEHAVIOR_RELATIVE_UNDERPERFORMANCE,
    BEHAVIOR_FAILED_RECOVERY,
    BEHAVIOR_DOWN_DAY_ABNORMAL_VOLUME,
)

AUXILIARY_BEHAVIORS: Final[Tuple[str, ...]] = (
    BEHAVIOR_PERSISTENT_DOWN_DAYS,
    BEHAVIOR_WEAK_CLOSE_LOCATION,
    BEHAVIOR_ABNORMAL_VOLUME,
)

SIGNAL_LIFECYCLE_BASE: Final[Mapping[str, int]] = {
    "active": 35,
    "failed_recovery": 32,
    "cooling": 25,
    "recent_resolved": 12,
    "historical_resolved": 5,
}

SIGNAL_SEVERITY_BASE: Final[Mapping[str, int]] = {
    "HIGH": 25,
    "ELEVATED": 15,
    "MODERATE": 8,
    "WATCH": 3,
    "NONE": 0,
}

SIGNAL_CORE_BEHAVIOR_BONUS: Final[int] = 6
SIGNAL_CORE_BEHAVIOR_BONUS_CAP: Final[int] = 24
SIGNAL_DRAWDOWN_CONFIRM_BONUS: Final[int] = 8
SIGNAL_DOWN_VOLUME_CONFIRM_BONUS: Final[int] = 8
SIGNAL_RELATIVE_CONFIRM_BONUS: Final[int] = 8
SIGNAL_FAILED_RECOVERY_CONFIRM_BONUS: Final[int] = 10

SIGNAL_HISTORICAL_SCORE_CAP: Final[int] = 35
SIGNAL_SINGLE_CORE_SCORE_CAP: Final[int] = 49

SIGNAL_NOTE: Final[str] = (
    "Headline signal summarizes observable market pressure only; it is not a "
    "prediction or assertion about investor identity, intent, or hidden cause."
)

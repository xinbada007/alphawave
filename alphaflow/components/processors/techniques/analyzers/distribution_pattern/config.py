"""
Distribution Pattern Configuration
===================================
派发型价格形态（CLV / VWAP-deviation / Amihud Illiquidity）的阈值表与窗口配置。

设计原则
--------
- **表驱动**：所有 tier 阈值集中此处；调阈值不需改 metrics / profiler。
- **量纲无关**：CLV ∈ [-1, +1]、VWAP_dev 是百分比、Amihud 是 zscore — 各自独立 tier。
- **审美一致**：tier 字符串使用 SCREAMING_SNAKE_CASE；与 volume_anomaly TIER_ORDER
  风格一致；标签使用 [BRACKET_TAG] 风格呼应 legacy market_analyzer.py。
"""
from __future__ import annotations

from typing import Final, Mapping, Tuple


# =========================================================================
# CLV (Close Location Value)
# =========================================================================
# 标准化 CLV ∈ [-1, +1]：
#   CLV = 2 * (Close - Low) / (High - Low) - 1
#
#   <-0.5 PINNED_LOW   收盘被压回低位 — 强派发尾盘
#   <-0.2 WEAK_CLOSE   收盘偏弱 — 派发倾向
#   < 0.2 NEUTRAL      中性
#   < 0.5 STRONG_CLOSE 收盘偏强 — 吸筹倾向
#   else  PINNED_HIGH  收盘冲顶 — 强吸筹尾盘
CLV_TIERS: Final[Tuple[Tuple[float, str], ...]] = (
    (-0.5, "PINNED_LOW"),
    (-0.2, "WEAK_CLOSE"),
    ( 0.2, "NEUTRAL"),
    ( 0.5, "STRONG_CLOSE"),
    (float("inf"), "PINNED_HIGH"),
)

CLV_WINDOWS: Final[Tuple[int, ...]] = (5, 20, 60)

# 在 20d 窗口内"收盘偏低 (CLV<0)"占比阈值
CLV_WEAK_TREND_PCT_THRESHOLD: Final[float] = 0.55


# =========================================================================
# VWAP Deviation
# =========================================================================
# vwap_dev = (close - vwap) / vwap
#   <-0.02  STRONG_BELOW   显著低于 VWAP — 派发强信号
#   <-0.005 MILDLY_BELOW   轻度低于 VWAP
#   < 0.005 AT_VWAP        贴近 VWAP — 中性
#   < 0.02  MILDLY_ABOVE   轻度高于 VWAP
#   else    STRONG_ABOVE   显著高于 VWAP — 吸筹/拉抬
VWAP_DEV_TIERS: Final[Tuple[Tuple[float, str], ...]] = (
    (-0.02,  "STRONG_BELOW"),
    (-0.005, "MILDLY_BELOW"),
    ( 0.005, "AT_VWAP"),
    ( 0.02,  "MILDLY_ABOVE"),
    (float("inf"), "STRONG_ABOVE"),
)

VWAP_DEV_WINDOWS: Final[Tuple[int, ...]] = (5, 20, 60)
VWAP_BELOW_TREND_PCT_THRESHOLD: Final[float] = 0.60


# =========================================================================
# Amihud Illiquidity
# =========================================================================
# Amihud_t = |return_t| / dollar_volume_t
# 用 zscore 标准化（与 baseline_window 比较），跨股可比
AMIHUD_ZSCORE_TIERS: Final[Tuple[Tuple[float, str], ...]] = (
    (1.0, "NORMAL"),
    (2.0, "ELEVATED"),
    (3.0, "HIGH"),
    (float("inf"), "EXTREME"),
)

AMIHUD_BASELINE_WINDOW: Final[int] = 60
AMIHUD_WINDOWS: Final[Tuple[int, ...]] = (5, 20)


# =========================================================================
# 数据质量门槛
# =========================================================================
MIN_DAYS_FOR_PATTERN: Final[int] = 30

# VWAP 来源标签
VWAP_SOURCE_NATIVE: Final[str] = "native"
VWAP_SOURCE_AMT_VOL: Final[str] = "amount_volume_synthetic"
VWAP_SOURCE_TYPICAL: Final[str] = "typical_price_fallback"
VWAP_SOURCE_NONE: Final[str] = "unavailable"

VWAP_NATIVE_NONNULL_THRESHOLD: Final[float] = 0.80

# Dollar volume 来源
DV_SOURCE_NATIVE: Final[str] = "native_amount"
DV_SOURCE_SYNTHETIC: Final[str] = "close_volume_synthetic"


# =========================================================================
# Summary Tag 映射（[BRACKET_TAG] — 呼应 legacy market_analyzer.py）
# =========================================================================
TAG_CLV_LATEST: Final[Mapping[str, str]] = {
    "PINNED_LOW":    "[CLV_PINNED_LOW]",
    "WEAK_CLOSE":    "[CLV_WEAK_CLOSE]",
    "NEUTRAL":       "[CLV_NEUTRAL]",
    "STRONG_CLOSE":  "[CLV_STRONG_CLOSE]",
    "PINNED_HIGH":   "[CLV_PINNED_HIGH]",
}

TAG_VWAP_LATEST: Final[Mapping[str, str]] = {
    "STRONG_BELOW":  "[VWAP_STRONG_BELOW]",
    "MILDLY_BELOW":  "[VWAP_MILDLY_BELOW]",
    "AT_VWAP":       "[VWAP_AT]",
    "MILDLY_ABOVE":  "[VWAP_MILDLY_ABOVE]",
    "STRONG_ABOVE":  "[VWAP_STRONG_ABOVE]",
}

TAG_AMIHUD_LATEST: Final[Mapping[str, str]] = {
    "NORMAL":   "[AMIHUD_NORMAL]",
    "ELEVATED": "[AMIHUD_ELEVATED]",
    "HIGH":     "[AMIHUD_HIGH]",
    "EXTREME":  "[AMIHUD_EXTREME]",
}

TAG_CLV_WEAK_TREND_20D: Final[str] = "[CLV_WEAK_TREND_20D]"
TAG_VWAP_BELOW_TREND_20D: Final[str] = "[VWAP_BELOW_60PCT_20D]"

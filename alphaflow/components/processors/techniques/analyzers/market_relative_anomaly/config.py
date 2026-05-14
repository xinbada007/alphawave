"""
Market Relative Anomaly — Configuration
========================================
阈值表 / 窗口 / tag 常量。表驱动，所有"魔术数"集中在此。
"""
from __future__ import annotations

from typing import Dict, Final, Tuple

# =========================================================================
# 相对量比 (rel_volume_vs_index)
# =========================================================================
# rel_volume = (stock_vol / stock_vol_ma_N) / (idx_vol / idx_vol_ma_N)
#   含义：扣除大盘节奏后的相对量比
#   < 0.7    LOW           个股放量明显**不及**大盘 → 落后于大盘节奏
#   < 1.2    NORMAL        与大盘同步
#   < 2.0    ELEVATED      显著快于大盘
#   < 3.5    SPIKE         相对放量异常
#   else     HISTORIC      极端相对放量
REL_VOLUME_TIERS: Final[Tuple[Tuple[float, str], ...]] = (
    (0.7, "LOW"),
    (1.2, "NORMAL"),
    (2.0, "ELEVATED"),
    (3.5, "SPIKE"),
    (float("inf"), "HISTORIC"),
)

# =========================================================================
# 相对收益 (rel_return_vs_index)
# =========================================================================
# rel_return = stock_return - index_return  （单日，小数）
REL_RETURN_TIERS: Final[Tuple[Tuple[float, str], ...]] = (
    (-0.05, "STRONG_UNDERPERFORM"),
    (-0.02, "MILD_UNDERPERFORM"),
    ( 0.02, "INLINE"),
    ( 0.05, "MILD_OUTPERFORM"),
    (float("inf"), "STRONG_OUTPERFORM"),
)

# =========================================================================
# 大盘自身放量异常阈值（指数当日 vol_ratio）
# =========================================================================
INDEX_ANOMALOUS_RATIO: Final[float] = 1.8  # 指数 vol/vol_ma_20 > 1.8 视为大盘共振放量

# =========================================================================
# 滚动窗口 / 数据门槛
# =========================================================================
REL_VOLUME_BASELINE_WINDOW: Final[int] = 20
ROLLING_WINDOWS: Final[Tuple[int, ...]] = (5, 20, 60)
ROLLING_PCT_UNDERPERFORM_WINDOW: Final[int] = 20

#: 至少需要这么多天对齐数据才能输出 latest_day + rolling
MIN_DAYS_FOR_PROFILE: Final[int] = 30


# =========================================================================
# Summary tags（[BRACKET] 风格，与 volume_anomaly / distribution_pattern 一致）
# =========================================================================
TAG_REL_VOLUME_LATEST: Final[Dict[str, str]] = {
    "LOW":       "[REL_VOLUME_LOW]",
    "NORMAL":    "[REL_VOLUME_NORMAL]",
    "ELEVATED":  "[REL_VOLUME_ELEVATED]",
    "SPIKE":     "[REL_VOLUME_SPIKE]",
    "HISTORIC":  "[REL_VOLUME_HISTORIC]",
}

TAG_REL_RETURN_LATEST: Final[Dict[str, str]] = {
    "STRONG_UNDERPERFORM": "[REL_RETURN_STRONG_UNDER]",
    "MILD_UNDERPERFORM":   "[REL_RETURN_MILD_UNDER]",
    "INLINE":              "[REL_RETURN_INLINE]",
    "MILD_OUTPERFORM":     "[REL_RETURN_MILD_OUTPERFORM]",
    "STRONG_OUTPERFORM":   "[REL_RETURN_STRONG_OUTPERFORM]",
}

TAG_INDEX_CO_ANOMALY: Final[str] = "[INDEX_CO_ANOMALY]"
TAG_STOCK_OUTPACES_INDEX: Final[str] = "[STOCK_OUTPACES_INDEX_VOLUME_20D]"
TAG_PCT_UNDERPERFORM_20D: Final[str] = "[UNDERPERFORM_INDEX_60PCT_20D]"

#: 触发 [STOCK_OUTPACES_INDEX_VOLUME_20D] 的 20d 平均相对量比阈值
OUTPACE_AVG_THRESHOLD: Final[float] = 1.5
#: 触发 [UNDERPERFORM_INDEX_60PCT_20D] 的 20d 跑输天数占比阈值
UNDERPERFORM_PCT_THRESHOLD: Final[float] = 0.60


# =========================================================================
# benchmark_meta status 常量（与 BenchmarkCollector 输出对齐）
# =========================================================================
BENCH_STATUS_OK: Final[str] = "ok"
BENCH_STATUS_UNAVAILABLE: Final[str] = "unavailable"

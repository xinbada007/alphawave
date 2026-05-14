"""
Volume Anomaly Metrics
=======================
纯函数式数学算子层。所有函数：
- 输入 pandas.Series / DataFrame，输出 dict 或标量
- 无副作用，无 IO，无 ResearchPack 依赖
- 所有 NaN / 边界场景显式返回，绝不抛异常

约定：
- 输入 series 已按时间升序排列（最新在尾部）
- volume / amount / turnover_rate 均可作为输入（量纲不同但语义同质）
"""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from .config import (
    ANOMALY_PERCENTILE_TIERS,
    BASELINE_WINDOW,
    CAV_BASELINE_WINDOW,
    RATIO_GUARDS,
    REGIME_SHIFT_LONG_WINDOW,
    REGIME_SHIFT_RATIO_THRESHOLD,
    REGIME_SHIFT_SHORT_WINDOW,
    TIER_ORDER,
)


# =========================================================================
# 1. 基线计算
# =========================================================================
def compute_rolling_baselines(
    series: pd.Series, baseline_window: int = BASELINE_WINDOW
) -> pd.DataFrame:
    """
    计算每个时点的滚动 baseline 与该点的 percentile rank。

    Returns DataFrame with columns:
        - baseline_mean   : 过去 baseline_window 日均值（不含当日）
        - baseline_std    : 过去 baseline_window 日标准差（不含当日）
        - ratio           : 当日 / baseline_mean
        - zscore          : (当日 - baseline_mean) / baseline_std
        - pct_rank        : 当日在过去 baseline_window 日窗口内的百分位 (0–100)
    """
    s = series.astype("float64")

    # shift(1) 让 baseline 不含当日，避免 look-ahead
    rolling = s.shift(1).rolling(window=baseline_window, min_periods=max(5, baseline_window // 4))
    base_mean = rolling.mean()
    base_std = rolling.std()

    ratio = s / base_mean.replace(0, np.nan)
    zscore = (s - base_mean) / base_std.replace(0, np.nan)

    # percentile rank：当日值在过去 baseline_window 日中的百分位
    # 用 rolling.rank(pct=True) 的实现思路 —— 但 pandas 的 rolling.rank 仅在 1.5+
    # 且不支持 min_periods 与 shift 的组合，这里手写一个清晰版本：
    def _pct_rank(window_vals: np.ndarray) -> float:
        # window_vals 含"当日"在尾部；我们要"当日"在过去窗口的位置
        if len(window_vals) < 2:
            return np.nan
        today = window_vals[-1]
        past = window_vals[:-1]
        if np.all(np.isnan(past)):
            return np.nan
        past_clean = past[~np.isnan(past)]
        if past_clean.size == 0:
            return np.nan
        # 严格小于 + 0.5*相等 (Hyndman/Fan Type 7-ish for ties)
        below = (past_clean < today).sum()
        equal = (past_clean == today).sum()
        return (below + 0.5 * equal) / past_clean.size * 100.0

    # raw=True + min_periods 保证 numpy ndarray 路径，速度更快
    pct_rank = s.rolling(window=baseline_window + 1, min_periods=6).apply(_pct_rank, raw=True)

    return pd.DataFrame({
        "baseline_mean": base_mean,
        "baseline_std": base_std,
        "ratio": ratio,
        "zscore": zscore,
        "pct_rank": pct_rank,
    }, index=s.index)


# =========================================================================
# 2. Tier 分级
# =========================================================================
def classify_anomaly_tier(pct_rank: float, ratio: float) -> str:
    """
    单点分级：百分位**且** ratio 共振才升级。
    返回 TIER_ORDER 中的标签，最低为 "NORMAL"。

    边界：pct_rank/ratio 任一为 NaN 时返回 "NORMAL"（数据不足，保守判定）。
    """
    if pct_rank is None or pd.isna(pct_rank):
        return "NORMAL"
    if ratio is None or pd.isna(ratio):
        return "NORMAL"

    # 从最高级往下扫，第一个满足的即为该点 tier
    # ELEVATED 仅看 percentile，无 ratio 守卫
    tiers_descending = ["HISTORIC", "BLOWOUT", "EXTREME", "SPIKE", "ELEVATED"]
    for tier in tiers_descending:
        pct_threshold = ANOMALY_PERCENTILE_TIERS[tier]
        ratio_threshold = RATIO_GUARDS.get(tier)
        if pct_rank >= pct_threshold:
            if ratio_threshold is None or ratio >= ratio_threshold:
                return tier
    return "NORMAL"


def classify_series(baselines: pd.DataFrame) -> pd.Series:
    """对整个 baselines DataFrame 逐行分级，返回 tier 字符串 Series。"""
    return pd.Series(
        [classify_anomaly_tier(r.pct_rank, r.ratio) for r in baselines.itertuples(index=False)],
        index=baselines.index,
        name="tier",
    )


# =========================================================================
# 3. 区间异常计数
# =========================================================================
def count_anomalies_per_window(
    tiers: pd.Series,
    daily_returns: pd.Series,
    window: int,
) -> Mapping[str, Any]:
    """
    在尾部 `window` 天内统计异常情况。

    返回：
      - period_days: 实际有效天数（停牌等不计入）
      - by_tier:     {tier: count} 各等级计数（含 NORMAL）
      - anomaly_days_total:  非 NORMAL 总天数
      - anomaly_days_down:   非 NORMAL 且当日下跌的天数（潜在派发信号）
      - anomaly_days_up:     非 NORMAL 且当日上涨的天数
      - longest_streak:      连续异常天数最大值
      - latest_tier:         最近一日的 tier
    """
    if len(tiers) == 0 or window <= 0:
        return _empty_count_result()

    tail_tiers = tiers.tail(window)
    tail_rets = daily_returns.reindex(tail_tiers.index)

    # 排除完全无数据的尾段（前期不足 baseline 时 tier 为 NORMAL 但实质是无效）
    period_days = int((tail_tiers != "").sum())  # 防御性：tier 必非空字符串

    by_tier = {t: 0 for t in TIER_ORDER}
    for t in tail_tiers:
        if t in by_tier:
            by_tier[t] += 1

    anomaly_mask = tail_tiers != "NORMAL"
    anomaly_days_total = int(anomaly_mask.sum())

    # 涨跌方向（对齐索引；NaN 视为持平不计入任一方向）
    rets_aligned = tail_rets.fillna(0.0)
    anomaly_days_down = int(((tail_tiers != "NORMAL") & (rets_aligned < 0)).sum())
    anomaly_days_up = int(((tail_tiers != "NORMAL") & (rets_aligned > 0)).sum())

    # 最长连续 streak
    longest = 0
    current = 0
    for is_anom in anomaly_mask:
        if is_anom:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    return {
        "period_days": period_days,
        "by_tier": by_tier,
        "anomaly_days_total": anomaly_days_total,
        "anomaly_days_down": anomaly_days_down,
        "anomaly_days_up": anomaly_days_up,
        "longest_streak": longest,
        "latest_tier": str(tail_tiers.iloc[-1]) if len(tail_tiers) > 0 else "NORMAL",
    }


def _empty_count_result() -> Mapping[str, Any]:
    return {
        "period_days": 0,
        "by_tier": {t: 0 for t in TIER_ORDER},
        "anomaly_days_total": 0,
        "anomaly_days_down": 0,
        "anomaly_days_up": 0,
        "longest_streak": 0,
        "latest_tier": "NORMAL",
    }


# =========================================================================
# 4. CAV (Cumulative Abnormal Volume)
# =========================================================================
def cumulative_abnormal_volume(
    series: pd.Series,
    window: int,
    baseline_window: int = CAV_BASELINE_WINDOW,
) -> float:
    """
    CAV = sum(window 内的 (实际值 - baseline_mean)) / baseline_mean
    用于"过去 N 日累计异常成交量相对于常态的比例"。

    边界：数据不足时返回 NaN。
    """
    s = series.astype("float64")
    if len(s) < window + 1:
        return float("nan")
    recent = s.tail(window)
    baseline_slice = s.shift(window).tail(baseline_window).dropna()
    if baseline_slice.empty:
        return float("nan")
    base_mean = baseline_slice.mean()
    if not np.isfinite(base_mean) or base_mean == 0:
        return float("nan")
    abnormal = (recent - base_mean).sum()
    return float(abnormal / (base_mean * window)) if base_mean > 0 else float("nan")


# =========================================================================
# 5. Regime Shift
# =========================================================================
def detect_regime_shift(
    series: pd.Series,
    short_window: int = REGIME_SHIFT_SHORT_WINDOW,
    long_window: int = REGIME_SHIFT_LONG_WINDOW,
) -> Mapping[str, Any]:
    """
    判断最近一段时间是否相对长期窗口出现"成交结构性放大"。

    Returns:
        - adv_short / adv_long
        - ratio
        - shifted: bool (ratio >= REGIME_SHIFT_RATIO_THRESHOLD)
    数据不足或 long 均值为 0 时，shifted=False, 各值为 NaN。
    """
    s = series.astype("float64")
    if len(s) < long_window:
        return {"adv_short": float("nan"), "adv_long": float("nan"),
                "ratio": float("nan"), "shifted": False}
    adv_short = float(s.tail(short_window).mean())
    adv_long = float(s.tail(long_window).mean())
    if not np.isfinite(adv_long) or adv_long <= 0:
        return {"adv_short": adv_short, "adv_long": adv_long,
                "ratio": float("nan"), "shifted": False}
    ratio = adv_short / adv_long
    return {
        "adv_short": adv_short,
        "adv_long": adv_long,
        "ratio": ratio,
        "shifted": bool(ratio >= REGIME_SHIFT_RATIO_THRESHOLD),
    }


# =========================================================================
# 6. 数据质量
# =========================================================================
def assess_data_quality(df: pd.DataFrame, lookback_window: int) -> Mapping[str, Any]:
    """
    评估 df 用于 lookback_window 计算时的数据质量。

    返回：
      - lookback_actual_days: tail(lookback) 中非空数据天数
      - has_suspension_gap:   日期序列是否存在 > 5 个交易日缺口
      - ipo_age_days:         数据起点到末端的总天数（粗略估计）
    """
    if df.empty:
        return {"lookback_actual_days": 0, "has_suspension_gap": False, "ipo_age_days": 0}

    tail = df.tail(lookback_window)
    actual = int(tail.dropna(subset=["close"]).shape[0]) if "close" in tail.columns else len(tail)

    has_gap = False
    if "date" in df.columns and len(df) >= 2:
        try:
            dates = pd.to_datetime(df["date"], errors="coerce").dropna().sort_values()
            if len(dates) >= 2:
                diffs = dates.diff().dt.days.dropna()
                # 工作日序列正常 1–3 天，> 7 视为长假/停牌；用 7 作阈值
                has_gap = bool((diffs > 7).any())
        except Exception:
            has_gap = False

    ipo_age = len(df)  # 粗略估计：数据可见天数即"足够长上市时间"的代理
    return {
        "lookback_actual_days": actual,
        "has_suspension_gap": has_gap,
        "ipo_age_days": ipo_age,
    }

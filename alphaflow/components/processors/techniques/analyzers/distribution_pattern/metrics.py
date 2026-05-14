"""
Distribution Pattern Metrics — 纯函数式数学算子层
==================================================
所有函数：
- 输入 pandas.DataFrame / Series，输出 dict 或标量 / Series
- 无副作用，无 IO，无 ResearchPack 依赖
- NaN / inf 显式返回 None / NaN，绝不抛异常
- 量纲无关算子（zscore）与量纲有关算子（CLV / vwap_dev）严格分开
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .config import (
    AMIHUD_BASELINE_WINDOW,
    AMIHUD_ZSCORE_TIERS,
    CLV_TIERS,
    DV_SOURCE_NATIVE,
    DV_SOURCE_SYNTHETIC,
    PATH_PRESSURE_WINDOWS,
    VWAP_DEV_TIERS,
    VWAP_NATIVE_NONNULL_THRESHOLD,
    VWAP_SOURCE_AMT_VOL,
    VWAP_SOURCE_NATIVE,
    VWAP_SOURCE_NONE,
    VWAP_SOURCE_TYPICAL,
)


# =========================================================================
# 辅助
# =========================================================================
def _safe_round(value: Any, ndigits: int = 4) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(f):
        return None
    return round(f, ndigits)


def _classify_by_tiers(
    value: Optional[float],
    tiers: Tuple[Tuple[float, str], ...],
    default: str = "NEUTRAL",
) -> str:
    """通用 tier 分类：从前向后第一个满足 value < threshold 的 tier。"""
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(f):
        return default
    for threshold, label in tiers:
        if f < threshold:
            return label
    return default


# =========================================================================
# VWAP 来源解析（4 级 fallback chain）
# =========================================================================
def resolve_vwap_series(df: pd.DataFrame) -> Tuple[pd.Series, str]:
    """
    返回 (vwap_series, source_label)。

    Fallback：
      1) df['vwap'] 非空率 ≥ 80% → "native"
      2) amount/volume 双在 → 派生 amount/volume → "amount_volume_synthetic"
      3) high+low+close 在 → typical_price=(H+L+C)/3 → "typical_price_fallback"
      4) 都不行 → 全 NaN Series + "unavailable"
    """
    n = len(df) if df is not None else 0
    if n == 0:
        return pd.Series([], dtype="float64"), VWAP_SOURCE_NONE

    if "vwap" in df.columns:
        vwap = pd.to_numeric(df["vwap"], errors="coerce").astype("float64")
        if vwap.notna().sum() / n >= VWAP_NATIVE_NONNULL_THRESHOLD:
            return vwap, VWAP_SOURCE_NATIVE

    if {"amount", "volume"}.issubset(df.columns):
        vol = pd.to_numeric(df["volume"], errors="coerce").replace(0, np.nan)
        amt = pd.to_numeric(df["amount"], errors="coerce")
        amt_vol = (amt / vol).astype("float64")
        if amt_vol.notna().sum() >= 1:
            return amt_vol, VWAP_SOURCE_AMT_VOL

    if {"high", "low", "close"}.issubset(df.columns):
        h = pd.to_numeric(df["high"], errors="coerce").astype("float64")
        l = pd.to_numeric(df["low"],  errors="coerce").astype("float64")
        c = pd.to_numeric(df["close"], errors="coerce").astype("float64")
        tp = ((h + l + c) / 3.0).astype("float64")
        if tp.notna().sum() >= 1:
            return tp, VWAP_SOURCE_TYPICAL

    return pd.Series([np.nan] * n, index=df.index, dtype="float64"), VWAP_SOURCE_NONE


# =========================================================================
# Dollar Volume 来源解析（2 级 fallback chain）
# =========================================================================
def resolve_dollar_volume_series(df: pd.DataFrame) -> Tuple[pd.Series, str]:
    """
    返回 (dollar_volume_series, source_label)。

    Fallback：
      1) df['amount'] 列存在且非空 > 0 → "native_amount"  (HK/CN 真实金额)
      2) 否则 close × volume → "close_volume_synthetic"   (US Amihud 标准近似)
    """
    n = len(df) if df is not None else 0
    if n == 0:
        return pd.Series([], dtype="float64"), DV_SOURCE_SYNTHETIC

    if "amount" in df.columns:
        amt = pd.to_numeric(df["amount"], errors="coerce").astype("float64")
        if amt.notna().sum() > 0:
            return amt, DV_SOURCE_NATIVE

    if {"close", "volume"}.issubset(df.columns):
        c = pd.to_numeric(df["close"],  errors="coerce").astype("float64")
        v = pd.to_numeric(df["volume"], errors="coerce").astype("float64")
        return (c * v).astype("float64"), DV_SOURCE_SYNTHETIC

    return pd.Series([np.nan] * n, index=df.index, dtype="float64"), DV_SOURCE_SYNTHETIC


# =========================================================================
# 1. CLV (Close Location Value)
# =========================================================================
def compute_clv_series(df: pd.DataFrame) -> pd.Series:
    """
    标准化 CLV ∈ [-1, +1]：

        CLV = 2 * (Close - Low) / (High - Low) - 1

    高低相等（H==L）→ NaN（避免除零）。
    """
    h = pd.to_numeric(df["high"],  errors="coerce").astype("float64")
    l = pd.to_numeric(df["low"],   errors="coerce").astype("float64")
    c = pd.to_numeric(df["close"], errors="coerce").astype("float64")
    rng = h - l
    rng_safe = rng.where(rng > 0, np.nan)
    clv = 2.0 * (c - l) / rng_safe - 1.0
    return clv.astype("float64")


def classify_clv(value: Optional[float]) -> str:
    return _classify_by_tiers(value, CLV_TIERS, default="NEUTRAL")


# =========================================================================
# 2. VWAP Deviation
# =========================================================================
def compute_vwap_deviation_series(
    df: pd.DataFrame, vwap_series: pd.Series,
) -> pd.Series:
    """vwap_dev = (close - vwap) / vwap，vwap<=0 / NaN 时返回 NaN。"""
    c = pd.to_numeric(df["close"], errors="coerce").astype("float64")
    v = vwap_series.astype("float64")
    v_safe = v.where(v > 0, np.nan)
    return ((c - v_safe) / v_safe).astype("float64")


def classify_vwap_dev(value: Optional[float]) -> str:
    return _classify_by_tiers(value, VWAP_DEV_TIERS, default="AT_VWAP")


# =========================================================================
# 3. Amihud Illiquidity
# =========================================================================
def compute_amihud_series(
    df: pd.DataFrame, dollar_volume: pd.Series,
) -> pd.Series:
    """
    Amihud_t = |return_t| / dollar_volume_t

    return_t = close.pct_change()。dollar_volume<=0 / NaN → NaN。
    """
    c = pd.to_numeric(df["close"], errors="coerce").astype("float64")
    ret = c.pct_change()
    dv_safe = dollar_volume.where(dollar_volume > 0, np.nan)
    return (ret.abs() / dv_safe).astype("float64")


def compute_amihud_zscore_series(
    amihud: pd.Series, baseline_window: int = AMIHUD_BASELINE_WINDOW,
) -> pd.Series:
    """Rolling zscore（baseline 不含当日，shift(1) 防 look-ahead）。"""
    base = amihud.shift(1)
    min_p = max(5, baseline_window // 4)
    mean = base.rolling(baseline_window, min_periods=min_p).mean()
    std = base.rolling(baseline_window, min_periods=min_p).std(ddof=0)
    std_safe = std.where(std > 0, np.nan)
    return ((amihud - mean) / std_safe).astype("float64")


def classify_amihud_zscore(value: Optional[float]) -> str:
    """zscore 取绝对值落 tier（流动性恶化方向单向：值越大越坏）。"""
    if value is None:
        return "NORMAL"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "NORMAL"
    if not np.isfinite(f):
        return "NORMAL"
    return _classify_by_tiers(abs(f), AMIHUD_ZSCORE_TIERS, default="EXTREME")


# =========================================================================
# 4. Path Pressure（过去路径压力）
# =========================================================================
def compute_path_pressure_block(
    df: pd.DataFrame,
    windows: Tuple[int, ...] = PATH_PRESSURE_WINDOWS,
) -> Dict[str, Any]:
    """
    基于过去窗口的客观市场行为计算路径压力。

    只使用 OHLCV / amount，不使用任何事件层或未来数据。
    返回每个窗口的：
      - return: 窗口起点到最新收盘收益
      - drawdown_from_peak: 最新收盘相对窗口内最高收盘回撤
      - max_drawdown: 窗口内 running-peak 最大回撤
      - neg_day_ratio: 下跌日占比
      - down_volume_share: 下跌日成交量 / 全窗口成交量
      - down_up_volume_ratio: 下跌日均量 / 上涨日均量
      - days_since_peak/trough
      - recovery_ratio: 从 trough 到 latest 的恢复幅度 / |peak-to-trough|
    """
    if df is None or len(df) == 0 or "close" not in df.columns:
        return {}

    close = pd.to_numeric(df["close"], errors="coerce").astype("float64")
    if "volume" in df.columns:
        volume = pd.to_numeric(df["volume"], errors="coerce").astype("float64")
    else:
        volume = pd.Series([np.nan] * len(df), index=df.index, dtype="float64")

    out: Dict[str, Any] = {}
    for window in windows:
        if len(close.dropna()) < max(5, min(window, len(close))):
            continue

        c = close.tail(window).reset_index(drop=True)
        v = volume.tail(window).reset_index(drop=True)
        valid = c.dropna()
        if len(valid) < 5:
            continue

        latest = float(valid.iloc[-1])
        first = float(valid.iloc[0])
        peak_idx = int(valid.idxmax())
        trough_idx = int(valid.idxmin())
        peak = float(valid.loc[peak_idx])
        trough = float(valid.loc[trough_idx])

        window_return = (latest - first) / first if first > 0 else np.nan
        drawdown_from_peak = (latest - peak) / peak if peak > 0 else np.nan

        running_peak = valid.cummax()
        dd_series = (valid - running_peak) / running_peak.replace(0, np.nan)
        max_dd = float(dd_series.min()) if dd_series.notna().any() else np.nan

        ret = valid.pct_change()
        neg_mask = ret < 0
        neg_ratio = float(neg_mask.sum() / ret.dropna().shape[0]) if ret.dropna().shape[0] else np.nan

        v_aligned = v.reindex(valid.index)
        total_vol = float(v_aligned.sum(skipna=True)) if v_aligned.notna().any() else np.nan
        down_vol = float(v_aligned[neg_mask].sum(skipna=True)) if v_aligned.notna().any() else np.nan
        down_volume_share = down_vol / total_vol if total_vol and total_vol > 0 else np.nan

        down_avg = float(v_aligned[neg_mask].mean(skipna=True)) if v_aligned[neg_mask].notna().any() else np.nan
        up_avg = float(v_aligned[ret > 0].mean(skipna=True)) if v_aligned[ret > 0].notna().any() else np.nan
        down_up_volume_ratio = down_avg / up_avg if up_avg and up_avg > 0 else np.nan

        # recovery_ratio 只在 peak 先于 trough 时有派发路径语义；否则记 1（已恢复/非典型）
        if peak_idx < trough_idx and peak > trough:
            recovery_ratio = (latest - trough) / (peak - trough)
        else:
            recovery_ratio = 1.0

        out[f"{window}d"] = {
            "return": _safe_round(window_return, 4),
            "drawdown_from_peak": _safe_round(drawdown_from_peak, 4),
            "max_drawdown": _safe_round(max_dd, 4),
            "neg_day_ratio": _safe_round(neg_ratio, 4),
            "down_volume_share": _safe_round(down_volume_share, 4),
            "down_up_volume_ratio": _safe_round(down_up_volume_ratio, 4),
            "days_since_peak": int(len(valid) - 1 - peak_idx),
            "days_since_trough": int(len(valid) - 1 - trough_idx),
            "recovery_ratio": _safe_round(recovery_ratio, 4),
        }

    return out


# =========================================================================
# 5. 滚动统计
# =========================================================================
def rolling_avg(series: pd.Series, window: int) -> Optional[float]:
    """series 尾部 window 个有效值的平均。"""
    s = series.dropna().tail(window)
    if len(s) == 0:
        return None
    return float(s.mean())


def rolling_pct_below(
    series: pd.Series, window: int, threshold: float = 0.0,
) -> Optional[float]:
    """series 尾部 window 个有效值中 < threshold 的占比。"""
    s = series.dropna().tail(window)
    if len(s) == 0:
        return None
    return float((s < threshold).sum() / len(s))


# =========================================================================
# 6. 数据质量评估
# =========================================================================
def assess_data_quality(df: pd.DataFrame) -> Dict[str, Any]:
    """基础信息（vwap_source / dv_source 由 profiler 在 resolve_*_series 后填）。"""
    n = len(df) if df is not None else 0
    if n == 0:
        return {
            "lookback_actual_days": 0,
            "has_suspension_gap": False,
            "ipo_age_days": 0,
        }

    suspension_gap = False
    if "volume" in df.columns:
        zero_vol = (pd.to_numeric(df["volume"], errors="coerce").fillna(0) == 0).sum()
        suspension_gap = bool(zero_vol >= 3)

    return {
        "lookback_actual_days": int(n),
        "has_suspension_gap": suspension_gap,
        "ipo_age_days": int(n),
    }

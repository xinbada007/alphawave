"""
Market Relative Anomaly — Pure Metrics
========================================
纯函数算子层（NaN 安全 / 不依赖 pack / 不写日志）。

四区段：
  - alignment    : align_by_date 内连接
  - compute      : 相对量比 / 相对收益 / 指数自身异常
  - classify     : tier 分类
  - aggregate    : rolling avg / rolling pct
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from .config import (
    INDEX_ANOMALOUS_RATIO,
    REL_RETURN_TIERS,
    REL_VOLUME_BASELINE_WINDOW,
    REL_VOLUME_TIERS,
)


# ---------------------------------------------------------------- alignment
def align_by_date(
    stock_df: pd.DataFrame,
    index_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, int]:
    """
    将个股与指数按 date 内连接对齐；以个股的日期为主体计算 dropped 数。

    Returns: (stock_aligned, index_aligned, alignment_dropped_days)
      - 任一缺 date 列或为空 → (空, 空, 0)
    """
    if (stock_df is None or stock_df.empty
            or index_df is None or index_df.empty):
        return pd.DataFrame(), pd.DataFrame(), 0
    if "date" not in stock_df.columns or "date" not in index_df.columns:
        return pd.DataFrame(), pd.DataFrame(), 0

    s = stock_df.copy()
    i = index_df.copy()
    s["date"] = pd.to_datetime(s["date"], errors="coerce")
    i["date"] = pd.to_datetime(i["date"], errors="coerce")
    s = s.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    i = i.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    common = pd.Index(s["date"]).intersection(pd.Index(i["date"]))
    if len(common) == 0:
        return pd.DataFrame(), pd.DataFrame(), len(s)

    s_aligned = s[s["date"].isin(common)].sort_values("date").reset_index(drop=True)
    i_aligned = i[i["date"].isin(common)].sort_values("date").reset_index(drop=True)
    dropped = max(0, len(s) - len(s_aligned))
    return s_aligned, i_aligned, dropped


# ---------------------------------------------------------------- compute
def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """除法，分母 0/NaN → NaN（不出 inf）。"""
    den_safe = den.replace(0, np.nan)
    out = num / den_safe
    out = out.replace([np.inf, -np.inf], np.nan)
    return out


def compute_rel_volume_series(
    stock_volume: pd.Series,
    index_volume: pd.Series,
    window: int = REL_VOLUME_BASELINE_WINDOW,
) -> pd.Series:
    """
    相对量比序列 = (stock_vol / stock_vol_ma_N) / (idx_vol / idx_vol_ma_N)
    baseline 用 shift(1) 防 look-ahead。
    """
    if stock_volume is None or index_volume is None:
        return pd.Series(dtype=float)
    s = pd.to_numeric(stock_volume, errors="coerce")
    i = pd.to_numeric(index_volume, errors="coerce")
    s_ma = s.rolling(window=window, min_periods=max(5, window // 2)).mean().shift(1)
    i_ma = i.rolling(window=window, min_periods=max(5, window // 2)).mean().shift(1)
    s_ratio = _safe_ratio(s, s_ma)
    i_ratio = _safe_ratio(i, i_ma)
    return _safe_ratio(s_ratio, i_ratio)


def compute_rel_return_series(
    stock_close: pd.Series,
    index_close: pd.Series,
) -> pd.Series:
    """日收益差：stock_ret - index_ret（小数）。"""
    if stock_close is None or index_close is None:
        return pd.Series(dtype=float)
    s = pd.to_numeric(stock_close, errors="coerce").pct_change()
    i = pd.to_numeric(index_close, errors="coerce").pct_change()
    return s - i


def compute_index_anomalous_series(
    index_volume: pd.Series,
    window: int = REL_VOLUME_BASELINE_WINDOW,
    threshold: float = INDEX_ANOMALOUS_RATIO,
) -> pd.Series:
    """大盘自身放量异常 bool 序列：idx_vol / idx_vol_ma > threshold。"""
    if index_volume is None:
        return pd.Series(dtype=bool)
    i = pd.to_numeric(index_volume, errors="coerce")
    i_ma = i.rolling(window=window, min_periods=max(5, window // 2)).mean().shift(1)
    ratio = _safe_ratio(i, i_ma)
    return (ratio > threshold).fillna(False)


# ---------------------------------------------------------------- classify
def _classify(value: Optional[float], tiers, nan_default: str) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return nan_default
    for threshold, label in tiers:
        if value < threshold:
            return label
    return tiers[-1][1]


def classify_rel_volume(value: Optional[float]) -> str:
    return _classify(value, REL_VOLUME_TIERS, nan_default="NORMAL")


def classify_rel_return(value: Optional[float]) -> str:
    return _classify(value, REL_RETURN_TIERS, nan_default="INLINE")


# ---------------------------------------------------------------- aggregate
def rolling_avg(series: pd.Series, window: int) -> Optional[float]:
    if series is None or len(series) == 0:
        return None
    s = series.tail(window)
    if s.notna().sum() == 0:
        return None
    return float(s.mean(skipna=True))


def rolling_pct_below(series: pd.Series, window: int, threshold: float = 0.0) -> Optional[float]:
    if series is None or len(series) == 0:
        return None
    s = series.tail(window).dropna()
    if len(s) == 0:
        return None
    return float((s < threshold).sum() / len(s))


# ---------------------------------------------------------------- helpers
def _safe_round(value, ndigits: int = 4):
    """NaN/inf → None；否则四舍五入。"""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v):
        return None
    return round(v, ndigits)

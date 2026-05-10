"""
Distribution Pattern Profiler
==============================
单股的派发型形态多指标编排器：CLV / VWAP-deviation / Amihud-illiquidity 三组。

输入：DataFrame（按 date 升序）
输出：
{
  "data_quality": {
    "lookback_actual_days": int,
    "has_suspension_gap": bool,
    "ipo_age_days": int,
    "fields_available": ["clv", "vwap_deviation", "amihud_illiquidity"],
    "vwap_source": "native|amount_volume_synthetic|typical_price_fallback|unavailable",
    "dollar_volume_source": "native_amount|close_volume_synthetic",
    "sufficient_for_profile": bool,
    "market_type": "hk|cn|us|unknown",
  },
  "clv":                {"latest_day": {...}, "rolling": {...}},
  "vwap_deviation":     {"latest_day": {...}, "rolling": {...}},
  "amihud_illiquidity": {"latest_day": {...}, "rolling": {...}},
  "summary": {
    "pressure_signals": ["[CLV_WEAK_TREND_20D]", "[VWAP_BELOW_60PCT_20D]", ...],
    "neutral_signals":  ["[AMIHUD_NORMAL]", ...],
  }
}

设计要点
--------
- 与 VolumeAnomalyProfiler 同构：data_quality + 多个指标子树 + summary
- 三个指标各自独立纯函数（metrics.py），profiler 只做编排与字段安全
- VWAP / dollar_volume 缺失 → 该指标子树不出现（Null Object 沉默降级）
- 所有数值通过 _safe_round 处理 NaN，绝不污染 JSON allow_nan=False
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

import numpy as np
import pandas as pd

from alphaflow.core.acl.mappings.enums import MarketType

from . import metrics
from .config import (
    AMIHUD_BASELINE_WINDOW,
    AMIHUD_WINDOWS,
    CLV_WEAK_TREND_PCT_THRESHOLD,
    CLV_WINDOWS,
    MIN_DAYS_FOR_PATTERN,
    PATH_DOWN_UP_VOLUME_RATIO_THRESHOLD,
    PATH_DOWN_VOLUME_SHARE_THRESHOLD,
    PATH_DRAWDOWN_20D_CONFIRMED_THRESHOLD,
    PATH_DRAWDOWN_60D_CONFIRMED_THRESHOLD,
    PATH_FAILED_RECOVERY_DD_THRESHOLD,
    PATH_FAILED_RECOVERY_RATIO_MAX,
    PATH_NEG_DAY_RATIO_THRESHOLD,
    PATH_PRESSURE_WINDOWS,
    TAG_AMIHUD_LATEST,
    TAG_CLV_LATEST,
    TAG_CLV_WEAK_TREND_20D,
    TAG_CHRONIC_DISTRIBUTION_60D,
    TAG_FAILED_RECOVERY_60D,
    TAG_PATH_DRAWDOWN_20D,
    TAG_PATH_DRAWDOWN_60D,
    TAG_VWAP_BELOW_TREND_20D,
    TAG_VWAP_LATEST,
    VWAP_BELOW_TREND_PCT_THRESHOLD,
    VWAP_DEV_WINDOWS,
    VWAP_SOURCE_NONE,
)


class DistributionPatternProfiler:
    """单股派发型形态编排器（CLV / VWAP-dev / Amihud）。"""

    # 自描述：与项目其他 profiler 一致
    @property
    def target_slot(self) -> str:
        return "technical"

    def __init__(self, config: Optional[Mapping[str, Any]] = None) -> None:
        self.config = dict(config or {})
        self.clv_windows = tuple(self.config.get("clv_windows", CLV_WINDOWS))
        self.vwap_windows = tuple(self.config.get("vwap_dev_windows", VWAP_DEV_WINDOWS))
        self.amihud_windows = tuple(self.config.get("amihud_windows", AMIHUD_WINDOWS))
        self.path_windows = tuple(self.config.get("path_pressure_windows", PATH_PRESSURE_WINDOWS))
        self.amihud_baseline = int(self.config.get("amihud_baseline", AMIHUD_BASELINE_WINDOW))

    # =====================================================================
    # 公开入口
    # =====================================================================
    def analyze(
        self,
        df: pd.DataFrame,
        market_type: Optional[MarketType] = None,
    ) -> Dict[str, Any]:
        market_label = (market_type.value if isinstance(market_type, MarketType)
                        else MarketType.UNKNOWN.value)

        if df is None or len(df) == 0:
            return {"data_quality": self._empty_dq(market_label)}

        df_sorted = self._ensure_sorted(df)
        n = len(df_sorted)

        # ---- 数据质量基础
        dq = dict(metrics.assess_data_quality(df_sorted))
        dq["market_type"] = market_label
        dq["sufficient_for_profile"] = bool(n >= MIN_DAYS_FOR_PATTERN)

        # ---- VWAP / dollar_volume 来源解析（一次性跑，cache 在本作用域）
        vwap_series, vwap_source = metrics.resolve_vwap_series(df_sorted)
        dv_series, dv_source = metrics.resolve_dollar_volume_series(df_sorted)
        dq["vwap_source"] = vwap_source
        dq["dollar_volume_source"] = dv_source

        # 数据不足：仅返回 data_quality（仍含 source 标签便于上游诊断）
        if not dq["sufficient_for_profile"]:
            dq["fields_available"] = []
            return {"data_quality": dq}

        result: Dict[str, Any] = {}
        fields: List[str] = []
        pressure: List[str] = []
        neutral: List[str] = []

        # ---- CLV
        clv_series = metrics.compute_clv_series(df_sorted)
        if clv_series.notna().sum() >= 1:
            clv_block, clv_pressure, clv_neutral = self._build_clv(clv_series)
            result["clv"] = clv_block
            fields.append("clv")
            pressure.extend(clv_pressure)
            neutral.extend(clv_neutral)

        # ---- VWAP Deviation（仅当 VWAP 可得才出）
        if vwap_source != VWAP_SOURCE_NONE:
            vd_series = metrics.compute_vwap_deviation_series(df_sorted, vwap_series)
            if vd_series.notna().sum() >= 1:
                vd_block, vd_pressure, vd_neutral = self._build_vwap_dev(vd_series)
                result["vwap_deviation"] = vd_block
                fields.append("vwap_deviation")
                pressure.extend(vd_pressure)
                neutral.extend(vd_neutral)

        # ---- Amihud Illiquidity
        amihud_series = metrics.compute_amihud_series(df_sorted, dv_series)
        if amihud_series.notna().sum() >= 1:
            amihud_zscore = metrics.compute_amihud_zscore_series(
                amihud_series, self.amihud_baseline,
            )
            am_block, am_pressure, am_neutral = self._build_amihud(amihud_series, amihud_zscore)
            result["amihud_illiquidity"] = am_block
            fields.append("amihud_illiquidity")
            pressure.extend(am_pressure)
            neutral.extend(am_neutral)

        # ---- Path Pressure（只使用历史 OHLCV；无事件层、无未来数据）
        path_block, path_pressure, path_neutral = self._build_path_pressure(df_sorted)
        if path_block:
            result["path_pressure"] = path_block
            fields.append("path_pressure")
            pressure.extend(path_pressure)
            neutral.extend(path_neutral)

        dq["fields_available"] = fields
        result["data_quality"] = dq
        result["summary"] = {
            "pressure_signals": pressure,
            "neutral_signals":  neutral,
        }
        return result

    # =====================================================================
    # 内部
    # =====================================================================
    @staticmethod
    def _ensure_sorted(df: pd.DataFrame) -> pd.DataFrame:
        if "date" in df.columns:
            try:
                return df.sort_values("date", kind="mergesort").reset_index(drop=True)
            except Exception:
                pass
        return df.reset_index(drop=True)

    @staticmethod
    def _empty_dq(market_label: str) -> Dict[str, Any]:
        return {
            "lookback_actual_days": 0,
            "has_suspension_gap": False,
            "ipo_age_days": 0,
            "fields_available": [],
            "sufficient_for_profile": False,
            "market_type": market_label,
            "vwap_source": VWAP_SOURCE_NONE,
            "dollar_volume_source": "close_volume_synthetic",  # 默认值；空 df 时占位
        }

    # ---- CLV block
    def _build_clv(self, clv: pd.Series):
        latest = clv.dropna().iloc[-1] if clv.notna().any() else None
        latest_tier = metrics.classify_clv(latest)
        block: Dict[str, Any] = {
            "latest_day": {
                "value": metrics._safe_round(latest, 4),
                "tier":  latest_tier,
            },
            "rolling": {},
        }
        # rolling: 5d_avg / 20d_avg / 20d_pct_negative / 60d_avg
        for w in self.clv_windows:
            block["rolling"][f"{w}d_avg"] = metrics._safe_round(metrics.rolling_avg(clv, w), 4)
        block["rolling"]["20d_pct_negative"] = metrics._safe_round(
            metrics.rolling_pct_below(clv, 20, threshold=0.0), 4,
        )

        pressure: List[str] = []
        neutral: List[str] = []
        # 当日标签
        latest_tag = TAG_CLV_LATEST.get(latest_tier)
        if latest_tag:
            (pressure if latest_tier in ("PINNED_LOW", "WEAK_CLOSE") else neutral).append(latest_tag)
        # 趋势标签
        pct_neg = block["rolling"]["20d_pct_negative"]
        if pct_neg is not None and pct_neg >= CLV_WEAK_TREND_PCT_THRESHOLD:
            pressure.append(TAG_CLV_WEAK_TREND_20D)

        return block, pressure, neutral

    # ---- Path Pressure block
    def _build_path_pressure(self, df: pd.DataFrame):
        block = metrics.compute_path_pressure_block(df, self.path_windows)
        pressure: List[str] = []
        neutral: List[str] = []
        if not block:
            return {}, pressure, neutral

        b20 = block.get("20d") or {}
        b60 = block.get("60d") or {}

        dd20 = b20.get("drawdown_from_peak")
        dd60 = b60.get("drawdown_from_peak")
        max_dd60 = b60.get("max_drawdown")
        neg60 = b60.get("neg_day_ratio")
        down_share60 = b60.get("down_volume_share")
        down_up60 = b60.get("down_up_volume_ratio")
        recovery60 = b60.get("recovery_ratio")

        persistent_down = bool(neg60 is not None and neg60 >= PATH_NEG_DAY_RATIO_THRESHOLD)
        down_volume = bool(
            (down_share60 is not None and down_share60 >= PATH_DOWN_VOLUME_SHARE_THRESHOLD)
            or (down_up60 is not None and down_up60 >= PATH_DOWN_UP_VOLUME_RATIO_THRESHOLD)
        )

        failed_recovery = bool(
            max_dd60 is not None
            and max_dd60 <= PATH_FAILED_RECOVERY_DD_THRESHOLD
            and recovery60 is not None
            and recovery60 <= PATH_FAILED_RECOVERY_RATIO_MAX
        )

        # 原子条件只作为 evidence 留在 path_pressure block 中；summary.pressure 只发
        # 组合信号，避免把普通市场下跌/短期波动误计为派发风险。
        if dd20 is not None and dd20 <= PATH_DRAWDOWN_20D_CONFIRMED_THRESHOLD and down_volume:
            pressure.append(TAG_PATH_DRAWDOWN_20D)

        if dd60 is not None and dd60 <= PATH_DRAWDOWN_60D_CONFIRMED_THRESHOLD and down_volume:
            pressure.append(TAG_PATH_DRAWDOWN_60D)

        if (
            dd60 is not None
            and dd60 <= -0.08
            and persistent_down
            and down_volume
        ):
            pressure.append(TAG_CHRONIC_DISTRIBUTION_60D)

        if failed_recovery and (persistent_down or down_volume):
            pressure.append(TAG_FAILED_RECOVERY_60D)

        if not pressure:
            neutral.append("[PATH_PRESSURE_NEUTRAL]")

        return block, pressure, neutral

    # ---- VWAP Deviation block
    def _build_vwap_dev(self, vd: pd.Series):
        latest = vd.dropna().iloc[-1] if vd.notna().any() else None
        latest_tier = metrics.classify_vwap_dev(latest)
        block: Dict[str, Any] = {
            "latest_day": {
                "value":       metrics._safe_round(latest, 4),
                "below_vwap":  bool(latest is not None and np.isfinite(float(latest)) and float(latest) < 0),
                "tier":        latest_tier,
            },
            "rolling": {},
        }
        for w in self.vwap_windows:
            block["rolling"][f"{w}d_avg"] = metrics._safe_round(metrics.rolling_avg(vd, w), 4)
        block["rolling"]["20d_pct_below_vwap"] = metrics._safe_round(
            metrics.rolling_pct_below(vd, 20, threshold=0.0), 4,
        )

        pressure: List[str] = []
        neutral: List[str] = []
        latest_tag = TAG_VWAP_LATEST.get(latest_tier)
        if latest_tag:
            (pressure if latest_tier in ("STRONG_BELOW", "MILDLY_BELOW") else neutral).append(latest_tag)
        pct_below = block["rolling"]["20d_pct_below_vwap"]
        if pct_below is not None and pct_below >= VWAP_BELOW_TREND_PCT_THRESHOLD:
            pressure.append(TAG_VWAP_BELOW_TREND_20D)

        return block, pressure, neutral

    # ---- Amihud block
    def _build_amihud(self, amihud: pd.Series, zscore: pd.Series):
        latest_val = amihud.dropna().iloc[-1] if amihud.notna().any() else None
        latest_z = zscore.dropna().iloc[-1] if zscore.notna().any() else None
        tier = metrics.classify_amihud_zscore(latest_z)
        block: Dict[str, Any] = {
            "latest_day": {
                "value":      metrics._safe_round(latest_val, 12),
                "zscore_60d": metrics._safe_round(latest_z, 4),
                "tier":       tier,
            },
            "rolling": {},
        }
        for w in self.amihud_windows:
            block["rolling"][f"{w}d_avg"] = metrics._safe_round(
                metrics.rolling_avg(amihud, w), 12,
            )
        block["rolling"]["60d_baseline_mean"] = metrics._safe_round(
            metrics.rolling_avg(amihud, self.amihud_baseline), 12,
        )

        pressure: List[str] = []
        neutral: List[str] = []
        latest_tag = TAG_AMIHUD_LATEST.get(tier)
        if latest_tag:
            (pressure if tier in ("HIGH", "EXTREME") else neutral).append(latest_tag)

        return block, pressure, neutral

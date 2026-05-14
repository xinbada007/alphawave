"""
Volume Anomaly Profiler
========================
单维度编排器：给定 DataFrame 与维度配置，产出该维度的多周期异常剖面。

输入：DataFrame（按 date 升序）、配置中的 DIMENSIONS
输出：
{
  "volume": {                       # dimension key
    "lookbacks": {
      "5d":   {...count_anomalies_per_window 输出...},
      "20d":  {...},
      "60d":  {...},
      "252d": {...},
    },
    "latest_day": {
      "tier": "SPIKE",
      "ratio": 2.34,
      "pct_rank": 92.1,
      "zscore": 1.84,
    },
    "cav": {"5d": 1.23, "20d": 0.45},
    "regime_shift": {
      "adv_short": ..., "adv_long": ..., "ratio": ..., "shifted": True
    }
  }
}

设计要点：
- 维度可扩展：DIMENSIONS 元组追加即可，profiler 一次循环全部处理
- 计算过程纯函数，便于单测
- 所有数值通过 _safe_round 处理 NaN，绝不污染下游 JSON
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import numpy as np
import pandas as pd

from alphaflow.core.acl.mappings.enums import MarketType

from . import metrics
from .config import (
    BASELINE_WINDOW,
    CAV_WINDOWS,
    DIMENSIONS,
    LOOKBACK_WINDOWS,
    MIN_DAYS_FOR_PROFILE,
)
from .dimensions import DimensionResolver


def _safe_round(value: Any, ndigits: int = 4) -> Optional[float]:
    """将可能为 NaN/inf 的数值转为 JSON 安全的 float 或 None。"""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(f):
        return None
    return round(f, ndigits)


class VolumeAnomalyProfiler:
    """
    单股、多维度、多周期的量价异常剖面编排器。

    用法：
        profiler = VolumeAnomalyProfiler()
        result = profiler.analyze(df)  # df 须按时间升序，含 'close' 列
    """

    # 自描述：与项目中其他 processor 一致的契约
    @property
    def target_slot(self) -> str:
        return "technical"  # 写入 distilled_features.technical 下的子 key

    def __init__(self, config: Optional[Mapping[str, Any]] = None) -> None:
        self.config = dict(config or {})
        # 允许通过 config 覆盖默认窗口/维度（开闭原则）
        self.lookback_windows: tuple[int, ...] = tuple(
            self.config.get("lookback_windows", LOOKBACK_WINDOWS)
        )
        self.dimensions = tuple(self.config.get("dimensions", DIMENSIONS))
        self.baseline_window: int = int(self.config.get("baseline_window", BASELINE_WINDOW))
        self.cav_windows: tuple[int, ...] = tuple(self.config.get("cav_windows", CAV_WINDOWS))

    # -------------------------------------------------------------------
    # 公开入口
    # -------------------------------------------------------------------
    def analyze(
        self,
        df: pd.DataFrame,
        market_type: Optional[MarketType] = None,
    ) -> Dict[str, Any]:
        """
        给定 OHLCV-类 DataFrame，输出该股的 volume_anomaly_profile dict。

        Args:
            df: 时间序列（按 date 升序），需含 'close' 与至少一个量纲列
                （volume / amount / turnover_rate）
            market_type: 市场类型，决定 primary_dimension 与 fallback chain
                None / UNKNOWN → 退化为"按 DIMENSIONS 表序首个可得维度"（Phase 1 行为）

        返回结构：
        {
          "data_quality": {
              "lookback_actual_days": int,
              "has_suspension_gap": bool,
              "ipo_age_days": int,
              "fields_available": [...],            # 实际跑通的 dimension keys
              "sufficient_for_profile": bool,
              "market_type": "hk"/"cn"/"us"/"unknown",   # Phase 2 新增
              "primary_dimension": "amount",              # Phase 2 新增
              "available_dimensions": ["volume","amount","turnover_rate"], # Phase 2 新增
          },
          "<dim_key>": {                            # 每个 active 维度一份
              "lookbacks": {...},
              "latest_day": {...},
              "cav": {...},
              "regime_shift": {...}
          },
          ...
        }

        若数据不足 MIN_DAYS_FOR_PROFILE，则返回仅含 data_quality 的降级结果。
        """
        if df is None or len(df) == 0:
            return {"data_quality": self._empty_dq(market_type)}

        df_sorted = self._ensure_sorted(df)
        daily_returns = self._daily_returns(df_sorted)
        max_lookback = max(self.lookback_windows) if self.lookback_windows else 0

        # ---- DimensionResolver: 单一入口决定"用哪些 + 谁主信号"
        active_dims, primary_dim, market_label = DimensionResolver.resolve(
            available_columns=df_sorted.columns,
            market_type=market_type,
            all_dimensions=self.dimensions,
        )

        result: Dict[str, Any] = {}

        # data_quality 用最大 lookback 评估（最严格视图）
        dq = dict(metrics.assess_data_quality(df_sorted, max_lookback))
        dq["fields_available"] = [d["key"] for d in active_dims]
        dq["sufficient_for_profile"] = bool(
            dq["lookback_actual_days"] >= MIN_DAYS_FOR_PROFILE
        )
        # Phase 2 — 市场感知元数据
        dq["market_type"] = market_label
        dq["primary_dimension"] = primary_dim
        dq["available_dimensions"] = list(dq["fields_available"])  # 同义别名（语义更显式）
        result["data_quality"] = dq

        if not dq["sufficient_for_profile"]:
            return result  # 降级：天数不足，profile 不出

        for dim in active_dims:
            series = df_sorted[dim["column"]]
            result[dim["key"]] = self._analyze_dimension(series, daily_returns)

        return result

    @staticmethod
    def _empty_dq(market_type: Optional[MarketType]) -> Dict[str, Any]:
        """空 DataFrame 时统一的降级 data_quality。"""
        mlabel = (market_type.value if isinstance(market_type, MarketType)
                  else MarketType.UNKNOWN.value)
        return {
            "lookback_actual_days": 0,
            "has_suspension_gap": False,
            "ipo_age_days": 0,
            "fields_available": [],
            "sufficient_for_profile": False,
            "market_type": mlabel,
            "primary_dimension": "",
            "available_dimensions": [],
        }

    # -------------------------------------------------------------------
    # 内部
    # -------------------------------------------------------------------
    def _ensure_sorted(self, df: pd.DataFrame) -> pd.DataFrame:
        """统一按 date 升序；若无 date 列则信任原序。"""
        if "date" in df.columns:
            try:
                return df.sort_values("date", kind="mergesort").reset_index(drop=True)
            except Exception:
                pass
        return df.reset_index(drop=True)

    @staticmethod
    def _daily_returns(df: pd.DataFrame) -> pd.Series:
        if "close" in df.columns:
            return df["close"].pct_change().fillna(0.0)
        return pd.Series(0.0, index=df.index, name="daily_return")

    def _analyze_dimension(
        self,
        series: pd.Series,
        daily_returns: pd.Series,
    ) -> Dict[str, Any]:
        """对单个维度的 series 跑完整异常剖面。"""
        baselines = metrics.compute_rolling_baselines(series, self.baseline_window)
        tiers = metrics.classify_series(baselines)

        # lookbacks
        lookbacks: Dict[str, Any] = {}
        for w in self.lookback_windows:
            counts = metrics.count_anomalies_per_window(tiers, daily_returns, w)
            lookbacks[f"{w}d"] = self._sanitize_counts(counts)

        # latest_day
        last_idx = baselines.index[-1] if len(baselines) > 0 else None
        if last_idx is not None:
            latest_row = baselines.loc[last_idx]
            latest_day = {
                "tier": str(tiers.iloc[-1]),
                "ratio": _safe_round(latest_row["ratio"], 4),
                "pct_rank": _safe_round(latest_row["pct_rank"], 2),
                "zscore": _safe_round(latest_row["zscore"], 4),
            }
        else:
            latest_day = {"tier": "NORMAL", "ratio": None, "pct_rank": None, "zscore": None}

        # CAV
        cav: Dict[str, Optional[float]] = {}
        for w in self.cav_windows:
            cav[f"{w}d"] = _safe_round(metrics.cumulative_abnormal_volume(series, w), 4)

        # regime shift
        rs = metrics.detect_regime_shift(series)
        regime_shift = {
            "adv_short": _safe_round(rs["adv_short"], 2),
            "adv_long": _safe_round(rs["adv_long"], 2),
            "ratio": _safe_round(rs["ratio"], 4),
            "shifted": bool(rs["shifted"]),
        }

        return {
            "lookbacks": lookbacks,
            "latest_day": latest_day,
            "cav": cav,
            "regime_shift": regime_shift,
        }

    @staticmethod
    def _sanitize_counts(counts: Mapping[str, Any]) -> Dict[str, Any]:
        """count_anomalies_per_window 的输出已是纯 Python 类型，这里仅做防御性深拷贝。"""
        out = dict(counts)
        out["by_tier"] = dict(counts.get("by_tier", {}))
        return out

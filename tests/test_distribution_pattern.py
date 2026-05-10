#!/usr/bin/env python3
"""
test_distribution_pattern.py
=============================
Phase 4 单元测试：DistributionPattern 子系统（CLV / VWAP-dev / Amihud + 来源解析）。

测试矩阵（共 14 用例）：

  [config 完整性]
    C01 CLV/VWAP/AMIHUD tier 表非空且 threshold 单调
    C02 source 标签集合完整且互斥

  [metrics.resolve_vwap_series]
    V01 native vwap 列覆盖率 ≥ 80% → "native"
    V02 vwap 列稀疏 + amount/volume 完整 → "amount_volume_synthetic"
    V03 vwap 缺失 + amount 缺失 → "typical_price_fallback"，等于 (H+L+C)/3
    V04 全列缺失 → "unavailable"

  [metrics.resolve_dollar_volume_series]
    D01 amount 列存在 → "native_amount"
    D02 仅 close+volume → "close_volume_synthetic"

  [classifier 边界]
    K01 CLV: 0.85 → STRONG_CLOSE; -0.55 → PINNED_LOW; nan → NEUTRAL
    K02 VWAP_DEV: -0.025 → STRONG_BELOW; 0.0 → AT_VWAP
    K03 AMIHUD zscore: 3.5 → EXTREME; -1.0 → NORMAL

  [profiler.DistributionPatternProfiler]
    P01 数据不足（< 30 天）→ 仅 data_quality, sufficient=False
    P02 端到端 HK：dq.vwap_source="amount_volume_synthetic", dollar_volume_source="native_amount"
    P03 端到端 US：dq.vwap_source="typical_price_fallback", dollar_volume_source="close_volume_synthetic"
    P04 派发型构造（弱收 + 跌破均价）→ summary 含 [CLV_PINNED_LOW] / [CLV_WEAK_TREND_20D]
    P05 latest_day JSON 安全（NaN→None，无 inf）

运行：python3 tests/test_distribution_pattern.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd

from alphaflow.components.processors.techniques.analyzers.distribution_pattern import (
    DistributionPatternProfiler,
)
from alphaflow.components.processors.techniques.analyzers.distribution_pattern import metrics
from alphaflow.components.processors.techniques.analyzers.distribution_pattern.config import (
    AMIHUD_ZSCORE_TIERS,
    CLV_TIERS,
    DV_SOURCE_NATIVE,
    DV_SOURCE_SYNTHETIC,
    MIN_DAYS_FOR_PATTERN,
    TAG_CHRONIC_DISTRIBUTION_60D,
    TAG_DOWN_DAY_VOLUME_60D,
    TAG_FAILED_RECOVERY_60D,
    TAG_PATH_DRAWDOWN_60D,
    TAG_PATH_PERSISTENT_DOWN_60D,
    VWAP_DEV_TIERS,
    VWAP_SOURCE_AMT_VOL,
    VWAP_SOURCE_NATIVE,
    VWAP_SOURCE_NONE,
    VWAP_SOURCE_TYPICAL,
)
from alphaflow.core.acl.mappings.enums import MarketType


# --------------------------------------------------------------------- runner
_results: list[tuple[str, bool, str]] = []


def _case(name: str):
    def deco(fn):
        def w():
            try:
                fn()
                _results.append((name, True, ""))
                print(f"  ✅ {name}")
            except AssertionError as e:
                _results.append((name, False, str(e)))
                print(f"  ❌ {name}: {e}")
            except Exception as e:
                _results.append((name, False, f"{type(e).__name__}: {e}"))
                print(f"  💥 {name}: {type(e).__name__}: {e}")
                traceback.print_exc()
        return w
    return deco


def _make_ohlc(n=250, *, weak_close=False, with_amount=True, with_vwap=False, seed=7):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-02", periods=n, freq="B").strftime("%Y-%m-%d")
    high = 100 + rng.standard_normal(n) * 0.5
    low = high - np.abs(rng.standard_normal(n) * 0.6) - 0.5
    if weak_close:
        # CLV 显著为负：close 落在 [low, low + 0.3*range]
        close_pos = rng.uniform(0.05, 0.30, n)
    else:
        close_pos = rng.uniform(0.4, 0.6, n)
    close = low + close_pos * (high - low)
    volume = rng.lognormal(15, 0.3, n).astype(np.int64)
    df = pd.DataFrame({
        "date": dates, "open": close, "high": high, "low": low,
        "close": close, "volume": volume,
    })
    if with_amount:
        df["amount"] = (volume * close).round(2)
    if with_vwap:
        df["vwap"] = (high + low + close) / 3
    return df


def _make_chronic_distribution(n=250):
    """构造客观市场行为：60D 慢性下跌 + 下跌日放量 + 反弹失败。"""
    dates = pd.date_range("2024-01-02", periods=n, freq="B").strftime("%Y-%m-%d")
    close = np.full(n, 100.0)
    # 前 190 天平稳，后 60 天缓慢下跌至 -18%
    close[-60:] = np.linspace(100.0, 82.0, 60)
    # 让每隔 5 天小反弹，避免单调路径过于人工
    for i in range(n - 55, n, 5):
        close[i] += 1.2
    high = close * 1.01
    low = close * 0.99
    open_ = close * 1.003
    volume = np.full(n, 1_000_000.0)
    ret = pd.Series(close).pct_change()
    volume[ret < 0] = 1_400_000.0
    volume[ret > 0] = 800_000.0
    df = pd.DataFrame({
        "date": dates,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
    df["amount"] = df["close"] * df["volume"]
    return df


# ============================================================ Section: config
print("\n[Section] Config integrity")


@_case("C01 CLV/VWAP/AMIHUD tier 表非空且阈值单调")
def c01():
    for table, name in [(CLV_TIERS, "CLV"),
                        (VWAP_DEV_TIERS, "VWAP_DEV"),
                        (AMIHUD_ZSCORE_TIERS, "AMIHUD")]:
        assert len(table) >= 2, f"{name} tier table 太短"
        thresholds = [t for t, _ in table[:-1]]
        assert thresholds == sorted(thresholds), f"{name} 阈值非单调: {thresholds}"


@_case("C02 source 标签集合完整且互斥")
def c02():
    vwap_sources = {VWAP_SOURCE_NATIVE, VWAP_SOURCE_AMT_VOL,
                    VWAP_SOURCE_TYPICAL, VWAP_SOURCE_NONE}
    assert len(vwap_sources) == 4, "VWAP 来源标签重复"
    dv_sources = {DV_SOURCE_NATIVE, DV_SOURCE_SYNTHETIC}
    assert len(dv_sources) == 2, "DV 来源标签重复"


# ============================================== Section: VWAP source resolver
print("\n[Section] metrics.resolve_vwap_series")


@_case("V01 native vwap 覆盖率 ≥ 80% → 'native'")
def v01():
    df = _make_ohlc(n=50, with_vwap=True, with_amount=True)
    series, src = metrics.resolve_vwap_series(df)
    assert src == VWAP_SOURCE_NATIVE, f"got {src}"
    assert series.notna().all()


@_case("V02 vwap 稀疏 + amount/volume 完整 → 'amount_volume_synthetic'")
def v02():
    df = _make_ohlc(n=50, with_vwap=False, with_amount=True)
    series, src = metrics.resolve_vwap_series(df)
    assert src == VWAP_SOURCE_AMT_VOL, f"got {src}"
    # 抽样校验
    assert abs(series.iloc[0] - df["amount"].iloc[0] / df["volume"].iloc[0]) < 1e-6


@_case("V03 vwap+amount 都缺 → typical_price_fallback")
def v03():
    df = _make_ohlc(n=50, with_vwap=False, with_amount=False)
    series, src = metrics.resolve_vwap_series(df)
    assert src == VWAP_SOURCE_TYPICAL, f"got {src}"
    expected = (df["high"].iloc[0] + df["low"].iloc[0] + df["close"].iloc[0]) / 3
    assert abs(series.iloc[0] - expected) < 1e-6


@_case("V04 关键列全缺失 → unavailable")
def v04():
    df = pd.DataFrame({"date": ["2024-01-02"], "volume": [100]})
    series, src = metrics.resolve_vwap_series(df)
    assert src == VWAP_SOURCE_NONE, f"got {src}"
    assert series.isna().all()


# ============================================== Section: dollar_volume resolver
print("\n[Section] metrics.resolve_dollar_volume_series")


@_case("D01 amount 列存在 → native_amount")
def d01():
    df = _make_ohlc(n=10, with_amount=True)
    series, src = metrics.resolve_dollar_volume_series(df)
    assert src == DV_SOURCE_NATIVE


@_case("D02 仅 close+volume → close_volume_synthetic")
def d02():
    df = _make_ohlc(n=10, with_amount=False)
    series, src = metrics.resolve_dollar_volume_series(df)
    assert src == DV_SOURCE_SYNTHETIC
    assert abs(series.iloc[0] - df["close"].iloc[0] * df["volume"].iloc[0]) < 1e-6


# ============================================== Section: classifier 边界
print("\n[Section] classifier boundaries")


@_case("K01 CLV: 0.3→STRONG_CLOSE; -0.55→PINNED_LOW; NaN→NEUTRAL")
def k01():
    assert metrics.classify_clv(0.3) == "STRONG_CLOSE", metrics.classify_clv(0.3)
    assert metrics.classify_clv(-0.55) == "PINNED_LOW"
    assert metrics.classify_clv(float("nan")) == "NEUTRAL"


@_case("K02 VWAP_DEV: -0.025→STRONG_BELOW; 0.0→AT_VWAP")
def k02():
    assert metrics.classify_vwap_dev(-0.025) == "STRONG_BELOW"
    assert metrics.classify_vwap_dev(0.0) == "AT_VWAP"


@_case("K03 AMIHUD zscore: 3.5→EXTREME; -0.5→NORMAL")
def k03():
    assert metrics.classify_amihud_zscore(3.5) == "EXTREME"
    assert metrics.classify_amihud_zscore(-0.5) == "NORMAL"


# ============================================ Section: Profiler 端到端
print("\n[Section] DistributionPatternProfiler end-to-end")


@_case("P01 数据不足 (< MIN_DAYS_FOR_PATTERN) → sufficient=False")
def p01():
    df = _make_ohlc(n=10, with_amount=True)
    out = DistributionPatternProfiler().analyze(df, market_type=MarketType.HK)
    assert "data_quality" in out
    assert out["data_quality"]["sufficient_for_profile"] is False
    assert "clv" not in out, "数据不足时不应输出指标子树"


@_case("P02 HK 端到端 → vwap_source=amount_volume_synthetic, dv=native_amount")
def p02():
    df = _make_ohlc(n=250, with_amount=True, with_vwap=False)
    out = DistributionPatternProfiler().analyze(df, market_type=MarketType.HK)
    dq = out["data_quality"]
    assert dq["vwap_source"] == VWAP_SOURCE_AMT_VOL, dq
    assert dq["dollar_volume_source"] == DV_SOURCE_NATIVE, dq
    assert dq["market_type"] == "hk"
    assert "clv" in out and "vwap_deviation" in out and "amihud_illiquidity" in out
    assert set(dq["fields_available"]) == {
        "clv", "vwap_deviation", "amihud_illiquidity", "path_pressure",
    }


@_case("P03 US 端到端 → vwap_source=typical_price_fallback, dv=close_volume_synthetic")
def p03():
    df = _make_ohlc(n=250, with_amount=False, with_vwap=False)
    out = DistributionPatternProfiler().analyze(df, market_type=MarketType.US)
    dq = out["data_quality"]
    assert dq["vwap_source"] == VWAP_SOURCE_TYPICAL, dq
    assert dq["dollar_volume_source"] == DV_SOURCE_SYNTHETIC, dq
    assert dq["market_type"] == "us"
    assert "vwap_deviation" in out, "US 也应有 vwap_deviation（用 typical_price 兜底）"


@_case("P04 派发型构造 → summary 含 [CLV_PINNED_LOW] + [CLV_WEAK_TREND_20D]")
def p04():
    df = _make_ohlc(n=250, weak_close=True, with_amount=True)
    out = DistributionPatternProfiler().analyze(df, market_type=MarketType.HK)
    pressure = out["summary"]["pressure_signals"]
    assert "[CLV_PINNED_LOW]" in pressure or "[CLV_WEAK_CLOSE]" in pressure, pressure
    assert "[CLV_WEAK_TREND_20D]" in pressure, pressure


@_case("P05 latest_day JSON 安全（NaN→None，无 inf）")
def p05():
    df = _make_ohlc(n=250, with_amount=True)
    out = DistributionPatternProfiler().analyze(df, market_type=MarketType.HK)
    # 严格 JSON 序列化
    s = json.dumps(out, allow_nan=False)
    assert "Infinity" not in s and "NaN" not in s


@_case("P06 path_pressure 慢性派发 → 路径/下跌日放量/反弹失败标签")
def p06():
    df = _make_chronic_distribution()
    out = DistributionPatternProfiler().analyze(df, market_type=MarketType.US)
    assert "path_pressure" in out, out.keys()
    pressure = out["summary"]["pressure_signals"]
    assert TAG_PATH_DRAWDOWN_60D in pressure, pressure
    assert TAG_PATH_PERSISTENT_DOWN_60D in pressure, pressure
    assert TAG_DOWN_DAY_VOLUME_60D in pressure, pressure
    assert TAG_FAILED_RECOVERY_60D in pressure, pressure
    assert TAG_CHRONIC_DISTRIBUTION_60D in pressure, pressure
    path60 = out["path_pressure"]["60d"]
    assert path60["drawdown_from_peak"] <= -0.12, path60
    assert path60["down_volume_share"] >= 0.55, path60


# ============================================================ Entry
if __name__ == "__main__":
    test_funcs = [v for k, v in list(globals().items())
                  if (k.startswith(("c", "v", "d", "k", "p"))
                      and len(k) >= 3 and k[1:3].isdigit() and callable(v))]
    test_funcs.sort(key=lambda f: f.__name__)
    print(f"\n[Runner] 共 {len(test_funcs)} 个测试用例\n")
    for fn in test_funcs:
        fn()
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = len(_results) - passed
    print(f"\n{'='*60}")
    print(f"  Total: {len(_results)}  Passed: {passed}  Failed: {failed}")
    print(f"{'='*60}")
    if failed:
        print("\nFailures:")
        for name, ok, err in _results:
            if not ok:
                print(f"  - {name}: {err}")
        sys.exit(1)
    sys.exit(0)

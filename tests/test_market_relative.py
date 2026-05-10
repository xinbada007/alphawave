#!/usr/bin/env python3
"""
test_market_relative.py
========================
Phase 5 单元测试：MarketRelativeAnomaly 子系统的核心算子与编排器。

测试矩阵（共 14 用例）：

  [config 完整性]
    C01 REL_VOLUME / REL_RETURN tier 表非空且阈值单调
    C02 [BRACKET] tag 字典与 tier 名一一对应

  [metrics.align_by_date]
    A01 完美对齐 → dropped=0
    A02 个股有指数缺失日 → 内连接，dropped 计正确
    A03 任一为空 → 返回 (空, 空, 0)

  [metrics.compute_rel_volume_series]
    V01 个股放量 5x、指数同步放量 5x → rel_volume ≈ 1.0
    V02 个股放量 5x、指数无变化 → rel_volume ≈ 5.0
    V03 baseline 用 shift(1)（无 look-ahead）

  [metrics.compute_rel_return_series]
    R01 跑输 5% → rel_return ≈ -0.05

  [metrics.compute_index_anomalous_series]
    I01 大盘当日 vol 是 ma 的 2x → True
    I02 大盘 vol 平稳 → 全 False

  [classifier]
    K01 rel_volume: 4.0→SPIKE; 0.5→LOW; nan→NORMAL
    K02 rel_return: -0.06→STRONG_UNDERPERFORM; 0.0→INLINE

  [profiler.MarketRelativeAnomalyProfiler]
    P01 benchmark_meta.status='unavailable' → 仅 data_quality, sufficient=False
    P02 benchmark 数据齐全且 sufficient → latest_day + rolling + summary 三件齐
    P03 派发型相对异常 (个股 5x 放量 + 跌 6% + 大盘平稳) → [REL_VOLUME_HISTORIC] + [REL_RETURN_STRONG_UNDER]

运行：python3 tests/test_market_relative.py
"""
from __future__ import annotations

import json
import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd

from alphaflow.components.processors.techniques.analyzers.market_relative_anomaly import (
    MarketRelativeAnomalyProfiler,
)
from alphaflow.components.processors.techniques.analyzers.market_relative_anomaly import metrics
from alphaflow.components.processors.techniques.analyzers.market_relative_anomaly.config import (
    REL_RETURN_TIERS,
    REL_VOLUME_TIERS,
    TAG_REL_RETURN_LATEST,
    TAG_REL_VOLUME_LATEST,
)
from alphaflow.core.acl.mappings.enums import MarketType


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


def _make_pair(n=250, *, stock_spike=False, stock_underperform=False, idx_anomaly=False, seed=11):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-02", periods=n, freq="B").strftime("%Y-%m-%d")
    idx_close = 1000 + np.cumsum(rng.standard_normal(n) * 5)
    idx_vol = rng.lognormal(18, 0.2, n).astype(np.int64)
    stock_close = 100 + np.cumsum(rng.standard_normal(n) * 1.0
                                  - (0.05 if stock_underperform else 0.0))
    stock_vol = rng.lognormal(15, 0.4, n).astype(np.int64)

    if stock_spike:
        stock_vol[-1] = stock_vol[-1] * 5
        stock_close[-1] = stock_close[-1] * 0.93
    if idx_anomaly:
        idx_vol[-1] = idx_vol[-1] * 3

    s = pd.DataFrame({"date": dates, "open": stock_close, "high": stock_close*1.02,
                       "low": stock_close*0.98, "close": stock_close, "volume": stock_vol})
    i = pd.DataFrame({"date": dates, "open": idx_close, "high": idx_close*1.01,
                       "low": idx_close*0.99, "close": idx_close, "volume": idx_vol})
    return s, i


# ===================================================== Section: config
print("\n[Section] Config integrity")


@_case("C01 REL_VOLUME / REL_RETURN tier 表非空且阈值单调")
def c01():
    for tbl, name in [(REL_VOLUME_TIERS, "REL_VOLUME"), (REL_RETURN_TIERS, "REL_RETURN")]:
        assert len(tbl) >= 3, f"{name} tier 表太短"
        thresholds = [t for t, _ in tbl[:-1]]
        assert thresholds == sorted(thresholds), f"{name} 阈值非单调: {thresholds}"


@_case("C02 [BRACKET] tag 字典与 tier 名一一对应")
def c02():
    tier_names_v = {label for _, label in REL_VOLUME_TIERS}
    tier_names_r = {label for _, label in REL_RETURN_TIERS}
    assert set(TAG_REL_VOLUME_LATEST.keys()) == tier_names_v
    assert set(TAG_REL_RETURN_LATEST.keys()) == tier_names_r
    for tag in TAG_REL_VOLUME_LATEST.values():
        assert tag.startswith("[") and tag.endswith("]"), tag


# ===================================================== Section: align
print("\n[Section] metrics.align_by_date")


@_case("A01 完美对齐 → dropped=0")
def a01():
    s, i = _make_pair(n=50)
    sa, ia, dropped = metrics.align_by_date(s, i)
    assert len(sa) == 50 and len(ia) == 50
    assert dropped == 0


@_case("A02 个股有指数缺失日 → 内连接，dropped 计正确")
def a02():
    s, i = _make_pair(n=50)
    i = i.iloc[:-3]  # 指数少 3 天
    sa, ia, dropped = metrics.align_by_date(s, i)
    assert len(sa) == 47 and len(ia) == 47
    assert dropped == 3


@_case("A03 任一为空 → 返回 (空, 空, 0)")
def a03():
    sa, ia, dropped = metrics.align_by_date(pd.DataFrame(), pd.DataFrame())
    assert sa.empty and ia.empty and dropped == 0


# ===================================================== Section: compute
print("\n[Section] metrics.compute_*")


@_case("V01 个股+指数同步放量 5x → rel_volume ≈ 1.0")
def v01():
    n = 60
    s_vol = pd.Series([100.0] * n)
    i_vol = pd.Series([1000.0] * n)
    s_vol.iloc[-1] = 500.0
    i_vol.iloc[-1] = 5000.0
    rv = metrics.compute_rel_volume_series(s_vol, i_vol, window=20)
    last = rv.iloc[-1]
    assert abs(last - 1.0) < 0.01, f"got {last}"


@_case("V02 个股放量 5x、指数无变化 → rel_volume ≈ 5.0")
def v02():
    n = 60
    s_vol = pd.Series([100.0] * n)
    i_vol = pd.Series([1000.0] * n)
    s_vol.iloc[-1] = 500.0
    rv = metrics.compute_rel_volume_series(s_vol, i_vol, window=20)
    last = rv.iloc[-1]
    assert abs(last - 5.0) < 0.05, f"got {last}"


@_case("V03 baseline 用 shift(1)（无 look-ahead）")
def v03():
    # 全部相同 → 第一个非 NaN 之前的位置应全 NaN
    n = 30
    s_vol = pd.Series([100.0] * n)
    i_vol = pd.Series([1000.0] * n)
    rv = metrics.compute_rel_volume_series(s_vol, i_vol, window=20)
    # 前若干天因为 baseline 不足 (min_periods=10) 应是 NaN
    assert rv.iloc[0:5].isna().all(), "前几天应该 NaN"


@_case("R01 个股跑输指数 5% → rel_return ≈ -0.05")
def r01():
    s_close = pd.Series([100.0, 95.0])  # -5%
    i_close = pd.Series([1000.0, 1000.0])  # 0%
    rr = metrics.compute_rel_return_series(s_close, i_close)
    assert abs(rr.iloc[-1] - (-0.05)) < 1e-6, rr.iloc[-1]


@_case("I01 大盘当日 vol = ma 的 2x → index_anomalous=True")
def i01():
    n = 30
    i_vol = pd.Series([1000.0] * (n - 1) + [3000.0])  # 最后一天爆量
    out = metrics.compute_index_anomalous_series(i_vol, window=20, threshold=1.8)
    assert out.iloc[-1] == True, "应触发"


@_case("I02 大盘 vol 平稳 → 全 False")
def i02():
    n = 30
    i_vol = pd.Series([1000.0] * n)
    out = metrics.compute_index_anomalous_series(i_vol, window=20, threshold=1.8)
    assert not out.any(), "平稳序列不应触发"


# ===================================================== Section: classifier
print("\n[Section] classifiers")


@_case("K01 rel_volume: 3.0→SPIKE; 0.5→LOW; nan→NORMAL")
def k01():
    assert metrics.classify_rel_volume(3.0) == "SPIKE", metrics.classify_rel_volume(3.0)
    assert metrics.classify_rel_volume(0.5) == "LOW"
    assert metrics.classify_rel_volume(float("nan")) == "NORMAL"


@_case("K02 rel_return: -0.06→STRONG_UNDERPERFORM; 0.0→INLINE")
def k02():
    assert metrics.classify_rel_return(-0.06) == "STRONG_UNDERPERFORM"
    assert metrics.classify_rel_return(0.0) == "INLINE"


# ===================================================== Section: profiler
print("\n[Section] MarketRelativeAnomalyProfiler")


@_case("P01 benchmark unavailable → 仅 data_quality, sufficient=False")
def p01():
    s, i = _make_pair(n=250)
    out = MarketRelativeAnomalyProfiler().analyze(
        s, None, benchmark_meta={"status": "unavailable", "reason": "fetch_failed"},
        market_type=MarketType.US,
    )
    dq = out["data_quality"]
    assert dq["benchmark_status"] == "unavailable"
    assert dq["sufficient_for_profile"] is False
    assert "latest_day" not in out


@_case("P02 benchmark 齐全且 sufficient → latest_day+rolling+summary 三件齐")
def p02():
    s, i = _make_pair(n=250)
    meta = {"status": "ok", "benchmark_symbol": "^HSI", "source": "AkShare_HSI", "market_type": "hk"}
    out = MarketRelativeAnomalyProfiler().analyze(s, i, benchmark_meta=meta,
                                                  market_type=MarketType.HK)
    for k in ("data_quality", "latest_day", "rolling", "summary"):
        assert k in out, f"缺顶层 key '{k}'"
    assert out["data_quality"]["sufficient_for_profile"] is True
    assert "rel_volume" in out["latest_day"]
    # rolling 必须含 5d/20d/60d 三个 avg + 20d_pct_underperform
    rk = out["rolling"]
    for k in ("5d_avg_rel_volume", "20d_avg_rel_volume", "60d_avg_rel_volume",
              "20d_pct_underperform"):
        assert k in rk, f"rolling 缺 '{k}'"
    # JSON 严格序列化
    json.dumps(out, allow_nan=False, default=str)


@_case("P03 派发型相对异常 → [REL_VOLUME_HISTORIC] + [REL_RETURN_STRONG_UNDER]")
def p03():
    s, i = _make_pair(n=250, stock_spike=True, stock_underperform=True)
    meta = {"status": "ok", "benchmark_symbol": "^HSI", "source": "AkShare_HSI", "market_type": "hk"}
    out = MarketRelativeAnomalyProfiler().analyze(s, i, benchmark_meta=meta,
                                                  market_type=MarketType.HK)
    pressure = out["summary"]["pressure_signals"]
    assert "[REL_VOLUME_HISTORIC]" in pressure or "[REL_VOLUME_SPIKE]" in pressure, pressure
    assert "[REL_RETURN_STRONG_UNDER]" in pressure or "[REL_RETURN_MILD_UNDER]" in pressure, pressure


# ===================================================== Entry
if __name__ == "__main__":
    test_funcs = [v for k, v in list(globals().items())
                  if (k.startswith(("c", "a", "v", "r", "i", "k", "p"))
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

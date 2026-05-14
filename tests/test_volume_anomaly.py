#!/usr/bin/env python3
"""
test_volume_anomaly.py
========================
Phase 1 单元测试：VolumeAnomaly 子系统的核心算子与编排器。

测试矩阵（共 18 用例）：

  [config 完整性]
    C01 TIER_ORDER 单调；ELEVATED 无 ratio 守卫；其他 tier 有
    C02 LOOKBACK_WINDOWS 单调上升

  [metrics.compute_rolling_baselines]
    M01 输出列齐全 (mean/std/ratio/zscore/pct_rank)
    M02 baseline 不含当日（验证 shift(1)，无 look-ahead）
    M03 全 0 序列：ratio = NaN, std = 0 → zscore = NaN
    M04 极端尖峰：尖峰日 pct_rank 应接近 100, ratio 巨大

  [metrics.classify_anomaly_tier]
    T01 NORMAL：pct_rank=70 → NORMAL
    T02 ELEVATED：pct_rank=85, ratio=1.0 → ELEVATED（无 ratio 守卫）
    T03 SPIKE 共振失败：pct_rank=92, ratio=1.5 → ELEVATED（pct 够但 ratio 不够）
    T04 SPIKE 共振：pct_rank=92, ratio=2.5 → SPIKE
    T05 HISTORIC 共振：pct_rank=99.5, ratio=15 → HISTORIC
    T06 NaN 输入 → NORMAL

  [metrics.count_anomalies_per_window]
    W01 全 NORMAL → all zeros，longest_streak=0
    W02 含异常下跌日 → anomaly_days_down 正确
    W03 连续 3 天异常 → longest_streak=3

  [metrics.cumulative_abnormal_volume]
    V01 数据不足 → NaN
    V02 平稳序列 → CAV ≈ 0

  [metrics.detect_regime_shift]
    R01 平稳序列 → ratio≈1.0, shifted=False
    R02 近期放量 2x → shifted=True

  [profiler.VolumeAnomalyProfiler]
    P01 端到端：构造 250 天序列含 1 个 SPIKE 日，输出结构合法
    P02 数据不足（< MIN_DAYS_FOR_PROFILE）→ 仅返回 data_quality, sufficient=False
    P03 缺 volume 列 → fields_available=[], 不抛异常
    P04 latest_day 字段类型为 JSON 安全（NaN→None）

运行：python3 tests/test_volume_anomaly.py
"""
from __future__ import annotations

import math
import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd

from alphaflow.components.processors.techniques.analyzers.volume_anomaly import VolumeAnomalyProfiler
from alphaflow.components.processors.techniques.analyzers.volume_anomaly import metrics
from alphaflow.components.processors.techniques.analyzers.volume_anomaly.config import (
    ANOMALY_PERCENTILE_TIERS,
    LOOKBACK_WINDOWS,
    MIN_DAYS_FOR_PROFILE,
    RATIO_GUARDS,
    TIER_ORDER,
)


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


def _make_df(volumes, dates_start="2024-01-02"):
    n = len(volumes)
    dates = pd.date_range(dates_start, periods=n, freq="B").strftime("%Y-%m-%d")
    closes = np.linspace(100, 110, n)
    return pd.DataFrame({
        "date": dates,
        "open":   closes,
        "high":   closes * 1.01,
        "low":    closes * 0.99,
        "close":  closes,
        "volume": volumes,
    })


# ============================================================ Section: config
print("\n[Section] Config integrity")

@_case("C01 TIER_ORDER 与 RATIO_GUARDS 一致性")
def c01():
    assert TIER_ORDER[0] == "NORMAL"
    # ELEVATED 不应在 RATIO_GUARDS 中（仅靠百分位）
    assert "ELEVATED" not in RATIO_GUARDS
    # SPIKE 及以上必须在 RATIO_GUARDS 中
    for t in ("SPIKE", "EXTREME", "BLOWOUT", "HISTORIC"):
        assert t in RATIO_GUARDS, f"{t} 缺 ratio guard"
        assert t in ANOMALY_PERCENTILE_TIERS
    # ratio 单调上升
    rs = [RATIO_GUARDS[t] for t in ("SPIKE", "EXTREME", "BLOWOUT", "HISTORIC")]
    assert rs == sorted(rs), f"ratio guards 应单调上升: {rs}"


@_case("C02 LOOKBACK_WINDOWS 严格递增")
def c02():
    L = list(LOOKBACK_WINDOWS)
    assert L == sorted(L) and len(set(L)) == len(L), f"重复或乱序: {L}"


# =============================================== Section: rolling baselines
print("\n[Section] metrics.compute_rolling_baselines")

@_case("M01 输出列齐全")
def m01():
    s = pd.Series(np.random.RandomState(0).rand(100) + 1)
    out = metrics.compute_rolling_baselines(s, baseline_window=20)
    for col in ("baseline_mean", "baseline_std", "ratio", "zscore", "pct_rank"):
        assert col in out.columns, f"missing {col}"


@_case("M02 baseline 不含当日（无 look-ahead）")
def m02():
    s = pd.Series([1.0] * 30 + [1000.0])  # 第 31 天突变
    out = metrics.compute_rolling_baselines(s, baseline_window=20)
    # 末日的 baseline_mean 必须是过去 20 日均值（=1.0），不含当日的 1000
    last = out.iloc[-1]
    assert math.isclose(last["baseline_mean"], 1.0, abs_tol=1e-9), \
        f"baseline 含当日: {last['baseline_mean']}"
    # ratio 应反映 1000 / 1 = 1000
    assert last["ratio"] > 500, f"ratio 反映异常: {last['ratio']}"


@_case("M03 全 0 序列：ratio/zscore 应为 NaN（不报错不出 inf）")
def m03():
    s = pd.Series([0.0] * 100)
    out = metrics.compute_rolling_baselines(s, baseline_window=20)
    last = out.iloc[-1]
    # 0/0 → NaN（因为我们 replace(0, NaN)）
    assert pd.isna(last["ratio"])
    # 标准差是 0 → zscore = (0-0)/0 → NaN
    assert pd.isna(last["zscore"])
    assert not np.isinf(out["ratio"]).any()


@_case("M04 极端尖峰日 pct_rank≈100 + ratio 巨大")
def m04():
    s = pd.Series([100.0] * 60 + [1e9])
    out = metrics.compute_rolling_baselines(s, baseline_window=30)
    last = out.iloc[-1]
    assert last["pct_rank"] > 95, f"pct_rank 应接近 100, got {last['pct_rank']}"
    assert last["ratio"] > 1e6, f"ratio={last['ratio']}"


# ================================================= Section: classify
print("\n[Section] metrics.classify_anomaly_tier")

@_case("T01 NORMAL: pct=70")
def t01():
    assert metrics.classify_anomaly_tier(70.0, 1.5) == "NORMAL"


@_case("T02 ELEVATED: pct=85, ratio 不重要")
def t02():
    assert metrics.classify_anomaly_tier(85.0, 1.0) == "ELEVATED"
    assert metrics.classify_anomaly_tier(85.0, 0.1) == "ELEVATED"


@_case("T03 SPIKE 共振失败 → 退到 ELEVATED")
def t03():
    # pct=92 ≥ 90 (SPIKE 门槛) 但 ratio=1.5 < 2.0 → 不升 SPIKE，退到 ELEVATED
    assert metrics.classify_anomaly_tier(92.0, 1.5) == "ELEVATED"


@_case("T04 SPIKE 共振")
def t04():
    assert metrics.classify_anomaly_tier(92.0, 2.5) == "SPIKE"


@_case("T05 HISTORIC 共振")
def t05():
    assert metrics.classify_anomaly_tier(99.5, 15.0) == "HISTORIC"


@_case("T06 NaN → NORMAL")
def t06():
    assert metrics.classify_anomaly_tier(float("nan"), 5.0) == "NORMAL"
    assert metrics.classify_anomaly_tier(95.0, float("nan")) == "NORMAL"


# ========================================== Section: count_anomalies_per_window
print("\n[Section] metrics.count_anomalies_per_window")

@_case("W01 全 NORMAL")
def w01():
    tiers = pd.Series(["NORMAL"] * 20)
    rets = pd.Series([0.01] * 20)
    out = metrics.count_anomalies_per_window(tiers, rets, 20)
    assert out["anomaly_days_total"] == 0
    assert out["longest_streak"] == 0
    assert out["latest_tier"] == "NORMAL"


@_case("W02 含异常下跌日")
def w02():
    tiers = pd.Series(["NORMAL"] * 18 + ["SPIKE", "BLOWOUT"])
    rets  = pd.Series([0.0] * 18 + [-0.05, -0.02])  # 都下跌
    out = metrics.count_anomalies_per_window(tiers, rets, 20)
    assert out["anomaly_days_total"] == 2
    assert out["anomaly_days_down"] == 2
    assert out["anomaly_days_up"] == 0
    assert out["latest_tier"] == "BLOWOUT"
    assert out["by_tier"]["SPIKE"] == 1
    assert out["by_tier"]["BLOWOUT"] == 1


@_case("W03 longest_streak=3")
def w03():
    tiers = pd.Series(["NORMAL", "SPIKE", "EXTREME", "SPIKE", "NORMAL", "SPIKE"])
    rets  = pd.Series([0.0] * 6)
    out = metrics.count_anomalies_per_window(tiers, rets, 6)
    assert out["longest_streak"] == 3, f"expect 3, got {out['longest_streak']}"


# =============================================== Section: CAV
print("\n[Section] metrics.cumulative_abnormal_volume")

@_case("V01 数据不足 → NaN")
def v01():
    s = pd.Series([100.0] * 5)
    cav = metrics.cumulative_abnormal_volume(s, window=20)
    assert math.isnan(cav)


@_case("V02 平稳序列 → CAV ≈ 0")
def v02():
    s = pd.Series([100.0] * 200)
    cav = metrics.cumulative_abnormal_volume(s, window=20, baseline_window=60)
    assert abs(cav) < 1e-9, f"expect ~0, got {cav}"


# =============================================== Section: regime shift
print("\n[Section] metrics.detect_regime_shift")

@_case("R01 平稳 → shifted=False")
def r01():
    s = pd.Series([100.0] * 200)
    rs = metrics.detect_regime_shift(s)
    assert rs["shifted"] is False
    assert math.isclose(rs["ratio"], 1.0, abs_tol=1e-9)


@_case("R02 近期放量 2x → shifted=True")
def r02():
    s = pd.Series([100.0] * 100 + [200.0] * 20)
    rs = metrics.detect_regime_shift(s, short_window=20, long_window=120)
    assert rs["shifted"] is True
    assert rs["ratio"] > 1.5


# =============================================== Section: Profiler
print("\n[Section] VolumeAnomalyProfiler end-to-end")

@_case("P01 端到端：250 天 + 1 个尖峰，结构合法")
def p01():
    rng = np.random.RandomState(42)
    vols = rng.normal(1_000_000, 100_000, 250).astype(int)
    vols[200] = 20_000_000   # 极端尖峰
    df = _make_df(vols.tolist())

    profiler = VolumeAnomalyProfiler()
    out = profiler.analyze(df)

    assert "data_quality" in out
    assert out["data_quality"]["sufficient_for_profile"] is True
    assert "volume" in out
    v = out["volume"]
    # 4 个 lookback 都应该存在
    assert set(v["lookbacks"].keys()) == {f"{w}d" for w in LOOKBACK_WINDOWS}
    # latest_day schema
    for f in ("tier", "ratio", "pct_rank", "zscore"):
        assert f in v["latest_day"]
    # CAV
    assert "cav" in v and "20d" in v["cav"]
    # regime_shift schema
    rs = v["regime_shift"]
    for f in ("adv_short", "adv_long", "ratio", "shifted"):
        assert f in rs

    # 历史尖峰应至少在 60d 窗口里被计入（it's at index 200, last 60 means 190-249）
    assert v["lookbacks"]["60d"]["anomaly_days_total"] >= 1, \
        f"60d 应含尖峰: {v['lookbacks']['60d']}"


@_case("P02 数据不足 → 仅 data_quality")
def p02():
    df = _make_df([1_000_000] * 10)
    profiler = VolumeAnomalyProfiler()
    out = profiler.analyze(df)
    assert "volume" not in out, "数据不足时不应输出 profile"
    assert out["data_quality"]["sufficient_for_profile"] is False
    assert out["data_quality"]["lookback_actual_days"] <= 10


@_case("P03 缺 volume 列 → 优雅降级")
def p03():
    df = _make_df([1_000_000] * 100).drop(columns=["volume"])
    profiler = VolumeAnomalyProfiler()
    out = profiler.analyze(df)
    # data_quality 仍出，但 volume key 不出
    assert "volume" not in out
    assert out["data_quality"]["fields_available"] == []


@_case("P04 latest_day JSON 安全（NaN→None，无 inf）")
def p04():
    # 全 0 序列：ratio/zscore 必为 NaN
    df = _make_df([0] * 100)
    profiler = VolumeAnomalyProfiler()
    out = profiler.analyze(df)
    # 由于 close=linspace 仍非空，sufficient_for_profile 取决于 close 非空数
    # 验证：若 volume 维度有值，latest_day 不应有 NaN（应为 None）
    if "volume" in out:
        ld = out["volume"]["latest_day"]
        for k, v in ld.items():
            if v is not None and isinstance(v, float):
                assert math.isfinite(v), f"{k}={v} 应为 None 或有限数"
    # 关键：JSON 序列化必须不抛
    import json
    json.dumps(out)  # NaN 会让 dumps(allow_nan=False) 失败；默认允许，但我们要求 None
    json.dumps(out, allow_nan=False)  # 严格模式必须通过


# ============================================================ Phase 2 — 多维度 + 市场感知
print("\n[Section] VolumeAnomalyProfiler · Phase 2 multi-dimension")

from alphaflow.core.acl.mappings.enums import MarketType


def _make_multi_df(n: int = 250, with_amount: bool = True, with_turnover: bool = True):
    rng = np.random.RandomState(42)
    dates = pd.date_range("2024-01-02", periods=n, freq="B").strftime("%Y-%m-%d")
    close = (100 + np.cumsum(rng.randn(n) * 0.5)).round(2)
    vol = rng.normal(1_000_000, 100_000, n).astype(int)
    cols = {"date": dates, "close": close, "volume": vol}
    if with_amount:
        cols["amount"] = (vol * close).round(2)
    if with_turnover:
        cols["turnover_rate"] = (vol / 1e8).round(4)
    return pd.DataFrame(cols)


@_case("P05 HK + 全维度 → 三个 dim 子树齐全, primary='amount'")
def p05():
    df = _make_multi_df()
    out = VolumeAnomalyProfiler().analyze(df, market_type=MarketType.HK)
    dq = out["data_quality"]
    assert dq["market_type"] == "hk"
    assert dq["primary_dimension"] == "amount"
    assert set(dq["available_dimensions"]) == {"volume", "amount", "turnover_rate"}
    for dim in ("volume", "amount", "turnover_rate"):
        assert dim in out, f"missing {dim}"
        assert "latest_day" in out[dim] and "tier" in out[dim]["latest_day"]


@_case("P06 CN → primary='turnover_rate'，金额/换手共存")
def p06():
    df = _make_multi_df()
    out = VolumeAnomalyProfiler().analyze(df, market_type=MarketType.CN)
    assert out["data_quality"]["primary_dimension"] == "turnover_rate"
    assert out["data_quality"]["market_type"] == "cn"


@_case("P07 US 仅 volume → turnover_rate/amount 字段不出现 (Null Object 沉默降级)")
def p07():
    df = _make_multi_df(with_amount=False, with_turnover=False)
    out = VolumeAnomalyProfiler().analyze(df, market_type=MarketType.US)
    dq = out["data_quality"]
    assert dq["primary_dimension"] == "volume"
    assert dq["available_dimensions"] == ["volume"]
    assert "amount" not in out
    assert "turnover_rate" not in out
    # JSON 严格模式仍须通过
    import json as _json
    _json.dumps(out, allow_nan=False)


@_case("P08 HK 缺 amount → fallback 到 'volume'")
def p08():
    df = _make_multi_df(with_amount=False, with_turnover=False)
    out = VolumeAnomalyProfiler().analyze(df, market_type=MarketType.HK)
    assert out["data_quality"]["market_type"] == "hk"
    assert out["data_quality"]["primary_dimension"] == "volume", \
        "HK 缺 amount 应降级到 volume"


@_case("P09 market_type=None → 向后兼容 Phase 1 行为")
def p09():
    df = _make_multi_df(with_amount=False, with_turnover=False)
    # 既不传 market_type，也不传 keyword，应同 Phase 1
    out = VolumeAnomalyProfiler().analyze(df)
    assert out["data_quality"]["market_type"] == "unknown"
    assert out["data_quality"]["primary_dimension"] == "volume"
    assert "volume" in out


@_case("P10 全维度数据 + market_type=None → primary='volume' (表序首个)")
def p10():
    df = _make_multi_df()  # 三维齐全
    out = VolumeAnomalyProfiler().analyze(df)
    # 不传 market_type → DIMENSIONS 表序首个 volume
    assert out["data_quality"]["primary_dimension"] == "volume"
    # 但所有维度仍输出（避免数据浪费）
    assert all(k in out for k in ("volume", "amount", "turnover_rate"))


@_case("P11 空 df → data_quality 含 Phase 2 元数据，无崩溃")
def p11():
    out = VolumeAnomalyProfiler().analyze(pd.DataFrame(), market_type=MarketType.HK)
    dq = out["data_quality"]
    assert dq["sufficient_for_profile"] is False
    assert dq["market_type"] == "hk"
    assert dq["primary_dimension"] == ""
    assert dq["available_dimensions"] == []


# ============================================================ Entry
if __name__ == "__main__":
    test_funcs = [v for k, v in list(globals().items())
                  if (k.startswith(("c", "m", "t", "w", "v", "r", "p"))
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

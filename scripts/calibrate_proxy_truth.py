#!/usr/bin/env python3
"""
calibrate_proxy_truth.py
========================
Phase A2-A3：用现有 60 样本（V1+V2+V3，30 派发 + 30 正常）
验证 ProxyTruth (H1-H5) 的阈值是否合理。

合格标准：
  - 派发组 ProxyTruth.is_distribution=True ≥ 25/30  (≥83%)
  - 正常组 ProxyTruth.is_distribution=False ≥ 25/30 (≥83%)
  - 派发组 STRONG 占比 ≥ 50%
  - 正常组若有 True，必须落在 MILD 而非 STRONG

不合格 → 反馈调阈值（当前阈值视为 V1 baseline）。

需要 benchmark：US→SPY, HK→^HSI, CN→000300.SS
fixture 已有 SPY/HSI/000300 在 tests/fixtures/golden_samples/_benchmark/ 则用，
否则提示 build_benchmark_fixtures.py 抓取。
"""
from __future__ import annotations

import os, sys
from typing import Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from tests.test_golden_samples import load_fixture
from scripts.audit_signal_correlation import SAMPLES, AuditSample
from scripts.proxy_truth import evaluate as proxy_evaluate, ProxyLabel


BENCHMARK_DIR = os.path.join(
    os.path.dirname(__file__), "..", "tests", "fixtures", "golden_samples", "_benchmark"
)


def market_of(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith(".HK"):
        return "HK"
    if s.endswith(".SH") or s.endswith(".SS") or s.endswith(".SZ"):
        return "CN"
    return "US"


BENCHMARK_TICKER = {
    "US": "SPY",
    "HK": "_HSI",       # ^HSI 文件名转义
    "CN": "000300_SS",
}


def load_benchmark(market: str) -> Optional[pd.DataFrame]:
    fname = f"{BENCHMARK_TICKER[market]}.csv"
    path = os.path.join(BENCHMARK_DIR, fname)
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def main():
    # 检查 benchmark 是否就绪
    benches = {m: load_benchmark(m) for m in ("US", "HK", "CN")}
    missing = [m for m, b in benches.items() if b is None]
    if missing:
        print(f"❌ Missing benchmark fixtures for: {missing}")
        print(f"   Expected at: {BENCHMARK_DIR}/")
        print(f"   Files: SPY.csv, _HSI.csv, 000300_SS.csv")
        print(f"   Run: python scripts/build_benchmark_fixtures.py")
        return 2

    print("=" * 165)
    print("ProxyTruth Calibration v2 (R4 = Politis-Romano Stationary Bootstrap)")
    print("  H1: abs_dd ≤ -8% (mild) / -15% (strict)  OR  bootstrap p ≤ 5% / 1%")
    print("  H2: excess_dd vs benchmark ≤ -5% mild / -10% strong")
    print("  H3-H4: vol_ratio≥1.2; neg_days≥40%   H5: V反弹辅助打分（不否决）")
    print("=" * 165)
    hdr = (f"{'alias':<22}{'klass':<14}{'mkt':<3}{'abs_dd':>8}{'pVal':>7}"
           f"{'excDD':>8}{'volR':>6}{'neg%':>6}{'tT':>4}{'recR':>6}  "
           f"{'pattern':<8}{'truth':<7}{'inten':<7}  H1 H1b H2 H3 H4 H5  conf  match")
    print(hdr)
    print("-" * 165)

    dist_total = norm_total = 0
    dist_true = norm_false = 0
    dist_strong = 0
    norm_true_strong = 0  # 正常组被误判为 STRONG（最严重错误）
    expected_dist, expected_norm = [], []
    actual_dist_truth, actual_norm_truth = [], []

    for s in SAMPLES:
        try:
            df = load_fixture(s.alias)
        except Exception as e:
            print(f"  ⚠️  {s.alias}: cannot load fixture — {e}")
            continue
        df["date"] = pd.to_datetime(df["date"])
        market = market_of(s.symbol)
        bench = benches[market]
        anchor = pd.Timestamp(s.anchor)
        # anchor 落点：取 fixture 中 ≤ anchor 的最近交易日作为 base_day
        mask = df["date"] <= anchor
        if not mask.any():
            continue
        base_day = df[mask].iloc[-1]["date"]

        label: ProxyLabel = proxy_evaluate(
            stock=df, benchmark=bench, base_day=base_day,
        )

        ev = label.evidence
        h = label.hypotheses
        match = "—"
        if s.klass == "distribution":
            dist_total += 1
            if label.is_distribution:
                dist_true += 1
                match = "✅"
            else:
                match = "❌ MISS"
            if label.intensity == "STRONG":
                dist_strong += 1
            expected_dist.append(s.alias)
            actual_dist_truth.append(label.is_distribution)
        else:
            norm_total += 1
            if not label.is_distribution:
                norm_false += 1
                match = "✅"
            else:
                match = f"❌ FP-{label.intensity}"
                if label.intensity == "STRONG":
                    norm_true_strong += 1
            expected_norm.append(s.alias)
            actual_norm_truth.append(label.is_distribution)

        h_str = (
            f"{'✓' if h.get('H1_strict') else '·':>2} "
            f"{'S' if h.get('H1_boot_strong') else ('m' if h.get('H1_bootstrap') else '·'):>2} "
            f"{'S' if h.get('H2_strong') else ('m' if h.get('H2_excess') else '·'):>2} "
            f"{'✓' if h.get('H3_volume') else '·':>2} "
            f"{'✓' if h.get('H4_persist') else '·':>2} "
            f"{'✓' if h.get('H5_no_vshape') else '·':>2}"
        )
        excd_s = f"{ev.get('excess_dd', 0):+.1%}" if ev.get('excess_dd') is not None else "  -  "
        vol_s = f"{ev.get('vol_ratio', 0):.2f}" if ev.get('vol_ratio') is not None else "  -"
        pv = ev.get('p_value')
        pv_s = f"{pv:.3f}" if pv is not None else "  -  "
        print(
            f"{s.alias:<22}{s.klass:<14}{market:<3}"
            f"{ev.get('abs_dd_60d', 0):>+7.1%}{pv_s:>7}"
            f"{excd_s:>8}{vol_s:>6}{ev.get('neg_day_ratio', 0):>+6.1%}"
            f"{ev.get('days_to_trough', 0):>4}{ev.get('recovery_ratio', 0):>+6.1%}  "
            f"{label.pattern:<8}"
            f"{('TRUE' if label.is_distribution else 'FALSE'):<7}"
            f"{label.intensity:<7}  {h_str}  {label.confidence:.2f}  {match}"
        )

    print("\n" + "=" * 165)
    print(f"全集派发组 ({dist_total}): is_distribution=TRUE {dist_true} ({dist_true/max(1,dist_total):.0%})  "
          f"STRONG={dist_strong}")
    print(f"全集正常组 ({norm_total}): is_distribution=FALSE {norm_false} ({norm_false/max(1,norm_total):.0%})  "
          f"误升 STRONG={norm_true_strong}")

    # —— Effective subset：剔除 anchor 后实质未发生下跌的派发样本（dd > -5% 视为 anchor 失效）——
    eff_dist_total = eff_dist_true = eff_dist_strong = 0
    invalid_dist = []
    for s, dist_truth in zip(expected_dist, actual_dist_truth):
        # 重跑一次取 abs_dd（避免在循环中重新评估，简化处理）
        pass
    # 用 evidence 字段从二次扫描
    eff_records = []
    for s in SAMPLES:
        if s.klass != "distribution":
            continue
        try:
            df = load_fixture(s.alias)
        except Exception:
            continue
        df["date"] = pd.to_datetime(df["date"])
        market = market_of(s.symbol)
        anchor = pd.Timestamp(s.anchor)
        mask = df["date"] <= anchor
        if not mask.any():
            continue
        base_day = df[mask].iloc[-1]["date"]
        label = proxy_evaluate(stock=df, benchmark=benches[market], base_day=base_day)
        abs_dd = label.evidence.get("abs_dd_60d", 0)
        if abs_dd > -0.05:  # anchor 后没下跌 → 视为 anchor 失效，不计入有效集
            invalid_dist.append((s.alias, abs_dd))
            continue
        eff_dist_total += 1
        if label.is_distribution:
            eff_dist_true += 1
            if label.intensity == "STRONG":
                eff_dist_strong += 1

    print(f"\n有效派发组 (剔除 abs_dd > -5% 的 {len(invalid_dist)} 个 anchor 失效样本): "
          f"{eff_dist_total} 个")
    print(f"  有效 recall: {eff_dist_true}/{eff_dist_total} = {eff_dist_true/max(1,eff_dist_total):.0%}")
    print(f"  有效 STRONG: {eff_dist_strong}/{eff_dist_total} = {eff_dist_strong/max(1,eff_dist_total):.0%}")
    print(f"  剔除清单: {[a for a,_ in invalid_dist]}")


    # 合格判定
    pass_dist = dist_true / max(1, dist_total) >= 0.83
    pass_norm = norm_false / max(1, norm_total) >= 0.83
    pass_strong_ratio = dist_strong / max(1, dist_total) >= 0.50
    pass_no_norm_strong = norm_true_strong == 0

    print("\n校准合格判定:")
    print(f"  派发 recall ≥ 83%:   {'✅' if pass_dist else '❌'}  ({dist_true}/{dist_total} = {dist_true/max(1,dist_total):.0%})")
    print(f"  正常 specificity≥83%: {'✅' if pass_norm else '❌'}  ({norm_false}/{norm_total} = {norm_false/max(1,norm_total):.0%})")
    print(f"  派发 STRONG≥50%:     {'✅' if pass_strong_ratio else '❌'}  ({dist_strong}/{dist_total})")
    print(f"  正常无 STRONG 误判:  {'✅' if pass_no_norm_strong else '❌'}  ({norm_true_strong})")
    print("=" * 145)

    return 0 if (pass_dist and pass_norm and pass_no_norm_strong) else 1


if __name__ == "__main__":
    sys.exit(main())

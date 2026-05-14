"""
Phase 7 — flow_signals 单测
============================
四组用例：
  M 组 — metrics 纯函数（block_trade / lhb / southbound）
  P 组 — profiler 编排 + Null Object 降级
  C 组 — composite_risk 集成（score_flow_signals 现已生效）
  E 组 — 边界

无 pytest，沿用 if __name__ == "__main__" runner 约定。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from alphaflow.components.processors.techniques.analyzers.flow_signals import (
    config as cfg,
    metrics,
)
from alphaflow.components.processors.techniques.analyzers.flow_signals.profiler import (
    FlowSignalsProfiler,
)
from alphaflow.components.processors.techniques.analyzers.composite_risk import (
    scorers as composite_scorers,
)


_CASES = []


def _case(name):
    def deco(fn):
        _CASES.append((name, fn))
        return fn
    return deco


# ============================================================
# 辅助：mock DataFrame
# ============================================================
def mk_block_df(*, n_total=5, n_discount=3, avg_disc=-4.5):
    """构造大宗交易 DF：n_total 笔，其中 n_discount 笔显著折价。"""
    base_date = pd.Timestamp("2024-08-01")
    rows = []
    for i in range(n_total):
        is_disc = i < n_discount
        rows.append({
            "date":        base_date + pd.Timedelta(days=i),
            "symbol":      "600519",
            "discount_pct": avg_disc if is_disc else -0.5,
            "deal_value":  1e7,
        })
    return pd.DataFrame(rows)


def mk_lhb_df(*, appearances=2, net_buy_pct=-1.5):
    base_date = pd.Timestamp("2024-08-01")
    rows = []
    for i in range(appearances):
        rows.append({
            "date":                  base_date + pd.Timedelta(days=i * 2),
            "symbol":                "600519",
            "net_buy_to_market_pct": net_buy_pct,
            "net_buy":               -5e6,
        })
    return pd.DataFrame(rows)


# ============================================================
# M 组 — metrics 纯函数
# ============================================================
@_case("M01 block_trade 3 折价 → tier=HIGH + DISCOUNT_FREQUENT")
def m01():
    s = metrics.compute_block_trade_summary(mk_block_df(n_total=5, n_discount=3))
    assert s["rolling"]["discount_count"] == 3
    assert s["rolling"]["tier"] == "HIGH"
    assert cfg.TAG_BLOCK_DISCOUNT_FREQUENT in s["pressure_signals"]


@_case("M02 block_trade 0 折价 → tier=NORMAL, no signal")
def m02():
    s = metrics.compute_block_trade_summary(mk_block_df(n_total=2, n_discount=0))
    assert s["rolling"]["discount_count"] == 0
    assert s["rolling"]["tier"] == "NORMAL"
    assert s["pressure_signals"] == []


@_case("M03 block_trade 深度折价 → DEEP signal")
def m03():
    # avg_disc=-8 < -3*2=-6 → DEEP
    s = metrics.compute_block_trade_summary(mk_block_df(n_total=4, n_discount=3, avg_disc=-8))
    assert cfg.TAG_BLOCK_DISCOUNT_DEEP in s["pressure_signals"]


@_case("M04 block_trade 空 DF → 空 summary")
def m04():
    s = metrics.compute_block_trade_summary(pd.DataFrame())
    assert s["rolling"] == {}
    assert s["pressure_signals"] == []


@_case("M05 lhb 2 次上榜 + 净卖出 → FREQUENT + NET_SELL")
def m05():
    s = metrics.compute_lhb_summary(mk_lhb_df(appearances=2, net_buy_pct=-1.5))
    assert s["rolling"]["appearances"] == 2
    assert s["rolling"]["tier"] == "ELEVATED"
    assert cfg.TAG_LHB_FREQUENT_APPEARANCE in s["pressure_signals"]
    assert cfg.TAG_LHB_NET_SELL in s["pressure_signals"]


@_case("M06 lhb 1 次上榜 + 净买入 → 仅 NORMAL，无 pressure")
def m06():
    s = metrics.compute_lhb_summary(mk_lhb_df(appearances=1, net_buy_pct=2.0))
    assert s["rolling"]["tier"] == "NORMAL"
    assert s["pressure_signals"] == []


@_case("M07 southbound 占位 → 不为空但无 signals")
def m07():
    df = pd.DataFrame({"date": [pd.Timestamp("2024-08-01")], "value": [1.0]})
    s = metrics.compute_southbound_summary(df)
    assert s["pressure_signals"] == []


# ============================================================
# P 组 — profiler
# ============================================================
@_case("P01 全部 unavailable → Null Object")
def p01():
    p = FlowSignalsProfiler().analyze(flow_data=None, flow_meta={"sources": {}}, market_type="hk")
    dq = p["data_quality"]
    assert dq["sufficient_for_profile"] is False
    assert "block_trade" not in p
    assert "lhb" not in p


@_case("P02 仅 block_trade 在场 → sufficient + 子键存在")
def p02():
    df = mk_block_df(n_total=4, n_discount=2)
    p = FlowSignalsProfiler().analyze(
        flow_data={"block_trade": df},
        flow_meta={"sources": {"block_trade": {"status": "ok"}, "lhb": {"status": "unavailable"}}},
        market_type="cn",
    )
    dq = p["data_quality"]
    assert dq["sufficient_for_profile"] is True
    assert "block_trade" in p
    assert "lhb" not in p
    assert dq["sources_available"] == ["block_trade"]
    assert "lhb" in dq["sources_missing"]


@_case("P03 双子源全在场 → summary 聚合两源 pressure_signals")
def p03():
    p = FlowSignalsProfiler().analyze(
        flow_data={
            "block_trade": mk_block_df(n_total=5, n_discount=3, avg_disc=-8),  # FREQUENT + DEEP
            "lhb":         mk_lhb_df(appearances=2, net_buy_pct=-1.5),         # FREQUENT + NET_SELL
        },
        flow_meta={"sources": {"block_trade": {"status": "ok"}, "lhb": {"status": "ok"}}},
        market_type="cn",
    )
    sigs = p["summary"]["pressure_signals"]
    assert len(sigs) == 4, sigs
    assert cfg.TAG_BLOCK_DISCOUNT_FREQUENT in sigs
    assert cfg.TAG_BLOCK_DISCOUNT_DEEP in sigs
    assert cfg.TAG_LHB_FREQUENT_APPEARANCE in sigs
    assert cfg.TAG_LHB_NET_SELL in sigs


# ============================================================
# C 组 — composite_risk 集成（Phase 7 接入闭环）
# ============================================================
@_case("C01 score_flow_signals: 0 signals → 0")
def c01():
    profile = {
        "data_quality": {"sufficient_for_profile": True, "sources_available": ["block_trade"]},
        "summary": {"pressure_signals": [], "neutral_signals": []},
    }
    raw, evi = composite_scorers.score_flow_signals(profile)
    assert raw == 0.0
    assert "0 flow pressure" in evi


@_case("C02 score_flow_signals: 2 signals → 70")
def c02():
    profile = {
        "data_quality": {"sufficient_for_profile": True, "sources_available": ["block_trade", "lhb"]},
        "summary": {"pressure_signals": ["[A]", "[B]"], "neutral_signals": []},
    }
    raw, evi = composite_scorers.score_flow_signals(profile)
    assert raw == 70.0
    assert "2 source(s)" in evi


@_case("C03 score_flow_signals: 4+ signals 封顶 95")
def c03():
    profile = {
        "data_quality": {"sufficient_for_profile": True, "sources_available": ["block_trade"]},
        "summary": {"pressure_signals": ["[A]", "[B]", "[C]", "[D]"], "neutral_signals": []},
    }
    raw, _ = composite_scorers.score_flow_signals(profile)
    assert raw == 95.0


@_case("C04 score_flow_signals: Null Object → None")
def c04():
    raw, _ = composite_scorers.score_flow_signals({"data_quality": {"sufficient_for_profile": False}})
    assert raw is None


# ============================================================
# E 组 — 边界
# ============================================================
@_case("E01 metrics 输入 None → 空 summary")
def e01():
    for fn in (metrics.compute_block_trade_summary, metrics.compute_lhb_summary,
               metrics.compute_southbound_summary):
        s = fn(None)
        assert s["rolling"] == {}
        assert s["pressure_signals"] == []


@_case("E02 metrics 缺关键列 → 仍能运行（不抛错）")
def e02():
    df_no_disc = pd.DataFrame({"date": [pd.Timestamp("2024-08-01")], "deal_value": [1e7]})
    s = metrics.compute_block_trade_summary(df_no_disc)
    assert s["rolling"]["discount_count"] == 0


# ============================================================
# Runner
# ============================================================
def main():
    passed = failed = 0
    failures = []
    for name, fn in _CASES:
        try:
            fn()
            print(f"  ✅ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {name}: {e}")
            failures.append((name, str(e)))
            failed += 1
        except Exception as e:
            print(f"  ❌ {name}: {type(e).__name__}: {e}")
            failures.append((name, f"{type(e).__name__}: {e}"))
            failed += 1
    print()
    print("=" * 60)
    print(f"  Total: {passed + failed}  Passed: {passed}  Failed: {failed}")
    print("=" * 60)
    if failures:
        print("\nFailures:")
        for n, err in failures:
            print(f"  - {n}: {err}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

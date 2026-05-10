"""
Phase 6 — composite_risk 单测
================================
五组用例：
  S 组 — 子分纯映射（scorers.score_*）
  W 组 — 权重重分配（cap / quorum / unallocated）
  L 组 — level / confidence 边界
  E 组 — 边界（全 unavailable / 全 0 / essential 缺）
  C 组 — 完整 composer 端到端

无 pytest，用 if __name__ == "__main__" runner（小写两字母+两位数字命名约定）。
"""
import os
import sys
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alphaflow.components.processors.techniques.analyzers.composite_risk import (
    config as cfg,
    scorers,
)
from alphaflow.components.processors.techniques.analyzers.composite_risk.scorer import (
    CompositeRiskScorer,
)


_CASES = []


def _case(name):
    def deco(fn):
        _CASES.append((name, fn))
        return fn
    return deco


# ============================================================
# 辅助：构造各种 mock profile
# ============================================================
def mk_vol(tier="SPIKE", primary="volume", extreme=0, blowout=0, historic=0, sufficient=True):
    """volume_anomaly_profile mock — tier 必须是 TIER_ORDER 的真实值"""
    return {
        "data_quality": {
            "primary_dimension": primary,
            "sufficient_for_profile": sufficient,
        },
        primary: {
            "latest_day": {"tier": tier},
            "rolling": {"by_tier": {
                "EXTREME":  extreme,
                "BLOWOUT":  blowout,
                "HISTORIC": historic,
            }},
        },
    }


def mk_dist(n_pressure=2, sufficient=True):
    return {
        "data_quality": {"sufficient_for_profile": sufficient},
        "summary": {"pressure_signals": [f"[SIG_{i}]" for i in range(n_pressure)]},
    }


def mk_rel(rv="ELEVATED", rr="INLINE", index_anom=False, sufficient=True):
    return {
        "data_quality": {"sufficient_for_profile": sufficient},
        "latest_day": {
            "rel_volume_tier": rv,
            "rel_return_tier": rr,
            "index_anomalous": index_anom,
        },
    }


def mk_null():
    """Null Object — 仅 data_quality（如 benchmark unavailable 时）"""
    return {"data_quality": {"sufficient_for_profile": False}}


# ============================================================
# S 组 — 子分纯映射
# ============================================================
@_case("S01 volume SPIKE no rolling → 60")
def s01():
    raw, evi = scorers.score_volume_anomaly(mk_vol("SPIKE"))
    assert raw == 60.0, raw
    assert "tier=SPIKE" in evi


@_case("S02 volume EXTREME + rolling 3 → 80+10=90")
def s02():
    raw, evi = scorers.score_volume_anomaly(mk_vol("EXTREME", extreme=2, blowout=1))
    assert raw == 90.0, raw
    assert "rolling_extreme=3d" in evi


@_case("S03 volume NORMAL no rolling → 0")
def s03():
    raw, _ = scorers.score_volume_anomaly(mk_vol("NORMAL"))
    assert raw == 0.0


@_case("S04 volume primary=amount works")
def s04():
    raw, _ = scorers.score_volume_anomaly(mk_vol("EXTREME", primary="amount"))
    assert raw == 80.0


@_case("S05 volume Null Object → None")
def s05():
    raw, evi = scorers.score_volume_anomaly(mk_null())
    assert raw is None
    assert "unavailable" in evi


@_case("S06 distribution 0/1/2/3/4 → 0/35/65/90/95")
def s06():
    cases = [(0, 0), (1, 35), (2, 65), (3, 90), (4, 95), (5, 95)]
    for n, expected in cases:
        raw, _ = scorers.score_distribution_pattern(mk_dist(n_pressure=n))
        assert raw == expected, f"n={n} got {raw} expected {expected}"


@_case("S07 market_relative SPIKE+INLINE → 70")
def s07():
    raw, evi = scorers.score_market_relative(mk_rel(rv="SPIKE", rr="INLINE"))
    assert raw == 70.0
    assert "rel_volume=SPIKE" in evi


@_case("S08 market_relative HISTORIC + STRONG_UNDER → max 90")
def s08():
    raw, _ = scorers.score_market_relative(mk_rel(rv="HISTORIC", rr="STRONG_UNDERPERFORM"))
    assert raw == 90.0


@_case("S09 market_relative index_anomalous=True 阻尼 ×0.5")
def s09():
    raw, evi = scorers.score_market_relative(mk_rel(rv="HISTORIC", rr="INLINE", index_anom=True))
    assert raw == 45.0, raw
    assert "index_anomalous" in evi


@_case("S10 flow_signals → None (Phase 7 未实现)")
def s10():
    raw, evi = scorers.score_flow_signals(None)
    assert raw is None
    assert "unavailable" in evi


# ============================================================
# W 组 — 权重重分配
# ============================================================
@_case("W01 全在场 → 原权重不变")
def w01():
    eff, unalloc, capped = CompositeRiskScorer._redistribute(
        available=["volume_anomaly", "distribution_pattern", "market_relative", "flow_signals"],
        missing=[],
    )
    assert eff == {"volume_anomaly": 40, "distribution_pattern": 30,
                   "market_relative": 20, "flow_signals": 10}
    assert unalloc == 0
    assert not capped


@_case("W02 仅 flow 缺 → 10 分按 4:3:2 分给三件套，无 cap")
def w02():
    eff, unalloc, capped = CompositeRiskScorer._redistribute(
        available=["volume_anomaly", "distribution_pattern", "market_relative"],
        missing=["flow_signals"],
    )
    assert math.isclose(sum(eff.values()), 100.0, abs_tol=1e-6)
    assert unalloc == 0
    assert not capped
    # 比例：40 收 10*4/9=4.44 → 44.44；30 收 3.33 → 33.33；20 收 2.22 → 22.22
    assert math.isclose(eff["volume_anomaly"], 40 + 10*40/90, abs_tol=1e-6)


@_case("W03 仅 vol → 60 分要分给 vol，但 cap 60，剩 40 unallocated")
def w03():
    eff, unalloc, capped = CompositeRiskScorer._redistribute(
        available=["volume_anomaly"],
        missing=["distribution_pattern", "market_relative", "flow_signals"],
    )
    assert eff["volume_anomaly"] == 60.0  # 40 × 1.5
    assert math.isclose(unalloc, 40.0, abs_tol=1e-6)
    assert "volume_anomaly" in capped


@_case("W04 仅 vol+dist → 30 分能否在 cap 内吃掉")
def w04():
    eff, unalloc, capped = CompositeRiskScorer._redistribute(
        available=["volume_anomaly", "distribution_pattern"],
        missing=["market_relative", "flow_signals"],
    )
    # pool=30, vol/dist 比例 4:3
    # vol 收 30*4/7 ≈ 17.14 → 40+17.14=57.14, cap=60 OK
    # dist 收 30*3/7 ≈ 12.86 → 30+12.86=42.86, cap=45 OK
    assert math.isclose(sum(eff.values()), 100.0, abs_tol=1e-6)
    assert unalloc == 0
    assert not capped


@_case("W05 全缺 → unalloc=100, eff 全 0")
def w05():
    eff, unalloc, capped = CompositeRiskScorer._redistribute(available=[], missing=list(cfg.WEIGHTS))
    assert eff == {}
    assert unalloc == 100.0


# ============================================================
# L 组 — level / confidence 分类
# ============================================================
@_case("L01 level 边界")
def l01():
    s = CompositeRiskScorer
    assert s._classify_level(0)   == "LOW"
    assert s._classify_level(29.9) == "LOW"
    assert s._classify_level(30)   == "MODERATE"
    assert s._classify_level(54.9) == "MODERATE"
    assert s._classify_level(55)   == "ELEVATED"
    assert s._classify_level(74.9) == "ELEVATED"
    assert s._classify_level(75)   == "HIGH"
    assert s._classify_level(89.9) == "HIGH"
    assert s._classify_level(90)   == "CRITICAL"
    assert s._classify_level(100)  == "CRITICAL"


@_case("L02 confidence 边界")
def l02():
    s = CompositeRiskScorer
    assert s._classify_confidence(0.30) == "very_low"
    assert s._classify_confidence(0.45) == "low"
    assert s._classify_confidence(0.65) == "moderate"
    assert s._classify_confidence(0.85) == "high"
    assert s._classify_confidence(1.00) == "high"


# ============================================================
# E 组 — 边界
# ============================================================
@_case("E01 全 unavailable → score=None, sufficient=False, 标 essential 缺失")
def e01():
    out = CompositeRiskScorer().score()
    assert out["score"] is None
    assert out["level"] is None
    assert out["data_quality"]["sufficient_for_score"] is False
    assert out["data_quality"]["essential_present"] is False
    assert cfg.TAG_INSUFFICIENT_ESSENTIAL in out["data_quality"]["diagnostic_tags"]
    assert out["primary_drivers"] == []


@_case("E02 essential 缺（无 vol 但有其他）→ score=None")
def e02():
    out = CompositeRiskScorer().score(
        distribution_pattern=mk_dist(2),
        market_relative=mk_rel(rv="SPIKE"),
    )
    assert out["score"] is None
    assert out["level"] is None
    assert out["data_quality"]["essential_present"] is False


@_case("E03 仅 vol 在场 → quorum=1<2 → advisory_only, level=None")
def e03():
    out = CompositeRiskScorer().score(volume_anomaly=mk_vol("EXTREME"))
    assert out["score"] is not None
    assert out["level"] is None  # advisory 不出 level
    assert out["data_quality"]["advisory_only"] is True
    assert out["data_quality"]["sufficient_for_score"] is False
    assert out["data_quality"]["core_quorum"] == "1/3"
    assert cfg.TAG_INSUFFICIENT_QUORUM in out["data_quality"]["diagnostic_tags"]
    # vol 被 cap 到 60，有 40 unalloc → confidence 0.6 → low
    assert out["data_quality"]["confidence"] == 0.6
    assert out["data_quality"]["confidence_level"] == "low"


@_case("E04 全 0 raw 但都在场 → score=0, level=LOW, drivers=[]")
def e04():
    out = CompositeRiskScorer().score(
        volume_anomaly=mk_vol("NORMAL"),
        distribution_pattern=mk_dist(0),
        market_relative=mk_rel(rv="NORMAL", rr="INLINE"),
    )
    assert out["score"] == 0.0
    assert out["level"] == "LOW"
    assert out["data_quality"]["sufficient_for_score"] is True
    assert out["primary_drivers"] == []  # 所有 weighted=0


# ============================================================
# C 组 — 完整 composer 端到端
# ============================================================
@_case("C01 三件套 + flow 缺 → 满 confidence + level 合理")
def c01():
    out = CompositeRiskScorer().score(
        volume_anomaly=mk_vol("SPIKE", extreme=1, blowout=2),  # 60 + 10 = 70
        distribution_pattern=mk_dist(2),                        # 65
        market_relative=mk_rel(rv="ELEVATED", rr="MILD_UNDERPERFORM"),  # max(40,20)=40
    )
    assert out["data_quality"]["sufficient_for_score"] is True
    assert out["data_quality"]["advisory_only"] is False
    assert out["data_quality"]["confidence"] == 1.0  # 重分配后总效权重=100
    assert out["score"] is not None
    assert out["level"] in {"MODERATE", "ELEVATED"}, out["level"]
    assert len(out["primary_drivers"]) >= 2
    # vol 应该是首个 driver (weighted 最大)
    assert out["primary_drivers"][0]["component"] == "volume_anomaly"


@_case("C02 派发样本：所有信号都触发 → 高分")
def c02():
    out = CompositeRiskScorer().score(
        volume_anomaly=mk_vol("HISTORIC", extreme=3, blowout=2),  # 95
        distribution_pattern=mk_dist(4),                          # 95
        market_relative=mk_rel(rv="HISTORIC", rr="STRONG_UNDERPERFORM"),  # 90
    )
    assert out["score"] >= 90, out["score"]
    assert out["level"] == "CRITICAL", out["level"]


@_case("C03 index_anomalous 抑制 market_relative 子分")
def c03():
    out_anom = CompositeRiskScorer().score(
        volume_anomaly=mk_vol("ELEVATED"),
        distribution_pattern=mk_dist(1),
        market_relative=mk_rel(rv="HISTORIC", rr="INLINE", index_anom=True),
    )
    out_normal = CompositeRiskScorer().score(
        volume_anomaly=mk_vol("ELEVATED"),
        distribution_pattern=mk_dist(1),
        market_relative=mk_rel(rv="HISTORIC", rr="INLINE", index_anom=False),
    )
    # index_anomalous=True 时 rel 子分 90→45，总分应更低
    assert out_anom["score"] < out_normal["score"]


@_case("C04 weight_redistribution 留痕完整")
def c04():
    out = CompositeRiskScorer().score(
        volume_anomaly=mk_vol("SPIKE"),
        distribution_pattern=mk_dist(2),
        market_relative=mk_rel(rv="ELEVATED"),
    )
    wr = out["data_quality"]["weight_redistribution"]
    assert wr["flow_signals"]["effective"] == 0
    assert wr["flow_signals"].get("reason") == "unavailable"
    assert wr["volume_anomaly"]["original"] == 40
    assert wr["volume_anomaly"]["effective"] > 40  # 收到了重分配


@_case("C05 distribution Null Object → 仍出 score（quorum=2 满足）")
def c05():
    out = CompositeRiskScorer().score(
        volume_anomaly=mk_vol("EXTREME"),
        distribution_pattern=mk_null(),  # ← Null Object
        market_relative=mk_rel(rv="SPIKE"),
    )
    assert out["data_quality"]["sufficient_for_score"] is True
    assert "distribution_pattern" in out["data_quality"]["missing_components"]
    assert out["data_quality"]["core_quorum"] == "2/3"


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

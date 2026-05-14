#!/usr/bin/env python3
"""
test_volume_anomaly_dimensions.py
==================================
DimensionResolver 单元测试（纯函数，无 IO）。

测试矩阵（12 用例）：
  D01 HK + 全维度 → primary='amount'
  D02 CN + 全维度 → primary='turnover_rate'
  D03 US + 全维度 → primary='volume' (policy 决定即使有 turnover/amount 仍选 volume)
  D04 HK 缺 amount → fallback 'volume'
  D05 CN 缺 turnover_rate → fallback 'amount'
  D06 CN 仅 volume → fallback 'volume'
  D07 US 仅 volume → 'volume'
  D08 market_type=None → 退化为表序首个可得（向后兼容）
  D09 market_type=UNKNOWN → 同 None
  D10 active_dimensions 保留 DIMENSIONS 表序，不被 columns 顺序左右
  D11 空 columns → ([], '', mlabel)
  D12 自定义 all_dimensions 子集（profiler config 覆盖场景）
"""
from __future__ import annotations

import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alphaflow.core.acl.mappings.enums import MarketType
from alphaflow.components.processors.techniques.analyzers.volume_anomaly.dimensions import (
    DimensionResolver,
)
from alphaflow.components.processors.techniques.analyzers.volume_anomaly.config import (
    DIMENSIONS,
)


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


print("\n[Section] DimensionResolver — 市场感知 + Fallback Chain")


@_case("D01 HK + 全维度 → primary='amount'")
def d01():
    active, primary, mlabel = DimensionResolver.resolve(
        {"close", "volume", "amount", "turnover_rate"},
        MarketType.HK,
    )
    assert primary == "amount", f"got {primary}"
    assert mlabel == "hk"
    assert [d["key"] for d in active] == ["volume", "amount", "turnover_rate"]


@_case("D02 CN + 全维度 → primary='turnover_rate'")
def d02():
    _, primary, mlabel = DimensionResolver.resolve(
        {"volume", "amount", "turnover_rate"}, MarketType.CN,
    )
    assert primary == "turnover_rate", f"got {primary}"
    assert mlabel == "cn"


@_case("D03 US + 全维度 → primary='volume' (policy)")
def d03():
    # 即使数据中有 turnover_rate/amount，US policy 仍选 volume
    _, primary, _ = DimensionResolver.resolve(
        {"volume", "amount", "turnover_rate"}, MarketType.US,
    )
    assert primary == "volume", f"got {primary}"


@_case("D04 HK 缺 amount → fallback 'volume'")
def d04():
    _, primary, _ = DimensionResolver.resolve({"volume"}, MarketType.HK)
    assert primary == "volume", f"got {primary}"


@_case("D05 CN 缺 turnover_rate → fallback 'amount'")
def d05():
    _, primary, _ = DimensionResolver.resolve({"volume", "amount"}, MarketType.CN)
    assert primary == "amount", f"got {primary}"


@_case("D06 CN 仅 volume → 链尾 'volume'")
def d06():
    _, primary, _ = DimensionResolver.resolve({"volume"}, MarketType.CN)
    assert primary == "volume"


@_case("D07 US 仅 volume → 'volume'")
def d07():
    active, primary, _ = DimensionResolver.resolve({"volume"}, MarketType.US)
    assert primary == "volume"
    assert len(active) == 1 and active[0]["key"] == "volume"


@_case("D08 market_type=None → 表序首个 (向后兼容 Phase 1)")
def d08():
    _, primary, mlabel = DimensionResolver.resolve(
        {"volume", "amount"}, market_type=None,
    )
    # DIMENSIONS 表序 volume 在前
    assert primary == "volume"
    assert mlabel == "unknown"


@_case("D09 market_type=UNKNOWN → 同 None")
def d09():
    _, primary, mlabel = DimensionResolver.resolve(
        {"volume", "amount", "turnover_rate"}, MarketType.UNKNOWN,
    )
    assert primary == "volume"
    assert mlabel == "unknown"


@_case("D10 active_dimensions 保留 DIMENSIONS 表序")
def d10():
    # columns 用相反顺序传入，结果应仍是表序
    active, _, _ = DimensionResolver.resolve(
        ["turnover_rate", "amount", "volume"],  # 倒序 iterable
        MarketType.HK,
    )
    keys = [d["key"] for d in active]
    expected = [d["key"] for d in DIMENSIONS]
    assert keys == expected, f"got {keys}, expected {expected}"


@_case("D11 空 columns → ([], '', mlabel)")
def d11():
    active, primary, mlabel = DimensionResolver.resolve(set(), MarketType.HK)
    assert active == []
    assert primary == ""
    assert mlabel == "hk"


@_case("D12 自定义 all_dimensions 子集（config 覆盖场景）")
def d12():
    # profiler 用户通过 config 只启用 amount 单维度
    custom_dims = ({"key": "amount", "column": "amount"},)
    active, primary, _ = DimensionResolver.resolve(
        {"volume", "amount", "turnover_rate"},
        MarketType.HK,
        all_dimensions=custom_dims,
    )
    assert [d["key"] for d in active] == ["amount"]
    assert primary == "amount"  # 唯一可得即主


# ============================================================== entry
if __name__ == "__main__":
    funcs = [v for k, v in list(globals().items())
             if k.startswith("d") and len(k) >= 3 and k[1:3].isdigit() and callable(v)]
    funcs.sort(key=lambda f: f.__name__)
    print(f"\n[Runner] 共 {len(funcs)} 个测试用例\n")
    for fn in funcs:
        fn()
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = len(_results) - passed
    print(f"\n{'='*60}")
    print(f"  Total: {len(_results)}  Passed: {passed}  Failed: {failed}")
    print(f"{'='*60}")
    if failed:
        print("\nFailures:")
        for n, ok, err in _results:
            if not ok:
                print(f"  - {n}: {err}")
        sys.exit(1)
    sys.exit(0)

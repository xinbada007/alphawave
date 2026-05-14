#!/usr/bin/env python3
"""
test_vwap_fallback.py
=====================
验证 Derived Column Enricher 框架与 VwapFromAmountEnricher 实现。

测试矩阵：
  [基类契约]
    T01 can_apply: output 已存在时跳过
    T02 can_apply: 缺少 required_inputs 时跳过
    T03 can_apply: 空 df 时跳过
    T04 can_apply: 输入齐全时返回 True

  [VwapFromAmountEnricher]
    T05 amount+volume 派生 vwap = amount/volume
    T06 volume=0 行 → vwap = NaN（不是 inf）
    T07 已有 vwap 列时不被覆写
    T08 缺 amount 时不派生
    T09 空 df 直通
    T10 幂等：apply 两次 == apply 一次（通过 can_apply 守卫）

  [BaseMarketFetcher 集成]
    T11 _clean_dataframe 自动调用 enrichers，AkShare 风格输入产出 vwap
    T12 OpenBB 风格输入（已有 vwap）不被覆写
    T13 子类覆写 enrichers ClassVar 可追加新 enricher

不依赖网络。运行：
    python3 tests/test_vwap_fallback.py
"""
from __future__ import annotations

import math
import os
import sys
import traceback
from typing import ClassVar, Sequence

import pandas as pd
import numpy as np

# 路径注入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alphaflow.components.collectors.market_data.fetchers.enrichers import (  # noqa: E402
    DerivedColumnEnricher,
    VwapFromAmountEnricher,
    DEFAULT_ENRICHERS,
)
from alphaflow.components.collectors.market_data.fetchers.base import (  # noqa: E402
    BaseMarketFetcher,
)


# ---------------------------------------------------------------
# 测试运行器
# ---------------------------------------------------------------
_results: list[tuple[str, bool, str]] = []


def _case(name: str):
    def deco(fn):
        def wrapper():
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
        return wrapper
    return deco


def _make_df(**kwargs) -> pd.DataFrame:
    """构造样本 DataFrame，列由 kwargs 决定。"""
    return pd.DataFrame(kwargs)


# ---------------------------------------------------------------
# Section 1: 基类契约
# ---------------------------------------------------------------
print("\n[Section 1] DerivedColumnEnricher base contract")

@_case("T01 can_apply 跳过：output 已存在")
def t01():
    e = VwapFromAmountEnricher()
    df = _make_df(amount=[1.0, 2.0], volume=[10, 20], vwap=[0.1, 0.1])
    assert e.can_apply(df) is False, "已有 vwap 列时应跳过"


@_case("T02 can_apply 跳过：缺 required_inputs")
def t02():
    e = VwapFromAmountEnricher()
    df = _make_df(amount=[1.0, 2.0])  # 缺 volume
    assert e.can_apply(df) is False


@_case("T03 can_apply 跳过：空 df")
def t03():
    e = VwapFromAmountEnricher()
    df = pd.DataFrame(columns=["amount", "volume"])
    assert e.can_apply(df) is False


@_case("T04 can_apply 通过：输入齐全且 output 缺失")
def t04():
    e = VwapFromAmountEnricher()
    df = _make_df(amount=[1.0, 2.0], volume=[10, 20])
    assert e.can_apply(df) is True


# ---------------------------------------------------------------
# Section 2: VwapFromAmountEnricher 实现
# ---------------------------------------------------------------
print("\n[Section 2] VwapFromAmountEnricher implementation")

@_case("T05 派生 vwap = amount / volume")
def t05():
    e = VwapFromAmountEnricher()
    df = _make_df(amount=[100.0, 200.0, 300.0], volume=[10, 20, 30])
    out = e.apply(df)
    assert "vwap" in out.columns
    expected = [10.0, 10.0, 10.0]
    actual = out["vwap"].tolist()
    assert actual == expected, f"vwap mismatch: {actual} vs {expected}"
    assert out["vwap"].dtype == np.float64, f"dtype wrong: {out['vwap'].dtype}"


@_case("T06 volume=0 → vwap=NaN（不是 inf）")
def t06():
    e = VwapFromAmountEnricher()
    df = _make_df(amount=[100.0, 200.0, 300.0], volume=[10, 0, 30])
    out = e.apply(df)
    v = out["vwap"].tolist()
    assert v[0] == 10.0
    assert math.isnan(v[1]), f"expected NaN, got {v[1]!r}"
    assert v[2] == 10.0
    # 关键：不能产生 inf
    assert not np.isinf(out["vwap"]).any(), "vwap should never be inf"


@_case("T07 已有 vwap 列时不被覆写（OpenBB 兼容性）")
def t07():
    e = VwapFromAmountEnricher()
    df = _make_df(
        amount=[100.0, 200.0],
        volume=[10, 20],
        vwap=[7.7, 8.8],  # 假设来自 OpenBB
    )
    # can_apply 应跳过，故 apply 不应被外部触发；
    # 但即使误调用 apply，业务约定是 enricher pipeline 走 can_apply 守卫
    assert e.can_apply(df) is False
    # 模拟 _apply_enrichers 流程
    if e.can_apply(df):
        df = e.apply(df)
    assert df["vwap"].tolist() == [7.7, 8.8], "原 vwap 应保留"


@_case("T08 缺 amount 时整体不派生 vwap")
def t08():
    e = VwapFromAmountEnricher()
    df = _make_df(volume=[10, 20], close=[1.0, 2.0])
    assert e.can_apply(df) is False
    if e.can_apply(df):
        df = e.apply(df)
    assert "vwap" not in df.columns


@_case("T09 空 df 直通：can_apply=False")
def t09():
    e = VwapFromAmountEnricher()
    df = pd.DataFrame(columns=["amount", "volume"])
    assert e.can_apply(df) is False


@_case("T10 幂等：can_apply 守卫保证多次安全")
def t10():
    e = VwapFromAmountEnricher()
    df = _make_df(amount=[100.0], volume=[10])

    # 第一次
    if e.can_apply(df):
        df = e.apply(df)
    snapshot = df["vwap"].tolist()

    # 第二次（守卫拦截）
    if e.can_apply(df):
        df = e.apply(df)

    assert df["vwap"].tolist() == snapshot, "重复应用不应改变结果"


# ---------------------------------------------------------------
# Section 3: BaseMarketFetcher 集成
# ---------------------------------------------------------------
print("\n[Section 3] BaseMarketFetcher integration")


class _FakeFetcher(BaseMarketFetcher):
    """测试桩 fetcher，仅暴露 _clean_dataframe 用于校验集成行为。"""
    name = "FakeFetcher"

    async def fetch_price(self, symbol: str, days: int) -> pd.DataFrame:
        return pd.DataFrame()

    async def fetch_metrics(self, symbol: str):
        return {}


@_case("T11 _clean_dataframe 自动调用 enrichers (AkShare HK 风格)")
def t11():
    f = _FakeFetcher()
    # 模拟 AkShare HK 原始数据 (中文列 + 缺 vwap)
    raw = pd.DataFrame({
        "日期": ["2025-01-02", "2025-01-03"],
        "开盘": [100.0, 105.0],
        "最高": [110.0, 112.0],
        "最低": [99.0, 104.0],
        "收盘": [108.0, 110.0],
        "成交量": [1000, 2000],
        "成交额": [108000.0, 220000.0],
        "换手率": [1.2, 1.5],
    })
    rename_map = {
        "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
        "收盘": "close", "成交量": "volume", "成交额": "amount", "换手率": "turnover_rate",
    }
    out = f._clean_dataframe(raw, rename_map)
    assert "vwap" in out.columns, f"vwap 应被自动派生; 实际列: {out.columns.tolist()}"
    expected = [108.0, 110.0]
    actual = out["vwap"].tolist()
    assert actual == expected, f"vwap mismatch: {actual} vs {expected}"


@_case("T12 OpenBB 风格输入（已有 vwap）不被覆写")
def t12():
    f = _FakeFetcher()
    # 模拟 OpenBB 美股原始数据 (英文列 + 已有 vwap)
    raw = pd.DataFrame({
        "date": ["2025-01-02", "2025-01-03"],
        "open": [100.0, 105.0],
        "high": [110.0, 112.0],
        "low":  [99.0, 104.0],
        "close": [108.0, 110.0],
        "volume": [1000, 2000],
        "vwap":  [105.5, 108.5],  # ← OpenBB 提供
    })
    out = f._clean_dataframe(raw, {})
    assert out["vwap"].tolist() == [105.5, 108.5], "OpenBB vwap 不应被覆写"


@_case("T13 子类可覆写 enrichers ClassVar 追加新 enricher")
def t13():
    class _TypicalPriceEnricher(DerivedColumnEnricher):
        output_column = "typical_price"
        required_inputs = frozenset({"high", "low", "close"})

        def apply(self, df: pd.DataFrame) -> pd.DataFrame:
            return df.assign(
                typical_price=((df["high"] + df["low"] + df["close"]) / 3.0).astype("float64")
            )

    class _ExtendedFetcher(_FakeFetcher):
        # 追加自定义 enricher，验证开闭原则
        enrichers: ClassVar[Sequence[DerivedColumnEnricher]] = (
            *DEFAULT_ENRICHERS,
            _TypicalPriceEnricher(),
        )

    f = _ExtendedFetcher()
    raw = pd.DataFrame({
        "date": ["2025-01-02"],
        "high": [110.0], "low": [90.0], "close": [100.0],
        "volume": [1000], "amount": [100000.0],
    })
    out = f._clean_dataframe(raw, {})
    assert "vwap" in out.columns, "vwap 应仍被派生"
    assert "typical_price" in out.columns, "新追加的 typical_price 应被派生"
    assert out["typical_price"].iloc[0] == 100.0
    assert out["vwap"].iloc[0] == 100.0

    # 验证基类未受污染
    assert "typical_price" not in [e.output_column for e in BaseMarketFetcher.enrichers], \
        "基类 enrichers 不应被子类污染"


# ---------------------------------------------------------------
# 入口
# ---------------------------------------------------------------
if __name__ == "__main__":
    import unittest  # 仅用于显式调用本文件中的 @_case 测试

    # 直接遍历模块全局变量，调用所有 @_case 装饰过的函数
    test_funcs = [v for k, v in list(globals().items())
                  if k.startswith("t") and len(k) >= 3 and k[1:3].isdigit() and callable(v)]
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

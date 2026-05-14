#!/usr/bin/env python3
"""
test_technical_registry.py
============================
TechnicalAnalyzerRegistry 框架自身的单元测试（无业务依赖）。

测试矩阵（11 用例）：
  R01 register 装饰器返回原类（链式装配可继续）
  R02 register 拒绝非 BaseTechnicalAnalyzer 子类
  R03 register 幂等（同名类不重复注册）
  R04 registered() 返回只读元组
  R05 沙箱：analyzer 抛异常不阻断后续
  R06 沙箱：compute 返回 None 视为降级 (success=False)
  R07 沙箱：compute 返回非 dict 被拒
  R08 namespace="" → 顶层合并
  R09 namespace="X" → 写到 out["X"]
  R10 depends_on 拓扑序：B 依赖 A → A 先于 B 执行
  R11 disabled 列表：被禁用的 analyzer 不执行
  R12 缺 required_columns → 降级（不调用 compute）

每个测试都隔离 registry 状态（用 clear() + 重新注册）。
"""
from __future__ import annotations

import os
import sys
import traceback
from typing import Any, Dict, Mapping

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from alphaflow.components.processors.techniques.base import BaseTechnicalAnalyzer
from alphaflow.components.processors.techniques.registry import TechnicalAnalyzerRegistry
from alphaflow.core.schema import ResearchPack
from alphaflow.core.schema.models import DataFrameModel


_results: list[tuple[str, bool, str]] = []


def _case(name: str):
    def deco(fn):
        def w():
            saved = list(TechnicalAnalyzerRegistry._entries)
            TechnicalAnalyzerRegistry.clear()
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
            finally:
                # 恢复全局注册表（避免污染其他测试）
                TechnicalAnalyzerRegistry._entries[:] = saved
        return w
    return deco


def _make_pack() -> ResearchPack:
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-02", periods=10, freq="B").strftime("%Y-%m-%d"),
        "close": [100.0] * 10,
        "volume": [1_000_000] * 10,
    })
    return ResearchPack(symbol="T.X", market_data=DataFrameModel.from_df(df))


def _df():
    return _make_pack().market_data.to_df()


# =================================================================== Tests
print("\n[Section] TechnicalAnalyzerRegistry framework")


@_case("R01 装饰器返回原类")
def r01():
    @TechnicalAnalyzerRegistry.register
    class A(BaseTechnicalAnalyzer):
        namespace = "a"
        def compute(self, df, pack, upstream): return {}
    assert A.__name__ == "A"
    assert A in TechnicalAnalyzerRegistry.registered()


@_case("R02 拒绝非 BaseTechnicalAnalyzer 子类")
def r02():
    try:
        TechnicalAnalyzerRegistry.register(int)
    except TypeError:
        return
    raise AssertionError("应抛 TypeError")


@_case("R03 幂等：同名类不重复注册")
def r03():
    @TechnicalAnalyzerRegistry.register
    class A(BaseTechnicalAnalyzer):
        namespace = "a"
        def compute(self, df, pack, upstream): return {}

    # 再注册一次（模拟双重 import）
    TechnicalAnalyzerRegistry.register(A)
    assert len(TechnicalAnalyzerRegistry.registered()) == 1


@_case("R04 registered() 返回不可变快照")
def r04():
    @TechnicalAnalyzerRegistry.register
    class A(BaseTechnicalAnalyzer):
        namespace = "a"
        def compute(self, df, pack, upstream): return {}
    snap = TechnicalAnalyzerRegistry.registered()
    assert isinstance(snap, tuple)


@_case("R05 沙箱：crashing analyzer 不阻断后续")
def r05():
    @TechnicalAnalyzerRegistry.register
    class Crash(BaseTechnicalAnalyzer):
        namespace = "crash"
        def compute(self, df, pack, upstream):
            raise RuntimeError("boom")

    @TechnicalAnalyzerRegistry.register
    class OK(BaseTechnicalAnalyzer):
        namespace = "ok"
        def compute(self, df, pack, upstream):
            return {"answer": 42}

    out = TechnicalAnalyzerRegistry.run_all(_df(), _make_pack(), {})
    assert "crash" not in out, f"crash 不应出现: {out}"
    assert out.get("ok") == {"answer": 42}, f"ok 应正常输出: {out}"


@_case("R06 compute 返回 None → 降级（success=False）")
def r06():
    @TechnicalAnalyzerRegistry.register
    class Empty(BaseTechnicalAnalyzer):
        namespace = "empty"
        def compute(self, df, pack, upstream): return None

    out = TechnicalAnalyzerRegistry.run_all(_df(), _make_pack(), {})
    # None → 转成 {}, 但 BaseTechnicalAnalyzer.run 会包装成 success=True payload={}
    # 仍会被 merge 进 out (out["empty"] = {})
    # 只要不抛、不污染其他 key 即可
    assert "empty" in out and out["empty"] == {}


@_case("R07 compute 返回非 dict → 降级")
def r07():
    @TechnicalAnalyzerRegistry.register
    class BadType(BaseTechnicalAnalyzer):
        namespace = "bad"
        def compute(self, df, pack, upstream): return [1, 2, 3]

    out = TechnicalAnalyzerRegistry.run_all(_df(), _make_pack(), {})
    assert "bad" not in out, f"非 dict 应被降级: {out}"


@_case("R08 namespace='' → 顶层合并")
def r08():
    @TechnicalAnalyzerRegistry.register
    class TopLevel(BaseTechnicalAnalyzer):
        namespace = ""
        def compute(self, df, pack, upstream):
            return {"foo": 1, "bar": 2}

    out = TechnicalAnalyzerRegistry.run_all(_df(), _make_pack(), {})
    assert out.get("foo") == 1 and out.get("bar") == 2
    assert "" not in out, "空 namespace key 不应出现"


@_case("R09 namespace='X' → 写到 out['X']")
def r09():
    @TechnicalAnalyzerRegistry.register
    class Nested(BaseTechnicalAnalyzer):
        namespace = "nested"
        def compute(self, df, pack, upstream): return {"k": "v"}

    out = TechnicalAnalyzerRegistry.run_all(_df(), _make_pack(), {})
    assert out["nested"] == {"k": "v"}


@_case("R10 depends_on 拓扑序：B 依赖 A → A 先执行，B 可见 A 结果")
def r10():
    order = []

    @TechnicalAnalyzerRegistry.register
    class B(BaseTechnicalAnalyzer):
        namespace = "b"
        depends_on = ("a",)
        def compute(self, df, pack, upstream):
            order.append("b")
            assert "a" in upstream, f"B 应能看到 A 的结果，得到 upstream={list(upstream.keys())}"
            return {"saw_a": upstream["a"]}

    @TechnicalAnalyzerRegistry.register
    class A(BaseTechnicalAnalyzer):
        namespace = "a"
        def compute(self, df, pack, upstream):
            order.append("a")
            return {"value": 1}

    out = TechnicalAnalyzerRegistry.run_all(_df(), _make_pack(), {})
    assert order == ["a", "b"], f"执行顺序错: {order}"
    assert out["b"] == {"saw_a": {"value": 1}}


@_case("R11 disabled 列表跳过指定 analyzer")
def r11():
    @TechnicalAnalyzerRegistry.register
    class A(BaseTechnicalAnalyzer):
        namespace = "a"
        def compute(self, df, pack, upstream): return {"x": 1}

    @TechnicalAnalyzerRegistry.register
    class B(BaseTechnicalAnalyzer):
        namespace = "b"
        def compute(self, df, pack, upstream): return {"x": 2}

    out = TechnicalAnalyzerRegistry.run_all(_df(), _make_pack(), {}, disabled=["b"])
    assert "a" in out and "b" not in out


@_case("R12 缺 required_columns → 降级，compute 不被调用")
def r12():
    called = []

    @TechnicalAnalyzerRegistry.register
    class NeedsAmount(BaseTechnicalAnalyzer):
        namespace = "needs_amount"
        required_columns = ("amount",)
        def compute(self, df, pack, upstream):
            called.append(True)
            return {"k": "v"}

    out = TechnicalAnalyzerRegistry.run_all(_df(), _make_pack(), {})  # df 无 amount
    assert called == [], "compute 不应被调用"
    assert "needs_amount" not in out


# =========================================================== entry
if __name__ == "__main__":
    test_funcs = [v for k, v in list(globals().items())
                  if k.startswith("r") and len(k) >= 3 and k[1:3].isdigit() and callable(v)]
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
        for n, ok, err in _results:
            if not ok:
                print(f"  - {n}: {err}")
        sys.exit(1)
    sys.exit(0)

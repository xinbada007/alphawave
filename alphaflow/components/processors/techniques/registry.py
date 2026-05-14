"""
Technical Analyzer Registry
============================
集中注册并编排所有 BaseTechnicalAnalyzer 子类。镜像 MetricEngine 哲学：

  | MetricEngine                           | TechnicalAnalyzerRegistry          |
  |----------------------------------------|------------------------------------|
  | @MetricEngine.fundamental_metric(...)  | @TechnicalAnalyzerRegistry.register|
  | domain 分桶                            | namespace 分桶                     |
  | depends_on 三元组                      | depends_on 字符串元组              |
  | 沙箱执行                               | 沙箱执行                           |
  | 幂等防重复注册                         | 幂等防重复注册                     |

执行流程（run_all）：
  1. 拓扑排序（按 depends_on）
  2. 逐个 analyzer 调 .run()，捕获顶层异常 → AnalyzerResult(success=False)
  3. 成功结果纳入 upstream 上下文，供下游 analyzer 消费
  4. 合并：namespace == "" 顶层 update；namespace != "" 写到 out[namespace]

对架构漂移的免疫力：
  - 加 analyzer：新建文件 + @register，无需碰本文件
  - 加依赖：在子类 depends_on 声明，自动拓扑
  - Phase 6 综合评分：声明 depends_on=("volume_anomaly_profile", "distribution_patterns", ...)
"""
from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Mapping, Optional, Sequence, Type

import pandas as pd

from alphaflow.core.schema import ResearchPack

from .base import AnalyzerResult, BaseTechnicalAnalyzer


class TechnicalAnalyzerRegistry:
    """全局单例式注册中心。所有 analyzer 通过装饰器 / 显式 register() 进入。"""

    # 类变量：全局注册表（与 MetricEngine._registry 同款）
    _entries: ClassVar[List[Type[BaseTechnicalAnalyzer]]] = []

    # =========================================================
    # 注册 API
    # =========================================================
    @classmethod
    def register(cls, analyzer_cls: Type[BaseTechnicalAnalyzer]) -> Type[BaseTechnicalAnalyzer]:
        """
        装饰器糖：

            @TechnicalAnalyzerRegistry.register
            class VolumeAnomalyAnalyzer(BaseTechnicalAnalyzer): ...

        亦可显式调用：

            TechnicalAnalyzerRegistry.register(MyAnalyzer)

        幂等：同名类不重复注册（防止 import 副作用导致的双重装饰）。
        """
        if not isinstance(analyzer_cls, type) or not issubclass(analyzer_cls, BaseTechnicalAnalyzer):
            raise TypeError(
                f"register() expects BaseTechnicalAnalyzer subclass, got {analyzer_cls!r}"
            )
        if any(e.__qualname__ == analyzer_cls.__qualname__ for e in cls._entries):
            return analyzer_cls
        cls._entries.append(analyzer_cls)
        return analyzer_cls

    @classmethod
    def registered(cls) -> Sequence[Type[BaseTechnicalAnalyzer]]:
        """返回当前注册的所有 analyzer 类（只读视图）。用于诊断与测试。"""
        return tuple(cls._entries)

    @classmethod
    def clear(cls) -> None:
        """清空注册表。仅供测试使用，生产代码不应调用。"""
        cls._entries.clear()

    # =========================================================
    # 执行 API
    # =========================================================
    @classmethod
    def run_all(
        cls,
        df: pd.DataFrame,
        pack: ResearchPack,
        config: Optional[Mapping[str, Any]] = None,
        disabled: Sequence[str] = (),
    ) -> Dict[str, Any]:
        """
        按 depends_on 拓扑顺序执行所有 analyzer，沙箱化错误。

        Args:
            df:        清洗后的 OHLCV-类 DataFrame
            pack:      ResearchPack（只读传入，analyzer 不应修改）
            config:    全局配置 dict，逐个传给 analyzer 构造器
            disabled:  要跳过的 namespace 列表（生产配置开关）

        Returns:
            合并后的 dict，可直接赋给 distilled_features.technical
        """
        ordered = cls._topological_order(cls._entries)
        merged: Dict[str, Any] = {}
        upstream: Dict[str, Any] = {}

        for analyzer_cls in ordered:
            ns = analyzer_cls.namespace
            if ns in disabled:
                continue
            try:
                instance = analyzer_cls(config)
                result = instance.run(df, pack, upstream)
            except Exception as e:  # 沙箱：单 analyzer 失败不阻断
                print(f"  [TechnicalRegistry] ⚠️ {analyzer_cls.__name__} crashed: "
                      f"{type(e).__name__}: {e}")
                continue

            if not result.success:
                print(f"  [TechnicalRegistry] ⚠️ {analyzer_cls.__name__} degraded: "
                      f"{result.note}")
                continue

            # 上下文：供下游 analyzer 通过 depends_on 消费
            if ns:
                upstream[ns] = result.payload
            else:
                # 顶层合并的 analyzer，用类名作 upstream key（避免冲突）
                upstream[f"_root_{analyzer_cls.__name__}"] = result.payload

            # 合并到最终输出
            if ns == "":
                merged.update(result.payload)
            else:
                merged[ns] = result.payload

        return merged

    # =========================================================
    # 内部：拓扑排序
    # =========================================================
    @staticmethod
    def _topological_order(
        entries: Sequence[Type[BaseTechnicalAnalyzer]],
    ) -> List[Type[BaseTechnicalAnalyzer]]:
        """
        Kahn 算法。namespace 为 key；空 namespace 视为无名（不可被依赖，但优先）。
        循环依赖时按原顺序回退（打日志），保证不死锁。
        """
        # 索引：namespace -> analyzer
        by_ns: Dict[str, Type[BaseTechnicalAnalyzer]] = {
            e.namespace: e for e in entries if e.namespace
        }
        no_name = [e for e in entries if not e.namespace]

        # 入度
        indeg: Dict[Type[BaseTechnicalAnalyzer], int] = {e: 0 for e in entries}
        deps_resolved: Dict[Type[BaseTechnicalAnalyzer], List[Type[BaseTechnicalAnalyzer]]] = {
            e: [] for e in entries
        }
        for e in entries:
            for dep_ns in e.depends_on:
                dep = by_ns.get(dep_ns)
                if dep is None:
                    print(f"  [TechnicalRegistry] ⚠️ {e.__name__} depends_on '{dep_ns}' "
                          f"which is not registered; ignoring this edge")
                    continue
                indeg[e] += 1
                deps_resolved[dep].append(e)

        # 先放入空 namespace 的（兜底优先级），再放入无前置依赖的
        ordered: List[Type[BaseTechnicalAnalyzer]] = list(no_name)
        ready = [e for e in entries if e not in no_name and indeg[e] == 0]
        while ready:
            cur = ready.pop(0)
            ordered.append(cur)
            for nxt in deps_resolved[cur]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready.append(nxt)

        if len(ordered) < len(entries):
            # 存在循环依赖；按原序追加未排入者，记日志
            remaining = [e for e in entries if e not in ordered]
            print(f"  [TechnicalRegistry] ⚠️ cyclic depends_on detected among "
                  f"{[e.__name__ for e in remaining]}; falling back to registration order")
            ordered.extend(remaining)
        return ordered

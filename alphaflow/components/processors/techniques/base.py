"""
Technical Analyzer Base Contract
=================================
所有"技术因子分析器"的统一抽象。与 MetricEngine 哲学对称：
- MetricEngine: 装饰器注册 + domain 分桶 + 沙箱执行 + depends_on 依赖
- TechnicalAnalyzerRegistry: 同上，但作用于"中粒度因子模块"而非"细粒度指标"

设计模式：
- Template Method: BaseTechnicalAnalyzer.run() 编排公共流程，子类只覆写 compute()
- Strategy: 每个具体 analyzer 是一个策略实现
- Result Object: AnalyzerResult 显式封装成功/失败/降级语义

职责边界（单一职责）：
- BaseTechnicalAnalyzer: 模板编排 + 输入校验 + 输出 sanitize
- 子类 compute(): 仅做业务计算，不关心错误处理与序列化
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Mapping, Optional, Tuple

import pandas as pd

from alphaflow.core.schema import ResearchPack


@dataclass(frozen=True)
class AnalyzerResult:
    """
    Analyzer 输出的统一结果对象。

    - namespace == ""  → registry 将 payload 顶层合并到 distilled_features.technical
    - namespace != ""  → registry 写入 distilled_features.technical[namespace] = payload
    - success == False → analyzer 沙箱降级（保留 note 用于诊断），payload 仍合法（dict）
    """
    namespace: str
    payload: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    note: Optional[str] = None


class BaseTechnicalAnalyzer(ABC):
    """
    技术因子 analyzer 抽象基类（Template Method）。

    子类必须声明：
      - namespace: ClassVar[str]   写入 distilled_features.technical 的 key（"" 表示顶层合并）
      - depends_on: ClassVar[Tuple[str, ...]]  依赖的其他 analyzer 的 namespace（DAG 拓扑提示）

    子类必须实现：
      - compute(df, pack, upstream) -> Dict[str, Any]
        upstream 是已成功运行的上游 analyzer 的 payload 映射 {namespace: payload}

    禁止：
      - 在 compute 内捕获顶层异常吃掉错误（registry 沙箱已保护）
      - 在 compute 内修改 pack（写入由 TechnicalProcessor 统一执行，遵守 Pydantic 写入契约）
    """

    namespace: ClassVar[str] = ""
    depends_on: ClassVar[Tuple[str, ...]] = ()

    def __init__(self, config: Optional[Mapping[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = dict(config or {})

    # -------------------------------------------------------------------
    # 模板方法：公共流程一锤定音，子类不应覆写
    # -------------------------------------------------------------------
    def run(
        self,
        df: pd.DataFrame,
        pack: ResearchPack,
        upstream: Mapping[str, Any],
    ) -> AnalyzerResult:
        # 输入校验
        if df is None:
            return AnalyzerResult(self.namespace, {}, success=False, note="df is None")
        if not self._meets_prerequisites(df):
            return AnalyzerResult(self.namespace, {}, success=False,
                                  note="prerequisite columns missing")

        # 业务计算（不吞异常 — 由 registry 沙箱处理）
        payload = self.compute(df, pack, upstream)

        # 防御：payload 必须是 dict
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return AnalyzerResult(self.namespace, {}, success=False,
                                  note=f"compute returned non-dict: {type(payload).__name__}")

        return AnalyzerResult(self.namespace, payload, success=True)

    # -------------------------------------------------------------------
    # 子类必须实现
    # -------------------------------------------------------------------
    @abstractmethod
    def compute(
        self,
        df: pd.DataFrame,
        pack: ResearchPack,
        upstream: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """业务计算。返回要写入 distilled_features.technical 下的 dict。"""

    # -------------------------------------------------------------------
    # 可选钩子：子类覆写以声明列依赖（用于 _meets_prerequisites）
    # -------------------------------------------------------------------
    required_columns: ClassVar[Tuple[str, ...]] = ()

    def _meets_prerequisites(self, df: pd.DataFrame) -> bool:
        if not self.required_columns:
            return True
        return all(col in df.columns for col in self.required_columns)

"""
Derived Column Enrichers - 派生列计算器框架
============================================
策略模式 + 自描述：把"从已有列派生新列"抽象为可注册的纯函数对象。

设计哲学：
- 仅派生"行情语义内禀"的列（如 VWAP、典型价、对数收益）
- 不计算分析层因子（CLV / Amihud / RSI 等留给 processor 层）
- 与现有 BaseMarketStrategy 责任链同源：表驱动、自描述、可组合

子类契约（开放扩展，封闭修改）：
- output_column:   声明产出列名（自描述）
- required_inputs: 声明输入列依赖
- apply(df):       纯函数，不修改输入；返回新 df 或 .assign 后的 df

幂等性：can_apply 默认守卫 output_column 不存在，多次应用安全。

依赖排序约定：当前注册表使用 list 顺序，依赖必须在依赖者之前。
（未来若 enricher ≥ 5 个，可改为拓扑排序，不破坏对外接口。）
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, FrozenSet

import pandas as pd


class DerivedColumnEnricher(ABC):
    """派生列计算器抽象基类。
    
    所有子类必须声明：
    - output_column (str)：本计算器产出哪一列
    - required_inputs (frozenset[str])：依赖哪些列
    - apply(df)：派生逻辑（纯函数）
    """

    #: 本计算器产出的列名，子类必须声明
    output_column: ClassVar[str]
    #: 本计算器依赖的输入列集合，默认为空
    required_inputs: ClassVar[FrozenSet[str]] = frozenset()

    def can_apply(self, df: pd.DataFrame) -> bool:
        """默认实现：当 output 列不存在且所有 required_inputs 存在时可应用。
        
        子类一般不需覆写；除非有更复杂的判定（如基于行数或 dtype）。
        """
        if df is None or df.empty:
            return False
        if self.output_column in df.columns:
            return False
        return all(col in df.columns for col in self.required_inputs)

    @abstractmethod
    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        """派生 output_column。
        
        实现要求：
        - 纯函数：不修改入参 df 的内容（推荐使用 df.assign 或 df.copy）
        - 类型安全：派生列应为明确的 dtype（避免 object 列）
        - NaN 友好：边界情况（除零、缺失）应产出 NaN 而非 inf 或抛错
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} output={self.output_column!r}>"

"""
主治医师诊断中心 (Evaluator Engine Hub)
=====================================
统一拉起所有的定性评估器（Evaluators）。
在此注册的 evaluator 会像流水线一样依次运行，读取数字并写下医嘱标签。
"""

import importlib
import inspect
import sys
from typing import Callable, Sequence, Dict

from alphaflow.core.schema import ResearchPack


class EvaluatorEngine:
    """
    诊断结论评估仪 (L2 Tagging Engine)
    
    职责：
    读取 metrics 里的客观数值（Float），
    通过业务规则转换为定性标签（String），
    并将其作为扩展属性写回所属领域的 metrics 字典。
    """
    
    _evaluators: list[Callable[[ResearchPack], None]] = []

    @classmethod
    def register(cls, func: Callable[[ResearchPack], None]) -> Callable:
        """注册诊断器函数"""
        cls._evaluators.append(func)
        return func

    @classmethod
    def evaluate_all(cls, pack: ResearchPack) -> None:
        """
        一次性运行所有注册的评估器。
        所有评估器都可以毫无约束地读取 pack 中已有的 (特别是 fundamental_metrics 中的) 数据。
        """
        for evaluate_func in cls._evaluators:
            evaluate_func(pack)


# ==============
# 自动加载所有域求值器
# ==============
from . import trend_evaluator  # noqa: F401

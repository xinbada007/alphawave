"""
基本面蒸馏模块 (Fundamentals Distillation)
==========================================
模块职责：
1. Insider 高管交易降噪 (硬编码输入，Pydantic 输出)
2. Dividend 分红分析 (硬编码输入，Pydantic 输出)
3. Earnings 财报超预期分析 (ACL 标准化输入，Pydantic 输出)
4. Cross-Domain Scanner 跨域基本面扫描
"""

# 核心分析器
from alphaflow.components.processors.fundamentals.insider import InsiderAnalyzer

# 跨域扫描器
from alphaflow.components.processors.fundamentals.scanner import scan_fundamentals

__all__ = [
    "InsiderAnalyzer",
    "scan_fundamentals",
]

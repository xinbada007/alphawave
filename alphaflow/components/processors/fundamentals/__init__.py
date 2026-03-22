"""
基本面蒸馏模块 (Fundamentals Distillation)
==========================================
模块职责：
1. Insider 高管交易降噪 (硬编码输入，Pydantic 输出)
2. Dividend 分红分析 (硬编码输入，Pydantic 输出)
3. Cross-Domain Scanner 跨域基本面扫描
"""

# 核心分析器
from alphaflow.components.processors.fundamentals.insider import InsiderAnalyzer

# 跨域扫描器
from alphaflow.components.processors.fundamentals.scanner import scan_fundamentals

# Health Tagger (保留向后兼容)
from alphaflow.components.processors.fundamentals.health_tagger import (
    HealthTagger,
    generate_health_tags,
    generate_health_tags_with_desc,
)

__all__ = [
    # 核心分析器
    "InsiderAnalyzer",

    # 跨域扫描器
    "scan_fundamentals",

    # Health Tagger (legacy)
    "HealthTagger",
    "generate_health_tags",
    "generate_health_tags_with_desc",
]

"""
基本面蒸馏模块 (Fundamentals Distillation) - V3 架构
====================================================
极简设计：仅保留核心降噪逻辑，消灭冗余映射层。

模块职责：
1. Insider 高管交易降噪 (硬编码输入，Pydantic 输出)
2. Dividend 分红分析 (硬编码输入，Pydantic 输出)
3. Health Tag 生成

使用方式：
    from alphaflow.components.processors.fundamentals.insider import InsiderAnalyzer
    
    feature = InsiderAnalyzer.analyze(pack)
"""

# 核心分析器
from alphaflow.components.processors.fundamentals.insider import InsiderAnalyzer

# Health Tagger (保留)
from alphaflow.components.processors.fundamentals.health_tagger import (
    HealthTagger,
    generate_health_tags,
    generate_health_tags_with_desc,
)

__all__ = [
    # 核心分析器
    "InsiderAnalyzer",
    
    # Health Tagger
    "HealthTagger",
    "generate_health_tags",
    "generate_health_tags_with_desc",
]

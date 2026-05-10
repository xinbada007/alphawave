"""
Composite Risk — 配置常量层
============================
所有阈值、权重、闸门规则集中此处，可审计、可调参不改代码。

设计哲学：
- 显式权重：每一分都可追溯到 component → raw → effective → weighted
- 闸门体系：essential → quorum → cap → confidence 四层防御，避免"一两个因素吞掉所有权重"
- 无新概念：仅常量，无逻辑（逻辑全在 scorers.py / scorer.py）
"""
from __future__ import annotations

from typing import Tuple


# =============================================================================
# 名称统一（与上游 namespace 对齐）
# =============================================================================
COMPONENT_VOLUME       = "volume_anomaly"
COMPONENT_DISTRIBUTION = "distribution_pattern"
COMPONENT_MARKET_REL   = "market_relative"
COMPONENT_FLOW         = "flow_signals"

# 上游 namespace 映射（analyzer.py 用此从 upstream dict 取数）
UPSTREAM_NAMESPACES = {
    COMPONENT_VOLUME:       "volume_anomaly_profile",
    COMPONENT_DISTRIBUTION: "distribution_pattern_profile",
    COMPONENT_MARKET_REL:   "market_relative_anomaly_profile",
    COMPONENT_FLOW:         "flow_signals_profile",  # Phase 7 预留
}


# =============================================================================
# 权重表（总和 = 100）
# =============================================================================
WEIGHTS = {
    COMPONENT_VOLUME:       40,
    COMPONENT_DISTRIBUTION: 30,
    COMPONENT_MARKET_REL:   20,
    COMPONENT_FLOW:         10,
}
assert sum(WEIGHTS.values()) == 100, "WEIGHTS 总和必须 = 100"


# =============================================================================
# 闸门 1：必备组件（缺则不发分）
# =============================================================================
ESSENTIAL_COMPONENTS: Tuple[str, ...] = (COMPONENT_VOLUME,)

# =============================================================================
# 闸门 2：核心三件套法定多数
# =============================================================================
CORE_COMPONENTS: Tuple[str, ...] = (
    COMPONENT_VOLUME,
    COMPONENT_DISTRIBUTION,
    COMPONENT_MARKET_REL,
)
MIN_QUORUM = 2  # 至少 2 / 3 在场

# =============================================================================
# 闸门 3：单子项膨胀上限（防止 1 因素吞所有重分配）
# =============================================================================
MAX_INFLATION = 1.5  # effective_weight ≤ original × 1.5

# =============================================================================
# 闸门 4：置信度分层 + 硬底
# =============================================================================
# 升序：value < threshold → label
CONFIDENCE_TIERS: Tuple[Tuple[float, str], ...] = (
    (0.45, "very_low"),
    (0.65, "low"),
    (0.85, "moderate"),
    (1.01, "high"),  # 1.01 上界容错浮点
)
HARD_FLOOR_CONFIDENCE = 0.45  # 低于此即使 essential+quorum 满足也屏蔽 level


# =============================================================================
# 风险等级阈值（score → level）
# =============================================================================
# 升序：score < threshold → label
LEVEL_TIERS: Tuple[Tuple[float, str], ...] = (
    (30,    "LOW"),
    (55,    "MODERATE"),
    (75,    "ELEVATED"),
    (90,    "HIGH"),
    (101,   "CRITICAL"),
)


# =============================================================================
# 子分映射表（D3 — 子 tier → raw score 0..100）
# =============================================================================
# volume_anomaly: latest_day.tier
# 必须与 volume_anomaly/config.py::TIER_ORDER 对齐
# (NORMAL, ELEVATED, SPIKE, EXTREME, BLOWOUT, HISTORIC)
VOLUME_TIER_SCORES = {
    "NORMAL":   0,
    "ELEVATED": 35,
    "SPIKE":    60,
    "EXTREME":  80,
    "BLOWOUT":  90,
    "HISTORIC": 95,
}

# market_relative: latest_day.rel_volume_tier
REL_VOLUME_TIER_SCORES = {
    "LOW":      0,
    "NORMAL":   0,
    "ELEVATED": 40,
    "SPIKE":    70,
    "HISTORIC": 90,
}

# market_relative: latest_day.rel_return_tier（过弱表现配合放量 = 强派发信号）
REL_RETURN_TIER_SCORES = {
    "STRONG_OUTPERFORM": 0,
    "MILD_OUTPERFORM":   0,
    "INLINE":            0,
    "MILD_UNDERPERFORM": 20,
    "STRONG_UNDERPERFORM": 40,
}

# distribution: pressure_signals 计数 → 分数（0/1/2/3+）
DISTRIBUTION_SIGNAL_COUNT_SCORES = {
    0: 0,
    1: 35,
    2: 65,
    3: 90,
}
DISTRIBUTION_MAX_SCORE = 95  # 4+ 信号封顶

# flow_signals: pressure_signals 计数 → 分数（与 distribution 同形）
FLOW_SIGNAL_COUNT_SCORES = {
    0: 0,
    1: 40,
    2: 70,
    3: 90,
}
FLOW_MAX_SCORE = 95  # 4+ 信号封顶

# rolling 异常天数加成
# 取 lookbacks 中的哪个窗口 — 必须是 volume_anomaly/config.py::LOOKBACK_WINDOWS 之一
# 选 20d：~1 个月交易窗口，对"近期密集出货"最敏感（5d 噪声大、60d/252d 太迟钝）
ROLLING_BONUS_WINDOW = "20d"
ROLLING_EXTREME_BONUS_THRESHOLD = 3   # 近窗内 EXTREME+BLOWOUT+HISTORIC ≥ 3 天 → +bonus
ROLLING_EXTREME_BONUS_POINTS = 10
VOLUME_MAX_SCORE = 95  # 加 bonus 后封顶

# market_relative: index_anomalous=True 时该子分系数（剥离系统性放量）
INDEX_ANOMALOUS_DAMPING = 0.5


# =============================================================================
# Tag（输出诊断字符串前缀）
# =============================================================================
TAG_INSUFFICIENT_ESSENTIAL = "[COMPOSITE_RISK_NO_ESSENTIAL]"
TAG_INSUFFICIENT_QUORUM    = "[COMPOSITE_RISK_LOW_QUORUM]"
TAG_LOW_CONFIDENCE         = "[COMPOSITE_RISK_LOW_CONFIDENCE]"
TAG_ADVISORY_ONLY          = "[COMPOSITE_RISK_ADVISORY_ONLY]"

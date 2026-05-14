"""
Flow Signals — 配置常量层
============================
所有阈值、tier 表、TAG 集中此处。可调参不改代码。
"""
from __future__ import annotations

from typing import Tuple


# =============================================================================
# Rolling 窗口
# =============================================================================
BLOCK_TRADE_WINDOW_DAYS = 10
LHB_WINDOW_DAYS         = 10
SOUTHBOUND_WINDOW_DAYS  = 5  # 第一版无历史，仅占位

# =============================================================================
# 大宗交易：信号判定阈值
# =============================================================================
# tier: NORMAL → ELEVATED → HIGH，依据近 10 日折价大宗笔数
BLOCK_TRADE_TIERS: Tuple[Tuple[int, str], ...] = (
    (1,  "NORMAL"),       # < 1 笔 → NORMAL
    (3,  "ELEVATED"),     # < 3 笔 → ELEVATED
    (10, "HIGH"),         # ≥ 3 笔 → HIGH
)

# 折价定义：discount_pct 字段为负表示折价；阈值用绝对值比较
BLOCK_DISCOUNT_THRESHOLD_PCT = -3.0  # ≤ -3% 视为显著折价

# tag
TAG_BLOCK_DISCOUNT_FREQUENT = "[BLOCK_DISCOUNT_FREQUENT]"
TAG_BLOCK_DISCOUNT_DEEP     = "[BLOCK_DISCOUNT_DEEP]"

# =============================================================================
# 龙虎榜
# =============================================================================
LHB_TIERS: Tuple[Tuple[int, str], ...] = (
    (2,   "NORMAL"),     # 0,1 次 → NORMAL
    (3,   "ELEVATED"),   # 2 次 → ELEVATED
    (100, "HIGH"),       # ≥ 3 次 → HIGH
)
LHB_NET_SELL_THRESHOLD_PCT = -1.0  # 净买额占总成交比 ≤ -1% 视为净卖出

TAG_LHB_FREQUENT_APPEARANCE = "[LHB_FREQUENT_APPEARANCE]"
TAG_LHB_NET_SELL            = "[LHB_NET_SELL]"

# =============================================================================
# Southbound（占位）
# =============================================================================
TAG_SOUTHBOUND_OUTFLOW = "[SOUTHBOUND_OUTFLOW]"

# =============================================================================
# 最少需要的天数 / 子源
# =============================================================================
MIN_SOURCES_FOR_PROFILE = 1  # 至少 1 个子源 ok 即可出 profile

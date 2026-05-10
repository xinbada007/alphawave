"""
Volume Anomaly Configuration
=============================
所有阈值、窗口、维度映射集中于此 — 表驱动设计。
修改阈值 / 加 tier / 加维度，原则上只改本文件。
"""
from __future__ import annotations

from typing import Final, Mapping, Tuple

from alphaflow.core.acl.mappings.enums import MarketType


# ----- Tier 分级（百分位为主，ratio 为辅）------------------------------------
# 必须 percentile 与 ratio 共振才升级，避免单一维度噪声触发
ANOMALY_PERCENTILE_TIERS: Final[Mapping[str, float]] = {
    "ELEVATED": 80.0,
    "SPIKE":    90.0,
    "EXTREME":  95.0,
    "BLOWOUT":  98.0,
    "HISTORIC": 99.0,
}

RATIO_GUARDS: Final[Mapping[str, float]] = {
    # ELEVATED 仅靠百分位即可（80 分位是温和门槛）
    "SPIKE":    2.0,
    "EXTREME":  3.0,
    "BLOWOUT":  5.0,
    "HISTORIC": 10.0,
}

# Tier 优先级（升序）— 用于"取最高满足等级"
TIER_ORDER: Final[tuple[str, ...]] = (
    "NORMAL", "ELEVATED", "SPIKE", "EXTREME", "BLOWOUT", "HISTORIC",
)

# ----- 时间窗口配置 -----------------------------------------------------------
LOOKBACK_WINDOWS: Final[tuple[int, ...]] = (5, 20, 60, 252)

# baseline 滚动窗口（计算 mean / std / percentile rank 用）
# 选 60 天：足够稳定，又对最近半年节奏敏感
BASELINE_WINDOW: Final[int] = 60

REGIME_SHIFT_RATIO_THRESHOLD: Final[float] = 1.5
REGIME_SHIFT_SHORT_WINDOW: Final[int] = 20
REGIME_SHIFT_LONG_WINDOW: Final[int] = 120

CAV_WINDOWS: Final[tuple[int, ...]] = (5, 20)
CAV_BASELINE_WINDOW: Final[int] = 60

# 数据质量门槛
MIN_DAYS_FOR_PROFILE: Final[int] = 30

# ----- 维度（Dimension）定义 -------------------------------------------------
# 所有可参与异常剖面的"量"维度。profiler 一次循环全部处理。
# 加新维度只需在此追加一行（{"key": ..., "column": ...}）；DimensionResolver/profiler/
# metrics 均无需改动 — 这是开闭原则的"开"侧入口。
#
# 约定：
#   - key:    输出 JSON 的子 dict 名（snake_case，下游 LLM 可见）
#   - column: 上游 fetcher 提供的列名（必须能在 DataFrame.columns 找到才会激活）
#
# 量纲说明（重要）：
#   metrics.py 的算子（ratio / zscore / pct_rank / CAV）都是 **相对量**，量纲无关；
#   因此 volume(股) / amount(币种金额) / turnover_rate(百分比) 共用同一套算子安全。
DIMENSIONS: Final[tuple[Mapping[str, str], ...]] = (
    {"key": "volume",        "column": "volume"},
    {"key": "amount",        "column": "amount"},
    {"key": "turnover_rate", "column": "turnover_rate"},
)


# ----- 市场感知：主信号维度 + Fallback Chain ----------------------------------
# 表驱动 Strategy — 加新市场只需追加一行；DimensionResolver 不需改。
#
# 选择依据（金融含义）：
#   - HK：amount(成交额, HKD) 比 volume(股数) 更稳定 — 港股股价跨度大、拆股频繁，
#         金额维度抗股价振幅干扰；turnover_rate 港股口径不统一（公众持股 vs 总股本）。
#   - CN：turnover_rate(换手率) — A 股流通股口径标准化、监管披露完整，是 A 股研究
#         机构最常用的活跃度指标，对配股/解禁等事件极其敏感。
#   - US：volume — 美股拆股已罕见、股价稳定，volume 即可；OpenBB 不提供 turnover_rate
#         （流通股精确数据缺失），amount 字段也通常不可得。
MARKET_PRIMARY_DIMENSION: Final[Mapping[MarketType, str]] = {
    MarketType.HK: "amount",
    MarketType.CN: "turnover_rate",
    MarketType.US: "volume",
}

# 主信号缺失时按链降级。链尾必为 "volume"（任何 OHLCV 数据源最低保证）。
MARKET_DIMENSION_FALLBACK: Final[Mapping[MarketType, Tuple[str, ...]]] = {
    MarketType.HK: ("amount", "volume"),
    MarketType.CN: ("turnover_rate", "amount", "volume"),
    MarketType.US: ("volume",),
}

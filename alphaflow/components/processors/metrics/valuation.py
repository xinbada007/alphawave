"""估值指标 (Valuation LCD) — 声明式

pe_ttm/pb: API 直供透传 (P0 — 完全规避币种问题)
ps_ttm: 使用 MARKET_CAP_ALIGNED (Collector 已对齐币种)
"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key

DOMAIN = "valuation_lcd"


@MetricEngine.fundamental_metric(
    feature_name="pe_ttm",
    domain=DOMAIN,
    depends_on=[
        ("LATEST", "metrics", Key.metrics.PE_RATIO),
    ]
)
def calc_pe_ttm(pe: float) -> Optional[float]:
    """市盈率 — API 直供透传"""
    return round(pe, 4)


@MetricEngine.fundamental_metric(
    feature_name="pb",
    domain=DOMAIN,
    depends_on=[
        ("LATEST", "metrics", Key.metrics.PRICE_TO_BOOK),
    ]
)
def calc_pb(pb: float) -> Optional[float]:
    """市净率 — API 直供透传"""
    return round(pb, 4)


@MetricEngine.fundamental_metric(
    feature_name="ps_ttm",
    domain=DOMAIN,
    depends_on=[
        ("LATEST", "metrics", Key.metrics.MARKET_CAP_ALIGNED),
        ("TTM", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_ps_ttm(mcap: float, rev: float) -> Optional[float]:
    """市销率 — 使用 MARKET_CAP_ALIGNED 实现币种透明"""
    return round(mcap / rev, 4) if rev > 0 else None

"""增长趋势 (Growth & Trend Delta) — 年报跨期比较

利用 Facade 的 ANNUAL_LATEST/ANNUAL_PREV 时间锚点，
声明式实现 YoY 增长率和趋势变化。
"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key

DOMAIN_GROWTH = "growth"
DOMAIN_TREND = "trend_delta"


# ==========================================
# YoY 增长率 (Growth) — 年报口径
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="revenue_yoy_pct",
    domain=DOMAIN_GROWTH,
    depends_on=[
        ("ANNUAL_LATEST", "income", Key.income.TOTAL_REVENUE),
        ("ANNUAL_PREV", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_revenue_yoy(cur: float, prev: float) -> Optional[float]:
    """营收 YoY 增长率 (小数形式，0.35 = 35%)"""
    return round((cur - prev) / abs(prev), 4) if abs(prev) > 0 else None


@MetricEngine.fundamental_metric(
    feature_name="net_income_yoy_pct",
    domain=DOMAIN_GROWTH,
    depends_on=[
        ("ANNUAL_LATEST", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
        ("ANNUAL_PREV", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
    ]
)
def calc_ni_yoy(cur: float, prev: float) -> Optional[float]:
    """归母净利 YoY 增长率 (小数形式，0.35 = 35%)"""
    return round((cur - prev) / abs(prev), 4) if abs(prev) > 0 else None


@MetricEngine.fundamental_metric(
    feature_name="gross_profit_yoy_pct",
    domain=DOMAIN_GROWTH,
    depends_on=[
        ("ANNUAL_LATEST", "income", Key.income.GROSS_PROFIT),
        ("ANNUAL_PREV", "income", Key.income.GROSS_PROFIT),
    ]
)
def calc_gp_yoy(cur: float, prev: float) -> Optional[float]:
    """毛利 YoY 增长率 (小数形式，0.35 = 35%)"""
    return round((cur - prev) / abs(prev), 4) if abs(prev) > 0 else None


# ==========================================
# 趋势变化 (Trend Delta) — 百分点 delta
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="gross_margin_delta",
    domain=DOMAIN_TREND,
    depends_on=[
        ("ANNUAL_LATEST", "income", Key.income.GROSS_PROFIT),
        ("ANNUAL_LATEST", "income", Key.income.TOTAL_REVENUE),
        ("ANNUAL_PREV", "income", Key.income.GROSS_PROFIT),
        ("ANNUAL_PREV", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_gm_delta(gp_cur: float, rev_cur: float, gp_prev: float, rev_prev: float) -> Optional[float]:
    """毛利率变化（小数形式，0.02 = 2个百分点）"""
    if rev_cur == 0 or rev_prev == 0:
        return None
    return round(gp_cur / rev_cur - gp_prev / rev_prev, 4)


@MetricEngine.fundamental_metric(
    feature_name="net_margin_delta",
    domain=DOMAIN_TREND,
    depends_on=[
        ("ANNUAL_LATEST", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
        ("ANNUAL_LATEST", "income", Key.income.TOTAL_REVENUE),
        ("ANNUAL_PREV", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
        ("ANNUAL_PREV", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_nm_delta(ni_cur: float, rev_cur: float, ni_prev: float, rev_prev: float) -> Optional[float]:
    """净利率变化（小数形式，0.02 = 2个百分点）"""
    if rev_cur == 0 or rev_prev == 0:
        return None
    return round(ni_cur / rev_cur - ni_prev / rev_prev, 4)


@MetricEngine.fundamental_metric(
    feature_name="roe_delta",
    domain=DOMAIN_TREND,
    depends_on=[
        ("ANNUAL_LATEST", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
        ("ANNUAL_LATEST", "balance", Key.balance.TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT),
        ("ANNUAL_PREV", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
        ("ANNUAL_PREV", "balance", Key.balance.TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT),
    ]
)
def calc_roe_delta(ni_cur: float, eq_cur: float, ni_prev: float, eq_prev: float) -> Optional[float]:
    """ROE 变化（小数形式，0.02 = 2个百分点）"""
    if eq_cur == 0 or eq_prev == 0:
        return None
    return round(ni_cur / eq_cur - ni_prev / eq_prev, 4)

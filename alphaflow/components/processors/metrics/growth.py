"""
增长趋势 (Growth & Trend Delta) — 死磕 TTM 前瞻性口径

V3 架构升级：绝对时间一致性
- 废弃一切跨时空的 Annual 降级
- 只有严格满足 TTM 时间窗的数据才会被纳入计算
- 有就有，没有就 None，宁缺毋滥 (Absolute Coherence)
"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key

DOMAIN_GROWTH = "growth_ttm"
DOMAIN_TREND = "trend_delta_ttm"

# ==========================================
# 辅助函数
# ==========================================

def _yoy_pct(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    """标准 YoY 计算：(cur - prev) / |prev|，返回小数形式"""
    if cur is not None and prev is not None and abs(prev) > 0:
        return round((cur - prev) / abs(prev), 4)
    return None

def _margin_delta(
    num_cur: Optional[float], den_cur: Optional[float],
    num_prev: Optional[float], den_prev: Optional[float],
) -> Optional[float]:
    """标准利润率 Delta：(num_cur/den_cur) - (num_prev/den_prev)"""
    if all(v is not None for v in [num_cur, den_cur, num_prev, den_prev]):
        if den_cur and den_prev:
            return round(num_cur / den_cur - num_prev / den_prev, 4)  # type: ignore[operator]
    return None

# ==========================================
# YoY 增长率 (Growth) — 纯 TTM
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="revenue_yoy_pct",
    domain=DOMAIN_GROWTH,
    depends_on=[
        ("TTM", "income", Key.income.TOTAL_REVENUE),
        ("TTM_PREV", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_revenue_yoy(ttm_cur, ttm_prev) -> Optional[float]:
    """营收 YoY"""
    return _yoy_pct(ttm_cur, ttm_prev)

@MetricEngine.fundamental_metric(
    feature_name="net_income_yoy_pct",
    domain=DOMAIN_GROWTH,
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
        ("TTM_PREV", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
    ]
)
def calc_ni_yoy(ttm_cur, ttm_prev) -> Optional[float]:
    """归母净利 YoY"""
    return _yoy_pct(ttm_cur, ttm_prev)

@MetricEngine.fundamental_metric(
    feature_name="gross_profit_yoy_pct",
    domain=DOMAIN_GROWTH,
    depends_on=[
        ("TTM", "income", Key.income.GROSS_PROFIT),
        ("TTM_PREV", "income", Key.income.GROSS_PROFIT),
    ]
)
def calc_gp_yoy(ttm_cur, ttm_prev) -> Optional[float]:
    """毛利 YoY"""
    return _yoy_pct(ttm_cur, ttm_prev)

@MetricEngine.fundamental_metric(
    feature_name="operating_income_yoy_pct",
    domain=DOMAIN_GROWTH,
    depends_on=[
        ("TTM", "income", Key.income.OPERATING_INCOME),
        ("TTM_PREV", "income", Key.income.OPERATING_INCOME),
    ]
)
def calc_oi_yoy(ttm_cur, ttm_prev) -> Optional[float]:
    """核心营业利润 YoY"""
    return _yoy_pct(ttm_cur, ttm_prev)

@MetricEngine.fundamental_metric(
    feature_name="operating_cashflow_yoy_pct",
    domain=DOMAIN_GROWTH,
    depends_on=[
        ("TTM", "cash", Key.cash.OPERATING_CASH_FLOW),
        ("TTM_PREV", "cash", Key.cash.OPERATING_CASH_FLOW),
    ]
)
def calc_ocf_yoy(ttm_cur, ttm_prev) -> Optional[float]:
    """经营现金流 YoY"""
    return _yoy_pct(ttm_cur, ttm_prev)

# ==========================================
# 趋势变化 (Trend Delta) — 纯 TTM
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="gross_margin_delta",
    domain=DOMAIN_TREND,
    depends_on=[
        ("TTM", "income", Key.income.GROSS_PROFIT),
        ("TTM", "income", Key.income.TOTAL_REVENUE),
        ("TTM_PREV", "income", Key.income.GROSS_PROFIT),
        ("TTM_PREV", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_gm_delta(gp_t, rev_t, gp_tp, rev_tp) -> Optional[float]:
    """毛利率变化"""
    return _margin_delta(gp_t, rev_t, gp_tp, rev_tp)

@MetricEngine.fundamental_metric(
    feature_name="net_margin_delta",
    domain=DOMAIN_TREND,
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
        ("TTM", "income", Key.income.TOTAL_REVENUE),
        ("TTM_PREV", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
        ("TTM_PREV", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_nm_delta(ni_t, rev_t, ni_tp, rev_tp) -> Optional[float]:
    """净利率变化"""
    return _margin_delta(ni_t, rev_t, ni_tp, rev_tp)

@MetricEngine.fundamental_metric(
    feature_name="roe_delta",
    domain=DOMAIN_TREND,
    depends_on=[
        # 流量(TTM净利) / 存量(LATEST权益) vs 流量(TTM_PREV净利) / 存量(ANNUAL_PREV权益)
        ("TTM", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT),
        ("TTM_PREV", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
        ("ANNUAL_PREV", "balance", Key.balance.TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT),
    ]
)
def calc_roe_delta(ni_t, eq_cur, ni_tp, eq_prev) -> Optional[float]:
    """ROE变化 — 流量与存量时间对齐完全合规"""
    if all(v is not None for v in [ni_t, eq_cur, ni_tp, eq_prev]) and eq_cur and eq_prev:
        return round(ni_t / eq_cur - ni_tp / eq_prev, 4)  # type: ignore[operator]
    return None

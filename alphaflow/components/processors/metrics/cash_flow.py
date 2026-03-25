"""
现金流护城河领域 (Cash Flow Moat Domain)
==========================================
FCF 类指标的双轨实现：
- TTM 版本：美股可算（年报有 CapEx 明细），港股视数据可用性
- H1 Semiannual Proxy 版本：港股年报缺 CapEx 时的降级补位
  分子分母全部来自同一半年报期，确保比率含义自洽

命名约定：
- xxx_ttm → TTM 口径（标准 12 个月滚动）
- xxx_h1_semiannual_proxy → 最新半年报口径（6 个月窗口）
"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key

DOMAIN_CASHFLOW = "cashflow_quality_ttm"
DOMAIN_CASHFLOW_H1 = "cashflow_h1_semiannual_proxy"


# ==========================================
# TTM 版本（美股优先、港股视数据可用性）
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="fcf_margin_ttm",
    domain=DOMAIN_CASHFLOW,
    depends_on=[
        ("TTM", "cash", Key.cash.OPERATING_CASH_FLOW),
        ("TTM", "cash", Key.cash.CAPITAL_EXPENDITURE),
        ("TTM", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_fcf_margin_ttm(ocf: float, capex: float, rev: float) -> Optional[float]:
    """(OCF - |CapEx|) / Revenue — 真金白银落袋率（TTM 口径）"""
    if not rev:
        return None
    fcf = ocf - abs(capex)
    return round(fcf / rev, 4)


@MetricEngine.fundamental_metric(
    feature_name="fcf_to_net_income_ttm",
    domain=DOMAIN_CASHFLOW,
    depends_on=[
        ("TTM", "cash", Key.cash.OPERATING_CASH_FLOW),
        ("TTM", "cash", Key.cash.CAPITAL_EXPENDITURE),
        ("TTM", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
    ]
)
def calc_fcf_to_ni_ttm(ocf: float, capex: float, ni: float) -> Optional[float]:
    """(OCF - |CapEx|) / Net Income — FCF 覆盖利润的质量检验（TTM 口径）"""
    if not ni:
        return None
    fcf = ocf - abs(capex)
    return round(fcf / ni, 4)


# ==========================================
# H1 Semiannual Proxy 版本
# 所有分子分母锁定同一半年报 PERIOD_ENDING
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="fcf_margin_h1_semiannual_proxy",
    domain=DOMAIN_CASHFLOW_H1,
    depends_on=[
        ("SEMIANNUAL_LATEST", "cash", Key.cash.OPERATING_CASH_FLOW),
        ("SEMIANNUAL_LATEST", "cash", Key.cash.CAPITAL_EXPENDITURE),
        ("SEMIANNUAL_LATEST", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_fcf_margin_h1(ocf: float, capex: float, rev: float) -> Optional[float]:
    """(OCF_H1 - |CapEx_H1|) / Revenue_H1 — 半年报口径 FCF 利润率"""
    if not rev:
        return None
    fcf = ocf - abs(capex)
    return round(fcf / rev, 4)


@MetricEngine.fundamental_metric(
    feature_name="fcf_to_net_income_h1_semiannual_proxy",
    domain=DOMAIN_CASHFLOW_H1,
    depends_on=[
        ("SEMIANNUAL_LATEST", "cash", Key.cash.OPERATING_CASH_FLOW),
        ("SEMIANNUAL_LATEST", "cash", Key.cash.CAPITAL_EXPENDITURE),
        ("SEMIANNUAL_LATEST", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
    ]
)
def calc_fcf_to_ni_h1(ocf: float, capex: float, ni: float) -> Optional[float]:
    """(OCF_H1 - |CapEx_H1|) / NI_H1 — 半年报口径 FCF 利润覆盖"""
    if not ni:
        return None
    fcf = ocf - abs(capex)
    return round(fcf / ni, 4)


# ==========================================
# 现有指标的 H1 降级版
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="capex_to_revenue_h1_semiannual_proxy",
    domain=DOMAIN_CASHFLOW_H1,
    depends_on=[
        ("SEMIANNUAL_LATEST", "cash", Key.cash.CAPITAL_EXPENDITURE),
        ("SEMIANNUAL_LATEST", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_capex_to_rev_h1(capex: float, rev: float) -> Optional[float]:
    """|CapEx_H1| / Revenue_H1 — 半年报口径资本密集度"""
    if not rev:
        return None
    return round(abs(capex) / rev, 4)


@MetricEngine.fundamental_metric(
    feature_name="fcf_yield_h1_semiannual_proxy",
    domain=DOMAIN_CASHFLOW_H1,
    depends_on=[
        ("SEMIANNUAL_LATEST", "cash", Key.cash.OPERATING_CASH_FLOW),
        ("SEMIANNUAL_LATEST", "cash", Key.cash.CAPITAL_EXPENDITURE),
        ("LATEST", "metrics", Key.metrics.MARKET_CAP_ALIGNED),
    ]
)
def calc_fcf_yield_h1(ocf: float, capex: float, mcap: float) -> Optional[float]:
    """(OCF_H1 - |CapEx_H1|) / Market Cap — 半年报口径 FCF 收益率
    注：Market Cap 为实时值，与半年报混搭在金融上合理（类似 trailing yield）"""
    if not mcap or mcap <= 0:
        return None
    fcf = ocf - abs(capex)
    return round(fcf / mcap, 4)

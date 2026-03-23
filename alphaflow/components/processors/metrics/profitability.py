"""盈利能力 (Profitability) — TTM 口径"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key

DOMAIN = "profitability_ttm"


@MetricEngine.fundamental_metric(
    feature_name="ROE",
    domain=DOMAIN,
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT)
    ]
)
def calc_roe_ttm(ni_attr: float, equity_attr: float) -> Optional[float]:
    """归母净利润(TTM) / 归母权益 — 二级市场股东回报"""
    return round(ni_attr / equity_attr, 4) if equity_attr != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="ROA",
    domain=DOMAIN,
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
        ("LATEST", "balance", Key.balance.TOTAL_ASSETS)
    ]
)
def calc_roa_ttm(ni_incl_nci: float, assets: float) -> Optional[float]:
    """含NCI净利润(TTM) / 总资产 — 资产造血能力"""
    return round(ni_incl_nci / assets, 4) if assets != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="gross_margin",
    domain=DOMAIN,
    depends_on=[
        ("TTM", "income", Key.income.GROSS_PROFIT),
        ("TTM", "income", Key.income.TOTAL_REVENUE)
    ]
)
def calc_gross_margin_ttm(gp: float, rev: float) -> Optional[float]:
    """毛利(TTM) / 营收(TTM)"""
    return round(gp / rev, 4) if rev != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="net_margin",
    domain=DOMAIN,
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
        ("TTM", "income", Key.income.TOTAL_REVENUE)
    ]
)
def calc_net_margin_ttm(ni_incl_nci: float, rev: float) -> Optional[float]:
    """含NCI净利润(TTM) / 营收(TTM) — 100%并表口径一致"""
    return round(ni_incl_nci / rev, 4) if rev != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="op_margin",
    domain=DOMAIN,
    depends_on=[
        ("TTM", "income", Key.income.OPERATING_INCOME),
        ("TTM", "income", Key.income.TOTAL_REVENUE)
    ]
)
def calc_op_margin_ttm(oi: float, rev: float) -> Optional[float]:
    """营业利润(TTM) / 营收(TTM)"""
    return round(oi / rev, 4) if rev != 0 else None


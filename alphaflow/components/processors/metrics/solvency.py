"""偿债能力 (Solvency) — 最新快照"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key

DOMAIN = "solvency_latest"


@MetricEngine.fundamental_metric(
    feature_name="current_ratio",
    domain=DOMAIN,
    depends_on=[
        ("LATEST", "balance", Key.balance.TOTAL_CURRENT_ASSETS),
        ("LATEST", "balance", Key.balance.TOTAL_CURRENT_LIABILITIES)
    ]
)
def calc_current_ratio(ca: float, cl: float) -> Optional[float]:
    """流动资产 / 流动负债"""
    return round(ca / cl, 2) if cl != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="quick_ratio",
    domain=DOMAIN,
    depends_on=[
        ("LATEST", "balance", Key.balance.TOTAL_CURRENT_ASSETS),
        ("LATEST", "balance", Key.balance.INVENTORIES),
        ("LATEST", "balance", Key.balance.TOTAL_CURRENT_LIABILITIES)
    ]
)
def calc_quick_ratio(ca: float, inv: float, cl: float) -> Optional[float]:
    """(流动资产 - 存货) / 流动负债"""
    return round((ca - inv) / cl, 2) if cl != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="debt_to_equity",
    domain=DOMAIN,
    depends_on=[
        ("LATEST", "balance", Key.balance.TOTAL_LIABILITIES),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_CONSOLIDATED)
    ]
)
def calc_debt_to_equity(liab: float, equity: float) -> Optional[float]:
    """总负债 / 综合总权益 — NCI也是安全垫"""
    return round(liab / equity, 4) if equity != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="interest_coverage_ratio",
    domain=DOMAIN,
    depends_on=[
        ("TTM", "income", Key.income.OPERATING_INCOME),
        ("TTM", "income", Key.income.INTEREST_EXPENSE),
    ]
)
def calc_interest_coverage(op_income: float, interest_exp: float) -> Optional[float]:
    """营业利润 / |利息支出| — 利息保障倍数，越高越安全"""
    ie = abs(interest_exp)
    return round(op_income / ie, 2) if ie > 0 else None

"""运营效率 (Efficiency) — TTM 周转率指标"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key

DOMAIN_EFFICIENCY = "efficiency_ttm"


@MetricEngine.fundamental_metric(
    feature_name="asset_turnover",
    domain=DOMAIN_EFFICIENCY,
    depends_on=[
        ("TTM", "income", Key.income.TOTAL_REVENUE),
        ("LATEST", "balance", Key.balance.TOTAL_ASSETS)
    ]
)
def calc_asset_turnover(rev: float, assets: float) -> Optional[float]:
    """营收(TTM) / 总资产"""
    return round(rev / assets, 4) if assets != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="equity_turnover",
    domain=DOMAIN_EFFICIENCY,
    depends_on=[
        ("TTM", "income", Key.income.TOTAL_REVENUE),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_CONSOLIDATED)
    ]
)
def calc_equity_turnover(rev: float, equity: float) -> Optional[float]:
    """营收(TTM) / 综合权益"""
    return round(rev / equity, 4) if equity != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="working_capital_turnover_ttm",
    domain=DOMAIN_EFFICIENCY,
    depends_on=[
        ("TTM", "income", Key.income.TOTAL_REVENUE),
        ("LATEST", "balance", Key.balance.NET_WORKING_CAPITAL)
    ]
)
def calc_wc_turnover(rev: float, nwc: float) -> Optional[float]:
    """营收(TTM) / 净营运资金 — 运用存量资金的效率，越大越好（NWC ≤ 0 无意义，返回 None）"""
    if nwc is None or nwc <= 0:
        return None
    return round(rev / nwc, 4) if rev else None

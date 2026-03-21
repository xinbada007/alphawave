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

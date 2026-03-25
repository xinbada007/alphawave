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
    feature_name="quick_ratio_standard",
    domain=DOMAIN,
    depends_on=[
        ("LATEST", "balance", Key.balance.TOTAL_CURRENT_ASSETS),
        ("LATEST", "balance", Key.balance.INVENTORIES),
        ("LATEST", "balance", Key.balance.TOTAL_CURRENT_LIABILITIES)
    ]
)
def calc_quick_ratio_standard(ca: float, inv: float, cl: float) -> Optional[float]:
    """(流动资产 - 存货) / 流动负债 — 标准会计学速动比率"""
    ca_val = ca if ca else 0.0
    inv_val = inv if inv else 0.0
    return round((ca_val - inv_val) / cl, 2) if cl != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="cash_coverage_ratio",
    domain=DOMAIN,
    depends_on=[
        ("LATEST", "balance", Key.balance.CASH_AND_CASH_EQUIVALENTS),
        ("LATEST", "balance", Key.balance.RESTRICTED_CASH),
        ("LATEST", "balance", Key.balance.SHORT_TERM_DEPOSITS),
        ("LATEST", "balance", Key.balance.FINANCIAL_ASSETS_AT_FAIR_VALUE_CURRENT),
        ("LATEST", "balance", Key.balance.SHORT_TERM_INVESTMENTS),
        ("LATEST", "balance", Key.balance.TOTAL_CURRENT_LIABILITIES)
    ]
)
def calc_cash_coverage_ratio(cash: float, restr_cash: float, st_deposits: float, fv_fin_assets: Optional[float], st_investments: Optional[float], cl: float) -> Optional[float]:
    """(现金 + 受限制存款及现金 + 短期定期存款 + 公允价值计量金融资产 + 短期投资) / 流动负债 — YF 严苛口径 (已修复准现金遗漏)"""
    c = cash if cash else 0.0
    rc = restr_cash if restr_cash else 0.0
    sd = st_deposits if st_deposits else 0.0
    fv = fv_fin_assets if fv_fin_assets else 0.0
    sti = st_investments if st_investments else 0.0
    strict_assets = c + rc + sd + fv + sti
    return round(strict_assets / cl, 4) if cl != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="debt_to_equity",
    domain=DOMAIN,
    depends_on=[
        ("LATEST", "balance", Key.balance.SHORT_TERM_DEBT),
        ("LATEST", "balance", Key.balance.LONG_TERM_DEBT),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_CONSOLIDATED)
    ]
)
def calc_debt_to_equity(st_debt: float, lt_debt: float, equity: float) -> Optional[float]:
    """(短期贷款 + 长期贷款) / 综合总权益 — 标准带息负债率"""
    st = st_debt if st_debt else 0.0
    lt = lt_debt if lt_debt else 0.0
    total_debt = st + lt
    return round(total_debt / equity, 4) if equity != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="debt_to_equity_incl_leases",
    domain=DOMAIN,
    depends_on=[
        ("LATEST", "balance", Key.balance.SHORT_TERM_DEBT),
        ("LATEST", "balance", Key.balance.LONG_TERM_DEBT),
        ("LATEST", "balance", Key.balance.NOTES_PAYABLE),
        ("LATEST", "balance", Key.balance.NOTES_PAYABLE_NON_CURRENT),
        ("LATEST", "balance", Key.balance.CAPITAL_LEASE_OBLIGATIONS_CURRENT),
        ("LATEST", "balance", Key.balance.CAPITAL_LEASE_OBLIGATIONS_NON_CURRENT),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_CONSOLIDATED)
    ]
)
def calc_debt_to_equity_incl_leases(st: Optional[float], lt: Optional[float], np_c: Optional[float], np_nc: Optional[float], lease_c: Optional[float], lease_nc: Optional[float], equity: Optional[float]) -> Optional[float]:
    """(长短贷款 + 长短应付票据 + 长短租赁负债) / 总权益 — 严格泛带息负债口径 (对应 YF 算法)"""
    v_st = st if st else 0.0
    v_lt = lt if lt else 0.0
    v_np_c = np_c if np_c else 0.0
    v_np_nc = np_nc if np_nc else 0.0
    v_lc = lease_c if lease_c else 0.0
    v_lnc = lease_nc if lease_nc else 0.0
    total_strict_debt = v_st + v_lt + v_np_c + v_np_nc + v_lc + v_lnc
    return round(total_strict_debt / equity, 4) if equity and equity != 0 else None


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

"""盈利能力 (Profitability) — TTM 口径"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key

DOMAIN = "profitability_ttm"


@MetricEngine.fundamental_metric(
    feature_name="roe_latest_equity",
    domain=DOMAIN,
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT)
    ]
)
def calc_roe_latest(ni_attr: float, equity_attr: float) -> Optional[float]:
    """归母净利润(TTM) / 最新归母权益 — 看板与量化速筛口径"""
    return round(ni_attr / equity_attr, 4) if equity_attr != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="roe_average_equity",
    domain=DOMAIN,
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
        ("AVERAGE_1Y", "balance", Key.balance.TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT)
    ]
)
def calc_roe_average(ni_attr: float, avg_equity_attr: float) -> Optional[float]:
    """归母净利润(TTM) / 近一年平均归母权益 — 杜邦分析与 YF 标准口径"""
    return round(ni_attr / avg_equity_attr, 4) if avg_equity_attr != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="roa_latest_assets",
    domain=DOMAIN,
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
        ("LATEST", "balance", Key.balance.TOTAL_ASSETS)
    ]
)
def calc_roa_latest(ni_incl_nci: float, assets: float) -> Optional[float]:
    """含NCI净利润(TTM) / 最新总资产 — 速筛口径"""
    return round(ni_incl_nci / assets, 4) if assets != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="roa_average_assets",
    domain=DOMAIN,
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
        ("AVERAGE_1Y", "balance", Key.balance.TOTAL_ASSETS)
    ]
)
def calc_roa_average(ni_incl_nci: float, avg_assets: float) -> Optional[float]:
    """含NCI净利润(TTM) / 近一年平均总资产 — YF 标准口径"""
    return round(ni_incl_nci / avg_assets, 4) if avg_assets != 0 else None


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
    feature_name="op_margin_statutory",
    domain=DOMAIN,
    depends_on=[
        ("TTM", "income", Key.income.OPERATING_INCOME),
        ("TTM", "income", Key.income.TOTAL_REVENUE)
    ]
)
def calc_op_margin_ttm(oi: float, rev: float) -> Optional[float]:
    """法定营业利润(TTM) / 营收(TTM) — 包含补贴等 IFRS 原生科目，不针对美股 Non-GAAP 剔除"""
    return round(oi / rev, 4) if rev != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="roic_ttm",
    domain=DOMAIN,
    depends_on=[
        # NOPAT 分子
        ("TTM", "income", Key.income.OPERATING_INCOME),
        ("TTM", "income", Key.income.TAX_PROVISION),
        ("TTM", "income", Key.income.PRETAX_INCOME),
        # Invested Capital 分母 — 全口径有息负债 + 权益 - 现金
        ("LATEST", "balance", Key.balance.SHORT_TERM_DEBT),
        ("LATEST", "balance", Key.balance.LONG_TERM_DEBT),
        # NOTE: BONDS_PAYABLE 未列入 depends_on，因为 MetricEngine 视所有依赖为强制，
        # 而港股/美股的 BONDS_PAYABLE 永远为 None（债券已含在 LONG_TERM_DEBT 里）。
        # 待 A 股支撑上线后，需配合 Engine 可选依赖机制一并补回。
        ("LATEST", "balance", Key.balance.NOTES_PAYABLE),
        ("LATEST", "balance", Key.balance.NOTES_PAYABLE_NON_CURRENT),
        ("LATEST", "balance", Key.balance.CAPITAL_LEASE_OBLIGATIONS_CURRENT),
        ("LATEST", "balance", Key.balance.CAPITAL_LEASE_OBLIGATIONS_NON_CURRENT),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_CONSOLIDATED),
        ("LATEST", "balance", Key.balance.CASH_AND_CASH_EQUIVALENTS),
    ]
)
def calc_roic(
    oi: float, tax: float, pretax: float,
    st_debt: Optional[float], lt_debt: Optional[float],
    np_c: Optional[float], np_nc: Optional[float],
    lease_c: Optional[float], lease_nc: Optional[float],
    equity: Optional[float], cash: Optional[float]
) -> Optional[float]:
    """NOPAT / Invested Capital — 巴菲特最看重的单一指标，剥离杠杆幻觉"""
    if not oi or not equity:
        return None
    # 有效税率（税前利润 ≤ 0 时税率置 0）
    eff_tax = (tax / pretax) if pretax and pretax > 0 else 0.0
    nopat = oi * (1 - eff_tax)
    # Invested Capital = Total Debt + Equity - Cash
    total_debt = sum(v or 0.0 for v in [st_debt, lt_debt, np_c, np_nc, lease_c, lease_nc])
    ic = total_debt + (equity or 0.0) - (cash or 0.0)
    return round(nopat / ic, 4) if ic > 0 else None


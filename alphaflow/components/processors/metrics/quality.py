"""现金流质量 + 盈余质量 + 费用结构 + 资产结构"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key

DOMAIN_CASHFLOW = "cashflow_quality_ttm"
DOMAIN_INCOME_STRUCTURE = "income_structure_latest"
DOMAIN_BALANCE_STRUCTURE = "balance_structure_latest"
DOMAIN_EARNINGS_QUALITY = "earnings_quality_latest"


# ==========================================
# 现金流质量 (Cash Flow Quality) — TTM
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="ocf_to_net_income",
    domain=DOMAIN_CASHFLOW,
    depends_on=[
        ("TTM", "cash", Key.cash.OPERATING_CASH_FLOW),
        ("TTM", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
    ]
)
def calc_ocf_to_ni(ocf: float, ni: float) -> Optional[float]:
    """经营现金流(TTM) / 净利润(TTM) — 收现比，>1.0 为优"""
    return round(ocf / ni, 4) if ni != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="capex_to_revenue",
    domain=DOMAIN_CASHFLOW,
    depends_on=[
        ("TTM", "cash", Key.cash.CAPITAL_EXPENDITURE),
        ("TTM", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_capex_to_rev(capex: float, rev: float) -> Optional[float]:
    """abs(CAPEX)(TTM) / 营收(TTM) — CAPEX 强度"""
    return round(abs(capex) / rev, 4) if rev != 0 else None


# ==========================================
# 费用结构 (Income Structure) — 最新快照
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="rd_expense_ratio",
    domain=DOMAIN_INCOME_STRUCTURE,
    depends_on=[
        ("LATEST", "income", Key.income.RESEARCH_AND_DEVELOPMENT_EXPENSE),
        ("LATEST", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_rd_ratio(rd: float, rev: float) -> Optional[float]:
    """研发费用 / 营收 — 研发强度"""
    return round(rd / rev, 4) if rev != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="interest_burden_ratio",
    domain=DOMAIN_INCOME_STRUCTURE,
    depends_on=[
        ("LATEST", "income", Key.income.INTEREST_EXPENSE),
        ("LATEST", "income", Key.income.TOTAL_REVENUE),
    ]
)
def calc_interest_burden(interest: float, rev: float) -> Optional[float]:
    """利息支出 / 营收 — 利息负担"""
    return round(abs(interest) / rev, 4) if rev != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="effective_tax_rate",
    domain=DOMAIN_INCOME_STRUCTURE,
    depends_on=[
        ("LATEST", "income", Key.income.TAX_PROVISION),
        ("LATEST", "income", Key.income.PRETAX_INCOME),
    ]
)
def calc_effective_tax_rate(tax: float, pretax: float) -> Optional[float]:
    """所得税 / 税前利润 — 实际税率"""
    return round(tax / pretax, 4) if pretax != 0 else None


# ==========================================
# 资产结构 (Balance Structure) — 最新快照
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="equity_multiplier",
    domain=DOMAIN_BALANCE_STRUCTURE,
    depends_on=[
        ("LATEST", "balance", Key.balance.TOTAL_ASSETS),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT),
    ]
)
def calc_equity_multiplier(assets: float, equity: float) -> Optional[float]:
    """总资产 / 归母权益 — 杜邦权益乘数"""
    return round(assets / equity, 4) if equity != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="net_debt_to_equity",
    domain=DOMAIN_BALANCE_STRUCTURE,
    depends_on=[
        ("LATEST", "balance", Key.balance.SHORT_TERM_DEBT),
        ("LATEST", "balance", Key.balance.LONG_TERM_DEBT),
        ("LATEST", "balance", Key.balance.CASH_AND_CASH_EQUIVALENTS),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT),
    ]
)
def calc_net_debt_to_equity(st_debt: float, lt_debt: float, cash: float, equity: float) -> Optional[float]:
    """(短期负债 + 长期负债 - 现金) / 归母权益 — 净负债率"""
    net_debt = st_debt + lt_debt - cash
    return round(net_debt / equity, 4) if equity != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="cash_to_total_assets",
    domain=DOMAIN_BALANCE_STRUCTURE,
    depends_on=[
        ("LATEST", "balance", Key.balance.CASH_AND_CASH_EQUIVALENTS),
        ("LATEST", "balance", Key.balance.TOTAL_ASSETS),
    ]
)
def calc_cash_to_assets(cash: float, assets: float) -> Optional[float]:
    """现金 / 总资产 — 现金充裕度"""
    return round(cash / assets, 4) if assets != 0 else None


# ==========================================
# 盈余质量 (Earnings Quality) — 最新快照
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="core_profit_ratio",
    domain=DOMAIN_EARNINGS_QUALITY,
    depends_on=[
        ("LATEST", "income", Key.income.OPERATING_INCOME),
        ("LATEST", "income", Key.income.PRETAX_INCOME),
    ]
)
def calc_core_profit_ratio(oi: float, pretax: float) -> Optional[float]:
    """营业利润 / 税前利润 — 核心利润占比，越接近1越健康"""
    return round(oi / pretax, 4) if pretax != 0 else None


# ==========================================
# 现金派息率 — 年报口径
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="dividend_payout_ratio",
    domain=DOMAIN_CASHFLOW,
    depends_on=[
        ("ANNUAL_LATEST", "cash", Key.cash.CASH_DIVIDENDS_PAID),
        ("ANNUAL_LATEST", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
    ]
)
def calc_dividend_payout(div_paid: float, ni: float) -> Optional[float]:
    """现金股息 / 归母净利 — 真实分红意愿（年报口径，abs 防 YFinance 负值）"""
    return round(abs(div_paid) / ni, 4) if ni > 0 else None


# ==========================================
# Novy-Marx 毛利资产比 (GPA)
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="gross_profit_to_assets",
    domain=DOMAIN_EARNINGS_QUALITY,
    depends_on=[
        ("TTM", "income", Key.income.GROSS_PROFIT),
        ("LATEST", "balance", Key.balance.TOTAL_ASSETS),
    ]
)
def calc_gpa(gp: float, ta: float) -> Optional[float]:
    """毛利(TTM) / 总资产 — Novy-Marx 质量因子，比 ROA 更纯净"""
    return round(gp / ta, 4) if ta > 0 else None

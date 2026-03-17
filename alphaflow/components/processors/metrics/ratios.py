"""
纯净财务比率算子 (Pure Financial Ratio Operators)
====================================================
V4 架构：语义域分桶 (Semantic Domain Bucketing)

每个指标声明：
  - feature_name: 域内短名（去掉冗余的 _TTM 后缀，由域名承担口径说明）
  - domain: 语义域（后缀 _ttm = 滚动12月口径，_latest = 最新快照）
  - depends_on: 计算依赖三元组

域命名规范：
  profitability_ttm   — 盈利能力（TTM口径）
  solvency_latest     — 偿债能力（最新快照）
  efficiency_ttm      — 运营效率（TTM口径）
  analyst_consensus   — 分析师共识（实时数据源）
"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key


# ==========================================
# 盈利能力 (Profitability) — TTM 口径
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="ROE",
    domain="profitability_ttm",
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
    domain="profitability_ttm",
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
    domain="profitability_ttm",
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
    domain="profitability_ttm",
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
    domain="profitability_ttm",
    depends_on=[
        ("TTM", "income", Key.income.OPERATING_INCOME),
        ("TTM", "income", Key.income.TOTAL_REVENUE)
    ]
)
def calc_op_margin_ttm(oi: float, rev: float) -> Optional[float]:
    """营业利润(TTM) / 营收(TTM)"""
    return round(oi / rev, 4) if rev != 0 else None


# ==========================================
# 偿债能力 (Solvency) — 最新快照
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="current_ratio",
    domain="solvency_latest",
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
    domain="solvency_latest",
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
    domain="solvency_latest",
    depends_on=[
        ("LATEST", "balance", Key.balance.TOTAL_LIABILITIES),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_CONSOLIDATED)
    ]
)
def calc_debt_to_equity(liab: float, equity: float) -> Optional[float]:
    """总负债 / 综合总权益 — NCI也是安全垫"""
    return round(liab / equity, 4) if equity != 0 else None


# ==========================================
# 运营效率 (Efficiency) — TTM 口径
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="asset_turnover",
    domain="efficiency_ttm",
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
    domain="efficiency_ttm",
    depends_on=[
        ("TTM", "income", Key.income.TOTAL_REVENUE),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_CONSOLIDATED)
    ]
)
def calc_equity_turnover(rev: float, equity: float) -> Optional[float]:
    """营收(TTM) / 综合权益"""
    return round(rev / equity, 4) if equity != 0 else None


# ==========================================
# 分析师共识 (Analyst Consensus)
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="target_spread",
    domain="analyst_consensus",
    depends_on=[
        ("LATEST", "estimates", Key.estimates.TARGET_HIGH),
        ("LATEST", "estimates", Key.estimates.TARGET_LOW),
        ("LATEST", "estimates", Key.estimates.TARGET_PRICE)
    ]
)
def calc_target_spread(high: float, low: float, consensus: float) -> Optional[float]:
    """(最高目标价 - 最低目标价) / 共识均价 — 分歧度"""
    return round((high - low) / consensus, 4) if consensus and consensus > 0 else None


@MetricEngine.fundamental_metric(
    feature_name="upside_potential",
    domain="analyst_consensus",
    depends_on=[
        ("LATEST", "estimates", Key.estimates.TARGET_PRICE),
        ("LATEST", "estimates", Key.estimates.CURRENT_PRICE)
    ]
)
def calc_upside_potential(target: float, current: float) -> Optional[float]:
    """(共识目标价 - 现价) / 现价 — 潜在涨幅"""
    return round((target - current) / current, 4) if current and current > 0 else None

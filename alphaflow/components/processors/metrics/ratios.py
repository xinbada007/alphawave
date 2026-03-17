"""
纯净财务比率算子 (Pure Financial Ratio Operators)
====================================================
V3 架构：极简无状态的指标函数，消灭类爆炸。

所有函数通过 @MetricEngine.fundamental_metric 装饰器注册，
在 Import Time 自动注入 MetricEngine._registry。

更新日志：
- 2026-03-17: 严格采用全称 Key，删除所有缩写别名
              ROE_TTM: 使用 NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS / TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT
              ROA_TTM: 使用 NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS / TOTAL_ASSETS
              Net_Margin_TTM: 使用 NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS / TOTAL_REVENUE
              Op_Margin_TTM: 使用 OPERATING_INCOME / TOTAL_REVENUE
              Current_Ratio: 使用 TOTAL_CURRENT_ASSETS / TOTAL_CURRENT_LIABILITIES
              Debt_to_Equity: 使用 TOTAL_LIABILITIES / TOTAL_EQUITY_CONSOLIDATED
"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key


# ==========================================
# 盈利能力指标 (Profitability)
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="ROE_TTM",
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT)
    ]
)
def calc_roe_ttm(ni_attributable_ttm: float, equity_attributable_latest: float) -> Optional[float]:
    """
    净资产收益率 TTM (Return on Equity)
    公式：归母净利润(TTM) / 最新归母股东权益
    严格对应二级市场股东回报
    """
    return round(ni_attributable_ttm / equity_attributable_latest, 4) if equity_attributable_latest != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="ROA_TTM",
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
        ("LATEST", "balance", Key.balance.TOTAL_ASSETS)
    ]
)
def calc_roa_ttm(ni_including_nci_ttm: float, assets_latest: float) -> Optional[float]:
    """
    总资产收益率 TTM (Return on Assets)
    公式：包含少数股东的净利润(TTM) / 最新总资产
    严格对应资产造血能力
    """
    return round(ni_including_nci_ttm / assets_latest, 4) if assets_latest != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="Gross_Margin_TTM",
    depends_on=[
        ("TTM", "income", Key.income.GROSS_PROFIT),
        ("TTM", "income", Key.income.TOTAL_REVENUE)
    ]
)
def calc_gross_margin_ttm(gp_ttm: float, rev_ttm: float) -> Optional[float]:
    """
    毛利率 TTM (Gross Margin)
    公式：毛利润(TTM) / 营收(TTM)
    """
    return round(gp_ttm / rev_ttm, 4) if rev_ttm != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="Net_Margin_TTM",
    depends_on=[
        ("TTM", "income", Key.income.NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS),
        ("TTM", "income", Key.income.TOTAL_REVENUE)
    ]
)
def calc_net_margin_ttm(ni_including_nci_ttm: float, rev_ttm: float) -> Optional[float]:
    """
    净利率 TTM (Net Margin)
    公式：包含少数股东的净利润(TTM) / 营收(TTM)
    营收是100%并表的，利润也必须用100%并表口径
    """
    return round(ni_including_nci_ttm / rev_ttm, 4) if rev_ttm != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="Op_Margin_TTM",
    depends_on=[
        ("TTM", "income", Key.income.OPERATING_INCOME),
        ("TTM", "income", Key.income.TOTAL_REVENUE)
    ]
)
def calc_op_margin_ttm(oi_ttm: float, rev_ttm: float) -> Optional[float]:
    """
    营业利润率 TTM (Operating Margin)
    公式：营业利润(TTM) / 营收(TTM)
    """
    return round(oi_ttm / rev_ttm, 4) if rev_ttm != 0 else None


# ==========================================
# 偿债能力指标 (Solvency & Liquidity)
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="Current_Ratio",
    depends_on=[
        ("LATEST", "balance", Key.balance.TOTAL_CURRENT_ASSETS),
        ("LATEST", "balance", Key.balance.TOTAL_CURRENT_LIABILITIES)
    ]
)
def calc_current_ratio(ca: float, cl: float) -> Optional[float]:
    """
    流动比率 (Current Ratio)
    公式：流动资产 / 流动负债
    """
    return round(ca / cl, 2) if cl != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="Quick_Ratio",
    depends_on=[
        ("LATEST", "balance", Key.balance.TOTAL_CURRENT_ASSETS),
        ("LATEST", "balance", Key.balance.INVENTORIES),
        ("LATEST", "balance", Key.balance.TOTAL_CURRENT_LIABILITIES)
    ]
)
def calc_quick_ratio(ca: float, inventory: float, cl: float) -> Optional[float]:
    """
    速动比率 (Quick Ratio)
    公式：(流动资产 - 存货) / 流动负债
    """
    return round((ca - inventory) / cl, 2) if cl != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="Debt_to_Equity",
    depends_on=[
        ("LATEST", "balance", Key.balance.TOTAL_LIABILITIES),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_CONSOLIDATED)
    ]
)
def calc_debt_to_equity(liab: float, equity: float) -> Optional[float]:
    """
    负债权益比 (Debt to Equity Ratio)
    公式：总负债 / 综合总权益
    看整体破产风险时，少数股东权益也是安全垫
    """
    return round(liab / equity, 4) if equity != 0 else None


# ==========================================
# 运营效率指标 (Efficiency)
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="Asset_Turnover_TTM",
    depends_on=[
        ("TTM", "income", Key.income.TOTAL_REVENUE),
        ("LATEST", "balance", Key.balance.TOTAL_ASSETS)
    ]
)
def calc_asset_turnover_ttm(rev_ttm: float, assets_latest: float) -> Optional[float]:
    """
    总资产周转率 TTM (Asset Turnover)
    公式：营收(TTM) / 最新总资产
    """
    return round(rev_ttm / assets_latest, 4) if assets_latest != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="Equity_Turnover_TTM",
    depends_on=[
        ("TTM", "income", Key.income.TOTAL_REVENUE),
        ("LATEST", "balance", Key.balance.TOTAL_EQUITY_CONSOLIDATED)
    ]
)
def calc_equity_turnover_ttm(rev_ttm: float, equity_latest: float) -> Optional[float]:
    """
    权益周转率 TTM (Equity Turnover)
    公式：营收(TTM) / 最新综合股东权益
    """
    return round(rev_ttm / equity_latest, 4) if equity_latest != 0 else None


# ==========================================
# 估值指标 (Valuation) - 需要 market_metrics
# ==========================================

# 注意：估值指标通常需要市值数据，这部分可能需要通过其他方式计算
# 因为 market_metrics 不在 fundamentals 中，而是独立字段


# ==========================================
# 分析师共识派生指标 (Consensus)
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="TARGET_SPREAD",
    depends_on=[
        ("LATEST", "estimates", Key.estimates.TARGET_HIGH),
        ("LATEST", "estimates", Key.estimates.TARGET_LOW),
        ("LATEST", "estimates", Key.estimates.TARGET_PRICE)
    ]
)
def calc_target_spread(high: float, low: float, median: float) -> Optional[float]:
    """
    目标价分歧度 (Target Spread)
    公式：(HIGH - LOW) / MEDIAN
    """
    return round((high - low) / median, 4) if median and median > 0 else None


@MetricEngine.fundamental_metric(
    feature_name="UPSIDE_POTENTIAL",
    depends_on=[
        ("LATEST", "estimates", Key.estimates.TARGET_PRICE),
        ("LATEST", "estimates", Key.estimates.CURRENT_PRICE)
    ]
)
def calc_upside_potential(target: float, current: float) -> Optional[float]:
    """
    潜在上涨空间 (Upside Potential)
    公式：(TARGET - CURRENT) / CURRENT
    """
    return round((target - current) / current, 4) if current and current > 0 else None


# ==========================================
# 增长指标 (Growth) - YoY 计算
# ==========================================

# YoY 增长通常需要历史数据比较，可以通过 MetricEngine 扩展支持
# 或者保留在 Extractor 层处理

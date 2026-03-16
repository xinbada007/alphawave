"""
纯净财务比率算子 (Pure Financial Ratio Operators)
====================================================
V3 架构：极简无状态的指标函数，消灭类爆炸。

所有函数通过 @MetricEngine.fundamental_metric 装饰器注册，
在 Import Time 自动注入 MetricEngine._registry。
"""

from typing import Optional
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.core.keys import Key


# ==========================================
# 盈利能力指标 (Profitability)
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="ROE_TTM",
    depends_on=[("TTM", "income", Key.income.NI), ("LATEST", "balance", Key.balance.EQUITY)]
)
def calc_roe_ttm(ni_ttm: float, equity_latest: float) -> Optional[float]:
    """
    净资产收益率 TTM (Return on Equity)
    公式：净利润(TTM) / 最新股东权益
    """
    return round(ni_ttm / equity_latest, 4) if equity_latest != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="ROA_TTM",
    depends_on=[("TTM", "income", Key.income.NI), ("LATEST", "balance", Key.balance.ASSETS)]
)
def calc_roa_ttm(ni_ttm: float, assets_latest: float) -> Optional[float]:
    """
    总资产收益率 TTM (Return on Assets)
    公式：净利润(TTM) / 最新总资产
    """
    return round(ni_ttm / assets_latest, 4) if assets_latest != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="Gross_Margin_TTM",
    depends_on=[("TTM", "income", Key.income.GP), ("TTM", "income", Key.income.REV)]
)
def calc_gross_margin_ttm(gp_ttm: float, rev_ttm: float) -> Optional[float]:
    """
    毛利率 TTM (Gross Margin)
    公式：毛利润(TTM) / 营收(TTM)
    """
    return round(gp_ttm / rev_ttm, 4) if rev_ttm != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="Net_Margin_TTM",
    depends_on=[("TTM", "income", Key.income.NI), ("TTM", "income", Key.income.REV)]
)
def calc_net_margin_ttm(ni_ttm: float, rev_ttm: float) -> Optional[float]:
    """
    净利率 TTM (Net Margin)
    公式：净利润(TTM) / 营收(TTM)
    """
    return round(ni_ttm / rev_ttm, 4) if rev_ttm != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="Op_Margin_TTM",
    depends_on=[("TTM", "income", Key.income.OI), ("TTM", "income", Key.income.REV)]
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
    depends_on=[("LATEST", "balance", Key.balance.C_ASSETS), ("LATEST", "balance", Key.balance.C_LIAB)]
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
        ("LATEST", "balance", Key.balance.C_ASSETS),
        ("LATEST", "balance", Key.balance.INVENTORIES),
        ("LATEST", "balance", Key.balance.C_LIAB)
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
    depends_on=[("LATEST", "balance", Key.balance.LIAB), ("LATEST", "balance", Key.balance.EQUITY)]
)
def calc_debt_to_equity(liab: float, equity: float) -> Optional[float]:
    """
    负债权益比 (Debt to Equity Ratio)
    公式：总负债 / 股东权益
    """
    return round(liab / equity, 4) if equity != 0 else None


# ==========================================
# 运营效率指标 (Efficiency)
# ==========================================

@MetricEngine.fundamental_metric(
    feature_name="Asset_Turnover_TTM",
    depends_on=[("TTM", "income", Key.income.REV), ("LATEST", "balance", Key.balance.ASSETS)]
)
def calc_asset_turnover_ttm(rev_ttm: float, assets_latest: float) -> Optional[float]:
    """
    总资产周转率 TTM (Asset Turnover)
    公式：营收(TTM) / 最新总资产
    """
    return round(rev_ttm / assets_latest, 4) if assets_latest != 0 else None


@MetricEngine.fundamental_metric(
    feature_name="Equity_Turnover_TTM",
    depends_on=[("TTM", "income", Key.income.REV), ("LATEST", "balance", Key.balance.EQUITY)]
)
def calc_equity_turnover_ttm(rev_ttm: float, equity_latest: float) -> Optional[float]:
    """
    权益周转率 TTM (Equity Turnover)
    公式：营收(TTM) / 最新股东权益
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

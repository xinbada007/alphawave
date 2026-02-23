"""
数据工具共享模块
用于 AlphaFlow 组件间的数据定义和公共工具

包含：
- MarketType: 市场类型枚举
- get_market_type(): 根据 symbol 判断市场类型
- FINANCIAL_FIELD_CHAINS: 财务相关字段映射
- MARKET_FIELD_CHAINS: 市场/行情相关字段映射
- 辅助函数：字段提取、日期对齐等
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import pandas as pd
from datetime import datetime

# ==========================================
# 1. 市场类型枚举
# ==========================================

class ReportPeriod(str, Enum):
    """财报周期枚举 - 消除硬编码字符串"""
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"  # 半年报 (H1)
    ANNUAL = "annual"
    LATEST = "latest"  # 通常用于 snapshot 兜底


# ==========================================
# 报表类型映射 (统一数据源)
# ==========================================

# AkShare DATE_TYPE_CODE -> ReportPeriod 映射
_AKSHARE_DATE_TYPE_MAP: Dict[str, ReportPeriod] = {
    "001": ReportPeriod.ANNUAL,
    "002": ReportPeriod.SEMIANNUAL,
    "003": ReportPeriod.QUARTERLY,
    "004": ReportPeriod.QUARTERLY,
}

# OBB report_type -> ReportPeriod 映射
_OBB_REPORT_TYPE_MAP: Dict[str, ReportPeriod] = {
    "annual": ReportPeriod.ANNUAL,
    "quarter": ReportPeriod.QUARTERLY,
}


class MetaKey:
    """系统元数据/日期字段常量"""
    PERIOD_ENDING = "period_ending"  # 清洗后的统一会计期末日
    REPORT_DATE = "REPORT_DATE"      # 原始发布日
    START_DATE = "START_DATE"        # 报告起始日 (用于计算年化)
    DATE_TYPE_CODE = "DATE_TYPE_CODE" # AkShare 报告类型码
    REPORT_TYPE = "report_type"           # OBB 报告类型字段


class MarketType(Enum):
    """市场类型枚举"""
    HK = "hk"      # 港股
    CN = "cn"      # A股 (沪深)
    US = "us"      # 美股
    UNKNOWN = "unknown"


def get_market_type(symbol: str) -> MarketType:
    """
    根据 symbol 判断市场类型
    
    Args:
        symbol: 股票代码，如 "00700.HK", "600519.SH", "AAPL"
    
    Returns:
        MarketType: 市场类型
    """
    if not symbol:
        return MarketType.UNKNOWN
    
    s = symbol.upper().strip()
    
    if s.endswith(".HK"):
        return MarketType.HK
    elif s.endswith((".SH", ".SZ", ".SS")):
        return MarketType.CN
    else:
        # 默认认为是美股
        return MarketType.US


# ==========================================
# 2. 财务字段常量类 (Financial Key)
# ==========================================
class FinKey:
    """
    财务字段常量类 - 替代字符串字面量
    用于替代 FIELD_CHAINS 中的 Key，提供类型安全性和 IDE 自动补全
    """
    
    # ========== 利润表 (Income Statement) ==========
    REV = "REV"
    NI = "NI"
    OI = "OI"
    GP = "GP"
    EBITDA = "EBITDA"
    TAX = "TAX"
    
    # ========== 资产负债表 (Balance Sheet) ==========
    ASSETS = "ASSETS"
    LIAB = "LIAB"
    EQUITY = "EQUITY"
    C_ASSETS = "C_ASSETS"
    C_LIAB = "C_LIAB"
    CASH_AND_EQUIV = "CASH_AND_EQUIV"
    INTANGIBLE = "INTANGIBLE"
    GOODWILL = "GOODWILL"
    
    # ========== 现金流量表 (Cash Flow) ==========
    OCF = "OCF"
    ICF = "ICF"
    FCF = "FCF"
    CAPEX = "CAPEX"
    
    # ========== 效率与回报 (Efficiency & Returns) ==========
    ROE = "ROE"
    ROA = "ROA"
    NET_MARGIN = "NET_MARGIN"
    GROSS_MARGIN = "GROSS_MARGIN"
    
    # ========== 增长率 (Growth Ratios) ==========
    REV_GROWTH_QOQ = "REV_GROWTH_QOQ"
    NI_GROWTH_QOQ = "NI_GROWTH_QOQ"
    REV_GROWTH_YOY = "REV_GROWTH_YOY"
    NI_GROWTH_YOY = "NI_GROWTH_YOY"
    
    # ========== 市场字段 (Market Fields) ==========
    MCAP = "MCAP"
    MCAP_HK = "MCAP_HK"
    PE = "PE"
    PB = "PB"
    PS = "PS"
    PCF = "PCF"
    DIVIDEND_YIELD = "DIVIDEND_YIELD"
    
    # ========== 每股指标 (Per Share Metrics) ==========
    EPS = "EPS"
    BPS = "BPS"
    OCPS = "OCPS"
    DPS = "DPS"
    
    # ========== 股本信息 (Share Information) ==========
    SHARES = "SHARES"
    LOT_SIZE = "LOT_SIZE"
    PAYOUT_RATIO = "PAYOUT_RATIO"
    SHARES_H = "SHARES_H"
    AUTHORIZED_SHARES = "AUTHORIZED_SHARES"
    
    # ========== 分红/拆股字段 (Dividend & Splits Fields) ==========
    EX_DIVIDEND_DATE = "EX_DIVIDEND_DATE"
    DIVIDEND_PLAN = "DIVIDEND_PLAN"
    ANNOUNCE_DATE = "ANNOUNCE_DATE"
    PAYMENT_DATE = "PAYMENT_DATE"
    FISCAL_YEAR = "FISCAL_YEAR"
    RECORD_DATE = "RECORD_DATE"
    DIVIDEND_TYPE = "DIVIDEND_TYPE"
    SPLIT_DATE = "SPLIT_DATE"
    SPLIT_RATIO = "SPLIT_RATIO"
    DIVIDEND_AMOUNT = "DIVIDEND_AMOUNT"
    EX_DATE = "EX_DATE"
    
    # --- 新增：第三方 API 预计算/分析指标 (Analysis) ---
    # 统一增加 ANA_ 前缀，明确告知开发者这属于预计算指标，需做容错处理
    # 拆分原因：ROE_YEARLY 是成品（已年化），ROE_AVG 是半成品（未年化），需分别处理
    ANA_ROE_ACTUAL = "ANA_ROE_ACTUAL"  # 成品 - 已年化，如 ROE_YEARLY
    ANA_ROE_AVG = "ANA_ROE_AVG"          # 半成品 - 未年化 YTD，如 ROE_AVG
    ANA_NET_MARGIN = "ANA_NET_MARGIN"
    ANA_CURRENT_RATIO = "ANA_CURRENT_RATIO"
    ANA_REV_YOY = "ANA_REV_YOY"
    ANA_NI_YOY = "ANA_NI_YOY"


# ==========================================
# 3. 财务字段映射 (Financial Fields)
# ==========================================
FINANCIAL_FIELD_CHAINS: Dict[str, List[str]] = {
    # 利润表 (Income Statement)
    "REV": [
        "total_revenue", "totalRevenue", "operating_revenue", "OPERATE_INCOME", 
        "营业总收入", "营业额", "营收", "收益", "营业收入", "营运收入"
    ],
    "NI": [
        "net_income", "net_income_common_stockholders", "netIncome", "HOLDER_PROFIT",
        "归母净利润", "股东应占溢利", "净利润", "期内利润", "期内盈利", "归属于母公司所有者的净利润"
    ],
    "OI": [
        "operating_income", "operatingIncome", "OPERATING_PROFIT",
        "营业利润", "经营溢利", "营运利润", "PER_OI"
    ],
    "GP": [
        "gross_profit", "grossProfit", "GROSS_PROFIT",
        "毛利", "营业毛利", "毛利润"
    ],
    "EBITDA": [
        "ebitda", "EBITDA", "息税折旧摊销前利润"
    ],
    "TAX": [
        "income_tax_expense", "tax_provision", "税项", "所得税", "应交所得税"
    ],

    # 资产负债表 (Balance Sheet)
    "ASSETS": [
        "total_assets", "totalAssets", "TOTAL_ASSETS", 
        "资产总额", "总资产", "资产合计"
    ],
    "LIAB": [
        "total_liabilities", "totalLiabilities", "TOTAL_LIABILITIES", "total_liabilities_net_minority_interest",
        "总负债", "负债合计", "负债总额"
    ],
    "EQUITY": [
        "total_common_equity", "total_equity", "totalStockholderEquity", "TOTAL_EQUITY",
        "总权益", "股东权益", "权益总额", "所有者权益合计", "净资产"
    ],
    "C_ASSETS": [
        "total_current_assets", "currentAssets", "流动资产合计", "流动资产总额"
    ],
    "C_LIAB": [
        "total_current_liabilities", "currentLiabilities", "current_liabilities", "流动负债合计", "流动负债总额"
    ],
    "CASH_AND_EQUIV": [
        "cash_and_cash_equivalents", "cashAndCashEquivalents", 
        "现金及等价物", "货币资金", "现金及现金等价物"
    ],
    "INTANGIBLE": [
        "intangible_assets", "intangibleAssets", "无形资产"
    ],
    "GOODWILL": [
        "goodwill", "Goodwill", "商誉"
    ],

    # 现金流量表 (Cash Flow)
    "OCF": [
        "operating_cash_flow", "totalCashFromOperatingActivities", "NET_CASH_OPERATE",
        "经营业务现金净额", "经营活动产生的现金流量净额", "经营活动现金流量净额", "PER_NETCASH_OPERATE"
    ],
    "ICF": [
        "investing_cash_flow", "totalCashflowsFromInvestingActivities", 
        "投资业务现金净额", "投资活动产生的现金流量净额"
    ],
    "FCF": [
        "free_cash_flow", "freeCashflow", "自由现金流", "自由现金流量"
    ],
    "CAPEX": [
        "capital_expenditure", "capitalExpenditures", 
        "购建固定资产、无形资产和其他长期资产支付的现金", "购建固定资产", "资本开支", "资本支出"
    ],

    # 效率与回报 (Efficiency & Returns)
    "ROE": [
        "return_on_equity", "returnOnEquity", "roe", "股东权益回报率(%)", "净资产收益率"
    ],
    "ROA": [
        "return_on_assets", "returnOnAssets", "roa", "总资产回报率(%)", "总资产收益率"
    ],
    "NET_MARGIN": [
        "net_profit_margin", "netProfitMargin", "netMargin", "销售净利率(%)", "净利率"
    ],
    "GROSS_MARGIN": [
        "gross_profit_margin", "grossMargin", "gross_margin", "销售毛利率(%)", "毛利率"
    ],

    # 增长率 (Growth Ratios)
    "REV_GROWTH_QOQ": ["营业总收入滚动环比增长(%)"],
    "NI_GROWTH_QOQ": ["净利润滚动环比增长(%)"],
    "REV_GROWTH_YOY": ["OPERATE_INCOME_YOY", "营业总收入同比增长(%)"],
    "NI_GROWTH_YOY": ["HOLDER_PROFIT_YOY", "净利润同比增长(%)"],
}


# ==========================================
# 3. 市场字段映射 (Market Fields)
# ==========================================
MARKET_FIELD_CHAINS: Dict[str, List[str]] = {
    # 实时估值指标
    "MCAP": [
        "marketCap", "market_cap", "market_value",
        "总市值(港元)", "总市值", "市值"
    ],
    "MCAP_HK": ["港股市值(港元)", "港股市值"],
    "PE": [
        "trailingPE", "pe_ratio", "peRatio", "市盈率", "市盈率(TTM)"
    ],
    "PB": [
        "priceToBook", "price_to_book", "市净率"
    ],
    "PS": [
        "priceToSales", "price_to_sales", "priceToSalesTrailing12Months", "市销率"
    ],
    "PCF": [
        "priceToCashFlow", "price_to_cash_flow", "市现率"
    ],
    "DIVIDEND_YIELD": [
        "dividendYield", "dividend_yield", "股息率TTM(%)", "股息率"
    ],

    # 每股指标
    "EPS": [
        "trailingEps", "eps_ttm", "基本每股收益(元)", "基本每股收益", "每股收益"
    ],
    "BPS": [
        "bookValue", "book_value", "每股净资产(元)", "每股净资产"
    ],
    "OCPS": [
        "operating_cash_flow_per_share", "每股经营现金流(元)", "每股经营现金流"
    ],
    "DPS": [
        "dividend_per_share", "dps", "每股股息TTM(港元)", "每股派息"
    ],

    # 股本信息
    "SHARES": [
        "shares_outstanding", "sharesOutstanding", "total_common_shares",
        "已发行股本(股)", "总股本", "总发行股数"
    ],
    "LOT_SIZE": [
        "lot_size", "每手股", "最小交易单位"
    ],
    "PAYOUT_RATIO": [
        "payout_ratio", "payoutRatio", "派息比率(%)", "股利支付率"
    ],
    "SHARES_H": ["已发行股本-H股(股)"],
    "AUTHORIZED_SHARES": ["法定股本(股)"],
}


# ==========================================
# 4. 分红/拆股字段映射 (Dividend & Splits Fields)
# ==========================================
DIVIDEND_FIELD_CHAINS: Dict[str, List[str]] = {
    # 港股分红字段 (AkShare - stock_hk_dividend_payout_em)
    "EX_DIVIDEND_DATE": ["除净日", "ex_dividend_date"],
    "DIVIDEND_PLAN": ["分红方案", "dividend_plan"],
    "ANNOUNCE_DATE": ["最新公告日期", "announce_date"],
    "PAYMENT_DATE": ["发放日", "payment_date"],
    "FISCAL_YEAR": ["财政年度", "fiscal_year"],
    "RECORD_DATE": ["截至过户日", "record_date"],
    "DIVIDEND_TYPE": ["分配类型", "dividend_type"],
    
    # 港股拆股字段 (如有)
    "SPLIT_DATE": ["拆股日期", "split_date"],
    "SPLIT_RATIO": ["拆股比例", "split_ratio", "ratio"],
    
    # 美股分红字段 (OpenBB)
    "DIVIDEND_AMOUNT": ["amount", "dividend_amount"],
    "EX_DATE": ["ex_dividend_date", "ex_date"],
}

# ==========================================
# 新增：第三方分析/预计算指标字段映射 (Analysis Fields)
# ==========================================
ANALYSIS_FIELD_CHAINS: Dict[str, List[str]] = {
    # 净资产收益率 (ROE) - 拆分原因：ROE_YEARLY 是成品，ROE_AVG 是半成品
    # 成品 - 已年化
    "ANA_ROE_ACTUAL": [
        "ROE_YEARLY",                    # AkShare 已年化
        "returnOnEquity", "roe"           # yfinance (通常 TTM)
    ],
    # 半成品 - 未年化 YTD
    "ANA_ROE_AVG": [
        "ROE_AVG"                        # AkShare 未年化
    ],
    
    # 净利率 (Net Margin)
    "ANA_NET_MARGIN": [
        "NET_PROFIT_RATIO",               # AkShare (数据包中验证存在)
        "profitMargins", "netProfitMargin", "netMargin" # yfinance
    ],
    
    # 流动比率 (Current Ratio)
    "ANA_CURRENT_RATIO": [
        "CURRENT_RATIO",                  # AkShare (数据包中验证存在)
        "currentRatio", "current_ratio"   # yfinance
    ],
    
    # 营收同比增长 (Revenue YoY)
    "ANA_REV_YOY": [
        "OPERATE_INCOME_YOY",             # AkShare (数据包中验证存在)
        "revenueGrowth"                   # yfinance
    ],
    
    # 净利润同比增长 (Net Income YoY)
    "ANA_NI_YOY": [
        "HOLDER_PROFIT_YOY",              # AkShare (数据包中验证存在)
        "earningsGrowth"                  # yfinance
    ],
}

# ==========================================
# 5. 合并的完整 FIELD_CHAINS (向后兼容)
# ==========================================
FIELD_CHAINS: Dict[str, List[str]] = {
    **FINANCIAL_FIELD_CHAINS,
    **MARKET_FIELD_CHAINS,
    **DIVIDEND_FIELD_CHAINS,
    **ANALYSIS_FIELD_CHAINS,
}


# ==========================================
# 5. 辅助函数
# ==========================================

def find_closest_strictly(
    series: List[Dict], 
    anchor_date: Optional[datetime], 
    window: int = 20
) -> Optional[Dict]:
    """
    在数据序列中寻找与目标日期最接近的记录
    
    Args:
        series: 数据列表
        anchor_date: 目标日期
        window: 搜索窗口（天）
    
    Returns:
        最接近的记录，如果没有找到则返回 None
    """
    if not series or not anchor_date:
        return None
    
    best_item = None
    min_diff = float('inf')
    
    for item in series:
        d_raw = item.get(MetaKey.PERIOD_ENDING)
        if not d_raw:
            continue
            
        try:
            d = pd.to_datetime(d_raw)
        except:
            continue
            
        if pd.isna(d):
            continue

        diff = abs((d - anchor_date).days)
        
        if diff <= window and diff < min_diff:
            min_diff = diff
            best_item = item
            
    return best_item


def detect_report_type(item: Dict[str, Any]) -> Optional[ReportPeriod]:
    """
    判断报表类型 (兼容 AkShare 和 OBB)
    
    优先级:
    1. DATE_TYPE_CODE (AkShare 的报告类型码)
    2. report_type 字段 (OBB 添加的)
    
    Args:
        item: 报表记录 Dict
    
    Returns:
        ReportPeriod 枚举值，或 None (无法判断)
    
    注意: 
    - 离散制(美股)的 "quarterly" = 单季数据
    - 累积制(港股/A股)的 "quarterly" = YTD累计数据 (Q1/Q3)
    下游使用时需根据 is_cumulative 自行判断如何处理
    """
    if not item:
        return None
    
    # 优先级 1: DATE_TYPE_CODE (AkShare) - 使用映射字典
    code = item.get(MetaKey.DATE_TYPE_CODE)
    if code and code in _AKSHARE_DATE_TYPE_MAP:
        return _AKSHARE_DATE_TYPE_MAP[code]
    
    # 优先级 2: report_type (OBB) - 使用映射字典
    rt = item.get(MetaKey.REPORT_TYPE)
    if rt and rt in _OBB_REPORT_TYPE_MAP:
        return _OBB_REPORT_TYPE_MAP[rt]
    
    return None


def get_field_value(item: Optional[Dict], field_alias: str, field_chains: Optional[Dict[str, List[str]]] = None) -> Optional[float]:
    """
    从记录中提取字段值，支持多别名映射
    
    Args:
        item: 数据记录
        field_alias: 字段别名（如 "MCAP", "PE"）
        field_chains: 字段映射字典，默认使用 FIELD_CHAINS
    
    Returns:
        字段值（float），未找到返回 None
    """
    if not item:
        return None
    
    chains = field_chains or FIELD_CHAINS
    candidates = chains.get(field_alias, [field_alias])
    
    for c in candidates:
        v = item.get(c)
        if v is not None and v != "" and not pd.isna(v):
            try:
                return float(v)
            except (ValueError, TypeError):
                continue
    return None

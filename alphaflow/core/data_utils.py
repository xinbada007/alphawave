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
# 2. 财务字段映射 (Financial Fields)
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
# 5. 合并的完整 FIELD_CHAINS (向后兼容)
# ==========================================
FIELD_CHAINS: Dict[str, List[str]] = {
    **FINANCIAL_FIELD_CHAINS,
    **MARKET_FIELD_CHAINS,
    **DIVIDEND_FIELD_CHAINS,
}


# ==========================================
# 5. 辅助函数
# ==========================================

def find_closest_strictly(
    series: List[Dict], 
    anchor_date: Optional[datetime], 
    window: int = 15
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
        d_raw = item.get("period_ending")
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


def get_fcf_raw(item: Optional[Dict]) -> Optional[float]:
    """
    物理推导自由现金流 (FCF = OCF - |CAPEX|)
    
    Args:
        item: 现金流量表记录
    
    Returns:
        FCF 值，未找到返回 None
    """
    if not item:
        return None
    
    # 先尝试直接获取 FCF
    f = get_field_value(item, "FCF")
    if f is not None:
        return f
    
    # 如果没有，尝试通过 OCF - CAPEX 计算
    o = get_field_value(item, "OCF")
    c = get_field_value(item, "CAPEX")
    if o is not None and c is not None:
        return o - abs(c)
    
    return None

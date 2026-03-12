"""
AkShare 分析指标核心契约 (AkShare Analysis Domain)
==================================================
单一数据源 (Single Source of Truth)

设计哲学：
- 高内聚低耦合：所有分析指标相关定义集中于此
- 静态 Mixin 模式：保留 IDE 类型推断和静态检查
- 专属前缀：为与三大表原生字段区分，所有类属性加上 AKSHARE_ 前缀
- 输出净化：常量 Mixin 的值和映射表 value 保持简洁，最终 JSON 输出无 AKSHARE_ 前缀
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel

# ==========================================
# 1. OBB/AkShare → 标准字段映射表 (严格一一映射)
# ==========================================
AKSHARE_ANALYSIS_MAPPING: Dict[str, Dict[str, Any]] = {
    # --- 基础与币种信息 ---
    "SECURITY_NAME_ABBR": {"obb":[], "akshare": ["SECURITY_NAME_ABBR"]},
    "CURRENCY": {"obb":[], "akshare": ["CURRENCY"]},
    "FISCAL_YEAR": {"obb":[], "akshare": ["FISCAL_YEAR"]},
    
    # --- 每股指标 (Per Share) ---
    "PER_NETCASH_OPERATE": {"obb": [], "akshare":["PER_NETCASH_OPERATE"]},
    "PER_OI": {"obb":[], "akshare": ["PER_OI"]},
    "BPS": {"obb": [], "akshare":["BPS"]},
    "BASIC_EPS": {"obb": [], "akshare":["BASIC_EPS"]},
    "DILUTED_EPS": {"obb": [], "akshare":["DILUTED_EPS"]},
    "EPS_TTM": {"obb":[], "akshare": ["EPS_TTM"]},

    # --- 绝对值 (Income & Profits) ---
    "OPERATE_INCOME": {"obb": [], "akshare": ["OPERATE_INCOME"]},
    "GROSS_PROFIT": {"obb": [], "akshare":["GROSS_PROFIT"]},
    "HOLDER_PROFIT": {"obb": [], "akshare":["HOLDER_PROFIT"]},

    # --- 同比增长率 (YOY Growth) ---
    "OPERATE_INCOME_YOY": {"obb": [], "akshare":["OPERATE_INCOME_YOY"]},
    "GROSS_PROFIT_YOY": {"obb":[], "akshare": ["GROSS_PROFIT_YOY"]},
    "HOLDER_PROFIT_YOY": {"obb": [], "akshare":["HOLDER_PROFIT_YOY"]},

    # --- 环比增长率 (QOQ Growth) ---
    "OPERATE_INCOME_QOQ": {"obb": [], "akshare":["OPERATE_INCOME_QOQ"]},
    "GROSS_PROFIT_QOQ": {"obb":[], "akshare": ["GROSS_PROFIT_QOQ"]},
    "HOLDER_PROFIT_QOQ": {"obb": [], "akshare":["HOLDER_PROFIT_QOQ"]},

    # --- 盈利能力比率 (Profitability Ratios) ---
    "GROSS_PROFIT_RATIO": {"obb": [], "akshare": ["GROSS_PROFIT_RATIO"]},
    "NET_PROFIT_RATIO": {"obb": [], "akshare":["NET_PROFIT_RATIO"]},
    "ROE_AVG": {"obb":[], "akshare": ["ROE_AVG"]},
    "ROE_YEARLY": {"obb":[], "akshare": ["ROE_YEARLY"]},
    "ROA": {"obb":[], "akshare": ["ROA"]},
    "ROIC_YEARLY": {"obb":[], "akshare": ["ROIC_YEARLY"]},
    "TAX_EBT": {"obb":[], "akshare": ["TAX_EBT"]},
    "OCF_SALES": {"obb":[], "akshare": ["OCF_SALES"]},

    # --- 财务健康与杠杆比率 (Financial Health & Leverage) ---
    "DEBT_ASSET_RATIO": {"obb": [], "akshare": ["DEBT_ASSET_RATIO"]},
    "CURRENT_RATIO": {"obb": [], "akshare": ["CURRENT_RATIO"]},
    "CURRENTDEBT_DEBT": {"obb": [], "akshare": ["CURRENTDEBT_DEBT"]},
}


# ==========================================
# 2. 键名常量 Mixin (FinKey Mixin)
# ==========================================
class AkShareAnalysisKey:
    """AkShare 分析指标常量 Mixin
    
    设计哲学：
    - 类属性名带 AKSHARE_ 前缀：用于代码中明确区分数据来源，避免与三大表字段混淆
    - 属性值无 AKSHARE_ 前缀：最终输出到 JSON 的字段名，保持简洁
    """
    # --- 基础与币种信息 ---
    AKSHARE_SECURITY_NAME_ABBR: str = "SECURITY_NAME_ABBR"
    AKSHARE_CURRENCY: str = "CURRENCY"
    AKSHARE_FISCAL_YEAR: str = "FISCAL_YEAR"
    
    # --- 每股指标 (Per Share) ---
    AKSHARE_PER_NETCASH_OPERATE: str = "PER_NETCASH_OPERATE"
    AKSHARE_PER_OI: str = "PER_OI"
    AKSHARE_BPS: str = "BPS"
    AKSHARE_BASIC_EPS: str = "BASIC_EPS"
    AKSHARE_DILUTED_EPS: str = "DILUTED_EPS"
    AKSHARE_EPS_TTM: str = "EPS_TTM"

    # --- 绝对值 (Income & Profits) ---
    AKSHARE_OPERATE_INCOME: str = "OPERATE_INCOME"
    AKSHARE_GROSS_PROFIT: str = "GROSS_PROFIT"
    AKSHARE_HOLDER_PROFIT: str = "HOLDER_PROFIT"

    # --- 同比增长率 (YOY Growth) ---
    AKSHARE_OPERATE_INCOME_YOY: str = "OPERATE_INCOME_YOY"
    AKSHARE_GROSS_PROFIT_YOY: str = "GROSS_PROFIT_YOY"
    AKSHARE_HOLDER_PROFIT_YOY: str = "HOLDER_PROFIT_YOY"

    # --- 环比增长率 (QOQ Growth) ---
    AKSHARE_OPERATE_INCOME_QOQ: str = "OPERATE_INCOME_QOQ"
    AKSHARE_GROSS_PROFIT_QOQ: str = "GROSS_PROFIT_QOQ"
    AKSHARE_HOLDER_PROFIT_QOQ: str = "HOLDER_PROFIT_QOQ"

    # --- 盈利能力比率 (Profitability Ratios) ---
    AKSHARE_GROSS_PROFIT_RATIO: str = "GROSS_PROFIT_RATIO"
    AKSHARE_NET_PROFIT_RATIO: str = "NET_PROFIT_RATIO"
    AKSHARE_ROE_AVG: str = "ROE_AVG"
    AKSHARE_ROE_YEARLY: str = "ROE_YEARLY"
    AKSHARE_ROA: str = "ROA"
    AKSHARE_ROIC_YEARLY: str = "ROIC_YEARLY"
    AKSHARE_TAX_EBT: str = "TAX_EBT"
    AKSHARE_OCF_SALES: str = "OCF_SALES"

    # --- 财务健康与杠杆比率 (Financial Health & Leverage) ---
    AKSHARE_DEBT_ASSET_RATIO: str = "DEBT_ASSET_RATIO"
    AKSHARE_CURRENT_RATIO: str = "CURRENT_RATIO"
    AKSHARE_CURRENTDEBT_DEBT: str = "CURRENTDEBT_DEBT"


# ==========================================
# 3. Pydantic 模型 Mixin (Schema Mixin)
# ==========================================
class AkShareAnalysisRecord(BaseModel):
    """AkShare 分析指标 Pydantic 模型 Mixin
    
    设计哲学：
    - 字段名无 AKSHARE_ 前缀：与最终 JSON 输出字段名保持一致
    - 所有字段为 Optional，允许部分缺失
    """
    # --- 基础与币种信息 ---
    SECURITY_NAME_ABBR: Optional[str] = None
    CURRENCY: Optional[str] = None
    FISCAL_YEAR: Optional[str] = None
    
    # --- 每股指标 (Per Share) ---
    PER_NETCASH_OPERATE: Optional[float] = None
    PER_OI: Optional[float] = None
    BPS: Optional[float] = None
    BASIC_EPS: Optional[float] = None
    DILUTED_EPS: Optional[float] = None
    EPS_TTM: Optional[float] = None

    # --- 绝对值 (Income & Profits) ---
    OPERATE_INCOME: Optional[float] = None
    GROSS_PROFIT: Optional[float] = None
    HOLDER_PROFIT: Optional[float] = None

    # --- 同比增长率 (YOY Growth) ---
    OPERATE_INCOME_YOY: Optional[float] = None
    GROSS_PROFIT_YOY: Optional[float] = None
    HOLDER_PROFIT_YOY: Optional[float] = None

    # --- 环比增长率 (QOQ Growth) ---
    OPERATE_INCOME_QOQ: Optional[float] = None
    GROSS_PROFIT_QOQ: Optional[float] = None
    HOLDER_PROFIT_QOQ: Optional[float] = None

    # --- 盈利能力比率 (Profitability Ratios) ---
    GROSS_PROFIT_RATIO: Optional[float] = None
    NET_PROFIT_RATIO: Optional[float] = None
    ROE_AVG: Optional[float] = None
    ROE_YEARLY: Optional[float] = None
    ROA: Optional[float] = None
    ROIC_YEARLY: Optional[float] = None
    TAX_EBT: Optional[float] = None
    OCF_SALES: Optional[float] = None

    # --- 财务健康与杠杆比率 (Financial Health & Leverage) ---
    DEBT_ASSET_RATIO: Optional[float] = None
    CURRENT_RATIO: Optional[float] = None
    CURRENTDEBT_DEBT: Optional[float] = None

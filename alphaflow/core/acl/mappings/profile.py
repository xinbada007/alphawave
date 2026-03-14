"""
公司基本信息核心契约 (Profile Domain)
======================================
单一数据源 (Single Source of Truth)

设计哲学：
- 高内聚低耦合：所有公司基本信息相关定义集中于此
- 静态 Mixin 模式：保留 IDE 类型推断和静态检查
- 严格一一映射：每个 OBB 字段只映射一个标准字段（大写形式）
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from functools import partial

# 🚀 导入 transform 函数 (用于长文本截断)
from alphaflow.core.acl.transformers import _tx_truncate_text


# ==========================================
# 1. OBB → 标准字段映射表 (严格一一映射)
# ==========================================
PROFILE_MAPPING: Dict[str, Dict[str, Any]] = {
    # ==========================================
    # 📊 公司基本信息 (Company Basic Info)
    # ==========================================
    "SECTOR": {
        "obb": ["sector"],
        "akshare": ["所属行业"]
    },
    "INDUSTRY_CATEGORY": {
        "obb": ["industry_category"],
        "akshare": ["细分行业"]
    },
    "NAME": {
        "obb": ["name"],
        "akshare": ["公司名称"]
    },
    "LONG_DESCRIPTION": {
        "obb": {
            "aliases": ["long_description"],
            "transform": partial(_tx_truncate_text, max_len=1000),
        },
        "akshare": {
            "aliases": ["公司介绍"],
            "transform": partial(_tx_truncate_text, max_len=1000),
        },
    },
    "EMPLOYEES": {
        "obb": ["employees"],
        "akshare": ["员工人数"]
    },
    "STOCK_EXCHANGE": {
        "obb": ["stock_exchange"],
        "akshare": ["交易所"]
    },
    "COMPANY_URL": {
        "obb": ["company_url"],
        "akshare": ["公司网址"]
    },
    "BETA": {
        "obb": ["beta"],
        "akshare": []
    },
    "HQ_COUNTRY": {
        "obb": ["hq_country"],
        "akshare": {
            "aliases": ["办公地址"],
            "transform": partial(_tx_truncate_text, max_len=10),
        },
    },
    "ISSUE_TYPE": {
        "obb": ["issue_type"],
        "akshare": ["证券类型"]
    },
    "CURRENCY": {
        "obb": ["currency"],
        "akshare": []
    },
    
    # ==========================================
    # 📊 股本信息 (Share Information)
    # ==========================================
    "SHARES_OUTSTANDING": {
        "obb": ["shares_outstanding"],
        "akshare": ["发行量(股)"]
    },
    "SHARES_FLOAT": {
        "obb": ["shares_float"],
        "akshare": ["流通股本"]
    },
    "SHARES_IMPLIED_OUTSTANDING": {
        "obb": ["shares_implied_outstanding"],
        "akshare": []
    },
    "SHARES_SHORT": {
        "obb": ["shares_short"],
        "akshare": []
    },
    
    # ==========================================
    # 📊 市值与估值 (Market Cap & Valuation)
    # ==========================================
    "MARKET_CAP": {
        "obb": ["market_cap"],
        "akshare": ["总市值"]
    },
    "DIVIDEND_YIELD": {
        "obb": ["dividend_yield"],
        "akshare": ["股息率"]
    },
    
    # ==========================================
    # 📊 公司治理与上市信息 (Governance & Listing Info)
    # ==========================================
    "LISTING_DATE": {
        "obb": ["listing_date"],
        "akshare": ["上市日期"]
    },
    "CHAIRMAN": {
        "obb": ["chairman"],
        "akshare": ["董事长"]
    },
    "BOARD": {
        "obb": ["board"],
        "akshare": ["板块"]
    },
    "FISCAL_YEAR_END": {
        "obb": ["fiscal_year_end"],
        "akshare": ["年结日"]
    },
    "INCORPORATION": {
        "obb": ["incorporation"],
        "akshare": ["注册地"]
    },
    "LOT_SIZE": {
        "obb": ["lot_size"],
        "akshare": ["每手股数"]
    },
    "ISSUE_PRICE": {
        "obb": ["issue_price"],
        "akshare": ["发行价"]
    },
    
    # ==========================================
    # 📊 港股特有字段 (HK-Specific Fields)
    # ==========================================
    "COMPANY_NAME_ENG": {
        "obb": [],
        "akshare": ["英文名称"]
    },
    "SH_HK_CONNECT": {
        "obb": [],
        "akshare": ["是否沪港通标的"]
    },
    "SZ_HK_CONNECT": {
        "obb": [],
        "akshare": ["是否深港通标的"]
    },
}


# ==========================================
# 2. 键名常量 Mixin (FinKey Mixin)
# ==========================================
class ProfileKey:
    """
    公司基本信息字段常量 Mixin
    供 FinKey 类继承，实现静态类型支持
    严格一一映射：OBB 原始字段名直接大写
    """
    # ==========================================
    # 📊 公司基本信息 (Company Basic Info)
    # ==========================================
    SECTOR: str = "SECTOR"
    INDUSTRY_CATEGORY: str = "INDUSTRY_CATEGORY"
    NAME: str = "NAME"
    LONG_DESCRIPTION: str = "LONG_DESCRIPTION"
    EMPLOYEES: str = "EMPLOYEES"
    STOCK_EXCHANGE: str = "STOCK_EXCHANGE"
    COMPANY_URL: str = "COMPANY_URL"
    BETA: str = "BETA"
    HQ_COUNTRY: str = "HQ_COUNTRY"
    ISSUE_TYPE: str = "ISSUE_TYPE"
    CURRENCY: str = "CURRENCY"
    
    # ==========================================
    # 📊 股本信息 (Share Information)
    # ==========================================
    SHARES_OUTSTANDING: str = "SHARES_OUTSTANDING"
    SHARES_FLOAT: str = "SHARES_FLOAT"
    SHARES_IMPLIED_OUTSTANDING: str = "SHARES_IMPLIED_OUTSTANDING"
    SHARES_SHORT: str = "SHARES_SHORT"
    
    # ==========================================
    # 📊 市值与估值 (Market Cap & Valuation)
    # ==========================================
    MARKET_CAP: str = "MARKET_CAP"
    DIVIDEND_YIELD: str = "DIVIDEND_YIELD"
    
    # ==========================================
    # 📊 公司治理与上市信息 (Governance & Listing Info)
    # ==========================================
    LISTING_DATE: str = "LISTING_DATE"
    CHAIRMAN: str = "CHAIRMAN"
    BOARD: str = "BOARD"
    FISCAL_YEAR_END: str = "FISCAL_YEAR_END"
    INCORPORATION: str = "INCORPORATION"
    LOT_SIZE: str = "LOT_SIZE"
    ISSUE_PRICE: str = "ISSUE_PRICE"
    
    # ==========================================
    # 📊 港股特有字段 (HK-Specific Fields)
    # ==========================================
    COMPANY_NAME_ENG: str = "COMPANY_NAME_ENG"
    SH_HK_CONNECT: str = "SH_HK_CONNECT"
    SZ_HK_CONNECT: str = "SZ_HK_CONNECT"


# ==========================================
# 3. Pydantic 模型 Mixin (Schema Mixin)
# ==========================================
class ProfileRecord(BaseModel):
    """
    公司基本信息字段 Pydantic 模型 Mixin
    供 StandardFinancialRecord 类继承
    """
    # ==========================================
    # 📊 公司基本信息 (Company Basic Info)
    # ==========================================
    SECTOR: Optional[str] = None
    INDUSTRY_CATEGORY: Optional[str] = None
    NAME: Optional[str] = None
    LONG_DESCRIPTION: Optional[str] = None
    EMPLOYEES: Optional[int] = None
    STOCK_EXCHANGE: Optional[str] = None
    COMPANY_URL: Optional[str] = None
    BETA: Optional[float] = None
    HQ_COUNTRY: Optional[str] = None
    ISSUE_TYPE: Optional[str] = None
    CURRENCY: Optional[str] = None
    
    # ==========================================
    # 📊 股本信息 (Share Information)
    # ==========================================
    SHARES_OUTSTANDING: Optional[float] = None
    SHARES_FLOAT: Optional[float] = None
    SHARES_IMPLIED_OUTSTANDING: Optional[float] = None
    SHARES_SHORT: Optional[float] = None
    
    # ==========================================
    # 📊 市值与估值 (Market Cap & Valuation)
    # ==========================================
    MARKET_CAP: Optional[float] = None
    DIVIDEND_YIELD: Optional[float] = None
    
    # ==========================================
    # 📊 公司治理与上市信息 (Governance & Listing Info)
    # ==========================================
    LISTING_DATE: Optional[str] = None
    CHAIRMAN: Optional[str] = None
    BOARD: Optional[str] = None
    FISCAL_YEAR_END: Optional[str] = None
    INCORPORATION: Optional[str] = None
    LOT_SIZE: Optional[float] = None
    ISSUE_PRICE: Optional[float] = None
    
    # ==========================================
    # 📊 港股特有字段 (HK-Specific Fields)
    # ==========================================
    COMPANY_NAME_ENG: Optional[str] = None
    SH_HK_CONNECT: Optional[str] = None
    SZ_HK_CONNECT: Optional[str] = None
"""
股权结构与做空数据核心契约 (Share Stats Domain)
==============================================
单一数据源 (Single Source of Truth)

设计哲学：
- 一一映射：OBB 原始字段名直接大写作为标准字段名
- 高内聚低耦合：所有股权结构与做空数据相关定义集中于此
- 静态 Mixin 模式：保留 IDE 类型推断和静态检查
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel
# 🚀 导入 transform 函数 (用于虚拟字段)
from alphaflow.core.transform_adapter import _tx_calc_short_interest_change


# ==========================================
# 1. OBB → 标准字段映射表 (一一映射)
# ==========================================
SHARE_STATS_MAPPING: Dict[str, Dict[str, Any]] = {
    # ==========================================
    # 📊 股本结构 (Share Capital) - 一一映射
    # ==========================================
    "FLOAT_SHARES": {
        "obb": ["float_shares"],
        "akshare": ["流通股本", "流通股数", "流通股"]
    },
    "OUTSTANDING_SHARES": {
        "obb": ["outstanding_shares"],
        "akshare": ["总股本", "已发行股本(股)", "总发行股数"]
    },
    "IMPLIED_SHARES_OUTSTANDING": {
        "obb": ["implied_shares_outstanding"],
        "akshare": []
    },
    
    # ==========================================
    # 📊 机构与内部人持仓 (Ownership) - 一一映射
    # ==========================================
    "INSTITUTION_OWNERSHIP": {
        "obb": ["institution_ownership"],
        "akshare": ["机构持股比例"]
    },
    "INSTITUTION_FLOAT_OWNERSHIP": {
        "obb": ["institution_float_ownership"],
        "akshare": []
    },
    "INSIDER_OWNERSHIP": {
        "obb": ["insider_ownership"],
        "akshare": ["内部人持股比例"]
    },
    "INSTITUTIONS_COUNT": {
        "obb": ["institutions_count"],
        "akshare": []
    },
    
    # ==========================================
    # 📊 做空数据 (Short Interest) - 一一映射
    # ==========================================
    "SHORT_INTEREST": {
        "obb": ["short_interest"],
        "akshare": []
    },
    "SHORT_PERCENT_OF_FLOAT": {
        "obb": ["short_percent_of_float"],
        "akshare": []
    },
    "DAYS_TO_COVER": {
        "obb": ["days_to_cover"],
        "akshare": []
    },
    
    # ==========================================
    # 📊 虚拟字段：做空变化率 (计算得出)
    # ==========================================
    "SHORT_INT_CHANGE_PCT": {
        "obb": {
            "aliases": [],  # 虚拟字段，无直接映射
            "transform": _tx_calc_short_interest_change,
        },
        "akshare": [],  # AkShare 暂不支持
    },
}


# ==========================================
# 2. 键名常量 Mixin (FinKey Mixin)
# ==========================================
class ShareStatsKey:
    """
    股权结构与做空数据字段常量 Mixin
    供 FinKey 类继承，实现静态类型支持
    一一映射：OBB 原始字段名直接大写
    """
    # ==========================================
    # 📊 股本结构 (Share Capital)
    # ==========================================
    FLOAT_SHARES: str = "FLOAT_SHARES"
    OUTSTANDING_SHARES: str = "OUTSTANDING_SHARES"
    IMPLIED_SHARES_OUTSTANDING: str = "IMPLIED_SHARES_OUTSTANDING"
    
    # ==========================================
    # 📊 机构与内部人持仓 (Ownership)
    # ==========================================
    INSTITUTION_OWNERSHIP: str = "INSTITUTION_OWNERSHIP"
    INSTITUTION_FLOAT_OWNERSHIP: str = "INSTITUTION_FLOAT_OWNERSHIP"
    INSIDER_OWNERSHIP: str = "INSIDER_OWNERSHIP"
    INSTITUTIONS_COUNT: str = "INSTITUTIONS_COUNT"
    
    # ==========================================
    # 📊 做空数据 (Short Interest)
    # ==========================================
    SHORT_INTEREST: str = "SHORT_INTEREST"
    SHORT_PERCENT_OF_FLOAT: str = "SHORT_PERCENT_OF_FLOAT"
    DAYS_TO_COVER: str = "DAYS_TO_COVER"
    SHORT_INT_CHANGE_PCT: str = "SHORT_INT_CHANGE_PCT"


# ==========================================
# 3. Pydantic 模型 Mixin (Schema Mixin)
# ==========================================
class ShareStatsRecord(BaseModel):
    """
    股权结构与做空数据字段 Pydantic 模型 Mixin
    供 StandardFinancialRecord 类继承
    """
    # ==========================================
    # 📊 股本结构 (Share Capital)
    # ==========================================
    FLOAT_SHARES: Optional[float] = None
    OUTSTANDING_SHARES: Optional[float] = None
    IMPLIED_SHARES_OUTSTANDING: Optional[float] = None
    
    # ==========================================
    # 📊 机构与内部人持仓 (Ownership)
    # ==========================================
    INSTITUTION_OWNERSHIP: Optional[float] = None
    INSTITUTION_FLOAT_OWNERSHIP: Optional[float] = None
    INSIDER_OWNERSHIP: Optional[float] = None
    INSTITUTIONS_COUNT: Optional[int] = None
    
    # ==========================================
    # 📊 做空数据 (Short Interest)
    # ==========================================
    SHORT_INTEREST: Optional[float] = None
    SHORT_PERCENT_OF_FLOAT: Optional[float] = None
    DAYS_TO_COVER: Optional[float] = None
    SHORT_INT_CHANGE_PCT: Optional[float] = None
"""
分析师共识核心契约 (Estimates Domain)
======================================
单一数据源 (Single Source of Truth)

设计哲学：
- 高内聚低耦合：所有分析师共识相关定义集中于此
- 静态 Mixin 模式：保留 IDE 类型推断和静态检查
- 严格一一映射：每个 OBB 字段只映射一个标准字段（大写形式）
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ==========================================
# 1. OBB → 标准字段映射表 (严格一一映射)
# ==========================================
ESTIMATES_MAPPING: Dict[str, Dict[str, Any]] = {
    # ==========================================
    # 📊 价格目标 (Price Targets)
    # ==========================================
    "CURRENT_PRICE": {
        "obb": ["current_price"],
        "akshare": ["最新价"]
    },
    "TARGET_PRICE": {
        "obb": ["target_consensus"],
        "akshare": []
    },
    "TARGET_MEDIAN": {
        "obb": ["target_median"],
        "akshare": []
    },
    "TARGET_HIGH": {
        "obb": ["target_high"],
        "akshare": []
    },
    "TARGET_LOW": {
        "obb": ["target_low"],
        "akshare": []
    },
    
    # ==========================================
    # 📊 评级与共识 (Ratings & Consensus)
    # ==========================================
    "RECOMMENDATION_MEAN": {
        "obb": ["recommendation_mean"],
        "akshare": []
    },
    "CONSENSUS_RATING": {
        "obb": ["recommendation"],
        "akshare": []
    },
    "NUMBER_OF_ANALYSTS": {
        "obb": ["number_of_analysts"],
        "akshare": []
    },
}


# ==========================================
# 2. 键名常量 Mixin (FinKey Mixin)
# ==========================================
class EstimatesKey:
    """
    分析师共识字段常量 Mixin
    供 FinKey 类继承，实现静态类型支持
    严格一一映射：OBB 原始字段名直接大写
    """
    # ==========================================
    # 📊 价格目标 (Price Targets)
    # ==========================================
    CURRENT_PRICE: str = "CURRENT_PRICE"
    TARGET_PRICE: str = "TARGET_PRICE"
    TARGET_MEDIAN: str = "TARGET_MEDIAN"
    TARGET_HIGH: str = "TARGET_HIGH"
    TARGET_LOW: str = "TARGET_LOW"
    
    # ==========================================
    # 📊 评级与共识 (Ratings & Consensus)
    # ==========================================
    RECOMMENDATION_MEAN: str = "RECOMMENDATION_MEAN"
    CONSENSUS_RATING: str = "CONSENSUS_RATING"
    NUMBER_OF_ANALYSTS: str = "NUMBER_OF_ANALYSTS"


# ==========================================
# 3. Pydantic 模型 Mixin (Schema Mixin)
# ==========================================
class EstimatesRecord(BaseModel):
    """
    分析师共识字段 Pydantic 模型 Mixin
    供 StandardFinancialRecord 类继承
    """
    # ==========================================
    # 📊 价格目标 (Price Targets)
    # ==========================================
    CURRENT_PRICE: Optional[float] = None
    TARGET_PRICE: Optional[float] = None
    TARGET_MEDIAN: Optional[float] = None
    TARGET_HIGH: Optional[float] = None
    TARGET_LOW: Optional[float] = None
    
    # ==========================================
    # 📊 评级与共识 (Ratings & Consensus)
    # ==========================================
    RECOMMENDATION_MEAN: Optional[float] = None
    CONSENSUS_RATING: Optional[str] = None
    NUMBER_OF_ANALYSTS: Optional[int] = None
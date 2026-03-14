"""
系统核心元数据映射契约 (Meta Domain)
=====================================
三位一体：MAPPING + Key + Record Mixin
消除硬编码，将元数据提取逻辑归一化

设计原则：
- 本文件是纯净的原子定义层，无任何业务逻辑
- MetaKey 直接在此定义，不依赖任何外部模块
- 作为 data_utils.py 的上游，打破循环依赖
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from alphaflow.core.acl.transformers import _tx_format_date
from alphaflow.core.acl.mappings.enums import ReportPeriod


# ==========================================
# 1. 报表类型方言映射 (Value Translation)
# ==========================================

# AkShare 编码 -> 内部标准枚举
AKSHARE_DATE_TYPE_MAP: Dict[str, ReportPeriod] = {
    "001": ReportPeriod.ANNUAL,        # 年报 (12个月)
    "002": ReportPeriod.SEMIANNUAL,    # 中报 (6个月)
    "003": ReportPeriod.QUARTERLY,     # 一季报 (3个月)
    "004": ReportPeriod.NINE_MONTHS,   # 三季报 (9个月)
}

# OBB 字符串 -> 内部标准枚举
OBB_REPORT_TYPE_MAP: Dict[str, ReportPeriod] = {
    "annual": ReportPeriod.ANNUAL,
    "quarter": ReportPeriod.QUARTERLY,
}


# ==========================================
# 2. 字段映射字典 (Field Mapping) - Adapter 使用
# ==========================================
META_MAPPING: Dict[str, Dict[str, Any]] = {
    "PERIOD_ENDING": {
        "obb": {
            "aliases": ["date", "period_ending", "REPORT_DATE"],
            "transform": _tx_format_date
        },
        "akshare": {
            "aliases": ["REPORT_DATE", "period_ending", "date"],
            "transform": _tx_format_date
        }
    },
    "START_DATE": {
        "obb": {
            "aliases": ["start_date"],
            "transform": _tx_format_date
        },
        "akshare": {
            "aliases": ["START_DATE"],
            "transform": _tx_format_date
        }
    },
    "DATE_TYPE_CODE": {
        "obb": ["date_type_code"],
        "akshare": ["DATE_TYPE_CODE"]
    }
}


# ==========================================
# 2. 键名常量 (MetaKey) - 纯净原子定义
# ==========================================
class MetaKey:
    """
    系统元数据/日期字段常量 (统一大写风格)
    
    设计哲学：
    - 单点真理源：此处是唯一的常量定义处
    - 零依赖：不继承任何 Mixin，纯净字符串定义
    - 上游定义：作为 data_utils.py 的上游，打破循环依赖
    """
    PERIOD_ENDING: str = "PERIOD_ENDING"
    REPORT_DATE: str = "REPORT_DATE"
    REPORT_TYPE: str = "REPORT_TYPE"
    IS_CUMULATIVE: str = "IS_CUMULATIVE"
    START_DATE: str = "START_DATE"
    DATE_TYPE_CODE: str = "DATE_TYPE_CODE"


# ==========================================
# 3. Pydantic 模型 (Record Mixin) - schema_standard 继承
# ==========================================
class MetaRecord(BaseModel):
    """元数据字段骨架，供 StandardFinancialRecord 继承"""
    PERIOD_ENDING: Optional[str] = Field(default=None)
    REPORT_TYPE: Optional[ReportPeriod] = None
    IS_CUMULATIVE: Optional[bool] = None
    START_DATE: Optional[str] = None
    DATE_TYPE_CODE: Optional[str] = None

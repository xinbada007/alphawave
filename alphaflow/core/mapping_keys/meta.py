"""
系统核心元数据映射契约 (Meta Domain)
=====================================
三位一体：MAPPING + Key Mixin + Record Mixin
消除硬编码，将元数据提取逻辑归一化
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from alphaflow.core.transform_adapter import _tx_format_date
from alphaflow.core.mapping_keys.enums import ReportPeriod


# ==========================================
# 1. 映射字典 (Mapping) - Adapter 使用
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
# 2. 键名常量 (Key Mixin) - data_utils 继承
# ==========================================
class MetaKeyMixin:
    """元数据常量，供 data_utils.py 中的 MetaKey 继承"""
    PERIOD_ENDING: str = "PERIOD_ENDING"
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

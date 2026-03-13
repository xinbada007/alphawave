"""
AlphaFlow 核心枚举定义
======================
打破循环导入，将基础枚举下沉到 mapping_keys 层
"""

from enum import Enum


class ReportPeriod(str, Enum):
    """财报周期枚举 - 精准表达时间跨度"""
    QUARTERLY = "quarterly"         # 3个月 (美股全季度，A/港股Q1)
    SEMIANNUAL = "semiannual"       # 6个月 (A/港股H1中报)
    NINE_MONTHS = "nine_months"     # 9个月 (A/港股Q3三季报)
    ANNUAL = "annual"               # 12个月 (年报)
    LATEST = "latest"               # 兜底快照


class MarketType(Enum):
    """市场类型枚举"""
    HK = "hk"      # 港股
    CN = "cn"      # A股 (沪深)
    US = "us"      # 美股
    UNKNOWN = "unknown"

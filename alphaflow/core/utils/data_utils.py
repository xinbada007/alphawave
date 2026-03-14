"""
数据工具共享模块 - AlphaFlow Core 层
=====================================
全域统一词汇表 (Universal Vocabulary)
用于 AlphaFlow 组件间的数据定义和公共工具

设计哲学：
- 原子导入原则：只从 mapping_keys 导入原子常量，不碰 keys.py 总线
- 元数据契约化：MetaKey 从 mapping_keys.meta 导入
- 高内聚低耦合：修改字段只需修改对应文件
- IDE 完美支持：保留类型推断和代码补全
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import pandas as pd
from datetime import datetime

# 🚀 关键：直接导入原子常量，不碰 keys.py 总线
from alphaflow.core.acl.mappings.meta import (
    MetaKey,
    AKSHARE_DATE_TYPE_MAP,
    OBB_REPORT_TYPE_MAP,
)
from alphaflow.core.acl.mappings.enums import ReportPeriod, MarketType


# ==========================================
# 1. 数据槽位枚举 - ResearchPack 字段映射
# ==========================================

class PackSlot(str, Enum):
    """
    ResearchPack 数据槽位枚举 - 集中管理数据存储目标
    消除硬编码字符串，未来扩展只需修改此枚举
    """
    MARKET_DATA = "market_data"           # OHLCV 时间序列
    MARKET_METRICS = "market_metrics"     # 市值、PE、PB 等快照
    MARKET_DATA_META = "market_data_meta" # provider、columns 等元信息
    TECHNICALS = "technicals"            # 技术指标时间序列（兼容性）
    TECHNICAL_SUMMARY = "technical_summary"  # 技术面汇总（当前快照）
    FUNDAMENTALS = "fundamentals"         # 财务数据
    NEWS = "news"                        # 新闻列表
    EXTRA = "extra"                      # 扩展槽位
    CHARTS = "charts"                    # 图表


# ==========================================
# 2. 市场类型工具函数
# ==========================================

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
# 4. 辅助函数
# ==========================================

def get_field_value(
    item: Optional[Dict[str, Any]], 
    field_alias: str, 
    fallback_chains: Optional[Dict[str, List[str]]] = None
) -> Optional[float]:
    """
    极速字段提取器 (防腐层生效后的纯净版)
    """
    if not item:
        return None
        
    # 1. 优先极速匹配标准大写键
    val = item.get(field_alias)
    if val is not None and val != "" and not pd.isna(val):
        try:
            return float(val)
        except (ValueError, TypeError):
            pass
            
    # 2. 如果提供了回退链，则执行遍历
    if fallback_chains:
        candidates = fallback_chains.get(field_alias, [])
        for c in candidates:
            val = item.get(c)
            if val is not None and val != "" and not pd.isna(val):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue
                    
    return None


def find_closest_strictly(
    series: List[Dict], 
    anchor_date: Optional[datetime], 
    window: int = 20
) -> Optional[Dict]:
    """
    在数据序列中寻找与目标日期最接近的记录
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
    """
    if not item:
        return None
    
    # 优先级 1: DATE_TYPE_CODE (AkShare)
    code = item.get(MetaKey.DATE_TYPE_CODE)
    if code and code in AKSHARE_DATE_TYPE_MAP:
        return AKSHARE_DATE_TYPE_MAP[code]
    
    # 优先级 2: report_type (OBB)
    rt = item.get(MetaKey.REPORT_TYPE)
    if rt and rt in OBB_REPORT_TYPE_MAP:
        return OBB_REPORT_TYPE_MAP[rt]
    
    return None

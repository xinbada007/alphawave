"""
数据工具共享模块 - AlphaFlow Core 层
=====================================
全域统一词汇表 (Universal Vocabulary)
用于 AlphaFlow 组件间的数据定义和公共工具

设计哲学：
- 静态 Mixin 模式：利润表字段定义集中在 income_statement.py
- 元数据契约化：MetaKey 继承 MetaKeyMixin，实现单点真理源
- 高内聚低耦合：修改字段只需修改对应文件
- IDE 完美支持：保留类型推断和代码补全
"""

from enum import Enum  # 添加这行
from typing import Any, Dict, List, Optional
import pandas as pd
from datetime import datetime

# 🚀 基础枚举从 mapping_keys.enums 导入 (打破循环导入)
from alphaflow.core.mapping_keys.enums import ReportPeriod, MarketType

# 🚀 静态 Mixin 模式：从 mapping_keys 模块导入常量 Mixin
from alphaflow.core.mapping_keys.income_statement import IncomeStatementKey
from alphaflow.core.mapping_keys.balance_sheet import BalanceSheetKey
from alphaflow.core.mapping_keys.cash_flow import CashFlowKey
from alphaflow.core.mapping_keys.profile import ProfileKey as ProfileKeyMixin
from alphaflow.core.mapping_keys.estimates import EstimatesKey as EstimatesKeyMixin
from alphaflow.core.mapping_keys.share_stats import ShareStatsKey as ShareStatsKeyMixin
from alphaflow.core.mapping_keys.metrics import MetricsKey as MetricsKeyMixin
from alphaflow.core.mapping_keys.akshare_analysis import AkShareAnalysisKey

# 🚀 元数据常量继承 MetaKeyMixin，实现单点真理源
from alphaflow.core.mapping_keys.meta import MetaKeyMixin


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
# 2. 报表类型映射 (统一数据源)
# ==========================================

# AkShare DATE_TYPE_CODE -> ReportPeriod 映射
_AKSHARE_DATE_TYPE_MAP: Dict[str, ReportPeriod] = {
    "001": ReportPeriod.ANNUAL,        # 年报 (12个月)
    "002": ReportPeriod.SEMIANNUAL,    # 中报 (6个月)
    "003": ReportPeriod.QUARTERLY,     # 一季报 (3个月)
    "004": ReportPeriod.NINE_MONTHS,   # 三季报 (9个月)
}

# OBB report_type -> ReportPeriod 映射
_OBB_REPORT_TYPE_MAP: Dict[str, ReportPeriod] = {
    "annual": ReportPeriod.ANNUAL,
    "quarter": ReportPeriod.QUARTERLY,
}


# ==========================================
# 3. 元数据常量 (MetaKey) - 继承 MetaKeyMixin
# ==========================================
class MetaKey(MetaKeyMixin):
    """
    系统元数据/日期字段常量 (统一大写风格)
    通过继承 MetaKeyMixin 实现，保持与 META_MAPPING 的绝对同步！
    
    设计哲学：
    - 单点真理源：meta.py 中的 MetaKeyMixin 是唯一的常量定义处
    - 零硬编码：此处仅继承，不重复定义
    """
    pass


# ==========================================
# 4. 市场类型工具函数
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
# 5. 财务字段常量类 (Financial Key) - 静态 Mixin 模式
# ==========================================
class FinKey(IncomeStatementKey, BalanceSheetKey, CashFlowKey, AkShareAnalysisKey):
    """
    财务字段常量类 - 静态 Mixin 模式
    ============================================
    多重继承自 IncomeStatementKey、BalanceSheetKey、CashFlowKey，
    获取所有三大报表字段常量
    
    设计哲学：
    - 高内聚低耦合：每个报表字段定义集中在对应文件
    - IDE 完美支持：保留类型推断和代码补全
    - 单一数据源：修改字段只需修改对应文件
    """
    
    # ========== 环比增长率 (QOQ Growth - AkShare 特有) ==========
    REV_GROWTH_QOQ = "REV_GROWTH_QOQ"
    NI_GROWTH_QOQ = "NI_GROWTH_QOQ"
    
    # ========== 市场字段 (Market Fields - 港股特有) ==========
    MCAP_HK = "MCAP_HK"
    CURRENT_PRICE = "CURRENT_PRICE"
    
    # ========== 股本信息 ==========
    SHARES_H = "SHARES_H"
    AUTHORIZED_SHARES = "AUTHORIZED_SHARES"
    SHARES_AT_IPO = "SHARES_AT_IPO"
    
    # ========== 分红/拆股字段 ==========
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
    
    # ========== 第三方 API 预计算/分析指标 ==========
    ANA_ROE_ACTUAL = "ANA_ROE_ACTUAL"
    ANA_ROE_AVG = "ANA_ROE_AVG"
    ANA_NET_MARGIN = "ANA_NET_MARGIN"
    ANA_CURRENT_RATIO = "ANA_CURRENT_RATIO"
    ANA_REV_YOY = "ANA_REV_YOY"
    ANA_NI_YOY = "ANA_NI_YOY"


# ==========================================
# 6. 静态档案输出契约 (Profile Key)
# ==========================================
class ProfileKey(ProfileKeyMixin):
    """静态档案标准键 - 贪婪模式"""
    pass


# ==========================================
# 7. 分析师共识输出契约 (Consensus Key)
# ==========================================
class ConsensusKey(EstimatesKeyMixin):
    """分析师共识标准键"""
    TARGET_CURRENCY = "TARGET_CURRENCY"
    TARGET_SPREAD = "TARGET_SPREAD"
    UPSIDE_POTENTIAL = "UPSIDE_POTENTIAL"


# ==========================================
# 8. 股权结构输出契约 (ShareStats Key)
# ==========================================
class ShareStatsKey(ShareStatsKeyMixin):
    """股权结构与做空数据标准键"""
    pass


# ==========================================
# 9. 市场估值指标输出契约 (Metrics Key)
# ==========================================
class MetricsKey(MetricsKeyMixin):
    """市场估值指标标准键"""
    pass


# ==========================================
# 10. 股息成长输出契约 (Dividend Key)
# ==========================================
class DividendKey:
    """股息成长输出契约"""
    STATUS = "dividend_status"
    CURRENT_YIELD = "current_dividend_yield"
    DIVIDEND_CAGR = "dividend_cagr_3y"
    CONSECUTIVE_YEARS = "consecutive_growth_years"
    RECENT_PAYOUT = "recent_5_years_payout"
    RECENT_TIMELINE = "recent_timeline"
    SPECIAL_DIVIDEND = "has_special_dividend"


# ==========================================
# 11. 辅助函数
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
    if code and code in _AKSHARE_DATE_TYPE_MAP:
        return _AKSHARE_DATE_TYPE_MAP[code]
    
    # 优先级 2: report_type (OBB)
    rt = item.get(MetaKey.REPORT_TYPE)
    if rt and rt in _OBB_REPORT_TYPE_MAP:
        return _OBB_REPORT_TYPE_MAP[rt]
    
    return None

"""
数据工具共享模块 - AlphaFlow Core 层
=====================================
全域统一词汇表 (Universal Vocabulary)
用于 AlphaFlow 组件间的数据定义和公共工具

包含：
- PackSlot: 数据槽位枚举
- ReportPeriod: 财报周期枚举
- MetaKey: 系统元数据字段常量
- MarketType: 市场类型枚举
- FinKey: 财务字段常量类 (继承 IncomeStatementKey)
- ProfileKey: 静态档案输出契约
- ConsensusKey: 分析师共识输出契约
- DividendKey: 股息成长输出契约
- 辅助函数：字段提取、日期对齐等

设计哲学：
- 静态 Mixin 模式：利润表字段定义集中在 income_statement.py
- 高内聚低耦合：修改利润表字段只需修改 income_statement.py
- IDE 完美支持：保留类型推断和代码补全
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import pandas as pd
from datetime import datetime
# 🚀 静态 Mixin 模式：从 mapping_keys 模块导入常量 Mixin
from alphaflow.core.mapping_keys.income_statement import IncomeStatementKey
from alphaflow.core.mapping_keys.balance_sheet import BalanceSheetKey
from alphaflow.core.mapping_keys.cash_flow import CashFlowKey
from alphaflow.core.mapping_keys.profile import ProfileKey as ProfileKeyMixin
from alphaflow.core.mapping_keys.estimates import EstimatesKey as EstimatesKeyMixin
from alphaflow.core.mapping_keys.share_stats import ShareStatsKey as ShareStatsKeyMixin
from alphaflow.core.mapping_keys.metrics import MetricsKey as MetricsKeyMixin
from alphaflow.core.mapping_keys.akshare_analysis import AkShareAnalysisKey
# 注意：ShareStatsKey、MetricsKey 属于元数据字段，不属于 FinKey，由 META_MAPPING 管理


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
# 2. 报告周期枚举
# ==========================================

class ReportPeriod(str, Enum):
    """财报周期枚举 - 消除硬编码字符串"""
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"  # 半年报 (H1)
    ANNUAL = "annual"
    LATEST = "latest"  # 通常用于 snapshot 兜底


# ==========================================
# 3. 报表类型映射 (统一数据源)
# ==========================================

# AkShare DATE_TYPE_CODE -> ReportPeriod 映射
_AKSHARE_DATE_TYPE_MAP: Dict[str, ReportPeriod] = {
    "001": ReportPeriod.ANNUAL,
    "002": ReportPeriod.SEMIANNUAL,
    "003": ReportPeriod.QUARTERLY,
    "004": ReportPeriod.QUARTERLY,
}

# OBB report_type -> ReportPeriod 映射
_OBB_REPORT_TYPE_MAP: Dict[str, ReportPeriod] = {
    "annual": ReportPeriod.ANNUAL,
    "quarter": ReportPeriod.QUARTERLY,
}


class MetaKey:
    """系统元数据/日期字段常量 (统一大写风格)"""
    PERIOD_ENDING = "PERIOD_ENDING"    # 清洗后的统一会计期末日
    REPORT_DATE = "REPORT_DATE"        # 原始发布日
    START_DATE = "START_DATE"          # 报告起始日 (用于计算年化)
    DATE_TYPE_CODE = "DATE_TYPE_CODE"  # AkShare 报告类型码
    REPORT_TYPE = "REPORT_TYPE"        # 报告类型字段
    IS_CUMULATIVE = "IS_CUMULATIVE"    # 是否累积制


# ==========================================
# 4. 市场类型枚举
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
# 5. 财务字段常量类 (Financial Key) - 静态 Mixin 模式
# ==========================================
class FinKey(IncomeStatementKey, BalanceSheetKey, CashFlowKey, AkShareAnalysisKey):
    """
    财务字段常量类 - 静态 Mixin 模式
    ============================================
    多重继承自 IncomeStatementKey、BalanceSheetKey、CashFlowKey，
    获取所有三大报表字段常量
    
    注意：ShareStatsKey 属于元数据字段，由 META_MAPPING 管理
    
    设计哲学：
    - 高内聚低耦合：每个报表字段定义集中在对应文件
    - IDE 完美支持：保留类型推断和代码补全
    - 单一数据源：修改字段只需修改对应文件
    
    使用方式：
    - 利润表字段：FinKey.TOTAL_REVENUE, FinKey.NET_INCOME_CONSOLIDATED
    - 资产负债表字段：FinKey.TOTAL_ASSETS, FinKey.GOODWILL
    - 现金流量表字段：FinKey.OPERATING_CASH_FLOW, FinKey.FREE_CASH_FLOW
    - 别名：FinKey.OCF, FinKey.FCF
    """
    
    # ========== 效率与回报、增长率、市场估值、每股指标 ==========
    # 注意：以上字段已从 MetricsKey 继承
    # ROE, ROA, NET_MARGIN, GROSS_MARGIN -> 使用 MetricsKey.RETURN_ON_EQUITY 等
    # REV_GROWTH_YOY, NI_GROWTH_YOY -> 使用 MetricsKey.REVENUE_GROWTH 等
    # PE, PB, PS, PCF -> 使用 MetricsKey.PE_RATIO, PRICE_TO_BOOK 等
    # EPS, BPS, OCPS, DPS -> 使用 MetricsKey.EPS_TTM, BOOK_VALUE 等
    
    # ========== 环比增长率 (QOQ Growth - AkShare 特有) ==========
    REV_GROWTH_QOQ = "REV_GROWTH_QOQ"
    NI_GROWTH_QOQ = "NI_GROWTH_QOQ"
    
    # ========== 市场字段 (Market Fields - 港股特有) ==========
    MCAP_HK = "MCAP_HK"
    CURRENT_PRICE = "CURRENT_PRICE"
    
    # ========== 股本信息 (Share Information) ==========
    # 注意：SHARES 别名由 ShareStatsKey 提供，指向 SHARES_OUTSTANDING
    # 注意：LOT_SIZE 已从 ProfileKey 继承
    # 注意：PAYOUT_RATIO 已从 MetricsKey 继承
    SHARES_H = "SHARES_H"
    AUTHORIZED_SHARES = "AUTHORIZED_SHARES"
    SHARES_AT_IPO = "SHARES_AT_IPO"  # IPO 发行量
    
    # ========== 分红/拆股字段 (Dividend & Splits Fields) ==========
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
    
    # --- 新增：第三方 API 预计算/分析指标 (Analysis) ---
    # 统一增加 ANA_ 前缀，明确告知开发者这属于预计算指标，需做容错处理
    # 拆分原因：ROE_YEARLY 是成品（已年化），ROE_AVG 是半成品（未年化），需分别处理
    ANA_ROE_ACTUAL = "ANA_ROE_ACTUAL"  # 成品 - 已年化，如 ROE_YEARLY
    ANA_ROE_AVG = "ANA_ROE_AVG"          # 半成品 - 未年化 YTD，如 ROE_AVG
    ANA_NET_MARGIN = "ANA_NET_MARGIN"
    ANA_CURRENT_RATIO = "ANA_CURRENT_RATIO"
    ANA_REV_YOY = "ANA_REV_YOY"
    ANA_NI_YOY = "ANA_NI_YOY"


# ==========================================
# 6. 静态档案输出契约 (Profile Key) - 静态 Mixin 模式
# ==========================================
class ProfileKey(ProfileKeyMixin):
    """
    静态档案标准键 - 贪婪模式 (遵循正交萃取原则)
    用于 LLM 输出键名标准化
    
    静态 Mixin 模式：
    - 继承 ProfileKeyMixin，获取所有公司基本信息字段
    - 此处仅保留非 ProfileKeyMixin 字段
    
    设计哲学：
    - 贪婪提取 API Payload 中所有高价值金融字段
    - 不再人为规避 Task 间的重合
    - 股权结构独立为 ShareStatsKey，尊重金融客观事实
    """
    pass


# ==========================================
# 7. 分析师共识输出契约 (Consensus Key) - 静态 Mixin 模式
# ==========================================
class ConsensusKey(EstimatesKeyMixin):
    """
    分析师共识标准键 (全量保留)
    用于 LLM 输出键名标准化
    
    静态 Mixin 模式：
    - 继承 EstimatesKeyMixin，获取所有分析师共识字段
    - 此处仅保留非 EstimatesKeyMixin 字段
    
    设计哲学：
    - 仅保留分析师预测相关字段
    - 做空数据迁移至 ShareStatsKey
    """
    # --- 以下字段未在 EstimatesKeyMixin 中定义，保留在此处 ---
    TARGET_CURRENCY = "TARGET_CURRENCY"
    # 计算字段
    TARGET_SPREAD = "TARGET_SPREAD"        # 目标价分歧度 (high-low)/median
    UPSIDE_POTENTIAL = "UPSIDE_POTENTIAL"  # 潜在涨幅 (target-price)/current


# ==========================================
# 8. 股权结构输出契约 (ShareStats Key) - 静态 Mixin 模式
# ==========================================
class ShareStatsKey(ShareStatsKeyMixin):
    """
    股权结构与做空数据标准键
    用于 LLM 输出键名标准化
    
    静态 Mixin 模式：
    - 继承 ShareStatsKeyMixin，获取所有股权结构与做空数据字段
    """
    pass


# ==========================================
# 9. 市场估值指标输出契约 (Metrics Key) - 静态 Mixin 模式
# ==========================================
class MetricsKey(MetricsKeyMixin):
    """
    市场估值指标标准键
    用于 LLM 输出键名标准化
    
    静态 Mixin 模式：
    - 继承 MetricsKeyMixin，获取所有估值指标字段
    """
    pass


# ==========================================
# 10. 股息成长输出契约 (Dividend Key)
# ==========================================
class DividendKey:
    """
    股息成长输出契约
    用于 LLM 输出键名标准化
    """
    STATUS = "dividend_status"
    CURRENT_YIELD = "current_dividend_yield"
    DIVIDEND_CAGR = "dividend_cagr_3y"
    CONSECUTIVE_YEARS = "consecutive_growth_years"
    RECENT_PAYOUT = "recent_5_years_payout"
    RECENT_TIMELINE = "recent_timeline"
    SPECIAL_DIVIDEND = "has_special_dividend"


# ==========================================
# 9. 辅助函数
# ==========================================

def get_field_value(
    item: Optional[Dict[str, Any]], 
    field_alias: str, 
    fallback_chains: Optional[Dict[str, List[str]]] = None
) -> Optional[float]:
    """
    极速字段提取器 (防腐层生效后的纯净版)
    优先 O(1) 命中标准键名。兼容传入 fallback_chains 供遗留模块使用。
    """
    if not item:
        return None
        
    # 1. 优先极速匹配标准大写键 (防腐层已生效的情况)
    val = item.get(field_alias)
    if val is not None and val != "" and not pd.isna(val):
        try:
            return float(val)
        except (ValueError, TypeError):
            pass
            
    # 2. 如果提供了回退链 (如 market_data 模块)，则执行遍历
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
    
    Args:
        item: 报表记录 Dict
    
    Returns:
        ReportPeriod 枚举值，或 None (无法判断)
    
    注意: 
    - 离散制(美股)的 "quarterly" = 单季数据
    - 累积制(港股/A股)的 "quarterly" = YTD累计数据 (Q1/Q3)
    下游使用时需根据 is_cumulative 自行判断如何处理
    """
    if not item:
        return None
    
    # 优先级 1: DATE_TYPE_CODE (AkShare) - 使用映射字典
    code = item.get(MetaKey.DATE_TYPE_CODE)
    if code and code in _AKSHARE_DATE_TYPE_MAP:
        return _AKSHARE_DATE_TYPE_MAP[code]
    
    # 优先级 2: report_type (OBB) - 使用映射字典
    rt = item.get(MetaKey.REPORT_TYPE)
    if rt and rt in _OBB_REPORT_TYPE_MAP:
        return _OBB_REPORT_TYPE_MAP[rt]
    
    return None
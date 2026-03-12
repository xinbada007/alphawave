"""
Fundamental Keys - 财务数据键名常量
===================================
从 Core 层导入全域词汇表，确保全系统一致性

设计哲学：
- 消费端使用纯净的 1:1 映射
- 防腐层已在 Core 层完成所有 Provider 猜测
- 股权结构从 Profile 移出，建立独立的 ShareStats 消费单
"""

# 从 Core 层导入全域词汇表
from alphaflow.core.data_utils import ProfileKey, ConsensusKey, DividendKey, ShareStatsKey


# ==========================================
# Insider 内部人交易键 (本地定义)
# ==========================================
class InsiderKey:
    """
    内部人交易输出契约
    用于 LLM 输出键名标准化
    """
    # 基础字段
    NAME = "name"
    TITLE = "title"
    TRANSACTION_DATE = "transaction_date"
    TRANSACTION_TYPE = "transaction_type"
    SHARES = "shares"
    PRICE = "price"
    VALUE = "value"
    SHARES_OWNED = "shares_owned"
    INSIDER_RELATION = "insider_relation"
    
    # 汇总字段
    STATUS = "insider_status"
    NET_SHARES = "net_shares"
    NET_VALUE = "net_value"
    AVG_PRICE = "avg_price"
    ACTIVE_INSIDERS = "active_insiders"
    SUMMARY = "insider_summary"


# ==========================================
# Health Tag 配置 (本地定义)
# ==========================================
class HealthTagConfig:
    """
    健康/风险标签配置
    用于基本面健康评估
    """
    # 健康标签
    HEALTHY = "healthy"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"
    
    # 标签阈值
    ROE_HEALTHY_THRESHOLD = 15.0
    ROE_WATCH_THRESHOLD = 10.0
    NET_MARGIN_HEALTHY_THRESHOLD = 10.0
    DEBT_TO_EQUITY_WARNING_THRESHOLD = 2.0
    CURRENT_RATIO_HEALTHY_THRESHOLD = 1.5


# ==========================================
# Insider 噪音关键词 (本地定义)
# ==========================================
INSIDER_NOISE_KEYWORDS = {
    # 英文噪音词
    "acquisition", "exercise", "grant", "award", "gift", "inheritance",
    "trust", "divorce", "estate", "plan", "automatic", "rule 10b5",
    
    # 中文噪音词
    "行权", "授予", "赠与", "继承", "信托", "离婚", "遗产", "自动", "计划",
}


# ==========================================
# Profile 提取链 - 贪婪模式 (遵循正交萃取原则)
# 贪婪提取 API Payload 中所有高价值金融字段
# ==========================================
PROFILE_EXTRACTOR_CHAINS = {
    # 公司基本信息
    ProfileKey.SECTOR: ["SECTOR"],
    ProfileKey.INDUSTRY: ["INDUSTRY"],
    ProfileKey.NAME: ["NAME"],
    ProfileKey.DESC: ["DESC"],
    ProfileKey.EMPLOYEES: ["EMPLOYEES"],
    ProfileKey.EXCHANGE: ["EXCHANGE"],
    ProfileKey.LISTING_DATE: ["LISTING_DATE"],
    ProfileKey.CHAIRMAN: ["CHAIRMAN"],
    ProfileKey.BOARD: ["BOARD"],
    ProfileKey.FISCAL_YEAR_END: ["FISCAL_YEAR_END"],
    ProfileKey.INCORPORATION: ["INCORPORATION"],
    ProfileKey.WEBSITE: ["WEBSITE"],
    ProfileKey.LOT_SIZE: ["LOT_SIZE"],
    ProfileKey.ISSUE_PRICE: ["ISSUE_PRICE"],
    
    # 🚀 贪婪新增的高价值特征
    ProfileKey.HQ_COUNTRY: ["HQ_COUNTRY"],
    ProfileKey.ISSUE_TYPE: ["ISSUE_TYPE"],
    ProfileKey.CURRENCY: ["CURRENCY"],
    ProfileKey.MARKET_CAP: ["MARKET_CAP", "MCAP", "MCAP_HK"],
    ProfileKey.CURRENT_PRICE: ["CURRENT_PRICE"],
    ProfileKey.DIVIDEND_YIELD: ["DIVIDEND_YIELD"],
    ProfileKey.INSTITUTION_OWNERSHIP: ["INSTITUTION_OWNERSHIP"],
    ProfileKey.INSIDER_OWNERSHIP: ["INSIDER_OWNERSHIP"],
    ProfileKey.INSTITUTIONS_COUNT: ["INSTITUTIONS_COUNT"],
    
    # 🚀 股权精确化字段 (语义更名)
    ProfileKey.SHARES_OUTSTANDING: ["SHARES_OUTSTANDING"],
    ProfileKey.SHARES_FLOAT: ["SHARES_FLOAT"],
    ProfileKey.SHARES_IMPLIED: ["SHARES_IMPLIED"],
    ProfileKey.SHARES_SHORT: ["SHARES_SHORT"],
    ProfileKey.BETA: ["BETA"],
    
    # 🚀 并集扩充：AkShare 独有或重叠的高价值字段
    ProfileKey.COMPANY_NAME_ENG: ["COMPANY_NAME_ENG"],
    ProfileKey.SH_HK_CONNECT: ["SH_HK_CONNECT"],
    ProfileKey.SZ_HK_CONNECT: ["SZ_HK_CONNECT"],
}


# ==========================================
# Consensus 提取链 - 纯净 1:1 映射
# 分析师共识标准键
# ==========================================
CONSENSUS_EXTRACTOR_CHAINS = {
    # 目标价
    ConsensusKey.TARGET_PRICE: ["TARGET_PRICE"],
    ConsensusKey.TARGET_MEDIAN: ["TARGET_MEDIAN"],
    ConsensusKey.TARGET_HIGH: ["TARGET_HIGH"],
    ConsensusKey.TARGET_LOW: ["TARGET_LOW"],
    ConsensusKey.CURRENT_PRICE: ["CURRENT_PRICE"],
    ConsensusKey.RECOMMENDATION_MEAN: ["RECOMMENDATION_MEAN"],
    ConsensusKey.TARGET_CURRENCY: ["TARGET_CURRENCY"],
    ConsensusKey.CONSENSUS_RATING: ["CONSENSUS_RATING"],
    ConsensusKey.NUMBER_OF_ANALYSTS: ["NUMBER_OF_ANALYSTS"],
}


# ==========================================
# Share Stats 提取链 - 纯净 1:1 映射
# 资本结构与空头数据标准键
# ==========================================
SHARE_STATS_EXTRACTOR_CHAINS = {
    ShareStatsKey.SHARES: ["SHARES"],
    ShareStatsKey.FLOAT_SHARES: ["FLOAT_SHARES"],
    ShareStatsKey.IMPLIED_SHARES: ["IMPLIED_SHARES"],
    ShareStatsKey.INSTITUTION_OWNERSHIP: ["INSTITUTION_OWNERSHIP"],
    ShareStatsKey.INSTITUTION_FLOAT_OWNERSHIP: ["INSTITUTION_FLOAT_OWNERSHIP"],
    ShareStatsKey.INSIDER_OWNERSHIP: ["INSIDER_OWNERSHIP"],
    ShareStatsKey.INSTITUTIONS_COUNT: ["INSTITUTIONS_COUNT"],
    ShareStatsKey.SHORT_INTEREST: ["SHORT_INTEREST"],
    ShareStatsKey.SHORT_FLOAT: ["SHORT_FLOAT"],
    ShareStatsKey.SHORT_RATIO: ["SHORT_RATIO"],
}


# ==========================================
# Dividend 提取链 - 纯净 1:1 映射
# ==========================================
DIVIDEND_EXTRACTOR_CHAINS = {
    # 分红状态
    DividendKey.STATUS: ["dividend_status"],
    DividendKey.CURRENT_YIELD: ["DIVIDEND_YIELD"],
    
    # 分红成长
    DividendKey.DIVIDEND_CAGR: ["dividend_cagr_3y"],
    DividendKey.CONSECUTIVE_YEARS: ["consecutive_growth_years"],
    
    # 历史派息
    DividendKey.RECENT_PAYOUT: ["recent_5_years_payout"],
    DividendKey.RECENT_TIMELINE: ["recent_timeline"],
}


# ==========================================
# 导出列表
# ==========================================
__all__ = [
    "ProfileKey",
    "InsiderKey",
    "ConsensusKey", 
    "DividendKey",
    "ShareStatsKey",
    "HealthTagConfig",
    "PROFILE_EXTRACTOR_CHAINS",
    "CONSENSUS_EXTRACTOR_CHAINS",
    "SHARE_STATS_EXTRACTOR_CHAINS",
    "DIVIDEND_EXTRACTOR_CHAINS",
    "INSIDER_NOISE_KEYWORDS",
]
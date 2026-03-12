"""
全域数据防腐契约 (Standard Financial Record)
=============================================
基于 Pydantic V2 的强类型数据契约

设计哲学：
- 静态 Mixin 模式：利润表字段从 IncomeStatementRecord 继承
- 高内聚低耦合：修改利润表字段只需修改 income_statement.py
- IDE 完美支持：保留类型推断和代码补全
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, Optional
from alphaflow.core.data_utils import MetaKey, ReportPeriod
from alphaflow.core.context import GlobalContext  # 🚀 引入全局上下文，实现环境上下文模式
# 🚀 静态 Mixin 模式：从 mapping_keys 模块导入 Pydantic 模型 Mixin
from alphaflow.core.mapping_keys.income_statement import IncomeStatementRecord
from alphaflow.core.mapping_keys.balance_sheet import BalanceSheetRecord
from alphaflow.core.mapping_keys.cash_flow import CashFlowRecord
from alphaflow.core.mapping_keys.share_stats import ShareStatsRecord
from alphaflow.core.mapping_keys.profile import ProfileRecord
from alphaflow.core.mapping_keys.estimates import EstimatesRecord
from alphaflow.core.mapping_keys.metrics import MetricsRecord
from alphaflow.core.mapping_keys.akshare_analysis import AkShareAnalysisRecord


class StandardFinancialRecord(
    IncomeStatementRecord, BalanceSheetRecord, CashFlowRecord, 
    ShareStatsRecord, ProfileRecord, EstimatesRecord, MetricsRecord,
    AkShareAnalysisRecord
):
    """
    全域数据防腐契约
    强类型校验所有将被下游公式计算的数值字段，同时通过 extra="allow" 兜底 API 的非标长尾文本。
    
    数据隔离设计：
    - raw_provider_data: 存储原始 Provider 数据，仅供内部追溯，序列化时自动剔除
    - consumed_keys: 已映射的原始键名，防止脏键复活
    
    静态 Mixin 模式：
    - 继承 IncomeStatementRecord，获取所有利润表字段
    - 继承 ProfileRecord，获取公司基本信息字段
    - 继承 EstimatesRecord，获取分析师共识字段
    - 此处仅保留非利润表、非 Profile、非 Estimates 字段
    """
    model_config = ConfigDict(extra="allow", coerce_numbers_to_str=False, populate_by_name=True)
    
    # --- 系统对齐元数据 (统一大写风格) ---
    PERIOD_ENDING: Optional[str] = Field(default=None)
    REPORT_TYPE: Optional[ReportPeriod] = None
    IS_CUMULATIVE: Optional[bool] = None
    
    # --- 原始数据隔离槽位 (序列化时动态剔除) ---
    # 🚀 移除 exclude=True，将控制权交给 dump_for_pack() 动态决策
    raw_provider_data: Dict[str, Any] = Field(default_factory=dict)
    
    # 🚀 开放世界透传槽位：存放未被映射的原始字段
    # 由 Adapter 的 Task 黑名单决定是否注入
    unmapped_others: Dict[str, Any] = Field(default_factory=dict)
    
    # --- 静态档案与公司特征 (Profile) 已移至 ProfileRecord ---
    # SECTOR, INDUSTRY_CATEGORY, NAME, LONG_DESCRIPTION, EMPLOYEES, STOCK_EXCHANGE, COMPANY_URL, BETA, 
    # HQ_COUNTRY, ISSUE_TYPE, CURRENCY, MARKET_CAP, DIVIDEND_YIELD,
    # SHARES_OUTSTANDING, SHARES_FLOAT, SHARES_IMPLIED_OUTSTANDING, SHARES_SHORT
    # LISTING_DATE, CHAIRMAN, BOARD, FISCAL_YEAR_END, INCORPORATION,
    # LOT_SIZE, ISSUE_PRICE, COMPANY_NAME_ENG, SH_HK_CONNECT, SZ_HK_CONNECT
    # 均从 ProfileRecord 继承
    
    # --- 以下为非 Profile 字段 (保留在此处) ---
    
    # ==========================================
    # 📊 效率与回报、增长率、市场估值、每股指标、股息
    # 注意：以上字段已从 MetricsRecord 继承
    # RETURN_ON_EQUITY, RETURN_ON_ASSETS, PROFIT_MARGIN, GROSS_MARGIN 等
    # EARNINGS_GROWTH, REVENUE_GROWTH 等
    # PE_RATIO, PRICE_TO_BOOK, ENTERPRISE_VALUE 等
    # EPS_TTM, BOOK_VALUE, REVENUE_PER_SHARE 等
    # DIVIDEND_YIELD, PAYOUT_RATIO 等
    # ==========================================
    
    # ==========================================
    # 📊 港股特有字段 (保留在此处，未在 MetricsRecord 中定义)
    # ==========================================
    MCAP_HK: Optional[float] = None        # 港股市值
    SHARES_H: Optional[float] = None       # H股股本
    AUTHORIZED_SHARES: Optional[float] = None
    SHARES_AT_IPO: Optional[float] = None  # IPO 发行量
    DIVIDEND_AMOUNT: Optional[float] = None
    
    # ==========================================
    # 📊 分析师共识 (Analyst Consensus)
    # 注意：TARGET_PRICE, TARGET_MEDIAN, TARGET_HIGH, TARGET_LOW,
    # RECOMMENDATION_MEAN, CONSENSUS_RATING, NUMBER_OF_ANALYSTS, CURRENT_PRICE
    # 已从 EstimatesRecord 继承
    # ==========================================
    TARGET_CURRENCY: Optional[str] = None
    
    # ==========================================
    # 📊 第三方 API 预计算/分析指标 (Analysis)
    # ==========================================
    ANA_ROE_ACTUAL: Optional[float] = None
    ANA_ROE_AVG: Optional[float] = None
    ANA_NET_MARGIN: Optional[float] = None
    ANA_CURRENT_RATIO: Optional[float] = None
    ANA_REV_YOY: Optional[float] = None
    ANA_NI_YOY: Optional[float] = None
    
    # ==========================================
    # 📊 股息与公司事件 (Dividend & Events)
    # ==========================================
    EX_DIVIDEND_DATE: Optional[str] = None
    DIVIDEND_PLAN: Optional[str] = None
    ANNOUNCE_DATE: Optional[str] = None
    PAYMENT_DATE: Optional[str] = None
    FISCAL_YEAR: Optional[str] = None
    RECORD_DATE: Optional[str] = None
    DIVIDEND_TYPE: Optional[str] = None
    SPLIT_DATE: Optional[str] = None
    SPLIT_RATIO: Optional[float] = None
    
    def dump_for_pack(self) -> Dict[str, Any]:
        """环境上下文序列化"""
        is_debug = GlobalContext().get("DEBUG", False)
        exclude_set = set() if is_debug else {"raw_provider_data"}
        
        # 🚀 既然 Adapter 已经挡住了所有的 NaN，没有被赋值的字段全是纯粹的 None
        # 原生的 exclude_none=True 足以完美解决所有问题，0 冗余！
        data = self.model_dump(exclude_none=True, exclude=exclude_set)
        
        # 优雅清理：如果 unmapped_others 为空字典，不污染 LLM 视线
        if not data.get("unmapped_others"):
            data.pop("unmapped_others", None)
        
        # 补充元数据
        if self.REPORT_TYPE:
            data[MetaKey.REPORT_TYPE] = self.REPORT_TYPE.value
        if self.IS_CUMULATIVE is not None:
            data[MetaKey.IS_CUMULATIVE] = self.IS_CUMULATIVE
            
        return data

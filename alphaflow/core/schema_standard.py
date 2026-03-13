"""
全域数据防腐契约 (Standard Financial Record)
=============================================
基于 Pydantic V2 的强类型数据契约

设计哲学：
- 极致纯粹：StandardFinancialRecord 是"集大成者"容器，零硬编码
- 静态 Mixin 模式：所有字段从 Mixin 继承
- Meta 第一顺位：MetaRecord 提供系统骨架，业务 Mixin 提供血肉
- IDE 完美支持：保留类型推断和代码补全
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict
from alphaflow.core.context import GlobalContext

# 🚀 Meta 骨架：系统元数据字段 (第一顺位，确保基础字段存在)
from alphaflow.core.mapping_keys.meta import MetaRecord

# 🚀 业务血肉：财务报表字段
from alphaflow.core.mapping_keys.income_statement import IncomeStatementRecord
from alphaflow.core.mapping_keys.balance_sheet import BalanceSheetRecord
from alphaflow.core.mapping_keys.cash_flow import CashFlowRecord
from alphaflow.core.mapping_keys.share_stats import ShareStatsRecord
from alphaflow.core.mapping_keys.profile import ProfileRecord
from alphaflow.core.mapping_keys.estimates import EstimatesRecord
from alphaflow.core.mapping_keys.metrics import MetricsRecord
from alphaflow.core.mapping_keys.akshare_analysis import AkShareAnalysisRecord


class StandardFinancialRecord(
    MetaRecord,               # 🚀 第一顺位：系统骨架 (PERIOD_ENDING, REPORT_TYPE 等)
    IncomeStatementRecord,    # 业务血肉：利润表
    BalanceSheetRecord,       # 业务血肉：资产负债表
    CashFlowRecord,           # 业务血肉：现金流量表
    ShareStatsRecord,         # 业务血肉：股权结构
    ProfileRecord,            # 业务血肉：公司档案
    EstimatesRecord,          # 业务血肉：分析师共识
    MetricsRecord,            # 业务血肉：估值指标
    AkShareAnalysisRecord     # 业务血肉：AkShare 分析指标
):
    """
    全域数据防腐契约 - 极致纯粹的集大成者
    
    所有字段均从 Mixin 继承，此处零硬编码：
    - MetaRecord: PERIOD_ENDING, REPORT_TYPE, IS_CUMULATIVE, START_DATE, DATE_TYPE_CODE
    - IncomeStatementRecord: TOTAL_REVENUE, NET_INCOME 等
    - BalanceSheetRecord: TOTAL_ASSETS, TOTAL_LIABILITIES 等
    - ... (其他业务 Mixin)
    
    数据隔离设计：
    - raw_provider_data: 存储原始 Provider 数据，仅供内部追溯
    - unmapped_others: 存放未被映射的原始字段
    """
    model_config = ConfigDict(
        extra="allow",
        coerce_numbers_to_str=False,
        populate_by_name=True,
        use_enum_values=True
    )

    # --- 原始数据隔离槽位 ---
    raw_provider_data: Dict[str, Any] = Field(default_factory=dict)
    unmapped_others: Dict[str, Any] = Field(default_factory=dict)
    
    # 注意：所有元数据字段 (PERIOD_ENDING, REPORT_TYPE, IS_CUMULATIVE, START_DATE, DATE_TYPE_CODE)
    # 已由 MetaRecord 提供，此处无需重复定义！

    def dump_for_pack(self) -> Dict[str, Any]:
        """环境上下文序列化：极简、优雅的终极形态"""
        is_debug = GlobalContext().get("DEBUG", False)
        exclude_set = set() if is_debug else {"raw_provider_data"}

        # Pydantic 自动处理：去除 None、Enum 转 str、处理 extra kwargs
        data = self.model_dump(exclude_none=True, exclude=exclude_set)

        # 优雅清理：如果 unmapped_others 为空字典，不污染 LLM 视线
        if not data.get("unmapped_others"):
            data.pop("unmapped_others", None)

        return data

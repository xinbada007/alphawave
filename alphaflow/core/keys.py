"""
AlphaFlow 全域语义访问层 (Static Semantic Access Layer 2.0)
=======================================================
纯净总线：本文件严禁定义任何实际的 Key 字符串，仅负责领域路由的组装。

设计原则：
- 原子聚合：只从 mapping_keys 子模块导入，不定义新常量
- 零字符串定义：所有字符串常量必须在原子层定义
- 类型安全：100% Type-Safe Namespace
- 业务层入口：仅供 Collectors, Processors, Facade 使用
"""

from typing import Type

# 财务报表 Key 类（原子层导入）
from alphaflow.core.acl.mappings.income_statement import IncomeStatementKey
from alphaflow.core.acl.mappings.balance_sheet import BalanceSheetKey
from alphaflow.core.acl.mappings.cash_flow import CashFlowKey
from alphaflow.core.acl.mappings.metrics import MetricsKey
from alphaflow.core.acl.mappings.meta import MetaKey
from alphaflow.core.acl.mappings.profile import ProfileKey
from alphaflow.core.acl.mappings.estimates import EstimatesKey
from alphaflow.core.acl.mappings.share_stats import ShareStatsKey
from alphaflow.core.acl.mappings.akshare_analysis import AkShareAnalysisKey


class Key:
    """AlphaFlow 统一字段访问入口 (100% Type-Safe Namespace)"""
    
    # 财务报表
    income: Type[IncomeStatementKey] = IncomeStatementKey
    balance: Type[BalanceSheetKey] = BalanceSheetKey
    cash: Type[CashFlowKey] = CashFlowKey
    
    # 市场指标与元数据
    metrics: Type[MetricsKey] = MetricsKey
    meta: Type[MetaKey] = MetaKey
    
    # 公司与股权信息
    profile: Type[ProfileKey] = ProfileKey
    share_stats: Type[ShareStatsKey] = ShareStatsKey
    
    # 分析与预期
    analysis: Type[AkShareAnalysisKey] = AkShareAnalysisKey
    estimates: Type[EstimatesKey] = EstimatesKey
    consensus: Type[EstimatesKey] = EstimatesKey  # 别名

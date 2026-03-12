"""
映射键定义模块 (Mapping Keys Module)
=====================================
存放财务报表字段定义、映射表和常量

设计哲学：
- 静态 Mixin 模式：每个报表一个独立文件
- 高内聚低耦合：修改某个报表字段只需修改对应文件
- IDE 完美支持：保留类型推断和代码补全

模块结构：
- income_statement.py: 利润表字段定义
- balance_sheet.py: 资产负债表字段定义
- cash_flow.py: 现金流量表字段定义 (未来)
"""

from alphaflow.core.mapping_keys.income_statement import (
    INCOME_STATEMENT_MAPPING,
    IncomeStatementKey,
    IncomeStatementRecord,
)
from alphaflow.core.mapping_keys.balance_sheet import (
    BALANCE_SHEET_MAPPING,
    BalanceSheetKey,
    BalanceSheetRecord,
)
from alphaflow.core.mapping_keys.cash_flow import (
    CASH_FLOW_MAPPING,
    CashFlowKey,
    CashFlowRecord,
)
from alphaflow.core.mapping_keys.share_stats import (
    SHARE_STATS_MAPPING,
    ShareStatsKey,
    ShareStatsRecord,
)

__all__ = [
    # 利润表
    "INCOME_STATEMENT_MAPPING",
    "IncomeStatementKey",
    "IncomeStatementRecord",
    # 资产负债表
    "BALANCE_SHEET_MAPPING",
    "BalanceSheetKey",
    "BalanceSheetRecord",
    # 现金流量表
    "CASH_FLOW_MAPPING",
    "CashFlowKey",
    "CashFlowRecord",
    # 股权结构与做空数据
    "SHARE_STATS_MAPPING",
    "ShareStatsKey",
    "ShareStatsRecord",
]

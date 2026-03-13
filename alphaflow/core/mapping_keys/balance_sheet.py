"""
资产负债表核心契约 (Balance Sheet Domain)
==========================================
单一数据源 (Single Source of Truth)

设计哲学：
- 高内聚低耦合：所有资产负债表相关定义集中于此
- 静态 Mixin 模式：保留 IDE 类型推断和静态检查
- 严格一一映射：每个原始字段只映射一个标准字段

更新日志：
- 2026-03-11: 重构港股映射，基于 AkShare 港股资产负债表字段逐一审计
              采用架构师裁决的标准字段命名，符合 IFRS/HKFRS 规范
              修正致命错误：应付票据拆分、流动负债合计纠正
              合并 OBB 和 AkShare 映射，确保一一映射
              修复 V1 遗留 Bug：NONCONTROLLING_INTERESTS 和 TOTAL_EQUITY_CONSOLIDATED
              新增资产质量、CapEx 生命周期、隐藏杠杆、AOCI 字段
- 2026-03-13: 新增审计字段：LONG_TERM_EQUITY_INVESTMENT、COMMERCIAL_PAPER、OTHER_CURRENT_BORROWINGS
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


# ==========================================
# 1. OBB/AkShare → 标准字段映射表 (严格一一映射)
# 用于 adapters.py 的 FINANCIAL_MAPPING 合并
# ==========================================
BALANCE_SHEET_MAPPING: Dict[str, Dict[str, List[str]]] = {
    # ==========================================
    # 📊 流动资产 (Current Assets)
    # ==========================================
    "CASH_AND_CASH_EQUIVALENTS": {
        "obb": ["cash_and_cash_equivalents"],
        "akshare": ["现金及等价物"]
    },
    "CASH_ONLY": {
        "obb": ["cash_financial"],
        "akshare": []
    },
    "CASH_EQUIVALENTS": {
        "obb": ["cash_equivalents"],
        "akshare": []
    },
    "CASH_CASH_EQUIV_ST_INVEST": {
        "obb": ["cash_cash_equivalents_and_short_term_investments"],
        "akshare": []
    },
    "RESTRICTED_CASH": {
        "obb": [],
        "akshare": ["受限制存款及现金"]
    },
    "SHORT_TERM_DEPOSITS": {
        "obb": [],
        "akshare": ["短期存款"]
    },
    "LONG_TERM_DEPOSITS": {
        "obb": [],
        "akshare": ["中长期存款"]
    },
    "SHORT_TERM_INVESTMENTS": {
        "obb": ["short_term_investments"],
        "akshare": ["短期投资"]
    },
    "TRADING_FINANCIAL_ASSETS_CURRENT": {
        "obb": [],
        "akshare": ["交易性金融资产(流动)"]
    },
    "FINANCIAL_ASSETS_AT_FAIR_VALUE_CURRENT": {
        "obb": ["financial_assets_designatedas_fair_value_through_profitor_loss_total"],
        "akshare": ["指定以公允价值记账之金融资产(流动)"]
    },
    "OTHER_FINANCIAL_ASSETS_CURRENT": {
        "obb": [],
        "akshare": ["其他金融资产(流动)"]
    },
    "ACCOUNTS_RECEIVABLE": {
        "obb": ["accounts_receivable"],
        "akshare": ["应收帐款"]
    },
    "NET_RECEIVABLES": {
        "obb": ["net_receivables"],
        "akshare": []
    },
    "RECEIVABLES_FROM_RELATED_PARTIES": {
        "obb": [],
        "akshare": ["应收关联方款项"]
    },
    "PREPAYMENTS": {
        "obb": [],
        "akshare": ["预付款项"]
    },
    "PREPAYMENTS_AND_OTHER_RECEIVABLES": {
        "obb": [],
        "akshare": ["预付款按金及其他应收款"]
    },
    "INVENTORIES": {
        "obb": ["inventories"],
        "akshare": ["存货"]
    },
    "RAW_MATERIALS": {
        "obb": ["raw_materials"],
        "akshare": []
    },
    "WORK_IN_PROCESS": {
        "obb": ["work_in_process"],
        "akshare": []
    },
    "FINISHED_GOODS": {
        "obb": ["finished_goods"],
        "akshare": []
    },
    "HELD_TO_MATURITY_INVESTMENTS_CURRENT": {
        "obb": [],
        "akshare": ["持有至到期投资(流动)"]
    },
    "ASSETS_HELD_FOR_SALE": {
        "obb": [],
        "akshare": ["持作出售的资产(流动)"]
    },
    "DERIVATIVE_FINANCIAL_ASSETS_CURRENT": {
        "obb": ["hedging_assets_current"],
        "akshare": ["衍生金融工具-资产(流动)"]
    },
    "OTHER_CURRENT_ASSETS": {
        "obb": ["other_current_assets"],
        "akshare": []
    },
    "TOTAL_CURRENT_ASSETS": {
        "obb": ["total_current_assets"],
        "akshare": ["流动资产合计"]
    },

    # ==========================================
    # 📊 非流动资产 (Non-Current Assets)
    # ==========================================
    "PLANT_PROPERTY_EQUIPMENT_NET": {
        "obb": ["plant_property_equipment_net"],
        "akshare": ["物业厂房及设备", "固定资产"]
    },
    "PLANT_PROPERTY_EQUIPMENT_GROSS": {
        "obb": ["plant_property_equipment_gross"],
        "akshare": ["固定资产原值"]
    },
    "LAND_AND_IMPROVEMENTS": {
        "obb": ["land_and_improvements"],
        "akshare": []
    },
    "BUILDINGS_AND_IMPROVEMENTS": {
        "obb": ["buildings_and_improvements"],
        "akshare": []
    },
    "MACHINERY_FURNITURE_EQUIPMENT": {
        "obb": ["machinery_furniture_equipment"],
        "akshare": []
    },
    "OTHER_PROPERTIES": {
        "obb": ["other_properties"],
        "akshare": []
    },
    "INVESTMENT_PROPERTIES": {
        "obb": ["properties"],
        "akshare": ["投资物业"]
    },
    "LAND_USE_RIGHTS": {
        "obb": [],
        "akshare": ["土地使用权"]
    },
    "CONSTRUCTION_IN_PROGRESS": {
        "obb": [],
        "akshare": ["在建工程"]
    },
    "GOODWILL": {
        "obb": ["goodwill"],
        "akshare": []
    },
    "INTANGIBLE_ASSETS": {
        "obb": ["other_intangible_assets"],
        "akshare": ["无形资产"]
    },
    "INTERESTS_IN_ASSOCIATES": {
        "obb": ["investments_and_advances"],
        "akshare": ["联营公司权益"]
    },
    "LONG_TERM_EQUITY_INVESTMENT": {
        "obb": ["long_term_equity_investment"],
        "akshare": []
    },
    "TRADING_FINANCIAL_ASSETS_NON_CURRENT": {
        "obb": ["investmentin_financial_assets"],
        "akshare": ["交易性金融资产(非流动)"]
    },
    "INTERESTS_IN_JOINT_VENTURES": {
        "obb": [],
        "akshare": ["合营公司权益"]
    },
    "REDEEMABLE_INSTRUMENTS_IN_ASSOCIATES": {
        "obb": [],
        "akshare": ["于联营公司可赎回工具的投资"]
    },
    "AVAILABLE_FOR_SALE_INVESTMENTS": {
        "obb": ["available_for_sale_securities"],
        "akshare": ["可供出售投资"]
    },
    "HELD_TO_MATURITY_INVESTMENTS": {
        "obb": [],
        "akshare": ["持有至到期投资"]
    },
    "FINANCIAL_ASSETS_AT_FAIR_VALUE": {
        "obb": ["financial_assets"],
        "akshare": ["指定以公允价值记账之金融资产"]
    },
    "OTHER_NON_CURRENT_ASSETS": {
        "obb": ["other_non_current_assets"],
        "akshare": ["其他非流动资产"]
    },
    "OTHER_NON_CURRENT_ASSETS_ITEMS": {
        "obb": [],
        "akshare": ["非流动资产其他项目"]
    },
    "TOTAL_NON_CURRENT_ASSETS": {
        "obb": ["total_non_current_assets"],
        "akshare": ["非流动资产合计"]
    },

    # ==========================================
    # 📊 资产总计 (Total Assets)
    # ==========================================
    "TOTAL_ASSETS": {
        "obb": ["total_assets"],
        "akshare": ["总资产"]
    },
    "NET_WORKING_CAPITAL": {
        "obb": [],
        "akshare": ["净流动资产"]
    },
    "TOTAL_EQUITY_AND_NON_CURRENT_LIABILITIES": {
        "obb": [],
        "akshare": ["总权益及非流动负债"]
    },
    "TOTAL_EQUITY_AND_LIABILITIES": {
        "obb": [],
        "akshare": ["总权益及总负债"]
    },

    # ==========================================
    # 📊 流动负债 (Current Liabilities)
    # ==========================================
    "SHORT_TERM_DEBT": {
        "obb": ["current_debt"],
        "akshare": ["短期贷款"]
    },
    "COMMERCIAL_PAPER": {
        "obb": ["commercial_paper"],
        "akshare": []
    },
    "OTHER_CURRENT_BORROWINGS": {
        "obb": ["other_current_borrowings"],
        "akshare": []
    },
    "CURRENT_DEBT_AND_LEASE_OBLIG": {
        "obb": ["current_debt_and_capital_lease_obligation"],
        "akshare": []
    },
    "NOTES_PAYABLE": {
        "obb": [],
        "akshare": ["应付票据"]
    },
    "ACCOUNTS_PAYABLE": {
        "obb": ["accounts_payable"],
        "akshare": ["应付帐款"]
    },
    "PAYABLES_TO_RELATED_PARTIES_CURRENT": {
        "obb": [],
        "akshare": ["应付关联方款项(流动)"]
    },
    "TOTAL_TAX_PAYABLE": {
        "obb": ["total_tax_payable"],
        "akshare": ["应付税项"]
    },
    "INCOME_TAX_PAYABLE": {
        "obb": ["income_tax_payable"],
        "akshare": []
    },
    "DIVIDENDS_PAYABLE": {
        "obb": [],
        "akshare": ["应付股利"]
    },
    "OTHER_PAYABLES_AND_ACCRUALS": {
        "obb": [],
        "akshare": ["其他应付款及应计费用"]
    },
    "OTHER_FINANCIAL_LIABILITIES_CURRENT": {
        "obb": [],
        "akshare": ["其他金融负债(流动)"]
    },
    "CAPITAL_LEASE_OBLIGATIONS_CURRENT": {
        "obb": [],
        "akshare": ["融资租赁负债(流动)"]
    },
    "DEFERRED_REVENUE_CURRENT": {
        "obb": ["current_deferred_revenue"],
        "akshare": ["递延收入(流动)", "预收款项"]
    },
    "CURRENT_DEFERRED_LIABILITIES": {
        "obb": ["current_deferred_liabilities"],
        "akshare": []
    },
    "DERIVATIVE_FINANCIAL_LIABILITIES_CURRENT": {
        "obb": [],
        "akshare": ["衍生金融工具-负债(流动)"]
    },
    "OTHER_CURRENT_LIABILITIES": {
        "obb": ["other_current_liabilities"],
        "akshare": []
    },
    "TOTAL_CURRENT_LIABILITIES": {
        "obb": ["current_liabilities"],
        "akshare": ["流动负债合计"]
    },

    # ==========================================
    # 📊 非流动负债 (Non-Current Liabilities)
    # ==========================================
    "LONG_TERM_DEBT": {
        "obb": ["long_term_debt"],
        "akshare": ["长期贷款"]
    },
    "NOTES_PAYABLE_NON_CURRENT": {
        "obb": [],
        "akshare": ["应付票据(非流动)"]
    },
    "LONG_TERM_PAYABLES": {
        "obb": ["tradeand_other_payables_non_current"],
        "akshare": ["长期应付款"]
    },
    "CAPITAL_LEASE_OBLIGATIONS_NON_CURRENT": {
        "obb": ["long_term_capital_lease_obligation"],
        "akshare": ["融资租赁负债(非流动)"]
    },
    "DEFERRED_REVENUE_NON_CURRENT": {
        "obb": ["non_current_deferred_revenue"],
        "akshare": ["递延收入(非流动)"]
    },
    "NON_CURRENT_DEFERRED_LIABILITIES": {
        "obb": ["non_current_deferred_liabilities"],
        "akshare": []
    },
    "DEFERRED_TAX_LIABILITIES": {
        "obb": ["non_current_deferred_taxes_liabilities"],
        "akshare": ["递延税项负债"]
    },
    "OTHER_FINANCIAL_LIABILITIES_NON_CURRENT": {
        "obb": [],
        "akshare": ["其他金融负债(非流动)"]
    },
    "OTHER_NON_CURRENT_LIABILITIES": {
        "obb": ["other_non_current_liabilities"],
        "akshare": ["其他非流动负债", "非流动负债其他项目"]
    },
    "TOTAL_NON_CURRENT_LIABILITIES": {
        "obb": ["total_non_current_liabilities_net_minority_interest"],
        "akshare": ["非流动负债合计"]
    },

    # ==========================================
    # 📊 总负债 (Total Liabilities)
    # ==========================================
    "TOTAL_LIABILITIES": {
        "obb": ["total_liabilities_net_minority_interest"],
        "akshare": ["总负债"]
    },

    # ==========================================
    # 📊 股东权益 (Shareholders' Equity)
    # ==========================================
    "COMMON_STOCK": {
        "obb": ["common_stock"],
        "akshare": ["股本"]
    },
    "SHARE_PREMIUM": {
        "obb": [],
        "akshare": ["股本溢价"]
    },
    "RESERVES": {
        "obb": [],
        "akshare": ["储备"]
    },
    "OTHER_RESERVES": {
        "obb": [],
        "akshare": ["其他储备"]
    },
    "RETAINED_EARNINGS": {
        "obb": ["retained_earnings"],
        "akshare": ["保留溢利(累计亏损)"]
    },
    "TREASURY_STOCK": {
        "obb": [],
        "akshare": ["库存股"]
    },
    "NONCONTROLLING_INTERESTS": {
        "obb": ["minority_interest"],
        "akshare": ["少数股东权益"]
    },
    "TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT": {
        "obb": ["total_common_equity"],
        "akshare": ["股东权益"]
    },
    "COMMON_STOCK_EQUITY": {
        "obb": ["common_stock_equity"],
        "akshare": []
    },
    "TOTAL_EQUITY_CONSOLIDATED": {
        "obb": ["total_equity"],
        "akshare": ["总权益", "净资产"]
    },
    "TOTAL_EQUITY_NON_CONTROLLING_INTERESTS": {
        "obb": ["total_equity_non_controlling_interests"],
        "akshare": []
    },

    # ==========================================
    # 📊 衍生指标 (Derived Metrics)
    # ==========================================
    "NET_TANGIBLE_ASSETS": {
        "obb": ["net_tangible_assets"],
        "akshare": []
    },
    "WORKING_CAPITAL": {
        "obb": ["working_capital"],
        "akshare": []
    },
    "INVESTED_CAPITAL": {
        "obb": ["invested_capital"],
        "akshare": []
    },
    "TANGIBLE_BOOK_VALUE": {
        "obb": ["tangible_book_value"],
        "akshare": []
    },
    "TOTAL_DEBT": {
        "obb": ["total_debt"],
        "akshare": []
    },
    "NET_DEBT": {
        "obb": ["net_debt"],
        "akshare": []
    },
    "SHARE_ISSUED": {
        "obb": ["share_issued"],
        "akshare": []
    },

    # ==========================================
    # 🔵 新增流动资产/负债 (New Current Items)
    # ==========================================
    "NOTES_RECEIVABLE": {
        "obb": [],
        "akshare": ["应收票据"]
    },
    "LOANS_AND_ADVANCES_CURRENT": {
        "obb": [],
        "akshare": ["贷款及垫款(流动)"]
    },
    "CURRENT_PROVISIONS": {
        "obb": ["pensionand_other_post_retirement_benefit_plans_current"],
        "akshare": ["拨备(流动)"]
    },

    # ==========================================
    # 🟣 新增非流动资产/负债 (New Non-Current Items)
    # ==========================================
    "LONG_TERM_INVESTMENTS": {
        "obb": [],
        "akshare": ["长期投资"]
    },
    "OTHER_INVESTMENTS": {
        "obb": [],
        "akshare": ["其他投资"]
    },
    "DEFERRED_TAX_ASSETS": {
        "obb": [],
        "akshare": ["递延税项资产"]
    },
    "NON_CURRENT_PROVISIONS": {
        "obb": [],
        "akshare": ["拨备(非流动)"]
    },
    "CONVERTIBLE_REDEEMABLE_PREFERRED_SHARES": {
        "obb": [],
        "akshare": ["可转换可赎回优先股"]
    },

    # ==========================================
    # 🟠 新增汇总及交叉验证指标 (Derived / Check Items)
    # ==========================================
    "TOTAL_ASSETS_LESS_TOTAL_LIABILITIES": {
        "obb": [],
        "akshare": ["总资产减总负债合计"]
    },
    "TOTAL_ASSETS_LESS_CURRENT_LIABILITIES": {
        "obb": [],
        "akshare": ["总资产减流动负债"]
    },

    # ==========================================
    # 🔵 新增：资产质量与粉饰预警 (Asset Quality & Fraud Detection)
    # ==========================================
    "GROSS_ACCOUNTS_RECEIVABLE": {
        "obb": ["gross_accounts_receivable"],
        "akshare": []
    },
    "ALLOWANCE_FOR_DOUBTFUL_ACCOUNTS": {
        "obb": ["allowance_for_doubtful_accounts_receivable"],
        "akshare": ["坏账准备"]
    },

    # ==========================================
    # 🟢 新增：资本开支生命周期预测 (CapEx Lifecycle)
    # ==========================================
    "ACCUMULATED_DEPRECIATION": {
        "obb": ["accumulated_depreciation"],
        "akshare": ["累计折旧"]
    },
    "GOODWILL_AND_OTHER_INTANGIBLE_ASSETS": {
        "obb": ["goodwill_and_other_intangible_assets"],
        "akshare": []
    },

    # ==========================================
    # 🟠 新增：隐藏杠杆与类债务 (Hidden Leverage / ASC 842)
    # ==========================================
    "RIGHT_OF_USE_ASSETS": {
        "obb": ["leases"],
        "akshare": ["使用权资产"]
    },
    "LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS": {
        "obb": ["long_term_debt_and_capital_lease_obligation"],
        "akshare": []
    },

    # ==========================================
    # 🟣 新增：AOCI 留存收益的底色
    # ==========================================
    "ACCUMULATED_OTHER_COMPREHENSIVE_INCOME": {
        "obb": ["accumulated_other_comprehensive_income_loss"],
        "akshare": ["其他综合收益"]
    },
    "OTHER_EQUITY_ADJUSTMENTS": {
        "obb": ["other_equity_adjustments"],
        "akshare": []
    },
    "GAINS_LOSSES_NOT_AFFECTING_RETAINED_EARNINGS": {
        "obb": ["gains_losses_not_affecting_retained_earnings"],
        "akshare": []
    },

    # ==========================================
    # 🔴 新增：OBB 特有字段补充 (OBB Specific Fields)
    # ==========================================
    "CAPITAL_STOCK": {
        "obb": ["capital_stock"],
        "akshare": []
    },
    "ORDINARY_SHARES_NUMBER": {
        "obb": ["ordinary_shares_number"],
        "akshare": []
    },
    "TOTAL_PAYABLES_AND_ACCRUED_EXPENSES": {
        "obb": ["payables_and_accrued_expenses"],
        "akshare": []
    },
    "PAYABLES": {
        "obb": ["payables"],
        "akshare": []
    },
    "TOTAL_CAPITALIZATION": {
        "obb": ["total_capitalization"],
        "akshare": []
    },
    "CAPITAL_LEASE_OBLIGATIONS": {
        "obb": ["capital_lease_obligations"],
        "akshare": []
    },
}


# ==========================================
# 2. 键名常量 Mixin (FinKey Mixin)
# 用于 data_utils.py 的 FinKey 类继承
# ==========================================
class BalanceSheetKey:
    """
    资产负债表字段常量 Mixin
    供 FinKey 类继承，实现静态类型支持
    """
    # ==========================================
    # 📊 流动资产 (Current Assets)
    # ==========================================
    CASH_AND_CASH_EQUIVALENTS: str = "CASH_AND_CASH_EQUIVALENTS"
    CASH_ONLY: str = "CASH_ONLY"
    CASH_EQUIVALENTS: str = "CASH_EQUIVALENTS"
    CASH_CASH_EQUIV_ST_INVEST: str = "CASH_CASH_EQUIV_ST_INVEST"
    RESTRICTED_CASH: str = "RESTRICTED_CASH"
    SHORT_TERM_DEPOSITS: str = "SHORT_TERM_DEPOSITS"
    LONG_TERM_DEPOSITS: str = "LONG_TERM_DEPOSITS"
    SHORT_TERM_INVESTMENTS: str = "SHORT_TERM_INVESTMENTS"
    TRADING_FINANCIAL_ASSETS_CURRENT: str = "TRADING_FINANCIAL_ASSETS_CURRENT"
    FINANCIAL_ASSETS_AT_FAIR_VALUE_CURRENT: str = "FINANCIAL_ASSETS_AT_FAIR_VALUE_CURRENT"
    OTHER_FINANCIAL_ASSETS_CURRENT: str = "OTHER_FINANCIAL_ASSETS_CURRENT"
    ACCOUNTS_RECEIVABLE: str = "ACCOUNTS_RECEIVABLE"
    NET_RECEIVABLES: str = "NET_RECEIVABLES"
    RECEIVABLES_FROM_RELATED_PARTIES: str = "RECEIVABLES_FROM_RELATED_PARTIES"
    PREPAYMENTS: str = "PREPAYMENTS"
    PREPAYMENTS_AND_OTHER_RECEIVABLES: str = "PREPAYMENTS_AND_OTHER_RECEIVABLES"
    INVENTORIES: str = "INVENTORIES"
    RAW_MATERIALS: str = "RAW_MATERIALS"
    WORK_IN_PROCESS: str = "WORK_IN_PROCESS"
    FINISHED_GOODS: str = "FINISHED_GOODS"
    HELD_TO_MATURITY_INVESTMENTS_CURRENT: str = "HELD_TO_MATURITY_INVESTMENTS_CURRENT"
    ASSETS_HELD_FOR_SALE: str = "ASSETS_HELD_FOR_SALE"
    DERIVATIVE_FINANCIAL_ASSETS_CURRENT: str = "DERIVATIVE_FINANCIAL_ASSETS_CURRENT"
    OTHER_CURRENT_ASSETS: str = "OTHER_CURRENT_ASSETS"
    TOTAL_CURRENT_ASSETS: str = "TOTAL_CURRENT_ASSETS"

    # ==========================================
    # 📊 非流动资产 (Non-Current Assets)
    # ==========================================
    PLANT_PROPERTY_EQUIPMENT_NET: str = "PLANT_PROPERTY_EQUIPMENT_NET"
    PLANT_PROPERTY_EQUIPMENT_GROSS: str = "PLANT_PROPERTY_EQUIPMENT_GROSS"
    LAND_AND_IMPROVEMENTS: str = "LAND_AND_IMPROVEMENTS"
    BUILDINGS_AND_IMPROVEMENTS: str = "BUILDINGS_AND_IMPROVEMENTS"
    MACHINERY_FURNITURE_EQUIPMENT: str = "MACHINERY_FURNITURE_EQUIPMENT"
    OTHER_PROPERTIES: str = "OTHER_PROPERTIES"
    INVESTMENT_PROPERTIES: str = "INVESTMENT_PROPERTIES"
    LAND_USE_RIGHTS: str = "LAND_USE_RIGHTS"
    CONSTRUCTION_IN_PROGRESS: str = "CONSTRUCTION_IN_PROGRESS"
    GOODWILL: str = "GOODWILL"
    INTANGIBLE_ASSETS: str = "INTANGIBLE_ASSETS"
    INTERESTS_IN_ASSOCIATES: str = "INTERESTS_IN_ASSOCIATES"
    LONG_TERM_EQUITY_INVESTMENT: str = "LONG_TERM_EQUITY_INVESTMENT"
    TRADING_FINANCIAL_ASSETS_NON_CURRENT: str = "TRADING_FINANCIAL_ASSETS_NON_CURRENT"
    INTERESTS_IN_JOINT_VENTURES: str = "INTERESTS_IN_JOINT_VENTURES"
    REDEEMABLE_INSTRUMENTS_IN_ASSOCIATES: str = "REDEEMABLE_INSTRUMENTS_IN_ASSOCIATES"
    AVAILABLE_FOR_SALE_INVESTMENTS: str = "AVAILABLE_FOR_SALE_INVESTMENTS"
    HELD_TO_MATURITY_INVESTMENTS: str = "HELD_TO_MATURITY_INVESTMENTS"
    FINANCIAL_ASSETS_AT_FAIR_VALUE: str = "FINANCIAL_ASSETS_AT_FAIR_VALUE"
    OTHER_FINANCIAL_ASSETS_NON_CURRENT: str = "OTHER_FINANCIAL_ASSETS_NON_CURRENT"
    OTHER_NON_CURRENT_ASSETS: str = "OTHER_NON_CURRENT_ASSETS"
    OTHER_NON_CURRENT_ASSETS_ITEMS: str = "OTHER_NON_CURRENT_ASSETS_ITEMS"
    TOTAL_NON_CURRENT_ASSETS: str = "TOTAL_NON_CURRENT_ASSETS"

    # ==========================================
    # 📊 资产总计 (Total Assets)
    # ==========================================
    TOTAL_ASSETS: str = "TOTAL_ASSETS"
    NET_WORKING_CAPITAL: str = "NET_WORKING_CAPITAL"
    TOTAL_EQUITY_AND_NON_CURRENT_LIABILITIES: str = "TOTAL_EQUITY_AND_NON_CURRENT_LIABILITIES"
    TOTAL_EQUITY_AND_LIABILITIES: str = "TOTAL_EQUITY_AND_LIABILITIES"

    # ==========================================
    # 📊 流动负债 (Current Liabilities)
    # ==========================================
    SHORT_TERM_DEBT: str = "SHORT_TERM_DEBT"
    COMMERCIAL_PAPER: str = "COMMERCIAL_PAPER"
    OTHER_CURRENT_BORROWINGS: str = "OTHER_CURRENT_BORROWINGS"
    CURRENT_DEBT_AND_LEASE_OBLIG: str = "CURRENT_DEBT_AND_LEASE_OBLIG"
    NOTES_PAYABLE: str = "NOTES_PAYABLE"
    ACCOUNTS_PAYABLE: str = "ACCOUNTS_PAYABLE"
    PAYABLES_TO_RELATED_PARTIES_CURRENT: str = "PAYABLES_TO_RELATED_PARTIES_CURRENT"
    TOTAL_TAX_PAYABLE: str = "TOTAL_TAX_PAYABLE"
    INCOME_TAX_PAYABLE: str = "INCOME_TAX_PAYABLE"
    DIVIDENDS_PAYABLE: str = "DIVIDENDS_PAYABLE"
    OTHER_PAYABLES_AND_ACCRUALS: str = "OTHER_PAYABLES_AND_ACCRUALS"
    OTHER_FINANCIAL_LIABILITIES_CURRENT: str = "OTHER_FINANCIAL_LIABILITIES_CURRENT"
    CAPITAL_LEASE_OBLIGATIONS_CURRENT: str = "CAPITAL_LEASE_OBLIGATIONS_CURRENT"
    DEFERRED_REVENUE_CURRENT: str = "DEFERRED_REVENUE_CURRENT"
    CURRENT_DEFERRED_LIABILITIES: str = "CURRENT_DEFERRED_LIABILITIES"
    DERIVATIVE_FINANCIAL_LIABILITIES_CURRENT: str = "DERIVATIVE_FINANCIAL_LIABILITIES_CURRENT"
    OTHER_CURRENT_LIABILITIES: str = "OTHER_CURRENT_LIABILITIES"
    TOTAL_CURRENT_LIABILITIES: str = "TOTAL_CURRENT_LIABILITIES"

    # ==========================================
    # 📊 非流动负债 (Non-Current Liabilities)
    # ==========================================
    LONG_TERM_DEBT: str = "LONG_TERM_DEBT"
    NOTES_PAYABLE_NON_CURRENT: str = "NOTES_PAYABLE_NON_CURRENT"
    LONG_TERM_PAYABLES: str = "LONG_TERM_PAYABLES"
    CAPITAL_LEASE_OBLIGATIONS_NON_CURRENT: str = "CAPITAL_LEASE_OBLIGATIONS_NON_CURRENT"
    DEFERRED_REVENUE_NON_CURRENT: str = "DEFERRED_REVENUE_NON_CURRENT"
    NON_CURRENT_DEFERRED_LIABILITIES: str = "NON_CURRENT_DEFERRED_LIABILITIES"
    DEFERRED_TAX_LIABILITIES: str = "DEFERRED_TAX_LIABILITIES"
    OTHER_FINANCIAL_LIABILITIES_NON_CURRENT: str = "OTHER_FINANCIAL_LIABILITIES_NON_CURRENT"
    OTHER_NON_CURRENT_LIABILITIES: str = "OTHER_NON_CURRENT_LIABILITIES"
    TOTAL_NON_CURRENT_LIABILITIES: str = "TOTAL_NON_CURRENT_LIABILITIES"

    # ==========================================
    # 📊 总负债 (Total Liabilities)
    # ==========================================
    TOTAL_LIABILITIES: str = "TOTAL_LIABILITIES"

    # ==========================================
    # 📊 股东权益 (Shareholders' Equity)
    # ==========================================
    COMMON_STOCK: str = "COMMON_STOCK"
    SHARE_PREMIUM: str = "SHARE_PREMIUM"
    RESERVES: str = "RESERVES"
    OTHER_RESERVES: str = "OTHER_RESERVES"
    RETAINED_EARNINGS: str = "RETAINED_EARNINGS"
    TREASURY_STOCK: str = "TREASURY_STOCK"
    NONCONTROLLING_INTERESTS: str = "NONCONTROLLING_INTERESTS"
    TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT: str = "TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT"
    COMMON_STOCK_EQUITY: str = "COMMON_STOCK_EQUITY"
    TOTAL_EQUITY_CONSOLIDATED: str = "TOTAL_EQUITY_CONSOLIDATED"
    TOTAL_EQUITY_NON_CONTROLLING_INTERESTS: str = "TOTAL_EQUITY_NON_CONTROLLING_INTERESTS"

    # ==========================================
    # 📊 衍生指标 (Derived Metrics)
    # ==========================================
    NET_TANGIBLE_ASSETS: str = "NET_TANGIBLE_ASSETS"
    WORKING_CAPITAL: str = "WORKING_CAPITAL"
    INVESTED_CAPITAL: str = "INVESTED_CAPITAL"
    TANGIBLE_BOOK_VALUE: str = "TANGIBLE_BOOK_VALUE"
    TOTAL_DEBT: str = "TOTAL_DEBT"
    NET_DEBT: str = "NET_DEBT"
    SHARE_ISSUED: str = "SHARE_ISSUED"

    # ==========================================
    # 🔵 新增流动资产/负债 (New Current Items)
    # ==========================================
    NOTES_RECEIVABLE: str = "NOTES_RECEIVABLE"
    LOANS_AND_ADVANCES_CURRENT: str = "LOANS_AND_ADVANCES_CURRENT"
    CURRENT_PROVISIONS: str = "CURRENT_PROVISIONS"

    # ==========================================
    # 🟣 新增非流动资产/负债 (New Non-Current Items)
    # ==========================================
    LONG_TERM_INVESTMENTS: str = "LONG_TERM_INVESTMENTS"
    OTHER_INVESTMENTS: str = "OTHER_INVESTMENTS"
    DEFERRED_TAX_ASSETS: str = "DEFERRED_TAX_ASSETS"
    NON_CURRENT_PROVISIONS: str = "NON_CURRENT_PROVISIONS"
    CONVERTIBLE_REDEEMABLE_PREFERRED_SHARES: str = "CONVERTIBLE_REDEEMABLE_PREFERRED_SHARES"

    # ==========================================
    # 🟠 新增汇总及交叉验证指标 (Derived / Check Items)
    # ==========================================
    TOTAL_ASSETS_LESS_TOTAL_LIABILITIES: str = "TOTAL_ASSETS_LESS_TOTAL_LIABILITIES"
    TOTAL_ASSETS_LESS_CURRENT_LIABILITIES: str = "TOTAL_ASSETS_LESS_CURRENT_LIABILITIES"

    # ==========================================
    # 🔵 新增：资产质量与粉饰预警 (Asset Quality & Fraud Detection)
    # ==========================================
    GROSS_ACCOUNTS_RECEIVABLE: str = "GROSS_ACCOUNTS_RECEIVABLE"
    ALLOWANCE_FOR_DOUBTFUL_ACCOUNTS: str = "ALLOWANCE_FOR_DOUBTFUL_ACCOUNTS"

    # ==========================================
    # 🟢 新增：资本开支生命周期预测 (CapEx Lifecycle)
    # ==========================================
    ACCUMULATED_DEPRECIATION: str = "ACCUMULATED_DEPRECIATION"
    GOODWILL_AND_OTHER_INTANGIBLE_ASSETS: str = "GOODWILL_AND_OTHER_INTANGIBLE_ASSETS"

    # ==========================================
    # 🟠 新增：隐藏杠杆与类债务 (Hidden Leverage / ASC 842)
    # ==========================================
    RIGHT_OF_USE_ASSETS: str = "RIGHT_OF_USE_ASSETS"
    LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS: str = "LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS"

    # ==========================================
    # 🟣 新增：AOCI 留存收益的底色
    # ==========================================
    ACCUMULATED_OTHER_COMPREHENSIVE_INCOME: str = "ACCUMULATED_OTHER_COMPREHENSIVE_INCOME"
    OTHER_EQUITY_ADJUSTMENTS: str = "OTHER_EQUITY_ADJUSTMENTS"
    GAINS_LOSSES_NOT_AFFECTING_RETAINED_EARNINGS: str = "GAINS_LOSSES_NOT_AFFECTING_RETAINED_EARNINGS"

    # ==========================================
    # 🔴 新增：OBB 特有字段补充 (OBB Specific Fields)
    # ==========================================
    CAPITAL_STOCK: str = "CAPITAL_STOCK"
    ORDINARY_SHARES_NUMBER: str = "ORDINARY_SHARES_NUMBER"
    TOTAL_PAYABLES_AND_ACCRUED_EXPENSES: str = "TOTAL_PAYABLES_AND_ACCRUED_EXPENSES"
    PAYABLES: str = "PAYABLES"
    TOTAL_CAPITALIZATION: str = "TOTAL_CAPITALIZATION"
    CAPITAL_LEASE_OBLIGATIONS: str = "CAPITAL_LEASE_OBLIGATIONS"

    # ========== 向后兼容别名 (Backward Compatibility Aliases) ==========
    ASSETS: str = TOTAL_ASSETS
    LIAB: str = TOTAL_LIABILITIES
    EQUITY: str = TOTAL_EQUITY_CONSOLIDATED
    C_ASSETS: str = TOTAL_CURRENT_ASSETS
    C_LIAB: str = TOTAL_CURRENT_LIABILITIES
    CASH_AND_EQUIV: str = CASH_AND_CASH_EQUIVALENTS
    INTANGIBLE: str = INTANGIBLE_ASSETS
    NCI: str = NONCONTROLLING_INTERESTS
    PPENET: str = PLANT_PROPERTY_EQUIPMENT_NET


# ==========================================
# 3. Pydantic 模型 Mixin (Schema Mixin)
# 用于 schema_standard.py 的 StandardFinancialRecord 类继承
# ==========================================
class BalanceSheetRecord(BaseModel):
    """
    资产负债表字段 Pydantic 模型 Mixin
    供 StandardFinancialRecord 类继承，实现静态类型支持
    """

    # ==========================================
    # 📊 流动资产 (Current Assets)
    # ==========================================
    CASH_AND_CASH_EQUIVALENTS: Optional[float] = None
    CASH_ONLY: Optional[float] = None
    CASH_EQUIVALENTS: Optional[float] = None
    CASH_CASH_EQUIV_ST_INVEST: Optional[float] = None
    RESTRICTED_CASH: Optional[float] = None
    SHORT_TERM_DEPOSITS: Optional[float] = None
    LONG_TERM_DEPOSITS: Optional[float] = None
    SHORT_TERM_INVESTMENTS: Optional[float] = None
    TRADING_FINANCIAL_ASSETS_CURRENT: Optional[float] = None
    FINANCIAL_ASSETS_AT_FAIR_VALUE_CURRENT: Optional[float] = None
    OTHER_FINANCIAL_ASSETS_CURRENT: Optional[float] = None
    ACCOUNTS_RECEIVABLE: Optional[float] = None
    NET_RECEIVABLES: Optional[float] = None
    RECEIVABLES_FROM_RELATED_PARTIES: Optional[float] = None
    PREPAYMENTS: Optional[float] = None
    PREPAYMENTS_AND_OTHER_RECEIVABLES: Optional[float] = None
    INVENTORIES: Optional[float] = None
    RAW_MATERIALS: Optional[float] = None
    WORK_IN_PROCESS: Optional[float] = None
    FINISHED_GOODS: Optional[float] = None
    HELD_TO_MATURITY_INVESTMENTS_CURRENT: Optional[float] = None
    ASSETS_HELD_FOR_SALE: Optional[float] = None
    DERIVATIVE_FINANCIAL_ASSETS_CURRENT: Optional[float] = None
    OTHER_CURRENT_ASSETS: Optional[float] = None
    TOTAL_CURRENT_ASSETS: Optional[float] = None

    # ==========================================
    # 📊 非流动资产 (Non-Current Assets)
    # ==========================================
    PLANT_PROPERTY_EQUIPMENT_NET: Optional[float] = None
    PLANT_PROPERTY_EQUIPMENT_GROSS: Optional[float] = None
    LAND_AND_IMPROVEMENTS: Optional[float] = None
    BUILDINGS_AND_IMPROVEMENTS: Optional[float] = None
    MACHINERY_FURNITURE_EQUIPMENT: Optional[float] = None
    OTHER_PROPERTIES: Optional[float] = None
    INVESTMENT_PROPERTIES: Optional[float] = None
    LAND_USE_RIGHTS: Optional[float] = None
    CONSTRUCTION_IN_PROGRESS: Optional[float] = None
    GOODWILL: Optional[float] = None
    INTANGIBLE_ASSETS: Optional[float] = None
    INTERESTS_IN_ASSOCIATES: Optional[float] = None
    LONG_TERM_EQUITY_INVESTMENT: Optional[float] = None
    TRADING_FINANCIAL_ASSETS_NON_CURRENT: Optional[float] = None
    INTERESTS_IN_JOINT_VENTURES: Optional[float] = None
    REDEEMABLE_INSTRUMENTS_IN_ASSOCIATES: Optional[float] = None
    AVAILABLE_FOR_SALE_INVESTMENTS: Optional[float] = None
    HELD_TO_MATURITY_INVESTMENTS: Optional[float] = None
    FINANCIAL_ASSETS_AT_FAIR_VALUE: Optional[float] = None
    OTHER_FINANCIAL_ASSETS_NON_CURRENT: Optional[float] = None
    OTHER_NON_CURRENT_ASSETS: Optional[float] = None
    OTHER_NON_CURRENT_ASSETS_ITEMS: Optional[float] = None
    TOTAL_NON_CURRENT_ASSETS: Optional[float] = None

    # ==========================================
    # 📊 资产总计 (Total Assets)
    # ==========================================
    TOTAL_ASSETS: Optional[float] = None
    NET_WORKING_CAPITAL: Optional[float] = None
    TOTAL_EQUITY_AND_NON_CURRENT_LIABILITIES: Optional[float] = None
    TOTAL_EQUITY_AND_LIABILITIES: Optional[float] = None

    # ==========================================
    # 📊 流动负债 (Current Liabilities)
    # ==========================================
    SHORT_TERM_DEBT: Optional[float] = None
    COMMERCIAL_PAPER: Optional[float] = None
    OTHER_CURRENT_BORROWINGS: Optional[float] = None
    CURRENT_DEBT_AND_LEASE_OBLIG: Optional[float] = None
    NOTES_PAYABLE: Optional[float] = None
    ACCOUNTS_PAYABLE: Optional[float] = None
    PAYABLES_TO_RELATED_PARTIES_CURRENT: Optional[float] = None
    TOTAL_TAX_PAYABLE: Optional[float] = None
    INCOME_TAX_PAYABLE: Optional[float] = None
    DIVIDENDS_PAYABLE: Optional[float] = None
    OTHER_PAYABLES_AND_ACCRUALS: Optional[float] = None
    OTHER_FINANCIAL_LIABILITIES_CURRENT: Optional[float] = None
    CAPITAL_LEASE_OBLIGATIONS_CURRENT: Optional[float] = None
    DEFERRED_REVENUE_CURRENT: Optional[float] = None
    CURRENT_DEFERRED_LIABILITIES: Optional[float] = None
    DERIVATIVE_FINANCIAL_LIABILITIES_CURRENT: Optional[float] = None
    OTHER_CURRENT_LIABILITIES: Optional[float] = None
    TOTAL_CURRENT_LIABILITIES: Optional[float] = None

    # ==========================================
    # 📊 非流动负债 (Non-Current Liabilities)
    # ==========================================
    LONG_TERM_DEBT: Optional[float] = None
    NOTES_PAYABLE_NON_CURRENT: Optional[float] = None
    LONG_TERM_PAYABLES: Optional[float] = None
    CAPITAL_LEASE_OBLIGATIONS_NON_CURRENT: Optional[float] = None
    DEFERRED_REVENUE_NON_CURRENT: Optional[float] = None
    NON_CURRENT_DEFERRED_LIABILITIES: Optional[float] = None
    DEFERRED_TAX_LIABILITIES: Optional[float] = None
    OTHER_FINANCIAL_LIABILITIES_NON_CURRENT: Optional[float] = None
    OTHER_NON_CURRENT_LIABILITIES: Optional[float] = None
    TOTAL_NON_CURRENT_LIABILITIES: Optional[float] = None

    # ==========================================
    # 📊 总负债 (Total Liabilities)
    # ==========================================
    TOTAL_LIABILITIES: Optional[float] = None

    # ==========================================
    # 📊 股东权益 (Shareholders' Equity)
    # ==========================================
    COMMON_STOCK: Optional[float] = None
    SHARE_PREMIUM: Optional[float] = None
    RESERVES: Optional[float] = None
    OTHER_RESERVES: Optional[float] = None
    RETAINED_EARNINGS: Optional[float] = None
    TREASURY_STOCK: Optional[float] = None
    NONCONTROLLING_INTERESTS: Optional[float] = None
    TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT: Optional[float] = None
    COMMON_STOCK_EQUITY: Optional[float] = None
    TOTAL_EQUITY_CONSOLIDATED: Optional[float] = None
    TOTAL_EQUITY_NON_CONTROLLING_INTERESTS: Optional[float] = None

    # ==========================================
    # 📊 衍生指标 (Derived Metrics)
    # ==========================================
    NET_TANGIBLE_ASSETS: Optional[float] = None
    WORKING_CAPITAL: Optional[float] = None
    INVESTED_CAPITAL: Optional[float] = None
    TANGIBLE_BOOK_VALUE: Optional[float] = None
    TOTAL_DEBT: Optional[float] = None
    NET_DEBT: Optional[float] = None
    SHARE_ISSUED: Optional[float] = None

    # ==========================================
    # 🔵 新增流动资产/负债 (New Current Items)
    # ==========================================
    NOTES_RECEIVABLE: Optional[float] = None
    LOANS_AND_ADVANCES_CURRENT: Optional[float] = None
    CURRENT_PROVISIONS: Optional[float] = None

    # ==========================================
    # 🟣 新增非流动资产/负债 (New Non-Current Items)
    # ==========================================
    LONG_TERM_INVESTMENTS: Optional[float] = None
    OTHER_INVESTMENTS: Optional[float] = None
    DEFERRED_TAX_ASSETS: Optional[float] = None
    NON_CURRENT_PROVISIONS: Optional[float] = None
    CONVERTIBLE_REDEEMABLE_PREFERRED_SHARES: Optional[float] = None

    # ==========================================
    # 🟠 新增汇总及交叉验证指标 (Derived / Check Items)
    # ==========================================
    TOTAL_ASSETS_LESS_TOTAL_LIABILITIES: Optional[float] = None
    TOTAL_ASSETS_LESS_CURRENT_LIABILITIES: Optional[float] = None

    # ==========================================
    # 🔵 新增：资产质量与粉饰预警 (Asset Quality & Fraud Detection)
    # ==========================================
    GROSS_ACCOUNTS_RECEIVABLE: Optional[float] = None
    ALLOWANCE_FOR_DOUBTFUL_ACCOUNTS: Optional[float] = None

    # ==========================================
    # 🟢 新增：资本开支生命周期预测 (CapEx Lifecycle)
    # ==========================================
    ACCUMULATED_DEPRECIATION: Optional[float] = None
    GOODWILL_AND_OTHER_INTANGIBLE_ASSETS: Optional[float] = None

    # ==========================================
    # 🟠 新增：隐藏杠杆与类债务 (Hidden Leverage / ASC 842)
    # ==========================================
    RIGHT_OF_USE_ASSETS: Optional[float] = None
    LONG_TERM_DEBT_AND_CAPITAL_LEASE_OBLIGATIONS: Optional[float] = None

    # ==========================================
    # 🟣 新增：AOCI 留存收益的底色
    # ==========================================
    ACCUMULATED_OTHER_COMPREHENSIVE_INCOME: Optional[float] = None
    OTHER_EQUITY_ADJUSTMENTS: Optional[float] = None
    GAINS_LOSSES_NOT_AFFECTING_RETAINED_EARNINGS: Optional[float] = None

    # ==========================================
    # 🔴 新增：OBB 特有字段补充 (OBB Specific Fields)
    # ==========================================
    CAPITAL_STOCK: Optional[float] = None
    ORDINARY_SHARES_NUMBER: Optional[float] = None
    TOTAL_PAYABLES_AND_ACCRUED_EXPENSES: Optional[float] = None
    PAYABLES: Optional[float] = None
    TOTAL_CAPITALIZATION: Optional[float] = None
    CAPITAL_LEASE_OBLIGATIONS: Optional[float] = None

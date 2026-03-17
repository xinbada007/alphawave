"""
现金流量表核心契约 (Cash Flow Statement Domain)
==============================================
单一数据源 (Single Source of Truth)

设计哲学：
- 高内聚低耦合：所有现金流量表相关定义集中于此
- 静态 Mixin 模式：保留 IDE 类型推断和静态检查
- 严格一一映射：每个原始字段只映射一个标准字段

更新日志：
- 2026-03-11: 重构港股映射，基于 IFRS/HKFRS 现金流框架全面审计
              新增 39 个标准字段，完整支持港股间接法现金流穿透分析
              勘误修正：
              1. 新增 OTHER_CHANGES_IN_CASH_AND_EQUIVALENTS 独立字段
              2. 修正 CF_ADJUSTMENT_SHARE_OF_PROFIT_OF_ASSOCIATES → CF_ADJUSTMENT_PROFIT_OF_SUBSIDIARIES
              3. 去除 CHANGE_IN_PAYABLES_TO_RELATED_PARTIES_FINANCING 的主观后缀
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


# ==========================================
# 1. OBB → 标准字段映射表 (严格一一映射)
# 用于 adapters.py 的 FINANCIAL_MAPPING 合并
# ==========================================
CASH_FLOW_MAPPING: Dict[str, Dict[str, List[str]]] = {
    # ==========================================
    # 📊 一、经营活动现金流 (Operating Cash Flow)
    # ==========================================
    # --- 1.1 起点与非现金调整 (Starting Line & Non-Cash Adjustments) ---
    "NET_INCOME_FROM_CONTINUING_OPERATIONS": {
        "obb": ["net_income_from_continuing_operations"],
        "akshare": ["持续经营净利润"]  # 美股起点
    },
    "PRETAX_PROFIT_STARTING_LINE": {
        # 🚀 新增：港股间接法核心起点
        "obb": [],
        "akshare": ["除税前溢利(业务利润)"]
    },
    "OPERATING_GAINS_LOSSES": {
        "obb": ["operating_gains_losses"],
        "akshare": []
    },
    "DEPRECIATION": {
        "obb": ["depreciation"],
        "akshare": ["折旧"]
    },
    "DEPRECIATION_AND_AMORTIZATION": {
        "obb": ["depreciation_and_amortization"],
        "akshare": ["折旧和摊销", "折旧摊销", "加:折旧及摊销"]  # 纠正 1:1 违规，移出 depletion
    },
    "DEPRECIATION_AMORTIZATION_DEPLETION": {
        "obb": ["depreciation_amortization_depletion"],
        "akshare": []  # 新增：包含耗竭（Depletion，多见于矿业油气）
    },
    "DEFERRED_INCOME_TAX": {
        "obb": ["deferred_income_tax"],
        "akshare": ["递延所得税"]  # 纠正 1:1 违规，移出 deferred_tax
    },
    "DEFERRED_TAX": {
        "obb": ["deferred_tax"],
        "akshare": []  # 新增：独立建键，物理接纳 API 冗余数据
    },
    "STOCK_BASED_COMPENSATION": {
        "obb": ["stock_based_compensation"],
        "akshare": ["股份支付", "股权激励费用"]
    },
    "ASSET_IMPAIRMENT_CHARGE": {
        # 更名复用：原 CF_ADJUSTMENT_IMPAIRMENT_AND_PROVISION 更名，对齐 AkShare 拨备调整
        "obb": ["asset_impairment_charge"],
        "akshare": ["加:减值及拨备"]
    },
    "GAIN_LOSS_ON_INVESTMENT_SECURITIES": {
        # 新增：投资证券损益（已实现），核心 OCF 调整项
        "obb": ["gain_loss_on_investment_securities"],
        "akshare": []
    },
    "UNREALIZED_GAIN_LOSS_ON_INVESTMENT_SECURITIES": {
        # 新增：未实现投资证券损益，核心 OCF 调整项
        "obb": ["unrealized_gain_loss_on_investment_securities"],
        "akshare": []
    },
    "CF_ADJUSTMENT_INTEREST_EXPENSE": {
        # 🚀 新增：加回利息
        "obb": [],
        "akshare": ["加:利息支出"]
    },
    "CF_ADJUSTMENT_INTEREST_INCOME": {
        # 🚀 新增：扣除利息收入
        "obb": [],
        "akshare": ["减:利息收入"]
    },
    "CF_ADJUSTMENT_INVESTMENT_INCOME": {
        # 🚀 新增：扣除投资收益
        "obb": [],
        "akshare": ["减:投资收益"]
    },
    "CF_ADJUSTMENT_GAIN_ON_SALE_OF_ASSETS": {
        # 🚀 新增：资产处置收益调整
        "obb": [],
        "akshare": ["减:出售资产之溢利"]
    },
    "CF_ADJUSTMENT_FOREIGN_EXCHANGE_GAIN": {
        # 🚀 新增：汇兑收益调整
        "obb": [],
        "akshare": ["减:汇兑收益"]
    },
    "CF_ADJUSTMENT_REVALUATION_SURPLUS": {
        # 🚀 新增：投资物业重估盈余调整 (地产股核心)
        "obb": [],
        "akshare": ["减:重估盈余"]
    },
    "CF_ADJUSTMENT_PROFIT_OF_SUBSIDIARIES": {
        # 🚀 新增：附属公司利润调整 (勘误修正：ASSOCIATES → SUBSIDIARIES)
        "obb": [],
        "akshare": ["减:应占附属公司溢利"]
    },
    "CF_ADJUSTMENT_OTHER_OPERATING_ITEMS": {
        # 🚀 新增：其他经营调整
        "obb": [],
        "akshare": ["加:经营调整其他项目"]
    },
    "OPERATING_PROFIT_BEFORE_WORKING_CAPITAL_CHANGES": {
        # 🚀 新增：营运资金变动前经营溢利 (HKFRS 里程碑)
        "obb": [],
        "akshare": ["营运资金变动前经营溢利"]
    },

    # --- 1.2 营运资本变动 (Changes in Working Capital) ---
    "CHANGES_IN_ACCOUNT_RECEIVABLES": {
        "obb": ["changes_in_account_receivables"],
        "akshare": []
    },
    "CHANGE_IN_RECEIVABLES": {
        "obb": ["change_in_receivables"],
        "akshare": ["应收账款变动", "应收项目变动", "应收帐款减少"]  # ✅ 合并港股格式
    },
    "CHANGE_IN_INVENTORY": {
        "obb": ["change_in_inventory"],
        "akshare": ["存货变动", "存货增减", "存货(增加)减少"]  # ✅ 合并港股格式
    },
    "CHANGE_IN_ACCOUNT_PAYABLE": {
        "obb": ["change_in_account_payable"],
        "akshare": ["应付账款变动", "应付项目变动"]
    },
    "CHANGE_IN_PAYABLE": {
        "obb": ["change_in_payable"],
        "akshare": []
    },
    "CHANGE_IN_PAYABLES_AND_ACCRUED_EXPENSE": {
        "obb": ["change_in_payables_and_accrued_expense"],
        "akshare": ["应付帐款及应计费用增加(减少)"]  # ✅ 添加港股格式
    },
    "CHANGE_IN_PREPAYMENTS_AND_OTHER_RECEIVABLES": {
        # 🚀 新增：预付款项变动
        "obb": [],
        "akshare": ["预付款项、按金及其他应收款项减少(增加)"]
    },
    "CHANGE_IN_ADVANCES_AND_OTHER_PAYABLES": {
        # 🚀 新增：预收账款变动
        "obb": [],
        "akshare": ["预收账款、按金及其他应付款增加(减少)"]
    },
    "CHANGE_IN_DEFERRED_REVENUE": {
        # 🚀 新增：递延收入变动
        "obb": [],
        "akshare": ["递延收入(增加)减少"]
    },
    "CHANGE_IN_OTHER_CURRENT_ASSETS": {
        "obb": ["change_in_other_current_assets"],
        "akshare": ["其他流动资产变动"]
    },
    "CHANGE_IN_OTHER_CURRENT_LIABILITIES": {
        "obb": ["change_in_other_current_liabilities"],
        "akshare": ["其他流动负债变动"]
    },
    "CHANGE_IN_OTHER_WORKING_CAPITAL": {
        "obb": ["change_in_other_working_capital"],
        "akshare": ["营运资本变动其他项目"]  # ✅ 添加港股格式
    },
    "CHANGE_IN_WORKING_CAPITAL": {
        "obb": ["change_in_working_capital"],
        "akshare": ["营运资金变动", "经营性应收项目变动"]
    },
    "CHANGE_IN_INCOME_TAX_PAYABLE": {
        # 新增：营运资本中的所得税应付变动
        "obb": ["change_in_income_tax_payable"],
        "akshare": []
    },
    "CHANGE_IN_TAX_PAYABLE": {
        # 新增：营运资本中的总税项应付变动，独立建键以满足 1:1
        "obb": ["change_in_tax_payable"],
        "akshare": []
    },

    # --- 1.3 经营活动税息与净额 (Taxes, Interest & Net Operating CF) ---
    "CASH_GENERATED_FROM_OPERATIONS": {
        # 🚀 新增：经营产生现金 (未扣税息前)
        "obb": [],
        "akshare": ["经营产生现金"]
    },
    "INCOME_TAX_PAID": {
        # 🚀 新增：实缴所得税 (LLM 看现金流质量的核心)
        "obb": [],
        "akshare": ["已付税项"]
    },
    "INTEREST_PAID_OPERATING": {
        # 🚀 新增：计入经营活动的利息支出
        "obb": [],
        "akshare": ["已付利息(经营)"]
    },
    "CASH_FLOW_FROM_CONTINUING_OPERATING_ACTIVITIES": {
        "obb": ["cash_flow_from_continuing_operating_activities"],
        "akshare": []
    },
    "OPERATING_CASH_FLOW": {
        "obb": ["operating_cash_flow"],
        "akshare": ["经营活动产生的现金流量净额", "经营业务现金净额",
                    "经营活动现金流量净额", "NET_CASH_OPERATE", "PER_NETCASH_OPERATE"]  # ✅ 合并
    },

    # ==========================================
    # 📊 二、投资活动现金流 (Investing Cash Flow)
    # ==========================================
    "CAPITAL_EXPENDITURE": {
        "obb": ["capital_expenditure"],
        "akshare": ["购建固定资产、无形资产和其他长期资产支付的现金",
                    "购建固定资产", "资本开支", "资本支出"]  # ✅ 合并
    },
    "PURCHASE_OF_INTANGIBLE_AND_OTHER_ASSETS": {
        # 🚀 新增：购建无形资产
        "obb": [],
        "akshare": ["购建无形资产及其他资产"]
    },
    "PROCEEDS_FROM_SALE_OF_PPE": {
        # 🚀 新增：处置固定资产
        "obb": [],
        "akshare": ["处置固定资产"]
    },
    "PROCEEDS_FROM_SALE_OF_INTANGIBLE_AND_OTHER_ASSETS": {
        # 🚀 新增：处置无形资产
        "obb": [],
        "akshare": ["处置无形资产及其他资产"]
    },
    "INVESTMENTS_IN_PROPERTY_PLANT_AND_EQUIPMENT": {
        "obb": ["investments_in_property_plant_and_equipment"],
        "akshare": []
    },
    "NET_PPE_PURCHASE_AND_SALE": {
        "obb": ["net_ppe_purchase_and_sale"],
        "akshare": []
    },
    "PURCHASE_OF_BUSINESS": {
        "obb": ["purchase_of_business"],
        "akshare": ["购买子公司", "收购企业", "收购附属公司"]  # ✅ 合并港股格式
    },
    "PROCEEDS_FROM_SALE_OF_BUSINESS": {
        # 🚀 新增：出售附属公司
        "obb": [],
        "akshare": ["出售附属公司"]
    },
    "PURCHASE_OF_MINORITY_INTERESTS": {
        # 🚀 新增：购买子公司少数股权
        "obb": [],
        "akshare": ["购买子公司少数股权而支付的现金"]
    },
    "NET_BUSINESS_PURCHASE_AND_SALE": {
        "obb": ["net_business_purchase_and_sale"],
        "akshare": []
    },
    "PURCHASE_OF_INVESTMENT": {
        "obb": ["purchase_of_investment"],
        "akshare": ["投资支付的现金", "购买投资"]  # ✅ 合并
    },
    "SALE_OF_INVESTMENT": {
        "obb": ["sale_of_investment"],
        "akshare": ["收回投资收到的现金", "出售投资", "收回投资所得现金"]  # ✅ 合并港股格式
    },
    "NET_INVESTMENT_PURCHASE_AND_SALE": {
        "obb": ["net_investment_purchase_and_sale"],
        "akshare": []
    },
    "CHANGE_IN_TERM_DEPOSITS": {
        # 🚀 新增：长短期定期存款进出
        "obb": [],
        "akshare": ["存款(增加)减少", "存款减少(增加)"]
    },
    
    # ==========================================
    # 🔴 核心 FCF 调整项 (Core FCF Adjustments)
    # ==========================================
    "CF_ADJUSTMENT_SHARE_BASED_COMPENSATION": {
        "obb": ["stock_based_compensation"],
        "akshare": ["加:购股权开支"]
    },
    
    # ==========================================
    # 🔵 投资与经营相关变动项 (Investing & Operating Cash Changes)
    # ==========================================
    "CASH_PAID_FOR_INVESTMENTS": {
        "obb": [],
        "akshare": ["投资支付现金"]
    },
    "CHANGE_IN_RESTRICTED_CASH": {
        "obb": [],
        "akshare": ["受限制存款及现金增加(减少)"]
    },
    "CHANGE_IN_LOANS_AND_ADVANCES": {
        "obb": [],
        "akshare": ["贷款和垫款(增加)减少"]
    },
    "CHANGE_IN_TRADING_INVESTMENTS": {
        # 🚀 新增：买卖投资变动
        "obb": [],
        "akshare": ["持作买卖投资(增加)减少"]
    },
    "CHANGE_IN_RECEIVABLES_FROM_RELATED_PARTIES_INVESTING": {
        # 🚀 新增：应收关联方款项(投资)
        "obb": [],
        "akshare": ["应收关联方款项(增加)减少(投资)"]
    },
    "INTEREST_RECEIVED_INVESTING": {
        # 🚀 新增：(IFRS 归类至投资)
        "obb": [],
        "akshare": ["已收利息(投资)"]
    },
    "DIVIDENDS_RECEIVED_INVESTING": {
        # 🚀 新增：(IFRS 归类至投资)
        "obb": [],
        "akshare": ["已收股息(投资)"]
    },
    "NET_OTHER_INVESTING_CHANGES": {
        "obb": ["net_other_investing_changes"],
        "akshare": ["投资业务其他项目"]  # ✅ 添加港股格式
    },
    "CASH_FLOW_FROM_CONTINUING_INVESTING_ACTIVITIES": {
        "obb": ["cash_flow_from_continuing_investing_activities"],
        "akshare": []
    },
    "INVESTING_CASH_FLOW": {
        "obb": ["investing_cash_flow"],
        "akshare": ["投资活动产生的现金流量净额", "投资业务现金净额"]  # ✅ 合并
    },

    # ==========================================
    # 📊 三、融资活动现金流 (Financing Cash Flow)
    # ==========================================
    "PROCEEDS_FROM_BORROWINGS": {
        # 修正：借款毛流入，跨市场复用（issuance_of_debt 从独立映射移入）
        "obb": ["issuance_of_debt"],
        "akshare": ["新增借款", "借款收到的现金"]  # 从 NET_ISSUANCE_PAYMENTS_OF_DEBT 移入
    },
    "REPAYMENT_OF_DEBT": {
        "obb": ["repayment_of_debt"],
        "akshare": ["偿还债务支付的现金", "偿还借款"]  # ✅ 合并港股格式
    },
    "PROCEEDS_FROM_ISSUANCE_OF_BONDS": {
        # 🚀 新增：发行债券
        "obb": [],
        "akshare": ["发行债券"]
    },
    "REPAYMENT_OF_BONDS": {
        # 🚀 新增：赎回债券
        "obb": [],
        "akshare": ["赎回债券"]
    },
    "LONG_TERM_DEBT_ISSUANCE": {
        # 新增：纯发行（流入），区别于 Net Issuance
        "obb": ["long_term_debt_issuance"],
        "akshare": []
    },
    "LONG_TERM_DEBT_PAYMENTS": {
        "obb": ["long_term_debt_payments"],
        "akshare": []
    },
    "NET_LONG_TERM_DEBT_ISSUANCE": {
        "obb": ["net_long_term_debt_issuance"],
        "akshare": []
    },
    "SHORT_TERM_DEBT_ISSUANCE": {
        # 新增：短期债务发行（纯流入）
        "obb": ["short_term_debt_issuance"],
        "akshare": []
    },
    "SHORT_TERM_DEBT_PAYMENTS": {
        "obb": ["short_term_debt_payments"],
        "akshare": []
    },
    "NET_SHORT_TERM_DEBT_ISSUANCE": {
        "obb": ["net_short_term_debt_issuance"],
        "akshare": []
    },
    "NET_ISSUANCE_PAYMENTS_OF_DEBT": {
        "obb": ["net_issuance_payments_of_debt"],
        "akshare": ["债务净变动"]  # 踢出 "借款收到的现金"（毛流入不能放在净变动里）
    },
    "PROCEEDS_FROM_CAPITAL_CONTRIBUTIONS": {
        # 🚀 新增：吸收投资
        "obb": [],
        "akshare": ["吸收投资所得"]
    },
    "SHARE_ISSUANCE_COSTS": {
        # 🚀 新增：发行费用
        "obb": [],
        "akshare": ["发行相关费用"]
    },
    "ISSUANCE_OF_CAPITAL_STOCK": {
        "obb": ["issuance_of_capital_stock"],
        "akshare": ["发行股份"]  # ✅ 添加港股格式
    },
    "ISSUANCE_OF_COMMON_EQUITY": {
        "obb": ["issuance_of_common_equity"],
        "akshare": []
    },
    "REPURCHASE_OF_CAPITAL_STOCK": {
        "obb": ["repurchase_of_capital_stock"],
        "akshare": ["回购股票", "回购股份"]  # ✅ 合并港股格式
    },
    "REPURCHASE_OF_COMMON_EQUITY": {
        "obb": ["repurchase_of_common_equity"],
        "akshare": []
    },
    "NET_COMMON_STOCK_ISSUANCE": {
        "obb": ["net_common_stock_issuance"],
        "akshare": ["吸收投资收到的现金", "发行股票净额"]
    },
    "COMMON_STOCK_DIVIDEND_PAID": {
        "obb": ["common_stock_dividend_paid"],
        "akshare": []
    },
    "CASH_DIVIDENDS_PAID": {
        "obb": ["cash_dividends_paid"],
        "akshare": ["分配股利、利润或偿付利息支付的现金", "支付股利", "已付股息(融资)"]  # ✅ 合并港股格式
    },
    "INTEREST_PAID_FINANCING": {
        # 🚀 新增：(IFRS 归类至融资)
        "obb": [],
        "akshare": ["已付利息(融资)"]
    },
    "PRINCIPAL_PAYMENTS_FOR_FINANCE_LEASES": {
        # 🚀 新增：租赁负债还本
        "obb": [],
        "akshare": ["偿还融资租赁"]
    },
    "CHANGE_IN_PAYABLES_TO_RELATED_PARTIES": {
        # 🚀 新增：应付关联方款项变动 (勘误修正：去除 _FINANCING 后缀)
        "obb": [],
        "akshare": ["应付关联方款项增加(减少)"]
    },
    "NET_OTHER_FINANCING_CHARGES": {
        "obb": ["net_other_financing_charges"],
        "akshare": ["融资业务其他项目"]  # ✅ 添加港股格式
    },
    "CASH_FLOW_FROM_CONTINUING_FINANCING_ACTIVITIES": {
        "obb": ["cash_flow_from_continuing_financing_activities"],
        "akshare": []
    },
    "FINANCING_CASH_FLOW": {
        "obb": ["financing_cash_flow"],
        "akshare": ["筹资活动产生的现金流量净额", "融资业务现金净额"]  # ✅ 合并
    },

    # ==========================================
    # 📊 四、现金变动与衍生总计 (Cash Changes & Derived)
    # ==========================================
    "FREE_CASH_FLOW_BEFORE_FINANCING": {
        # 🚀 新增：港股极具特色的现金流诊断节点
        "obb": [],
        "akshare": ["融资前现金净额"]
    },
    "FREE_CASH_FLOW": {
        "obb": ["free_cash_flow"],
        "akshare": ["自由现金流", "自由现金流量"]
    },
    "NET_CHANGE_IN_CASH_AND_EQUIVALENTS": {
        "obb": ["net_change_in_cash_and_equivalents"],
        "akshare": ["现金及等价物净增加额", "现金净变动", "现金净额"]  # ✅ 合并港股格式
    },
    "EFFECT_OF_EXCHANGE_RATE_CHANGES": {
        "obb": ["effect_of_exchange_rate_changes"],
        "akshare": ["汇率变动影响"]  # ✅ 勘误修正：回归本源
    },
    "OTHER_CHANGES_IN_CASH_AND_EQUIVALENTS": {
        # 🚀 新增：期间变动其他项目 (勘误修正：独立字段，不混入汇率)
        "obb": [],
        "akshare": ["期间变动其他项目"]
    },
    "BEGINNING_CASH_POSITION": {
        "obb": ["beginning_cash_position"],
        "akshare": ["期初现金及等价物余额", "期初现金"]  # ✅ 合并港股格式
    },
    "END_CASH_POSITION": {
        "obb": ["end_cash_position"],
        "akshare": ["期末现金及等价物余额", "期末现金"]  # ✅ 合并港股格式
    }
}


# ==========================================
# 2. 键名常量 Mixin (FinKey Mixin)
# 用于 data_utils.py 的 FinKey 类继承
# ==========================================
class CashFlowKey:
    """
    现金流量表字段常量 Mixin
    供 FinKey 类继承，实现静态类型支持
    """
    # ==========================================
    # 📊 一、经营活动现金流 (Operating Cash Flow)
    # ==========================================
    # --- 1.1 起点与非现金调整 (Starting Line & Non-Cash Adjustments) ---
    NET_INCOME_FROM_CONTINUING_OPERATIONS: str = "NET_INCOME_FROM_CONTINUING_OPERATIONS"
    PRETAX_PROFIT_STARTING_LINE: str = "PRETAX_PROFIT_STARTING_LINE"  # 🚀 新增
    OPERATING_GAINS_LOSSES: str = "OPERATING_GAINS_LOSSES"
    DEPRECIATION: str = "DEPRECIATION"
    DEPRECIATION_AND_AMORTIZATION: str = "DEPRECIATION_AND_AMORTIZATION"
    DEPRECIATION_AMORTIZATION_DEPLETION: str = "DEPRECIATION_AMORTIZATION_DEPLETION"  # 新增
    DEFERRED_INCOME_TAX: str = "DEFERRED_INCOME_TAX"
    DEFERRED_TAX: str = "DEFERRED_TAX"  # 新增
    STOCK_BASED_COMPENSATION: str = "STOCK_BASED_COMPENSATION"
    ASSET_IMPAIRMENT_CHARGE: str = "ASSET_IMPAIRMENT_CHARGE"  # 更名复用
    GAIN_LOSS_ON_INVESTMENT_SECURITIES: str = "GAIN_LOSS_ON_INVESTMENT_SECURITIES"  # 新增
    UNREALIZED_GAIN_LOSS_ON_INVESTMENT_SECURITIES: str = "UNREALIZED_GAIN_LOSS_ON_INVESTMENT_SECURITIES"  # 新增
    CF_ADJUSTMENT_INTEREST_EXPENSE: str = "CF_ADJUSTMENT_INTEREST_EXPENSE"  # 🚀 新增
    CF_ADJUSTMENT_INTEREST_INCOME: str = "CF_ADJUSTMENT_INTEREST_INCOME"  # 🚀 新增
    CF_ADJUSTMENT_INVESTMENT_INCOME: str = "CF_ADJUSTMENT_INVESTMENT_INCOME"  # 🚀 新增
    CF_ADJUSTMENT_GAIN_ON_SALE_OF_ASSETS: str = "CF_ADJUSTMENT_GAIN_ON_SALE_OF_ASSETS"  # 🚀 新增
    CF_ADJUSTMENT_FOREIGN_EXCHANGE_GAIN: str = "CF_ADJUSTMENT_FOREIGN_EXCHANGE_GAIN"  # 🚀 新增
    CF_ADJUSTMENT_REVALUATION_SURPLUS: str = "CF_ADJUSTMENT_REVALUATION_SURPLUS"  # 🚀 新增
    CF_ADJUSTMENT_PROFIT_OF_SUBSIDIARIES: str = "CF_ADJUSTMENT_PROFIT_OF_SUBSIDIARIES"  # 🚀 新增 (勘误修正)
    CF_ADJUSTMENT_OTHER_OPERATING_ITEMS: str = "CF_ADJUSTMENT_OTHER_OPERATING_ITEMS"  # 🚀 新增
    CF_ADJUSTMENT_SHARE_BASED_COMPENSATION: str = "CF_ADJUSTMENT_SHARE_BASED_COMPENSATION"  # 🔴 核心FCF调整项
    OPERATING_PROFIT_BEFORE_WORKING_CAPITAL_CHANGES: str = "OPERATING_PROFIT_BEFORE_WORKING_CAPITAL_CHANGES"  # 🚀 新增

    # --- 1.2 营运资本变动 (Changes in Working Capital) ---
    CHANGES_IN_ACCOUNT_RECEIVABLES: str = "CHANGES_IN_ACCOUNT_RECEIVABLES"
    CHANGE_IN_RECEIVABLES: str = "CHANGE_IN_RECEIVABLES"
    CHANGE_IN_INVENTORY: str = "CHANGE_IN_INVENTORY"
    CHANGE_IN_ACCOUNT_PAYABLE: str = "CHANGE_IN_ACCOUNT_PAYABLE"
    CHANGE_IN_PAYABLE: str = "CHANGE_IN_PAYABLE"
    CHANGE_IN_PAYABLES_AND_ACCRUED_EXPENSE: str = "CHANGE_IN_PAYABLES_AND_ACCRUED_EXPENSE"
    CHANGE_IN_PREPAYMENTS_AND_OTHER_RECEIVABLES: str = "CHANGE_IN_PREPAYMENTS_AND_OTHER_RECEIVABLES"  # 🚀 新增
    CHANGE_IN_ADVANCES_AND_OTHER_PAYABLES: str = "CHANGE_IN_ADVANCES_AND_OTHER_PAYABLES"  # 🚀 新增
    CHANGE_IN_DEFERRED_REVENUE: str = "CHANGE_IN_DEFERRED_REVENUE"  # 🚀 新增
    CHANGE_IN_OTHER_CURRENT_ASSETS: str = "CHANGE_IN_OTHER_CURRENT_ASSETS"
    CHANGE_IN_OTHER_CURRENT_LIABILITIES: str = "CHANGE_IN_OTHER_CURRENT_LIABILITIES"
    CHANGE_IN_OTHER_WORKING_CAPITAL: str = "CHANGE_IN_OTHER_WORKING_CAPITAL"
    CHANGE_IN_WORKING_CAPITAL: str = "CHANGE_IN_WORKING_CAPITAL"
    CHANGE_IN_INCOME_TAX_PAYABLE: str = "CHANGE_IN_INCOME_TAX_PAYABLE"  # 新增
    CHANGE_IN_TAX_PAYABLE: str = "CHANGE_IN_TAX_PAYABLE"  # 新增

    # --- 1.3 经营活动税息与净额 (Taxes, Interest & Net Operating CF) ---
    CASH_GENERATED_FROM_OPERATIONS: str = "CASH_GENERATED_FROM_OPERATIONS"  # 🚀 新增
    INCOME_TAX_PAID: str = "INCOME_TAX_PAID"  # 🚀 新增
    INTEREST_PAID_OPERATING: str = "INTEREST_PAID_OPERATING"  # 🚀 新增
    CASH_FLOW_FROM_CONTINUING_OPERATING_ACTIVITIES: str = "CASH_FLOW_FROM_CONTINUING_OPERATING_ACTIVITIES"
    OPERATING_CASH_FLOW: str = "OPERATING_CASH_FLOW"

    # ==========================================
    # 📊 二、投资活动现金流 (Investing Cash Flow)
    # ==========================================
    CAPITAL_EXPENDITURE: str = "CAPITAL_EXPENDITURE"
    PURCHASE_OF_INTANGIBLE_AND_OTHER_ASSETS: str = "PURCHASE_OF_INTANGIBLE_AND_OTHER_ASSETS"  # 🚀 新增
    PROCEEDS_FROM_SALE_OF_PPE: str = "PROCEEDS_FROM_SALE_OF_PPE"  # 🚀 新增
    PROCEEDS_FROM_SALE_OF_INTANGIBLE_AND_OTHER_ASSETS: str = "PROCEEDS_FROM_SALE_OF_INTANGIBLE_AND_OTHER_ASSETS"  # 🚀 新增
    INVESTMENTS_IN_PROPERTY_PLANT_AND_EQUIPMENT: str = "INVESTMENTS_IN_PROPERTY_PLANT_AND_EQUIPMENT"
    NET_PPE_PURCHASE_AND_SALE: str = "NET_PPE_PURCHASE_AND_SALE"
    PURCHASE_OF_BUSINESS: str = "PURCHASE_OF_BUSINESS"
    PROCEEDS_FROM_SALE_OF_BUSINESS: str = "PROCEEDS_FROM_SALE_OF_BUSINESS"  # 🚀 新增
    PURCHASE_OF_MINORITY_INTERESTS: str = "PURCHASE_OF_MINORITY_INTERESTS"  # 🚀 新增
    NET_BUSINESS_PURCHASE_AND_SALE: str = "NET_BUSINESS_PURCHASE_AND_SALE"
    PURCHASE_OF_INVESTMENT: str = "PURCHASE_OF_INVESTMENT"
    SALE_OF_INVESTMENT: str = "SALE_OF_INVESTMENT"
    NET_INVESTMENT_PURCHASE_AND_SALE: str = "NET_INVESTMENT_PURCHASE_AND_SALE"
    CHANGE_IN_TERM_DEPOSITS: str = "CHANGE_IN_TERM_DEPOSITS"  # 🚀 新增
    CHANGE_IN_TRADING_INVESTMENTS: str = "CHANGE_IN_TRADING_INVESTMENTS"  # 🚀 新增
    CASH_PAID_FOR_INVESTMENTS: str = "CASH_PAID_FOR_INVESTMENTS"  # 🔵 新增
    CHANGE_IN_RESTRICTED_CASH: str = "CHANGE_IN_RESTRICTED_CASH"  # 🔵 新增
    CHANGE_IN_LOANS_AND_ADVANCES: str = "CHANGE_IN_LOANS_AND_ADVANCES"  # 🔵 新增
    CHANGE_IN_RECEIVABLES_FROM_RELATED_PARTIES_INVESTING: str = "CHANGE_IN_RECEIVABLES_FROM_RELATED_PARTIES_INVESTING"  # 🚀 新增
    INTEREST_RECEIVED_INVESTING: str = "INTEREST_RECEIVED_INVESTING"  # 🚀 新增
    DIVIDENDS_RECEIVED_INVESTING: str = "DIVIDENDS_RECEIVED_INVESTING"  # 🚀 新增
    NET_OTHER_INVESTING_CHANGES: str = "NET_OTHER_INVESTING_CHANGES"
    CASH_FLOW_FROM_CONTINUING_INVESTING_ACTIVITIES: str = "CASH_FLOW_FROM_CONTINUING_INVESTING_ACTIVITIES"
    INVESTING_CASH_FLOW: str = "INVESTING_CASH_FLOW"

    # ==========================================
    # 📊 三、融资活动现金流 (Financing Cash Flow)
    # ==========================================
    PROCEEDS_FROM_BORROWINGS: str = "PROCEEDS_FROM_BORROWINGS"  # 🚀 新增
    REPAYMENT_OF_DEBT: str = "REPAYMENT_OF_DEBT"
    PROCEEDS_FROM_ISSUANCE_OF_BONDS: str = "PROCEEDS_FROM_ISSUANCE_OF_BONDS"  # 🚀 新增
    REPAYMENT_OF_BONDS: str = "REPAYMENT_OF_BONDS"  # 🚀 新增
    LONG_TERM_DEBT_ISSUANCE: str = "LONG_TERM_DEBT_ISSUANCE"  # 新增
    LONG_TERM_DEBT_PAYMENTS: str = "LONG_TERM_DEBT_PAYMENTS"
    NET_LONG_TERM_DEBT_ISSUANCE: str = "NET_LONG_TERM_DEBT_ISSUANCE"
    SHORT_TERM_DEBT_ISSUANCE: str = "SHORT_TERM_DEBT_ISSUANCE"  # 新增
    SHORT_TERM_DEBT_PAYMENTS: str = "SHORT_TERM_DEBT_PAYMENTS"
    NET_SHORT_TERM_DEBT_ISSUANCE: str = "NET_SHORT_TERM_DEBT_ISSUANCE"
    NET_ISSUANCE_PAYMENTS_OF_DEBT: str = "NET_ISSUANCE_PAYMENTS_OF_DEBT"
    PROCEEDS_FROM_CAPITAL_CONTRIBUTIONS: str = "PROCEEDS_FROM_CAPITAL_CONTRIBUTIONS"  # 🚀 新增
    SHARE_ISSUANCE_COSTS: str = "SHARE_ISSUANCE_COSTS"  # 🚀 新增
    ISSUANCE_OF_CAPITAL_STOCK: str = "ISSUANCE_OF_CAPITAL_STOCK"
    ISSUANCE_OF_COMMON_EQUITY: str = "ISSUANCE_OF_COMMON_EQUITY"
    REPURCHASE_OF_CAPITAL_STOCK: str = "REPURCHASE_OF_CAPITAL_STOCK"
    REPURCHASE_OF_COMMON_EQUITY: str = "REPURCHASE_OF_COMMON_EQUITY"
    NET_COMMON_STOCK_ISSUANCE: str = "NET_COMMON_STOCK_ISSUANCE"
    COMMON_STOCK_DIVIDEND_PAID: str = "COMMON_STOCK_DIVIDEND_PAID"
    CASH_DIVIDENDS_PAID: str = "CASH_DIVIDENDS_PAID"
    INTEREST_PAID_FINANCING: str = "INTEREST_PAID_FINANCING"  # 🚀 新增
    PRINCIPAL_PAYMENTS_FOR_FINANCE_LEASES: str = "PRINCIPAL_PAYMENTS_FOR_FINANCE_LEASES"  # 🚀 新增
    CHANGE_IN_PAYABLES_TO_RELATED_PARTIES: str = "CHANGE_IN_PAYABLES_TO_RELATED_PARTIES"  # 🚀 新增 (勘误修正)
    NET_OTHER_FINANCING_CHARGES: str = "NET_OTHER_FINANCING_CHARGES"
    CASH_FLOW_FROM_CONTINUING_FINANCING_ACTIVITIES: str = "CASH_FLOW_FROM_CONTINUING_FINANCING_ACTIVITIES"
    FINANCING_CASH_FLOW: str = "FINANCING_CASH_FLOW"

    # ==========================================
    # 📊 四、现金变动与衍生总计 (Cash Changes & Derived)
    # ==========================================
    FREE_CASH_FLOW_BEFORE_FINANCING: str = "FREE_CASH_FLOW_BEFORE_FINANCING"  # 🚀 新增
    FREE_CASH_FLOW: str = "FREE_CASH_FLOW"
    NET_CHANGE_IN_CASH_AND_EQUIVALENTS: str = "NET_CHANGE_IN_CASH_AND_EQUIVALENTS"
    EFFECT_OF_EXCHANGE_RATE_CHANGES: str = "EFFECT_OF_EXCHANGE_RATE_CHANGES"
    OTHER_CHANGES_IN_CASH_AND_EQUIVALENTS: str = "OTHER_CHANGES_IN_CASH_AND_EQUIVALENTS"  # 🚀 新增 (勘误修正)
    BEGINNING_CASH_POSITION: str = "BEGINNING_CASH_POSITION"
    END_CASH_POSITION: str = "END_CASH_POSITION"



# ==========================================
# 3. Pydantic 模型 Mixin (Schema Mixin)
# 用于 schema_standard.py 的 StandardFinancialRecord 类继承
# 必须显式声明类型，拒绝动态生成！
# ==========================================
class CashFlowRecord(BaseModel):
    """
    现金流量表字段 Pydantic 模型 Mixin
    供 StandardFinancialRecord 类继承，实现静态类型支持

    设计原则：
    - 所有字段显式声明类型
    - 所有字段默认值为 None (Optional)
    - 保留 IDE 类型推断和代码补全
    """

    # ==========================================
    # 📊 一、经营活动现金流 (Operating Cash Flow)
    # ==========================================
    # --- 1.1 起点与非现金调整 (Starting Line & Non-Cash Adjustments) ---
    NET_INCOME_FROM_CONTINUING_OPERATIONS: Optional[float] = None  # 持续经营净利润 (美股起点)
    PRETAX_PROFIT_STARTING_LINE: Optional[float] = None  # 除税前溢利 (港股间接法起点)
    OPERATING_GAINS_LOSSES: Optional[float] = None  # 经营损益
    DEPRECIATION: Optional[float] = None  # 折旧
    DEPRECIATION_AND_AMORTIZATION: Optional[float] = None  # 折旧和摊销
    DEPRECIATION_AMORTIZATION_DEPLETION: Optional[float] = None  # 折旧、摊销和耗竭
    DEFERRED_INCOME_TAX: Optional[float] = None  # 递延所得税
    DEFERRED_TAX: Optional[float] = None  # 递延税项
    STOCK_BASED_COMPENSATION: Optional[float] = None  # 股份支付/股权激励
    ASSET_IMPAIRMENT_CHARGE: Optional[float] = None  # 资产减值费用
    GAIN_LOSS_ON_INVESTMENT_SECURITIES: Optional[float] = None  # 投资证券损益（已实现）
    UNREALIZED_GAIN_LOSS_ON_INVESTMENT_SECURITIES: Optional[float] = None  # 未实现投资证券损益
    CF_ADJUSTMENT_INTEREST_EXPENSE: Optional[float] = None  # 加:利息支出
    CF_ADJUSTMENT_INTEREST_INCOME: Optional[float] = None  # 减:利息收入
    CF_ADJUSTMENT_INVESTMENT_INCOME: Optional[float] = None  # 减:投资收益
    CF_ADJUSTMENT_GAIN_ON_SALE_OF_ASSETS: Optional[float] = None  # 减:出售资产之溢利
    CF_ADJUSTMENT_FOREIGN_EXCHANGE_GAIN: Optional[float] = None  # 减:汇兑收益
    CF_ADJUSTMENT_REVALUATION_SURPLUS: Optional[float] = None  # 减:重估盈余 (地产股核心)
    CF_ADJUSTMENT_PROFIT_OF_SUBSIDIARIES: Optional[float] = None  # 减:应占附属公司溢利
    CF_ADJUSTMENT_OTHER_OPERATING_ITEMS: Optional[float] = None  # 加:经营调整其他项目
    CF_ADJUSTMENT_SHARE_BASED_COMPENSATION: Optional[float] = None  # 加:购股权开支 (FCF核心调整项)
    OPERATING_PROFIT_BEFORE_WORKING_CAPITAL_CHANGES: Optional[float] = None  # 营运资金变动前经营溢利

    # --- 1.2 营运资本变动 (Changes in Working Capital) ---
    CHANGES_IN_ACCOUNT_RECEIVABLES: Optional[float] = None  # 应收账款变动
    CHANGE_IN_RECEIVABLES: Optional[float] = None  # 应收项目变动
    CHANGE_IN_INVENTORY: Optional[float] = None  # 存货变动
    CHANGE_IN_ACCOUNT_PAYABLE: Optional[float] = None  # 应付账款变动
    CHANGE_IN_PAYABLE: Optional[float] = None  # 应付项目变动
    CHANGE_IN_PAYABLES_AND_ACCRUED_EXPENSE: Optional[float] = None  # 应付帐款及应计费用变动
    CHANGE_IN_PREPAYMENTS_AND_OTHER_RECEIVABLES: Optional[float] = None  # 预付款项、按金及其他应收款项变动
    CHANGE_IN_ADVANCES_AND_OTHER_PAYABLES: Optional[float] = None  # 预收账款、按金及其他应付款变动
    CHANGE_IN_DEFERRED_REVENUE: Optional[float] = None  # 递延收入变动
    CHANGE_IN_OTHER_CURRENT_ASSETS: Optional[float] = None  # 其他流动资产变动
    CHANGE_IN_OTHER_CURRENT_LIABILITIES: Optional[float] = None  # 其他流动负债变动
    CHANGE_IN_OTHER_WORKING_CAPITAL: Optional[float] = None  # 营运资本变动其他项目
    CHANGE_IN_WORKING_CAPITAL: Optional[float] = None  # 营运资金变动总计
    CHANGE_IN_INCOME_TAX_PAYABLE: Optional[float] = None  # 营运资本-所得税应付变动
    CHANGE_IN_TAX_PAYABLE: Optional[float] = None  # 营运资本-总税项应付变动

    # --- 1.3 经营活动税息与净额 (Taxes, Interest & Net Operating CF) ---
    CASH_GENERATED_FROM_OPERATIONS: Optional[float] = None  # 经营产生现金 (未扣税息前)
    INCOME_TAX_PAID: Optional[float] = None  # 实缴所得税
    INTEREST_PAID_OPERATING: Optional[float] = None  # 已付利息(经营)
    CASH_FLOW_FROM_CONTINUING_OPERATING_ACTIVITIES: Optional[float] = None  # 持续经营经营活动现金流
    OPERATING_CASH_FLOW: Optional[float] = None  # 经营活动现金流量净额

    # ==========================================
    # 📊 二、投资活动现金流 (Investing Cash Flow)
    # ==========================================
    CAPITAL_EXPENDITURE: Optional[float] = None  # 资本支出
    PURCHASE_OF_INTANGIBLE_AND_OTHER_ASSETS: Optional[float] = None  # 购建无形资产及其他资产
    PROCEEDS_FROM_SALE_OF_PPE: Optional[float] = None  # 处置固定资产所得
    PROCEEDS_FROM_SALE_OF_INTANGIBLE_AND_OTHER_ASSETS: Optional[float] = None  # 处置无形资产及其他资产所得
    INVESTMENTS_IN_PROPERTY_PLANT_AND_EQUIPMENT: Optional[float] = None  # 固定资产投资
    NET_PPE_PURCHASE_AND_SALE: Optional[float] = None  # 固定资产买卖净额
    PURCHASE_OF_BUSINESS: Optional[float] = None  # 收购附属公司
    PROCEEDS_FROM_SALE_OF_BUSINESS: Optional[float] = None  # 出售附属公司所得
    PURCHASE_OF_MINORITY_INTERESTS: Optional[float] = None  # 购买子公司少数股权
    NET_BUSINESS_PURCHASE_AND_SALE: Optional[float] = None  # 企业买卖净额
    PURCHASE_OF_INVESTMENT: Optional[float] = None  # 投资支付现金
    SALE_OF_INVESTMENT: Optional[float] = None  # 收回投资所得现金
    NET_INVESTMENT_PURCHASE_AND_SALE: Optional[float] = None  # 投资买卖净额
    CHANGE_IN_TERM_DEPOSITS: Optional[float] = None  # 定期存款变动
    CHANGE_IN_TRADING_INVESTMENTS: Optional[float] = None  # 持作买卖投资变动
    CASH_PAID_FOR_INVESTMENTS: Optional[float] = None  # 投资支付现金
    CHANGE_IN_RESTRICTED_CASH: Optional[float] = None  # 受限制存款及现金增加(减少)
    CHANGE_IN_LOANS_AND_ADVANCES: Optional[float] = None  # 贷款和垫款(增加)减少
    CHANGE_IN_RECEIVABLES_FROM_RELATED_PARTIES_INVESTING: Optional[float] = None  # 应收关联方款项变动(投资)
    INTEREST_RECEIVED_INVESTING: Optional[float] = None  # 已收利息(投资)
    DIVIDENDS_RECEIVED_INVESTING: Optional[float] = None  # 已收股息(投资)
    NET_OTHER_INVESTING_CHANGES: Optional[float] = None  # 投资业务其他项目
    CASH_FLOW_FROM_CONTINUING_INVESTING_ACTIVITIES: Optional[float] = None  # 持续经营投资活动现金流
    INVESTING_CASH_FLOW: Optional[float] = None  # 投资活动现金流量净额

    # ==========================================
    # 📊 三、融资活动现金流 (Financing Cash Flow)
    # ==========================================
    PROCEEDS_FROM_BORROWINGS: Optional[float] = None  # 新增借款
    REPAYMENT_OF_DEBT: Optional[float] = None  # 偿还借款
    PROCEEDS_FROM_ISSUANCE_OF_BONDS: Optional[float] = None  # 发行债券所得
    REPAYMENT_OF_BONDS: Optional[float] = None  # 赎回债券
    LONG_TERM_DEBT_ISSUANCE: Optional[float] = None  # 长期债务发行（纯流入）
    LONG_TERM_DEBT_PAYMENTS: Optional[float] = None  # 长期债务偿还
    NET_LONG_TERM_DEBT_ISSUANCE: Optional[float] = None  # 长期债务净发行
    SHORT_TERM_DEBT_ISSUANCE: Optional[float] = None  # 短期债务发行（纯流入）
    SHORT_TERM_DEBT_PAYMENTS: Optional[float] = None  # 短期债务偿还
    NET_SHORT_TERM_DEBT_ISSUANCE: Optional[float] = None  # 短期债务净发行
    NET_ISSUANCE_PAYMENTS_OF_DEBT: Optional[float] = None  # 债务净变动
    PROCEEDS_FROM_CAPITAL_CONTRIBUTIONS: Optional[float] = None  # 吸收投资所得
    SHARE_ISSUANCE_COSTS: Optional[float] = None  # 发行相关费用
    ISSUANCE_OF_CAPITAL_STOCK: Optional[float] = None  # 发行股份
    ISSUANCE_OF_COMMON_EQUITY: Optional[float] = None  # 发行普通股
    REPURCHASE_OF_CAPITAL_STOCK: Optional[float] = None  # 回购股份
    REPURCHASE_OF_COMMON_EQUITY: Optional[float] = None  # 回购普通股
    NET_COMMON_STOCK_ISSUANCE: Optional[float] = None  # 普通股净发行
    COMMON_STOCK_DIVIDEND_PAID: Optional[float] = None  # 普通股股利支付
    CASH_DIVIDENDS_PAID: Optional[float] = None  # 现金股利支付
    INTEREST_PAID_FINANCING: Optional[float] = None  # 已付利息(融资)
    PRINCIPAL_PAYMENTS_FOR_FINANCE_LEASES: Optional[float] = None  # 偿还融资租赁
    CHANGE_IN_PAYABLES_TO_RELATED_PARTIES: Optional[float] = None  # 应付关联方款项变动
    NET_OTHER_FINANCING_CHARGES: Optional[float] = None  # 融资业务其他项目
    CASH_FLOW_FROM_CONTINUING_FINANCING_ACTIVITIES: Optional[float] = None  # 持续经营融资活动现金流
    FINANCING_CASH_FLOW: Optional[float] = None  # 融资活动现金流量净额

    # ==========================================
    # 📊 四、现金变动与衍生总计 (Cash Changes & Derived)
    # ==========================================
    FREE_CASH_FLOW_BEFORE_FINANCING: Optional[float] = None  # 融资前现金净额 (港股特色诊断节点)
    FREE_CASH_FLOW: Optional[float] = None  # 自由现金流
    NET_CHANGE_IN_CASH_AND_EQUIVALENTS: Optional[float] = None  # 现金净变动
    EFFECT_OF_EXCHANGE_RATE_CHANGES: Optional[float] = None  # 汇率变动影响
    OTHER_CHANGES_IN_CASH_AND_EQUIVALENTS: Optional[float] = None  # 期间变动其他项目
    BEGINNING_CASH_POSITION: Optional[float] = None  # 期初现金
    END_CASH_POSITION: Optional[float] = None  # 期末现金


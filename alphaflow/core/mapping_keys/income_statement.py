"""
利润表核心契约 (Income Statement Domain)
==========================================
单一数据源 (Single Source of Truth)

设计哲学：
- 高内聚低耦合：所有利润表相关定义集中于此
- 静态 Mixin 模式：保留 IDE 类型推断和静态检查
- 严格一一映射：每个原始字段只映射一个标准字段

更新日志：
- 2026-03-11: 重构港股映射，基于 AkShare 港股利润表 32 个 STD_ITEM_NAME 逐一审计
              采用架构师裁决的标准字段命名，符合 IFRS/HKFRS 规范
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


# ==========================================
# 1. OBB → 标准字段映射表 (严格一一映射)
# 用于 adapters.py 的 FINANCIAL_MAPPING 合并
# ==========================================
INCOME_STATEMENT_MAPPING: Dict[str, Dict[str, List[str]]] = {
    # ==========================================
    # 一、收入与成本 (Revenue & Cost)
    # ==========================================
    "TOTAL_REVENUE": {"obb": ["total_revenue"], "akshare": ["营业额"]},
    "OPERATING_REVENUE": {"obb": ["operating_revenue"], "akshare": ["营运收入"]},
    "COST_OF_REVENUE": {"obb": ["cost_of_revenue"], "akshare": ["销售成本"]},
    "GROSS_PROFIT": {"obb": ["gross_profit"], "akshare": ["毛利"]},
    
    # ==========================================
    # 二、期间费用 (Operating Expenses)
    # ==========================================
    "RESEARCH_AND_DEVELOPMENT_EXPENSE": {"obb": ["research_and_development_expense"], "akshare": ["研发费用"]},
    "SELLING_GENERAL_AND_ADMINISTRATIVE_EXPENSE": {"obb": ["selling_general_and_admin_expense"], "akshare": []},
    "SELLING_MARKETING_EXPENSE": {"obb": ["selling_and_marketing_expense"], "akshare": ["销售及分销费用"]},
    "GENERAL_ADMIN_EXPENSE": {"obb": ["general_and_administrative_expense"], "akshare": ["行政开支"]},
    "TOTAL_OPERATING_EXPENSES": {"obb": ["operating_expense"], "akshare": ["营运支出"]},
    "RECONCILED_DEPRECIATION": {"obb": ["reconciled_depreciation"], "akshare": []},
    "OTHER_GENERAL_AND_ADMINISTRATIVE_EXPENSES": {"obb": ["other_gand_a"], "akshare": []},
    
    # ==========================================
    # 三、营业利润与 EBITDA (Operating Profit & EBITDA)
    # ==========================================
    "OPERATING_INCOME": {"obb": ["operating_income"], "akshare": ["经营溢利"]},
    "EBIT": {"obb": ["ebit"], "akshare": []},
    "EBITDA": {"obb": ["ebitda"], "akshare": []},
    "NORMALIZED_EBITDA": {"obb": ["normalized_ebitda"], "akshare": []},
    
    # ==========================================
    # 四、利息、非经与税前 (Interest, Non-Operating & Pretax)
    # ==========================================
    "INTEREST_INCOME": {"obb": ["interest_income"], "akshare": ["利息收入"]},
    "INTEREST_EXPENSE": {"obb": ["interest_expense"], "akshare": ["融资成本"]},
    "NET_INTEREST_INCOME": {"obb": ["net_interest_income"], "akshare": []},
    "INTEREST_INCOME_NON_OPERATING": {"obb": ["interest_income_non_operating"], "akshare": []},
    "INTEREST_EXPENSE_NON_OPERATING": {"obb": ["interest_expense_non_operating"], "akshare": []},
    "NET_NON_OPERATING_INTEREST_INCOME_EXPENSE": {"obb": ["net_non_operating_interest_income_expense"], "akshare": []},
    "TOTAL_UNUSUAL_ITEMS": {"obb": ["total_unusual_items"], "akshare": []},
    "PRETAX_INCOME": {"obb": ["total_pre_tax_income"], "akshare": ["除税前溢利"]},
    
    # ==========================================
    # 五、细分利润项 (Detailed Profit Items)
    # ==========================================
    "GAIN_ON_SALE_OF_SECURITY": {"obb": ["gain_on_sale_of_security"], "akshare": []},
    "WRITE_OFF": {"obb": ["write_off"], "akshare": []},
    "SPECIAL_INCOME_CHARGES": {"obb": ["special_income_charges"], "akshare": []},
    "OTHER_NON_OPERATING_INCOME_EXPENSES": {"obb": ["other_non_operating_income_expenses"], "akshare": []},
    "OTHER_NON_OPERATING_NET_ADJUSTMENTS": {"obb": ["other_income_expense"], "akshare": []},
    
    # ==========================================
    # 六、净利润 (Net Income)
    # ==========================================
    "TAX_PROVISION": {"obb": ["tax_provision"], "akshare": ["税项"]},
    "NET_INCOME_CONSOLIDATED": {"obb": ["net_income"], "akshare": ["期内利润", "期内溢利"]},
    "NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS": {"obb": ["net_income_including_noncontrolling_interests"], "akshare": ["除税后溢利"]},
    "NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS": {"obb": ["net_income_attributable_to_common_shareholders"], "akshare": ["股东应占溢利"]},
    "NET_INCOME_CONTINUING_OPERATIONS": {"obb": ["net_income_continuous_operations"], "akshare": ["持续经营业务税后利润"]},
    "NET_INCOME_FROM_CONTINUING_AND_DISCONTINUED_OPERATIONS": {"obb": ["net_income_from_continuing_and_discontinued_operation"], "akshare": []},
    "DILUTED_NET_INCOME_AVAILABLE_TO_COMMON_STOCKHOLDERS": {"obb": ["diluted_ni_availto_com_stockholders"], "akshare": []},
    "NET_INCOME_CONTINUING_OPERATIONS_NET_MINORITY_INTEREST": {"obb": ["net_income_from_continuing_operation_net_minority_interest"], "akshare": []},
    "NORMALIZED_NET_INCOME": {"obb": ["normalized_income"], "akshare": []},
    
    # ==========================================
    # 七、每股与股本 (Per Share & Shares)
    # ==========================================
    "BASIC_EARNINGS_PER_SHARE": {"obb": ["basic_earnings_per_share"], "akshare": ["每股基本盈利"]},
    "DILUTED_EARNINGS_PER_SHARE": {"obb": ["diluted_earnings_per_share"], "akshare": ["每股摊薄盈利"]},
    "WEIGHTED_AVERAGE_BASIC_SHARES_OUTSTANDING": {"obb": ["weighted_average_basic_shares_outstanding"], "akshare": []},
    "WEIGHTED_AVERAGE_DILUTED_SHARES_OUTSTANDING": {"obb": ["weighted_average_diluted_shares_outstanding"], "akshare": []},
    
    # ==========================================
    # 八、费用与调整 (Expenses & Adjustments)
    # ==========================================
    "TOTAL_COSTS_AND_OPERATING_EXPENSES": {"obb": ["total_expenses"], "akshare": []},
    "RECONCILED_COST_OF_REVENUE": {"obb": ["reconciled_cost_of_revenue"], "akshare": []},
    "OPERATING_INCOME_AS_REPORTED": {"obb": ["total_operating_income_as_reported"], "akshare": []},
    "TOTAL_UNUSUAL_ITEMS_EXCLUDING_GOODWILL": {"obb": ["total_unusual_items_excluding_goodwill"], "akshare": []},
    "TAX_RATE_FOR_CALCULATIONS": {"obb": ["tax_rate_for_calcs"], "akshare": []},
    "TAX_EFFECT_OF_UNUSUAL_ITEMS": {"obb": ["tax_effect_of_unusual_items"], "akshare": []},
    
    # ==========================================
    # 九、港股特有字段 (HK-Specific Fields - IFRS/HKFRS)
    # ==========================================
    # 其他收入/支出
    "OTHER_INCOME": {"obb": [], "akshare": ["其他收入"]},
    "OTHER_EXPENSE": {"obb": [], "akshare": ["其他支出"]},
    "OTHER_GAINS_AND_LOSSES": {"obb": [], "akshare": ["其他收益"]},
    
    # 少数股东损益 (IFRS NCI 术语 - 全球通用)
    "NET_INCOME_ATTRIBUTABLE_TO_NONCONTROLLING_INTERESTS": {"obb": ["minority_interests"], "akshare": ["少数股东损益"]},
    
    # 综合收益 (Comprehensive Income - 全球通用)
    "COMPREHENSIVE_INCOME": {"obb": ["total_comprehensive_income", "comprehensive_income_net_of_tax"], "akshare": ["全面收益总额"]},
    "OTHER_COMPREHENSIVE_INCOME": {"obb": ["other_comprehensive_income"], "akshare": ["其他全面收益"]},
    "OTHER_COMPREHENSIVE_INCOME_OTHER": {"obb": [], "akshare": ["其他全面收益其他项目"]},
    "COMPREHENSIVE_INCOME_ATTRIBUTABLE_TO_PARENT": {"obb": [], "akshare": ["本公司拥有人应占全面收益总额"]},
    "COMPREHENSIVE_INCOME_ATTRIBUTABLE_TO_NONCONTROLLING_INTERESTS": {"obb": [], "akshare": ["非控股权益应占全面收益总额"]},
    
    # 联营/合营公司 (Associates & Joint Ventures)
    "SHARE_OF_PROFIT_ASSOCIATES": {"obb": [], "akshare": ["应占联营公司溢利"]},
    "SHARE_OF_PROFIT_JOINT_VENTURES": {"obb": [], "akshare": ["应占合营公司溢利"]},
    
    # 其他
    "OTHER_PROFIT_ITEMS": {"obb": [], "akshare": ["溢利其他项目"]},
    "OTHER_OPERATING_REVENUE": {"obb": [], "akshare": ["其他营业收入"]},
    "NON_OPERATING_ITEMS": {"obb": [], "akshare": ["非运算项目"]},
    
    # 投资物业重估 (地产股核心科目)
    "REVALUATION_SURPLUS_ON_INVESTMENT_PROPERTIES": {"obb": [], "akshare": ["重估盈余"]},
    
    # 股息附注 (利润表附注信息，不参与加总)
    "DIVIDENDS_DECLARED_SUPPLEMENTARY": {"obb": [], "akshare": ["股息"]},
    "DIVIDEND_PER_SHARE_SUPPLEMENTARY": {"obb": [], "akshare": ["每股股息"]},
}


# ==========================================
# 2. 键名常量 Mixin (FinKey Mixin)
# 用于 data_utils.py 的 FinKey 类继承
# ==========================================
class IncomeStatementKey:
    """
    利润表字段常量 Mixin
    供 FinKey 类继承，实现静态类型支持
    """
    # --- 1. 收入与成本 (Revenue & Cost) ---
    TOTAL_REVENUE: str = "TOTAL_REVENUE"
    OPERATING_REVENUE: str = "OPERATING_REVENUE"
    COST_OF_REVENUE: str = "COST_OF_REVENUE"
    GROSS_PROFIT: str = "GROSS_PROFIT"
    
    # --- 2. 期间费用 (Operating Expenses) ---
    RESEARCH_AND_DEVELOPMENT_EXPENSE: str = "RESEARCH_AND_DEVELOPMENT_EXPENSE"
    SELLING_GENERAL_AND_ADMINISTRATIVE_EXPENSE: str = "SELLING_GENERAL_AND_ADMINISTRATIVE_EXPENSE"
    SELLING_MARKETING_EXPENSE: str = "SELLING_MARKETING_EXPENSE"
    GENERAL_ADMIN_EXPENSE: str = "GENERAL_ADMIN_EXPENSE"
    TOTAL_OPERATING_EXPENSES: str = "TOTAL_OPERATING_EXPENSES"
    RECONCILED_DEPRECIATION: str = "RECONCILED_DEPRECIATION"
    OTHER_GENERAL_AND_ADMINISTRATIVE_EXPENSES: str = "OTHER_GENERAL_AND_ADMINISTRATIVE_EXPENSES"
    
    # --- 3. 营业利润与 EBITDA (Operating Profit & EBITDA) ---
    OPERATING_INCOME: str = "OPERATING_INCOME"
    EBIT: str = "EBIT"
    EBITDA: str = "EBITDA"
    NORMALIZED_EBITDA: str = "NORMALIZED_EBITDA"
    
    # --- 4. 利息、非经与税前 (Interest, Non-Operating & Pretax) ---
    INTEREST_INCOME: str = "INTEREST_INCOME"
    INTEREST_EXPENSE: str = "INTEREST_EXPENSE"
    NET_INTEREST_INCOME: str = "NET_INTEREST_INCOME"
    INTEREST_INCOME_NON_OPERATING: str = "INTEREST_INCOME_NON_OPERATING"
    INTEREST_EXPENSE_NON_OPERATING: str = "INTEREST_EXPENSE_NON_OPERATING"
    NET_NON_OPERATING_INTEREST_INCOME_EXPENSE: str = "NET_NON_OPERATING_INTEREST_INCOME_EXPENSE"
    TOTAL_UNUSUAL_ITEMS: str = "TOTAL_UNUSUAL_ITEMS"
    PRETAX_INCOME: str = "PRETAX_INCOME"
    
    # --- 5. 细分利润项 (Detailed Profit Items) ---
    GAIN_ON_SALE_OF_SECURITY: str = "GAIN_ON_SALE_OF_SECURITY"
    WRITE_OFF: str = "WRITE_OFF"
    SPECIAL_INCOME_CHARGES: str = "SPECIAL_INCOME_CHARGES"
    OTHER_NON_OPERATING_INCOME_EXPENSES: str = "OTHER_NON_OPERATING_INCOME_EXPENSES"
    OTHER_NON_OPERATING_NET_ADJUSTMENTS: str = "OTHER_NON_OPERATING_NET_ADJUSTMENTS"
    
    # --- 6. 净利润 (Net Income) ---
    TAX_PROVISION: str = "TAX_PROVISION"
    NET_INCOME_CONSOLIDATED: str = "NET_INCOME_CONSOLIDATED"
    NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS: str = "NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS"
    NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS: str = "NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS"
    NET_INCOME_CONTINUING_OPERATIONS: str = "NET_INCOME_CONTINUING_OPERATIONS"
    NET_INCOME_FROM_CONTINUING_AND_DISCONTINUED_OPERATIONS: str = "NET_INCOME_FROM_CONTINUING_AND_DISCONTINUED_OPERATIONS"
    DILUTED_NET_INCOME_AVAILABLE_TO_COMMON_STOCKHOLDERS: str = "DILUTED_NET_INCOME_AVAILABLE_TO_COMMON_STOCKHOLDERS"
    NET_INCOME_CONTINUING_OPERATIONS_NET_MINORITY_INTEREST: str = "NET_INCOME_CONTINUING_OPERATIONS_NET_MINORITY_INTEREST"
    NORMALIZED_NET_INCOME: str = "NORMALIZED_NET_INCOME"
    
    # --- 7. 每股与股本 (Per Share & Shares) ---
    BASIC_EARNINGS_PER_SHARE: str = "BASIC_EARNINGS_PER_SHARE"
    DILUTED_EARNINGS_PER_SHARE: str = "DILUTED_EARNINGS_PER_SHARE"
    WEIGHTED_AVERAGE_BASIC_SHARES_OUTSTANDING: str = "WEIGHTED_AVERAGE_BASIC_SHARES_OUTSTANDING"
    WEIGHTED_AVERAGE_DILUTED_SHARES_OUTSTANDING: str = "WEIGHTED_AVERAGE_DILUTED_SHARES_OUTSTANDING"
    
    # --- 8. 费用与调整 (Expenses & Adjustments) ---
    TOTAL_COSTS_AND_OPERATING_EXPENSES: str = "TOTAL_COSTS_AND_OPERATING_EXPENSES"
    RECONCILED_COST_OF_REVENUE: str = "RECONCILED_COST_OF_REVENUE"
    OPERATING_INCOME_AS_REPORTED: str = "OPERATING_INCOME_AS_REPORTED"
    TOTAL_UNUSUAL_ITEMS_EXCLUDING_GOODWILL: str = "TOTAL_UNUSUAL_ITEMS_EXCLUDING_GOODWILL"
    TAX_RATE_FOR_CALCULATIONS: str = "TAX_RATE_FOR_CALCULATIONS"
    TAX_EFFECT_OF_UNUSUAL_ITEMS: str = "TAX_EFFECT_OF_UNUSUAL_ITEMS"
    
    # --- 9. 港股特有字段 (HK-Specific Fields) ---
    OTHER_INCOME: str = "OTHER_INCOME"
    OTHER_EXPENSE: str = "OTHER_EXPENSE"
    OTHER_GAINS_AND_LOSSES: str = "OTHER_GAINS_AND_LOSSES"
    NET_INCOME_ATTRIBUTABLE_TO_NONCONTROLLING_INTERESTS: str = "NET_INCOME_ATTRIBUTABLE_TO_NONCONTROLLING_INTERESTS"
    COMPREHENSIVE_INCOME: str = "COMPREHENSIVE_INCOME"
    OTHER_COMPREHENSIVE_INCOME: str = "OTHER_COMPREHENSIVE_INCOME"
    OTHER_COMPREHENSIVE_INCOME_OTHER: str = "OTHER_COMPREHENSIVE_INCOME_OTHER"
    COMPREHENSIVE_INCOME_ATTRIBUTABLE_TO_PARENT: str = "COMPREHENSIVE_INCOME_ATTRIBUTABLE_TO_PARENT"
    COMPREHENSIVE_INCOME_ATTRIBUTABLE_TO_NONCONTROLLING_INTERESTS: str = "COMPREHENSIVE_INCOME_ATTRIBUTABLE_TO_NONCONTROLLING_INTERESTS"
    SHARE_OF_PROFIT_ASSOCIATES: str = "SHARE_OF_PROFIT_ASSOCIATES"
    SHARE_OF_PROFIT_JOINT_VENTURES: str = "SHARE_OF_PROFIT_JOINT_VENTURES"
    OTHER_PROFIT_ITEMS: str = "OTHER_PROFIT_ITEMS"
    OTHER_OPERATING_REVENUE: str = "OTHER_OPERATING_REVENUE"
    NON_OPERATING_ITEMS: str = "NON_OPERATING_ITEMS"
    REVALUATION_SURPLUS_ON_INVESTMENT_PROPERTIES: str = "REVALUATION_SURPLUS_ON_INVESTMENT_PROPERTIES"
    DIVIDENDS_DECLARED_SUPPLEMENTARY: str = "DIVIDENDS_DECLARED_SUPPLEMENTARY"
    DIVIDEND_PER_SHARE_SUPPLEMENTARY: str = "DIVIDEND_PER_SHARE_SUPPLEMENTARY"
    
    # ========== 向后兼容别名 (Backward Compatibility Aliases) ==========
    REV: str = TOTAL_REVENUE                    # 营收 -> 总营收
    NI: str = NET_INCOME_CONSOLIDATED           # 净利润 -> 综合净利润
    OI: str = OPERATING_INCOME                  # 营业利润
    GP: str = GROSS_PROFIT                      # 毛利润
    TAX: str = TAX_PROVISION                    # 所得税费用


# ==========================================
# 3. Pydantic 模型 Mixin (Schema Mixin)
# 用于 schema_standard.py 的 StandardFinancialRecord 类继承
# 必须显式声明类型，拒绝动态生成！
# ==========================================
class IncomeStatementRecord(BaseModel):
    """
    利润表字段 Pydantic 模型 Mixin
    供 StandardFinancialRecord 类继承，实现静态类型支持
    
    设计原则：
    - 所有字段显式声明类型
    - 所有字段默认值为 None (Optional)
    - 保留 IDE 类型推断和代码补全
    """
    
    # --- 1. 收入与成本 (Revenue & Cost) ---
    TOTAL_REVENUE: Optional[float] = None              # 总营收
    OPERATING_REVENUE: Optional[float] = None          # 营运收入
    COST_OF_REVENUE: Optional[float] = None            # 销售成本
    GROSS_PROFIT: Optional[float] = None               # 毛利润
    
    # --- 2. 运营开支 (Operating Expenses) ---
    RESEARCH_AND_DEVELOPMENT_EXPENSE: Optional[float] = None  # 研发费用
    SELLING_GENERAL_AND_ADMINISTRATIVE_EXPENSE: Optional[float] = None  # 销售及管理费用 (总计)
    SELLING_MARKETING_EXPENSE: Optional[float] = None  # 销售及分销费用
    GENERAL_ADMIN_EXPENSE: Optional[float] = None      # 行政开支
    TOTAL_OPERATING_EXPENSES: Optional[float] = None   # 营运支出
    RECONCILED_DEPRECIATION: Optional[float] = None    # 折旧与摊销 (D&A) - 对账后
    OTHER_GENERAL_AND_ADMINISTRATIVE_EXPENSES: Optional[float] = None  # 其他行政管理费用
    
    # --- 3. 盈利能力 (Profitability) ---
    OPERATING_INCOME: Optional[float] = None           # 经营溢利
    EBIT: Optional[float] = None                       # 息税前利润
    EBITDA: Optional[float] = None                     # 息税折旧摊销前利润
    NORMALIZED_EBITDA: Optional[float] = None          # 调整后/标准化 EBITDA
    
    # --- 4. 非经常性与利息 (Non-Operating & Interest) ---
    INTEREST_INCOME: Optional[float] = None            # 利息收入
    INTEREST_EXPENSE: Optional[float] = None           # 融资成本
    NET_INTEREST_INCOME: Optional[float] = None        # 净利息收入
    INTEREST_INCOME_NON_OPERATING: Optional[float] = None  # 非经营性利息收入
    INTEREST_EXPENSE_NON_OPERATING: Optional[float] = None  # 非经营性利息支出
    NET_NON_OPERATING_INTEREST_INCOME_EXPENSE: Optional[float] = None  # 净非经营性利息收入/支出
    TOTAL_UNUSUAL_ITEMS: Optional[float] = None        # 非经常性损益/特殊项目
    PRETAX_INCOME: Optional[float] = None              # 除税前溢利
    
    # --- 5. 细分利润项 (Detailed Profit Items) ---
    GAIN_ON_SALE_OF_SECURITY: Optional[float] = None   # 证券处置收益
    WRITE_OFF: Optional[float] = None                  # 资产核销/减值
    SPECIAL_INCOME_CHARGES: Optional[float] = None     # 特殊收支
    OTHER_NON_OPERATING_INCOME_EXPENSES: Optional[float] = None  # 总非经营性收支净额
    OTHER_NON_OPERATING_NET_ADJUSTMENTS: Optional[float] = None  # 其他损益调节项
    
    # --- 6. 净利润 (Net Income) ---
    TAX_PROVISION: Optional[float] = None              # 税项
    NET_INCOME_CONSOLIDATED: Optional[float] = None    # 股东应占溢利 (归母净利润)
    NET_INCOME_INCLUDING_NONCONTROLLING_INTERESTS: Optional[float] = None  # 除税后溢利 (含少数股东净利润)
    NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS: Optional[float] = None  # 归母净利润
    NET_INCOME_CONTINUING_OPERATIONS: Optional[float] = None  # 持续经营业务税后利润
    NET_INCOME_FROM_CONTINUING_AND_DISCONTINUED_OPERATIONS: Optional[float] = None  # 包含终止经营的净利润
    DILUTED_NET_INCOME_AVAILABLE_TO_COMMON_STOCKHOLDERS: Optional[float] = None  # 可供分配给稀释后股东的净利润
    NET_INCOME_CONTINUING_OPERATIONS_NET_MINORITY_INTEREST: Optional[float] = None  # 持续经营归母净利润
    NORMALIZED_NET_INCOME: Optional[float] = None      # 标准化/调整后净利润
    
    # --- 7. 每股指标与股本 (Per Share & Shares) ---
    BASIC_EARNINGS_PER_SHARE: Optional[float] = None   # 每股基本盈利
    DILUTED_EARNINGS_PER_SHARE: Optional[float] = None # 每股摊薄盈利
    WEIGHTED_AVERAGE_BASIC_SHARES_OUTSTANDING: Optional[float] = None  # 基本加权平均股本
    WEIGHTED_AVERAGE_DILUTED_SHARES_OUTSTANDING: Optional[float] = None  # 稀释加权平均股本
    
    # --- 8. 费用与调整 (Expenses & Adjustments) ---
    TOTAL_COSTS_AND_OPERATING_EXPENSES: Optional[float] = None  # 总成本与费用
    RECONCILED_COST_OF_REVENUE: Optional[float] = None  # 对账后营收成本
    OPERATING_INCOME_AS_REPORTED: Optional[float] = None  # 官方财报披露的营业利润
    TOTAL_UNUSUAL_ITEMS_EXCLUDING_GOODWILL: Optional[float] = None  # 剔除商誉后的非经常性损益
    TAX_EFFECT_OF_UNUSUAL_ITEMS: Optional[float] = None  # 非经常性损益的所得税影响
    TAX_RATE_FOR_CALCULATIONS: Optional[float] = None  # 计算用税率
    
    # --- 9. 港股特有字段 (HK-Specific Fields - IFRS/HKFRS) ---
    OTHER_INCOME: Optional[float] = None               # 其他收入 (持续性非主营收入)
    OTHER_EXPENSE: Optional[float] = None              # 其他支出
    OTHER_GAINS_AND_LOSSES: Optional[float] = None     # 其他收益 (偶发利得)
    NET_INCOME_ATTRIBUTABLE_TO_NONCONTROLLING_INTERESTS: Optional[float] = None  # 少数股东损益 (IFRS NCI)
    COMPREHENSIVE_INCOME: Optional[float] = None       # 全面收益总额 (综合收益)
    OTHER_COMPREHENSIVE_INCOME: Optional[float] = None # 其他全面收益 (OCI)
    OTHER_COMPREHENSIVE_INCOME_OTHER: Optional[float] = None  # 其他全面收益其他项目
    COMPREHENSIVE_INCOME_ATTRIBUTABLE_TO_PARENT: Optional[float] = None  # 本公司拥有人应占全面收益总额
    COMPREHENSIVE_INCOME_ATTRIBUTABLE_TO_NONCONTROLLING_INTERESTS: Optional[float] = None  # 非控股权益应占全面收益总额
    SHARE_OF_PROFIT_ASSOCIATES: Optional[float] = None # 应占联营公司溢利
    SHARE_OF_PROFIT_JOINT_VENTURES: Optional[float] = None  # 应占合营公司溢利
    OTHER_PROFIT_ITEMS: Optional[float] = None         # 溢利其他项目
    OTHER_OPERATING_REVENUE: Optional[float] = None    # 其他营业收入
    NON_OPERATING_ITEMS: Optional[float] = None        # 非运算项目
    REVALUATION_SURPLUS_ON_INVESTMENT_PROPERTIES: Optional[float] = None  # 重估盈余 (投资物业公允价值变动)
    DIVIDENDS_DECLARED_SUPPLEMENTARY: Optional[float] = None  # 股息 (附注，不参与利润加总)
    DIVIDEND_PER_SHARE_SUPPLEMENTARY: Optional[float] = None  # 每股股息 (附注)
    
    # ========== 向后兼容别名 (Backward Compatibility Aliases) ==========
    REV: Optional[float] = None                        # 别名: TOTAL_REVENUE
    NI: Optional[float] = None                         # 别名: NET_INCOME_CONSOLIDATED
    OI: Optional[float] = None                         # 别名: OPERATING_INCOME
    GP: Optional[float] = None                         # 别名: GROSS_PROFIT
    TAX: Optional[float] = None                        # 别名: TAX_PROVISION
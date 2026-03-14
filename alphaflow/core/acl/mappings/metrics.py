"""
市场估值指标核心契约 (Market Metrics Domain)
=============================================
单一数据源 (Single Source of Truth)

设计哲学：
- 高内聚低耦合：所有估值指标相关定义集中于此
- 静态 Mixin 模式：保留 IDE 类型推断和静态检查
- 严格一一映射：每个 OBB 字段只映射一个标准字段（大写形式）
- Provider-Specific Transform：百分比归一化在映射层完成
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel

# 导入百分比归一化转换器和特征提取函数
from alphaflow.core.acl.transformers import _tx_normalize_pct, _tx_detect_cny_hkd_mismatch


# ==========================================
# 1. OBB → 标准字段映射表 (严格一一映射)
# ==========================================
METRICS_MAPPING: Dict[str, Dict[str, Any]] = {
    # ==========================================
    # 📊 估值指标 (Valuation Metrics)
    # ==========================================
    "MARKET_CAP": {
        "obb": ["market_cap"],
        "akshare": ["总市值(港元)"]
    },
    "HK_ONLY_MCAP": {
        "obb": [],
        "akshare": ["港股市值(港元)"]
    },
    "TOTAL_REVENUE": {
        "obb": [],
        "akshare": ["营业总收入"]
    },
    "PE_RATIO": {
        "obb": ["pe_ratio"],
        "akshare": ["市盈率"]
    },
    "FORWARD_PE": {
        "obb": ["forward_pe"],
        "akshare": ["预测市盈率"]
    },
    "PEG_RATIO": {
        "obb": ["peg_ratio"],
        "akshare": ["PEG"]
    },
    "PEG_RATIO_TTM": {
        "obb": ["peg_ratio_ttm"],
        "akshare": []
    },
    "PRICE_TO_BOOK": {
        "obb": ["price_to_book"],
        "akshare": ["市净率"]
    },
    "ENTERPRISE_VALUE": {
        "obb": ["enterprise_value"],
        "akshare": ["企业价值"]
    },
    "ENTERPRISE_TO_EBITDA": {
        "obb": ["enterprise_to_ebitda"],
        "akshare": ["EV/EBITDA"]
    },
    "ENTERPRISE_TO_REVENUE": {
        "obb": ["enterprise_to_revenue"],
        "akshare": ["EV/Revenue"]
    },

    # ==========================================
    # 📊 盈利能力 (Profitability) - AkShare 需归一化
    # ==========================================
    "GROSS_MARGIN": {
        "obb": ["gross_margin"],
        "akshare": {
            "aliases": ["毛利率"],
            "transform": _tx_normalize_pct
        }
    },
    "OPERATING_MARGIN": {
        "obb": ["operating_margin"],
        "akshare": {
            "aliases": ["营业利润率"],
            "transform": _tx_normalize_pct
        }
    },
    "EBITDA_MARGIN": {
        "obb": ["ebitda_margin"],
        "akshare": {
            "aliases": ["EBITDA利润率"],
            "transform": _tx_normalize_pct
        }
    },
    "PROFIT_MARGIN": {
        "obb": ["profit_margin"],
        "akshare": {
            "aliases": ["销售净利率(%)"],
            "transform": _tx_normalize_pct
        }
    },
    "RETURN_ON_ASSETS": {
        "obb": ["return_on_assets"],
        "akshare": {
            "aliases": ["总资产回报率(%)"],
            "transform": _tx_normalize_pct
        }
    },
    "RETURN_ON_EQUITY": {
        "obb": ["return_on_equity"],
        "akshare": {
            "aliases": ["股东权益回报率(%)"],
            "transform": _tx_normalize_pct
        }
    },

    # ==========================================
    # 📊 每股指标 (Per-Share Metrics)
    # ==========================================
    "EPS_TTM": {
        "obb": ["eps_ttm"],
        "akshare": ["每股收益TTM"]
    },
    "EPS_BASIC": {
        "obb": [],
        "akshare": ["基本每股收益(元)"]
    },
    "EPS_FORWARD": {
        "obb": ["eps_forward"],
        "akshare": ["预测每股收益"]
    },
    "REVENUE_PER_SHARE": {
        "obb": ["revenue_per_share"],
        "akshare": ["每股营收"]
    },
    "CASH_PER_SHARE": {
        "obb": ["cash_per_share"],
        "akshare": ["每股现金"]
    },
    "BOOK_VALUE": {
        "obb": ["book_value"],
        "akshare": ["每股净资产(元)"]
    },
    "OPERATING_CASH_FLOW_PER_SHARE": {
        "obb": [],
        "akshare": ["每股经营现金流(元)"]
    },
    "DIVIDEND_PER_SHARE": {
        "obb": [],
        "akshare": ["每股股息TTM(港元)"]
    },

    # ==========================================
    # 📊 成长性 (Growth) - AkShare 需归一化
    # ==========================================
    "EARNINGS_GROWTH": {
        "obb": ["earnings_growth"],
        "akshare": {
            "aliases": ["盈利增长率"],
            "transform": _tx_normalize_pct
        }
    },
    "EARNINGS_GROWTH_QUARTERLY": {
        "obb": ["earnings_growth_quarterly"],
        "akshare": ["季度盈利增长"]
    },
    "REVENUE_GROWTH": {
        "obb": ["revenue_growth"],
        "akshare": {
            "aliases": ["营收增长率"],
            "transform": _tx_normalize_pct
        }
    },
    "PRICE_RETURN_1Y": {
        "obb": ["price_return_1y"],
        "akshare": ["一年回报率"]
    },

    # ==========================================
    # 📊 财务健康 (Financial Health)
    # ==========================================
    "QUICK_RATIO": {
        "obb": ["quick_ratio"],
        "akshare": ["速动比率"]
    },
    "CURRENT_RATIO": {
        "obb": ["current_ratio"],
        "akshare": ["流动比率"]
    },
    "DEBT_TO_EQUITY": {
        "obb": {
            "aliases": ["debt_to_equity"],
            "transform": _tx_normalize_pct  # YFinance 返回整数百分比
        },
        "akshare": ["资产负债率"]
    },

    # ==========================================
    # 📊 股息 (Dividend) - 需归一化
    # ==========================================
    "DIVIDEND_YIELD": {
        "obb": {
            "aliases": ["dividend_yield"],
            "transform": _tx_normalize_pct  # YFinance 返回整数百分比
        },
        "akshare": {
            "aliases": ["股息率TTM(%)"],
            "transform": _tx_normalize_pct
        }
    },
    "DIVIDEND_YIELD_5Y_AVG": {
        "obb": ["dividend_yield_5y_avg"],
        "akshare": ["5年平均股息率"]
    },
    "PAYOUT_RATIO": {
        "obb": ["payout_ratio"],
        "akshare": {
            "aliases": ["派息比率(%)"],
            "transform": _tx_normalize_pct
        }
    },

    # ==========================================
    # 📊 风险评分 (Risk Scores)
    # ==========================================
    "OVERALL_RISK": {
        "obb": ["overall_risk"],
        "akshare": []
    },
    "AUDIT_RISK": {
        "obb": ["audit_risk"],
        "akshare": []
    },
    "BOARD_RISK": {
        "obb": ["board_risk"],
        "akshare": []
    },
    "COMPENSATION_RISK": {
        "obb": ["compensation_risk"],
        "akshare": []
    },
    "SHAREHOLDER_RIGHTS_RISK": {
        "obb": ["shareholder_rights_risk"],
        "akshare": []
    },
    "BETA": {
        "obb": ["beta"],
        "akshare": ["Beta系数"]
    },

    # ==========================================
    # 📊 股本结构 (Share Capital) - AkShare 港股补充
    # ==========================================
    "AUTHORIZED_SHARES": {
        "obb": [],
        "akshare": ["法定股本(股)"]
    },
    "SHARES_H": {
        "obb": [],
        "akshare": ["已发行股本-H股(股)"]
    },
    "OUTSTANDING_SHARES": {
        "obb": ["outstanding_shares"],
        "akshare": ["已发行股本(股)"]
    },

    # ==========================================
    # 📊 公司信息 (Company Info) - AkShare 港股补充
    # ==========================================
    "LOT_SIZE": {
        "obb": ["lot_size"],
        "akshare": ["每手股"]
    },

    # ==========================================
    # 📊 利润指标 (Profit) - AkShare 港股补充
    # ==========================================
    "NET_INCOME": {
        "obb": [],
        "akshare": ["净利润"]
    },

    # ==========================================
    # 📊 环比增长 (QOQ Growth) - AkShare 港股补充，需归一化
    # ==========================================
    "REV_GROWTH_QOQ": {
        "obb": [],
        "akshare": {
            "aliases": ["营业总收入滚动环比增长(%)"],
            "transform": _tx_normalize_pct
        }
    },
    "NI_GROWTH_QOQ": {
        "obb": [],
        "akshare": {
            "aliases": ["净利润滚动环比增长(%)"],
            "transform": _tx_normalize_pct
        }
    },

    # ==========================================
    # 🤖 虚拟特征与衍生输出 (Virtual & Derived)
    # ==========================================
    "IS_CNY_HKD_MISMATCH": {
        "obb": [],
        "akshare": {
            "aliases": [],  # 无需别名，纯靠 transform 生成
            "transform": _tx_detect_cny_hkd_mismatch
        }
    },
}


# ==========================================
# 2. 键名常量 Mixin (FinKey Mixin)
# ==========================================
class MetricsKey:
    """
    市场估值指标字段常量 Mixin
    供 FinKey 类继承，实现静态类型支持
    严格一一映射：OBB 原始字段名直接大写
    """
    # 估值指标
    MARKET_CAP: str = "MARKET_CAP"
    HK_ONLY_MCAP: str = "HK_ONLY_MCAP"
    TOTAL_REVENUE: str = "TOTAL_REVENUE"
    PE_RATIO: str = "PE_RATIO"
    FORWARD_PE: str = "FORWARD_PE"
    PEG_RATIO: str = "PEG_RATIO"
    PEG_RATIO_TTM: str = "PEG_RATIO_TTM"
    PRICE_TO_BOOK: str = "PRICE_TO_BOOK"
    ENTERPRISE_VALUE: str = "ENTERPRISE_VALUE"
    ENTERPRISE_TO_EBITDA: str = "ENTERPRISE_TO_EBITDA"
    ENTERPRISE_TO_REVENUE: str = "ENTERPRISE_TO_REVENUE"

    # 盈利能力
    GROSS_MARGIN: str = "GROSS_MARGIN"
    OPERATING_MARGIN: str = "OPERATING_MARGIN"
    EBITDA_MARGIN: str = "EBITDA_MARGIN"
    PROFIT_MARGIN: str = "PROFIT_MARGIN"
    RETURN_ON_ASSETS: str = "RETURN_ON_ASSETS"
    RETURN_ON_EQUITY: str = "RETURN_ON_EQUITY"

    # 每股指标
    EPS_TTM: str = "EPS_TTM"
    EPS_BASIC: str = "EPS_BASIC"
    EPS_FORWARD: str = "EPS_FORWARD"
    REVENUE_PER_SHARE: str = "REVENUE_PER_SHARE"
    CASH_PER_SHARE: str = "CASH_PER_SHARE"
    BOOK_VALUE: str = "BOOK_VALUE"
    OPERATING_CASH_FLOW_PER_SHARE: str = "OPERATING_CASH_FLOW_PER_SHARE"
    DIVIDEND_PER_SHARE: str = "DIVIDEND_PER_SHARE"

    # 成长性
    EARNINGS_GROWTH: str = "EARNINGS_GROWTH"
    EARNINGS_GROWTH_QUARTERLY: str = "EARNINGS_GROWTH_QUARTERLY"
    REVENUE_GROWTH: str = "REVENUE_GROWTH"
    PRICE_RETURN_1Y: str = "PRICE_RETURN_1Y"

    # 财务健康
    QUICK_RATIO: str = "QUICK_RATIO"
    CURRENT_RATIO: str = "CURRENT_RATIO"
    DEBT_TO_EQUITY: str = "DEBT_TO_EQUITY"

    # 股息
    DIVIDEND_YIELD: str = "DIVIDEND_YIELD"
    DIVIDEND_YIELD_5Y_AVG: str = "DIVIDEND_YIELD_5Y_AVG"
    PAYOUT_RATIO: str = "PAYOUT_RATIO"

    # 风险评分
    OVERALL_RISK: str = "OVERALL_RISK"
    AUDIT_RISK: str = "AUDIT_RISK"
    BOARD_RISK: str = "BOARD_RISK"
    COMPENSATION_RISK: str = "COMPENSATION_RISK"
    SHAREHOLDER_RIGHTS_RISK: str = "SHAREHOLDER_RIGHTS_RISK"
    BETA: str = "BETA"

    # 股本结构
    AUTHORIZED_SHARES: str = "AUTHORIZED_SHARES"
    SHARES_H: str = "SHARES_H"
    OUTSTANDING_SHARES: str = "OUTSTANDING_SHARES"

    # 公司信息
    LOT_SIZE: str = "LOT_SIZE"

    # 利润指标
    NET_INCOME: str = "NET_INCOME"

    # 环比增长
    REV_GROWTH_QOQ: str = "REV_GROWTH_QOQ"
    NI_GROWTH_QOQ: str = "NI_GROWTH_QOQ"

    # ========== 派生指标 (Runtime Derived Fields) ==========
    MARKET_CAP_RMB: str = "MARKET_CAP_RMB"  # 汇率对齐后的市值
    FX_RATE: str = "FX_RATE"                # 实时汇率因子

    # ========== 虚拟特征 (Virtual Features) ==========
    IS_CNY_HKD_MISMATCH: str = "IS_CNY_HKD_MISMATCH"  # 港股币种错配特征


# ==========================================
# 3. Pydantic 模型 Mixin (Schema Mixin)
# ==========================================
class MetricsRecord(BaseModel):
    """市场估值指标字段 Pydantic 模型 Mixin"""
    # 估值指标
    MARKET_CAP: Optional[float] = None
    HK_ONLY_MCAP: Optional[float] = None
    TOTAL_REVENUE: Optional[float] = None
    PE_RATIO: Optional[float] = None
    FORWARD_PE: Optional[float] = None
    PEG_RATIO: Optional[float] = None
    PEG_RATIO_TTM: Optional[float] = None
    PRICE_TO_BOOK: Optional[float] = None
    ENTERPRISE_VALUE: Optional[float] = None
    ENTERPRISE_TO_EBITDA: Optional[float] = None
    ENTERPRISE_TO_REVENUE: Optional[float] = None

    # 盈利能力
    GROSS_MARGIN: Optional[float] = None
    OPERATING_MARGIN: Optional[float] = None
    EBITDA_MARGIN: Optional[float] = None
    PROFIT_MARGIN: Optional[float] = None
    RETURN_ON_ASSETS: Optional[float] = None
    RETURN_ON_EQUITY: Optional[float] = None

    # 每股指标
    EPS_TTM: Optional[float] = None
    EPS_BASIC: Optional[float] = None
    EPS_FORWARD: Optional[float] = None
    REVENUE_PER_SHARE: Optional[float] = None
    CASH_PER_SHARE: Optional[float] = None
    BOOK_VALUE: Optional[float] = None
    OPERATING_CASH_FLOW_PER_SHARE: Optional[float] = None
    DIVIDEND_PER_SHARE: Optional[float] = None

    # 成长性
    EARNINGS_GROWTH: Optional[float] = None
    EARNINGS_GROWTH_QUARTERLY: Optional[float] = None
    REVENUE_GROWTH: Optional[float] = None
    PRICE_RETURN_1Y: Optional[float] = None

    # 财务健康
    QUICK_RATIO: Optional[float] = None
    CURRENT_RATIO: Optional[float] = None
    DEBT_TO_EQUITY: Optional[float] = None

    # 股息
    DIVIDEND_YIELD: Optional[float] = None
    DIVIDEND_YIELD_5Y_AVG: Optional[float] = None
    PAYOUT_RATIO: Optional[float] = None

    # 风险评分
    OVERALL_RISK: Optional[float] = None
    AUDIT_RISK: Optional[float] = None
    BOARD_RISK: Optional[float] = None
    COMPENSATION_RISK: Optional[float] = None
    SHAREHOLDER_RIGHTS_RISK: Optional[float] = None
    BETA: Optional[float] = None

    # 股本结构
    AUTHORIZED_SHARES: Optional[float] = None
    SHARES_H: Optional[float] = None
    OUTSTANDING_SHARES: Optional[float] = None

    # 公司信息
    LOT_SIZE: Optional[float] = None

    # 利润指标
    NET_INCOME: Optional[float] = None

    # 环比增长
    REV_GROWTH_QOQ: Optional[float] = None
    NI_GROWTH_QOQ: Optional[float] = None

    # ========== 派生指标 (Runtime Derived Fields) ==========
    MARKET_CAP_RMB: Optional[float] = None
    FX_RATE: Optional[float] = None

    # ========== 虚拟特征 (Virtual Features) ==========
    IS_CNY_HKD_MISMATCH: Optional[bool] = None  # 港股币种错配特征

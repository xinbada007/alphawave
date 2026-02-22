"""
ResearchPack Facade - 数据防腐层
==================================
用于屏蔽 ResearchPack 内部复杂的字典嵌套结构。

提供统一的访问接口：
- 自动处理 CN/HK (累积制 _ytd) 和 US (离散制 _discrete) 的后缀差异
- 预计算并缓存数据路径，避免反复的 .get().get() 操作
- 封装 TTM 计算等复杂逻辑

使用方式：
    from alphaflow.core.facade import ResearchPackFacade, to_facade
    
    facade = to_facade(pack)
    ttm_ni = facade.get_ttm_value(lambda x: get_field_value(x, "NI"))
"""

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from alphaflow.core.data_utils import (
    MarketType,
    find_closest_strictly,
    get_field_value,
    get_market_type,
)
from alphaflow.core.financial_math import calc_ttm_stitch
from alphaflow.core.schema import ResearchPack


# ==========================================
# 1. 报表类型枚举
# ==========================================

class StatementType(Enum):
    """财务报表类型"""
    INCOME = "income"      # 利润表
    BALANCE = "balance"    # 资产负债表
    CASH = "cash"          # 现金流量表
    ANALYSIS = "analysis"  # 分析指标 (AkShare 特有)


# ==========================================
# 2. ResearchPackFacade 类
# ==========================================

class ResearchPackFacade:
    """
    ResearchPack 防腐层视图
    
    设计目标：
    1. 屏蔽 ResearchPack 内部复杂的字典嵌套结构
    2. 预计算并缓存数据路径 (annual_series, quarterly_series)
    3. 提供统一的数据访问接口
    """
    
    # 支持的报表类型映射到 extra 中的 key 前缀
    STMT_KEY_MAP: Dict[StatementType, str] = {
        StatementType.INCOME: "income",
        StatementType.BALANCE: "balance",
        StatementType.CASH: "cash",
    }
    
    def __init__(self, pack: ResearchPack):
        """
        初始化 Facade，预先计算并缓存路径信息
        
        Args:
            pack: ResearchPack 实例
        """
        self.pack = pack
        self.symbol = pack.symbol
        
        # 1. 判断市场类型
        self.market_type: MarketType = get_market_type(self.symbol)
        
        # 2. 预先计算 is_cumulative
        self.is_cumulative: bool = self.market_type in (MarketType.HK, MarketType.CN)
        
        # 3. 确定后缀 (CN/HK 用 _ytd, US 用 _discrete)
        self._q_suffix: str = "_ytd" if self.is_cumulative else "_discrete"
        
        # 4. 缓存 annual_series 路径
        self._annual_series: Dict[str, List[Dict]] = pack.extra.get("annual_series", {})
        
        # 5. 缓存 quarterly_series 路径
        self._quarterly_series: Dict[str, List[Dict]] = pack.extra.get(
            f"quarterly_series{self._q_suffix}", {}
        )
        
        # 6. 缓存 akshare_analysis 路径
        self._analysis_series: Dict[str, List[Dict]] = pack.extra.get("akshare_analysis", {})
    
    # ======================================
    # 通用数据获取接口
    # ======================================
    
    def get_scoped_series(
        self, 
        period: str, 
        stmt_type: StatementType = StatementType.INCOME
    ) -> List[Dict]:
        """
        获取指定周期和类型的财务数据序列
        
        Args:
            period: "quarterly" | "annual"
            stmt_type: 报表类型 (income/balance/cash/analysis)
        
        Returns:
            数据列表，如果不存在则返回空列表
        """
        period = period.lower()
        
        # 处理 ANALYSIS 类型 (AkShare 特有)
        if stmt_type == StatementType.ANALYSIS:
            if period == "annual":
                return self._analysis_series.get("annual", [])
            elif period == "quarterly":
                # 根据累积/离散选择不同的 key
                key = "quarterly_cumulative_ytd" if self.is_cumulative else "quarterly_discrete"
                return self._analysis_series.get(key, [])
            return []
        
        # 处理三表 (income/balance/cash)
        stmt_key = self.STMT_KEY_MAP[stmt_type]
        
        if period == "annual":
            # annual_series: {"a_income": [...], "a_balance": [...], "a_cash": [...]}
            key = f"a_{stmt_key}"
            return self._annual_series.get(key, [])
        
        elif period == "quarterly":
            # quarterly_series: {"q_income_ytd": [...], "q_balance_discrete": [...], ...}
            key = f"q_{stmt_key}{self._q_suffix}"
            return self._quarterly_series.get(key, [])
        
        return []
    
    def get_latest_report(
        self, 
        period: str, 
        stmt_type: StatementType = StatementType.INCOME
    ) -> Optional[Dict]:
        """
        获取最新一期的财务报告
        
        Args:
            period: "quarterly" | "annual"
            stmt_type: 报表类型
        
        Returns:
            最新一期的财报字典，如果不存在则返回 None
        """
        series = self.get_scoped_series(period, stmt_type)
        return series[0] if series else None
    
    def get_snapshot_value(
        self,
        field: str,
        stmt_type: StatementType = StatementType.INCOME,
        period: str = "latest"
    ) -> Optional[float]:
        """
        从最新财报中提取某个字段的值
        支持字段级 Fallback：如果 period='latest'，优先查季报，查不到再去查年报。
        
        Args:
            field: 字段名 (如 "NI", "REV", "PE")
            stmt_type: 报表类型
            period: "latest" (默认) | "quarterly" | "annual"
        
        Returns:
            字段值 (float)，未找到返回 None
        """
        if period == "latest":
            # 1. 尝试从季报获取
            q_report = self.get_latest_report("quarterly", stmt_type)
            val = get_field_value(q_report, field) if q_report else None
            
            # 2. 如果季报没值 (None)，回退到年报
            if val is None:
                a_report = self.get_latest_report("annual", stmt_type)
                val = get_field_value(a_report, field) if a_report else None
            
            return val
            
        else:
            # 指定了特定周期，直接查，不 fallback
            report = self.get_latest_report(period, stmt_type)
            return get_field_value(report, field) if report else None
    
    # ======================================
    # TTM 专用接口
    # ======================================
    
    def get_ttm_value(
        self,
        field_func: Callable[[Dict], Optional[float]],
        stmt_type: StatementType = StatementType.INCOME
    ) -> Optional[float]:
        """
        计算滚动12个月 (TTM) 值
        
        这是核心解耦点：内部自动组装 q_series 和 a_series，
        调用 financial_math.calc_ttm_stitch 完成计算。
        
        Args:
            field_func: 字段提取函数，接收 Dict 返回 Optional[float]
            stmt_type: 报表类型 (默认 income)
        
        Returns:
            TTM 值，如果无法计算则返回 None
        """
        # 1. 获取季度和年度数据
        stmt_key = self.STMT_KEY_MAP[stmt_type]
        
        q_key = f"q_{stmt_key}{self._q_suffix}"
        a_key = f"a_{stmt_key}"
        
        q_series = self._quarterly_series.get(q_key, [])
        a_series = self._annual_series.get(a_key, [])
        
        # 2. 调用 calc_ttm_stitch
        return calc_ttm_stitch(
            q_series=q_series,
            a_series=a_series,
            field_func=field_func,
            is_cumulative=self.is_cumulative
        )
    
    # ======================================
    # 便捷属性
    # ======================================
    
    # ======================================
    # 完全封装属性 (彻底阻断裸调 pack 的路径)
    # ======================================
    
    @property
    def currency_context(self) -> Dict[str, Any]:
        """安全获取币种审计上下文"""
        return self.fundamentals.get("currency_context", {})
    
    # ======================================
    # 时间对齐与基准获取接口 (Time-Aligned API)
    # ======================================
    
    def get_baseline_context(self) -> Tuple[str, Optional[datetime], Optional[Dict]]:
        """
        获取当前财报的基准上下文 (通常由最新利润表决定)
        
        Returns:
            (p_type, anchor_date, latest_is_report)
            - p_type: "quarterly" 或 "annual"
            - anchor_date: 统一对齐所用的时间戳
            - latest_is_report: 最新的利润表原始字典
        """
        latest_is = self.get_latest_report("quarterly", StatementType.INCOME)
        p_type = "quarterly"
        if not latest_is:
            latest_is = self.get_latest_report("annual", StatementType.INCOME)
            p_type = "annual"
            
        if not latest_is:
            return "annual", None, None
            
        date_str = latest_is.get("period_ending")
        anchor_date = pd.to_datetime(date_str) if date_str else None
        
        return p_type, anchor_date, latest_is

    def get_aligned_report(
        self, 
        period: str, 
        stmt_type: StatementType, 
        anchor_date: Optional[datetime], 
        window: int = 15
    ) -> Optional[Dict]:
        """
        根据锚点日期，严格获取在时间上对齐的特定报表
        （完美屏蔽 find_closest_strictly 逻辑）
        """
        series = self.get_scoped_series(period, stmt_type)
        if not series or not anchor_date:
            return None
            
        return find_closest_strictly(series, anchor_date, window=window)

    def get_aligned_value(
        self, 
        field: str, 
        stmt_type: StatementType, 
        period: str, 
        anchor_date: Optional[datetime],
        window: int = 15
    ) -> Optional[float]:
        """直接获取在时间上对齐的某个特定字段的值"""
        report = self.get_aligned_report(period, stmt_type, anchor_date, window)
        return get_field_value(report, field) if report else None
    
    # ======================================
    # 便捷属性
    # ======================================
    
    @property
    def fundamentals(self) -> Dict[str, Any]:
        """直接访问 fundamentals 字典"""
        return self.pack.fundamentals or {}
    
    @property
    def market_metrics(self) -> Dict[str, Any]:
        """直接访问 market_metrics 字典"""
        return self.pack.market_metrics or {}
    
    @property
    def extra(self) -> Dict[str, Any]:
        """直接访问 extra 字典"""
        return self.pack.extra or {}


# ==========================================
# 3. 工厂函数
# ==========================================


def to_facade(pack: ResearchPack) -> ResearchPackFacade:
    """
    将 ResearchPack 转换为 Facade 视图的工厂函数
    
    Args:
        pack: ResearchPack 实例
    
    Returns:
        ResearchPackFacade 实例
    
    使用方式:
        facade = to_facade(pack)
        ttm_ni = facade.get_ttm_value(lambda x: get_field_value(x, "NI"))
    """
    return ResearchPackFacade(pack)

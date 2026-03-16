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
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from alphaflow.core.keys import Key

import pandas as pd

from alphaflow.core.utils.data_utils import (
    MarketType,
    MetaKey,
    ReportPeriod,
    find_closest_strictly,
    get_field_value,
    get_market_type,
)
from alphaflow.core.utils.financial_math import calc_ttm_stitch
from alphaflow.core.schema.models import ResearchPack


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
        
        # 🚀 声明式路由表 (Dispatcher Map)：彻底消灭 if-elif 硬编码
        # 键: 领域名 (小写) -> 值: 对应的取值解析器函数 (接收 period 和 standard_key)
        self._domain_routers = {
            "metrics": lambda p, k: self.get_metric_value(k),
            "estimates": lambda p, k: self.get_estimate_value(k),
            "profile": lambda p, k: self.get_profile_value(k),
            "share_stats": lambda p, k: self.get_share_stats_value(k),
            # 财务三大表路由：统一交由内部报表提取器处理
            "income": lambda p, k: self._resolve_statement(p, StatementType.INCOME, k),
            "balance": lambda p, k: self._resolve_statement(p, StatementType.BALANCE, k),
            "cash": lambda p, k: self._resolve_statement(p, StatementType.CASH, k),
            "analysis": lambda p, k: self._resolve_statement(p, StatementType.ANALYSIS, k),
        }
    
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
            if period == ReportPeriod.ANNUAL.value:
                return self._analysis_series.get(ReportPeriod.ANNUAL.value, [])
            elif period == ReportPeriod.QUARTERLY.value:
                # 根据累积/离散选择不同的 key
                key = "quarterly_cumulative_ytd" if self.is_cumulative else "quarterly_discrete"
                return self._analysis_series.get(key, [])
            return []
        
        # 处理三表 (income/balance/cash)
        stmt_key = self.STMT_KEY_MAP[stmt_type]
        
        if period == ReportPeriod.ANNUAL.value:
            # annual_series: {"a_income": [...], "a_balance": [...], "a_cash": [...]}
            key = f"a_{stmt_key}"
            return self._annual_series.get(key, [])
        
        elif period == ReportPeriod.QUARTERLY.value:
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
        if period == ReportPeriod.LATEST.value:
            # 1. 尝试从季报获取
            q_report = self.get_latest_report(ReportPeriod.QUARTERLY.value, stmt_type)
            val = get_field_value(q_report, field) if q_report else None
            
            # 2. 如果季报没值 (None)，回退到年报
            if val is None:
                a_report = self.get_latest_report(ReportPeriod.ANNUAL.value, stmt_type)
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
        # 🚀 柔性签名：允许传入 Key 字符串，也向下兼容传入计算函数 (如 FCF)
        field_key_or_func: Union[str, Callable[[Dict], Optional[float]]],
        stmt_type: StatementType = StatementType.INCOME
    ) -> Optional[float]:
        """
        计算滚动12个月 (TTM) 值
        """
        stmt_key = self.STMT_KEY_MAP[stmt_type]
        q_key = f"q_{stmt_key}{self._q_suffix}"
        a_key = f"a_{stmt_key}"
        
        q_series = self._quarterly_series.get(q_key, [])
        a_series = self._annual_series.get(a_key,[])
        
        # 智能分发提取器
        if isinstance(field_key_or_func, str):
            field_func = lambda x: get_field_value(x, field_key_or_func)
        else:
            field_func = field_key_or_func
            
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
    
    # alphaflow/core/facade.py
    def get_baseline_context(self) -> Tuple[str, Optional[datetime], Optional[Dict]]:
        """
        获取基准上下文 (严格按照日期最新原则)
        """
        q_is = self.get_latest_report(ReportPeriod.QUARTERLY.value, StatementType.INCOME)
        a_is = self.get_latest_report(ReportPeriod.ANNUAL.value, StatementType.INCOME)
        
        q_date = pd.to_datetime(q_is.get(MetaKey.PERIOD_ENDING)) if q_is and q_is.get(MetaKey.PERIOD_ENDING) else pd.Timestamp.min
        a_date = pd.to_datetime(a_is.get(MetaKey.PERIOD_ENDING)) if a_is and a_is.get(MetaKey.PERIOD_ENDING) else pd.Timestamp.min

        if q_date is pd.Timestamp.min and a_date is pd.Timestamp.min:
            return ReportPeriod.ANNUAL.value, None, None

        # 如果同一天 (例如美股 Q4 季报和年报同时出在 12-31)，优先使用年报，因为年报经过审计，数据更准
        if a_date >= q_date:
            return ReportPeriod.ANNUAL.value, a_date, a_is
        else:
            return ReportPeriod.QUARTERLY.value, q_date, q_is

    def get_aligned_report(
        self, 
        period: str, 
        stmt_type: StatementType, 
        anchor_date: Optional[datetime], 
        window: int = 20
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
        window: int = 20
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

    # ======================================
    # 领域感知与语境访问接口 (Semantic Access API)
    # ======================================
    def get_metric_value(self, key: str) -> Optional[Any]:
        """显式获取：市场快照/计算指标 (对应 pack.market_metrics)"""
        return get_field_value(self.market_metrics, key)
        
    def get_profile_value(self, key: str) -> Optional[Any]:
        """显式获取：公司档案/元数据 (对应 pack.fundamentals['profile'])"""
        profile_dict = self.fundamentals.get("profile", {})
        return get_field_value(profile_dict, key)
        
    def get_estimate_value(self, key: str) -> Optional[Any]:
        """显式获取：分析师共识预测 (对应 pack.fundamentals['estimates'])"""
        estimates_dict = self.fundamentals.get("estimates", {})
        return get_field_value(estimates_dict, key)
        
    def get_share_stats_value(self, key: str) -> Optional[Any]:
        """显式获取：股本结构与做空数据 (对应 pack.fundamentals['share_stats'])"""
        share_stats_dict = self.fundamentals.get("share_stats", {})
        return get_field_value(share_stats_dict, key)

    # ======================================
    # V3 架构：统一依赖解析器 (Dependency Resolver)
    # ======================================
    
    def _resolve_statement(self, period: str, stmt_type: StatementType, standard_key: str) -> Optional[float]:
        """内部辅助方法：处理结构化财报的时态路由"""
        if period == "TTM":
            return self.get_ttm_value(standard_key, stmt_type=stmt_type)
        elif period == "LATEST":
            return self.get_snapshot_value(standard_key, stmt_type=stmt_type, period="latest")
        elif period == "ANNUAL":
            return self.get_snapshot_value(standard_key, stmt_type=stmt_type, period="annual")
        elif period == "QUARTERLY":
            return self.get_snapshot_value(standard_key, stmt_type=stmt_type, period="quarterly")
        return None

    def resolve_dependency(self, period_type: str, domain: str, standard_key: str) -> Optional[float]:
        """
        全域寻址网关 (Universal Data Address Resolver)
        完全符合开闭原则 (OCP)，通过路由表动态下发，杜绝硬编码。
        
        Args:
            period_type: 周期类型，支持 "TTM", "LATEST", "ANNUAL", "QUARTERLY"
            domain: 报表域，支持 "income", "balance", "cash", "metrics", "estimates", "profile", "share_stats"
            standard_key: 标准字段键，如 "NET_INCOME", "TOTAL_EQUITY"
        
        Returns:
            字段值 (float)，如果无法解析则返回 None
        """
        period = period_type.upper()
        d_lower = domain.lower()
        
        # 核心：字典路由查表，O(1) 复杂度，无缝适应未来新增领域
        router_func = self._domain_routers.get(d_lower)
        if router_func:
            return router_func(period, standard_key)
            
        # 未知领域兜底防爆
        print(f"  [Facade] ⚠️ Unknown domain requested: {domain}")
        return None


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

"""
技术与衍生特征处理器 (Technical & Derived Processor)
=================================================
"""

import pandas as pd
from typing import Any, Dict, List, Optional, Protocol
from datetime import datetime

# 严格遵循你提供的基类
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.core.data_utils import (
    get_field_value,
)
from alphaflow.core.facade import ResearchPackFacade, StatementType
from alphaflow.core.financial_math import (
    get_annual_multiplier,
    get_fcf_raw,
    calculate_growth_yoy,
)


# ==========================================
# 1. Analyzer 插件接口定义 (保持不变)
# ==========================================

class FeatureAnalyzer(Protocol):
    def analyze(self, pack: ResearchPack) -> Dict[str, Any]:
        ...

# ==========================================
# 2. 财务比率计算引擎 (LegacyFinancialRatioAnalyzer)
# ==========================================
class LegacyFinancialRatioAnalyzer:
    """
    基础财务比率分析器
    复用 facade 和 financial_math 模块进行语义化数据访问和计算。
    """

    def analyze(self, pack: ResearchPack) -> Dict[str, Any]:
        """执行核心指标计算 (终极解耦、无硬编码版)"""
        if not pack.fundamentals or not pack.extra:
            return {}

        facade = ResearchPackFacade(pack)
        
        # 1. 获取基准时空锚点 (一句话搞定 p_type, anchor_date, latest_is)
        p_type, anchor_date, latest_is = facade.get_baseline_context()
        if not latest_is or not anchor_date:
            return {}

        # 2. 获取严格时间对齐的报表 (一句话搞定 find_closest_strictly)
        cur_bs = facade.get_aligned_report(p_type, StatementType.BALANCE, anchor_date)
        cur_cf = facade.get_aligned_report(p_type, StatementType.CASH, anchor_date)
        
        latest_ana = facade.get_aligned_report(p_type, StatementType.ANALYSIS, anchor_date)
        latest_annual_ana = facade.get_aligned_report("annual", StatementType.ANALYSIS, anchor_date)

        # 3. 上下文准备 (一句话阻断对 pack 的裸调)
        metrics = facade.market_metrics
        m_cap = metrics.get("market_cap_rmb", get_field_value(metrics, "MCAP"))
        currency_ctx = facade.currency_context

        # 4. TTM 计算
        ttm_ni = facade.get_ttm_value(lambda x: get_field_value(x, "NI"), StatementType.INCOME)
        ttm_fcf = facade.get_ttm_value(get_fcf_raw, StatementType.CASH)
        
        # 5. 提取核心标量 (依赖对齐后的报表)
        rev = get_field_value(latest_is, "REV")
        ni = get_field_value(latest_is, "NI")
        oi = get_field_value(latest_is, "OI")
        eq = get_field_value(cur_bs, "EQUITY")
        liab = get_field_value(cur_bs, "LIAB")
        ocf = get_field_value(cur_cf, "OCF")
        fcf_cur = get_fcf_raw(cur_cf)
        
        ann_multiplier = get_annual_multiplier(latest_is, latest_ana or {}, p_type, facade.is_cumulative)

        # ==========================================
        # 核心指标计算逻辑
        # ==========================================
        indicators = {}

        # --- A. 增长指标 ---
        if p_type == "quarterly":
            y_r_q = latest_ana.get("OPERATE_INCOME_YOY") if latest_ana else None
            # 逻辑还原：calculate_growth_yoy 必须传入具体的 series 列表
            indicators["rev_growth_yoy_quarter"] = (
                round(float(y_r_q) / 100, 4) if y_r_q is not None 
                else calculate_growth_yoy(
                    facade.get_scoped_series("quarterly", StatementType.INCOME),
                    "REV", True, get_field_value
                )
            )
            
            y_ni_q = latest_ana.get("HOLDER_PROFIT_YOY") if latest_ana else None
            indicators["ni_growth_yoy_quarter"] = (
                round(float(y_ni_q) / 100, 4) if y_ni_q is not None
                else calculate_growth_yoy(
                    facade.get_scoped_series("quarterly", StatementType.INCOME),
                    "NI", True, get_field_value
                )
            )

        # 年度增长
        y_r_a = latest_annual_ana.get("OPERATE_INCOME_YOY") if latest_annual_ana else None
        indicators["rev_growth_yoy_annual"] = (
            round(float(y_r_a) / 100, 4) if y_r_a is not None
            else calculate_growth_yoy(
                facade.get_scoped_series("annual", StatementType.INCOME),
                "REV", False, get_field_value
            )
        )
        
        y_ni_a = latest_annual_ana.get("HOLDER_PROFIT_YOY") if latest_annual_ana else None
        indicators["ni_growth_yoy_annual"] = (
            round(float(y_ni_a) / 100, 4) if y_ni_a is not None
            else calculate_growth_yoy(
                facade.get_scoped_series("annual", StatementType.INCOME),
                "NI", False, get_field_value
            )
        )

        # --- B. 效率与回报 (年化) ---
        # 🚨 关键修复：使用 p_type 锁定当前报表周期，严禁混用 quarterly/annual
        # (核心标量已在第5步提取完毕)

        # ROE 逻辑 (完全一致)
        roe_off = (latest_ana.get("ROE_YEARLY") or latest_ana.get("ROE_AVG")) if latest_ana else None
        if roe_off is not None:
            val = float(roe_off) / 100
            if latest_ana and not latest_ana.get("ROE_YEARLY") and facade.is_cumulative and ann_multiplier is not None:
                val = val * ann_multiplier
            indicators["roe_period_actual"] = round(val, 4)
        elif ni and eq and eq > 0 and ann_multiplier is not None:
            indicators["roe_period_actual"] = round((ni * ann_multiplier) / eq, 4)
        else:
            indicators["roe_period_actual"] = None

        # Margin 逻辑 (完全一致)
        npm_off = latest_ana.get("NET_PROFIT_RATIO") if latest_ana else None
        indicators["net_margin_period_actual"] = (
            round(float(npm_off) / 100, 4) if npm_off is not None 
            else (round(ni / rev, 4) if ni and rev and rev > 0 else None)
        )
        indicators["op_margin_period_actual"] = round(oi / rev, 4) if oi and rev and rev > 0 else None
        if fcf_cur is not None and rev and rev > 0:
            indicators["fcf_margin_period_actual"] = round(fcf_cur / rev, 4)

        # --- C. 杠杆与流动性 ---
        if eq and eq > 0 and liab is not None:
            indicators["total_liabilities_to_equity"] = round(liab / eq, 4)
        
        cr_off = latest_ana.get("CURRENT_RATIO") if latest_ana else None
        if cr_off is not None:
            indicators["current_ratio_liquidity"] = round(float(cr_off), 4)
        else:
            ca = get_field_value(cur_bs, "C_ASSETS") if cur_bs else None
            cl = get_field_value(cur_bs, "C_LIAB") if cur_bs else None
            indicators["current_ratio_liquidity"] = round(ca / cl, 4) if ca and cl and cl > 0 else None
        
        if ni and abs(ni) > 0 and ocf is not None:
            indicators["earnings_quality_period"] = round(ocf / ni, 4)

        # --- D. 估值指标 ---
        if m_cap and m_cap > 0 and ttm_fcf is not None:
            method = currency_ctx.get("audit_method", "")
            if "PE_Collision" in method:
                api_pe = metrics.get('trailingPE') or metrics.get('pe_ratio')
                if api_pe and api_pe > 0 and ttm_ni and ttm_ni > 0:
                    indicators["fcf_yield_realtime_ttm"] = round((ttm_fcf / ttm_ni) / api_pe, 4)
            else:
                indicators["fcf_yield_realtime_ttm"] = round((ttm_fcf / m_cap), 4)

        # --- E. 元数据注入 ---
        indicators["report_period"] = p_type
        indicators["fiscal_date"] = anchor_date.strftime("%Y-%m-%d") if anchor_date else "N/A"

        return indicators


# ==========================================
# 3. 核心 Processor (保持不变)
# ==========================================

class TechnicalProcessor(BaseProcessor):
    """
    量化与衍生特征管道处理器
    按需组装各类 Analyzer，加工出最终的衍生特征。
    """
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        # 挂载分析器插件池
        self.analyzers: List[FeatureAnalyzer] = [
            LegacyFinancialRatioAnalyzer(),
        ]

    async def process(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        """
        核心执行逻辑，覆盖 BaseProcessor 的抽象方法。
        
        Args:
            context: 分析上下文 (包含 symbols, days 等)
            input_data: 管道传输的对象 (通常是上一步的 ComponentOutput)
            **kwargs: 其他透传参数
        """
        # 1. 标准化解包 (参考 FundamentalCollector 实现)
        pack = (
            input_data.payload
            if isinstance(input_data, ComponentOutput)
            else input_data
        )
        
        # 2. 兜底保护
        if pack is None:
            pack = ResearchPack(symbol=context.symbols[0])
            
        print(f"  [TechnicalProcessor] Computing derived indicators for {pack.symbol}...")

        # 3. 为 A/B 测试创建一个新的承载容器
        if not hasattr(pack, "fundamentals") or pack.fundamentals is None:
            pack.fundamentals = {}
            
        if "indicators_v2" not in pack.fundamentals:
            pack.fundamentals["indicators_v2"] = {}

        # 4. 遍历所有挂载的分析器进行运算
        for analyzer in self.analyzers:
            try:
                result = analyzer.analyze(pack)
                if result:
                    pack.fundamentals["indicators_v2"].update(result)
            except Exception as e:
                print(f"  [TechnicalProcessor] {analyzer.__class__.__name__} Failed for {pack.symbol}: {e}")

        # 5. 封装并返回标准输出
        return ComponentOutput(success=True, payload=pack)

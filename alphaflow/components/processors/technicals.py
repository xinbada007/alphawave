"""
技术与衍生特征处理器 (Technical & Derived Processor)
=================================================
"""

import asyncio
import pandas as pd
from typing import Any, Dict, List, Optional, Protocol
from datetime import datetime

# 严格遵循你提供的基类
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack

# 技术面分析组件
from alphaflow.components.processors.techniques import MultiTimeframeMarketAnalyzer

# 基本面蒸馏组件
from alphaflow.components.processors.fundamentals import FundamentalDistillationAnalyzer

from alphaflow.core.data_utils import (
    FinKey,
    MetaKey,
    PackSlot,
    ReportPeriod,
    get_field_value,
)
from alphaflow.core.facade import ResearchPackFacade, StatementType
from alphaflow.core.financial_math import (
    get_annual_multiplier,
    get_fcf_raw,
    calculate_growth_yoy,
)


# ==========================================
# 1. Analyzer 插件接口定义 (自描述模式)
# ==========================================

class FeatureAnalyzer(Protocol):
    """分析器协议 - 每个 Analyzer 自描述数据存储位置"""
    
    @property
    def target_slot(self) -> str:
        """返回目标槽位路径，如 'technical_and_sentiment' 或 'indicators'"""
        ...
    
    def analyze(self, pack: ResearchPack) -> Dict[str, Any]:
        ...


# ==========================================
# 2. 财务比率计算引擎 (CoreFinancialRatioAnalyzer)
# ==========================================
class CoreFinancialRatioAnalyzer:
    """
    核心财务比率分析器 (Standardized Financial Ratio Analyzer)
    
    架构原则:
    1. Orchestrator Pattern: analyze() 负责数据对齐与调度，不含计算逻辑。
    2. Dimension Separation: 增长/效率/偿债/估值 拆分为独立方法。
    3. Explicit Naming: 变量名严格对应计算口径 (TTM vs Period Actual)。
    """

    @property
    def target_slot(self) -> str:
        """自描述：财务比率数据存到 indicators"""
        return "indicators"

    def analyze(self, pack: ResearchPack) -> Dict[str, Any]:
        """调度器：准备数据并分发计算任务"""
        if not pack.fundamentals or not pack.extra:
            return {}

        facade = ResearchPackFacade(pack)
        
        # 1. 基础时空锚点
        p_type, anchor_date, latest_is = facade.get_baseline_context()
        if not latest_is or not anchor_date:
            return {}

        # 2. 报表对齐 (Window=20 for Financials, Window=30 for Analysis/Metrics)
        cur_bs = facade.get_aligned_report(p_type, StatementType.BALANCE, anchor_date, window=20)
        cur_cf = facade.get_aligned_report(p_type, StatementType.CASH, anchor_date, window=20)
        
        latest_ana = facade.get_aligned_report(p_type, StatementType.ANALYSIS, anchor_date, window=30)
        latest_annual_ana = facade.get_aligned_report(ReportPeriod.ANNUAL.value, StatementType.ANALYSIS, anchor_date, window=30)

        # 3. 准备计算所需的中间变量 (Context)
        # 年化乘数
        ann_multiplier = get_annual_multiplier(latest_is, latest_ana or {}, p_type, facade.is_cumulative)
        
        # TTM 核心数据 (用于效率和估值)
        ttm_ni = facade.get_ttm_value(lambda x: get_field_value(x, FinKey.NI), StatementType.INCOME)
        ttm_fcf = facade.get_ttm_value(get_fcf_raw, StatementType.CASH)

        # 4. 执行分模块计算
        indicators = {}
        
        # A. 增长维度 (Growth)
        indicators.update(self._calc_growth_metrics(
            facade, latest_ana, latest_annual_ana, p_type, anchor_date
        ))

        # B. 效率与回报维度 (Efficiency)
        indicators.update(self._calc_efficiency_metrics(
            latest_is, cur_bs, cur_cf, latest_ana, 
            ttm_ni, ann_multiplier, facade.is_cumulative
        ))

        # C. 偿债与流动性维度 (Solvency)
        indicators.update(self._calc_solvency_metrics(
            latest_is, cur_bs, cur_cf, latest_ana
        ))

        # D. 估值维度 (Valuation)
        indicators.update(self._calc_valuation_metrics(
            facade, ttm_fcf, ttm_ni
        ))

        # E. 元数据注入
        indicators["report_period"] = p_type
        indicators["fiscal_date"] = anchor_date.strftime("%Y-%m-%d")

        # F. 过滤 None 值，避免 LLM JSON Payload 污染
        return {k: v for k, v in indicators.items() if v is not None}

    # ==========================================
    # 私有计算方法 (Private Calculation Methods)
    # ==========================================

    def _calc_growth_metrics(
        self, 
        facade: ResearchPackFacade, 
        latest_ana: Optional[Dict], 
        latest_annual_ana: Optional[Dict], 
        p_type: str,
        anchor_date: Optional[datetime]
    ) -> Dict[str, Any]:
        """计算增长率 (Growth) - 支持动态时态对齐与 Q4 动量捕获"""
        res = {}
        
        # ==================================================
        # 1. 季度/中期增长 (Quarterly YoY)
        # ==================================================
        # 检查系统最新的季报是否与当前基准日期(年报)处于同一时期
        latest_q_is = facade.get_latest_report(ReportPeriod.QUARTERLY.value, StatementType.INCOME)
        q_date_raw = latest_q_is.get(MetaKey.PERIOD_ENDING) if latest_q_is else None
        q_date = pd.to_datetime(q_date_raw) if q_date_raw else None
        
        is_q_aligned = False
        if p_type == ReportPeriod.QUARTERLY.value:
            is_q_aligned = True # 锚点本身就是季报，天然放行
        elif p_type == ReportPeriod.ANNUAL.value and q_date and anchor_date:
            # 核心业务逻辑升级：如果当前在看年报，但系统里有新鲜的 Q4 数据 (相差不到30天)，予以放行！
            # 这挽救了美股和优质 A/港股的 Q4 Exit-Velocity 动量指标。
            if abs((q_date - anchor_date).days) <= 30:
                is_q_aligned = True
                
        if is_q_aligned:
            # 获取严格对齐的季度分析指标 (若 p_type=annual，latest_ana 是年报指标，必须重新取季度指标)
            q_ana = facade.get_aligned_report(ReportPeriod.QUARTERLY.value, StatementType.ANALYSIS, q_date, window=30)
            
            y_r_q = get_field_value(q_ana, FinKey.ANA_REV_YOY) if q_ana else None
            res["rev_growth_yoy_quarter"] = (
                round(float(y_r_q) / 100, 4) if y_r_q is not None 
                else calculate_growth_yoy(
                    facade.get_scoped_series(ReportPeriod.QUARTERLY.value, StatementType.INCOME),
                    FinKey.REV, True, get_field_value
                )
            )
            
            y_ni_q = get_field_value(q_ana, FinKey.ANA_NI_YOY) if q_ana else None
            res["ni_growth_yoy_quarter"] = (
                round(float(y_ni_q) / 100, 4) if y_ni_q is not None
                else calculate_growth_yoy(
                    facade.get_scoped_series(ReportPeriod.QUARTERLY.value, StatementType.INCOME),
                    FinKey.NI, True, get_field_value
                )
            )

        # ==================================================
        # 2. 年度增长 (Annual YoY) - 长期视角，始终执行
        # ==================================================
        y_r_a = get_field_value(latest_annual_ana, FinKey.ANA_REV_YOY) if latest_annual_ana else None
        res["rev_growth_yoy_annual"] = (
            round(float(y_r_a) / 100, 4) if y_r_a is not None
            else calculate_growth_yoy(
                facade.get_scoped_series(ReportPeriod.ANNUAL.value, StatementType.INCOME),
                FinKey.REV, False, get_field_value
            )
        )
        
        y_ni_a = get_field_value(latest_annual_ana, FinKey.ANA_NI_YOY) if latest_annual_ana else None
        res["ni_growth_yoy_annual"] = (
            round(float(y_ni_a) / 100, 4) if y_ni_a is not None
            else calculate_growth_yoy(
                facade.get_scoped_series(ReportPeriod.ANNUAL.value, StatementType.INCOME),
                FinKey.NI, False, get_field_value
            )
        )
        
        return res

    def _calc_efficiency_metrics(
        self,
        latest_is: Dict,
        cur_bs: Optional[Dict],
        cur_cf: Optional[Dict],
        latest_ana: Optional[Dict],
        ttm_ni: Optional[float],
        ann_multiplier: Optional[float],
        is_cumulative: bool
    ) -> Dict[str, Any]:
        """计算效率与回报 (Efficiency) - 区分 TTM 与 当期年化"""
        res = {}
        
        # 提取基础标量
        rev = get_field_value(latest_is, FinKey.REV)
        ni = get_field_value(latest_is, FinKey.NI)
        oi = get_field_value(latest_is, FinKey.OI)
        eq = get_field_value(cur_bs, FinKey.EQUITY)
        fcf_cur = get_fcf_raw(cur_cf)

        # --- 1. ROE (Return on Equity) ---
        # Priority A: 成品 (API Actual)
        roe_api = get_field_value(latest_ana, FinKey.ANA_ROE_ACTUAL) if latest_ana else None
        if roe_api is not None:
            res["roe_annual_yearly"] = round(float(roe_api) / 100, 4)
        
        # 负权益检查 (规则一：Equity <= 0 返回字符串)
        if eq is not None and eq <= 0:
            res["roe_status"] = "N/A (Negative Equity From Latest Report)"
        else:
            # 1.1 ROE TTM (滚动12个月，平滑季节性，最推荐)
            if ttm_ni is not None and eq is not None and eq > 0:
                res["roe_annual_ttm"] = round(ttm_ni / eq, 4)

            # 1.2 ROE Period Actual (基于当期表现推演)
            # 策略：成品(Actual) -> 半成品(Avg*M) -> 自算(NI*M/Eq)
            # 一旦获取到高优先级的，就不再计算低优先级的，避免冗余
            roe_period = None
            # Priority B: 半成品 (API Avg * Multiplier) - 仅在累积制下尝试
            if roe_period is None and latest_ana is not None and is_cumulative and ann_multiplier is not None:
                roe_avg = get_field_value(latest_ana, FinKey.ANA_ROE_AVG)
                if roe_avg is not None:
                    roe_period = (float(roe_avg) / 100) * ann_multiplier

            # Priority C: 自算 (NI * Multiplier / Equity)
            if roe_period is None and ni is not None and eq is not None and eq > 0 and ann_multiplier is not None:
                roe_period = (ni * ann_multiplier) / eq

            if roe_period is not None:
                res["roe_period_actual"] = round(roe_period, 4)

        # --- 2. Margins (利润率) ---
        # 优先使用 API 提供的 Net Margin (防止计算误差)
        npm_api = get_field_value(latest_ana, FinKey.ANA_NET_MARGIN) if latest_ana else None
        res["net_margin_period_actual"] = (
            round(float(npm_api) / 100, 4) if npm_api is not None 
            else (round(ni / rev, 4) if ni is not None and rev is not None and rev > 0 else None)
        )
        
        if oi is not None and rev is not None and rev > 0:
            res["op_margin_period_actual"] = round(oi / rev, 4)
            
        if fcf_cur is not None and rev is not None and rev > 0:
            res["fcf_margin_period_actual"] = round(fcf_cur / rev, 4)

        return res

    def _calc_solvency_metrics(
        self,
        latest_is: Dict,
        cur_bs: Optional[Dict],
        cur_cf: Optional[Dict],
        latest_ana: Optional[Dict]
    ) -> Dict[str, Any]:
        """计算偿债与流动性 (Solvency)"""
        res = {}
        
        eq = get_field_value(cur_bs, FinKey.EQUITY)
        liab = get_field_value(cur_bs, FinKey.LIAB)
        ni = get_field_value(latest_is, FinKey.NI)
        ocf = get_field_value(cur_cf, FinKey.OCF)

        # 负债权益比
        if eq is not None and eq > 0 and liab is not None:
            res["total_liabilities_to_equity"] = round(liab / eq, 4)
        
        # 流动比率 (优先 API)
        cr_api = get_field_value(latest_ana, FinKey.ANA_CURRENT_RATIO) if latest_ana else None
        if cr_api is not None:
            res["current_ratio_liquidity"] = round(float(cr_api), 4)
        else:
            ca = get_field_value(cur_bs, FinKey.C_ASSETS)
            cl = get_field_value(cur_bs, FinKey.C_LIAB)
            if ca is not None and cl is not None and cl > 0:
                res["current_ratio_liquidity"] = round(ca / cl, 4)
        
        # 盈利质量 (规则三：语义化标记)
        # 若 NI > 0：计算 OCF / NI
        # 若 NI <= 0 且 OCF > 0：必须返回字符串 "Positive OCF with Net Loss"
        # 其他情况返回 None
        if ni is not None and ni > 0 and ocf is not None:
            res["earnings_quality_period"] = round(ocf / ni, 4)
        elif ni is not None and ni <= 0 and ocf is not None and ocf > 0:
            # 语义化标记：亏损但现金流为正
            res["earnings_quality_period"] = "Positive OCF with Net Loss"
            
        return res

    def _calc_valuation_metrics(
        self,
        facade: ResearchPackFacade,
        ttm_fcf: Optional[float],
        ttm_ni: Optional[float]
    ) -> Dict[str, Any]:
        """计算估值指标 (Valuation)"""
        res = {}
        
        metrics = facade.market_metrics
        m_cap = metrics.get("market_cap_rmb", get_field_value(metrics, FinKey.MCAP))
        currency_ctx = facade.currency_context

        # FCF Yield (规则四：包含币种碰撞逻辑)
        if m_cap and m_cap > 0 and ttm_fcf is not None:
            method = currency_ctx.get("audit_method", "")
            
            # 场景: 币种错配 (如港股 RMB 财报 vs HKD 市值) -> 借道 PE 消除汇率
            if "PE_Collision" in method:
                api_pe = get_field_value(metrics, FinKey.PE)
                if api_pe is not None and api_pe > 0 and ttm_ni is not None and ttm_ni > 0 and ttm_fcf > 0:
                    res["fcf_yield_realtime_ttm"] = round((ttm_fcf / ttm_ni) / api_pe, 4)
            # 场景: 常规同币种 -> 直接除
            else:
                res["fcf_yield_realtime_ttm"] = round((ttm_fcf / m_cap), 4)
                
        return res


# ==========================================
# 3. 核心 Processor (优雅升级)
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
            CoreFinancialRatioAnalyzer(),
            MultiTimeframeMarketAnalyzer(config),  # 新增：多时间框架市场分析器
            FundamentalDistillationAnalyzer(),      # 新增：基本面蒸馏分析器
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

        # 3. 初始化 technical_summary 容器
        if pack.technical_summary is None:
            pack.technical_summary = {}

        # 4. 遍历所有挂载的分析器进行运算（自描述路由）
        # 使用 asyncio.to_thread 将同步计算密集型任务放入线程池，避免阻塞事件循环
        for analyzer in self.analyzers:
            try:
                result = await asyncio.to_thread(analyzer.analyze, pack)
                if result:
                    # 🌟 动态路由：每个 Analyzer 自描述存储位置
                    slot_name = analyzer.target_slot
                    # 如果 result 已经是扁平结构，直接赋值；否则提取内部值
                    if slot_name in result:
                        pack.technical_summary[slot_name] = result[slot_name]
                    else:
                        pack.technical_summary[slot_name] = result
            except Exception as e:
                print(f"  [TechnicalProcessor] {analyzer.__class__.__name__} Failed for {pack.symbol}: {e}")

        # 5. 封装并返回标准输出
        return ComponentOutput(success=True, payload=pack)

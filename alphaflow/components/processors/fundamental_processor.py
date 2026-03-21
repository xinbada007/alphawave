from typing import Any, Dict, Optional
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.core.facade import to_facade
from alphaflow.core.keys import Key
from alphaflow.core.utils import resolve_aligned_mcap
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.components.processors.fundamentals.insider import InsiderAnalyzer
from alphaflow.components.processors.fundamentals.health_tagger import generate_health_tags
from alphaflow.components.processors.fundamentals.dividend import DividendAnalyzer

# 触发指标注册
import alphaflow.components.processors.metrics.ratios


class FundamentalProcessor(BaseProcessor):
    """基本面与估值调度器 - V3 架构"""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)

    async def process(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        pack: ResearchPack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        
        if not pack.fundamentals:
            return ComponentOutput(success=True, payload=pack)
            
        print(f"  [{self.name}] Distilling fundamental features for {pack.symbol}...")
        
        # 1. 发动指标引擎
        facade = to_facade(pack)
        MetricEngine.execute_all(facade, pack)
        
        # 2. 估值 LCD 域（含币种修正，需可选依赖，故不走 MetricEngine）
        self._compute_valuation_lcd(facade, pack)

        # 3. 拯救孤儿：触发 HealthTagger，根据引擎算出的指标生成语义标签
        if pack.distilled_features.fundamental_metrics:
            health_tags = generate_health_tags(pack.distilled_features.fundamental_metrics)
            # 🚀 显式赋值替代原地变异，与 exclude_unset=True 兼容
            pack.distilled_features.fundamental_insights = {"health_tags": health_tags}

        # 4. 高管交易降噪
        pack.distilled_features.insider_insights = InsiderAnalyzer.analyze(pack)
        
        # 5. 分红分析 (闭环漏洞 4)
        pack.distilled_features.dividend_insights = DividendAnalyzer.analyze(pack)

        # 6. 向黑板宣告：隐匿原始脏时序
        pack.registry.claim_domain("insider_trading_history")
        pack.registry.claim_domain("dividends_history")

        return ComponentOutput(success=True, payload=pack)

    def _compute_valuation_lcd(self, facade, pack: ResearchPack):
        """
        估值 LCD 域：PE/PB 透传 + 币种修正的 PS_TTM。
        不走 MetricEngine 的原因：ps_ttm 依赖可选的 currency_context 和 MARKET_CAP_RMB,
        MetricEngine 的 strict None-skip 无法处理可选依赖。
        """
        valuation = {}

        # PE/PB: 直接透传 API 值 (P0 — 完全规避币种问题)
        pe = facade.resolve_dependency("LATEST", "metrics", Key.metrics.PE_RATIO)
        if pe is not None:
            valuation["pe_ttm"] = round(pe, 4)

        pb = facade.resolve_dependency("LATEST", "metrics", Key.metrics.PRICE_TO_BOOK)
        if pb is not None:
            valuation["pb"] = round(pb, 4)

        # PS_TTM: 需要币种修正的市值
        rev_ttm = facade.resolve_dependency("TTM", "income", Key.income.TOTAL_REVENUE)
        if rev_ttm and rev_ttm > 0:
            mcap_rmb = facade.resolve_dependency("LATEST", "metrics", Key.metrics.MARKET_CAP_RMB)
            mcap_raw = facade.resolve_dependency("LATEST", "metrics", Key.metrics.MARKET_CAP)
            currency_ctx = getattr(facade, 'currency_context', None)

            aligned = resolve_aligned_mcap(mcap_rmb, mcap_raw, currency_ctx)
            if aligned is not None:
                valuation["ps_ttm"] = round(aligned / rev_ttm, 4)

        if valuation:
            metrics = pack.distilled_features.fundamental_metrics or {}
            metrics["valuation_lcd"] = valuation
            pack.distilled_features.fundamental_metrics = metrics
            # 认领消费的 Keys
            pack.registry.claim_standard_key(Key.metrics.PE_RATIO)
            pack.registry.claim_standard_key(Key.metrics.PRICE_TO_BOOK)
            pack.registry.claim_standard_key(Key.metrics.MARKET_CAP)
            pack.registry.claim_standard_key(Key.metrics.MARKET_CAP_RMB)


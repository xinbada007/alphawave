from typing import Any, Dict, Optional
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.core.facade import to_facade
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.components.processors.fundamentals.insider import InsiderAnalyzer
from alphaflow.components.processors.fundamentals.health_tagger import generate_health_tags
from alphaflow.components.processors.fundamentals.dividend import DividendAnalyzer

# 触发全量声明式指标注册（6个域模块）
import alphaflow.components.processors.metrics  # noqa: F401


class FundamentalProcessor(BaseProcessor):
    """基本面与估值调度器 — 纯编排器架构"""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)

    async def process(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        pack: ResearchPack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        
        if not pack.fundamentals:
            return ComponentOutput(success=True, payload=pack)
            
        print(f"  [{self.name}] Distilling fundamental features for {pack.symbol}...")
        
        # 1. 发动声明式指标引擎（含 profitability/solvency/efficiency/quality/growth/valuation）
        facade = to_facade(pack)
        MetricEngine.execute_all(facade, pack)
        
        # 2. trend_status 元判定（读已算的 trend_delta 域做联合裁决）
        self._synthesize_trend_status(pack)

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

    @staticmethod
    def _synthesize_trend_status(pack: ResearchPack):
        """
        趋势方向元判定：读取 MetricEngine 已算出的 trend_delta 域的百分点 delta，
        联合投票决定 IMPROVING / DECLINING / MIXED。
        """
        metrics = pack.distilled_features.fundamental_metrics or {}
        td = metrics.get("trend_delta", {})
        if not td:
            return

        deltas = [v for k, v in td.items() if k.endswith("_pp") and isinstance(v, (int, float))]
        if not deltas:
            return

        improving = sum(1 for d in deltas if d > 0.5)
        declining = sum(1 for d in deltas if d < -0.5)

        if improving > declining:
            td["trend_status"] = "IMPROVING"
        elif declining > improving:
            td["trend_status"] = "DECLINING"
        else:
            td["trend_status"] = "MIXED"

        metrics["trend_delta"] = td
        pack.distilled_features.fundamental_metrics = metrics

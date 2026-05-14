from typing import Any, Dict, Optional
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.core.facade import to_facade
from alphaflow.components.processors.engine import MetricEngine
from alphaflow.components.processors.fundamentals.insider import InsiderAnalyzer
from alphaflow.components.processors.fundamentals.scanner import scan_fundamentals
from alphaflow.components.processors.fundamentals.dividend import DividendAnalyzer
from alphaflow.components.processors.fundamentals.earnings import EarningsAnalyzer
from alphaflow.components.processors.fundamentals.evaluators import EvaluatorEngine
from alphaflow.components.processors.fundamentals.consensus import ConsensusAnalyzer

# 触发全量声明式指标注册（6个域模块）
import alphaflow.components.processors.metrics  # noqa: F401


class FundamentalProcessor(BaseProcessor):
    """基本面与估值调度器 — 纯编排器架构（零业务逻辑）"""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)

    async def process(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        pack: ResearchPack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        
        if not pack.fundamentals:
            return ComponentOutput(success=True, payload=pack)
            
        print(f"  [{self.name}] Distilling fundamental features for {pack.symbol}...")
        
        # ==========================================
        # 优雅的三层架构 (The 3-Layer Architecture)
        # ==========================================
        
        # 1. 检验科 (Metrics) — 纯数值提取，无任何定性判断
        facade = to_facade(pack)
        MetricEngine.execute_all(facade, pack)
        
        # 2. 主治医师 (Evaluator/Tagging) — 基于本域指标下发必须的分类诊断
        # 这将自动触发 trend_status, (未来) solvency_verdict 等标签逻辑
        EvaluatorEngine.evaluate_all(pack)

        # 3. 会诊室 (Scanner) — 跨域复杂病理信号检测 (事件/异象抓取)
        if pack.distilled_features.fundamental_metrics:
            signals = scan_fundamentals(pack.distilled_features.fundamental_metrics)
            # 🚀 显式赋值替代原地变异，与 exclude_unset=True 兼容
            if signals:
                pack.distilled_features.fundamental_insights = {"signals": signals}

        # 4. 高管交易降噪
        pack.distilled_features.insider_insights = InsiderAnalyzer.analyze(pack)
        
        # 5. 分红分析 (闭环漏洞 4)
        pack.distilled_features.dividend_insights = DividendAnalyzer.analyze(pack)

        # 6. 财报超预期分析
        pack.distilled_features.earnings_insights = EarningsAnalyzer.analyze(pack)

        # 7. 分析师共识
        pack.distilled_features.analyst_consensus = ConsensusAnalyzer.analyze(pack)
        from alphaflow.core.context import GlobalContext
        is_debug = GlobalContext().get("DEBUG", False)
        
        if not is_debug:
            pack.registry.claim_domain("insider_trading_history")
            pack.registry.claim_domain("dividends_history")
            pack.registry.claim_domain("earnings_calendar")
            pack.registry.claim_domain("management_history")
            pack.registry.claim_domain("splits_history")
            pack.registry.claim_domain("estimates")

        return ComponentOutput(success=True, payload=pack)


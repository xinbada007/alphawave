from typing import Any, Dict, Optional
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.core.facade import to_facade
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
        
        # 2. 拯救孤儿：触发 HealthTagger，根据引擎算出的指标生成语义标签
        if pack.distilled_features.fundamental_metrics:
            health_tags = generate_health_tags(pack.distilled_features.fundamental_metrics)
            pack.distilled_features.fundamental_insights["health_tags"] = health_tags

        # 3. 高管交易降噪
        pack.distilled_features.insider_insights = InsiderAnalyzer.analyze(pack)
        
        # 4. 分红分析 (闭环漏洞 4)
        pack.distilled_features.dividend_insights = DividendAnalyzer.analyze(pack)

        # 5. 向黑板宣告：隐匿原始脏时序
        pack.registry.claim_domain("insider_trading_history")
        pack.registry.claim_domain("dividends_history")

        return ComponentOutput(success=True, payload=pack)

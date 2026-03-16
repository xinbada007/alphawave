from typing import Any, Dict, Optional
import asyncio
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.components.processors.techniques import MultiTimeframeMarketAnalyzer

class TechnicalProcessor(BaseProcessor):
    """纯粹的技术面处理器 (Pure Technical Processor)"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.analyzer = MultiTimeframeMarketAnalyzer(config)

    async def process(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        pack: ResearchPack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        
        if not pack.market_data:
            return ComponentOutput(success=True, payload=pack)
            
        print(f"  [{self.name}] Distilling technical features for {pack.symbol}...")

        try:
            # 1. 线程池中执行技术面分析
            result = await asyncio.to_thread(self.analyzer.analyze, pack)
            if result and "technical_and_sentiment" in result:
                # 2. 写入强类型特征槽位
                pack.distilled_features.technical = result["technical_and_sentiment"]
                
                # 3. 【核心】领域级认领！告诉 LLM 视图屏蔽整个原始 market_data！
                pack.registry.claim_domain("market_data")
                
        except Exception as e:
            print(f"  [{self.name}] ⚠️ Analysis failed for {pack.symbol}: {e}")

        return ComponentOutput(success=True, payload=pack)

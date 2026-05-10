from typing import Any, Dict, Optional
import asyncio
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.components.processors.techniques.registry import TechnicalAnalyzerRegistry

# 关键：导入 _legacy_adapter 与 analyzers 触发 @register 装饰器副作用。
# 与 metrics/__init__.py 触发 @MetricEngine.fundamental_metric 同款模式。
from alphaflow.components.processors.techniques import _legacy_adapter  # noqa: F401
from alphaflow.components.processors.techniques import analyzers        # noqa: F401


class TechnicalProcessor(BaseProcessor):
    """
    纯粹的技术面处理器 (Pure Technical Processor)
    
    V4 架构：本类是 TechnicalAnalyzerRegistry 的薄胶水层，
    不再硬编码任何 analyzer。所有技术因子通过 @TechnicalAnalyzerRegistry.register
    装饰器注册并由 registry 沙箱化执行。
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self._registry = TechnicalAnalyzerRegistry

    async def process(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        pack: ResearchPack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        
        if not pack.market_data:
            return ComponentOutput(success=True, payload=pack)
            
        print(f"  [{self.name}] Distilling technical features for {pack.symbol}...")

        try:
            df = pack.market_data.to_df()
            # 1. 线程池中执行所有注册的 analyzer（沙箱化、按 DAG 拓扑序）
            merged = await asyncio.to_thread(
                self._registry.run_all, df, pack, self.config
            )
            if merged:
                # 2. 写入强类型特征槽位（Pydantic V2 写入契约：整体重赋值）
                pack.distilled_features.technical = merged
                
                # 3. 【核心】领域级认领！告诉 LLM 视图屏蔽整个原始 market_data！
                pack.registry.claim_domain("market_data")
                
        except Exception as e:
            print(f"  [{self.name}] ⚠️ Analysis failed for {pack.symbol}: {e}")

        return ComponentOutput(success=True, payload=pack)

from typing import Any
from alphaflow.core.base import BaseVisualizer
from alphaflow.core.schema import AnalysisContext, ComponentOutput, MarketData, ResearchPack
from alphaflow.utils.quickchart import QuickChartClient

class QuickChartVisualizer(BaseVisualizer):
    async def visualize(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        
        # 支持 ResearchPack
        pack = input_data
        if isinstance(input_data, ComponentOutput):
            pack = input_data.payload
        
        if not isinstance(pack, ResearchPack):
             return ComponentOutput(success=False, error=f"Expected ResearchPack, got {type(pack)}")

        try:
            df = pack.market_data.to_df()
            print("  [Chart] Generating URL...")

            client = QuickChartClient()
            
            # 生成主图 (收盘价)
            url = client.create_chart_url(
                df, 
                title=f"{pack.symbol} Analysis", 
                target_col="close"
            )
            
            # 存入 pack
            pack.charts["main"] = url

            return ComponentOutput(success=True, payload=pack)

        except Exception as e:
            return ComponentOutput(success=False, error=str(e))

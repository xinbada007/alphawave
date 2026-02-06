from typing import Any
from alphaflow.core.base import BaseVisualizer
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.utils.quickchart import QuickChartClient

class QuickChartVisualizer(BaseVisualizer):
    """
    【可视化展示器】
    职责：将计算后的数据生成 QuickChart 短链接。
    """
    async def visualize(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        pack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        
        if not isinstance(pack, ResearchPack) or pack.market_data is None:
             return ComponentOutput(success=False, error="Visualizer: No data to plot")

        try:
            df = pack.market_data.to_df()
            print(f"  [Visualizer] Generating chart for {pack.symbol}...")

            # 使用我们在 utils 中定义的智能客户端
            # 默认 250 点限额，自动降采样，自动处理最新点
            client = QuickChartClient(max_points=250)
            
            # 生成主图
            url = client.create_chart_url(
                df, 
                title=f"{pack.symbol} Integrated Analysis (Price + Indicators)", 
                target_col="close"
            )
            
            # 存入 pack 的 charts 字典
            pack.charts["main_analysis"] = url

            return ComponentOutput(success=True, payload=pack)

        except Exception as e:
            return ComponentOutput(success=False, error=f"Visualizer Fail: {str(e)}")
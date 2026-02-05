from typing import Any
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, DataFrameModel, MarketData, ResearchPack
from openbb import obb
import pandas as pd

class RSIProcessor(BaseProcessor):
    async def process(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        # 支持 ResearchPack
        pack = input_data
        if isinstance(input_data, ComponentOutput):
             pack = input_data.payload

        if not isinstance(pack, ResearchPack):
            return ComponentOutput(success=False, error=f"Expected ResearchPack, got {type(pack)}")

        try:
            df = pack.market_data.to_df()
            print("  [RSI] Calculating RSI...")

            rsi_df = obb.technical.rsi(data=df, target="close").to_df()
            
            if 'rsi' in rsi_df.columns:
                 df = df.join(rsi_df[['rsi']])
            
            # 更新 pack 中的 technicals 和 market_data
            pack.technicals = DataFrameModel.from_df(rsi_df)
            pack.market_data = DataFrameModel.from_df(df)
            
            return ComponentOutput(success=True, payload=pack)
            
        except Exception as e:
             return ComponentOutput(success=False, error=str(e))

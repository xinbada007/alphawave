from typing import Any
import pandas as pd
from openbb import obb
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, DataFrameModel, ResearchPack

class TechnicalProcessor(BaseProcessor):
    """
    【技术面分析器】
    职责：基于原始行情数据计算各类技术指标 (RSI, MA, etc.)。
    它不关心数据来源，只关心计算逻辑。
    """
    async def process(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        # 支持从上一步 Pipeline 的输出中解包
        pack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        
        if not isinstance(pack, ResearchPack) or pack.market_data is None:
            return ComponentOutput(success=False, error="TechnicalProcessor: Invalid Input (No Market Data)")

        try:
            # 1. 解包数据
            df = pack.market_data.to_df()
            print(f"  [Processor] Calculating indicators for {pack.symbol}...")

            # 2. 计算指标 (使用标准 SMA)
            rsi_res = obb.technical.rsi(data=df, target="close")
            rsi_df = rsi_res.to_df()
            
            # 使用 sma 替代 ma
            ma_res = obb.technical.sma(data=df, target="close", length=20)
            ma_df = ma_res.to_df()

            # 3. 数据沉淀
            if not rsi_df.empty:
                # 某些版本返回的列名可能不同，强制取第一列
                col = rsi_df.columns[0]
                df['rsi'] = rsi_df[col]
            
            if not ma_df.empty:
                col = ma_df.columns[0]
                df['sma_20'] = ma_df[col]
            
            # 更新 ResearchPack
            pack.market_data = DataFrameModel.from_df(df)
            pack.technicals = DataFrameModel.from_df(rsi_df) # 存储纯指标数据
            
            return ComponentOutput(success=True, payload=pack)
            
        except Exception as e:
            return ComponentOutput(success=False, error=f"Processor Fail: {str(e)}")
from typing import Any, Dict
from openbb import obb
from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack

class FundamentalCollector(BaseCollector):
    """
    【经营面分析器】
    职责：获取财报指标、经营数据快照。
    Vibe Coding 特性：半固定流程，易于扩展指标字段。
    """
    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        input_data = kwargs.get('input_data')
        pack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        
        if pack is None:
            pack = ResearchPack(symbol=context.symbols[0])

        try:
            print(f"  [Fundamental] Fetching metrics for {pack.symbol}...")
            # 获取基本面指标
            metrics_res = obb.equity.fundamental.metrics(symbol=pack.symbol, provider="yfinance")
            m_df = metrics_res.to_df()
            
            if not m_df.empty:
                # 记录核心经营数据
                pack.fundamentals = m_df.iloc[0].to_dict()
                
            # 预留：此处可以继续扩展获取 Balance Sheet 或 Cash Flow
            
            return ComponentOutput(success=True, payload=pack)
        except Exception as e:
            # 基本面抓取失败不应导致 Pipeline 中断
            print(f"  [!] Fundamental Data skipped: {e}")
            return ComponentOutput(success=True, payload=pack)

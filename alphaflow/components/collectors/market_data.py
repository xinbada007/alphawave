from typing import Any, Dict
import pandas as pd
from openbb import obb
from alphaflow.core.base import BaseCollector
from alphaflow.utils.cache import DiskCache
from alphaflow.core.schema import AnalysisContext, ComponentOutput, DataFrameModel, ResearchPack

class EquityPriceCollector(BaseCollector):
    """
    【股价采集器】
    职责：获取标准 OHLCV 数据。
    Vibe Coding 特性：固定流程，高确定性。
    """
    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        self.cache = DiskCache(expiry_seconds=3600 * 24)

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        symbol = context.symbols[0]
        
        # 稳健的 pack 初始化逻辑
        input_data = kwargs.get('input_data')
        pack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        
        if pack is None:
            pack = ResearchPack(symbol=symbol)

        try:
            cache_key = f"raw_ohlcv_{symbol}"
            df = self.cache.get(cache_key)
            
            if df is None:
                print(f"  [MarketData] Fetching {symbol} from yfinance...")
                res = obb.equity.price.historical(symbol=symbol, provider="yfinance")
                df = res.to_df()
                self.cache.set(cache_key, df)
            
            # 标准化清洗
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
            
            pack.market_data = DataFrameModel.from_df(df)
            return ComponentOutput(success=True, payload=pack)
            
        except Exception as e:
            return ComponentOutput(success=False, error=f"MarketData Error: {str(e)}")

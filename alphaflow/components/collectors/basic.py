from typing import Any, Dict
import pandas as pd
from openbb import obb
from alphaflow.core.base import BaseCollector
from alphaflow.utils.cache import DiskCache
from alphaflow.core.schema import AnalysisContext, ComponentOutput, DataFrameModel, ResearchPack

class OpenBBCollector(BaseCollector):
    """
    【行情采集器】
    职责：获取原始 OHLCV 数据、公司新闻和基本面指标。
    不包含任何技术指标计算逻辑。
    """
    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        # 默认缓存 24 小时，减少 API 压力
        self.cache = DiskCache(expiry_seconds=3600 * 24)

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        symbol = context.symbols[0]
        pack = ResearchPack(symbol=symbol)

        try:
            # 1. 抓取原始行情 (OHLCV)
            cache_key = f"raw_ohlcv_{symbol}"
            df = self.cache.get(cache_key)
            
            if df is None:
                print(f"  [Collector] Fetching fresh OHLCV for {symbol}...")
                res = obb.equity.price.historical(symbol=symbol, provider="yfinance")
                df = res.to_df()
                self.cache.set(cache_key, df)
            else:
                print(f"  [Collector] Using cached OHLCV for {symbol}.")

            # 数据标准化清洗
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
            
            pack.market_data = DataFrameModel.from_df(df)

            # 2. 抓取新闻 (Raw News)
            if hasattr(obb, 'news'):
                try:
                    news_res = obb.news.company(symbol=symbol, provider="yfinance")
                    pack.news = news_res.to_df().head(5).to_dict(orient='records')
                except Exception as e:
                    print(f"  [!] News fetch failed: {e}")
            else:
                print("  [!] News module not available in OpenBB.")

            # 3. 抓取基本面快照 (Raw Metrics)
            try:
                metrics_res = obb.equity.fundamental.metrics(symbol=symbol, provider="yfinance")
                m_df = metrics_res.to_df()
                if not m_df.empty:
                    pack.fundamentals = m_df.iloc[0].to_dict()
            except Exception as e:
                print(f"  [!] Metrics fetch failed: {e}")

            return ComponentOutput(success=True, payload=pack)
            
        except Exception as e:
            return ComponentOutput(success=False, error=f"Collector Fail: {str(e)}")
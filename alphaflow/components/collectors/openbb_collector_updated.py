from typing import Any, Dict
import pandas as pd
from openbb import obb
from alphaflow.core.base import BaseCollector
from alphaflow.utils.cache import DiskCache
from alphaflow.core.schema import AnalysisContext, ComponentOutput, MarketData, DataFrameModel, ResearchPack

class OpenBBCollector(BaseCollector):
    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        self.cache = DiskCache(expiry_seconds=3600 * 24)
        # 从配置中获取提供商，默认为yfinance
        self.provider = config.get('provider', 'yfinance') if config else 'yfinance'

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        symbol = context.symbols[0]
        pack = ResearchPack(symbol=symbol)

        try:
            # 1. 行情数据 (带缓存)
            cache_key = f"ohlcv_{symbol}_{self.provider}"
            df = self.cache.get(cache_key)
            if df is None:
                print(f"  [OpenBB] Fetching fresh data for {symbol} using {self.provider}...")
                try:
                    res = obb.equity.price.historical(symbol=symbol, provider=self.provider)
                    df = res.to_df()
                    self.cache.set(cache_key, df)
                except Exception as e:
                    print(f"  [!] Failed to fetch with {self.provider}: {e}")
                    # 如果指定提供商失败，尝试yfinance作为后备
                    if self.provider != 'yfinance':
                        print(f"  [OpenBB] Falling back to yfinance for {symbol}...")
                        res = obb.equity.price.historical(symbol=symbol, provider='yfinance')
                        df = res.to_df()
                        self.cache.set(cache_key, df)
            else:
                print(f"  [OpenBB] Using cached data for {symbol} ({self.provider}).")
            
            # 清洗并存入 pack
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
            
            pack.market_data = DataFrameModel.from_df(df)

            # 2. 获取新闻 (尝试)
            try:
                news_res = obb.news.company(symbol=symbol, provider=self.provider)
                news_df = news_res.to_df()
                pack.news = news_df.head(5).to_dict(orient='records')
            except Exception as e:
                print(f"  [!] News fetch failed with {self.provider}: {e}")
                # 尝试使用yfinance作为后备
                try:
                    news_res = obb.news.company(symbol=symbol, provider="yfinance")
                    news_df = news_res.to_df()
                    pack.news = news_df.head(5).to_dict(orient='records')
                except Exception as e2:
                    print(f"  [!] News fetch failed with yfinance too: {e2}")

            # 3. 获取基本面指标 (尝试)
            try:
                metrics_res = obb.equity.fundamental.metrics(symbol=symbol, provider=self.provider)
                m_df = metrics_res.to_df()
                pack.fundamentals = m_df.iloc[0].to_dict() if not m_df.empty else {}
            except Exception as e:
                print(f"  [!] Metrics fetch failed with {self.provider}: {e}")
                # 尝试使用yfinance作为后备
                try:
                    metrics_res = obb.equity.fundamental.metrics(symbol=symbol, provider="yfinance")
                    m_df = metrics_res.to_df()
                    pack.fundamentals = m_df.iloc[0].to_dict() if not m_df.empty else {}
                except Exception as e2:
                    print(f"  [!] Metrics fetch failed with yfinance too: {e2}")

            return ComponentOutput(success=True, payload=pack)
        except Exception as e:
            return ComponentOutput(success=False, error=str(e))
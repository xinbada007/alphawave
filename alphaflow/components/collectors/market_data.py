from typing import Any, Dict
import pandas as pd
import os
from openbb import obb
from alphaflow.core.base import BaseCollector
from alphaflow.utils.cache import DiskCache
from alphaflow.core.schema import AnalysisContext, ComponentOutput, DataFrameModel, ResearchPack
from alphaflow.utils.api_rotator import get_api_key, report_api_usage


class EquityPriceCollector(BaseCollector):
    """
    【增强版股价采集器】
    职责：获取标准 OHLCV 数据及相关的市场指标。
    Vibe Coding 特性：固定流程，高确定性，多提供商支持，API轮询。
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        self.cache = DiskCache(expiry_seconds=3600 * 24)  # 24小时缓存
        # 从配置中获取提供商，默认为yfinance
        self.provider = config.get('provider', 'yfinance') if config else 'yfinance'

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        # 1. 标准解包
        input_data = kwargs.get('input_data')
        pack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        if pack is None:
            pack = ResearchPack(symbol=context.symbols[0])

        try:
            # 获取OHLCV数据（带缓存）
            cache_key = f"raw_ohlcv_{pack.symbol}_{self.provider}"
            df = self.cache.get(cache_key)
            
            if df is None:
                print(f"  [MarketData] Fetching {pack.symbol} from {self.provider}...")
                
                # 尝试获取API密钥并设置环境变量
                api_key = None
                if self.provider in ['polygon', 'fmp', 'alpha_vantage', 'tiingo']:
                    # 对于Polygon，使用API轮询机制获取多个API密钥中的一个
                    if self.provider == 'polygon':
                        # 使用轮询获取Polygon API密钥
                        api_key = get_api_key(self.provider, api_type='market_data')
                        if api_key:
                            print(f"  [MarketData] Using rotated {self.provider} API key")
                            # 临时设置环境变量
                            original_key = os.environ.get(f"{self.provider.upper()}_API_KEY")
                            os.environ[f"{self.provider.upper()}_API_KEY"] = api_key
                            
                            try:
                                # 执行API调用
                                res = obb.equity.price.historical(symbol=pack.symbol, provider=self.provider)
                                df = res.to_df()
                                
                                # 报告API使用情况
                                report_api_usage(self.provider, api_key, success=True)
                                self.cache.set(cache_key, df)
                                print(f"  [MarketData] Successfully fetched data using {self.provider} API key")
                            except Exception as e:
                                print(f"  [!] Failed to fetch with {self.provider}: {e}")
                                # 报告API使用失败
                                report_api_usage(self.provider, api_key, success=False)
                                # 尝试yfinance作为后备
                                print(f"  [MarketData] Falling back to yfinance for {pack.symbol}...")
                                res = obb.equity.price.historical(symbol=pack.symbol, provider='yfinance')
                                df = res.to_df()
                                fallback_cache_key = f"raw_ohlcv_{pack.symbol}_yfinance"
                                self.cache.set(fallback_cache_key, df)
                            finally:
                                # 恢复原始环境变量
                                if original_key is not None:
                                    os.environ[f"{self.provider.upper()}_API_KEY"] = original_key
                                elif f"{self.provider.upper()}_API_KEY" in os.environ:
                                    del os.environ[f"{self.provider.upper()}_API_KEY"]
                    else:
                        # 对于其他需要API密钥的提供商，也使用轮询
                        api_key = get_api_key(self.provider)
                        if api_key:
                            # 临时设置环境变量
                            original_key = os.environ.get(f"{self.provider.upper()}_API_KEY")
                            os.environ[f"{self.provider.upper()}_API_KEY"] = api_key
                            
                            try:
                                # 执行API调用
                                res = obb.equity.price.historical(symbol=pack.symbol, provider=self.provider)
                                df = res.to_df()
                                
                                # 恢复原始环境变量
                                if original_key is not None:
                                    os.environ[f"{self.provider.upper()}_API_KEY"] = original_key
                                elif f"{self.provider.upper()}_API_KEY" in os.environ:
                                    del os.environ[f"{self.provider.upper()}_API_KEY"]
                                
                                # 报告API使用情况
                                report_api_usage(self.provider, api_key, success=True)
                                self.cache.set(cache_key, df)
                            except Exception as e:
                                print(f"  [!] Failed to fetch with {self.provider} (using key): {e}")
                                # 报告API使用失败
                                report_api_usage(self.provider, api_key, success=False)
                                # 恢复环境变量
                                if original_key is not None:
                                    os.environ[f"{self.provider.upper()}_API_KEY"] = original_key
                                elif f"{self.provider.upper()}_API_KEY" in os.environ:
                                    del os.environ[f"{self.provider.upper()}_API_KEY"]
                                
                                # 如果指定提供商失败，尝试yfinance作为后备
                                print(f"  [MarketData] Falling back to yfinance for {pack.symbol}...")
                                res = obb.equity.price.historical(symbol=pack.symbol, provider='yfinance')
                                df = res.to_df()
                                # 使用yfinance作为后备缓存
                                fallback_cache_key = f"raw_ohlcv_{pack.symbol}_yfinance"
                                self.cache.set(fallback_cache_key, df)
                else:
                    # 对于yfinance等不需要API密钥的提供商，直接调用
                    try:
                        res = obb.equity.price.historical(symbol=pack.symbol, provider=self.provider)
                        df = res.to_df()
                        self.cache.set(cache_key, df)
                    except Exception as e:
                        print(f"  [!] Failed to fetch with {self.provider}: {e}")
                        # 如果指定提供商失败，尝试yfinance作为后备
                        print(f"  [MarketData] Falling back to yfinance for {pack.symbol}...")
                        res = obb.equity.price.historical(symbol=pack.symbol, provider='yfinance')
                        df = res.to_df()
                        # 使用yfinance作为后备缓存
                        fallback_cache_key = f"raw_ohlcv_{pack.symbol}_yfinance"
                        self.cache.set(fallback_cache_key, df)
            else:
                print(f"  [MarketData] Using cached data for {pack.symbol} ({self.provider}).")
            
            # 标准化清洗
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
            
            # 获取额外的市场相关指标
            try:
                # 获取成交量加权平均价 (VWAP) 如果可用
                cache_key_vwap = f"vwap_{pack.symbol}"
                vwap_data = self.cache.get(cache_key_vwap)
                
                if vwap_data is None:
                    try:
                        vwap_res = obb.technical.vwap(data=df)
                        vwap_df = vwap_res.to_df()
                        if not vwap_df.empty and 'vwap' in vwap_df.columns:
                            # 将VWAP合并到主数据框
                            df = df.join(vwap_df[['vwap']])
                            self.cache.set(cache_key_vwap, vwap_df)
                    except Exception as e:
                        print(f"  [MarketData] VWAP calculation failed: {e}")
                        
            except Exception as e:
                print(f"  [MarketData] Additional market data fetch failed: {e}")
            
            pack.market_data = DataFrameModel.from_df(df)
            return ComponentOutput(success=True, payload=pack)
            
        except Exception as e:
            return ComponentOutput(success=False, error=f"MarketData Error: {str(e)}")

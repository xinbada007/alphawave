from typing import Any, Dict
import pandas as pd
import requests
from alphaflow.core.base import BaseCollector
from alphaflow.utils.cache import DiskCache
from alphaflow.core.schema import AnalysisContext, ComponentOutput, DataFrameModel, ResearchPack
import json
from datetime import datetime


class AllTickCollectorFlexible(BaseCollector):
    """
    AllTick数据收集器 - 灵活版本
    支持多种可能的API端点和数据格式
    API Key: d512a2cb352dfb3b7d10c5ae0fe09b99-c-app
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        self.api_key = config.get('api_key', 'd512a2cb352dfb3b7d10c5ae0fe09b99-c-app') if config else 'd512a2cb352dfb3b7d10c5ae0fe09b99-c-app'
        
        # 尝试多个可能的API端点
        self.possible_base_urls = [
            'https://api.alltickdata.com',
            'https://alltickdata.com/api',
            'https://api.alltick-data.com',
            'https://alltick-data.com/api',
            'https://api.alltick.market',
            'https://api.alltick.finance'
        ]
        
        # 使用配置中指定的URL或第一个可用的URL
        self.base_url = config.get('base_url', self.possible_base_urls[0]) if config else self.possible_base_urls[0]
        self.cache = DiskCache(expiry_seconds=3600 * 2)  # 2小时缓存
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        })

    def _try_different_endpoints(self, endpoint: str, params: Dict = None) -> Dict:
        """尝试多个可能的API端点"""
        # 首先尝试原始端点
        result = self._make_request(self.base_url, endpoint, params)
        if result and "error" not in result:
            return result
            
        # 如果失败，尝试其他可能的基础URL
        for base_url in self.possible_base_urls:
            if base_url != self.base_url:
                result = self._make_request(base_url, endpoint, params)
                if result and "error" not in result:
                    # 更新基础URL以供后续请求使用
                    self.base_url = base_url
                    return result
                    
        return {"error": "所有端点都无法访问"}

    def _make_request(self, base_url: str, endpoint: str, params: Dict = None) -> Dict:
        """执行API请求"""
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  [AllTick] API请求失败 ({url}): {e}")
            return {"error": str(e)}
        except ValueError as e:
            print(f"  [AllTick] JSON解析失败 ({url}): {e}")
            return {"error": str(e)}

    def _find_data_in_response(self, data: Dict, possible_keys: list) -> Any:
        """在响应中查找数据，尝试多个可能的键名"""
        for key in possible_keys:
            if key in data:
                return data[key]
        return None

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        """
        获取AllTick数据
        """
        symbol = context.symbols[0] if context.symbols else "AAPL"
        pack = ResearchPack(symbol=symbol)

        try:
            print(f"  [AllTick] 正在获取 {symbol} 的数据...")
            
            # 1. 获取实时行情数据
            quote_endpoints = [
                "/v1/quote", "/v1/quotes", "/quote", "/price", "/data/quote", 
                f"/ticker/{symbol}", f"/stock/{symbol}/quote"
            ]
            
            quote_data = None
            for endpoint in quote_endpoints:
                if endpoint.startswith('/ticker/') or endpoint.startswith('/stock/'):
                    temp_data = self._try_different_endpoints(endpoint.replace('{symbol}', symbol))
                else:
                    temp_data = self._try_different_endpoints(endpoint, {"symbol": symbol})
                
                if temp_data and "error" not in temp_data:
                    quote_data = temp_data
                    break
            
            if quote_data and "error" not in quote_data:
                pack.market_data = self._process_quote_data(quote_data)
                print(f"  [AllTick] 行情数据获取成功")
            else:
                print(f"  [AllTick] 行情数据获取失败或API不可用")

            # 2. 获取历史数据
            hist_endpoints = [
                "/v1/history", "/history", "/data/history", "/timeseries",
                f"/stock/{symbol}/history", f"/ticker/{symbol}/history"
            ]
            
            hist_data = None
            for endpoint in hist_endpoints:
                if endpoint.startswith('/stock/') or endpoint.startswith('/ticker/'):
                    temp_data = self._try_different_endpoints(endpoint.replace('{symbol}', symbol), {"range": "1M"})
                else:
                    temp_data = self._try_different_endpoints(endpoint, {
                        "symbol": symbol,
                        "range": "1M"  # 1个月数据
                    })
                
                if temp_data and "error" not in temp_data:
                    hist_data = temp_data
                    break
            
            if hist_data and "error" not in hist_data:
                historical_df = self._process_history_data(hist_data)
                if pack.market_data and not historical_df.empty:
                    # 合并历史数据和实时数据
                    current_df = pack.market_data.to_df()
                    combined_df = pd.concat([historical_df, current_df]).drop_duplicates(subset=['date']).sort_values('date')
                    pack.market_data = DataFrameModel.from_df(combined_df)
                elif not historical_df.empty:
                    pack.market_data = DataFrameModel.from_df(historical_df)
                print(f"  [AllTick] 历史数据获取成功")
            else:
                print(f"  [AllTick] 历史数据获取失败或API不可用")

            # 3. 获取公司基本面信息
            profile_endpoints = [
                "/v1/company/profile", "/company/profile", "/profile", "/company",
                f"/stock/{symbol}/profile", f"/ticker/{symbol}/profile"
            ]
            
            profile_data = None
            for endpoint in profile_endpoints:
                if endpoint.startswith('/stock/') or endpoint.startswith('/ticker/'):
                    temp_data = self._try_different_endpoints(endpoint.replace('{symbol}', symbol))
                else:
                    temp_data = self._try_different_endpoints(endpoint, {"symbol": symbol})
                
                if temp_data and "error" not in temp_data:
                    profile_data = temp_data
                    break
            
            if profile_data and "error" not in profile_data:
                pack.fundamentals = self._process_company_profile(profile_data)
                print(f"  [AllTick] 公司信息获取成功")
            else:
                print(f"  [AllTick] 公司信息获取失败或API不可用")

            # 4. 获取新闻资讯
            news_endpoints = [
                "/v1/news", "/news", "/articles", "/data/news",
                f"/stock/{symbol}/news", f"/ticker/{symbol}/news"
            ]
            
            news_data = None
            for endpoint in news_endpoints:
                if endpoint.startswith('/stock/') or endpoint.startswith('/ticker/'):
                    temp_data = self._try_different_endpoints(endpoint.replace('{symbol}', symbol), {"limit": 10})
                else:
                    temp_data = self._try_different_endpoints(endpoint, {
                        "symbol": symbol,
                        "limit": 10
                    })
                
                if temp_data and "error" not in temp_data:
                    news_data = temp_data
                    break
            
            if news_data and "error" not in news_data:
                pack.news = self._process_news_data(news_data)
                print(f"  [AllTick] 新闻数据获取成功")
            else:
                print(f"  [AllTick] 新闻数据获取失败或API不可用")

            # 5. 获取技术指标
            technicals_endpoints = [
                "/v1/technicals", "/technicals", "/technical", "/indicators",
                f"/stock/{symbol}/technicals", f"/ticker/{symbol}/technicals"
            ]
            
            technicals_data = None
            for endpoint in technicals_endpoints:
                if endpoint.startswith('/stock/') or endpoint.startswith('/ticker/'):
                    temp_data = self._try_different_endpoints(endpoint.replace('{symbol}', symbol))
                else:
                    temp_data = self._try_different_endpoints(endpoint, {"symbol": symbol})
                
                if temp_data and "error" not in temp_data:
                    technicals_data = temp_data
                    break
            
            if technicals_data and "error" not in technicals_data:
                pack.technicals = self._process_technicals_data(technicals_data)
                print(f"  [AllTick] 技术指标数据获取成功")
            else:
                print(f"  [AllTick] 技术指标数据获取失败或API不可用")

            return ComponentOutput(success=True, payload=pack)

        except Exception as e:
            print(f"  [AllTick] 数据获取过程中发生错误: {str(e)}")
            return ComponentOutput(success=False, error=str(e))

    def _process_quote_data(self, data: Dict) -> DataFrameModel:
        """处理实时行情数据"""
        try:
            # 尝试多种可能的数据结构
            quote = self._find_data_in_response(data, [
                'quote', 'data', 'result', 'response', 'price', 'ticker'
            ])
            
            if not quote:
                quote = data  # 如果直接就是quote数据
            
            if isinstance(quote, list) and len(quote) > 0:
                quote = quote[0]  # 如果是数组，取第一项
            
            if not isinstance(quote, dict):
                print("  [AllTick] 行情数据格式不正确")
                # 返回空的DataFrame
                df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
                return DataFrameModel.from_df(df)
            
            # 创建标准化的DataFrame
            df_data = {
                'date': [datetime.now().strftime('%Y-%m-%d')],
                'open': [quote.get('open', 
                      quote.get('open_price', 
                      quote.get('openPrice', 
                      quote.get('first', 0))))],
                'high': [quote.get('high', 
                      quote.get('high_price', 
                      quote.get('highPrice', 
                      quote.get('max', 0))))],
                'low': [quote.get('low', 
                     quote.get('low_price', 
                     quote.get('lowPrice', 
                     quote.get('min', 0))))],
                'close': [quote.get('close', 
                       quote.get('close_price', 
                       quote.get('closePrice', 
                       quote.get('last', 
                       quote.get('last_price', 0))))],
                'volume': [quote.get('volume', 
                        quote.get('volume_traded', 
                        quote.get('volumeTraded', 0)))],
                'prev_close': [quote.get('prev_close', 
                            quote.get('previous_close', 
                            quote.get('prevClose', 0)))],
                'change': [quote.get('change', 
                        quote.get('price_change', 
                        quote.get('changeValue', 0)))],
                'change_percent': [quote.get('change_percent', 
                                quote.get('change_percentage', 
                                quote.get('changePercent', 0)))],
                'bid': [quote.get('bid', 
                     quote.get('bid_price', 
                     quote.get('bidPrice', 0)))],
                'ask': [quote.get('ask', 
                     quote.get('ask_price', 
                     quote.get('askPrice', 0)))],
                'market_cap': [quote.get('market_cap', 
                          quote.get('market_capitalization', 
                          quote.get('marketCap', 0)))]
            }
            
            df = pd.DataFrame(df_data)
            # 确保数值列是正确的数据类型
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'prev_close', 
                             'change', 'change_percent', 'bid', 'ask', 'market_cap']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return DataFrameModel.from_df(df)
        except Exception as e:
            print(f"  [AllTick] 处理行情数据时出错: {e}")
            # 返回空的DataFrame
            df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            return DataFrameModel.from_df(df)

    def _process_history_data(self, data: Dict) -> pd.DataFrame:
        """处理历史数据"""
        try:
            # 尝试多种可能的数据结构
            history = self._find_data_in_response(data, [
                'history', 'data', 'result', 'response', 'candles', 'prices', 'time_series'
            ])
            
            if not history:
                print("  [AllTick] 历史数据为空")
                # 返回空DataFrame
                return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            
            if isinstance(history, dict):
                # 如果是字典，可能按日期组织
                if 'Time Series' in str(history) or 'daily' in str(history) or 'weekly' in str(history) or 'monthly' in str(history):
                    # 假设是时间序列格式 { "YYYY-MM-DD": { "open": ..., }, ... }
                    dates = []
                    opens = []
                    highs = []
                    lows = []
                    closes = []
                    volumes = []
                    
                    for date_str, values in history.items():
                        if isinstance(values, dict):
                            dates.append(date_str)
                            opens.append(values.get('1. open', 
                                          values.get('open', 
                                          values.get('open_price', 0))))
                            highs.append(values.get('2. high', 
                                          values.get('high', 
                                          values.get('high_price', 0))))
                            lows.append(values.get('3. low', 
                                         values.get('low', 
                                         values.get('low_price', 0))))
                            closes.append(values.get('4. close', 
                                           values.get('close', 
                                           values.get('close_price', 0))))
                            volumes.append(values.get('5. volume', 
                                            values.get('volume', 
                                            values.get('volume_traded', 0))))
                    
                    df = pd.DataFrame({
                        'date': pd.to_datetime(dates),
                        'open': pd.to_numeric(opens, errors='coerce'),
                        'high': pd.to_numeric(highs, errors='coerce'),
                        'low': pd.to_numeric(lows, errors='coerce'),
                        'close': pd.to_numeric(closes, errors='coerce'),
                        'volume': pd.to_numeric(volumes, errors='coerce')
                    })
                else:
                    # 如果不是时间序列格式，可能是其他结构
                    history = list(history.values()) if isinstance(history, dict) else history
            elif isinstance(history, str):
                # 如果是字符串，可能是错误消息
                print(f"  [AllTick] 历史数据返回字符串: {history}")
                return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            else:
                # 假设是列表
                pass
            
            if isinstance(history, (list, tuple)):
                # 提取历史数据
                dates = []
                opens = []
                highs = []
                lows = []
                closes = []
                volumes = []
                
                for item in history:
                    if isinstance(item, dict):
                        dates.append(item.get('date', 
                                    item.get('timestamp', 
                                    item.get('time', ''))))
                        opens.append(item.get('open', 
                                      item.get('open_price', 
                                      item.get('openPrice', 0))))
                        highs.append(item.get('high', 
                                      item.get('high_price', 
                                      item.get('highPrice', 0))))
                        lows.append(item.get('low', 
                                     item.get('low_price', 
                                     item.get('lowPrice', 0))))
                        closes.append(item.get('close', 
                                       item.get('close_price', 
                                       item.get('closePrice', 0))))
                        volumes.append(item.get('volume', 
                                        item.get('volume_traded', 
                                        item.get('volumeTraded', 0))))
                
                df = pd.DataFrame({
                    'date': pd.to_datetime(dates),
                    'open': pd.to_numeric(opens, errors='coerce'),
                    'high': pd.to_numeric(highs, errors='coerce'),
                    'low': pd.to_numeric(lows, errors='coerce'),
                    'close': pd.to_numeric(closes, errors='coerce'),
                    'volume': pd.to_numeric(volumes, errors='coerce')
                })
            else:
                df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            
            # 删除无效数据行
            df = df.dropna(subset=['open', 'high', 'low', 'close'])
            
            return df
        except Exception as e:
            print(f"  [AllTick] 处理历史数据时出错: {e}")
            return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])

    def _process_company_profile(self, data: Dict) -> Dict:
        """处理公司基本面信息"""
        try:
            # 尝试多种可能的数据结构
            profile = self._find_data_in_response(data, [
                'profile', 'company', 'data', 'result', 'response', 'info'
            ])
            
            if not profile:
                profile = data  # 如果直接就是profile数据
            
            if isinstance(profile, list) and len(profile) > 0:
                profile = profile[0]  # 如果是数组，取第一项
            
            if not isinstance(profile, dict):
                print("  [AllTick] 公司信息格式不正确")
                return {}
            
            fundamentals = {
                'company_name': profile.get('company_name', 
                              profile.get('name', 
                              profile.get('companyName', 
                              profile.get('shortName', '')))),
                'sector': profile.get('sector', 
                        profile.get('sectorName', 
                        profile.get('industry_group', ''))),
                'industry': profile.get('industry', 
                          profile.get('industryName', 
                          profile.get('sub_industry', ''))),
                'market_cap': profile.get('market_cap', 
                            profile.get('market_capitalization', 
                            profile.get('marketCap', 0))),
                'pe_ratio': profile.get('pe_ratio', 
                          profile.get('price_to_earnings', 
                          profile.get('peRatio', 0))),
                'pb_ratio': profile.get('pb_ratio', 
                          profile.get('price_to_book', 
                          profile.get('pbRatio', 0))),
                'dividend_yield': profile.get('dividend_yield', 
                                profile.get('dividend_rate', 
                                profile.get('dividendYield', 0))),
                'eps': profile.get('eps', 
                         profile.get('earnings_per_share', 
                         profile.get('epsTTM', 0))),
                'beta': profile.get('beta', 
                          profile.get('beta_value', 
                          profile.get('beta', 1.0))),
                'employees': profile.get('employees', 
                           profile.get('employee_count', 
                           profile.get('fullTimeEmployees', 0))),
                'hq_location': profile.get('headquarters', 
                             profile.get('headquarters_location', 
                             profile.get('address', ''))),
                'website': profile.get('website', 
                         profile.get('website_url', 
                         profile.get('WebURL', ''))),
                'description': profile.get('description', 
                             profile.get('longBusinessSummary', 
                             profile.get('description', 
                             profile.get('business_summary', ''))))
            }
            
            return fundamentals
        except Exception as e:
            print(f"  [AllTick] 处理公司信息时出错: {e}")
            return {}

    def _process_news_data(self, data: Dict) -> list:
        """处理新闻数据"""
        try:
            # 尝试多种可能的数据结构
            news_items = self._find_data_in_response(data, [
                'news', 'articles', 'items', 'result', 'response', 'data'
            ])
            
            if not news_items:
                news_items = data  # 如果直接就是news数据
                if isinstance(news_items, dict):
                    # 如果整个响应就是一个新闻项
                    if 'title' in news_items or 'headline' in news_items:
                        news_items = [news_items]
            
            if isinstance(news_items, (str, int, float)):
                # 如果是基本类型，说明没有有效数据
                print(f"  [AllTick] 新闻数据格式无效: {type(news_items)}")
                return []
            
            if not isinstance(news_items, list):
                if isinstance(news_items, dict):
                    # 如果是字典，可能按某种键组织
                    if 'hits' in news_items:
                        news_items = news_items['hits']
                    elif 'articles' in news_items:
                        news_items = news_items['articles']
                    elif 'data' in news_items:
                        news_items = news_items['data']
                    else:
                        # 尝试将字典的值作为新闻项
                        news_items = list(news_items.values()) if all(isinstance(v, dict) for v in news_items.values()) else []
                else:
                    print(f"  [AllTick] 新闻数据格式未知: {type(news_items)}")
                    return []
            
            processed_news = []
            for item in news_items:
                if isinstance(item, dict):
                    news_item = {
                        'published_date': item.get('published_at', 
                                     item.get('publishDate', 
                                     item.get('date', 
                                     item.get('pub_date', '')))),
                        'title': item.get('title', 
                                item.get('headline', 
                                item.get('name', ''))),
                        'summary': item.get('summary', 
                                  item.get('description', 
                                  item.get('snippet', 
                                  item.get('content', '')))),
                        'source': item.get('source', 
                                 item.get('publisher', 
                                 item.get('source_name', 'Unknown'))),
                        'url': item.get('url', 
                              item.get('link', 
                              item.get('article_url', ''))),
                        'sentiment_score': item.get('sentiment', {}).get('score', 0) if 'sentiment' in item else item.get('sentiment_score', 0),
                        'relevance_score': item.get('relevance', 0.5),
                        'topics': item.get('topics', 
                                 item.get('categories', 
                                 item.get('tags', [])))
                    }
                    processed_news.append(news_item)
            
            return processed_news[:10]  # 限制返回最多10条新闻
        except Exception as e:
            print(f"  [AllTick] 处理新闻数据时出错: {e}")
            return []

    def _process_technicals_data(self, data: Dict) -> DataFrameModel:
        """处理技术指标数据"""
        try:
            # 尝试多种可能的数据结构
            technicals = self._find_data_in_response(data, [
                'technicals', 'indicators', 'data', 'result', 'response', 'analysis'
            ])
            
            if not technicals:
                technicals = data  # 如果直接就是technicals数据
            
            if isinstance(technicals, list) and len(technicals) > 0:
                technicals = technicals[0]  # 如果是数组，取第一项
            
            if not isinstance(technicals, dict):
                print("  [AllTick] 技术指标数据格式不正确")
                df = pd.DataFrame(columns=['date', 'rsi', 'macd', 'sma_20', 'sma_50'])
                return DataFrameModel.from_df(df)
            
            # 创建技术指标DataFrame
            df_data = {
                'date': [datetime.now().strftime('%Y-%m-%d')],
                'rsi': [technicals.get('rsi', 
                       technicals.get('rsi_value', 
                       technicals.get('RSI', 0)))],
                'macd': [technicals.get('macd', 
                        technicals.get('macd_value', 
                        technicals.get('MACD', 0)))],
                'macd_signal': [technicals.get('macd_signal', 
                              technicals.get('macd_signal_line', 
                              technicals.get('MACD_Signal', 0)))],
                'macd_histogram': [technicals.get('macd_histogram', 
                                 technicals.get('MACD_Histogram', 0))],
                'sma_20': [technicals.get('sma_20', 
                         technicals.get('sma20', 
                         technicals.get('SMA20', 0)))],
                'sma_50': [technicals.get('sma_50', 
                         technicals.get('sma50', 
                         technicals.get('SMA50', 0)))],
                'ema_12': [technicals.get('ema_12', 
                         technicals.get('ema12', 
                         technicals.get('EMA12', 0)))],
                'ema_26': [technicals.get('ema_26', 
                         technicals.get('ema26', 
                         technicals.get('EMA26', 0)))],
                'stoch_k': [technicals.get('stoch_k', 
                          technicals.get('stochastics_k', 
                          technicals.get('STOCH_K', 0)))],
                'stoch_d': [technicals.get('stoch_d', 
                          technicals.get('stochastics_d', 
                          technicals.get('STOCH_D', 0)))],
                'bollinger_upper': [technicals.get('bollinger_upper', 
                                  technicals.get('bb_upper_band', 
                                  technicals.get('BB_Upper', 0)))],
                'bollinger_lower': [technicals.get('bollinger_lower', 
                                  technicals.get('bb_lower_band', 
                                  technicals.get('BB_Lower', 0)))],
                'adx': [technicals.get('adx', 
                       technicals.get('adx_value', 
                       technicals.get('ADX', 0)))],
                'williams_r': [technicals.get('williams_r', 
                             technicals.get('williams_r_value', 
                             technicals.get('WilliamsR', 0)))]
            }
            
            df = pd.DataFrame(df_data)
            # 确保数值列是正确的数据类型
            for col in df.columns:
                if col != 'date':
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return DataFrameModel.from_df(df)
        except Exception as e:
            print(f"  [AllTick] 处理技术指标数据时出错: {e}")
            df = pd.DataFrame(columns=['date', 'rsi', 'macd', 'sma_20', 'sma_50'])
            return DataFrameModel.from_df(df)


# 便捷函数，用于快速创建AllTick收集器
def create_alltick_collector(api_key: str = 'd512a2cb352dfb3b7d10c5ae0fe09b99-c-app', 
                           base_url: str = 'https://api.alltickdata.com') -> AllTickCollectorFlexible:
    """
    创建AllTick数据收集器的便捷函数
    """
    config = {
        'api_key': api_key,
        'base_url': base_url
    }
    return AllTickCollectorFlexible(name="AllTickCollector", config=config)
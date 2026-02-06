from typing import Any, Dict
import pandas as pd
import requests
from alphaflow.core.base import BaseCollector
from alphaflow.utils.cache import DiskCache
from alphaflow.core.schema import AnalysisContext, ComponentOutput, DataFrameModel, ResearchPack
import json
from datetime import datetime


class AllTickCollector(BaseCollector):
    """
    AllTick数据收集器
    API Key: d512a2cb352dfb3b7d10c5ae0fe09b99-c-app
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        super().__init__(name, config)
        self.api_key = config.get('api_key', 'd512a2cb352dfb3b7d10c5ae0fe09b99-c-app') if config else 'd512a2cb352dfb3b7d10c5ae0fe09b99-c-app'
        self.base_url = config.get('base_url', 'https://api.alltickdata.com') if config else 'https://api.alltickdata.com'
        self.cache = DiskCache(expiry_seconds=3600 * 2)  # 2小时缓存
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        })

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """执行API请求"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  [AllTick] API请求失败: {e}")
            return {"error": str(e)}
        except ValueError as e:
            print(f"  [AllTick] JSON解析失败: {e}")
            return {"error": str(e)}

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        """
        获取AllTick数据
        """
        symbol = context.symbols[0] if context.symbols else "AAPL"
        pack = ResearchPack(symbol=symbol)

        try:
            print(f"  [AllTick] 正在获取 {symbol} 的数据...")
            
            # 1. 获取实时行情数据
            quote_data = self._make_request("/v1/quote", {"symbol": symbol})
            if "error" not in quote_data:
                pack.market_data = self._process_quote_data(quote_data)
                print(f"  [AllTick] 行情数据获取成功")
            else:
                print(f"  [AllTick] 行情数据获取失败: {quote_data['error']}")

            # 2. 获取历史数据
            hist_data = self._make_request("/v1/history", {
                "symbol": symbol,
                "range": "1M"  # 1个月数据
            })
            if "error" not in hist_data:
                historical_df = self._process_history_data(hist_data)
                if pack.market_data:
                    # 合并历史数据和实时数据
                    current_df = pack.market_data.to_df()
                    combined_df = pd.concat([historical_df, current_df]).drop_duplicates(subset=['date']).sort_values('date')
                    pack.market_data = DataFrameModel.from_df(combined_df)
                else:
                    pack.market_data = DataFrameModel.from_df(historical_df)
                print(f"  [AllTick] 历史数据获取成功")
            else:
                print(f"  [AllTick] 历史数据获取失败: {hist_data['error']}")

            # 3. 获取公司基本面信息
            profile_data = self._make_request("/v1/company/profile", {"symbol": symbol})
            if "error" not in profile_data:
                pack.fundamentals = self._process_company_profile(profile_data)
                print(f"  [AllTick] 公司信息获取成功")
            else:
                print(f"  [AllTick] 公司信息获取失败: {profile_data['error']}")

            # 4. 获取新闻资讯
            news_data = self._make_request("/v1/news", {
                "symbol": symbol,
                "limit": 10
            })
            if "error" not in news_data:
                pack.news = self._process_news_data(news_data)
                print(f"  [AllTick] 新闻数据获取成功")
            else:
                print(f"  [AllTick] 新闻数据获取失败: {news_data['error']}")

            # 5. 获取技术指标
            technicals_data = self._make_request("/v1/technicals", {"symbol": symbol})
            if "error" not in technicals_data:
                pack.technicals = self._process_technicals_data(technicals_data)
                print(f"  [AllTick] 技术指标数据获取成功")
            else:
                print(f"  [AllTick] 技术指标数据获取失败: {technicals_data['error']}")

            return ComponentOutput(success=True, payload=pack)

        except Exception as e:
            print(f"  [AllTick] 数据获取过程中发生错误: {str(e)}")
            return ComponentOutput(success=False, error=str(e))

    def _process_quote_data(self, data: Dict) -> DataFrameModel:
        """处理实时行情数据"""
        try:
            quote = data.get('quote', {})
            if not quote:
                # 如果API结构不同，尝试其他可能的字段
                quote = data
            
            # 创建标准化的DataFrame
            df_data = {
                'date': [datetime.now().strftime('%Y-%m-%d')],
                'open': [quote.get('open', quote.get('open_price', 0))],
                'high': [quote.get('high', quote.get('high_price', 0))],
                'low': [quote.get('low', quote.get('low_price', 0))],
                'close': [quote.get('close', quote.get('last_price', 0))],
                'volume': [quote.get('volume', quote.get('volume_traded', 0))],
                'prev_close': [quote.get('prev_close', quote.get('previous_close', 0))],
                'change': [quote.get('change', quote.get('price_change', 0))],
                'change_percent': [quote.get('change_percent', quote.get('change_percentage', 0))],
                'bid': [quote.get('bid', quote.get('bid_price', 0))],
                'ask': [quote.get('ask', quote.get('ask_price', 0))],
                'market_cap': [quote.get('market_cap', quote.get('market_capitalization', 0))]
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
            # 假设历史数据在data['history']中，如果不是则调整
            history = data.get('history', [])
            if not history and isinstance(data, list):
                history = data
            elif not history:
                # 尝试其他可能的字段名
                for key in ['data', 'results', 'candles', 'prices']:
                    if key in data:
                        history = data[key]
                        break
            
            if not history:
                print("  [AllTick] 历史数据为空")
                # 返回空DataFrame
                return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
            
            # 提取历史数据
            dates = []
            opens = []
            highs = []
            lows = []
            closes = []
            volumes = []
            
            for item in history:
                if isinstance(item, dict):
                    dates.append(item.get('date', item.get('timestamp', '')))
                    opens.append(item.get('open', item.get('open_price', 0)))
                    highs.append(item.get('high', item.get('high_price', 0)))
                    lows.append(item.get('low', item.get('low_price', 0)))
                    closes.append(item.get('close', item.get('close_price', 0)))
                    volumes.append(item.get('volume', item.get('volume_traded', 0)))
            
            df = pd.DataFrame({
                'date': pd.to_datetime(dates),
                'open': pd.to_numeric(opens, errors='coerce'),
                'high': pd.to_numeric(highs, errors='coerce'),
                'low': pd.to_numeric(lows, errors='coerce'),
                'close': pd.to_numeric(closes, errors='coerce'),
                'volume': pd.to_numeric(volumes, errors='coerce')
            })
            
            # 删除无效数据行
            df = df.dropna(subset=['open', 'high', 'low', 'close'])
            
            return df
        except Exception as e:
            print(f"  [AllTick] 处理历史数据时出错: {e}")
            return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])

    def _process_company_profile(self, data: Dict) -> Dict:
        """处理公司基本面信息"""
        try:
            profile = data.get('profile', {})
            if not profile:
                profile = data  # 如果直接就是profile数据
            
            fundamentals = {
                'company_name': profile.get('company_name', profile.get('name', '')),
                'sector': profile.get('sector', profile.get('industry_group', '')),
                'industry': profile.get('industry', profile.get('sub_industry', '')),
                'market_cap': profile.get('market_cap', profile.get('market_capitalization', 0)),
                'pe_ratio': profile.get('pe_ratio', profile.get('price_to_earnings', 0)),
                'pb_ratio': profile.get('pb_ratio', profile.get('price_to_book', 0)),
                'dividend_yield': profile.get('dividend_yield', profile.get('dividend_rate', 0)),
                'eps': profile.get('eps', profile.get('earnings_per_share', 0)),
                'beta': profile.get('beta', profile.get('beta_value', 1.0)),
                'employees': profile.get('employees', profile.get('employee_count', 0)),
                'hq_location': profile.get('headquarters', profile.get('headquarters_location', '')),
                'website': profile.get('website', ''),
                'description': profile.get('description', profile.get('business_summary', ''))
            }
            
            return fundamentals
        except Exception as e:
            print(f"  [AllTick] 处理公司信息时出错: {e}")
            return {}

    def _process_news_data(self, data: Dict) -> list:
        """处理新闻数据"""
        try:
            news_items = data.get('news', [])
            if not news_items and isinstance(data, list):
                news_items = data
            elif not news_items:
                # 尝试其他可能的字段名
                for key in ['articles', 'items', 'results']:
                    if key in data:
                        news_items = data[key]
                        break
            
            processed_news = []
            for item in news_items:
                if isinstance(item, dict):
                    news_item = {
                        'published_date': item.get('published_at', item.get('date', '')),
                        'title': item.get('title', ''),
                        'summary': item.get('summary', item.get('description', item.get('snippet', ''))),
                        'source': item.get('source', item.get('publisher', 'Unknown')),
                        'url': item.get('url', item.get('link', '')),
                        'sentiment_score': item.get('sentiment', {}).get('score', 0) if 'sentiment' in item else 0,
                        'relevance_score': item.get('relevance', 0.5),
                        'topics': item.get('topics', item.get('categories', []))
                    }
                    processed_news.append(news_item)
            
            return processed_news[:10]  # 限制返回最多10条新闻
        except Exception as e:
            print(f"  [AllTick] 处理新闻数据时出错: {e}")
            return []

    def _process_technicals_data(self, data: Dict) -> DataFrameModel:
        """处理技术指标数据"""
        try:
            technicals = data.get('technicals', {})
            if not technicals:
                technicals = data  # 如果直接就是technicals数据
            
            # 创建技术指标DataFrame
            df_data = {
                'date': [datetime.now().strftime('%Y-%m-%d')],
                'rsi': [technicals.get('rsi', technicals.get('rsi_14', 0))],
                'macd': [technicals.get('macd', 0)],
                'macd_signal': [technicals.get('macd_signal', 0)],
                'macd_histogram': [technicals.get('macd_histogram', 0)],
                'sma_20': [technicals.get('sma_20', 0)],
                'sma_50': [technicals.get('sma_50', 0)],
                'ema_12': [technicals.get('ema_12', 0)],
                'ema_26': [technicals.get('ema_26', 0)],
                'stoch_k': [technicals.get('stoch_k', 0)],
                'stoch_d': [technicals.get('stoch_d', 0)],
                'bollinger_upper': [technicals.get('bollinger_upper', 0)],
                'bollinger_lower': [technicals.get('bollinger_lower', 0)],
                'adx': [technicals.get('adx', 0)],
                'williams_r': [technicals.get('williams_r', 0)]
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
                           base_url: str = 'https://api.alltickdata.com') -> AllTickCollector:
    """
    创建AllTick数据收集器的便捷函数
    """
    config = {
        'api_key': api_key,
        'base_url': base_url
    }
    return AllTickCollector(name="AllTickCollector", config=config)
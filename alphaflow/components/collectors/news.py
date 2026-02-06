from typing import Any, Dict
from openbb import obb
from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack

class NewsCollector(BaseCollector):
    """
    【消息面采集器】
    职责：聚合新闻、公告、社交媒体情绪。
    Vibe Coding 特性：高扩展性，支持接入多源爬虫。
    """
    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        input_data = kwargs.get('input_data')
        pack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data
        
        if pack is None:
            pack = ResearchPack(symbol=context.symbols[0])

        try:
            if hasattr(obb, 'news'):
                print(f"  [News] Fetching latest headlines for {pack.symbol}...")
                news_res = obb.news.company(symbol=pack.symbol, provider="yfinance")
                news_df = news_res.to_df()
                pack.news = news_df.head(5).to_dict(orient='records')
            else:
                # Vibe Coding 预留位置：此处未来可以替换为 Selenium 或 BeautifulSoup 爬虫
                pack.extra["news_status"] = "OpenBB News module not found"
            
            return ComponentOutput(success=True, payload=pack)
        except Exception as e:
            print(f"  [!] News Data skipped: {e}")
            return ComponentOutput(success=True, payload=pack)

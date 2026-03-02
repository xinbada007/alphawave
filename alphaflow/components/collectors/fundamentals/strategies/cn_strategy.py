"""
CN Market Strategy - A股市场策略
A股：使用 AkShare 获取基本面数据
"""
from typing import Dict, List

from .base import BaseMarketStrategy
from ..fetchers.akshare_cn_fetcher import AkShareCNFetcher


class CNMarketStrategy(BaseMarketStrategy):
    """A股基本面策略：使用 AkShareCNFetcher"""
    
    def __init__(self):
        self.ak = AkShareCNFetcher()
    
    def build_routing_table(self) -> Dict[str, List]:
        """
        A股路由表
        
        定义任务到 fetcher 的映射
        """
        return {
            "financial_indicator": [self.ak],
            "company_info": [self.ak],
            "main_bt": [self.ak],
        }
    
    async def fetch(self, task_name: str, symbol: str, **kwargs) -> List[Dict]:
        """
        A股基本面数据获取
        """
        print(f"  [CN] Fetching {symbol} via AkShareCNFetcher for task: {task_name}")
        
        try:
            result = await self.ak.fetch(task_name, symbol, **kwargs)
            if result:
                print(f"  [CN] Successfully fetched {len(result)} records")
                return result
            else:
                print(f"  [CN] No data returned for {task_name}")
                return []
        except Exception as e:
            print(f"  [CN] Fetch failed: {e}")
            return []

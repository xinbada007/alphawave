"""
AkShare CN Fetcher - 纯 AkShare A股抓取器
负责 A 股的财务数据抓取 (占位，后续实现)
"""
from typing import List, Dict, Any

from .base import BaseFetcher


class AkShareCNFetcher(BaseFetcher):
    """纯 AkShare A股抓取器 - 占位实现，后续添加业务"""
    
    name = "AkShareCN"
    
    async def fetch(self, task_name: str, symbol: str, **kwargs) -> List[Dict]:
        """任务翻译官：A 股抓取器待实现"""
        raise NotImplementedError(f"{self.name} is not implemented yet")

"""
Base Fetcher - 原子数据抓取器基类
所有 Fetcher 必须继承此类，实现纯化的抓取逻辑（无 fallback）
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseFetcher(ABC):
    """原子抓取器基类：只负责抓取，失败抛异常"""
    
    name: str = "BaseFetcher"  # 类属性，用于日志追踪
    
    @abstractmethod
    async def fetch(self, task_name: str, symbol: str, **kwargs) -> List[Dict]:
        """
        原子抓取接口
        
        Args:
            task_name: 标准任务名 (如 "a_income", "splits", "major_holders")
            symbol: 股票代码
            **kwargs: 额外参数 (如 limit_a, limit_q)
            
        Returns:
            抓取的数据列表，失败时抛出异常
            
        Raises:
            Exception: 抓取失败时抛出异常，由上层 Strategy 捕获并尝试下一个 Fetcher
        """
        pass

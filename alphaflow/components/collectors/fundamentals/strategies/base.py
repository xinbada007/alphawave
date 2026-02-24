"""
Base Market Strategy - 市场策略基类
实现基于任务的并发与兜底责任链
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Tuple

from ..fetchers.base import BaseFetcher


class BaseMarketStrategy(ABC):
    """市场策略基类：实现基于任务的并发与兜底责任链"""
    
    @abstractmethod
    def build_routing_table(self) -> Dict[str, List[BaseFetcher]]:
        """
        子类必须实现此方法，返回声明式路由表
        
        格式: {"任务名": [首选Fetcher, 备用Fetcher1, 备用Fetcher2]}
        
        Example:
            return {
                "splits": [self.obb_fmp, self.native_yf],  # OBB 失败 -> 原生 YF
                "major_holders": [self.obb_yf, self.native_yf],
            }
        """
        pass
    
    async def execute(
        self, 
        symbol: str, 
        tasks: List[str], 
        **kwargs
    ) -> Dict[str, List[Dict]]:
        """
        执行策略：Task 级别全并发 + 责任链兜底
        
        Args:
            symbol: 股票代码
            tasks: 需要抓取的任务列表
            **kwargs: 额外参数 (limit_a, limit_q 等)
            
        Returns:
            Dict[str, List[Dict]]: {task_name: data_list}
        """
        routing_table = self.build_routing_table()
        
        async def execute_task_with_fallback(task_name: str) -> Tuple[str, List[Dict]]:
            """单个任务的责任链执行逻辑"""
            fetchers = routing_table.get(task_name, [])
            
            if not fetchers:
                # 没有配置 Fetcher，返回空
                return task_name, []
            
            # 遍历责任链 (Fallback 机制)
            for fetcher in fetchers:
                try:
                    # 尝试用当前 Fetcher 抓取
                    data = await fetcher.fetch(task_name, symbol, **kwargs)
                    if data:  # 抓到数据，立刻返回，中断责任链
                        return task_name, data
                except Exception as e:
                    # 打印结构化日志：谁失败了什么，错误原因
                    err_msg = str(e)[:80]  # 截断过长错误信息
                    print(f"  [Fallback ⚠️] {fetcher.name} -> {task_name} failed: {err_msg}")
                    continue
            
            # 如果整条责任链都失败了，返回空列表
            return task_name, []
        
        # 所有任务完全并行化执行！
        results = await asyncio.gather(*[execute_task_with_fallback(t) for t in tasks])
        return dict(results)

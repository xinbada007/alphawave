"""
Market Data Collector - 调度枢纽
负责根据 Symbol 路由到对应的市场策略
"""
from typing import Any, Dict, Optional
import pandas as pd

from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import (
    AnalysisContext, 
    ComponentOutput, 
    ResearchPack, 
    DataFrameModel
)
from alphaflow.core.utils import get_market_type, MarketType

from .strategies.us_strategy import USMarketStrategy
from .strategies.hk_strategy import HKMarketStrategy
from .strategies.cn_strategy import CNMarketStrategy

class MarketDataCollector(BaseCollector):
    """市场数据采集器 - 调度中心"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        # 初始化策略池
        self.strategies = {
            MarketType.US: USMarketStrategy(config),
            MarketType.HK: HKMarketStrategy(),
            MarketType.CN: CNMarketStrategy(),
        }

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        """执行抓取流程"""
        # 1. 标准解包
        pack = self._unpack_pack(context, kwargs)

        symbol = pack.symbol
        target_days = context.metadata.get("days", 250)
        market_type = get_market_type(symbol)
        
        # 2. 策略路由
        strategy = self.strategies.get(market_type, self.strategies[MarketType.US])
        
        print(f"  [MarketData] Fetching {symbol} via {market_type.name} strategy...")

        # 3. 调度执行 (Price 与 Metrics 双链并发获取)
        price_df, market_metrics, used_provider = await strategy.execute(symbol, target_days)

        # 4. 结果组装
        if not price_df.empty:
            # 截取目标长度
            price_df = price_df.sort_index(ascending=True).tail(target_days)
            
            # 封装 DataFrame
            pack.market_data = DataFrameModel.from_df(price_df)
            
            # 封装 Metrics
            if market_metrics:
                pack.market_metrics = market_metrics
                print(f"  [MarketData] Metrics captured: {len(market_metrics)} fields")
                
            # 记录元数据
            pack.market_data_meta = {
                "price_source": used_provider,
                "columns": price_df.columns.tolist()
            }
            
            print(f"  [MarketData] Success via {used_provider} ({len(price_df)} bars)")
            return ComponentOutput(success=True, payload=pack)

        return ComponentOutput(
            success=False,
            error=f"Failed to fetch market data for {symbol} (Strategy: {market_type.name})",
            payload=pack,
        )

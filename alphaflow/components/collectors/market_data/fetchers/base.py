"""
Market Data Fetcher Base - 市场数据抓取器基类
=============================================
提供价格行情和估值指标的通用抓取能力
"""
import asyncio
from abc import ABC, abstractmethod
from typing import ClassVar, Dict, Any, List, Optional, Sequence
import pandas as pd
import akshare as ak  # type: ignore

from alphaflow.core.acl.core_adapter import DynamicFinancialAdapter
from alphaflow.core.utils import (
    normalize_date_column,
    coerce_numeric_columns,
)
from .enrichers import DEFAULT_ENRICHERS, DerivedColumnEnricher


# ==========================================
# 辅助函数：AkShare 安全调用
# ==========================================
async def _safe_akshare_call(func, **kwargs) -> pd.DataFrame:
    """带重试和异常捕获的 AkShare 调用封装"""
    try:
        df = await asyncio.to_thread(func, **kwargs)
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception as e:
        print(f"  [AkShare] {func.__name__} failed: {e}")
        return pd.DataFrame()


class BaseMarketFetcher(ABC):
    """
    市场数据抓取器基类
    
    职责：
    - fetch_price(): 获取 OHLCV 时间序列
    - fetch_metrics(): 获取估值指标快照
    - _clean_dataframe(): 通用清洗 (rename / type / date / 派生列)
    """
    
    name: str = "BaseMarketFetcher"

    #: 派生列计算器注册表 (类级，子类可覆写以追加/替换)。
    #: 使用元组以防运行时意外变异；扩展请定义新的 ClassVar 元组而非 .append()。
    enrichers: ClassVar[Sequence[DerivedColumnEnricher]] = DEFAULT_ENRICHERS
    
    def __init__(self):
        """初始化 - 子类应设置 adapter"""
        self.adapter: Optional[DynamicFinancialAdapter] = None
    
    @abstractmethod
    async def fetch_price(self, symbol: str, days: int) -> pd.DataFrame:
        """获取价格行情 (OHLCV)"""
        pass
    
    @abstractmethod
    async def fetch_metrics(self, symbol: str) -> Dict[str, Any]:
        """获取估值指标快照"""
        pass
    
    def _clean_dataframe(self, df: pd.DataFrame, rename_map: Dict[str, str]) -> pd.DataFrame:
        """
        清洗 DataFrame：rename → date 归一 → numeric (NaN→0.0) → enrichers
        
        注意：market 业务允许 NaN 数值列回填 0.0（与历史行为兼容）；
        如需保留 NaN 语义，请使用 `BaseBenchmarkFetcher._clean_index_df` 形态。
        """
        if df is None or df.empty:
            return df if df is not None else pd.DataFrame()
        
        if rename_map:
            df = df.rename(columns=rename_map)
        
        df = normalize_date_column(df)
        df = coerce_numeric_columns(
            df,
            columns=("open", "high", "low", "close", "volume"),
            fill_na=0.0,
        )
        
        # 派生列计算 (策略模式：表驱动，开闭原则)
        df = self._apply_enrichers(df)
        
        return df

    def _apply_enrichers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        应用注册的派生列计算器。
        
        子类可覆写本方法以完全定制派生流程；多数情况下应通过覆写
        类变量 `enrichers` (ClassVar 元组) 来追加/替换计算器。
        
        Args:
            df: 已完成 rename/type 清洗的 DataFrame
            
        Returns:
            追加了派生列的 DataFrame
        """
        for enricher in self.enrichers:
            if enricher.can_apply(df):
                df = enricher.apply(df)
        return df
    
    def _map_standard_metrics(self, data: Dict[str, Any], provider_id: str = "unknown") -> Dict[str, Any]:
        """
        通用工具：使用 Core 层的全局 Adapter 进行极速清洗，消灭重复字典
        
        Args:
            data: 原始数据字典
            provider_id: Provider 标识符 ("obb" 或 "akshare")
            
        Returns:
            标准化后的数据字典
        """
        if provider_id == "unknown" or not data:
            return data
        
        adapter = DynamicFinancialAdapter(provider_id=provider_id)
        # 市场快照属于估值指标上下文，调用 normalize 时传入 task_name="metrics"
        cleaned_list = adapter.normalize([data], task_name="metrics")
        
        return cleaned_list[0] if cleaned_list else {}

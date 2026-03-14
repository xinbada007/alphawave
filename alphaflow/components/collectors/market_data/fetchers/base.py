"""
Market Data Fetcher Base - 市场数据抓取器基类
=============================================
提供价格行情和估值指标的通用抓取能力
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import pandas as pd
import akshare as ak  # type: ignore

from alphaflow.core.acl.core_adapter import DynamicFinancialAdapter


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
    """
    
    name: str = "BaseMarketFetcher"
    
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
        清洗 DataFrame
        
        Args:
            df: 原始 DataFrame
            rename_map: 列名重命名映射
            
        Returns:
            清洗后的 DataFrame
        """
        if df.empty:
            return df
        
        # 重命名
        if rename_map:
            df = df.rename(columns=rename_map)
        
        # 统一 date 列
        if "date" not in df.columns:
            for c in ["Date", "DATE", "时间", "日期"]:
                if c in df.columns:
                    df = df.rename(columns={c: "date"})
                    break
        
        # 确保 date 是 datetime
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        
        # 删除空行
        df = df.dropna(subset=["date"])
        
        # 数值清洗
        numeric_cols = ["open", "high", "low", "close", "volume"]
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
        
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

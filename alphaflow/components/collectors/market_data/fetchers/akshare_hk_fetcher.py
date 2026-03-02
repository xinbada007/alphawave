"""
AkShare HK Fetcher - 港股专用抓取器
"""
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
from typing import Dict, Any

from .base import BaseMarketFetcher, _safe_akshare_call


class AkShareHKFetcher(BaseMarketFetcher):
    """港股专用抓取器"""
    
    name = "AkShare_HK"

    def _normalize_code(self, symbol: str) -> str:
        """标准化港股代码为5位数字格式"""
        # 00700.HK -> 00700
        code = symbol.split(".")[0]
        # 确保5位数字
        return code.zfill(5)

    async def fetch_price(self, symbol: str, days: int) -> pd.DataFrame:
        code = self._normalize_code(symbol)
        
        try:
            df = await _safe_akshare_call(
                ak.stock_hk_daily,
                symbol=code
            )
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            # 过滤到目标天数
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                cutoff = datetime.now() - timedelta(days=days*1.5)
                df = df[df['date'] >= cutoff]
            
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    return pd.DataFrame()
            
            return df[required_cols].dropna()
            
        except Exception as e:
            print(f"  [{self.name}] fetch_price failed for {symbol}: {e}")
            return pd.DataFrame()

    async def fetch_metrics(self, symbol: str) -> Dict[str, Any]:
        code = self._normalize_code(symbol)
        
        try:
            m_df = await _safe_akshare_call(
                ak.stock_hk_financial_indicator_em,
                symbol=code
            )
            
            if m_df is None or m_df.empty:
                return {}
            
            raw_dict = {str(k).strip(): v for k, v in m_df.iloc[0].to_dict().items()}
            metrics = self._map_standard_metrics(raw_dict)
            metrics["_source"] = "akshare"
            metrics["_market_type"] = "hk"
            return metrics
            
        except Exception as e:
            print(f"  [{self.name}] fetch_metrics failed for {symbol}: {e}")
            return {}

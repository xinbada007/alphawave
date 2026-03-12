"""
AkShare HK Fetcher - 港股专用抓取器
职责：处理 .HK 代码，清洗港股特有的字段
注意：百分比归一化已迁移至映射层 (metrics.py)，Fetcher 只负责数据搬运
"""
import pandas as pd
import akshare as ak # type: ignore
from datetime import datetime
from typing import Dict, Any

from .base import BaseMarketFetcher, _safe_akshare_call

class AkShareHKFetcher(BaseMarketFetcher):
    """港股专用抓取器"""
    
    name = "AkShare_HK"

    async def fetch_price(self, symbol: str, days: int) -> pd.DataFrame:
        # 脏活1：处理代码格式 (00700.HK -> 00700)
        code = symbol.split(".")[0].zfill(5)
        start_date = (datetime.now() - pd.Timedelta(days=int(days * 1.8))).strftime("%Y%m%d")
        
        try:
            # 港股行情接口 (带重试)
            df = await _safe_akshare_call(
                ak.stock_hk_hist,
                symbol=code,
                period="daily",
                start_date=start_date,
                adjust="qfq"
            )
            
            # 脏活2：中文列名映射
            rename_map = {
                "日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close",
                "成交量": "volume", "成交额": "amount", "换手率": "turnover_rate",
                "振幅": "amplitude", "涨跌幅": "pct_change", "涨跌额": "change_amount",
            }
            
            return self._clean_dataframe(df, rename_map)
            
        except Exception as e:
            # 记录日志但不崩溃，交给责任链
            print(f"  [{self.name}] fetch_price failed for {symbol}: {e}")
            return pd.DataFrame()

    async def fetch_metrics(self, symbol: str) -> Dict[str, Any]:
        code = symbol.split(".")[0].zfill(5)

        try:
            # 港股指标接口 (带重试)
            m_df = await _safe_akshare_call(
                ak.stock_hk_financial_indicator_em,
                symbol=code
            )

            if m_df is None or m_df.empty:
                return {}

            raw_dict = {str(k).strip(): v for k, v in m_df.iloc[0].to_dict().items()}

            # 字段映射 - 百分比归一化由映射层 (metrics.py) 的 transform 处理
            metrics = self._map_standard_metrics(raw_dict, provider_id="akshare")

            metrics["_source"] = "akshare"
            metrics["_market_type"] = "hk"
            return metrics

        except Exception as e:
            print(f"  [{self.name}] fetch_metrics failed for {symbol}: {e}")
            return {}

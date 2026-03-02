"""
AkShare CN Fetcher - A股专用抓取器
职责：处理 A 股代码，清洗 A 股特有字段
"""
import pandas as pd
import akshare as ak # type: ignore
from datetime import datetime
from typing import Dict, Any

from .base import BaseMarketFetcher, _safe_akshare_call

class AkShareCNFetcher(BaseMarketFetcher):
    """A股专用抓取器"""
    
    name = "AkShare_CN"

    async def fetch_price(self, symbol: str, days: int) -> pd.DataFrame:
        # 脏活1：处理代码格式 (600519.SH -> sh600519, 000001.SZ -> sz000001)
        code = symbol.split(".")[0]
        # 添加市场前缀: 6开头=sh, 0/3开头=sz
        if code.startswith("6"):
            market_prefix = "sh"
        else:
            market_prefix = "sz"
        tx_symbol = f"{market_prefix}{code}"
        
        start_date = (datetime.now() - pd.Timedelta(days=int(days * 1.8))).strftime("%Y%m%d")
        end_date = datetime.now().strftime("%Y%m%d")
        
        try:
            # A股行情接口 - 使用腾讯接口 (stock_zh_a_hist_tx)
            # 注意：参数不同，无 period 参数
            df = await _safe_akshare_call(
                ak.stock_zh_a_hist_tx,
                symbol=tx_symbol,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            
            # 脏活2：中文列名映射 (A股与港股基本一致，共用映射)
            rename_map = {
                "日期": "date", "开盘": "open", "最高": "high", "最低": "low", "收盘": "close",
                "成交量": "volume", "成交额": "amount", "换手率": "turnover_rate",
                "振幅": "amplitude", "涨跌幅": "pct_change", "涨跌额": "change_amount",
            }
            
            return self._clean_dataframe(df, rename_map)
            
        except Exception as e:
            print(f"  [{self.name}] fetch_price failed for {symbol}: {e}")
            return pd.DataFrame()

    async def fetch_metrics(self, symbol: str) -> Dict[str, Any]:
        """A股暂无稳定的免费实时指标接口，返回空字典"""
        # 策略层会 Fallback 到 OpenBB/YFinance
        return {}

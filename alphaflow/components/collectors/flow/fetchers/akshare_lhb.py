"""
AkShareLHBFetcher — A 股龙虎榜明细（stock_lhb_detail_em）
=========================================================
按 symbol 过滤近期上榜记录。

接口签名（akshare）：`stock_lhb_detail_em(start_date='YYYYMMDD', end_date='YYYYMMDD')`
列含「序号, 代码, 名称, 上榜日, 解读, ..., 龙虎榜净买额, 龙虎榜买入额, 龙虎榜卖出额, ...」。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pandas as pd

try:
    import akshare as ak  # type: ignore
except ImportError:  # pragma: no cover
    ak = None  # type: ignore

from .base import BaseFlowFetcher


class AkShareLHBFetcher(BaseFlowFetcher):
    name = "AkShare_LHB"
    source_key = "lhb"

    DEFAULT_LOOKBACK_DAYS = 30

    async def fetch(self, symbol: str, days: int) -> pd.DataFrame:
        if ak is None:
            return pd.DataFrame()

        code = symbol.split(".")[0]
        end = datetime.now()
        start = end - timedelta(days=self.DEFAULT_LOOKBACK_DAYS * 2)

        try:
            df = await asyncio.to_thread(
                ak.stock_lhb_detail_em,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
        except Exception as e:
            print(f"  [{self.name}] fetch failed: {str(e)[:80]}")
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        if "代码" in df.columns:
            df = df[df["代码"].astype(str).str.zfill(6) == code]
        if df.empty:
            return pd.DataFrame()

        rename_map = {
            "上榜日":           "date",
            "代码":             "symbol",
            "名称":             "name",
            "解读":             "reason",
            "收盘价":           "close",
            "涨跌幅":           "pct_change",
            "龙虎榜净买额":     "net_buy",
            "龙虎榜买入额":     "buy_amount",
            "龙虎榜卖出额":     "sell_amount",
            "龙虎榜成交额":     "lhb_value",
            "市场总成交额":     "market_value",
            "净买额占总成交比": "net_buy_to_market_pct",
            "成交额占总成交比": "lhb_to_market_pct",
            "换手率":           "turnover_rate",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        df = self._ensure_date_col(df)
        for c in ("close", "pct_change", "net_buy", "buy_amount", "sell_amount",
                  "lhb_value", "market_value", "net_buy_to_market_pct",
                  "lhb_to_market_pct", "turnover_rate"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        return df.sort_values("date", kind="mergesort").reset_index(drop=True)

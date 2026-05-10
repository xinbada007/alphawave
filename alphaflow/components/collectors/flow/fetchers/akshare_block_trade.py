"""
AkShareBlockTradeFetcher — A 股大宗交易（stock_dzjy_mrtj）
============================================================
按 symbol 在历史窗口内逐日抓取并过滤。
Akshare 接口签名 `stock_dzjy_mrtj(start_date='YYYYMMDD', end_date='YYYYMMDD')` 返回
当日全市场大宗汇总（4000+ 行/日）；按"证券代码"过滤到目标股。

设计取舍：第一版只取近 ~30 个工作日（足够判 rolling_10d）。
失败任意一日 → 跳过，不阻塞其他日。
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import List

import pandas as pd

try:
    import akshare as ak  # type: ignore
except ImportError:  # pragma: no cover
    ak = None  # type: ignore

from .base import BaseFlowFetcher


class AkShareBlockTradeFetcher(BaseFlowFetcher):
    name = "AkShare_BlockTrade"
    source_key = "block_trade"

    # 为减少接口调用次数，抓取 lookback_days 个工作日；profiler rolling 默认看 10 天
    DEFAULT_LOOKBACK_DAYS = 30

    async def fetch(self, symbol: str, days: int) -> pd.DataFrame:
        if ak is None:
            return pd.DataFrame()

        # symbol 从 "600519.SH" → "600519"（akshare 大宗交易接口用 6 位代码）
        code = symbol.split(".")[0]

        # 限制抓取窗口（与 days 无关，固定 lookback 防止超时）
        end = datetime.now()
        start = end - timedelta(days=self.DEFAULT_LOOKBACK_DAYS * 2)  # 含周末

        try:
            df = await asyncio.to_thread(
                ak.stock_dzjy_mrtj,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
        except Exception as e:
            print(f"  [{self.name}] fetch failed: {str(e)[:80]}")
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        # 过滤到目标 symbol
        if "证券代码" in df.columns:
            df = df[df["证券代码"].astype(str).str.zfill(6) == code]
        if df.empty:
            return pd.DataFrame()

        # 标准化列名
        rename_map = {
            "交易日期":  "date",
            "证券代码":  "symbol",
            "证券简称":  "name",
            "成交价":     "trade_price",
            "收盘价":     "close",
            "折溢率":     "discount_pct",   # 已是百分数
            "成交笔数":  "deal_count",
            "成交总量":  "deal_volume",
            "成交总额":  "deal_value",
            "成交总额/流通市值": "value_to_float_mcap",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        df = self._ensure_date_col(df)
        for c in ("trade_price", "close", "discount_pct", "deal_count",
                  "deal_volume", "deal_value", "value_to_float_mcap"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        return df.sort_values("date", kind="mergesort").reset_index(drop=True)

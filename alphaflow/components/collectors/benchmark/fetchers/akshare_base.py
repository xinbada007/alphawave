"""
AkShareIndexFetcher — akshare 指数 fetcher 模板基类
====================================================
Template Method 模式：把 4 处重复的 try/empty/clean/tail 模板内化到中间层，
子类只需声明 rename_map 与 _ak_call。

继承链：
  BaseBenchmarkFetcher (ABC, 通用清洗)
    └── AkShareIndexFetcher (本类，ak 模板)
          ├── AkShareHSIFetcher        (EM ^HSI，T+0，无 volume)
          ├── AkShareHSISinaFetcher    (Sina ^HSI，T-1，含 volume)
          └── AkShareHS300Fetcher      (EM 沪深 300，T-0，含 volume)

OBBIndexFetcher 因有 semaphore / 字段过滤等独立逻辑，不走本模板，仍直接继承
BaseBenchmarkFetcher。
"""
from __future__ import annotations

import asyncio
from abc import abstractmethod
from typing import ClassVar, Dict

import pandas as pd

from .base import BaseBenchmarkFetcher


class AkShareIndexFetcher(BaseBenchmarkFetcher):
    """所有 akshare 指数 fetcher 的模板基类。"""

    #: 列名重命名表；子类按各自接口字段覆盖。空表示原始列名已规范。
    rename_map: ClassVar[Dict[str, str]] = {}

    @abstractmethod
    def _ak_call(self) -> pd.DataFrame:
        """子类返回同步 akshare 接口调用结果（包装具体函数 + 参数）。"""
        raise NotImplementedError

    async def fetch_index(self, days: int) -> pd.DataFrame:
        try:
            df = await asyncio.to_thread(self._ak_call)
        except Exception as e:
            print(f"  [{self.name}] fetch_index failed: {str(e)[:80]}")
            return pd.DataFrame()

        if df is None or df.empty:
            return pd.DataFrame()

        df = self._clean_index_df(df, self.rename_map)
        if not df.empty:
            df = df.tail(int(days * 1.6))
        return df

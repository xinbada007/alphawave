"""
DataFrame 清洗共享工具
=======================
跨 collector 共享的 DataFrame 规整原子操作（M2 DRY 修复）。

设计原则
--------
* **拆成正交原子**：date 列归一 / 数值强转 / 排序去重——每个函数单一职责，
  调用方按需组合，避免"一锅烩 + flag 参数"反 DRY。
* **不耦合业务策略**：是否 fillna(0)、是否走 enricher、是否 drop NaN
  都由调用方决定（market 业务允许 0 填充；benchmark/flow 保留 NaN 区分缺失）。
* **幂等**：所有函数对已规整过的 DF 重复调用是无副作用的。
* **空 DF 安全**：传入空 / None 均稳定返回空 DataFrame，不抛异常。
"""
from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd


# 项目内常见的 date 列别名（中英 / 大小写）
DEFAULT_DATE_ALIASES: tuple = ("Date", "DATE", "时间", "日期", "交易日期", "上榜日")


def normalize_date_column(
    df: pd.DataFrame,
    candidates: Iterable[str] = DEFAULT_DATE_ALIASES,
    drop_invalid: bool = True,
) -> pd.DataFrame:
    """统一 date 列：rename 别名 → to_datetime → drop NaT 行。"""
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df

    if "date" not in df.columns:
        for c in candidates:
            if c in df.columns:
                df = df.rename(columns={c: "date"})
                break

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        if drop_invalid:
            df = df.dropna(subset=["date"])
    return df


def coerce_numeric_columns(
    df: pd.DataFrame,
    columns: Iterable[str],
    fill_na: Optional[float] = None,
) -> pd.DataFrame:
    """对存在的列做 to_numeric；fill_na 非 None 时 fillna，否则保留 NaN。"""
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()

    for c in columns:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            if fill_na is not None:
                df[c] = df[c].fillna(fill_na)
    return df


def dedupe_and_sort_by_date(df: pd.DataFrame) -> pd.DataFrame:
    """按 date 升序、去重、reset_index。无 date 列原样返回。"""
    if df is None or df.empty or "date" not in df.columns:
        return df if df is not None else pd.DataFrame()

    return (
        df.sort_values("date", kind="mergesort")
          .drop_duplicates(subset=["date"])
          .reset_index(drop=True)
    )


__all__ = [
    "DEFAULT_DATE_ALIASES",
    "normalize_date_column",
    "coerce_numeric_columns",
    "dedupe_and_sort_by_date",
]

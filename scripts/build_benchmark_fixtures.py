#!/usr/bin/env python3
"""
build_benchmark_fixtures.py
============================
抓取 ProxyTruth 所需的 benchmark 历史 OHLCV：
  US: SPY
  HK: ^HSI (filename: _HSI.csv)
  CN: 000300.SS

时间区间：2019-06-01 ~ 2025-12-31（覆盖所有 V1+V2+V3 anchor 与未来随机基线）
"""
from __future__ import annotations
import os, sys
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

OUT = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures",
                   "golden_samples", "_benchmark")
os.makedirs(OUT, exist_ok=True)

BENCHES = [
    ("SPY", "SPY"),
    ("_HSI", "^HSI"),
    ("000300_SS", "000300.SS"),
]

START = "2019-06-01"
END = "2025-12-31"


def fetch(ticker: str) -> pd.DataFrame:
    df = yf.download(ticker, start=START, end=END, auto_adjust=False,
                     progress=False, threads=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    if "adj close" in df.columns:
        df = df.drop(columns=["adj close"])
    if "close" in df.columns and "volume" in df.columns:
        df["amount"] = df["close"] * df["volume"]
    cols = [c for c in ["date", "open", "high", "low", "close", "volume", "amount"] if c in df.columns]
    return df[cols]


def main():
    for fname, ticker in BENCHES:
        out_path = os.path.join(OUT, f"{fname}.csv")
        if os.path.exists(out_path):
            print(f"  [skip] {fname} exists ({os.path.getsize(out_path)} bytes)")
            continue
        print(f"  fetching {ticker} → {fname}.csv ... ", end="", flush=True)
        try:
            df = fetch(ticker)
        except Exception as e:
            print(f"FAILED: {e}")
            continue
        if df.empty:
            print("EMPTY")
            continue
        df.to_csv(out_path, index=False)
        print(f"OK {len(df)} rows")


if __name__ == "__main__":
    main()

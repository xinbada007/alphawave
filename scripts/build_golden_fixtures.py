#!/usr/bin/env python3
"""
Golden Sample Fixture Builder
==============================
拉取各黄金样本"事件日 ±N 天"窗口的真实 OHLCV，落地为 CSV fixture。
后续测试只读 fixture，零网络、可重放。

派发样本（5）：1810.HK / 3690.HK / 600519.SS / NFLX / META
正常样本（5）：0700.HK / MSFT / 0939.HK / 600036.SS / AAPL
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "fixtures", "golden_samples")
os.makedirs(OUT_DIR, exist_ok=True)

# (alias, yfinance_ticker, anchor_date, label)
SAMPLES = [
    # 派发样本
    ("1810_HK", "1810.HK", "2025-03-25", "distribution_xiaomi_placement"),
    ("3690_HK", "3690.HK", "2021-07-26", "distribution_meituan_regulatory_crackdown"),
    ("600519_SS", "600519.SS", "2021-02-22", "distribution_moutai_post_cny_top"),
    ("NFLX", "NFLX", "2022-04-20", "distribution_netflix_subscriber_loss"),
    ("META", "META", "2022-02-03", "distribution_meta_user_stagnation"),
    # 正常样本（取常态期作锚点）
    ("0700_HK_normal", "0700.HK", "2024-06-30", "normal_tencent"),
    ("MSFT_normal", "MSFT", "2024-06-30", "normal_microsoft"),
    ("0939_HK_normal", "0939.HK", "2024-06-30", "normal_ccb"),
    ("600036_SS_normal", "600036.SS", "2024-06-30", "normal_cmb"),
    ("AAPL_normal", "AAPL", "2024-09-30", "normal_apple"),
]

# 事件锚点 ±180 天：让 analyzer 有足够 lookback (60 + 60 + 缓冲)
PRE_DAYS = 200
POST_DAYS = 30


def fetch_one(ticker: str, anchor: str) -> pd.DataFrame:
    anchor_dt = datetime.strptime(anchor, "%Y-%m-%d")
    start = (anchor_dt - timedelta(days=PRE_DAYS)).strftime("%Y-%m-%d")
    end = (anchor_dt + timedelta(days=POST_DAYS)).strftime("%Y-%m-%d")
    df = yf.download(
        ticker, start=start, end=end,
        auto_adjust=False, progress=False, threads=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()

    # 拉平 MultiIndex（yfinance 0.2.x 行为）
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]

    df = df.reset_index().rename(columns={"date": "date"})
    df.columns = [c.lower() for c in df.columns]
    if "adj close" in df.columns:
        df = df.drop(columns=["adj close"])
    # 派生 amount = close * volume（HK/CN/US 通用代理）
    if "close" in df.columns and "volume" in df.columns:
        df["amount"] = df["close"] * df["volume"]
    return df[["date", "open", "high", "low", "close", "volume", "amount"]]


def main():
    summary = []
    for alias, ticker, anchor, label in SAMPLES:
        print(f"\n[{alias}] {ticker} @ {anchor}")
        try:
            df = fetch_one(ticker, anchor)
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
            summary.append((alias, ticker, anchor, "ERROR", str(e)[:60]))
            continue
        if df.empty:
            print(f"  EMPTY")
            summary.append((alias, ticker, anchor, "EMPTY", ""))
            continue
        out_path = os.path.join(OUT_DIR, f"{alias}.csv")
        df.to_csv(out_path, index=False)
        # 事件日附近抽样
        anchor_dt = pd.to_datetime(anchor)
        nearby = df[(df["date"] >= anchor_dt - pd.Timedelta(days=5)) &
                    (df["date"] <= anchor_dt + pd.Timedelta(days=5))]
        vol_event = nearby["volume"].max() if not nearby.empty else 0
        vol_pre = df[df["date"] < anchor_dt - pd.Timedelta(days=20)]["volume"].mean()
        ratio = (vol_event / vol_pre) if vol_pre and vol_pre > 0 else 0
        print(f"  rows={len(df)} window=[{df['date'].min().date()}..{df['date'].max().date()}] "
              f"event_max_vol/pre_avg_vol={ratio:.2f}x")
        summary.append((alias, ticker, anchor, "OK", f"{len(df)}d | vol×{ratio:.1f}"))

    print("\n" + "=" * 80)
    print(f"{'alias':<22}{'ticker':<14}{'anchor':<14}{'status':<8}info")
    print("=" * 80)
    for s in summary:
        print(f"{s[0]:<22}{s[1]:<14}{s[2]:<14}{s[3]:<8}{s[4]}")


if __name__ == "__main__":
    main()

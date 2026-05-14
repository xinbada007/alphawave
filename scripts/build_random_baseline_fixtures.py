"""
build_random_baseline_fixtures.py
=================================
Phase B Step 2: 抓取 100 股票的完整历史 OHLCV，覆盖所有 anchor 区间。

策略
----
- 100 股票各下载一次 [2019-01-01, 2025-04-30]（覆盖 anchor-300d ~ anchor+90d）
- 单文件存全期，audit 阶段按 anchor 切片
- 失败 ticker 写 fail.log + 跳过
- 跳过已存在文件（增量）

输出
----
tests/fixtures/random_baseline/<ticker>.csv  (sanitized: . → _, ^ → _)
tests/fixtures/random_baseline/fetch_summary.csv
"""
from __future__ import annotations

import os
import sys
import csv
import time
from typing import List

import pandas as pd
import yfinance as yf

DIR = os.path.join(
    os.path.dirname(__file__), "..", "tests", "fixtures", "random_baseline"
)
ANCHORS_CSV = os.path.join(DIR, "ticker_anchors.csv")
SUMMARY = os.path.join(DIR, "fetch_summary.csv")
FAIL_LOG = os.path.join(DIR, "fetch_fails.log")

START = "2019-01-01"
END = "2025-04-30"
PAUSE = 0.6  # 节流，避 yfinance 限流


def sanitize(t: str) -> str:
    return t.replace(".", "_").replace("^", "_")


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
    if not os.path.exists(ANCHORS_CSV):
        print(f"ERROR: {ANCHORS_CSV} missing. Run sample_random_baseline.py first.")
        return 2

    with open(ANCHORS_CSV) as f:
        reader = csv.DictReader(f)
        tickers: List[str] = sorted({r["ticker"] for r in reader})
    print(f"Total unique tickers: {len(tickers)}")

    results = []
    fails = []
    t0 = time.time()
    for i, t in enumerate(tickers, 1):
        out = os.path.join(DIR, f"{sanitize(t)}.csv")
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            print(f"  [{i:3}/{len(tickers)}] {t:14s} skip (exists, {os.path.getsize(out)//1024}KB)")
            results.append((t, "cached", os.path.getsize(out)))
            continue
        try:
            df = fetch(t)
            if df.empty or len(df) < 100:
                print(f"  [{i:3}/{len(tickers)}] {t:14s} ❌ EMPTY/short ({len(df)})")
                fails.append((t, "empty_or_short"))
                continue
            df.to_csv(out, index=False)
            print(f"  [{i:3}/{len(tickers)}] {t:14s} ✅ {len(df)} rows")
            results.append((t, "ok", len(df)))
        except Exception as e:
            print(f"  [{i:3}/{len(tickers)}] {t:14s} ❌ {type(e).__name__}: {e}")
            fails.append((t, f"{type(e).__name__}:{e}"))
        time.sleep(PAUSE)

    elapsed = time.time() - t0
    with open(SUMMARY, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "status", "size_or_rows"])
        w.writerows(results)
    if fails:
        with open(FAIL_LOG, "w") as f:
            for t, reason in fails:
                f.write(f"{t}\t{reason}\n")

    print(f"\n=== Done in {elapsed:.0f}s ===")
    print(f"  Success: {len(results)}/{len(tickers)}")
    print(f"  Fail: {len(fails)}")
    if fails:
        print(f"  See: {FAIL_LOG}")


if __name__ == "__main__":
    sys.exit(main() or 0)

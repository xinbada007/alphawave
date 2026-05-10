"""
sample_random_baseline.py
=========================
Phase B Step 1: 生成 100 股票 × 4 anchor = 400 个 (ticker, anchor) 采样清单。

设计
----
- 市场分层: US 50 / HK 30 / CN 20
- 每股 4 anchor: 60% 全市场随机 + 40% 富派发期 (per-anchor 抽样)
- 富派发期 (4 windows):
    * COVID-19 crash:        2020-03-01 ~ 2020-03-31
    * China-tech crackdown:  2021-07-01 ~ 2021-12-31
    * US tech bear:          2022-04-01 ~ 2022-08-31
    * Yen-carry unwind:      2024-08-01 ~ 2024-08-31
- 随机种子: 固定 seed=20260510 (复现性)
- 输出: tests/fixtures/random_baseline/ticker_anchors.csv

Universe 来源
-------------
- US: SP500 sector leaders + 高交易量 mid-caps (curated 80, sample 50)
- HK: HSI 蓝筹 + Hang Seng Tech (curated 40, sample 30)
- CN: CSI 300 sector leaders (curated 25, sample 20)
"""
from __future__ import annotations

import os
import random
import csv
from datetime import date, timedelta
from typing import List, Tuple

OUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "tests", "fixtures", "random_baseline"
)
os.makedirs(OUT_DIR, exist_ok=True)
OUT_CSV = os.path.join(OUT_DIR, "ticker_anchors.csv")

SEED = 20260510

# ============ Universe ============
# 80 US tickers，覆盖 11 个 GICS sectors
US_UNIVERSE = [
    # Tech
    "AAPL","MSFT","GOOGL","META","NVDA","AMD","INTC","CRM","ORCL","ADBE",
    "AVGO","CSCO","TXN","QCOM","NOW","SNOW","PANW","SHOP","UBER","XYZ",
    # Consumer Discretionary
    "AMZN","TSLA","HD","NKE","MCD","SBUX","BKNG","TGT","LOW","DIS",
    # Communication Services
    "NFLX","TMUS","T","VZ","CMCSA",
    # Financials
    "JPM","BAC","GS","MS","WFC","C","BLK","SCHW","AXP",
    # Health Care
    "JNJ","PFE","UNH","MRK","ABBV","LLY","TMO","ABT","CVS",
    # Industrials
    "BA","GE","CAT","UPS","HON","LMT","RTX","UNP",
    # Energy
    "XOM","CVX","COP","SLB",
    # Consumer Staples
    "PG","KO","PEP","WMT","COST","CL",
    # Materials
    "LIN","FCX","NEM",
    # Utilities
    "NEE","DUK","SO",
    # Real Estate
    "PLD","AMT","SPG",
]

# 40 HK tickers
HK_UNIVERSE = [
    # Tech
    "0700.HK","9988.HK","3690.HK","9618.HK","9999.HK","1024.HK","9888.HK",
    "0992.HK","0981.HK","1810.HK","6618.HK","1797.HK","9626.HK",
    # Financials
    "0005.HK","0939.HK","1398.HK","2318.HK","1299.HK","2388.HK","3988.HK",
    # Property / Infra
    "0001.HK","0016.HK","0017.HK","1109.HK","0688.HK",
    # Energy / Materials
    "0883.HK","0386.HK","1088.HK","1171.HK",
    # Consumer
    "1928.HK","2020.HK","6098.HK","2331.HK","0291.HK",
    # Healthcare
    "1093.HK","6160.HK","2269.HK",
    # Auto / Industrial
    "0175.HK","2238.HK","0489.HK",
]

# 25 CN A-share tickers (sector leaders)
# 注: .SS = Shanghai (60xxxx, 688xxx); .SZ = Shenzhen (000xxx, 002xxx, 300xxx)
CN_UNIVERSE = [
    # Tech
    "002475.SZ","000725.SZ","300750.SZ","300059.SZ",
    # Consumer
    "600519.SS","000858.SZ","603288.SS","600887.SS",
    # Financial
    "601318.SS","600036.SS","601398.SS","600000.SS","601166.SS",
    # Industrial / Energy
    "601857.SS","600028.SS","601088.SS","601628.SS",
    # Healthcare
    "600276.SS","300760.SZ","603259.SS",
    # Auto
    "000333.SZ","002594.SZ","000625.SZ","600104.SS","601633.SS",
]

MARKETS = [
    ("US", US_UNIVERSE, 50),
    ("HK", HK_UNIVERSE, 30),
    ("CN", CN_UNIVERSE, 20),
]

# ============ Anchor strategy ============
RANDOM_WINDOW = (date(2020, 1, 1), date(2024, 12, 31))
RICH_WINDOWS = [
    (date(2020, 3, 1),  date(2020, 3, 31)),    # COVID crash
    (date(2021, 7, 1),  date(2021, 12, 31)),   # China tech crackdown
    (date(2022, 4, 1),  date(2022, 8, 31)),    # US tech bear
    (date(2024, 8, 1),  date(2024, 8, 31)),    # Yen-carry unwind
]
ANCHORS_PER_STOCK = 4
RICH_RATIO = 0.40   # 40% from rich windows


def random_date_in(start: date, end: date, rng: random.Random) -> date:
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta))


def main():
    rng = random.Random(SEED)
    rows: List[Tuple[str, str, str, str]] = []  # (market, ticker, anchor, source)

    for market, universe, k in MARKETS:
        # 分层无放回抽样
        tickers = rng.sample(universe, k)
        for ticker in tickers:
            for i in range(ANCHORS_PER_STOCK):
                if rng.random() < RICH_RATIO:
                    # 富派发期
                    win = rng.choice(RICH_WINDOWS)
                    a = random_date_in(win[0], win[1], rng)
                    src = f"rich_{win[0]:%Y%m}"
                else:
                    a = random_date_in(*RANDOM_WINDOW, rng=rng)
                    src = "random"
                # 避开周末（简单跳到下周一）
                if a.weekday() >= 5:
                    a = a + timedelta(days=(7 - a.weekday()))
                rows.append((market, ticker, a.isoformat(), src))

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["market", "ticker", "anchor", "source"])
        w.writerows(rows)

    # 统计
    n_rich = sum(1 for r in rows if r[3].startswith("rich"))
    n_rand = sum(1 for r in rows if r[3] == "random")
    print(f"✅ Generated {len(rows)} (ticker, anchor) pairs → {OUT_CSV}")
    print(f"   Distribution: random={n_rand} ({n_rand/len(rows):.0%})  "
          f"rich={n_rich} ({n_rich/len(rows):.0%})")
    by_market = {}
    for r in rows:
        by_market.setdefault(r[0], 0)
        by_market[r[0]] += 1
    for m, n in by_market.items():
        print(f"   {m}: {n} pairs ({n/4:.0f} unique tickers × 4 anchors)")
    by_window = {}
    for r in rows:
        if r[3].startswith("rich"):
            by_window.setdefault(r[3], 0)
            by_window[r[3]] += 1
    print("   Rich-window breakdown:")
    for w, n in sorted(by_window.items()):
        print(f"     {w}: {n}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Golden Sample V3 Fixture Builder
=================================
扩大回归覆盖：在 v1 (10) + v2 (10) 基础上新增 v3 (20+20)，
覆盖更多事件类型 / 行业 / 地区，做最终体系正确性核实。

样本设计原则：
- 派发样本：选信号清晰、媒体可追溯、事件后股价确认下跌的真实事件
- 正常样本：选大盘 / 防御 / 成熟稳健龙头在常态期（无重大事件）
- 跨地区：US / HK / CN
- 跨事件类型：监管 / 财报雷 / 增发配售 / 行业冲击 / Hindenburg 类做空
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

OUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "tests", "fixtures", "golden_samples",
)
os.makedirs(OUT_DIR, exist_ok=True)

# (alias, yfinance_ticker, anchor_date, label)
# anchor_date 是事件 / 异动日；fixture 包含 anchor ± 200 / 30 天
SAMPLES = [
    # =================================================================
    # V3 派发样本（20）— 跨多事件类型、地区、行业
    # =================================================================
    # —— US 财报雷 / 业务雷 ————————————————————————————
    ("RBLX_v3",   "RBLX",     "2022-02-16", "distribution_roblox_q4_miss"),
    ("ZM_v3",     "ZM",       "2021-09-01", "distribution_zoom_growth_collapse"),
    ("DOCU_v3",   "DOCU",     "2021-12-03", "distribution_docusign_billings_miss"),
    ("CVNA_v3",   "CVNA",     "2022-05-11", "distribution_carvana_q1_disaster"),
    ("W_v3",      "W",        "2022-08-12", "distribution_wayfair_demand_collapse"),
    ("DIS_v3",    "DIS",      "2022-08-11", "distribution_disney_streaming_miss"),
    ("LULU_v3",   "LULU",     "2024-06-06", "distribution_lulu_guidance_cut"),
    # —— US Hindenburg / 治理风险 / IPO 解禁 ————————————
    ("SPCE_v3",   "SPCE",     "2021-07-12", "distribution_spce_post_branson_dump"),
    ("PLUG_v3",   "PLUG",     "2021-03-02", "distribution_plug_going_concern"),
    ("HOOD_v3",   "HOOD",     "2022-04-28", "distribution_hood_q1_disaster"),
    # —— 中概 / HK 监管类 ———————————————————————————————
    ("PDD_v3",    "PDD",      "2022-03-14", "distribution_pdd_china_adr_panic"),
    ("BIDU_v3",   "BIDU",     "2022-03-14", "distribution_bidu_china_adr_panic"),
    ("9988_HK_v3","9988.HK",  "2021-12-23", "distribution_baba_hk_drift_low"),
    ("0992_HK_v3","0992.HK",  "2024-04-15", "distribution_lenovo_pullback"),
    ("9618_HK_v3","9618.HK",  "2022-03-15", "distribution_jd_hk_panic"),
    # —— A 股 / 行业冲击 ————————————————————————————————
    ("002475_SS_v3","002475.SZ","2021-08-30","distribution_luxshare_apple_shock"),
    ("300750_SS_v3","300750.SZ","2022-04-25","distribution_catl_q1_miss"),
    # —— 增发 / 配售 / 大宗 ————————————————————————————
    ("9888_HK_v3","9888.HK",  "2024-09-13", "distribution_baidu_hk_drift"),
    ("F_v3",      "F",        "2024-07-25", "distribution_ford_q2_miss"),
    ("INTC_v3",   "INTC",     "2024-08-02", "distribution_intel_layoffs_dividend_cut"),

    # =================================================================
    # V3 正常样本（20）— 常态期、无重大事件、跨地区
    # =================================================================
    # —— US 蓝筹防御 ————————————————————————————————————
    ("BRK_B_normal_v3", "BRK-B",  "2024-04-30", "normal_berkshire"),
    ("WMT_normal_v3",   "WMT",    "2024-03-29", "normal_walmart"),
    ("PG_normal_v3",    "PG",     "2024-03-29", "normal_pg"),
    ("MCD_normal_v3",   "MCD",    "2024-03-29", "normal_mcdonalds"),
    ("COST_normal_v3",  "COST",   "2024-04-30", "normal_costco"),
    ("V_normal_v3",     "V",      "2024-03-29", "normal_visa"),
    ("HD_normal_v3",    "HD",     "2024-04-30", "normal_homedepot"),
    ("VZ_normal_v3",    "VZ",     "2024-03-29", "normal_verizon"),
    ("CSCO_normal_v3",  "CSCO",   "2024-03-29", "normal_cisco"),
    ("ADBE_normal_v3",  "ADBE",   "2024-04-30", "normal_adobe"),
    ("ORCL_normal_v3",  "ORCL",   "2024-04-30", "normal_oracle"),
    ("JPM_normal_v3",   "JPM",    "2024-03-29", "normal_jpmorgan"),
    # —— HK 蓝筹 / 公用 / 防御 —————————————————————————
    ("0001_HK_normal_v3", "0001.HK", "2024-06-30", "normal_ck_hutchison"),
    ("0005_HK_normal_v3", "0005.HK", "2024-06-30", "normal_hsbc"),
    ("1299_HK_normal_v3", "1299.HK", "2024-06-30", "normal_aia"),
    ("1398_HK_normal_v3", "1398.HK", "2024-06-30", "normal_icbc"),
    ("0883_HK_normal_v3", "0883.HK", "2024-06-30", "normal_cnooc"),
    # —— A 股稳健蓝筹 ——————————————————————————————————
    ("601318_SS_normal_v3","601318.SS","2024-06-28","normal_pingan"),
    ("600276_SS_normal_v3","600276.SS","2024-06-28","normal_hengrui"),
    ("000333_SS_normal_v3","000333.SZ","2024-06-28","normal_midea"),
]


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
    needed = ["date", "open", "high", "low", "close", "volume", "amount"]
    return df[[c for c in needed if c in df.columns]]


def main():
    summary = []
    for alias, ticker, anchor, label in SAMPLES:
        out_path = os.path.join(OUT_DIR, f"{alias}.csv")
        if os.path.exists(out_path):
            print(f"  [skip] {alias} already exists")
            summary.append((alias, ticker, anchor, "skip", ""))
            continue
        print(f"[{alias}] {ticker} @ {anchor} ... ", end="", flush=True)
        try:
            df = fetch_one(ticker, anchor)
        except Exception as e:
            print(f"FAILED: {type(e).__name__}: {e}")
            summary.append((alias, ticker, anchor, "ERROR", str(e)[:80]))
            continue
        if df.empty:
            print("EMPTY")
            summary.append((alias, ticker, anchor, "EMPTY", ""))
            continue
        if len(df) < 80:
            print(f"INSUFFICIENT ({len(df)} rows)")
            summary.append((alias, ticker, anchor, "SHORT", f"{len(df)} rows"))
            continue
        df.to_csv(out_path, index=False)
        print(f"OK {len(df)} rows → {alias}.csv")
        summary.append((alias, ticker, anchor, "OK", f"{len(df)} rows"))

    print("\n" + "=" * 80)
    print(f"  Total: {len(summary)}  OK: {sum(1 for s in summary if s[3] == 'OK')}  "
          f"FAIL: {sum(1 for s in summary if s[3] not in ('OK','skip'))}")
    print("=" * 80)
    for alias, t, a, st, msg in summary:
        if st not in ("OK", "skip"):
            print(f"  {st:<8} {alias:<25} {t:<12} {a}  {msg}")


if __name__ == "__main__":
    main()

"""
Flow Signals — 纯函数 metrics 层
=================================
按子源分组的纯函数：DataFrame → 子源 summary dict + pressure_signals 列表。
不依赖 framework，不知道 ResearchPack / Profile / Scorer 的存在。

每个 compute_*_summary 返回结构：
  {"latest": {...}, "rolling": {...}, "pressure_signals": [...], "neutral_signals": [...]}
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from . import config as cfg


def _classify(value: float, tiers, default: str = "NORMAL") -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return default
    for threshold, label in tiers:
        if value < threshold:
            return label
    return tiers[-1][1]


# =============================================================================
# 1. Block Trade
# =============================================================================
def compute_block_trade_summary(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """大宗交易：近 N 日折价笔数、平均折价、总成交额。"""
    if df is None or df.empty:
        return _empty_summary()

    # 近 N 日窗口（按日期排序后 tail）
    df = df.sort_values("date", kind="mergesort").reset_index(drop=True)
    window = df.tail(cfg.BLOCK_TRADE_WINDOW_DAYS * 5)  # 容纳重复日 + 多笔
    cutoff = (window["date"].max() - pd.Timedelta(days=cfg.BLOCK_TRADE_WINDOW_DAYS * 1.6)
              if "date" in window.columns else None)
    if cutoff is not None:
        window = window[window["date"] >= cutoff]

    # 折价笔数 & 总折价 & 总额
    if "discount_pct" in window.columns:
        discounted = window[window["discount_pct"] <= cfg.BLOCK_DISCOUNT_THRESHOLD_PCT]
    else:
        discounted = window.iloc[0:0]

    discount_count = int(len(discounted))
    total_count = int(len(window))
    avg_discount = (float(discounted["discount_pct"].mean())
                    if not discounted.empty and "discount_pct" in discounted else None)
    total_value = (float(window["deal_value"].sum())
                   if "deal_value" in window.columns and not window.empty else None)

    tier = _classify(discount_count, cfg.BLOCK_TRADE_TIERS)

    pressure: List[str] = []
    neutral:  List[str] = []
    if discount_count >= 3:
        pressure.append(cfg.TAG_BLOCK_DISCOUNT_FREQUENT)
    if avg_discount is not None and avg_discount <= cfg.BLOCK_DISCOUNT_THRESHOLD_PCT * 2:
        pressure.append(cfg.TAG_BLOCK_DISCOUNT_DEEP)

    return {
        "rolling": {
            "window_days":          cfg.BLOCK_TRADE_WINDOW_DAYS,
            "total_appearances":    total_count,
            "discount_count":       discount_count,
            "avg_discount_pct":     round(avg_discount, 2) if avg_discount is not None else None,
            "total_deal_value":     round(total_value, 2) if total_value is not None else None,
            "tier":                 tier,
        },
        "pressure_signals": pressure,
        "neutral_signals":  neutral,
    }


# =============================================================================
# 2. LHB（龙虎榜）
# =============================================================================
def compute_lhb_summary(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """龙虎榜：近 N 日上榜次数 + 净买额占总成交比。"""
    if df is None or df.empty:
        return _empty_summary()

    df = df.sort_values("date", kind="mergesort").reset_index(drop=True)
    cutoff = df["date"].max() - pd.Timedelta(days=cfg.LHB_WINDOW_DAYS * 1.6)
    window = df[df["date"] >= cutoff]

    appearances = int(len(window))
    net_buy_pct = (float(window["net_buy_to_market_pct"].mean())
                   if "net_buy_to_market_pct" in window.columns and not window.empty else None)
    total_net_buy = (float(window["net_buy"].sum())
                     if "net_buy" in window.columns and not window.empty else None)

    tier = _classify(appearances, cfg.LHB_TIERS)

    pressure: List[str] = []
    neutral:  List[str] = []
    if appearances >= 2:
        pressure.append(cfg.TAG_LHB_FREQUENT_APPEARANCE)
    if net_buy_pct is not None and net_buy_pct <= cfg.LHB_NET_SELL_THRESHOLD_PCT:
        pressure.append(cfg.TAG_LHB_NET_SELL)

    return {
        "rolling": {
            "window_days":          cfg.LHB_WINDOW_DAYS,
            "appearances":          appearances,
            "avg_net_buy_pct":      round(net_buy_pct, 4) if net_buy_pct is not None else None,
            "total_net_buy":        round(total_net_buy, 2) if total_net_buy is not None else None,
            "tier":                 tier,
        },
        "pressure_signals": pressure,
        "neutral_signals":  neutral,
    }


# =============================================================================
# 3. Southbound（占位）
# =============================================================================
def compute_southbound_summary(df: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """南向：第一版无历史，永远空。保留函数形态便于未来扩展。"""
    if df is None or df.empty:
        return _empty_summary()

    # 占位：未来可计算 net_flow_5d，目前直接返回空 + 一个 "stub" rolling 块
    return {
        "rolling": {
            "window_days":      cfg.SOUTHBOUND_WINDOW_DAYS,
            "appearances":      int(len(df)),
            "tier":             "NORMAL",
        },
        "pressure_signals": [],
        "neutral_signals":  [],
    }


# =============================================================================
# 工具
# =============================================================================
def _empty_summary() -> Dict[str, Any]:
    return {"rolling": {}, "pressure_signals": [], "neutral_signals": []}

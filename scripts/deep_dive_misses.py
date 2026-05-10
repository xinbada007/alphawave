#!/usr/bin/env python3
"""
deep_dive_misses.py
====================
对 audit MISS 案例逐一深度分析：

问题：原 audit 用 fwd_20d_return 单一时间点判定，可能错估
  - peak 日已是恐慌底（fwd 反弹 ≠ 信号错）
  - 20d 太短，无法捕获 30-60d 的慢跌
  - 应改用 [peak, peak+H] 区间内的最大回撤 / 最低点

本脚本对每个样本打印多 horizon 真值：
  - fwd_5d / 10d / 20d / 40d / 60d
  - max_drawdown_60d (peak 日起 60d 内最低收盘相对 peak 日的 drawdown)
  - days_to_trough_60d
  - peak_to_max_dd_horizon

判定升级（max-drawdown-based）：
  - 派发: peak ≥ ELEVATED & max_dd_60d ≤ -10% → STRONG_DD
  - 派发: peak ≥ ELEVATED & max_dd_60d ∈ (-10%, -5%] → MILD_DD
  - 派发: peak ≥ ELEVATED & max_dd_60d > -5% → 真伪反转（信号 vs 价格背离）
"""
from __future__ import annotations

import os, sys
from dataclasses import dataclass
from typing import Optional, Tuple, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from tests.test_golden_samples import (
    load_fixture, run_analyzers, extract_score, extract_level, primary_latest_tier,
)
from scripts.audit_signal_correlation import SAMPLES, sweep_one, LEVEL_RANK


HORIZONS = [5, 10, 20, 40, 60]


def fwd_return(full_df: pd.DataFrame, base_day: pd.Timestamp, h: int) -> Optional[float]:
    df = full_df.sort_values("date").reset_index(drop=True)
    mask = df["date"] >= base_day
    if not mask.any():
        return None
    s = mask.idxmax()
    e = min(s + h, len(df) - 1)
    if e == s:
        return None
    p0, p1 = float(df.loc[s, "close"]), float(df.loc[e, "close"])
    return (p1 - p0) / p0 if p0 else None


def max_drawdown_window(full_df: pd.DataFrame, base_day: pd.Timestamp, h: int):
    """从 base_day 到 base_day+h 之间，最低收盘相对 base_day 的最大跌幅 + 到达天数。"""
    df = full_df.sort_values("date").reset_index(drop=True)
    mask = df["date"] >= base_day
    if not mask.any():
        return None, None
    s = mask.idxmax()
    e = min(s + h, len(df) - 1)
    if e == s:
        return None, None
    p0 = float(df.loc[s, "close"])
    if p0 == 0:
        return None, None
    seg = df.loc[s:e, "close"].astype(float)
    trough_idx = seg.idxmin()
    p_low = float(seg.loc[trough_idx])
    dd = (p_low - p0) / p0
    days_to_trough = trough_idx - s
    return dd, days_to_trough


def main():
    print("=" * 150)
    print("Deep-dive MISS analysis — multi-horizon fwd return + max-drawdown over 60d")
    print("=" * 150)

    rows = []
    for s in SAMPLES:
        if s.klass != "distribution":
            continue
        points, anchor_actual, full_df = sweep_one(s)
        if not points:
            continue
        pre_window = [p for p in points if -10 <= p.dt <= 1]
        peak = max(pre_window, key=lambda p: (p.score or -1))

        fwd = {h: fwd_return(full_df, peak.day, h) for h in HORIZONS}
        dd_60, dt_trough = max_drawdown_window(full_df, peak.day, 60)

        rows.append((s, peak, fwd, dd_60, dt_trough))

    # 头部
    hdr = f"{'alias':<22}{'peak_dt':>8}{'score':>7}{'level':<11}"
    for h in HORIZONS: hdr += f"{'fwd_'+str(h)+'d':>9}"
    hdr += f"{'maxDD_60d':>11}{'tDtroughd':>10}  {'verdict':<25}"
    print(hdr); print("-" * 150)

    n_strong_dd = n_mild_dd = n_real_miss = n_anchor_bad = 0
    for s, peak, fwd, dd_60, dt_t in rows:
        peak_lvl = LEVEL_RANK.get(str(peak.level), 0)
        signal_strong = peak_lvl >= LEVEL_RANK["ELEVATED"]
        signal_weak = (peak.score or 0) >= 45 and not signal_strong

        # 判定
        if dd_60 is None:
            verdict = "no fwd data"
        elif signal_strong and dd_60 <= -0.10:
            verdict = "✅ STRONG_DD"; n_strong_dd += 1
        elif signal_strong and dd_60 <= -0.05:
            verdict = "🟢 MILD_DD"; n_mild_dd += 1
        elif signal_weak and dd_60 <= -0.10:
            verdict = "⚠️  WEAK_DD (level=MOD, dd ok)"; n_mild_dd += 1
        elif (peak.score or 0) < 45 and dd_60 > -0.05:
            verdict = "❓ ANCHOR? (no signal, no drop)"; n_anchor_bad += 1
        else:
            verdict = "❌ TRUE_MISS"; n_real_miss += 1

        line = f"{s.alias:<22}{peak.dt:>+8d}{(peak.score or 0):>7.1f}{(peak.level or '-'):<11}"
        for h in HORIZONS:
            v = fwd[h]
            line += f"{(f'{v:+.1%}' if v is not None else '-'):>9}"
        line += f"{(f'{dd_60:+.1%}' if dd_60 is not None else '-'):>11}{(str(dt_t) if dt_t is not None else '-'):>10}  {verdict:<25}"
        print(line)

    print()
    print("=" * 150)
    print(f"Distribution (30): STRONG_DD={n_strong_dd}  MILD/WEAK_DD={n_mild_dd}  "
          f"ANCHOR_SUSPECT={n_anchor_bad}  TRUE_MISS={n_real_miss}")
    print("=" * 150)


if __name__ == "__main__":
    main()

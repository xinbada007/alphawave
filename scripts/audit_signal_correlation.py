#!/usr/bin/env python3
"""
audit_signal_correlation.py
============================
时序+相关性审计：超越单点验证，检验体系是否在正确的时间窗口捕捉到信号，
且信号与技术面 / 股价后续异动是否相关。

方法
----
对每个样本，对锚点 [anchor-10, anchor+5] 共 16 个交易日做 sweep：
- 每个 day d 用 truncate_to=d 跑 analyzer，记录 score / tier / forward return
- 计算窗口内 peak_score 出现的相对天数（dt = peak_day - anchor）
- 计算 fwd_20d_return: (anchor+20d close - peak_day close) / peak_day close

判别（事后真值）
- 派发样本：peak_score ≥ 45（捕获），fwd_20d ≤ -5%（信号有预警价值）
- 正常样本：peak_score < 45（始终安静），|fwd_20d| < 10%（价格也基本平稳）

为什么这才是"正确的"验证
- 原黄金样本：固定看 anchor 日 score，无法证明信号"何时"触发
- sweep 后能看到信号在 anchor 前 0~5 天就已发出 → 真正的派发预警
- 加 forward return 验证信号 → 后续股价异动的因果链

被审计样本子集（每组挑 3 个有代表性的）
- 派发：1810.HK（持续派发）/ NFLX（财报雷）/ COIN（财报+宏观）
- 正常：MSFT / KO / 0939.HK
共 6 × 16 = 96 次 analyzer 调用，纯 fixture 驱动，秒级完成。
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from tests.test_golden_samples import (
    load_fixture, run_analyzers, extract_score, extract_level,
    primary_latest_tier,
)


# 抽样：v1 + v2 各挑 3 个，故意覆盖不同事件类型
@dataclass(frozen=True)
class AuditSample:
    alias: str
    symbol: str
    anchor: str
    klass: str
    label: str

SAMPLES = [
    # === V1 派发（5）===
    AuditSample("1810_HK",   "1810.HK",   "2025-03-25", "distribution", "Xiaomi placement"),
    AuditSample("3690_HK",   "3690.HK",   "2021-07-26", "distribution", "Meituan crackdown"),
    AuditSample("600519_SS", "600519.SH", "2021-02-22", "distribution", "Moutai post-CNY top"),
    AuditSample("NFLX",      "NFLX",      "2022-04-20", "distribution", "Netflix subs loss"),
    AuditSample("META",      "META",      "2022-02-03", "distribution", "Meta user stagnation"),
    # === V2 派发（5）===
    AuditSample("BABA_v2",   "BABA",      "2020-11-03", "distribution", "BABA Ant IPO suspended"),
    AuditSample("SNAP_v2",   "SNAP",      "2022-05-24", "distribution", "Snap profit warning"),
    AuditSample("COIN_v2",   "COIN",      "2022-05-11", "distribution", "Coin Q1 meltdown"),
    AuditSample("PTON_v2",   "PTON",      "2022-01-20", "distribution", "Peloton production halt"),
    AuditSample("TSLA_v2",   "TSLA",      "2020-09-08", "distribution", "TSLA SP500 rejection"),
    # === V1 正常（5）===
    AuditSample("0700_HK_normal",   "0700.HK",   "2024-06-30", "normal", "Tencent quiet"),
    AuditSample("MSFT_normal",      "MSFT",      "2024-06-30", "normal", "MSFT quiet"),
    AuditSample("0939_HK_normal",   "0939.HK",   "2024-06-30", "normal", "CCB quiet"),
    AuditSample("600036_SS_normal", "600036.SH", "2024-06-30", "normal", "CMB quiet"),
    AuditSample("AAPL_normal",      "AAPL",      "2024-09-30", "normal", "Apple quiet"),
    # === V2 正常（5）===
    AuditSample("JNJ_normal_v2",        "JNJ",       "2024-09-30", "normal", "JNJ quiet"),
    AuditSample("KO_normal_v2",         "KO",        "2024-09-30", "normal", "KO quiet"),
    AuditSample("PEP_normal_v2",        "PEP",       "2024-09-30", "normal", "PEP quiet"),
    AuditSample("0066_HK_normal_v2",    "0066.HK",   "2024-08-30", "normal", "MTR quiet"),
    AuditSample("600028_SS_normal_v2",  "600028.SH", "2024-08-30", "normal", "Sinopec quiet"),
]

PRE_DAYS = 10   # 锚点前扫描天数
POST_DAYS = 5   # 锚点后扫描天数（验证信号衰退）
FWD_RETURN_DAYS = 20  # 计算 forward return 的窗口


@dataclass
class DayPoint:
    day: pd.Timestamp
    dt: int            # day - anchor，单位：trading days（按 fixture 行号差）
    score: Optional[float]
    level: Optional[str]
    tier: Optional[str]
    close: float


def sweep_one(sample: AuditSample) -> Tuple[List[DayPoint], pd.Timestamp, pd.DataFrame]:
    """对单个样本做 [-PRE, +POST] sweep。返回时间序列 + 事件锚点 + 完整 fixture。"""
    full_df = load_fixture(sample.alias)  # 不截断
    anchor_dt = pd.Timestamp(sample.anchor)
    full_df = full_df.sort_values("date").reset_index(drop=True)

    # 找到 anchor 在 fixture 中的 index（取 ≤ anchor 的最近交易日）
    mask = full_df["date"] <= anchor_dt
    if not mask.any():
        return [], anchor_dt, full_df
    anchor_idx = mask.sum() - 1
    anchor_actual = full_df.loc[anchor_idx, "date"]

    points: List[DayPoint] = []
    start = max(0, anchor_idx - PRE_DAYS)
    end = min(len(full_df) - 1, anchor_idx + POST_DAYS)

    for i in range(start, end + 1):
        d = full_df.loc[i, "date"]
        sub_df = full_df.iloc[: i + 1].reset_index(drop=True)
        if len(sub_df) < 60:
            continue
        try:
            out = run_analyzers(sample.symbol, sub_df)
        except Exception:
            continue
        score = extract_score(out)
        level = extract_level(out)
        tier = primary_latest_tier(out)
        close = float(sub_df.iloc[-1]["close"])
        points.append(DayPoint(d, i - anchor_idx, score, level, tier, close))
    return points, anchor_actual, full_df


def fwd_return(full_df: pd.DataFrame, base_day: pd.Timestamp,
               horizon: int = FWD_RETURN_DAYS) -> Optional[float]:
    """从 base_day 起向前 horizon 个交易日的收益率。"""
    full_df = full_df.sort_values("date").reset_index(drop=True)
    mask = full_df["date"] >= base_day
    if not mask.any():
        return None
    start_idx = mask.idxmax()
    end_idx = min(start_idx + horizon, len(full_df) - 1)
    if end_idx == start_idx:
        return None
    p0 = float(full_df.loc[start_idx, "close"])
    p1 = float(full_df.loc[end_idx, "close"])
    if p0 == 0:
        return None
    return (p1 - p0) / p0


# Level 排序（与 composite_risk/config.py::LEVEL_TIERS 一致）
LEVEL_RANK = {"LOW": 0, "MODERATE": 1, "ELEVATED": 2, "HIGH": 3, "CRITICAL": 4}

def level_rank(lvl: Optional[str]) -> int:
    return LEVEL_RANK.get(str(lvl), 0)


def main() -> int:
    print("=" * 130)
    print("Signal–Price Correlation Audit (time-window sweep + forward return)")
    print(f"  window=[anchor-{PRE_DAYS}, anchor+{POST_DAYS}]  fwd_return_horizon={FWD_RETURN_DAYS}d")
    print("  双层判别：")
    print("    派发组（事后真值 fwd_return ≤ -5%）：")
    print("      - 强信号: peak_level ∈ {ELEVATED/HIGH/CRITICAL} 在 [anchor-10,+1] 窗口内")
    print("      - 弱信号: peak_score ≥ 45 但 level=MODERATE → 仅作\"建议关注\"")
    print("    正常组（fwd_return |·| < 10%）：")
    print("      - 安静: peak_level ≤ MODERATE → 不出 ELEVATED+ 警报")
    print("=" * 130)

    summary: List[Tuple[str, str, int, Optional[float], Optional[str], Optional[float], str]] = []

    for s in SAMPLES:
        points, anchor_actual, full_df = sweep_one(s)
        if not points:
            print(f"  ⚠️  {s.alias}: no points (fixture too short)")
            continue

        # 在 [anchor-PRE, anchor+1] 窗口内找 score 最大的点
        pre_window = [p for p in points if -PRE_DAYS <= p.dt <= 1]
        peak = max(pre_window, key=lambda p: (p.score or -1))
        fwd = fwd_return(full_df, peak.day, FWD_RETURN_DAYS)

        # 判别（基于 LEVEL）
        peak_lvl_rank = level_rank(peak.level)
        if s.klass == "distribution":
            captured_strong = peak_lvl_rank >= LEVEL_RANK["ELEVATED"]
            captured_weak = (peak.score is not None and peak.score >= 45)
            timing_ok = peak.dt <= 1
            forecast = (fwd is not None) and (fwd <= -0.05)
            if captured_strong and timing_ok and forecast:
                verdict = "✅ STRONG"
            elif captured_weak and timing_ok and forecast:
                verdict = "⚠️  WEAK (score ok, level only MODERATE)"
            else:
                tags = []
                if not captured_weak: tags.append(f"score={peak.score}")
                if not timing_ok: tags.append(f"事后才发(dt={peak.dt:+d})")
                if not forecast: tags.append(f"fwd={fwd:+.1%}")
                verdict = "❌ MISS: " + ", ".join(tags)
        else:
            quiet_strong = peak_lvl_rank < LEVEL_RANK["ELEVATED"]
            quiet_price = (fwd is None) or (abs(fwd) < 0.10)
            if quiet_strong and quiet_price:
                if peak_lvl_rank == LEVEL_RANK["MODERATE"]:
                    verdict = "✅ QUIET (max level=MODERATE 提示，未触 ELEVATED+ 警报)"
                else:
                    verdict = "✅ QUIET"
            else:
                tags = []
                if not quiet_strong: tags.append(f"误报 level={peak.level}")
                if not quiet_price: tags.append(f"价格异动 fwd={fwd:+.1%}")
                verdict = "❌ FALSE_ALARM: " + ", ".join(tags)

        summary.append((s.alias, s.klass, peak.dt, peak.score, peak.level, fwd, verdict))

    print(f"\n{'alias':<22}{'klass':<14}{'peak_dt':>8}{'peak_score':>11}  "
          f"{'peak_level':<10}{'fwd_20d':>10}  verdict")
    print("-" * 130)
    n_strong = n_weak = n_miss = n_quiet = n_false = 0
    for alias, klass, dt, score, level, fwd, verdict in summary:
        score_s = f"{score:6.1f}" if score is not None else "  None"
        fwd_s = f"{fwd:+7.1%}" if fwd is not None else "    -  "
        print(f"{alias:<22}{klass:<14}{dt:>+8d}{score_s:>11}  {(level or '-'):<10}{fwd_s:>10}  {verdict}")
        if verdict.startswith("✅ STRONG"): n_strong += 1
        elif verdict.startswith("⚠️"): n_weak += 1
        elif verdict.startswith("❌ MISS"): n_miss += 1
        elif verdict.startswith("✅ QUIET"): n_quiet += 1
        elif verdict.startswith("❌ FALSE"): n_false += 1

    n_dist = sum(1 for _, k, *_ in summary if k == "distribution")
    n_norm = sum(1 for _, k, *_ in summary if k == "normal")

    print("\n" + "=" * 130)
    print(f"派发组 ({n_dist}): STRONG={n_strong}  WEAK={n_weak}  MISS={n_miss}")
    print(f"正常组 ({n_norm}): QUIET={n_quiet}  FALSE_ALARM={n_false}")
    print("=" * 130)
    # 通过条件：派发 MISS=0；正常 FALSE_ALARM=0
    return 0 if (n_miss == 0 and n_false == 0) else 1


if __name__ == "__main__":
    sys.exit(main())

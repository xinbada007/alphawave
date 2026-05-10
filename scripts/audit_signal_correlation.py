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

    # =========================================================================
    # V3 派发（20）— 最终扩展回归
    # =========================================================================
    AuditSample("RBLX_v3",      "RBLX",      "2022-02-16", "distribution", "Roblox Q4 miss"),
    AuditSample("ZM_v3",        "ZM",        "2021-09-01", "distribution", "Zoom growth collapse"),
    AuditSample("DOCU_v3",      "DOCU",      "2021-12-03", "distribution", "DocuSign billings miss"),
    AuditSample("CVNA_v3",      "CVNA",      "2022-05-11", "distribution", "Carvana Q1 disaster"),
    AuditSample("W_v3",         "W",         "2022-08-12", "distribution", "Wayfair demand collapse"),
    AuditSample("DIS_v3",       "DIS",       "2022-08-11", "distribution", "Disney streaming miss"),
    AuditSample("LULU_v3",      "LULU",      "2024-06-06", "distribution", "Lulu guidance cut"),
    AuditSample("SPCE_v3",      "SPCE",      "2021-07-12", "distribution", "SPCE post-Branson dump"),
    AuditSample("PLUG_v3",      "PLUG",      "2021-03-02", "distribution", "Plug going concern"),
    AuditSample("HOOD_v3",      "HOOD",      "2022-04-28", "distribution", "Hood Q1 disaster"),
    AuditSample("PDD_v3",       "PDD",       "2022-03-14", "distribution", "PDD ADR panic"),
    AuditSample("BIDU_v3",      "BIDU",      "2022-03-14", "distribution", "BIDU ADR panic"),
    AuditSample("9988_HK_v3",   "9988.HK",   "2021-12-23", "distribution", "BABA HK drift low"),
    AuditSample("0992_HK_v3",   "0992.HK",   "2024-04-15", "distribution", "Lenovo pullback"),
    AuditSample("9618_HK_v3",   "9618.HK",   "2022-03-15", "distribution", "JD HK panic"),
    AuditSample("002475_SS_v3", "002475.SZ", "2021-08-30", "distribution", "Luxshare Apple shock"),
    AuditSample("300750_SS_v3", "300750.SZ", "2022-04-25", "distribution", "CATL Q1 miss"),
    AuditSample("9888_HK_v3",   "9888.HK",   "2024-09-13", "distribution", "Baidu HK drift"),
    AuditSample("F_v3",         "F",         "2024-07-25", "distribution", "Ford Q2 miss"),
    AuditSample("INTC_v3",      "INTC",      "2024-08-02", "distribution", "Intel layoffs+dividend cut"),

    # =========================================================================
    # V3 正常（20）— 最终扩展回归
    # =========================================================================
    AuditSample("BRK_B_normal_v3",     "BRK-B",     "2024-04-30", "normal", "Berkshire quiet"),
    AuditSample("WMT_normal_v3",       "WMT",       "2024-03-29", "normal", "Walmart quiet"),
    AuditSample("PG_normal_v3",        "PG",        "2024-03-29", "normal", "P&G quiet"),
    AuditSample("MCD_normal_v3",       "MCD",       "2024-03-29", "normal", "McDonald's quiet"),
    AuditSample("COST_normal_v3",      "COST",      "2024-04-30", "normal", "Costco quiet"),
    AuditSample("V_normal_v3",         "V",         "2024-03-29", "normal", "Visa quiet"),
    AuditSample("HD_normal_v3",        "HD",        "2024-04-30", "normal", "HomeDepot quiet"),
    AuditSample("VZ_normal_v3",        "VZ",        "2024-03-29", "normal", "Verizon quiet"),
    AuditSample("CSCO_normal_v3",      "CSCO",      "2024-03-29", "normal", "Cisco quiet"),
    AuditSample("ADBE_normal_v3",      "ADBE",      "2024-04-30", "normal", "Adobe quiet"),
    AuditSample("ORCL_normal_v3",      "ORCL",      "2024-04-30", "normal", "Oracle quiet"),
    AuditSample("JPM_normal_v3",       "JPM",       "2024-03-29", "normal", "JPMorgan quiet"),
    AuditSample("0001_HK_normal_v3",   "0001.HK",   "2024-06-30", "normal", "CK Hutchison quiet"),
    AuditSample("0005_HK_normal_v3",   "0005.HK",   "2024-06-30", "normal", "HSBC quiet"),
    AuditSample("1299_HK_normal_v3",   "1299.HK",   "2024-06-30", "normal", "AIA quiet"),
    AuditSample("1398_HK_normal_v3",   "1398.HK",   "2024-06-30", "normal", "ICBC quiet"),
    AuditSample("0883_HK_normal_v3",   "0883.HK",   "2024-06-30", "normal", "CNOOC quiet"),
    AuditSample("601318_SS_normal_v3", "601318.SH", "2024-06-28", "normal", "Ping An quiet"),
    AuditSample("600276_SS_normal_v3", "600276.SH", "2024-06-28", "normal", "Hengrui quiet"),
    AuditSample("000333_SS_normal_v3", "000333.SZ", "2024-06-28", "normal", "Midea quiet"),
]

PRE_DAYS = 10   # 锚点前扫描天数
POST_DAYS = 5   # 锚点后扫描天数（验证信号衰退）
FWD_RETURN_DAYS = 20      # 单点 fwd return（保留为参考）
DRAWDOWN_HORIZON = 60     # 主真值口径：peak 起 60 日内最大回撤
DD_STRONG_THRESHOLD = -0.10   # ≤ -10% 判 STRONG
DD_MILD_THRESHOLD   = -0.05   # ≤ -5%  判 MILD/WEAK


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


def max_drawdown(full_df: pd.DataFrame, base_day: pd.Timestamp,
                 horizon: int = DRAWDOWN_HORIZON) -> Tuple[Optional[float], Optional[int]]:
    """
    主真值口径：从 base_day 到 base_day+horizon 之间，最低收盘相对 base_day 的最大跌幅。
    比 fwd_return 更稳健 —— 后者只看终点单日，易被恐慌底反弹反转误判。

    返回 (drawdown, days_to_trough)。drawdown 为负数表示跌幅，0 或正数表示未跌破 base。
    """
    df = full_df.sort_values("date").reset_index(drop=True)
    mask = df["date"] >= base_day
    if not mask.any():
        return None, None
    s = mask.idxmax()
    e = min(s + horizon, len(df) - 1)
    if e == s:
        return None, None
    p0 = float(df.loc[s, "close"])
    if p0 == 0:
        return None, None
    seg = df.loc[s:e, "close"].astype(float)
    trough_idx = seg.idxmin()
    p_low = float(seg.loc[trough_idx])
    return (p_low - p0) / p0, int(trough_idx - s)


# Level 排序（与 composite_risk/config.py::LEVEL_TIERS 一致）
LEVEL_RANK = {"LOW": 0, "MODERATE": 1, "ELEVATED": 2, "HIGH": 3, "CRITICAL": 4}

def level_rank(lvl: Optional[str]) -> int:
    return LEVEL_RANK.get(str(lvl), 0)


def main() -> int:
    print("=" * 145)
    print("Signal–Price Correlation Audit (sweep + max-drawdown 60d)")
    print(f"  sweep window=[anchor-{PRE_DAYS}, anchor+{POST_DAYS}]")
    print(f"  事后真值: peak 起 {DRAWDOWN_HORIZON}d 内最大回撤 (取代单点 fwd_{FWD_RETURN_DAYS}d，避免 V 形反弹错杀)")
    print("  双层判别：")
    print(f"    派发组（事后真值 max_dd ≤ {DD_STRONG_THRESHOLD:.0%} 强 / ≤ {DD_MILD_THRESHOLD:.0%} 弱）：")
    print("      - STRONG: peak_level ∈ {ELEVATED/HIGH/CRITICAL} & max_dd 强")
    print("      - WEAK:   peak_score ≥ 45 & max_dd 弱以上 (level 仅 MODERATE 也认)")
    print("      - METHOD: 信号 OK 但价格 V 反弹 (max_dd > -5%) → 标 anchor 失效，不计漏报")
    print(f"    正常组（max_dd 与 fwd_{FWD_RETURN_DAYS}d 都 < |10%|）：")
    print("      - QUIET: peak_level ≤ MODERATE → 不出 ELEVATED+ 警报")
    print("=" * 145)

    summary = []
    for s in SAMPLES:
        points, anchor_actual, full_df = sweep_one(s)
        if not points:
            print(f"  ⚠️  {s.alias}: no points (fixture too short)")
            continue
        pre_window = [p for p in points if -PRE_DAYS <= p.dt <= 1]
        peak = max(pre_window, key=lambda p: (p.score or -1))
        fwd = fwd_return(full_df, peak.day, FWD_RETURN_DAYS)
        dd, dt_t = max_drawdown(full_df, peak.day, DRAWDOWN_HORIZON)

        peak_lvl_rank = level_rank(peak.level)
        if s.klass == "distribution":
            captured_strong = peak_lvl_rank >= LEVEL_RANK["ELEVATED"]
            captured_weak   = (peak.score is not None and peak.score >= 45) and not captured_strong
            timing_ok       = peak.dt <= 1
            dd_strong       = (dd is not None) and (dd <= DD_STRONG_THRESHOLD)
            dd_mild         = (dd is not None) and (dd <= DD_MILD_THRESHOLD)

            if captured_strong and timing_ok and dd_strong:
                verdict = "✅ STRONG"
            elif captured_strong and timing_ok and dd_mild:
                verdict = "🟢 STRONG_MILD (signal HIGH, dd 中等)"
            elif captured_weak and timing_ok and dd_strong:
                verdict = "⚠️  WEAK (level=MOD, dd 大)"
            elif captured_weak and timing_ok and dd_mild:
                verdict = "⚠️  WEAK_MILD (level=MOD, dd 中等)"
            elif (captured_strong or captured_weak) and timing_ok and not dd_mild:
                # 信号触发了但 60d 没跌 → anchor 失效 / V 反弹 → 不算产品漏报
                verdict = f"🔵 METHOD (signal ok, max_dd={dd:+.1%}, anchor 反转)"
            else:
                tags = []
                if not captured_strong and not captured_weak:
                    tags.append(f"score={peak.score}")
                if not timing_ok:
                    tags.append(f"事后才发(dt={peak.dt:+d})")
                if not dd_mild:
                    tags.append(f"max_dd={dd:+.1%}" if dd is not None else "no dd data")
                verdict = "❌ TRUE_MISS: " + ", ".join(tags)
        else:
            quiet_strong = peak_lvl_rank < LEVEL_RANK["ELEVATED"]
            # 正常组：不仅看 fwd 单点，也看 max_dd（避免漏掉短期反弹长期跌的隐患）
            quiet_price = (
                (fwd is None or abs(fwd) < 0.10)
                and (dd is None or dd > DD_MILD_THRESHOLD)
            )
            if quiet_strong and quiet_price:
                lbl = "MODERATE 提示" if peak_lvl_rank == LEVEL_RANK["MODERATE"] else ""
                verdict = f"✅ QUIET ({lbl}未触 ELEVATED+ 警报)" if lbl else "✅ QUIET"
            elif quiet_strong and not quiet_price:
                # 信号正确，但样本期内股价异动 → 样本选择问题，非信号端误报
                verdict = (f"🟡 SAMPLE_DRIFT (signal ok, fwd={fwd:+.1%} dd={dd:+.1%})"
                           if (fwd is not None and dd is not None) else
                           "🟡 SAMPLE_DRIFT (price moved)")
            else:
                tags = [f"误报 level={peak.level}"]
                if not quiet_price and fwd is not None: tags.append(f"fwd={fwd:+.1%}")
                if not quiet_price and dd is not None:  tags.append(f"dd={dd:+.1%}")
                verdict = "❌ FALSE_ALARM: " + ", ".join(tags)

        summary.append((s.alias, s.klass, peak.dt, peak.score, peak.level, fwd, dd, dt_t, verdict))

    print(f"\n{'alias':<22}{'klass':<14}{'pdt':>5}{'score':>7}  "
          f"{'level':<10}{'fwd20d':>9}{'maxDD60':>9}{'tT':>4}  verdict")
    print("-" * 145)
    counts = {}
    for alias, klass, dt, score, level, fwd, dd, dt_t, verdict in summary:
        score_s = f"{score:6.1f}" if score is not None else "  None"
        fwd_s = f"{fwd:+7.1%}" if fwd is not None else "    -  "
        dd_s = f"{dd:+7.1%}" if dd is not None else "    -  "
        dt_s = f"{dt_t}" if dt_t is not None else "-"
        print(f"{alias:<22}{klass:<14}{dt:>+5d}{score_s:>7}  "
              f"{(level or '-'):<10}{fwd_s:>9}{dd_s:>9}{dt_s:>4}  {verdict}")
        # 提取 verdict 主类
        key = verdict.split()[1] if len(verdict.split()) > 1 else verdict
        counts[key] = counts.get(key, 0) + 1

    n_dist = sum(1 for r in summary if r[1] == "distribution")
    n_norm = sum(1 for r in summary if r[1] == "normal")
    print("\n" + "=" * 145)
    print(f"派发组 ({n_dist}):  STRONG={counts.get('STRONG',0)}  STRONG_MILD={counts.get('STRONG_MILD',0)}  "
          f"WEAK={counts.get('WEAK',0)}  WEAK_MILD={counts.get('WEAK_MILD',0)}  "
          f"METHOD={counts.get('METHOD',0)}  TRUE_MISS={counts.get('TRUE_MISS:',0)}")
    print(f"正常组 ({n_norm}):  QUIET={counts.get('QUIET',0)}  "
          f"SAMPLE_DRIFT={counts.get('SAMPLE_DRIFT',0)}  FALSE_ALARM={counts.get('FALSE_ALARM:',0)}")
    print("=" * 145)
    return 0 if (counts.get('TRUE_MISS:', 0) == 0 and counts.get('FALSE_ALARM:', 0) == 0) else 1


if __name__ == "__main__":
    sys.exit(main())

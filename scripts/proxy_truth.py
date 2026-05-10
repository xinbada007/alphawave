"""
proxy_truth.py
==============
Backtest 评估的"代理真值"（Proxy Truth）层。

哲学
----
真值（机构是否派发）不可观测；只能通过价格/成交量的复合证据
做带先验假设的反推。本模块将这一假设集合显式化为可证伪规则。

输入: 个股 OHLCV + 同期 benchmark OHLCV（用于 excess drawdown）
输出: ProxyLabel 字典 (is_distribution, intensity, pattern, confidence,
                       evidence, hypotheses_passed)

设计原则
--------
- 纯函数：相同输入永远相同输出
- 假设可证伪：每条 H1-H5 都暴露 evidence + 通过/未通过状态
- 与 framework 解耦：仅依赖 pandas + numpy
- 显式阈值：所有阈值常量集中在文件头，可调可审计
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from scripts.bootstrap_mdd import bootstrap_mdd_pvalue, BootstrapResult


# =============================================================================
# 阈值常量 — 所有标定参数集中此处
# =============================================================================
# H1: 个股绝对 max drawdown
DD_HORIZON = 60                    # peak 起 60 个交易日
DD_STRONG_ABS = -0.15              # 绝对 ≤ -15% → STRONG 候选
DD_MILD_ABS = -0.08                # 绝对 ≤ -8%  → MILD 候选

# H1_bootstrap: Politis-Romano 平稳 bootstrap p-value
BOOTSTRAP_B = 2000                 # 重抽次数
BOOTSTRAP_L = 6                    # 平稳块长度
BOOTSTRAP_PRE_LOOKBACK = 252       # anchor 前历史天数
P_STRONG = 0.01                    # bootstrap p ≤ 1% → STRONG 候选
P_MILD = 0.05                      # bootstrap p ≤ 5% → MILD 候选

# H2: excess drawdown vs benchmark
EXCESS_DD_STRONG = -0.10           # excess ≤ -10% → STRONG
EXCESS_DD_MILD = -0.05             # excess ≤ -5%  → MILD

# H3: 成交量放大
VOLUME_RATIO_THRESHOLD = 1.20      # post 60d 平均量 / pre 60d 平均量 ≥ 1.2

# H4: 持续性（区分派发 vs 一次性 flash crash）
NEGATIVE_DAYS_RATIO = 0.40         # 60d 中下跌日 ≥ 40%

# H5: V 反弹排除
RECOVERY_RATIO_MAX = 0.50          # 60d 末价格相对 trough 的反弹幅度 / |max_dd| ≤ 0.5
DAYS_TO_TROUGH_RANGE = (3, 50)     # trough 出现在 [3d, 50d] 之间（剔除单日跳水和延迟跌）

# 终判阈值
STRONG_MIN_HYPOTHESES = 4          # H1+H2 必满足，再 ≥2 个辅助 → STRONG
MILD_MIN_HYPOTHESES = 2            # H1 mild 满足 + ≥1 辅助 → MILD


@dataclass
class ProxyLabel:
    """ProxyTruth 输出。"""
    is_distribution: bool
    intensity: str                 # "STRONG" / "MILD" / "NONE"
    pattern: str                   # "shock" / "drift" / "rebound" / "flat"
    confidence: float              # 0-1
    hypotheses: Dict[str, bool]    # H1/H1s/H2/H3/H4/H5 → passed
    evidence: Dict[str, float]     # 各 metric 的实际数值
    notes: List[str] = field(default_factory=list)


def _max_drawdown(close: pd.Series) -> Tuple[float, int]:
    """从第 0 日起到末日，最低收盘相对第 0 日的跌幅 + 触底天数。"""
    if len(close) < 2:
        return 0.0, 0
    p0 = float(close.iloc[0])
    if p0 == 0:
        return 0.0, 0
    seg = close.astype(float).reset_index(drop=True)
    trough_idx = int(seg.idxmin())
    p_low = float(seg.iloc[trough_idx])
    return (p_low - p0) / p0, trough_idx


def _classify_pattern(dd: float, days_to_trough: int, recovery_ratio: float) -> str:
    """根据轨迹形状给 pattern 标签。"""
    if dd > -0.05:
        return "flat"
    if days_to_trough <= 3:
        return "shock"          # 急跌型
    if recovery_ratio >= 0.5:
        return "rebound"        # V 反弹型（虽跌但收复）
    return "drift"              # 慢跌持续型


def evaluate(
    *,
    stock: pd.DataFrame,           # OHLCV，含 date / close / volume；按日期升序
    benchmark: Optional[pd.DataFrame],  # 同期 benchmark，含 date / close
    base_day: pd.Timestamp,        # 评估的锚点日（peak day）
    horizon: int = DD_HORIZON,
) -> ProxyLabel:
    """
    对单个 (stock, base_day) 评估 ProxyTruth。

    benchmark 为 None 时 H2 被标 inconclusive（passed=False，不否决，不肯定）。
    """
    # —— 取个股 base_day 起 horizon 段 ——
    s = stock.sort_values("date").reset_index(drop=True)
    smask = s["date"] >= base_day
    if not smask.any() or smask.sum() < 5:
        return _empty_label("insufficient stock data after base_day")
    s_start = int(smask.idxmax())
    s_end = min(s_start + horizon, len(s) - 1)
    seg = s.iloc[s_start: s_end + 1].reset_index(drop=True)
    if len(seg) < 5:
        return _empty_label("insufficient horizon data")

    # —— 个股 max drawdown ——
    abs_dd, t_trough = _max_drawdown(seg["close"])
    last_close = float(seg["close"].iloc[-1])
    trough_close = float(seg["close"].iloc[t_trough])
    p0 = float(seg["close"].iloc[0])
    recovery_ratio = (last_close - trough_close) / abs(trough_close - p0) if abs(trough_close - p0) > 1e-9 else 0.0

    # —— σ 标定（基于 base_day 之前的 BOOTSTRAP_PRE_LOOKBACK 段）——
    pre_mask = (s["date"] < base_day)
    pre_seg = s[pre_mask].tail(BOOTSTRAP_PRE_LOOKBACK)
    if len(pre_seg) >= 20:
        daily_ret = pre_seg["close"].astype(float).pct_change().dropna().values
        sigma_daily = float(daily_ret.std(ddof=1)) if len(daily_ret) > 0 else 0.0
    else:
        daily_ret = np.array([])
        sigma_daily = 0.0

    # —— H1_bootstrap: Politis-Romano stationary bootstrap on MDD ——
    # seed: deterministic from base_day to ensure reproducibility
    seed = int(pd.Timestamp(base_day).value % (2**31))
    if len(daily_ret) >= 20:
        # use log returns for bootstrap (path reconstruction via cumsum-exp)
        log_ret = np.log1p(daily_ret)
        boot: BootstrapResult = bootstrap_mdd_pvalue(
            log_ret, abs_dd,
            horizon=horizon, B=BOOTSTRAP_B, L=BOOTSTRAP_L, seed=seed,
        )
        p_value = boot.p_value
        boot_method = boot.method
        z_dd = boot.z_score
    else:
        p_value = None
        boot_method = "degenerated"
        z_dd = 0.0

    # —— H1: 个股绝对 dd（与 bootstrap p-value 联合判定）——
    H1_strong_abs = abs_dd <= DD_STRONG_ABS
    H1_mild_abs = abs_dd <= DD_MILD_ABS
    # bootstrap 判定（None 时不否决，但也不肯定）
    H1_strong_p = (p_value is not None and p_value <= P_STRONG)
    H1_mild_p = (p_value is not None and p_value <= P_MILD)
    # 综合 H1：abs OR bootstrap 任一通过即可（解耦双门）
    H1_strict = H1_strong_abs or H1_strong_p
    H1_loose = H1_mild_abs or H1_mild_p

    # —— H2: excess drawdown vs benchmark ——
    excess_dd = None
    H2 = None
    if benchmark is not None and len(benchmark) > 0:
        b = benchmark.sort_values("date").reset_index(drop=True)
        bmask = b["date"] >= base_day
        if bmask.any():
            b_start = int(bmask.idxmax())
            b_end = min(b_start + horizon, len(b) - 1)
            bseg = b.iloc[b_start: b_end + 1].reset_index(drop=True)
            if len(bseg) >= 5:
                bench_dd, _ = _max_drawdown(bseg["close"])
                excess_dd = abs_dd - bench_dd  # 个股跌得比 benchmark 更多 → 负值
                if excess_dd <= EXCESS_DD_STRONG:
                    H2 = "STRONG"
                elif excess_dd <= EXCESS_DD_MILD:
                    H2 = "MILD"
                else:
                    H2 = "NONE"

    # —— H3: 成交量放大 ——
    vol_ratio = None
    H3 = False
    if "volume" in s.columns and len(pre_seg) >= 10:
        vol_post = float(seg["volume"].astype(float).mean())
        vol_pre = float(pre_seg["volume"].astype(float).mean())
        if vol_pre > 0:
            vol_ratio = vol_post / vol_pre
            H3 = vol_ratio >= VOLUME_RATIO_THRESHOLD

    # —— H4: 持续性 ——
    daily_ret_post = seg["close"].astype(float).pct_change().dropna()
    neg_count = int((daily_ret_post < 0).sum())
    neg_ratio = neg_count / len(daily_ret_post) if len(daily_ret_post) > 0 else 0.0
    H4 = neg_ratio >= NEGATIVE_DAYS_RATIO

    # —— H5: 排除 V 反弹 ——
    H5 = (
        DAYS_TO_TROUGH_RANGE[0] <= t_trough <= DAYS_TO_TROUGH_RANGE[1]
        and recovery_ratio <= RECOVERY_RATIO_MAX
    )

    # —— 终判 ——
    h_dict = {
        "H1_abs":         H1_mild_abs,
        "H1_strict":      H1_strict,
        "H1_bootstrap":   H1_mild_p,
        "H1_boot_strong": H1_strong_p,
        "H2_excess":      (H2 in ("STRONG", "MILD")) if H2 else False,
        "H2_strong":      (H2 == "STRONG"),
        "H3_volume":      H3,
        "H4_persist":     H4,
        "H5_no_vshape":   H5,
    }

    # H5 降级为辅助打分而非否决（V反弹仍可能是派发的早期阶段）
    aux_passed = sum([H3, H4])  # 仅 H3+H4 计入 hard aux

    if H1_strict and h_dict["H2_strong"] and aux_passed >= 2:
        intensity = "STRONG"
        is_dist = True
    elif H1_loose and h_dict["H2_excess"] and aux_passed >= 1:
        intensity = "MILD"
        is_dist = True
    else:
        intensity = "NONE"
        is_dist = False

    pattern = _classify_pattern(abs_dd, t_trough, recovery_ratio)

    confidence = round(
        (int(h_dict["H1_strict"]) * 0.25
         + int(h_dict["H1_boot_strong"]) * 0.15
         + int(h_dict["H2_strong"]) * 0.20
         + int(H3) * 0.10
         + int(H4) * 0.15
         + int(H5) * 0.15),
        3,
    )

    notes = []
    if benchmark is None or H2 is None:
        notes.append("benchmark unavailable → H2 inconclusive (treated as not passed)")
    if boot_method != "bootstrap":
        notes.append(f"bootstrap method={boot_method}")

    return ProxyLabel(
        is_distribution=is_dist,
        intensity=intensity,
        pattern=pattern,
        confidence=confidence,
        hypotheses=h_dict,
        evidence={
            "abs_dd_60d":     round(abs_dd, 4),
            "p_value":        round(p_value, 4) if p_value is not None else None,
            "z_dd":           round(z_dd, 3),
            "sigma_daily":    round(sigma_daily, 4),
            "excess_dd":      round(excess_dd, 4) if excess_dd is not None else None,
            "vol_ratio":      round(vol_ratio, 3) if vol_ratio is not None else None,
            "neg_day_ratio":  round(neg_ratio, 3),
            "days_to_trough": int(t_trough),
            "recovery_ratio": round(recovery_ratio, 3),
            "boot_method":    boot_method,
        },
        notes=notes,
    )


def _empty_label(reason: str) -> ProxyLabel:
    return ProxyLabel(
        is_distribution=False,
        intensity="NONE",
        pattern="flat",
        confidence=0.0,
        hypotheses={},
        evidence={},
        notes=[reason],
    )

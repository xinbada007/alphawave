"""
bootstrap_mdd.py
================
Politis-Romano 平稳 Bootstrap：对路径上确界统计量（Maximum Drawdown）
做无分布假设的假设检验。

理论根基
--------
- Politis & Romano (1994, JASA): stationary bootstrap for weakly dependent data
- Hörmann & Kojadinovic (2014): bootstrap validity for path-functionals under β-mixing
- Magdon-Ismail & Atiya (2004): MDD parametric closed form (used as degeneration fallback)

核心 API
--------
  bootstrap_mdd_pvalue(pre_returns, observed_mdd, B=2000, L=6, seed=...) -> float

输入
----
- pre_returns: anchor 之前的日收益序列（np.array, 1D, no NaN）
- observed_mdd: anchor 后 60d 的实际 MDD（负数，e.g. -0.18 = -18%）

输出
----
- p_value: P(MDD_bootstrap <= observed_mdd | H_0)，越小越异常

设计原则
--------
- 数据泄露防护：函数签名仅接收 pre_returns，物理隔离 anchor 后数据
- 复现性：seed 强制传入；同 seed 同输入永远同输出
- 退化处理：pre 数据不足时回退 Magdon-Ismail 闭式（带 flag）
- 纯函数：无副作用，便于单测
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

import math
import numpy as np


# 默认参数
DEFAULT_B = 2000          # bootstrap 重抽次数
DEFAULT_L = 6             # 平稳块长度（Politis-White: ~T^{1/3}, T=252 ≈ 6）
DEFAULT_HORIZON = 60      # 评估窗口
MIN_PRE_DAYS_BOOTSTRAP = 100   # < 100 → 退化为 R1-corrected
MIN_PRE_DAYS_PARAMETRIC = 20   # < 20 → 完全退化（返回 None）

# Magdon-Ismail (2004) 常数：MDD 的零漂移 BM 闭式
MAGDON_MEAN_COEF = -math.sqrt(2.0 / math.pi)        # ≈ -0.7979
MAGDON_STD_COEF = math.sqrt(2.0 - 4.0 / math.pi)    # ≈ 0.8525


@dataclass
class BootstrapResult:
    """Bootstrap 输出。"""
    p_value: Optional[float]
    method: str                 # "bootstrap" / "parametric" / "degenerated"
    n_pre: int
    block_length: int
    n_resample: int
    observed_mdd: float
    null_mdd_mean: float        # bootstrap/parametric 给出的零分布均值
    null_mdd_std: float         # 零分布标准差
    z_score: float              # (observed - mean) / std
    notes: str = ""


def _path_mdd(returns: np.ndarray) -> float:
    """从一段收益序列还原归一化价格路径，返回 MDD（≤ 0）。"""
    log_p = np.cumsum(returns)
    p = np.exp(log_p)               # P_t / P_0
    p = np.concatenate([[1.0], p])  # 起点
    trough = p.min()
    return float(trough - 1.0)      # (p_low - p0) / p0


def _stationary_bootstrap_indices(
    n: int, length: int, block_length: int, rng: np.random.Generator
) -> np.ndarray:
    """
    Politis-Romano 平稳 bootstrap 索引序列。

    每步以 1/L 概率开新块（uniform 抽起点），1-1/L 概率延续。
    生成 length 长度的索引数组，元素 ∈ [0, n)。
    """
    if n <= 0 or length <= 0:
        return np.array([], dtype=int)
    p_new = 1.0 / max(1, block_length)
    out = np.empty(length, dtype=int)
    out[0] = rng.integers(0, n)
    starts = rng.random(length) < p_new
    for t in range(1, length):
        if starts[t]:
            out[t] = rng.integers(0, n)
        else:
            out[t] = (out[t - 1] + 1) % n
    return out


def bootstrap_mdd_pvalue(
    pre_returns: Union[np.ndarray, list],
    observed_mdd: float,
    *,
    horizon: int = DEFAULT_HORIZON,
    B: int = DEFAULT_B,
    L: int = DEFAULT_L,
    seed: int = 0,
) -> BootstrapResult:
    """
    检验 H0: anchor 后的 MDD 与 anchor 前 returns 同分布
    H1: anchor 后 MDD 显著更深（机构派发证据）

    Parameters
    ----------
    pre_returns : 1D array of daily log-returns BEFORE anchor (无 NaN)
    observed_mdd : 实际观测 60d max drawdown（负数）
    horizon : 评估窗口长度（与 observed_mdd 一致）
    B : bootstrap 重抽次数
    L : 平稳块长度
    seed : 随机种子（强制，保证复现性）

    Returns
    -------
    BootstrapResult，含 p_value（越小越异常）。
    """
    r = np.asarray(pre_returns, dtype=float)
    r = r[~np.isnan(r)]
    n_pre = len(r)

    if n_pre < MIN_PRE_DAYS_PARAMETRIC:
        return BootstrapResult(
            p_value=None, method="degenerated", n_pre=n_pre,
            block_length=L, n_resample=0, observed_mdd=observed_mdd,
            null_mdd_mean=float("nan"), null_mdd_std=float("nan"),
            z_score=float("nan"),
            notes=f"insufficient pre-period ({n_pre}<{MIN_PRE_DAYS_PARAMETRIC})",
        )

    if n_pre < MIN_PRE_DAYS_BOOTSTRAP:
        # 回退到 Magdon-Ismail 参数闭式
        sigma_d = float(np.std(r, ddof=1))
        if sigma_d <= 1e-9:
            return BootstrapResult(
                p_value=None, method="degenerated", n_pre=n_pre,
                block_length=L, n_resample=0, observed_mdd=observed_mdd,
                null_mdd_mean=float("nan"), null_mdd_std=float("nan"),
                z_score=float("nan"), notes="zero variance in pre-period",
            )
        mu = MAGDON_MEAN_COEF * sigma_d * math.sqrt(horizon)
        sd = MAGDON_STD_COEF * sigma_d * math.sqrt(horizon)
        z = (observed_mdd - mu) / sd
        # Gumbel 类近似（一阶矫正后用正态尾）
        from math import erf
        p = 0.5 * (1.0 + erf(z / math.sqrt(2.0)))
        return BootstrapResult(
            p_value=float(p), method="parametric", n_pre=n_pre,
            block_length=L, n_resample=0, observed_mdd=observed_mdd,
            null_mdd_mean=mu, null_mdd_std=sd, z_score=z,
            notes="Magdon-Ismail closed-form (insufficient bootstrap data)",
        )

    # —— 主路径：平稳 bootstrap ——
    rng = np.random.default_rng(seed)
    null_mdd = np.empty(B, dtype=float)
    for b in range(B):
        idx = _stationary_bootstrap_indices(n_pre, horizon, L, rng)
        sample_returns = r[idx]
        null_mdd[b] = _path_mdd(sample_returns)

    # 经验 p-value（左尾：MDD 更负→更异常）
    # 加 1 修正避免 p=0
    n_le = int(np.sum(null_mdd <= observed_mdd))
    p_value = (n_le + 1) / (B + 1)

    mu = float(null_mdd.mean())
    sd = float(null_mdd.std(ddof=1))
    z = (observed_mdd - mu) / sd if sd > 1e-9 else 0.0

    return BootstrapResult(
        p_value=p_value, method="bootstrap", n_pre=n_pre,
        block_length=L, n_resample=B, observed_mdd=observed_mdd,
        null_mdd_mean=mu, null_mdd_std=sd, z_score=z,
    )


def bh_fdr(p_values: np.ndarray, alpha: float = 0.10) -> np.ndarray:
    """
    Benjamini-Hochberg FDR 校正。
    返回 q-values（按原顺序）。
    """
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    if n == 0:
        return np.array([])
    order = np.argsort(p)
    ranked = p[order]
    # q_i = min over k>=i of (n / k * p_(k))
    q_sorted = np.minimum.accumulate((ranked * n / np.arange(1, n + 1))[::-1])[::-1]
    q_sorted = np.minimum(q_sorted, 1.0)
    out = np.empty(n)
    out[order] = q_sorted
    return out

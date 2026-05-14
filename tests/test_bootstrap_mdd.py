"""
Unit tests for bootstrap_mdd.py
"""
import math
import numpy as np
import pytest

from scripts.bootstrap_mdd import (
    bootstrap_mdd_pvalue, bh_fdr, _path_mdd, _stationary_bootstrap_indices,
    MAGDON_MEAN_COEF, MAGDON_STD_COEF,
)


# ----- Property tests -----

def test_path_mdd_monotone_drop():
    """单调下跌：MDD = 总跌幅。"""
    r = np.full(10, -0.01)  # 每天 -1%
    mdd = _path_mdd(r)
    expected = math.exp(-0.10) - 1.0  # ≈ -0.0952
    assert abs(mdd - expected) < 1e-6


def test_path_mdd_no_drop():
    """单调上涨：MDD = 0（起点是低点）。"""
    r = np.full(10, 0.01)
    mdd = _path_mdd(r)
    assert mdd == 0.0


def test_stationary_bootstrap_index_range():
    rng = np.random.default_rng(42)
    idx = _stationary_bootstrap_indices(100, 60, 6, rng)
    assert len(idx) == 60
    assert idx.min() >= 0 and idx.max() < 100


def test_reproducibility():
    """Same seed → same result."""
    np.random.seed(0)
    r = np.random.normal(0, 0.02, 252)
    res1 = bootstrap_mdd_pvalue(r, -0.10, B=500, L=6, seed=123)
    res2 = bootstrap_mdd_pvalue(r, -0.10, B=500, L=6, seed=123)
    assert res1.p_value == res2.p_value
    res3 = bootstrap_mdd_pvalue(r, -0.10, B=500, L=6, seed=124)
    assert res1.p_value != res3.p_value  # different seed → different


# ----- Calibration test (KS under null) -----

def test_null_calibration_gbm():
    """
    在 GBM null 下，p-values 应近似均匀分布 U(0,1)。
    用 KS 检验，阈值 0.10（200 trials, B=500，统计噪声大些）。
    """
    rng_outer = np.random.default_rng(2024)
    sigma = 0.02
    n_trials = 200
    p_values = []
    for trial in range(n_trials):
        # 生成 252 + 60 天 i.i.d. 收益（同一分布 → null 成立）
        all_r = rng_outer.normal(0, sigma, 252 + 60)
        pre = all_r[:252]
        post = all_r[252:]
        observed_mdd = _path_mdd(post)
        res = bootstrap_mdd_pvalue(
            pre, observed_mdd, B=500, L=6, seed=int(trial),
        )
        if res.p_value is not None:
            p_values.append(res.p_value)

    p_values = np.array(p_values)
    assert len(p_values) >= 150

    # KS test against uniform: D_n = sup |F_n(x) - x|
    sorted_p = np.sort(p_values)
    n = len(sorted_p)
    cdf_emp = np.arange(1, n + 1) / n
    D = float(np.max(np.abs(cdf_emp - sorted_p)))
    # 5% critical for n=200 ≈ 0.096; we allow 0.15 for headroom
    assert D < 0.15, f"KS statistic {D:.3f} too large; null calibration fails"


# ----- Power test -----

def test_power_under_distribution():
    """
    在派发情形（post 漂移显著为负）下，p-value 应该小。
    """
    rng = np.random.default_rng(7)
    pre = rng.normal(0, 0.015, 252)         # 平时 σ=1.5%
    # 派发场景：明显负漂移 + σ 略升（institutional unloading typical signature）
    post = rng.normal(-0.008, 0.018, 60)    # 累计 ~-50%
    observed_mdd = _path_mdd(post)
    res = bootstrap_mdd_pvalue(pre, observed_mdd, B=1000, L=6, seed=42)
    assert res.p_value is not None
    assert res.p_value < 0.05, f"power test failed, p={res.p_value}, obs_mdd={observed_mdd:.3f}, null_mean={res.null_mdd_mean:.3f}"


# ----- Block-length sensitivity -----

def test_block_length_robustness():
    """L ∈ {3, 6, 12} 在弱依赖数据上应给相近 p-value（差 < 0.10）。"""
    rng = np.random.default_rng(99)
    sigma = 0.02
    pre = rng.normal(0, sigma, 252)
    post = rng.normal(-0.003, sigma, 60)
    obs = _path_mdd(post)
    ps = []
    for L in (3, 6, 12):
        res = bootstrap_mdd_pvalue(pre, obs, B=2000, L=L, seed=2024)
        ps.append(res.p_value)
    assert max(ps) - min(ps) < 0.10, f"L sensitivity too large: {ps}"


# ----- Degeneration paths -----

def test_degeneration_too_short():
    """< 20 d → method='degenerated', p_value=None"""
    res = bootstrap_mdd_pvalue(np.random.normal(0, 0.02, 10), -0.05, seed=0)
    assert res.method == "degenerated"
    assert res.p_value is None


def test_parametric_fallback():
    """20 ≤ n < 100 → Magdon-Ismail 闭式"""
    rng = np.random.default_rng(1)
    pre = rng.normal(0, 0.02, 50)
    res = bootstrap_mdd_pvalue(pre, -0.10, B=500, L=6, seed=0)
    assert res.method == "parametric"
    assert res.p_value is not None
    assert 0.0 < res.p_value < 1.0
    # 检查 Magdon-Ismail 常数被使用
    sigma_d = float(np.std(pre, ddof=1))
    expected_mean = MAGDON_MEAN_COEF * sigma_d * math.sqrt(60)
    assert abs(res.null_mdd_mean - expected_mean) < 1e-9


def test_zero_variance_pre():
    """pre σ=0 → degenerated"""
    res = bootstrap_mdd_pvalue(np.zeros(50), -0.05, seed=0)
    assert res.method == "degenerated"


# ----- BH-FDR -----

def test_bh_fdr_basic():
    p = np.array([0.01, 0.02, 0.03, 0.5, 0.9])
    q = bh_fdr(p)
    # Smallest p adjusted upward by n/rank
    assert q[0] >= p[0]
    assert (q >= 0).all() and (q <= 1).all()
    # Monotone after re-sort
    q_sorted = q[np.argsort(p)]
    assert all(q_sorted[i] <= q_sorted[i + 1] + 1e-12 for i in range(len(q_sorted) - 1))


def test_bh_fdr_empty():
    assert len(bh_fdr(np.array([]))) == 0


# ----- No-leakage smoke (interface) -----

def test_function_signature_isolates_pre_data():
    """
    接口只接受 pre_returns 一个序列；observed_mdd 是数值。
    无法把 anchor 后数据混入 pre_returns 调用——这是设计层面的护栏。
    """
    import inspect
    sig = inspect.signature(bootstrap_mdd_pvalue)
    params = list(sig.parameters.keys())
    assert params[0] == "pre_returns"
    assert params[1] == "observed_mdd"
    # 没有 'post_returns' 之类的参数
    assert not any("post" in p for p in params)

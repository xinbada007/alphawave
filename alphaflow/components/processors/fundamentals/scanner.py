"""
Cross-Domain Fundamental Scanner（跨域基本面扫描器）
===================================================
设计哲学：检验科模式（Pathology Lab）
- 只输出冷静、客观、冷峻的多维度事实描述
- 绝不替 LLM 做判断：无 WARNING / DANGER / RISK / HEALTHY 等定性词
- 每条信号 = 一个跨域事实观察（observation）+ 支撑数值（metrics）

信号清单：
1. profit_vs_cashflow          — 利润表 × 现金流表（Sloan 应计异象）
2. dividend_vs_free_cashflow   — 融资现金流 × 经营现金流
3. growth_vs_margin_trend      — 增速 × 利润率趋势（McKinsey 增长质量）
4. solvency_stress             — 资产负债表 × 利润表（Altman Z 精神）
5. earnings_quality_composition — 经营利润 × 税前利润（核心利润纯度）
"""

from typing import Any, Dict, List, Optional


def _get(metrics: Dict[str, Any], domain: str, key: str) -> Optional[float]:
    """安全地从嵌套的语义域结构中提取指标值"""
    domain_data = metrics.get(domain)
    if isinstance(domain_data, dict):
        v = domain_data.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return None


# ==========================================
# 核心扫描函数
# ==========================================

def scan_fundamentals(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    扫描 MetricEngine 产出的 fundamental_metrics，检测跨域事实信号。

    Args:
        metrics: 来自 pack.distilled_features.fundamental_metrics 的嵌套字典

    Returns:
        信号列表，每条信号包含 id / observation / metrics
        若无信号触发，返回空列表
    """
    if not metrics:
        return []

    signals: List[Dict[str, Any]] = []

    # ── Signal 1: profit_vs_cashflow ──
    # 跨 利润表 × 现金流表：盈利含金量
    _scan_profit_vs_cashflow(metrics, signals)

    # ── Signal 2: dividend_vs_free_cashflow ──
    # 跨 融资现金流 × 经营现金流：派息可持续性
    _scan_dividend_vs_fcf(metrics, signals)

    # ── Signal 3: growth_vs_margin_trend ──
    # 跨 增速 × 利润率趋势：增长质量
    _scan_growth_vs_margin(metrics, signals)

    # ── Signal 4: solvency_stress ──
    # 跨 资产负债表 × 利润表：偿付压力
    _scan_solvency_stress(metrics, signals)

    # ── Signal 5: earnings_quality_composition ──
    # 跨 经营利润 × 税前利润：核心利润纯度
    _scan_earnings_quality(metrics, signals)

    return signals


# ==========================================
# 各信号的独立扫描实现
# ==========================================

def _scan_profit_vs_cashflow(
    metrics: Dict[str, Any], signals: List[Dict[str, Any]]
) -> None:
    """
    Signal 1: 盈利含金量背离
    学术原型: Sloan (1996) Accrual Anomaly, Beneish M-Score 核心因子
    逻辑: OCF/NI 偏离 1.0 超过 0.5 → 利润与现金流出现显著分歧
    """
    ocf_ratio = _get(metrics, "cashflow_quality_ttm", "ocf_to_net_income")
    if ocf_ratio is None:
        return

    deviation = round(ocf_ratio - 1.0, 4)
    if abs(deviation) <= 0.5:
        return

    signals.append({
        "id": "profit_vs_cashflow",
        "observation": (
            f"Operating cash flow is {ocf_ratio:.2f}x of net income, "
            f"deviating {abs(deviation):.2f} from parity (1.0x)"
        ),
        "metrics": {
            "ocf_to_net_income": ocf_ratio,
            "deviation_from_parity": round(deviation, 4),
        },
    })


def _scan_dividend_vs_fcf(
    metrics: Dict[str, Any], signals: List[Dict[str, Any]]
) -> None:
    """
    Signal 2: 派息可持续性
    行业原型: S&P / Moody's 信用评级派息压力测试
    逻辑: 派息率 > 80% 且 FCF Yield < 2% → 派息消耗了几乎全部甚至超过造血能力
    """
    payout = _get(metrics, "cashflow_quality_ttm", "dividend_payout_ratio")
    fcf_y = _get(metrics, "valuation_lcd", "fcf_yield")

    if payout is None or fcf_y is None:
        return
    if not (payout > 0.80 and fcf_y < 0.02):
        return

    signals.append({
        "id": "dividend_vs_free_cashflow",
        "observation": (
            f"Dividend payout ratio at {payout:.1%} "
            f"while free cash flow yield at {fcf_y:.1%}"
        ),
        "metrics": {
            "dividend_payout_ratio": payout,
            "fcf_yield": fcf_y,
        },
    })


def _scan_growth_vs_margin(
    metrics: Dict[str, Any], signals: List[Dict[str, Any]]
) -> None:
    """
    Signal 3: 增长质量
    行业原型: McKinsey "Growth that creates value" 框架
    逻辑: 营收增长 > 15% 但净利率同比萎缩超 2pp → 增收不增利
    """
    rev_g = _get(metrics, "growth", "revenue_yoy_pct")
    margin_d = _get(metrics, "trend_delta", "net_margin_delta")

    if rev_g is None or margin_d is None:
        return
    # growth 和 trend_delta 指标均为小数形式 (0.35 = 35%, 0.02 = 2pp)
    if not (rev_g > 0.15 and margin_d < -0.02):
        return

    signals.append({
        "id": "growth_vs_margin_trend",
        "observation": (
            f"Revenue grew {rev_g:.1%} YoY "
            f"while net margin contracted {abs(margin_d):.2%}"
        ),
        "metrics": {
            "revenue_yoy_pct": rev_g,
            "net_margin_delta": margin_d,
        },
    })


def _scan_solvency_stress(
    metrics: Dict[str, Any], signals: List[Dict[str, Any]]
) -> None:
    """
    Signal 4: 偿付压力
    行业原型: Altman Z-Score 精神 + ICR 信贷红线
    逻辑: 权益乘数 > 4 或 < 0（资不抵债），或利息覆盖倍数 < 1.5
    """
    em = _get(metrics, "balance_structure_latest", "equity_multiplier")
    icr = _get(metrics, "solvency_latest", "interest_coverage_ratio")

    observations = []
    signal_metrics = {}

    if em is not None:
        signal_metrics["equity_multiplier"] = em
        if em < 0:
            observations.append(
                f"Equity multiplier is negative ({em:.2f}x), "
                f"indicating total equity below zero"
            )
        elif em > 4.0:
            observations.append(
                f"Equity multiplier at {em:.2f}x "
                f"(assets are {em:.1f}x of equity)"
            )

    if icr is not None:
        signal_metrics["interest_coverage_ratio"] = icr
        if icr < 1.5:
            observations.append(
                f"Interest coverage ratio at {icr:.2f}x "
                f"(operating income covers {icr:.1f}x of interest expense)"
            )

    if not observations:
        return

    signals.append({
        "id": "solvency_stress",
        "observation": "; ".join(observations),
        "metrics": signal_metrics,
    })


def _scan_earnings_quality(
    metrics: Dict[str, Any], signals: List[Dict[str, Any]]
) -> None:
    """
    Signal 5: 核心利润纯度
    行业原型: IPO 审核标准 + CFA 盈利质量分析
    逻辑: 核心利润占税前利润 < 70% → 大量非经常性损益
    """
    cpr = _get(metrics, "earnings_quality_latest", "core_profit_ratio")
    gpa = _get(metrics, "earnings_quality_latest", "gross_profit_to_assets")

    if cpr is None:
        return
    if cpr >= 0.70:
        return

    signal_metrics = {"core_profit_ratio": cpr}
    if gpa is not None:
        signal_metrics["gross_profit_to_assets"] = gpa

    signals.append({
        "id": "earnings_quality_composition",
        "observation": (
            f"Core operating profit accounts for {cpr:.1%} of pre-tax income"
        ),
        "metrics": signal_metrics,
    })

#!/usr/bin/env python3
"""
audit_random_baseline.py
========================
Phase C: 对 Phase B 的 400 个 (ticker, anchor) 随机基线样本做大规模回归。

评估对象
--------
1. Product signal:
   - 在 anchor 当日（仅使用 anchor 及之前数据）运行 TechnicalAnalyzerRegistry
   - 取 composite_risk_profile.score / level
2. ProxyTruth:
   - 在完整 fixture 上，用 anchor 起未来 60d + market benchmark 评估 R4 ProxyTruth

输出
----
tests/fixtures/random_baseline/audit_results.csv
tests/fixtures/random_baseline/audit_report.txt

注意
----
这是代理真值评估，不声称观测到了机构真实持仓/出货；所有结论均在
ProxyTruth H1-H5 + R4 bootstrap 假设下成立。
"""
from __future__ import annotations

import csv
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.proxy_truth import evaluate as proxy_evaluate  # noqa: E402
from alphaflow.core.schema import DataFrameModel, ResearchPack  # noqa: E402
from alphaflow.components.processors.techniques.registry import TechnicalAnalyzerRegistry  # noqa: E402
from tests.test_golden_samples import (  # noqa: E402
    extract_score,
    extract_level,
    primary_latest_tier,
    count_extreme_anomalies,
)


BASE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "tests", "fixtures", "random_baseline"
)
ANCHORS_CSV = os.path.join(BASE_DIR, "ticker_anchors.csv")
RESULTS_CSV = os.path.join(BASE_DIR, "audit_results.csv")
REPORT_TXT = os.path.join(BASE_DIR, "audit_report.txt")

BENCHMARK_DIR = os.path.join(
    os.path.dirname(__file__), "..", "tests", "fixtures", "golden_samples", "_benchmark"
)
BENCHMARK_FILE = {
    "US": "SPY.csv",
    "HK": "_HSI.csv",
    "CN": "000300_SS.csv",
}

PRODUCT_SCORE_THRESHOLD = 45.0
PRODUCT_LEVEL_POSITIVE = {"ELEVATED", "HIGH", "CRITICAL"}
LEVEL_RANK = {"LOW": 0, "MODERATE": 1, "ELEVATED": 2, "HIGH": 3, "CRITICAL": 4}


@dataclass
class AuditRow:
    market: str
    ticker: str
    anchor_requested: str
    anchor_actual: str
    source: str
    product_score: Optional[float]
    product_level: Optional[str]
    product_tier: Optional[str]
    extreme_60d: int
    product_positive_score: bool
    product_positive_level: bool
    proxy_positive: bool
    proxy_intensity: str
    proxy_pattern: str
    proxy_confidence: float
    abs_dd_60d: Optional[float]
    excess_dd: Optional[float]
    p_value: Optional[float]
    vol_ratio: Optional[float]
    neg_day_ratio: Optional[float]
    days_to_trough: Optional[int]
    recovery_ratio: Optional[float]
    boot_method: Optional[str]
    status: str
    note: str


def sanitize(ticker: str) -> str:
    return ticker.replace(".", "_").replace("^", "_")


def load_price(ticker: str) -> pd.DataFrame:
    path = os.path.join(BASE_DIR, f"{sanitize(ticker)}.csv")
    df = pd.read_csv(path, parse_dates=["date"])
    for col in ("open", "high", "low", "close", "volume", "amount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def load_benchmark(market: str) -> pd.DataFrame:
    path = os.path.join(BENCHMARK_DIR, BENCHMARK_FILE[market])
    df = pd.read_csv(path, parse_dates=["date"])
    for col in ("open", "high", "low", "close", "volume", "amount"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def run_analyzers_with_benchmark(
    symbol: str,
    stock_df: pd.DataFrame,
    benchmark_df: pd.DataFrame,
    market: str,
) -> Dict[str, Any]:
    """Run product analyzers with benchmark history truncated to the same anchor."""
    pack = ResearchPack(
        symbol=symbol,
        market_data=DataFrameModel.from_df(stock_df),
        market_data_meta={"source": "random_baseline_fixture", "rows": len(stock_df)},
        benchmark_data=DataFrameModel.from_df(benchmark_df),
        benchmark_meta={
            "status": "ok",
            "benchmark_symbol": {"US": "SPY", "HK": "^HSI", "CN": "000300.SS"}[market],
            "source": "random_baseline_benchmark_fixture",
        },
    )
    return TechnicalAnalyzerRegistry.run_all(stock_df, pack, config={})


def actual_anchor(df: pd.DataFrame, anchor: str) -> Optional[pd.Timestamp]:
    requested = pd.Timestamp(anchor)
    mask = df["date"] <= requested
    if not mask.any():
        return None
    return pd.Timestamp(df.loc[mask[mask].index[-1], "date"])


def safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
        return int(v)
    except Exception:
        return None


def evaluate_one(row: Dict[str, str], benchmarks: Dict[str, pd.DataFrame]) -> AuditRow:
    market = row["market"]
    ticker = row["ticker"]
    anchor_req = row["anchor"]
    source = row["source"]

    try:
        df = load_price(ticker)
    except Exception as exc:
        return AuditRow(
            market, ticker, anchor_req, "", source, None, None, None, 0,
            False, False, False, "NONE", "flat", 0.0, None, None, None,
            None, None, None, None, None, "LOAD_ERROR", f"{type(exc).__name__}: {exc}",
        )

    anchor = actual_anchor(df, anchor_req)
    if anchor is None:
        return AuditRow(
            market, ticker, anchor_req, "", source, None, None, None, 0,
            False, False, False, "NONE", "flat", 0.0, None, None, None,
            None, None, None, None, None, "NO_ANCHOR", "no trading day <= requested anchor",
        )

    hist = df[df["date"] <= anchor].reset_index(drop=True)
    if len(hist) < 60:
        return AuditRow(
            market, ticker, anchor_req, anchor.date().isoformat(), source,
            None, None, None, 0, False, False, False, "NONE", "flat", 0.0,
            None, None, None, None, None, None, None, None, "SHORT_HISTORY",
            f"only {len(hist)} rows before anchor",
        )

    try:
        bench_hist = benchmarks[market][benchmarks[market]["date"] <= anchor].reset_index(drop=True)
        profile = run_analyzers_with_benchmark(ticker, hist, bench_hist, market)
        score = safe_float(extract_score(profile))
        level = extract_level(profile)
        tier = primary_latest_tier(profile)
        extreme = count_extreme_anomalies(profile)
    except Exception as exc:
        return AuditRow(
            market, ticker, anchor_req, anchor.date().isoformat(), source,
            None, None, None, 0, False, False, False, "NONE", "flat", 0.0,
            None, None, None, None, None, None, None, None, "ANALYZER_ERROR",
            f"{type(exc).__name__}: {exc}",
        )

    try:
        proxy = proxy_evaluate(stock=df, benchmark=benchmarks[market], base_day=anchor)
        ev = proxy.evidence or {}
        proxy_positive = bool(proxy.is_distribution)
        proxy_intensity = proxy.intensity
        proxy_pattern = proxy.pattern
        proxy_confidence = float(proxy.confidence)
    except Exception as exc:
        return AuditRow(
            market, ticker, anchor_req, anchor.date().isoformat(), source,
            score, level, tier, extreme,
            (score is not None and score >= PRODUCT_SCORE_THRESHOLD),
            level in PRODUCT_LEVEL_POSITIVE,
            False, "NONE", "flat", 0.0, None, None, None, None, None, None, None,
            None, "PROXY_ERROR", f"{type(exc).__name__}: {exc}",
        )

    product_positive_score = score is not None and score >= PRODUCT_SCORE_THRESHOLD
    product_positive_level = level in PRODUCT_LEVEL_POSITIVE

    return AuditRow(
        market=market,
        ticker=ticker,
        anchor_requested=anchor_req,
        anchor_actual=anchor.date().isoformat(),
        source=source,
        product_score=score,
        product_level=level,
        product_tier=tier,
        extreme_60d=extreme,
        product_positive_score=product_positive_score,
        product_positive_level=product_positive_level,
        proxy_positive=proxy_positive,
        proxy_intensity=proxy_intensity,
        proxy_pattern=proxy_pattern,
        proxy_confidence=proxy_confidence,
        abs_dd_60d=safe_float(ev.get("abs_dd_60d")),
        excess_dd=safe_float(ev.get("excess_dd")),
        p_value=safe_float(ev.get("p_value")),
        vol_ratio=safe_float(ev.get("vol_ratio")),
        neg_day_ratio=safe_float(ev.get("neg_day_ratio")),
        days_to_trough=safe_int(ev.get("days_to_trough")),
        recovery_ratio=safe_float(ev.get("recovery_ratio")),
        boot_method=ev.get("boot_method"),
        status="OK",
        note="",
    )


def confusion(rows: Iterable[AuditRow], *, use_level: bool = False) -> Dict[str, int]:
    tp = fp = tn = fn = 0
    for r in rows:
        if r.status != "OK":
            continue
        pred = r.product_positive_level if use_level else r.product_positive_score
        truth = r.proxy_positive
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif not pred and not truth:
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def metrics(c: Dict[str, int]) -> Dict[str, float]:
    tp, fp, tn, fn = c["tp"], c["fp"], c["tn"], c["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
    }


def roc_by_score(rows: List[AuditRow]) -> List[Tuple[float, float, float, int, int, int, int]]:
    thresholds = [0, 20, 27.5, 35, 45, 55, 65, 75]
    out = []
    ok_rows = [r for r in rows if r.status == "OK" and r.product_score is not None]
    for th in thresholds:
        tp = fp = tn = fn = 0
        for r in ok_rows:
            pred = float(r.product_score or 0) >= th
            truth = r.proxy_positive
            if pred and truth:
                tp += 1
            elif pred and not truth:
                fp += 1
            elif not pred and not truth:
                tn += 1
            else:
                fn += 1
        tpr = tp / (tp + fn) if tp + fn else 0.0
        fpr = fp / (fp + tn) if fp + tn else 0.0
        out.append((th, tpr, fpr, tp, fp, tn, fn))
    return out


def write_results(rows: List[AuditRow]) -> None:
    fields = list(AuditRow.__dataclass_fields__.keys())
    with open(RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({field: getattr(r, field) for field in fields})


def fmt_pct(x: float) -> str:
    return f"{x:.1%}"


def build_report(rows: List[AuditRow]) -> str:
    ok = [r for r in rows if r.status == "OK"]
    status_counts = Counter(r.status for r in rows)
    truth_counts = Counter(r.proxy_intensity for r in ok)
    source_counts = Counter(r.source for r in ok)

    c_score = confusion(ok, use_level=False)
    m_score = metrics(c_score)
    c_level = confusion(ok, use_level=True)
    m_level = metrics(c_level)

    lines: List[str] = []
    lines.append("=" * 120)
    lines.append("Random Baseline Audit — 400 anchors vs ProxyTruth R4")
    lines.append("=" * 120)
    lines.append(f"Total rows: {len(rows)}  OK: {len(ok)}  Status: {dict(status_counts)}")
    lines.append(f"ProxyTruth intensity counts: {dict(truth_counts)}")
    lines.append(f"Anchor source counts: {dict(source_counts)}")
    lines.append("")
    lines.append("Binary truth: ProxyTruth.is_distribution == TRUE (STRONG or MILD)")
    lines.append(f"Product positive(score): composite_risk.score >= {PRODUCT_SCORE_THRESHOLD:.1f}")
    lines.append("Product positive(level): composite_risk.level in {ELEVATED,HIGH,CRITICAL}")
    lines.append("")
    lines.append("Confusion — score threshold")
    lines.append(f"  TP={c_score['tp']} FP={c_score['fp']} TN={c_score['tn']} FN={c_score['fn']}")
    lines.append(
        "  precision={precision} recall={recall} specificity={specificity} f1={f1}".format(
            **{k: fmt_pct(v) for k, v in m_score.items()}
        )
    )
    lines.append("")
    lines.append("Confusion — level threshold")
    lines.append(f"  TP={c_level['tp']} FP={c_level['fp']} TN={c_level['tn']} FN={c_level['fn']}")
    lines.append(
        "  precision={precision} recall={recall} specificity={specificity} f1={f1}".format(
            **{k: fmt_pct(v) for k, v in m_level.items()}
        )
    )
    lines.append("")
    lines.append("ROC by composite_risk.score threshold")
    lines.append("  threshold   TPR(recall)   FPR      TP  FP  TN  FN")
    for th, tpr, fpr, tp, fp, tn, fn in roc_by_score(ok):
        lines.append(f"  {th:9.1f}   {tpr:10.1%}   {fpr:6.1%}   {tp:3} {fp:3} {tn:3} {fn:3}")

    lines.append("")
    lines.append("By market — score threshold")
    lines.append("  market   n   truth+  pred+   precision recall specificity")
    for market in ("US", "HK", "CN"):
        sub = [r for r in ok if r.market == market]
        c = confusion(sub, use_level=False)
        m = metrics(c)
        truth_pos = c["tp"] + c["fn"]
        pred_pos = c["tp"] + c["fp"]
        lines.append(
            f"  {market:<6} {len(sub):3} {truth_pos:7} {pred_pos:6} "
            f"{m['precision']:9.1%} {m['recall']:6.1%} {m['specificity']:11.1%}"
        )

    lines.append("")
    lines.append("By source — score threshold")
    lines.append("  source       n   truth+  pred+   precision recall specificity")
    for source in sorted(source_counts):
        sub = [r for r in ok if r.source == source]
        c = confusion(sub, use_level=False)
        m = metrics(c)
        truth_pos = c["tp"] + c["fn"]
        pred_pos = c["tp"] + c["fp"]
        lines.append(
            f"  {source:<11} {len(sub):3} {truth_pos:7} {pred_pos:6} "
            f"{m['precision']:9.1%} {m['recall']:6.1%} {m['specificity']:11.1%}"
        )

    false_negatives = sorted(
        [r for r in ok if r.proxy_positive and not r.product_positive_score],
        key=lambda r: (r.proxy_intensity != "STRONG", r.abs_dd_60d or 0),
    )
    false_positives = sorted(
        [r for r in ok if (not r.proxy_positive) and r.product_positive_score],
        key=lambda r: -(r.product_score or 0),
    )

    lines.append("")
    lines.append("Top false negatives (ProxyTruth TRUE, product score < threshold)")
    lines.append("  ticker anchor market src truth score level abs_dd excess_dd p volR neg%")
    for r in false_negatives[:25]:
        lines.append(
            f"  {r.ticker:<8} {r.anchor_actual:<10} {r.market:<2} {r.source:<11} "
            f"{r.proxy_intensity:<6} {r.product_score!s:<5} {r.product_level!s:<8} "
            f"{(r.abs_dd_60d or 0):+.1%} {(r.excess_dd or 0):+.1%} "
            f"{(r.p_value if r.p_value is not None else -1):.3f} "
            f"{(r.vol_ratio if r.vol_ratio is not None else 0):.2f} "
            f"{(r.neg_day_ratio if r.neg_day_ratio is not None else 0):.1%}"
        )

    lines.append("")
    lines.append("Top false positives (ProxyTruth FALSE, product score >= threshold)")
    lines.append("  ticker anchor market src score level abs_dd excess_dd p volR neg%")
    for r in false_positives[:25]:
        lines.append(
            f"  {r.ticker:<8} {r.anchor_actual:<10} {r.market:<2} {r.source:<11} "
            f"{r.product_score!s:<5} {r.product_level!s:<8} "
            f"{(r.abs_dd_60d or 0):+.1%} {(r.excess_dd or 0):+.1%} "
            f"{(r.p_value if r.p_value is not None else -1):.3f} "
            f"{(r.vol_ratio if r.vol_ratio is not None else 0):.2f} "
            f"{(r.neg_day_ratio if r.neg_day_ratio is not None else 0):.1%}"
        )

    lines.append("")
    lines.append(f"CSV: {RESULTS_CSV}")
    lines.append(f"Report: {REPORT_TXT}")
    lines.append("=" * 120)
    return "\n".join(lines)


def main() -> int:
    if not os.path.exists(ANCHORS_CSV):
        print(f"ERROR: missing {ANCHORS_CSV}. Run sample_random_baseline.py first.")
        return 2

    benchmarks = {market: load_benchmark(market) for market in BENCHMARK_FILE}

    with open(ANCHORS_CSV) as f:
        anchor_rows = list(csv.DictReader(f))

    rows: List[AuditRow] = []
    total = len(anchor_rows)
    for i, row in enumerate(anchor_rows, 1):
        result = evaluate_one(row, benchmarks)
        rows.append(result)
        if i % 25 == 0 or i == total:
            print(f"  [{i:3}/{total}] processed; last={result.ticker} {result.anchor_requested} {result.status}")

    write_results(rows)
    report = build_report(rows)
    with open(REPORT_TXT, "w") as f:
        f.write(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

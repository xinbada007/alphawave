#!/usr/bin/env python3
"""
audit_random_detection_window.py
================================
检测窗口审计：解决 random anchor 单点评估的时点错配问题。

对每个 Phase C anchor，在 anchor 后若干检查点（0/5/10/20/40/60 个交易日）
只使用截至检查点当天的历史行情运行产品，观察是否在 60D 路径风险展开过程中
触发 composite_risk.score >= 45。

这不是用未来数据做产品输入；未来只用于审计“在风险展开后多久能被捕捉”。
"""
from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.audit_random_baseline import (  # noqa: E402
    ANCHORS_CSV,
    BASE_DIR,
    load_benchmark,
    load_price,
    actual_anchor,
    run_analyzers_with_benchmark,
    evaluate_one,
    extract_score,
    extract_level,
)


CHECKPOINTS = (0, 5, 10, 20, 40, 60)
SCORE_THRESHOLD = 45.0
OUT_CSV = os.path.join(BASE_DIR, "detection_window_results.csv")
OUT_REPORT = os.path.join(BASE_DIR, "detection_window_report.txt")


@dataclass
class DetectionRow:
    market: str
    ticker: str
    anchor_requested: str
    anchor_actual: str
    source: str
    proxy_positive: bool
    proxy_intensity: str
    abs_dd_60d: Optional[float]
    peak_score: Optional[float]
    peak_level: Optional[str]
    peak_dt: Optional[int]
    detected: bool
    status: str
    note: str


def detect_one(row: Dict[str, str], benchmarks: Dict[str, pd.DataFrame]) -> DetectionRow:
    market = row["market"]
    ticker = row["ticker"]
    anchor_req = row["anchor"]
    source = row["source"]

    truth = evaluate_one(row, benchmarks)
    if truth.status != "OK":
        return DetectionRow(
            market, ticker, anchor_req, truth.anchor_actual, source,
            False, "NONE", None, None, None, None, False, truth.status, truth.note,
        )

    df = load_price(ticker)
    anchor = pd.Timestamp(truth.anchor_actual)
    idxs = df.index[df["date"] <= anchor]
    if len(idxs) == 0:
        return DetectionRow(
            market, ticker, anchor_req, "", source,
            truth.proxy_positive, truth.proxy_intensity, truth.abs_dd_60d,
            None, None, None, False, "NO_ANCHOR", "no anchor index",
        )
    anchor_idx = int(idxs[-1])

    peak_score: Optional[float] = None
    peak_level: Optional[str] = None
    peak_dt: Optional[int] = None

    for dt in CHECKPOINTS:
        i = min(anchor_idx + dt, len(df) - 1)
        hist = df.iloc[: i + 1].reset_index(drop=True)
        if len(hist) < 60:
            continue
        day = pd.Timestamp(hist.iloc[-1]["date"])
        bench_hist = benchmarks[market][benchmarks[market]["date"] <= day].reset_index(drop=True)
        try:
            profile = run_analyzers_with_benchmark(ticker, hist, bench_hist, market)
            score = extract_score(profile)
            level = extract_level(profile)
        except Exception:
            continue
        if score is None:
            continue
        score_f = float(score)
        if peak_score is None or score_f > peak_score:
            peak_score = score_f
            peak_level = level
            peak_dt = dt

    detected = bool(peak_score is not None and peak_score >= SCORE_THRESHOLD)
    return DetectionRow(
        market, ticker, anchor_req, truth.anchor_actual, source,
        truth.proxy_positive, truth.proxy_intensity, truth.abs_dd_60d,
        peak_score, peak_level, peak_dt, detected, "OK", "",
    )


def main() -> int:
    benchmarks = {m: load_benchmark(m) for m in ("US", "HK", "CN")}
    with open(ANCHORS_CSV) as f:
        rows = list(csv.DictReader(f))

    out: List[DetectionRow] = []
    for i, row in enumerate(rows, 1):
        r = detect_one(row, benchmarks)
        out.append(r)
        if i % 25 == 0 or i == len(rows):
            print(f"  [{i:3}/{len(rows)}] {r.ticker} {r.anchor_requested} {r.status}")

    fields = list(DetectionRow.__dataclass_fields__.keys())
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in out:
            w.writerow({k: getattr(r, k) for k in fields})

    ok = [r for r in out if r.status == "OK"]
    tp = sum(r.detected and r.proxy_positive for r in ok)
    fp = sum(r.detected and not r.proxy_positive for r in ok)
    tn = sum((not r.detected) and (not r.proxy_positive) for r in ok)
    fn = sum((not r.detected) and r.proxy_positive for r in ok)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    strong = [r for r in ok if r.proxy_intensity == "STRONG"]
    strong_recall = sum(r.detected for r in strong) / len(strong) if strong else 0.0

    report = "\n".join([
        "=" * 100,
        "Detection Window Audit — checkpoints 0/5/10/20/40/60d",
        "=" * 100,
        f"OK={len(ok)} status_counts={pd.Series([r.status for r in out]).value_counts().to_dict()}",
        f"TP={tp} FP={fp} TN={tn} FN={fn}",
        f"precision={precision:.1%} recall={recall:.1%} specificity={specificity:.1%}",
        f"STRONG recall={sum(r.detected for r in strong)}/{len(strong)} = {strong_recall:.1%}",
        "",
        "Peak detection dt distribution (detected TRUE only):",
        str(pd.Series([r.peak_dt for r in ok if r.detected]).value_counts().sort_index().to_dict()),
        "",
        f"CSV: {OUT_CSV}",
        f"Report: {OUT_REPORT}",
        "=" * 100,
    ])
    with open(OUT_REPORT, "w") as f:
        f.write(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())

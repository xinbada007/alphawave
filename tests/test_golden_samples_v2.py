#!/usr/bin/env python3
"""
test_golden_samples_v2.py
=========================
独立验证集（与 v1 不重叠的行业 / 事件类型）。

派发组（5）：
  - BABA   2020-11-03  蚂蚁集团 IPO 暂停后阿里暴跌
  - SNAP   2022-05-24  利润预警，盘后 -43%
  - COIN   2022-05-11  Q1 财报雷 + 宏观恐慌
  - 9988.HK 2020-12-24 阿里反垄断立案
  - TSLA   2020-09-08  -21% 单日（标普纳入失败 + 增发）

正常组（5）：
  - JNJ / KO / PEP    2024-09-30   美国防御股
  - 0066.HK           2024-09-30   港铁
  - 600028.SS         2024-08-30   中石化（避开 9/24 中国刺激政策）

复用 test_golden_samples 中的所有 helper —— 该文件只声明样本 + 跑测试。
"""
from __future__ import annotations

import os
import sys
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.test_golden_samples import (  # noqa: E402
    GoldenSample, CaseResult, test_one,
    DIST_SCORE_MIN, NORMAL_SCORE_MAX,
)


DISTRIBUTION_SAMPLES_V2 = (
    GoldenSample("BABA_v2",     "BABA",      "2020-11-03", "distribution", "BABA Ant IPO suspension"),
    GoldenSample("SNAP_v2",     "SNAP",      "2022-05-24", "distribution", "Snap profit warning"),
    GoldenSample("COIN_v2",     "COIN",      "2022-05-11", "distribution", "Coinbase Q1 meltdown"),
    GoldenSample("PTON_v2",     "PTON",      "2022-01-20", "distribution", "Peloton production halt -24%"),
    GoldenSample("TSLA_v2",     "TSLA",      "2020-09-08", "distribution", "TSLA SP500 rejection -21%"),
)
NORMAL_SAMPLES_V2 = (
    GoldenSample("JNJ_normal_v2",       "JNJ",       "2024-09-30", "normal", "Johnson & Johnson"),
    GoldenSample("KO_normal_v2",        "KO",        "2024-09-30", "normal", "Coca-Cola"),
    GoldenSample("PEP_normal_v2",       "PEP",       "2024-09-30", "normal", "PepsiCo"),
    GoldenSample("0066_HK_normal_v2",   "0066.HK",   "2024-08-30", "normal", "MTR pre-stimulus"),
    GoldenSample("600028_SS_normal_v2", "600028.SH", "2024-08-30", "normal", "Sinopec pre-stimulus"),
)


def main() -> int:
    print("=" * 102)
    print("Golden Sample Regression V2 — independent industry / event coverage")
    print(f"  thresholds (inherited from v1): DIST_SCORE_MIN={DIST_SCORE_MIN}  "
          f"NORMAL_SCORE_MAX={NORMAL_SCORE_MAX}")
    print("=" * 102)

    results: List[CaseResult] = []
    for s in DISTRIBUTION_SAMPLES_V2 + NORMAL_SAMPLES_V2:
        results.append(test_one(s))

    print(f"\n{'alias':<24}{'symbol':<14}{'class':<14}{'score':>7}  "
          f"{'level':<10}{'tier_now':<10}{'extreme':>8}{'sigs':>6}  status")
    print("-" * 102)
    for r in results:
        score_str = f"{r.score:6.1f}" if r.score is not None else "  None"
        lvl = r.level or "-"
        tier = r.primary_tier or "-"
        status = "✅ PASS" if r.passed else "❌ FAIL"
        print(f"{r.alias:<24}{r.symbol:<14}{r.klass:<14}{score_str}  "
              f"{lvl:<10}{tier:<10}{r.extreme_count:>8}{r.n_signals:>6}  {status}")
        if r.note:
            print(f"  ↳ {r.note}")

    n_pass = sum(1 for r in results if r.passed)
    n_total = len(results)
    print("\n" + "=" * 102)
    print(f"  Total: {n_total}  Passed: {n_pass}  Failed: {n_total - n_pass}")
    print("=" * 102)

    return 0 if n_pass == n_total else 1


if __name__ == "__main__":
    sys.exit(main())

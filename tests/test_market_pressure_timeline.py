from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alphaflow.components.processors.techniques.analyzers.market_pressure_timeline import (  # noqa: E402
    MarketPressureTimelineProfiler,
)
from alphaflow.components.processors.techniques.analyzers.market_pressure_timeline import (  # noqa: E402
    metrics,
)
from alphaflow.components.processors.techniques.analyzers.market_pressure_timeline.signal import (  # noqa: E402
    build_market_pressure_signal,
)
from alphaflow.components.processors.techniques.analyzers.market_pressure_timeline.config import (  # noqa: E402
    BEHAVIOR_RELATIVE_UNDERPERFORMANCE,
    EVENT_TRIGGER_SCORE,
    SIGNAL_STATE_ACTIVE_HIGH,
    SIGNAL_STATE_FAILED_RECOVERY,
    SIGNAL_STATE_HISTORICAL_ONLY,
    SIGNAL_STATE_NO_RECENT,
)
from alphaflow.components.processors.techniques.registry import TechnicalAnalyzerRegistry  # noqa: E402
from alphaflow.core.acl.mappings.enums import MarketType  # noqa: E402
from alphaflow.core.schema import ResearchPack  # noqa: E402
from alphaflow.core.schema.models import DataFrameModel  # noqa: E402


def _make_market_pressure_pair(n: int = 260):
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    close = np.full(n, 100.0)

    close[:70] = 100.0 + np.sin(np.linspace(0, 4, 70)) * 0.4
    close[70:80] = np.linspace(100.0, 110.0, 10)
    close[80:106] = np.linspace(108.0, 86.0, 26)
    for idx in range(84, 106, 6):
        close[idx] += 1.8
    close[106:132] = np.linspace(86.5, 103.0, 26)
    close[132:190] = 103.0 + np.sin(np.linspace(0, 5, 58)) * 0.5
    close[190:] = np.linspace(103.0, 76.0, n - 190)
    for idx in range(195, n, 7):
        close[idx] += 1.5

    returns = pd.Series(close).pct_change().fillna(0.0)
    volume = np.full(n, 1_000_000.0)
    volume[returns < 0] = 2_250_000.0
    volume[returns > 0] = 750_000.0

    high = close * 1.012
    low = close * 0.988
    down_mask = returns.to_numpy() < 0
    high[down_mask] = close[down_mask] * 1.030
    low[down_mask] = close[down_mask] * 0.995

    stock = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": close * 1.004,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "amount": close * volume,
    })
    benchmark_close = 100.0 + np.linspace(0.0, 5.0, n)
    benchmark = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": benchmark_close,
        "high": benchmark_close * 1.006,
        "low": benchmark_close * 0.994,
        "close": benchmark_close,
        "volume": np.full(n, 10_000_000.0),
    })
    return stock, benchmark


def _benchmark_meta():
    return {"status": "ok", "benchmark_symbol": "SPY", "source": "fixture"}


def _make_stable_pair(n: int = 260):
    rng = np.random.default_rng(17)
    dates = pd.date_range("2024-01-02", periods=n, freq="B").strftime("%Y-%m-%d")
    stock_close = 100.0 * np.cumprod(1.0 + rng.normal(0.0002, 0.003, n))
    benchmark_close = 100.0 * np.cumprod(1.0 + rng.normal(0.0002, 0.002, n))
    stock = pd.DataFrame({
        "date": dates,
        "open": stock_close,
        "high": stock_close * 1.01,
        "low": stock_close * 0.99,
        "close": stock_close,
        "volume": 1_000_000.0 * (1.0 + rng.normal(0.0, 0.04, n)),
    })
    benchmark = pd.DataFrame({
        "date": dates,
        "open": benchmark_close,
        "high": benchmark_close * 1.006,
        "low": benchmark_close * 0.994,
        "close": benchmark_close,
        "volume": np.full(n, 10_000_000.0),
    })
    return stock, benchmark


def test_daily_evidence_uses_no_future_rows():
    stock, benchmark = _make_market_pressure_pair()
    target_idx = 100

    full_prepared, _ = metrics.attach_benchmark_columns(stock, benchmark)
    full_points = metrics.compute_daily_evidence_points(full_prepared)

    truncated_stock = stock.iloc[:target_idx + 1].copy()
    truncated_benchmark = benchmark.iloc[:target_idx + 1].copy()
    truncated_prepared, _ = metrics.attach_benchmark_columns(truncated_stock, truncated_benchmark)
    truncated_points = metrics.compute_daily_evidence_points(truncated_prepared)

    full_point = full_points[target_idx]
    truncated_point = truncated_points[target_idx]
    assert full_point.date == truncated_point.date
    assert full_point.score == truncated_point.score
    assert full_point.observed_behaviors == truncated_point.observed_behaviors
    assert full_point.metrics == truncated_point.metrics
    assert full_point.score >= EVENT_TRIGGER_SCORE


def test_profiler_segments_multiple_objective_events():
    stock, benchmark = _make_market_pressure_pair()
    out = MarketPressureTimelineProfiler().analyze(
        stock,
        benchmark_df=benchmark,
        benchmark_meta=_benchmark_meta(),
        market_type=MarketType.US,
    )

    assert out["data_quality"]["benchmark_available"] is True
    assert out["summary"]["event_count"] >= 2, out["events"]
    assert out["summary"]["active_event"] is True
    assert out["events"][-1]["status"] == "active"
    assert any(e["end_date"] is not None for e in out["events"][:-1])

    latest_behaviors = set(out["events"][-1]["observed_behaviors"])
    assert BEHAVIOR_RELATIVE_UNDERPERFORMANCE in latest_behaviors
    assert "down_day_volume_concentration" in latest_behaviors

    signal = out["market_pressure_signal"]
    assert signal["state"] == SIGNAL_STATE_ACTIVE_HIGH
    assert signal["source_event_id"] == out["events"][-1]["event_id"]
    assert signal["confidence"] == "HIGH"
    assert signal["evidence_breadth"] >= 3
    assert signal["metric_confirmations"]["relative_underperformance_confirmed"] is True
    assert "active_event" in signal["reason_codes"]
    assert "confirmed distribution" not in signal["interpretation_note"].lower()


def test_profiler_degrades_without_benchmark_but_keeps_absolute_timeline():
    stock, _benchmark = _make_market_pressure_pair()
    out = MarketPressureTimelineProfiler().analyze(
        stock,
        benchmark_df=None,
        benchmark_meta=None,
        market_type=MarketType.US,
    )

    assert out["data_quality"]["benchmark_available"] is False
    assert out["summary"]["event_count"] >= 1
    behaviors = {b for event in out["events"] for b in event["observed_behaviors"]}
    assert BEHAVIOR_RELATIVE_UNDERPERFORMANCE not in behaviors
    signal = out["market_pressure_signal"]
    assert signal["confidence"] != "HIGH"
    assert signal["metric_confirmations"]["relative_underperformance_confirmed"] is False
    assert "benchmark_unavailable" in signal["reason_codes"]


def test_profiler_output_is_json_safe_and_objective_language():
    stock, benchmark = _make_market_pressure_pair()
    out = MarketPressureTimelineProfiler({"daily_points_max": 5}).analyze(
        stock,
        benchmark_df=benchmark,
        benchmark_meta=_benchmark_meta(),
        market_type=MarketType.US,
    )

    encoded = json.dumps(out, allow_nan=False)
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert len(out["daily_points"]) <= 5
    assert out["data_quality"]["daily_points_truncated"] is True
    forbidden = ("主力", "砸盘", "跑路", "institutional_selling", "manipulation")
    assert all(word not in encoded for word in forbidden)
    assert "observable market pressure patterns" in out["interpretation_note"]


def test_stable_market_behavior_does_not_form_events():
    stock, benchmark = _make_stable_pair()
    out = MarketPressureTimelineProfiler().analyze(
        stock,
        benchmark_df=benchmark,
        benchmark_meta=_benchmark_meta(),
        market_type=MarketType.US,
    )

    assert out["summary"]["event_count"] == 0
    assert out["summary"]["total_evidence_days"] == 0
    assert out["events"] == []
    assert out["market_pressure_signal"]["state"] == SIGNAL_STATE_NO_RECENT
    assert out["market_pressure_signal"]["source_event_id"] is None


def test_signal_state_machine_handles_historical_and_failed_recovery():
    historical = {
        "event_id": "mpe_001",
        "status": "resolved",
        "last_evidence_date": "2024-01-10",
        "duration_days": 10,
        "peak_pressure_score": 100,
        "intensity": "HIGH",
        "observed_behaviors": [
            "down_day_volume_concentration",
            "price_drawdown_from_peak",
            "relative_underperformance",
            "failed_recovery",
        ],
        "metrics": {
            "max_drawdown": -0.25,
            "down_day_volume_share": 0.7,
            "relative_underperformance": -0.2,
            "recovery_ratio": 0.2,
            "quiet_days_after": 80,
        },
    }
    failed = dict(historical)
    failed.update({
        "event_id": "mpe_002",
        "status": "failed_recovery",
        "last_evidence_date": "2024-04-01",
    })
    failed["metrics"] = dict(historical["metrics"], quiet_days_after=8)

    hist_signal = build_market_pressure_signal([historical], benchmark_available=True)
    assert hist_signal["state"] == SIGNAL_STATE_HISTORICAL_ONLY
    assert hist_signal["score"] <= 35

    failed_signal = build_market_pressure_signal([historical, failed], benchmark_available=True)
    assert failed_signal["state"] == SIGNAL_STATE_FAILED_RECOVERY
    assert failed_signal["source_event_id"] == "mpe_002"
    assert failed_signal["metric_confirmations"]["failed_recovery_confirmed"] is True
    assert "failed_recovery_event" in failed_signal["reason_codes"]


def test_registry_wires_market_pressure_timeline_profile():
    from alphaflow.components.processors.techniques import analyzers as _analyzers  # noqa: F401

    names = {cls.namespace for cls in TechnicalAnalyzerRegistry.registered()}
    assert "market_pressure_timeline_profile" in names

    stock, benchmark = _make_market_pressure_pair()
    pack = ResearchPack(
        symbol="MSFT",
        market_data=DataFrameModel.from_df(stock),
        benchmark_data=DataFrameModel.from_df(benchmark),
        benchmark_meta=_benchmark_meta(),
    )
    out = TechnicalAnalyzerRegistry.run_all(stock, pack, {})
    assert "market_pressure_timeline_profile" in out
    profile = out["market_pressure_timeline_profile"]
    assert profile["summary"]["event_count"] >= 1
    assert "market_pressure_signal" in profile

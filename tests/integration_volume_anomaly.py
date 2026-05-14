"""
集成验证 (Phase 1' + Phase 2 — 多维度 + 市场感知)：

  1. byte-level 不变守门：
     比较"重构前 baseline (合成 fixture)"与"V4 架构下 TechnicalProcessor"输出的
     market_summary / liquidity_and_volume / timeframes 三个顶层 key 的 hash
  2. volume_anomaly_profile 通过 registry 自动注入到 distilled_features.technical
  3. JSON 严格序列化 (allow_nan=False) 必过
  4. registry 拓扑执行：LegacyMarketAnalyzer 先于 VolumeAnomalyAnalyzer
  5. **Phase 2**：HK / CN / US 三只样本端到端，primary_dimension 各异，
     字段缺失沉默降级（US 无 amount/turnover_rate 时不出现 NaN）

不依赖网络。
"""
import asyncio
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd

from alphaflow.core.schema import ResearchPack, AnalysisContext, ComponentOutput
from alphaflow.core.schema.models import DataFrameModel
from alphaflow.components.processors.technical_processor import TechnicalProcessor
from alphaflow.components.processors.techniques import MultiTimeframeMarketAnalyzer
from alphaflow.components.processors.techniques.registry import TechnicalAnalyzerRegistry


def _build_pack(
    symbol: str = "TEST.HK",
    *,
    with_amount: bool = False,
    with_turnover: bool = False,
) -> ResearchPack:
    """构造合成 ResearchPack。with_amount/with_turnover 控制 Phase 2 多维度场景。"""
    rng = np.random.RandomState(42)
    n = 250
    dates = pd.date_range("2024-01-02", periods=n, freq="B").strftime("%Y-%m-%d")
    closes = 100 + np.cumsum(rng.normal(0, 0.5, n))
    highs = closes + np.abs(rng.normal(0.3, 0.2, n))
    lows = closes - np.abs(rng.normal(0.3, 0.2, n))
    opens = closes + rng.normal(0, 0.2, n)
    volumes = rng.normal(1_000_000, 100_000, n).clip(min=10_000).astype(int)
    volumes[200] = 20_000_000
    cols = {
        "date": dates, "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": volumes,
    }
    if with_amount:
        cols["amount"] = (volumes * closes).round(2)
    if with_turnover:
        cols["turnover_rate"] = (volumes / 1e8).round(4)
    df = pd.DataFrame(cols)
    return ResearchPack(symbol=symbol, market_data=DataFrameModel.from_df(df))


def _hash(obj) -> str:
    return hashlib.md5(
        json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


async def _run_processor(pack: ResearchPack):
    proc = TechnicalProcessor("Tech")
    ctx = AnalysisContext(symbols=[pack.symbol])
    out = await proc.execute(ctx, input_data=pack)
    return out.payload if isinstance(out, ComponentOutput) else out


async def main() -> int:
    # ---- 1. baseline: 直接调老 analyzer，得到 ground truth (legacy 路径仅看 volume)
    pack_legacy = _build_pack(with_amount=False, with_turnover=False)
    legacy = MultiTimeframeMarketAnalyzer()
    legacy_out = legacy.analyze(pack_legacy)["technical_and_sentiment"]
    legacy_hashes = {
        k: _hash(legacy_out.get(k, {}))
        for k in ("market_summary", "liquidity_and_volume", "timeframes")
    }
    print(f"[1] Legacy baseline hashes:")
    for k, h in legacy_hashes.items():
        print(f"      {k:24s} {h}")

    # ---- 2. 跑 V4 TechnicalProcessor（registry 路径），用与 legacy 同 fixture
    pack_v4 = await _run_processor(_build_pack(with_amount=False, with_turnover=False))
    tech = pack_v4.distilled_features.technical
    print(f"\n[2] V4 distilled_features.technical keys: {sorted(tech.keys())}")

    # ---- 3. byte-level 守门：legacy 三 key 必须不变
    for k, expected in legacy_hashes.items():
        got = _hash(tech.get(k, {}))
        assert got == expected, \
            f"❌ '{k}' byte-level 改变了！\n  expected: {expected}\n  got:      {got}"
        print(f"      ✅ '{k}' hash 一致: {got}")

    # ---- 4. volume_anomaly_profile 注入正确（Phase 1 行为：仅 volume）
    profile = tech.get("volume_anomaly_profile")
    assert profile is not None, "volume_anomaly_profile 未注入"
    dq = profile["data_quality"]
    # Phase 2 元数据必须存在
    for key in ("market_type", "primary_dimension", "available_dimensions"):
        assert key in dq, f"data_quality 缺 Phase 2 字段 '{key}'"
    # TEST.HK → HK，但只有 volume 列 → fallback 到 volume
    assert dq["market_type"] == "hk", f"got {dq['market_type']}"
    assert dq["primary_dimension"] == "volume", \
        f"HK 仅 volume 应 fallback 到 volume, got {dq['primary_dimension']}"
    assert dq["available_dimensions"] == ["volume"]

    v = profile["volume"]
    assert set(v["lookbacks"].keys()) == {"5d", "20d", "60d", "252d"}
    assert v["lookbacks"]["252d"]["anomaly_days_total"] >= 1, "尖峰未被识别"
    print(f"\n[3] volume_anomaly_profile 顶层 keys: {sorted(profile.keys())}")
    print(f"    data_quality.primary_dimension: {dq['primary_dimension']}")
    print(f"    data_quality.market_type:        {dq['market_type']}")
    print(f"    latest_day: {v['latest_day']}")

    # ---- 4b. distribution_pattern_profile (Phase 4) 注入正确
    dp = tech.get("distribution_pattern_profile")
    assert dp is not None, "distribution_pattern_profile 未注入 (Phase 4)"
    dp_dq = dp["data_quality"]
    for key in ("market_type", "vwap_source", "dollar_volume_source",
                "sufficient_for_profile", "fields_available"):
        assert key in dp_dq, f"distribution_pattern data_quality 缺字段 '{key}'"
    assert dp_dq["market_type"] == "hk"
    # TEST.HK 只有 volume → 没 amount → vwap 走 typical_price_fallback, dv 走 close_volume_synthetic
    assert dp_dq["vwap_source"] == "typical_price_fallback", dp_dq["vwap_source"]
    assert dp_dq["dollar_volume_source"] == "close_volume_synthetic", dp_dq["dollar_volume_source"]
    assert dp_dq["sufficient_for_profile"] is True
    # 三个指标子树齐全
    assert set(dp_dq["fields_available"]) == {"clv", "vwap_deviation", "amihud_illiquidity"}
    for sub in ("clv", "vwap_deviation", "amihud_illiquidity"):
        assert sub in dp, f"distribution_pattern 缺子树 '{sub}'"
        assert "latest_day" in dp[sub] and "rolling" in dp[sub]
    assert "summary" in dp and "pressure_signals" in dp["summary"]
    print(f"\n[3b] distribution_pattern_profile 顶层 keys: {sorted(dp.keys())}")
    print(f"     vwap_source: {dp_dq['vwap_source']}")
    print(f"     dv_source:   {dp_dq['dollar_volume_source']}")
    print(f"     fields:      {dp_dq['fields_available']}")

    # ---- 4c. market_relative_anomaly_profile (Phase 5) 注入正确
    # 没有 benchmark_data 时应 Null Object 沉默降级（仅 data_quality, status=unavailable）
    mra = tech.get("market_relative_anomaly_profile")
    assert mra is not None, "market_relative_anomaly_profile 未注入 (Phase 5)"
    mra_dq = mra["data_quality"]
    for key in ("benchmark_status", "benchmark_symbol", "benchmark_source",
                "sufficient_for_profile", "market_type"):
        assert key in mra_dq, f"market_relative data_quality 缺字段 '{key}'"
    # TEST.HK 的 pack 没有 benchmark_data → status=unavailable, sufficient=False
    assert mra_dq["benchmark_status"] == "unavailable", mra_dq["benchmark_status"]
    assert mra_dq["sufficient_for_profile"] is False
    assert "latest_day" not in mra, "无 benchmark 时不应输出 latest_day"
    print(f"\n[3c] market_relative_anomaly_profile (Phase 5, no benchmark) keys: {sorted(mra.keys())}")
    print(f"     benchmark_status: {mra_dq['benchmark_status']}")

    # ---- 4d. Phase 5 端到端：注入 benchmark_data 后应正常输出
    # 用合成的指数 OHLCV + meta，复用 _build_pack 的随机骨架
    rng2 = np.random.RandomState(11)
    bench_dates = pd.date_range("2024-01-02", periods=250, freq="B").strftime("%Y-%m-%d")
    bench_close = 1000 + np.cumsum(rng2.normal(0, 5, 250))
    bench_vol = rng2.normal(50_000_000, 5_000_000, 250).clip(min=1e6).astype(int)
    bench_df = pd.DataFrame({
        "date": bench_dates,
        "open":   bench_close, "high": bench_close * 1.01,
        "low":    bench_close * 0.99, "close": bench_close,
        "volume": bench_vol,
    })
    pack_with_bench = _build_pack(with_amount=False, with_turnover=False)
    pack_with_bench.benchmark_data = DataFrameModel.from_df(bench_df)
    pack_with_bench.benchmark_meta = {
        "status": "ok", "benchmark_symbol": "^HSI", "source": "synthetic_test",
        "market_type": "hk", "rows": 250, "columns": bench_df.columns.tolist(),
    }
    res2 = await _run_processor(pack_with_bench)
    mra2 = res2.distilled_features.technical["market_relative_anomaly_profile"]
    assert mra2["data_quality"]["benchmark_status"] == "ok"
    assert mra2["data_quality"]["sufficient_for_profile"] is True
    for k in ("latest_day", "rolling", "summary"):
        assert k in mra2, f"端到端缺顶层 '{k}'"
    json.dumps(mra2, allow_nan=False, default=str)
    print(f"\n[3d] market_relative_anomaly_profile (with benchmark, end-to-end) ✓")
    print(f"     latest_day.rel_volume_tier: {mra2['latest_day']['rel_volume_tier']}")
    print(f"     latest_day.index_anomalous: {mra2['latest_day']['index_anomalous']}")

    # ---- 4e. composite_risk_profile (Phase 6) — 主链路：无 benchmark 时三件套 quorum=2
    cr = tech.get("composite_risk_profile")
    assert cr is not None, "composite_risk_profile 未注入 (Phase 6)"
    cr_dq = cr["data_quality"]
    for key in ("available_components", "missing_components", "essential_present",
                "core_quorum", "weight_redistribution", "unallocated_weight",
                "confidence", "confidence_level", "sufficient_for_score",
                "advisory_only", "diagnostic_tags"):
        assert key in cr_dq, f"composite_risk data_quality 缺 '{key}'"
    assert "score" in cr and "level" in cr and "score_breakdown" in cr and "primary_drivers" in cr
    # essential (volume) 在场 → score 不为 None
    assert cr_dq["essential_present"] is True
    assert cr["score"] is not None
    # 此场景：volume + distribution 在场，market_relative Null Object，flow 缺 → quorum=2/3
    # （TEST.HK 无 benchmark，pack 主链路里 mra 是 Null Object 但 distribution 正常）
    assert cr_dq["core_quorum"] in {"2/3", "3/3"}, cr_dq["core_quorum"]
    assert sum(v["effective"] for v in cr_dq["weight_redistribution"].values()) <= 100.0001
    json.dumps(cr, allow_nan=False, default=str)
    print(f"\n[3e] composite_risk_profile (Phase 6) keys: {sorted(cr.keys())}")
    print(f"     score / level: {cr['score']} / {cr['level']}")
    print(f"     core_quorum:   {cr_dq['core_quorum']}  confidence: {cr_dq['confidence']}")
    print(f"     drivers:       {[d['component'] for d in cr['primary_drivers']]}")

    # ---- 4f. flow_signals_profile (Phase 7) — 主链路：无 flow_data 时 Null Object 降级
    fs = tech.get("flow_signals_profile")
    assert fs is not None, "flow_signals_profile 未注入 (Phase 7)"
    fs_dq = fs["data_quality"]
    for key in ("market_type", "sources_available", "sources_missing",
                "primary_source", "sufficient_for_profile"):
        assert key in fs_dq, f"flow_signals data_quality 缺 '{key}'"
    # TEST.HK pack 没 flow_data → sufficient=False
    assert fs_dq["sufficient_for_profile"] is False
    assert "block_trade" not in fs and "lhb" not in fs
    print(f"\n[3f] flow_signals_profile (Phase 7, no flow_data) keys: {sorted(fs.keys())}")
    print(f"     sources_available: {fs_dq['sources_available']}")

    # ---- 4g. Phase 7 端到端：注入合成 flow_data → 子树正常输出
    base_date = pd.Timestamp("2024-08-01")
    block_df = pd.DataFrame([
        {"date": base_date + pd.Timedelta(days=i), "symbol": "TEST",
         "discount_pct": -5.0 if i < 3 else -0.5, "deal_value": 1e7}
        for i in range(5)
    ])
    pack_with_flow = _build_pack(with_amount=False, with_turnover=False)
    pack_with_flow.flow_data = {"block_trade": DataFrameModel.from_df(block_df)}
    pack_with_flow.flow_meta = {
        "status": "ok", "market_type": "cn",
        "primary_source": "block_trade",
        "sources": {"block_trade": {"status": "ok", "rows": 5}},
    }
    res3 = await _run_processor(pack_with_flow)
    fs2 = res3.distilled_features.technical["flow_signals_profile"]
    assert fs2["data_quality"]["sufficient_for_profile"] is True
    assert "block_trade" in fs2
    assert fs2["block_trade"]["rolling"]["discount_count"] == 3
    assert "[BLOCK_DISCOUNT_FREQUENT]" in fs2["summary"]["pressure_signals"]
    json.dumps(fs2, allow_nan=False, default=str)
    # 同时验证 composite_risk 现已纳入 flow_signals 子分
    cr2 = res3.distilled_features.technical["composite_risk_profile"]
    assert cr2["score_breakdown"]["flow_signals"]["raw"] is not None, \
        "composite_risk 未消费 flow_signals 子分"
    print(f"\n[3g] flow_signals_profile (with flow_data, end-to-end) ✓")
    print(f"     block_trade.tier: {fs2['block_trade']['rolling']['tier']}")
    print(f"     pressure_signals: {fs2['summary']['pressure_signals']}")
    print(f"     composite flow raw: {cr2['score_breakdown']['flow_signals']['raw']}")


    # ---- 5. JSON 严格序列化必过
    json.dumps(tech, allow_nan=False, default=str)
    print(f"\n[4] ✅ technical 整体通过 allow_nan=False 严格序列化")

    # ---- 6. registry 状态自描述
    registered = TechnicalAnalyzerRegistry.registered()
    print(f"\n[5] Registered analyzers ({len(registered)}):")
    for cls in registered:
        print(f"      - {cls.__name__:25s} ns={cls.namespace!r:28s} deps={cls.depends_on}")
    assert any(c.__name__ == "LegacyMarketAnalyzer" for c in registered)
    assert any(c.__name__ == "VolumeAnomalyAnalyzer" for c in registered)
    assert any(c.__name__ == "DistributionPatternAnalyzer" for c in registered)
    assert any(c.__name__ == "MarketRelativeAnomalyAnalyzer" for c in registered)
    assert any(c.__name__ == "CompositeRiskAnalyzer" for c in registered)
    assert any(c.__name__ == "FlowSignalsAnalyzer" for c in registered)

    # ============================================================
    # Phase 2 — HK / CN / US 三样本：primary_dimension 各异
    # ============================================================
    print("\n" + "=" * 75)
    print("[6] Phase 2 multi-dimension regression (HK/CN/US)")
    print("=" * 75)

    expectations = [
        # (symbol,        market, with_amount, with_turnover, primary,         active)
        ("00700.HK",      "hk",   True,        True,          "amount",        ["volume", "amount", "turnover_rate"]),
        ("0700.HK",       "hk",   True,        False,         "amount",        ["volume", "amount"]),
        ("0700.HK",       "hk",   False,       False,         "volume",        ["volume"]),  # fallback
        ("600519.SH",     "cn",   True,        True,          "turnover_rate", ["volume", "amount", "turnover_rate"]),
        ("600519.SH",     "cn",   True,        False,         "amount",        ["volume", "amount"]),  # fallback
        ("MSFT",          "us",   False,       False,         "volume",        ["volume"]),
        ("AAPL",          "us",   True,        False,         "volume",        ["volume", "amount"]),  # policy: US 仍选 volume
    ]

    for symbol, expect_market, with_a, with_t, expect_primary, expect_active in expectations:
        pack = _build_pack(symbol, with_amount=with_a, with_turnover=with_t)
        result = await _run_processor(pack)
        prof = result.distilled_features.technical["volume_anomaly_profile"]
        dq = prof["data_quality"]
        # 断言市场类型
        assert dq["market_type"] == expect_market, \
            f"{symbol}: market_type expected {expect_market}, got {dq['market_type']}"
        # 断言 primary
        assert dq["primary_dimension"] == expect_primary, \
            f"{symbol} (with_a={with_a}, with_t={with_t}): primary expected {expect_primary}, got {dq['primary_dimension']}"
        # 断言可用维度
        assert dq["available_dimensions"] == expect_active, \
            f"{symbol}: active dims expected {expect_active}, got {dq['available_dimensions']}"
        # 断言子树存在
        for dim in expect_active:
            assert dim in prof, f"{symbol}: 维度 {dim} 子树缺失"
        # 断言不应存在的 dim 不出现（Null Object）
        for dim in ("volume", "amount", "turnover_rate"):
            if dim not in expect_active:
                assert dim not in prof, f"{symbol}: 不应出现的 {dim} 子树仍存在"
        # JSON 严格序列化
        json.dumps(prof, allow_nan=False, default=str)

        flags = []
        if with_a: flags.append("amount")
        if with_t: flags.append("turnover_rate")
        flags_str = "+".join(flags) if flags else "vol-only"
        print(f"      ✅ {symbol:12s} ({expect_market}, {flags_str:25s}) → "
              f"primary={dq['primary_dimension']:14s} active={dq['available_dimensions']}")

    print("\n🎉 Phase 1' + Phase 2 集成验证全部通过 — "
          "byte-level 零侵入 + 多维度 + 市场感知 + 沉默降级")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

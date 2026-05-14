"""
Composite Risk — 子分映射纯函数层
====================================
每个子分一个纯函数：上游 profile payload → (raw_score, evidence) | (None, reason)

设计哲学：
- 纯函数：相同输入永远相同输出，无副作用
- 容错：上游 profile 字段缺失 / 仅返回 data_quality（Null Object）→ 返回 None
- 可解释：每次返回都附 evidence 字符串，最终能拼到 score_breakdown
- 与 framework 解耦：仅依赖标准 dict / config 常量，不 import analyzer / scorer
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from . import config as cfg


SubScore = Tuple[Optional[float], str]
"""(raw_score 0..100 或 None, evidence 字符串)"""


# =============================================================================
# 通用工具
# =============================================================================
def _is_available(profile: Optional[Mapping[str, Any]]) -> bool:
    """
    判断上游 profile 是否真正可用：
    - None / 空 dict → 不可用
    - 仅含 data_quality（Null Object 降级）→ 不可用
    - data_quality.sufficient_for_profile == False → 不可用
    """
    if not profile or not isinstance(profile, Mapping):
        return False
    keys = set(profile.keys())
    # 仅含 data_quality 视为 Null Object
    if keys <= {"data_quality"}:
        return False
    dq = profile.get("data_quality") or {}
    if isinstance(dq, Mapping) and dq.get("sufficient_for_profile") is False:
        return False
    return True


def _safe_get(d: Optional[Mapping[str, Any]], *keys: str, default: Any = None) -> Any:
    """嵌套 .get 链，任一层 None 即返回 default。"""
    cur: Any = d
    for k in keys:
        if not isinstance(cur, Mapping):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def count_extreme_days(profile: Optional[Mapping[str, Any]], window: str) -> Optional[int]:
    """
    通用 helper：统计 volume_anomaly_profile 在指定 window 内
    EXTREME + BLOWOUT + HISTORIC 的累计天数。

    复用场景：
      1. score_volume_anomaly 的 rolling bonus 计数
      2. CompositeRiskScorer._persistence_gate 的持续性判定

    返回 None 表示 profile 不可用 / 无法判定（调用方决定如何降级）；
    返回 int 0 表示可判定且无异常天。
    """
    if not _is_available(profile):
        return None
    dq = profile.get("data_quality") or {}
    primary = dq.get("primary_dimension") or "volume"
    sub = profile.get(primary) or profile.get("volume")
    if not isinstance(sub, Mapping):
        return None
    by_tier = _safe_get(sub, "lookbacks", window, "by_tier", default=None)
    if not isinstance(by_tier, Mapping):
        return None
    return sum(int(by_tier.get(t, 0) or 0) for t in cfg.EXTREME_PLUS_TIERS)


# =============================================================================
# 1. volume_anomaly 子分
# =============================================================================
def score_volume_anomaly(profile: Optional[Mapping[str, Any]]) -> SubScore:
    """
    依据：<primary>.latest_day.tier (NORMAL/ELEVATED/SPIKE/EXTREME/BLOWOUT/HISTORIC)
    加成：<primary>.lookbacks.{ROLLING_BONUS_WINDOW}.by_tier 中
          EXTREME+BLOWOUT+HISTORIC 之和 ≥ ROLLING_EXTREME_BONUS_THRESHOLD → +bonus
    封顶：VOLUME_MAX_SCORE
    """
    if not _is_available(profile):
        return None, "unavailable"

    # primary_dimension 决定看哪个子树（volume / amount / turnover_rate）
    dq = profile.get("data_quality") or {}
    primary = dq.get("primary_dimension") or "volume"
    sub = profile.get(primary)
    if sub is None:
        # 兜底取 volume
        sub = profile.get("volume")
    if not isinstance(sub, Mapping):
        return None, f"unavailable (no '{primary}' subtree)"

    tier = _safe_get(sub, "latest_day", "tier")
    if tier is None:
        return None, "unavailable (no latest_day.tier)"

    base = cfg.VOLUME_TIER_SCORES.get(str(tier))
    if base is None:
        return None, f"unknown tier: {tier!r}"

    # rolling 加成：复用 count_extreme_days helper（与 persistence gate 同源）
    extreme_count = count_extreme_days(profile, cfg.ROLLING_BONUS_WINDOW) or 0

    bonus = 0
    if extreme_count >= cfg.ROLLING_EXTREME_BONUS_THRESHOLD:
        bonus = cfg.ROLLING_EXTREME_BONUS_POINTS

    raw = min(base + bonus, cfg.VOLUME_MAX_SCORE)
    evidence = f"tier={tier}"
    if bonus:
        evidence += f", {cfg.ROLLING_BONUS_WINDOW}_extreme={extreme_count}d (+{bonus})"
    return float(raw), evidence


# =============================================================================
# 2. distribution_pattern 子分
# =============================================================================
def score_distribution_pattern(profile: Optional[Mapping[str, Any]]) -> SubScore:
    """
    依据：summary.pressure_signals 数量
    映射：0→0, 1→35, 2→65, 3→90, 4+→DISTRIBUTION_MAX_SCORE
    """
    if not _is_available(profile):
        return None, "unavailable"

    pressure = _safe_get(profile, "summary", "pressure_signals", default=[])
    if not isinstance(pressure, list):
        pressure = []

    n = len(pressure)
    if n in cfg.DISTRIBUTION_SIGNAL_COUNT_SCORES:
        raw = cfg.DISTRIBUTION_SIGNAL_COUNT_SCORES[n]
    else:
        # n >= 4 封顶
        raw = cfg.DISTRIBUTION_MAX_SCORE

    if n == 0:
        evidence = "no pressure signals"
    else:
        evidence = f"{n} pressure signal(s)"
    return float(raw), evidence


# =============================================================================
# 3. market_relative 子分
# =============================================================================
def score_market_relative(profile: Optional[Mapping[str, Any]]) -> SubScore:
    """
    依据：latest_day.rel_volume_tier + latest_day.rel_return_tier 取较大者
    抑制：latest_day.index_anomalous=True 时 raw × INDEX_ANOMALOUS_DAMPING
    """
    if not _is_available(profile):
        return None, "unavailable"

    rv_tier = _safe_get(profile, "latest_day", "rel_volume_tier")
    rr_tier = _safe_get(profile, "latest_day", "rel_return_tier")
    idx_anom = bool(_safe_get(profile, "latest_day", "index_anomalous", default=False))

    if rv_tier is None and rr_tier is None:
        return None, "unavailable (no rel tiers)"

    rv_score = cfg.REL_VOLUME_TIER_SCORES.get(str(rv_tier), 0) if rv_tier else 0
    rr_score = cfg.REL_RETURN_TIER_SCORES.get(str(rr_tier), 0) if rr_tier else 0
    raw = max(rv_score, rr_score)

    evidence_parts = []
    if rv_tier:
        evidence_parts.append(f"rel_volume={rv_tier}")
    if rr_tier:
        evidence_parts.append(f"rel_return={rr_tier}")

    if idx_anom and raw > 0:
        raw = raw * cfg.INDEX_ANOMALOUS_DAMPING
        evidence_parts.append(f"index_anomalous→×{cfg.INDEX_ANOMALOUS_DAMPING}")

    return float(raw), ", ".join(evidence_parts) if evidence_parts else "no signal"


# =============================================================================
# 4. flow_signals 子分（Phase 7 占位）
# =============================================================================
def score_flow_signals(profile: Optional[Mapping[str, Any]]) -> SubScore:
    """
    Phase 7 实现：依据 summary.pressure_signals 数量映射 0..MAX。
    依赖 flow_signals analyzer 的 profile 形态（与 distribution_pattern 同构）。
    """
    if not _is_available(profile):
        return None, "unavailable"

    pressure = _safe_get(profile, "summary", "pressure_signals", default=[])
    if not isinstance(pressure, list):
        pressure = []
    n = len(pressure)
    if n in cfg.FLOW_SIGNAL_COUNT_SCORES:
        raw = cfg.FLOW_SIGNAL_COUNT_SCORES[n]
    else:
        raw = cfg.FLOW_MAX_SCORE

    sources = _safe_get(profile, "data_quality", "sources_available", default=[])
    n_src = len(sources) if isinstance(sources, list) else 0
    evidence = (f"{n} flow pressure signal(s) across {n_src} source(s)"
                if n_src else f"{n} flow pressure signal(s)")
    return float(raw), evidence


# =============================================================================
# Cross-component objective confirmation（纯函数）
# =============================================================================
def objective_path_confirmation(
    distribution_pattern: Optional[Mapping[str, Any]],
    market_relative: Optional[Mapping[str, Any]],
) -> Tuple[float, str]:
    """
    Phase 8 客观路径确认加分。

    仅在 distribution_pattern 给出路径压力，且 market_relative 给出相对弱势时
    返回 bounded bonus。此函数仍只依赖 profile dict + config，不触碰 scorer 状态，
    便于复用和单测。
    """
    if not _is_available(distribution_pattern) or not _is_available(market_relative):
        return 0.0, "unavailable"

    dist_pressure = _safe_get(distribution_pattern, "summary", "pressure_signals", default=[])
    market_pressure = _safe_get(market_relative, "summary", "pressure_signals", default=[])
    if not isinstance(dist_pressure, list):
        dist_pressure = []
    if not isinstance(market_pressure, list):
        market_pressure = []

    dist_hits = [tag for tag in cfg.OBJECTIVE_PATH_TAGS if tag in dist_pressure]
    market_hits = [tag for tag in cfg.OBJECTIVE_MARKET_CONFIRM_TAGS if tag in market_pressure]

    if dist_hits and market_hits:
        return (
            float(cfg.OBJECTIVE_PATH_CONFIRMATION_BONUS),
            f"path={dist_hits}; market={market_hits}",
        )
    return 0.0, "no objective path+market confirmation"


# =============================================================================
# 子分函数注册表（scorer.py 用此遍历）
# =============================================================================
SCORERS = {
    cfg.COMPONENT_VOLUME:       score_volume_anomaly,
    cfg.COMPONENT_DISTRIBUTION: score_distribution_pattern,
    cfg.COMPONENT_MARKET_REL:   score_market_relative,
    cfg.COMPONENT_FLOW:         score_flow_signals,
}

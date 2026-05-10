"""
Composite Risk — 编排器（Composite + Strategy 模式）
=====================================================
对应 volume_anomaly.profiler / distribution_pattern.profiler / market_relative.profiler
角色，但语义不同：本类不做特征计算，只做"已有特征→风险评分"的合成。

四道闸门 + 重分配算法：
  1. essential gate     缺 ESSENTIAL_COMPONENTS 任一 → score=None, sufficient=False
  2. core quorum        CORE_COMPONENTS 在场数 < MIN_QUORUM → advisory_only
  3. inflation cap      effective_weight ≤ original × MAX_INFLATION
  4. confidence floor   confidence < HARD_FLOOR → 屏蔽 level

架构属性：
  - 高内聚：所有评分合成逻辑都在本类
  - 低耦合：仅依赖 scorers.SCORERS（纯函数）+ config（常量），无 framework 依赖
  - 单一职责：本类只做"权重重分配 + 合成 + 输出格式化"，子分映射在 scorers.py
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

from . import config as cfg
from . import scorers


class CompositeRiskScorer:
    """无状态。重复调用 score(...) 安全。"""

    # -------------------------------------------------------------------------
    # 主入口
    # -------------------------------------------------------------------------
    def score(
        self,
        *,
        volume_anomaly:       Optional[Mapping[str, Any]] = None,
        distribution_pattern: Optional[Mapping[str, Any]] = None,
        market_relative:      Optional[Mapping[str, Any]] = None,
        flow_signals:         Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        # 1. 调用每个子分
        upstreams = {
            cfg.COMPONENT_VOLUME:       volume_anomaly,
            cfg.COMPONENT_DISTRIBUTION: distribution_pattern,
            cfg.COMPONENT_MARKET_REL:   market_relative,
            cfg.COMPONENT_FLOW:         flow_signals,
        }
        raw_scores: Dict[str, Optional[float]] = {}
        evidences:  Dict[str, str] = {}
        for comp, fn in scorers.SCORERS.items():
            raw, evi = fn(upstreams.get(comp))
            raw_scores[comp] = raw
            evidences[comp] = evi

        # 2. 闸门 1：essential gate
        available = [c for c, v in raw_scores.items() if v is not None]
        missing   = [c for c, v in raw_scores.items() if v is None]
        essential_present = all(c in available for c in cfg.ESSENTIAL_COMPONENTS)

        # 3. 闸门 2：core quorum
        core_in = [c for c in cfg.CORE_COMPONENTS if c in available]
        quorum  = len(core_in)
        advisory_only = quorum < cfg.MIN_QUORUM

        # 4. 权重重分配（带 cap）
        effective, unallocated, capped_set = self._redistribute(
            available=available, missing=missing,
        )

        # 5. confidence
        confidence = (sum(effective.values())) / 100.0
        confidence_level = self._classify_confidence(confidence)
        confidence_floor_breach = confidence < cfg.HARD_FLOOR_CONFIDENCE

        # 6. 计算合成分（即使 advisory_only 也计算，留痕）
        weighted = {
            c: (raw_scores[c] * effective.get(c, 0.0) / 100.0) if raw_scores[c] is not None else 0.0
            for c in raw_scores
        }
        score_value = sum(weighted.values())
        score_value = round(min(max(score_value, 0.0), 100.0), 2)

        # 7. sufficient_for_score 决策
        sufficient = (
            essential_present
            and (not advisory_only)
            and (not confidence_floor_breach)
        )

        # 8. level 仅在 sufficient 时输出
        level = self._classify_level(score_value) if sufficient else None

        # 8b. 闸门 5：persistence gate — 仅对 ELEVATED 做"持续性"约束
        # 防止单日异常事件（产品发布、单日暴量噪声）被推升至 ELEVATED；
        # HIGH/CRITICAL 不 gate（catastrophic 单日事件应被允许直升）。
        persistence_check = self._persistence_gate(volume_anomaly)
        persistence_triggered = False
        if level in cfg.PERSISTENCE_GATE_LEVELS and persistence_check["passed"] is False:
            level = cfg.PERSISTENCE_DOWNGRADE_TO
            persistence_triggered = True

        # 9. primary_drivers
        drivers = self._primary_drivers(raw_scores, effective, weighted, evidences)

        # 10. 组装输出
        breakdown = {}
        for c in raw_scores:
            breakdown[c] = {
                "raw":      None if raw_scores[c] is None else round(raw_scores[c], 2),
                "weight":   round(effective.get(c, 0.0), 2),
                "weighted": round(weighted.get(c, 0.0), 2),
                "evidence": evidences[c],
                "capped":   c in capped_set,
            }

        # 闸门触发标签
        tags: List[str] = []
        if not essential_present:
            tags.append(cfg.TAG_INSUFFICIENT_ESSENTIAL)
        if advisory_only:
            tags.append(cfg.TAG_INSUFFICIENT_QUORUM)
            tags.append(cfg.TAG_ADVISORY_ONLY)
        if confidence_floor_breach:
            tags.append(cfg.TAG_LOW_CONFIDENCE)
        if persistence_triggered:
            tags.append(cfg.TAG_NO_PERSISTENCE)

        out: Dict[str, Any] = {
            "data_quality": {
                "available_components":  list(available),
                "missing_components":    list(missing),
                "essential_present":     essential_present,
                "core_quorum":           f"{quorum}/{len(cfg.CORE_COMPONENTS)}",
                "weight_redistribution": {
                    c: {
                        "original":  cfg.WEIGHTS[c],
                        "effective": round(effective.get(c, 0.0), 2),
                        "capped":    c in capped_set,
                        **({"reason": "unavailable"} if c in missing else {}),
                    }
                    for c in raw_scores
                },
                "unallocated_weight":   round(unallocated, 2),
                "confidence":           round(confidence, 4),
                "confidence_level":     confidence_level,
                "sufficient_for_score": sufficient,
                "advisory_only":        advisory_only,
                "persistence_check":    persistence_check,
                "diagnostic_tags":      tags,
            },
            "score_breakdown": breakdown,
            "primary_drivers": drivers,
        }

        # essential 缺席：不输出 score / level（None 而非 0，避免误读）
        if not essential_present:
            out["score"] = None
            out["level"] = None
        else:
            out["score"] = score_value
            out["level"] = level  # advisory / 低置信时为 None

        return out

    # -------------------------------------------------------------------------
    # 内部：权重重分配（带 cap，分摊不下的进 unallocated）
    # -------------------------------------------------------------------------
    @staticmethod
    def _redistribute(
        *, available: List[str], missing: List[str],
    ) -> Tuple[Dict[str, float], float, set]:
        """
        分配规则（迭代直至稳定）：
          1. 缺席权重之和 = pool
          2. 在场组件按"原权重/在场总原权重"占比领取 pool
          3. 若某组件领取后超过 original × MAX_INFLATION → 截断到上限，盈余回流 pool
          4. 重复 2-3 直到 pool 分尽 / 全部封顶 → 剩余进 unallocated
        """
        if not available:
            return {}, float(sum(cfg.WEIGHTS.values())), set()

        original_avail_sum = sum(cfg.WEIGHTS[c] for c in available)
        pool = float(sum(cfg.WEIGHTS[c] for c in missing))
        # 初始化：在场者各自获得原权重
        effective: Dict[str, float] = {c: float(cfg.WEIGHTS[c]) for c in available}
        caps: Dict[str, float] = {c: cfg.WEIGHTS[c] * cfg.MAX_INFLATION for c in available}
        capped_set: set = set()

        # 迭代分配（最多 N 轮，N = 在场数，足够稳定）
        for _ in range(len(available) + 1):
            if pool <= 1e-9:
                break
            # 还能继续吃的（未封顶的）
            uncapped = [c for c in available if c not in capped_set]
            if not uncapped:
                break
            # 按未封顶者的"原权重比例"分 pool
            base_sum = sum(cfg.WEIGHTS[c] for c in uncapped)
            distributed_this_round = 0.0
            new_caps_hit: List[str] = []
            for c in uncapped:
                share = pool * (cfg.WEIGHTS[c] / base_sum)
                proposed = effective[c] + share
                if proposed >= caps[c] - 1e-9:
                    # 截断到 cap，盈余回流
                    take = caps[c] - effective[c]
                    effective[c] = caps[c]
                    distributed_this_round += take
                    new_caps_hit.append(c)
                else:
                    effective[c] = proposed
                    distributed_this_round += share
            for c in new_caps_hit:
                capped_set.add(c)
            pool = pool - distributed_this_round
            # 若 pool 几乎为 0 或本轮无人收纳（全封顶）→ 退出
            if not new_caps_hit and pool > 1e-9:
                # 没人封顶但 pool 还剩 → 浮点残差，吞掉
                # 实际上 pro-rata 一次就会分尽
                pool = 0.0

        # 缺席组件 effective = 0
        for c in missing:
            effective[c] = 0.0

        return effective, max(pool, 0.0), capped_set

    # -------------------------------------------------------------------------
    # 内部：tier 映射
    # -------------------------------------------------------------------------
    @staticmethod
    def _classify_confidence(value: float) -> str:
        for threshold, label in cfg.CONFIDENCE_TIERS:
            if value < threshold:
                return label
        return cfg.CONFIDENCE_TIERS[-1][1]

    @staticmethod
    def _classify_level(value: float) -> str:
        for threshold, label in cfg.LEVEL_TIERS:
            if value < threshold:
                return label
        return cfg.LEVEL_TIERS[-1][1]

    # -------------------------------------------------------------------------
    # 内部：闸门 5 — persistence gate
    # -------------------------------------------------------------------------
    @staticmethod
    def _persistence_gate(
        volume_profile: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        """
        判定近 LEVEL_PERSISTENCE_WINDOW 内是否有 ≥ MIN_DAYS 个 EXTREME+ 异常天。

        返回结构：
          {window, threshold, count, passed}
          - passed=True：count ≥ threshold（持续异常，允许 ELEVATED+）
          - passed=False：count 明确 < threshold（单日噪声，应 cap）
          - passed=None：无法判定（volume profile 缺失/损坏）→ 守护性放行，
                        不在缺数据时误伤 — essential gate 已先拦截真缺席场景。
        """
        count = scorers.count_extreme_days(volume_profile, cfg.LEVEL_PERSISTENCE_WINDOW)
        if count is None:
            return {
                "window":    cfg.LEVEL_PERSISTENCE_WINDOW,
                "threshold": cfg.LEVEL_PERSISTENCE_MIN_DAYS,
                "count":     None,
                "passed":    None,
            }
        return {
            "window":    cfg.LEVEL_PERSISTENCE_WINDOW,
            "threshold": cfg.LEVEL_PERSISTENCE_MIN_DAYS,
            "count":     int(count),
            "passed":    bool(count >= cfg.LEVEL_PERSISTENCE_MIN_DAYS),
        }

    # -------------------------------------------------------------------------
    # 内部：primary_drivers
    # -------------------------------------------------------------------------
    @staticmethod
    def _primary_drivers(
        raw: Dict[str, Optional[float]],
        effective: Dict[str, float],
        weighted: Dict[str, float],
        evidences: Dict[str, str],
        top_n: int = 3,
    ) -> List[Dict[str, Any]]:
        items = [
            {
                "component":      c,
                "weighted_score": round(w, 2),
                "raw":            None if raw[c] is None else round(raw[c], 2),
                "weight":         round(effective.get(c, 0.0), 2),
                "evidence":       evidences[c],
            }
            for c, w in weighted.items()
            if raw[c] is not None and w > 0
        ]
        items.sort(key=lambda x: x["weighted_score"], reverse=True)
        return items[:top_n]

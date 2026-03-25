"""
增长趋势鉴定医嘱 (Trend Status Evaluator)
"""

import math
from typing import Dict, Any
from alphaflow.core.schema import ResearchPack
from alphaflow.components.processors.fundamentals.evaluators import EvaluatorEngine


# 仲裁配置 (Named Constants)
_TREND_WEIGHTS = {"gross_margin_delta": 2.0, "net_margin_delta": 1.0, "roe_delta": 1.0}
_TREND_DEADZONE = 0.005     # ±0.5pp 死区过滤噪声
_TREND_THRESHOLD = 1.5      # 加权得分阈值
_VETO_THRESHOLD = -0.015    # 毛利率回撤超 1.5pp 触发否决


@EvaluatorEngine.register
def evaluate_trend_status(pack: ResearchPack) -> None:
    """
    趋势方向元判定：加权投票 + 毛利率一票否决权
    
    读取 MetricEngine 算出的 trend_delta 域的客观百分比，
    给实体出具 IMPROVING / DECLINING / MIXED 的主观状态结论，
    并作为属性扩展写回 metrics 字典。
    """
    metrics = pack.distilled_features.fundamental_metrics or {}
    td = metrics.get("trend_delta_ttm", {})
    if not td:
        return

    # 加权得分计算
    score = 0.0
    voted = 0
    for key, weight in _TREND_WEIGHTS.items():
        val = td.get(key)
        if val is not None and isinstance(val, (int, float)) and not math.isnan(val):
            if val > _TREND_DEADZONE:
                score += weight
            elif val < -_TREND_DEADZONE:
                score -= weight
            voted += 1

    if voted == 0:
        return

    # === 斩立决（Absolute Veto）===
    gm_d = td.get("gross_margin_delta")
    if gm_d is not None and gm_d <= _VETO_THRESHOLD:
        # 当核心护城河遭遇结构性摧毁时，无视一切下游粉饰（净利/杠杆拉升的ROE）
        # 剥夺后续所有计分程序，直接定谳
        td["trend_status"] = "DECLINING"
        # 顺便打上不可磨灭的思想烙印，供 LLM 或研究员一眼看穿死因
        td["veto_reason"] = f"Gross margin collapsed by {abs(gm_d)*100:.1f}pp"
        metrics["trend_delta_ttm"] = td
        pack.distilled_features.fundamental_metrics = metrics
        return

    # === 常规量刑程序（如果没有触发死刑）===
    if score >= _TREND_THRESHOLD:
        td["trend_status"] = "IMPROVING"
    elif score <= -_TREND_THRESHOLD:
        td["trend_status"] = "DECLINING"
    else:
        td["trend_status"] = "MIXED"

    # 写回 metrics
    metrics["trend_delta_ttm"] = td
    pack.distilled_features.fundamental_metrics = metrics

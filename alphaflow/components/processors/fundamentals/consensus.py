"""
ConsensusAnalyzer - 分析师共识聚合器
=======================================
Processor 层的事件流分析器，将原始 estimates 数据降噪为高维信号。

输入：pack.fundamentals["estimates"]（已被 ACL 标准化的分析师预测快照）
输出：Dict[str, Any]（合并后的分析师共识域）

遵循 .clinerules §V 范式 2：非结构化事件流分析器。
"""
from typing import Any, Dict

from alphaflow.core.schema.models import ResearchPack


class ConsensusAnalyzer:
    """分析师共识降噪器 — 从 estimates 快照中提炼 LLM 可消费的高维信号"""

    @staticmethod
    def analyze(pack: ResearchPack) -> Dict[str, Any]:
        """读取原始 estimates，计算衍生指标，返回合并的 consensus dict"""
        estimates_raw: Dict[str, Any] = (pack.fundamentals or {}).get("estimates", {}) or {}
        if not estimates_raw:
            return {}

        result: Dict[str, Any] = {}

        # ── 衍生指标计算 ──

        # 1. target_spread: (最高目标价 - 最低目标价) / 共识均价 — 分歧度
        high = estimates_raw.get("TARGET_HIGH")
        low = estimates_raw.get("TARGET_LOW")
        consensus = estimates_raw.get("TARGET_PRICE")
        if high is not None and low is not None and consensus and consensus > 0:
            result["target_spread"] = round((high - low) / consensus, 4)

        # 2. upside_potential: (共识目标价 - 现价) / 现价 — 潜在涨幅
        target = estimates_raw.get("TARGET_PRICE")
        current = estimates_raw.get("CURRENT_PRICE")
        if target is not None and current and current > 0:
            result["upside_potential"] = round((target - current) / current, 4)

        # ── 合并：衍生指标在前，原始数据补充 ──
        result.update(estimates_raw)
        return result

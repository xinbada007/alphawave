import json
from typing import Dict, Any, Optional
from pydantic import BaseModel
from alphaflow.core.schema.models import ResearchPack, DistilledFeatures


class LLMResearchReport(BaseModel):
    """专供 LLM 消费的极简、高密度视图"""

    symbol: str
    report_time: str
    distilled_insights: DistilledFeatures
    # 🚀 全部设为 Optional 并默认为 None，为蒸发逻辑打下基础
    unclaimed_fundamentals: Optional[Dict[str, Any]] = None
    market_metrics_snapshot: Optional[Dict[str, Any]] = None
    extra_context: Optional[Dict[str, Any]] = None
    news: Optional[list] = None


def _is_empty(v: Any) -> bool:
    """判断值是否为空（None、空 dict、空 list）。

    使用显式 isinstance 检查而非 `v in (None, {}, [])`，
    避免 numpy array 等对象重载 __eq__ 导致的 ValueError。
    """
    if v is None:
        return True
    if isinstance(v, dict):
        return len(v) == 0
    if isinstance(v, list):
        return len(v) == 0
    return False


def deep_clean_empty(data: Any) -> Any:
    """递归清理字典/列表中的 None、空字典 {} 和空列表[]

    这是一个纯函数，无副作用，用于在序列化前物理剔除所有空节点。
    宁可浪费 10 个 Token，绝不容忍 1 次静默的数据丢失。
    """
    if isinstance(data, dict):
        cleaned = {k: deep_clean_empty(v) for k, v in data.items()}
        # 物理剔除无价值节点
        return {k: v for k, v in cleaned.items() if not _is_empty(v)}
    elif isinstance(data, list):
        cleaned = [deep_clean_empty(v) for v in data]
        return [v for v in cleaned if not _is_empty(v)]
    return data


def build_llm_view(pack: ResearchPack) -> str:
    """视图投影工厂：动态裁切被消费的冗余数据，并执行极简空值净化"""

    unclaimed_funds = {}
    consumed_keys = pack.registry.consumed_standard_keys

    # 1. 动态过滤 Fundamentals 域
    for category, data_node in (pack.fundamentals or {}).items():
        if isinstance(data_node, dict):
            # 剔除已被 MetricEngine 消费的原子指标
            filtered = {k: v for k, v in data_node.items() if k not in consumed_keys}
            if filtered:
                unclaimed_funds[category] = filtered
        elif isinstance(data_node, list):
            # 剔除已被整体屏蔽的领域 (如 insider_trading_history)
            if category not in pack.registry.consumed_domains:
                # 信任 Collector 的原始数据长度，不越权截断
                unclaimed_funds[category] = data_node

    # 2. 动态过滤 Market Metrics 域
    clean_market_metrics = {}
    if pack.market_metrics:
        clean_market_metrics = {
            k: v for k, v in pack.market_metrics.items() if k not in consumed_keys
        }

    # 3. 组装最终 DTO
    # 🚀 方案 1：利用 Python 的 Truthiness，若为空则传 None，彻底蒸发 JSON 中的 Key
    view = LLMResearchReport(
        symbol=pack.symbol,
        report_time=pack.readable_timestamp,
        distilled_insights=pack.distilled_features,
        unclaimed_fundamentals=unclaimed_funds if unclaimed_funds else None,
        market_metrics_snapshot=clean_market_metrics if clean_market_metrics else None,
        extra_context=pack.extra if pack.extra else None,
        news=pack.news if pack.news else None,
    )

    # 4. 🚀 架构升级：废除 exclude_unset 地雷，改用纯函数后置清洗
    # 彻底蒸发 None、空列表 []、空字典 {}
    # 4. 🚀 架构升级：废除 exclude_unset 地雷，改用纯函数后置清洗
    # 彻底蒸发 None、空列表 []、空字典 {}
    # 实现 JSON 级别的极高信噪比，拯救 LLM Token
    raw_dict = view.model_dump(exclude_none=True)
    cleaned_dict = deep_clean_empty(raw_dict)

    # 直接输出清理后的字典为 JSON 字符串
    return json.dumps(cleaned_dict, ensure_ascii=False, indent=2)
    raw_dict = view.model_dump(exclude_none=True)
    cleaned_dict = deep_clean_empty(raw_dict)

    # 直接输出清理后的字典为 JSON 字符串
    return json.dumps(cleaned_dict, ensure_ascii=False, indent=2)

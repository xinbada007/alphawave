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
            k: v for k, v in pack.market_metrics.items() 
            if k not in consumed_keys
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
        news=pack.news if pack.news else None
    )
    
    # 4. 🚀 Pydantic 终极净化 (盲区3 修复)
    # 彻底蒸发 None、空列表 []、空字典 {}、以及未赋值的默认字段
    # 实现 JSON 级别的极高信噪比，拯救 LLM Token
    return view.model_dump_json(
        indent=2, 
        exclude_none=True, 
        exclude_unset=True
    )

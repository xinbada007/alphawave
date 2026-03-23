"""
全域中央注册表防腐层 (Central Mapping Registry - ACL)
========================================================
基于 Clean Architecture 原则，将防腐层下沉到 Core 层。
实施"基于上下文路由的防腐层 (Context-Routed ACL)"架构。

设计哲学：
1. 任务路由：TASK_MAPPING_ROUTER 为每个任务编排专属映射表组合
2. Meta 最高维底座：META_MAPPING 永远作为任务责任链首位，锁死元数据提取规则
3. 动态编译：运行时为每个 Provider 生成高速一维映射表
4. 铁腕精炼：严格白名单映射，不在白名单的字段一律丢弃
5. 长文本截断：LONG_DESCRIPTION 自动截断至 1000 字符，防 LLM Token 爆炸
6. 静态 Mixin 模式：利润表字段定义集中在 income_statement.py
"""

import math
from typing import Any, Dict, List, Optional, Set
import pandas as pd

from alphaflow.core.schema.standard import StandardFinancialRecord
from alphaflow.core.utils.data_utils import ReportPeriod, detect_report_type, MetaKey
from alphaflow.core.acl.mappings.meta import META_MAPPING

# 导入各类业务映射网...
from alphaflow.core.acl.mappings.income_statement import INCOME_STATEMENT_MAPPING
from alphaflow.core.acl.mappings.balance_sheet import BALANCE_SHEET_MAPPING
from alphaflow.core.acl.mappings.cash_flow import CASH_FLOW_MAPPING
from alphaflow.core.acl.mappings.share_stats import SHARE_STATS_MAPPING
from alphaflow.core.acl.mappings.profile import PROFILE_MAPPING
from alphaflow.core.acl.mappings.estimates import ESTIMATES_MAPPING
from alphaflow.core.acl.mappings.metrics import METRICS_MAPPING
from alphaflow.core.acl.mappings.akshare_analysis import AKSHARE_ANALYSIS_MAPPING

def is_valid_value(val: Any) -> bool:
    """
    【100% 精准过滤器】
    使命：剔除无意义 Token 杀手 (None, NaN, 空字符串, 空集合)
    底线：绝对不误伤 0, 0.0, False 等有金融/逻辑意义的值。
    """
    if val is None:
        return False
        
    # bool 是 int 的子类，所以会进入此分支。0, 0.0, False 全部返回 True。
    if isinstance(val, (int, float)):
        return not math.isnan(val) if isinstance(val, float) else True
        
    if isinstance(val, str):
        return val.strip().lower() not in {"", "nan", "n/a", "null", "none", "nat"}
        
    if isinstance(val, (list, dict)):
        return len(val) > 0  # 剔除空列表/空字典
        
    try:
        if pd.isna(val):
            return False
    except Exception:
        pass
        
    return True

# ==========================================
# 🚀 任务映射路由表 (Task Mapping Router)
# META_MAPPING 永远作为最高优的基础底座
# ==========================================
TASK_MAPPING_ROUTER: Dict[str, List[Dict[str, Any]]] = {
    "a_income":[META_MAPPING, INCOME_STATEMENT_MAPPING],
    "q_income": [META_MAPPING, INCOME_STATEMENT_MAPPING],
    "a_balance": [META_MAPPING, BALANCE_SHEET_MAPPING],
    "q_balance": [META_MAPPING, BALANCE_SHEET_MAPPING],
    "a_cash":[META_MAPPING, CASH_FLOW_MAPPING],
    "q_cash":[META_MAPPING, CASH_FLOW_MAPPING],
    
    "a_analysis":[META_MAPPING, AKSHARE_ANALYSIS_MAPPING],
    "q_analysis":[META_MAPPING, AKSHARE_ANALYSIS_MAPPING],
    
    "profile":[META_MAPPING, PROFILE_MAPPING, ESTIMATES_MAPPING, SHARE_STATS_MAPPING],
    "metrics":[META_MAPPING, METRICS_MAPPING, PROFILE_MAPPING, ESTIMATES_MAPPING, SHARE_STATS_MAPPING],
    "share_stats":[META_MAPPING, SHARE_STATS_MAPPING, PROFILE_MAPPING, METRICS_MAPPING],
    "estimates":[META_MAPPING, ESTIMATES_MAPPING, PROFILE_MAPPING, METRICS_MAPPING],
}

DATE_FIELDS: Set[str] = {
    "EX_DIVIDEND_DATE", "ANNOUNCE_DATE", "PAYMENT_DATE", 
    "RECORD_DATE", "SPLIT_DATE", "LISTING_DATE", "FISCAL_YEAR_END",
    "EX_DATE"
}

STRICT_MAPPED_TASKS = {"profile"}

class DynamicFinancialAdapter:
    def __init__(self, provider_id: str):
        self.provider_id = provider_id
        self._compiled_cache: Dict[str, Dict[str, Any]] = {}
    
    def _compile_mapping(self, source_mapping: Dict) -> Dict[str, Dict[str, Any]]:
        compiled: Dict[str, Dict[str, Any]] = {}
        for std_key, provider_config in source_mapping.items():
            cfg = provider_config.get(self.provider_id, {})
            if isinstance(cfg, list):
                compiled[std_key] = {"aliases": cfg, "transform": None}
            elif isinstance(cfg, dict):
                compiled[std_key] = {
                    # 🛡️ 修复：防止手滑写出 "aliases": None 导致后续列表操作崩溃
                    "aliases": cfg.get("aliases") or [],
                    "transform": cfg.get("transform"),
                }
        return compiled
    
    def _get_composed_mapping(self, task_name: str) -> Dict[str, Dict[str, Any]]:
        if task_name in self._compiled_cache:
            return self._compiled_cache[task_name]
        
        mappings_to_apply = TASK_MAPPING_ROUTER.get(task_name, [META_MAPPING])
        
        composed_mapping: Dict[str, Dict[str, Any]] = {}
        for mapping in mappings_to_apply:
            compiled_subset = self._compile_mapping(mapping)
            for std_key, cfg in compiled_subset.items():
                if std_key in composed_mapping:
                    existing_aliases = composed_mapping[std_key].get("aliases") or []
                    # 🛡️ 修复：严防 new_aliases 为 None
                    new_aliases = cfg.get("aliases") or []
                    merged_aliases = existing_aliases + [a for a in new_aliases if a not in existing_aliases]
                    composed_mapping[std_key]["aliases"] = merged_aliases
                    if composed_mapping[std_key].get("transform") is None and cfg.get("transform"):
                        composed_mapping[std_key]["transform"] = cfg.get("transform")
                else:
                    composed_mapping[std_key] = cfg
        
        self._compiled_cache[task_name] = composed_mapping
        return composed_mapping

    def normalize(self, raw_list: List[Dict[str, Any]], task_name: str, period_type=None, is_cumulative=None):
        if not raw_list:
            return[]
        
        active_mapping = self._get_composed_mapping(task_name)
        is_unconfigured_task = task_name not in TASK_MAPPING_ROUTER
        
        cleaned_records =[]
        for raw in raw_list:
            # 1. 核心纠偏：客观数据推翻主观推断
            real_rt = detect_report_type(raw)
            final_report_type = real_rt if real_rt else period_type

            # 2. 初始化骨架，彻底消灭魔法字符串
            kwargs: Dict[str, Any] = {
                MetaKey.REPORT_TYPE: final_report_type,
                MetaKey.IS_CUMULATIVE: is_cumulative,
                "raw_provider_data": raw,
            }
            
            # 只有进入路由管辖范围的任务，才配拥有隔离区
            if not is_unconfigured_task:
                kwargs["unmapped_others"] = {}

            consumed_raw_keys: Set[str] = set()
            
            # ==========================================
            # 3. 提取引擎：事务原子性 + 严格 Fallback
            # ==========================================
            for std_key, cfg in active_mapping.items():
                aliases = cfg.get("aliases") or []
                transform = cfg.get("transform")
                
                final_val = None
                
                # 🚀 场景 A：虚拟字段 (无别名，纯靠 raw 和 transform 计算，如做空变化率)
                if not aliases and transform:
                    try:
                        # 虚拟字段的 val 传 None，全部依赖 raw 字典推导
                        temp_val = transform(None, raw)
                        if is_valid_value(temp_val):
                            final_val = temp_val
                    except Exception:
                        pass
                
                # 🚀 场景 B：标准字段 (有别名，严格顺序 Fallback)
                elif aliases:
                    for alias in aliases:
                        raw_val = raw.get(alias)
                        if is_valid_value(raw_val):
                            try:
                                temp_val = transform(raw_val, raw) if transform else raw_val
                                if is_valid_value(temp_val):
                                    final_val = temp_val
                                    break  # 💥 彻底成功，跳出 Fallback
                            except Exception:
                                continue
                
                # ------------------------------------------
                # 落库与打标 (通用后处理)
                # ------------------------------------------
                if final_val is not None:
                    # 兼容性防御：老旧 DATE_FIELDS 处理
                    if std_key in DATE_FIELDS and hasattr(final_val, 'strftime'):
                        final_val = final_val.strftime("%Y-%m-%d")
                    
                    kwargs[std_key] = final_val
                    
                    # 销毁污染源：只销毁定义了 aliases 的源字段。
                    # 虚拟字段因为没有 aliases，所以不会错误地吃掉 raw 数据。
                    if aliases:
                        for alias in aliases:
                            if alias in raw and is_valid_value(raw.get(alias)):
                                consumed_raw_keys.add(alias)

            
            # ==========================================
            # 4. 剩余数据透传 (彻底贯彻原汁原味)
            # ==========================================
            if is_unconfigured_task:
                # 自由任务：平铺直入顶层！
                for raw_key, raw_val in raw.items():
                    # 🛡️ 修复 1：增加 `raw_key not in kwargs`，防止底层脏数据覆盖 REPORT_TYPE 等核心元数据！
                    # 🛡️ 修复 2：绝对保真，只要 isValid，不论是 list/dict，统统放行！
                    if raw_key not in consumed_raw_keys and raw_key not in kwargs:
                        if is_valid_value(raw_val):
                            kwargs[raw_key] = raw_val
            else:
                # 受控任务：原汁原味关进隔离区！
                if task_name not in STRICT_MAPPED_TASKS:
                    for raw_key, raw_val in raw.items():
                        if raw_key not in consumed_raw_keys:
                            # 🛡️ 修复 3：解除原有的 isinstance 封印，保留原始嵌套层级！
                            if is_valid_value(raw_val):
                                kwargs["unmapped_others"][raw_key] = raw_val
            
            # ==========================================
            # 5. Pydantic 边界安检
            # ==========================================
            try:
                record = StandardFinancialRecord(**kwargs)
                cleaned_records.append(record.dump_for_pack())
            except Exception as e:
                print(f"  [Adapter] Validation dropped record: {e}")
                
        return cleaned_records


# ==========================================
# 🚀 Track 2 事件流标准化引擎
# 与 DynamicFinancialAdapter (Track 1) 平行对称
#
# 关键区别：
# - Track 1: 白名单重建（只保留映射表中的字段）
# - Track 2: 原地翻译（保留未映射字段，删除已消费的非标原始键）
# ==========================================
def normalize_events(
    raw_data: List[Dict[str, Any]],
    provider_id: str = "",
) -> List[Dict[str, Any]]:
    """
    事件流字段标准化（BaseFetcher Track 2 的单行委托入口）

    Args:
        raw_data: 原始事件记录列表
        provider_id: 数据源标识 ("akshare" / "obb" / "yfinance")

    Returns:
        标准化后的记录列表（原地修改）
    """
    from alphaflow.core.acl.mappings.events import EVENT_STREAM_MAPPING, DATE_CANDIDATES

    if not raw_data or not provider_id:
        return raw_data

    # 编译当前 provider 的一维查找表：{原始别名: (标准键, transform_fn)}
    lookup: Dict[str, tuple] = {}
    for std_key, provider_configs in EVENT_STREAM_MAPPING.items():
        cfg = provider_configs.get(provider_id)
        if cfg is None:
            continue

        if isinstance(cfg, list):
            for alias in cfg:
                lookup[alias] = (std_key, None)
        elif isinstance(cfg, dict):
            transform_fn = cfg.get("transform")
            for alias in cfg.get("aliases", []):
                lookup[alias] = (std_key, transform_fn)

    # 逐条记录执行映射
    for item in raw_data:
        mapped_keys: Dict[str, Any] = {}
        consumed_originals: set = set()

        for old_key in list(item.keys()):
            if old_key in lookup:
                std_key, transform_fn = lookup[old_key]
                if std_key not in item and std_key not in mapped_keys:
                    raw_val = item[old_key]
                    if transform_fn:
                        mapped_keys[std_key] = transform_fn(raw_val, item)
                    else:
                        mapped_keys[std_key] = raw_val
                if old_key != std_key:
                    consumed_originals.add(old_key)

        item.update(mapped_keys)

        # 清除已消费的非标原始键
        for old_key in consumed_originals:
            item.pop(old_key, None)

        # period_ending 提取
        if "period_ending" not in item:
            for candidate in DATE_CANDIDATES:
                date_val = item.get(candidate)
                if date_val:
                    try:
                        item["period_ending"] = pd.to_datetime(date_val).strftime(
                            "%Y-%m-%d"
                        )
                    except Exception:
                        pass
                    break

    return raw_data

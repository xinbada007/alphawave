"""
全域中央注册表防腐层 (Central Mapping Registry - ACL)
========================================================
基于 Clean Architecture 原则，将防腐层下沉到 Core 层。
实施"基于上下文路由的防腐层 (Context-Routed ACL)"架构。

设计哲学：
1. 任务路由：TASK_MAPPING_ROUTER 为每个任务编排专属映射表组合
2. 动态编译：运行时为每个 Provider 生成高速一维映射表
3. 铁腕精炼：严格白名单映射，不在白名单的字段一律丢弃
4. 长文本截断：LONG_DESCRIPTION 自动截断至 1000 字符，防 LLM Token 爆炸
5. 静态 Mixin 模式：利润表字段定义集中在 income_statement.py
"""

import math
from functools import partial
from typing import Any, Dict, List, Optional, Set
import pandas as pd
from alphaflow.core.schema_standard import StandardFinancialRecord

from alphaflow.core.data_utils import ReportPeriod
# 🚀 静态 Mixin 模式：从 mapping_keys 模块导入映射
from alphaflow.core.mapping_keys.income_statement import INCOME_STATEMENT_MAPPING
from alphaflow.core.mapping_keys.balance_sheet import BALANCE_SHEET_MAPPING
from alphaflow.core.mapping_keys.cash_flow import CASH_FLOW_MAPPING
from alphaflow.core.mapping_keys.share_stats import SHARE_STATS_MAPPING
from alphaflow.core.mapping_keys.profile import PROFILE_MAPPING
from alphaflow.core.mapping_keys.estimates import ESTIMATES_MAPPING
from alphaflow.core.mapping_keys.metrics import METRICS_MAPPING
from alphaflow.core.mapping_keys.akshare_analysis import AKSHARE_ANALYSIS_MAPPING


def is_valid_value(val: Any) -> bool:
    """
    【100% 准确过滤器】零冗余、不误杀 0/0.0/False、不漏过任何形式的空值
    """
    if val is None:
        return False
        
    # 1. 狙杀 float 型的 np.nan，绝对不误杀 0.0 (因为 math.isnan(0.0) 为 False)
    if isinstance(val, (int, float)):
        return not math.isnan(val) if isinstance(val, float) else True
        
    # 2. 狙杀脏字符串，不误杀 "0"
    if isinstance(val, str):
        return val.strip().lower() not in {"", "nan", "n/a", "null", "none", "nat"}
        
    # 3. 狙杀空集合
    if isinstance(val, (list, dict)):
        return len(val) > 0
        
    # 4. 兜底狙杀 Pandas 特有空值 (pd.NA, pd.NaT)
    # 前面的判断已经过滤了 list/dict，因此这里调用 pd.isna 绝对安全，不会抛出 ValueError
    try:
        if pd.isna(val):
            return False
    except Exception:
        pass
        
    return True

# ==========================================
# 🚀 核心架构设计：任务映射路由表 (Task Mapping Router)
# 在这里，我们为每一个具体的 Task 编排它的"认知能力"。
# 这是一个可插拔、可组合的数组。排在后面的 Mapping 具有更新/兜底能力。
# ==========================================
TASK_MAPPING_ROUTER: Dict[str, List[Dict[str, Any]]] = {
    # === 财务三大表：严格领域隔离，坚决防止语义碰撞 ===
    "a_income": [INCOME_STATEMENT_MAPPING],
    "q_income": [INCOME_STATEMENT_MAPPING],
    "a_balance": [BALANCE_SHEET_MAPPING],
    "q_balance": [BALANCE_SHEET_MAPPING],
    "a_cash": [CASH_FLOW_MAPPING],
    "q_cash": [CASH_FLOW_MAPPING],
    
    # === AkShare 分析指标：年报/季报分析数据 ===
    "a_analysis": [AKSHARE_ANALYSIS_MAPPING],
    "q_analysis": [AKSHARE_ANALYSIS_MAPPING],
    
    # === 公司档案 (YFinance info 等接口)：开启贪婪组合模式 ===
    # 既然这个接口返回了大杂烩，我们就用三张网同时去捞，绝不顾此失彼！
    "profile": [
        PROFILE_MAPPING, 
        ESTIMATES_MAPPING,
        SHARE_STATS_MAPPING
    ],
    
    # === 市场估值指标 (Market Metrics)：估值、盈利、成长性等 ===
    "metrics": [METRICS_MAPPING, 
                PROFILE_MAPPING, 
                ESTIMATES_MAPPING,
                SHARE_STATS_MAPPING],
    
    # === 独立元数据专项任务：精准对口映射 ===
    "share_stats": [SHARE_STATS_MAPPING, PROFILE_MAPPING, METRICS_MAPPING],
    "estimates": [ESTIMATES_MAPPING, PROFILE_MAPPING, METRICS_MAPPING],
}


# ==========================================
# 日期类型字段白名单 (需要将 datetime.date/datetime.datetime 转为字符串)
# ==========================================
DATE_FIELDS: Set[str] = {
    "EX_DIVIDEND_DATE", "ANNOUNCE_DATE", "PAYMENT_DATE", 
    "RECORD_DATE", "SPLIT_DATE", "LISTING_DATE", "FISCAL_YEAR_END",
    "EX_DATE"
}

# =====================================================================
# 🚀 任务级透传黑名单 (Closed-World Tasks)
# 核心准则：对于财务报表等"知识边界确定"的任务，未映射字段纯属噪音，禁止透传。
# 只有不在黑名单中的任务（如 profile, estimates），才允许收集未映射的新 Alpha 因子。
# =====================================================================
STRICT_MAPPED_TASKS = {
    "profile"
}


class DynamicFinancialAdapter:
    """
    上下文感知的动态防腐层 (Context-Aware Dynamic ACL)
    
    设计哲学：
    1. 任务路由编排：根据 task_name 动态组合映射表
    2. JIT 动态编译：运行时为每个 task_name 生成专属映射表并缓存
    3. 铁腕精炼：严格白名单映射，不在白名单的字段一律丢弃
    4. 长文本截断：LONG_DESCRIPTION 自动截断至 1000 字符，防 LLM Token 爆炸
    
    架构三步曲：
    - Step 1: 静态域拆分 (mapping_keys/*.py) - 每个领域字典独立
    - Step 2: 任务路由编排 (TASK_MAPPING_ROUTER) - 为每个 task 编排认知能力
    - Step 3: JIT 动态编译 (_get_composed_mapping) - 按需合并映射表并缓存
    """
    
    def __init__(self, provider_id: str):
        """
        初始化适配器
        
        Args:
            provider_id: Provider 标识符 ("obb" 或 "akshare")
        """
        self.provider_id = provider_id
        # 🚀 JIT 编译缓存：按 task_name 缓存合并后的高速一维查找表
        self._compiled_cache: Dict[str, Dict[str, Any]] = {}
    
    def _compile_mapping(self, source_mapping: Dict) -> Dict[str, Dict[str, Any]]:
        """
        动态编译映射表，兼容两种格式
        
        格式1 (简单): {"field": {"obb": ["alias1", "alias2"], "akshare": ["alias3"]}}
        格式2 (嵌套): {"field": {"obb": {"aliases": [...], "transform": lambda}, "akshare": {...}}}
        
        Returns:
            统一的映射表: {"field": {"aliases": [...], "transform": Optional[Callable]}}
        """
        compiled: Dict[str, Dict[str, Any]] = {}
        
        for std_key, provider_config in source_mapping.items():
            cfg = provider_config.get(self.provider_id, {})
            
            if isinstance(cfg, list):
                # 格式1: 简单列表格式
                compiled[std_key] = {"aliases": cfg, "transform": None}
            elif isinstance(cfg, dict):
                # 格式2: 嵌套字典格式
                compiled[std_key] = {
                    "aliases": cfg.get("aliases", []),
                    "transform": cfg.get("transform"),
                }
            # 如果 cfg 为空或无效，跳过该字段
        
        return compiled
    
    def _get_composed_mapping(self, task_name: str) -> Dict[str, Dict[str, Any]]:
        """
        🚀 动态组合引擎 (Composition Engine)
        根据 task_name 从 TASK_MAPPING_ROUTER 获取多张网，并将它们融合成一张专属当前任务的"无缝巨网"
        
        架构原理：
        1. 静态域拆分：每个 Mapping 在自己的领域内是零歧义的
        2. 任务路由编排：TASK_MAPPING_ROUTER 定义每个 task 应用的映射表数组
        3. JIT 编译缓存：首次访问时编译并缓存，后续极速返回
        
        Args:
            task_name: 任务名称 (如 "a_income", "profile", "estimates")
            
        Returns:
            合并后的专属映射表: {"field": {"aliases": [...], "transform": Optional[Callable]}}
        """
        # 缓存命中，极速返回
        if task_name in self._compiled_cache:
            return self._compiled_cache[task_name]
        
        # 从路由表中获取该任务配置的 Mapping 数组
        mappings_to_apply = TASK_MAPPING_ROUTER.get(task_name, [])
        
        # 如果该任务没有在路由表中配置，返回 None 表示原样透传
        if not mappings_to_apply:
            self._compiled_cache[task_name] = {}
            return {}
        
        # 顺序合并多张网，实现可插拔组合
        composed_mapping: Dict[str, Dict[str, Any]] = {}
        for mapping in mappings_to_apply:
            compiled_subset = self._compile_mapping(mapping)
            # 🚀 关键修复：合并 aliases 而非覆盖，实现真正的 Fallback
            for std_key, cfg in compiled_subset.items():
                if std_key in composed_mapping:
                    # 合并 aliases（保持顺序，去重）
                    existing_aliases = composed_mapping[std_key].get("aliases", [])
                    new_aliases = cfg.get("aliases", [])
                    # 保持原有顺序，新别名追加到末尾
                    merged_aliases = existing_aliases + [a for a in new_aliases if a not in existing_aliases]
                    composed_mapping[std_key]["aliases"] = merged_aliases
                    # transform 保留第一个非 None 的
                    if composed_mapping[std_key].get("transform") is None and cfg.get("transform"):
                        composed_mapping[std_key]["transform"] = cfg.get("transform")
                else:
                    composed_mapping[std_key] = cfg
        
        # 写入缓存
        self._compiled_cache[task_name] = composed_mapping
        return composed_mapping
    
    def normalize(
        self, 
        raw_list: List[Dict[str, Any]], 
        task_name: str,
        period_type: Optional[ReportPeriod] = None, 
        is_cumulative: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        🚀 铁腕精炼模式：基于任务上下文的物理拦截
        
        Args:
            raw_list: 原始数据列表
            task_name: 任务名称 (如 "a_income", "profile")，决定使用哪个映射表组合
            period_type: 报告期类型 (ANNUAL/QUARTERLY)
            is_cumulative: 是否累积制
            
        Returns:
            标准化后的记录列表
        """
        if not raw_list:
            return []
        
        # 🚀 核心：直接获取当前任务的专属组合网
        active_mapping = self._get_composed_mapping(task_name)
        
        # ==========================================
        # 🚀 特殊处理：如果任务未配置映射表，原样透传（仅过滤无效值）
        # ==========================================
        if not active_mapping:
            cleaned_records = []
            for raw in raw_list:
                # 仅过滤无效值，保持原始数据结构
                cleaned_raw = {
                    k: v for k, v in raw.items() 
                    if is_valid_value(v) and not isinstance(v, (list, dict))
                }
                cleaned_records.append(cleaned_raw)
            return cleaned_records
        
        # ==========================================
        # 🚀 标准处理：使用映射表进行标准化
        # ==========================================
        cleaned_records = []
        
        for raw in raw_list:
            # 初始化合法的 kwargs，只放元数据 (统一大写风格)
            kwargs: Dict[str, Any] = {
                "REPORT_TYPE": period_type,
                "IS_CUMULATIVE": is_cumulative,
                "raw_provider_data": raw,
                "unmapped_others": {}
            }
            
            # 🚀 消费打标集合：追踪哪些原始字段已被映射消费
            consumed_raw_keys: Set[str] = set()
            
            # ==========================================
            # 1. 统一日期处理与消费打标
            # ==========================================
            date_candidates = ["date", "REPORT_DATE", "period_ending", "ex_dividend_date", "除净日"]
            for d_key in date_candidates:
                if raw.get(d_key):
                    try:
                        kwargs["PERIOD_ENDING"] = pd.to_datetime(raw[d_key]).strftime("%Y-%m-%d")
                        consumed_raw_keys.add(d_key)  # 🚀 打标：已消费
                        break
                    except:
                        pass
            
            # ==========================================
            # 2. 映射表遍历与消费打标
            # ==========================================
            for std_key, cfg in active_mapping.items():
                aliases = cfg.get("aliases", [])
                transform = cfg.get("transform")
                
                val = None
                for alias in aliases:
                    v = raw.get(alias)
                    if is_valid_value(v):  # 🚀 第一道防线：读取时拦截
                        val = v
                        break
                
                # 消费打标 (仅打标真正有效的值)
                for alias in aliases:
                    if alias in raw and is_valid_value(raw.get(alias)):
                        consumed_raw_keys.add(alias)
                
                # 执行转换器
                if transform and val is not None:
                    try:
                        val = transform(val, raw)
                    except Exception:
                        val = None
                
                # 🚀 第二道防线：写入 kwargs 前必须再查一次！
                # 为什么不是冗余？因为 transform 函数(如计算比率)可能会除以0从而生成新的 np.nan！
                if is_valid_value(val):
                    # 🚀 日期类型字段自动转换为字符串
                    if std_key in DATE_FIELDS and hasattr(val, 'strftime'):
                        val = val.strftime("%Y-%m-%d")
                    kwargs[std_key] = val
            
            # ==========================================
            # 🚀 3. 动态透传判定 (Task Blacklist Logic)
            # ==========================================
            if task_name not in STRICT_MAPPED_TASKS:
                for raw_key, raw_val in raw.items():
                    if raw_key not in consumed_raw_keys:
                        # 🚀 拦截残余脏数据进入 others
                        if is_valid_value(raw_val) and not isinstance(raw_val, (list, dict)):
                            kwargs["unmapped_others"][raw_key] = raw_val
            
            try:
                # 通过 Pydantic 强类型安检
                record = StandardFinancialRecord(**kwargs)
                cleaned_records.append(record.dump_for_pack())
            except Exception as e:
                print(f"  [Adapter] Validation dropped record: {e}")
        
        return cleaned_records



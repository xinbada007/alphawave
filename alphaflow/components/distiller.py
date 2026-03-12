import re
import pandas as pd
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Optional

# 假设你的 BaseProcessor 定义在 alphaflow.core.base 中
from alphaflow.core.base import BaseProcessor
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.core.data_utils import FIELD_CHAINS

# ==========================================
# 1. 声明式配置 (严格的边界正则)
# ==========================================
DEFAULT_DISTILL_SCHEMA: Dict[str, List[str]] = {
    # 只匹配完全等于这几个特定名字的 Key
    r"^(a_income|q_income.*|income_statement.*)$": ["REV", "GP", "OI", "NI", "TAX"],
    
    r"^(a_balance|q_balance.*|balance_sheet.*)$": ["C_ASSETS", "CASH_AND_EQUIV", "TOTAL_ASSETS", "C_LIAB", "LIAB", "EQUITY"],
    
    r"^(a_cash|q_cash.*|cash_flow.*)$": ["OCF", "ICF", "CAPEX", "FCF"],
    
    r"^(a_analysis|q_analysis.*)$": ["REV_GROWTH_YOY", "NI_GROWTH_YOY", "ROE", "GROSS_MARGIN", "NET_MARGIN"]
}

ALWAYS_KEEP_META = ["PERIOD_ENDING", "REPORT_DATE", "DATE_TYPE_CODE", "START_DATE"]


# ==========================================
# 2. 脏数据拦截器
# ==========================================
def is_empty_value(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, (int, float)) and pd.isna(val):
        return True
    if isinstance(val, str):
        if val.strip().lower() in ("", "n/a", "nan", "-", "null", "none"):
            return True
    return False


# ==========================================
# 3. 翻译策略
# ==========================================
@dataclass
class DistillRule:
    abstract_concepts: List[str]
    _allowed_physical_keys: Set[str] = field(init=False)

    def __post_init__(self):
        self._allowed_physical_keys = set(ALWAYS_KEEP_META)
        for concept in self.abstract_concepts:
            self._allowed_physical_keys.update(FIELD_CHAINS.get(concept, [concept]))

    def apply(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """对容器内的叶子节点执行清洗"""
        result = {}
        for k, v in record.items():
            if k in self._allowed_physical_keys:
                result[k] = None if is_empty_value(v) else v
        return result


# ==========================================
# 4. 核心管道组件 (继承 BaseProcessor)
# ==========================================
class DataDistiller(BaseProcessor):
    """
    数据蒸馏器 Processor
    作为 Pipeline 的最后一环，原地突变 (In-place) 数据，为 LLM 准备高信噪比 JSON。
    """
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.enabled = self.config.get("enabled", True)
        schema = self.config.get("schema", DEFAULT_DISTILL_SCHEMA)
        
        self._rules: List[tuple[re.Pattern, DistillRule]] = []
        for pattern_str, concepts in schema.items():
            self._rules.append((re.compile(pattern_str, re.IGNORECASE), DistillRule(concepts)))

    def _get_rule(self, node_key: str) -> Optional[DistillRule]:
        for pattern, rule in self._rules:
            if pattern.search(node_key):
                return rule
        return None

    def _walk(self, key: str, data: Any) -> Any:
        """结构 + 语义 双重守卫遍历"""
        
        # 结构 1: 列表序列
        if isinstance(data, list):
            if not data: return []
            rule = self._get_rule(key)
            
            # 【结构守卫】：只有列表内装的是 Dict (如历史报表)，才执行规则
            if rule and isinstance(data[0], dict):
                return [rule.apply(item) for item in data]
                
            # 若不是报表结构，递归向下找
            return [self._walk(key, item) for item in data]

        # 结构 2: 字典快照
        if isinstance(data, dict):
            rule = self._get_rule(key)
            
            # 【结构守卫】：当前层级是 Dict，且命中词法规则，直接清洗它
            if rule:
                return rule.apply(data)
                
            # 作为目录容器，继续深入
            return {k: self._walk(k, v) for k, v in data.items()}

        # 结构 3: 叶子节点标量
        # 【最终防御】：不论 key 叫什么，只要它是标量，一律跳过报表清洗逻辑，只做空值格式化
        if is_empty_value(data):
            return None
            
        return data

    async def process_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        """Pipeline 统一调度接口"""
        input_data = kwargs.get("input_data")
        pack: ResearchPack = input_data.payload if isinstance(input_data, ComponentOutput) else input_data

        if not self.enabled or not pack:
            return ComponentOutput(success=True, payload=pack)

        # 零拷贝原地修改 (In-place Mutation)
        if pack.fundamentals:
            pack.fundamentals = self._walk("root_fundamentals", pack.fundamentals)
            
        if pack.extra:
            pack.extra = self._walk("root_extra", pack.extra)

        print(f"  [Distiller] Successfully condensed data payload for {pack.symbol}.")
        
        return ComponentOutput(success=True, payload=pack)
"""
基本面提取策略基类 (Fundamental Strategy Base)
=============================================
定义所有 Extractor 的抽象基类和兜底策略。

设计原则：
1. 策略模式 (Strategy Pattern)：每个 MarketType 对应一个具体策略
2. 零回退原则：未命中策略时，使用 Passthrough 而非回退到其他市场
3. 纯 Python 实现：100% 原生数据结构，0 JSON 序列化隐患
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from alphaflow.core.utils import MarketType


# ==========================================
# 1. 策略基类 (Abstract Base Strategy)
# ==========================================
class BaseExtractorStrategy(ABC):
    """
    策略抽象基类
    所有具体策略必须实现 extract() 方法
    """
    
    @abstractmethod
    def extract(self, raw_data: Any) -> Any:
        """
        执行数据提取/清洗
        
        Args:
            raw_data: 原始数据 (Dict / List)
        
        Returns:
            清洗后的数据结构
        """
        pass


# ==========================================
# 2. 绝对安全兜底策略 (Default Passthrough)
# ==========================================
class DefaultPassthroughStrategy(BaseExtractorStrategy):
    """
    【绝对安全兜底策略】
    
    触发条件：遇到未知市场（如未来的 EU 市场），且系统尚未开发对应策略时。
    执行动作：原样返回，不做任何修改。
    
    防呆机制：
    - 列表类型最多截取前 10 条，防止 Token 爆炸
    - 绝对不尝试解析或转换字段
    """
    
    def extract(self, raw_data: Any) -> Any:
        # 你给我什么，我退什么，绝不擅自篡改
        if isinstance(raw_data, list):
            # 防御性截断，防止 LLM Token 爆炸
            if len(raw_data) > 10:
                return raw_data[:10]
        return raw_data


# ==========================================
# 3. 策略工厂 (Strategy Factory)
# ==========================================
class StrategyFactory:
    """
    策略工厂：根据 MarketType 动态路由到对应策略
    
    设计原则：
    - 未命中策略时，返回 DefaultPassthroughStrategy（而非回退到 US）
    """
    
    # 子类需要在注册表中注册具体策略
    _registry: Dict[str, Dict[MarketType, BaseExtractorStrategy]] = {}
    
    @classmethod
    def register(
        cls, 
        domain: str, 
        market_type: MarketType, 
        strategy: BaseExtractorStrategy
    ) -> None:
        """
        注册策略
        
        Args:
            domain: 领域名 (如 "profile", "insider")
            market_type: 市场类型
            strategy: 具体策略实例
        """
        if domain not in cls._registry:
            cls._registry[domain] = {}
        cls._registry[domain][market_type] = strategy
    
    @classmethod
    def get_strategy(
        cls, 
        domain: str, 
        market_type: MarketType
    ) -> BaseExtractorStrategy:
        """
        获取策略
        
        Args:
            domain: 领域名
            market_type: 市场类型
        
        Returns:
            对应的策略实例，未命中则返回 DefaultPassthroughStrategy
        """
        strategies = cls._registry.get(domain, {})
        return strategies.get(market_type, DefaultPassthroughStrategy())


# ==========================================
# 4. 通用字段映射工具函数
# ==========================================
def standardize_field(
    source: Dict[str, Any],
    target_key: str,
    field_chains: Dict[str, List[str]]
) -> Optional[Any]:
    """
    从源数据中提取目标字段，支持多别名映射
    
    Args:
        source: 源数据字典
        target_key: 目标键名
        field_chains: 字段映射链
    
    Returns:
        字段值，未找到返回 None
    """
    candidates = field_chains.get(target_key, [target_key])
    
    for candidate in candidates:
        value = source.get(candidate)
        if value is not None and value != "":
            return value
    
    return None


def standardize_fields(
    source: Dict[str, Any],
    field_chains: Dict[str, List[str]]
) -> Dict[str, Any]:
    """
    批量标准化字段
    
    Args:
        source: 源数据字典
        field_chains: 字段映射链
    
    Returns:
        标准化后的字典
    """
    result = {}
    for target_key in field_chains.keys():
        value = standardize_field(source, target_key, field_chains)
        if value is not None:
            result[target_key] = value
    return result

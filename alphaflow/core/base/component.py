from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar, Generic
from alphaflow.core.schema.models import AnalysisContext, ComponentOutput, ResearchPack

# 🚀 V3 架构升级：泛型组件基类
T_out = TypeVar("T_out")


class BaseComponent(ABC, Generic[T_out]):
    """
    AlphaFlow 所有组件的泛型基类。
    
    V3 升级：引入泛型参数 T_out，明确指定 execute() 返回的 ComponentOutput 的 payload 类型。
    """
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}

    def setup(self):
        """(可选) 初始化资源，如加载模型、建立数据库连接"""
        pass

    def teardown(self):
        """(可选) 释放资源"""
        pass

    @abstractmethod
    async def execute(self, context: AnalysisContext, **kwargs) -> ComponentOutput[T_out]:
        """
        核心执行逻辑。必须由子类实现。
        
        Returns:
            ComponentOutput[T_out]: 标准输出，payload 类型为 T_out
        """
        pass


class BaseCollector(BaseComponent[ResearchPack]):
    """
    数据采集器基类：明确输出为 ResearchPack。
    
    职责：从 OpenBB 或外部 API 获取原始数据，封装为 ResearchPack。
    """
    async def execute(self, context: AnalysisContext, **kwargs) -> ComponentOutput[ResearchPack]:
        return await self.fetch_data(context, **kwargs)

    @abstractmethod
    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput[ResearchPack]:
        """
        子类必须实现的数据获取逻辑。
        
        Returns:
            ComponentOutput[ResearchPack]: 包含 ResearchPack 的标准输出
        """
        pass

    @staticmethod
    def _unpack_pack(context: AnalysisContext, kwargs: Dict[str, Any]) -> ResearchPack:
        """从 pipeline kwargs 中统一解出 ResearchPack。

        - 若 input_data 是 ComponentOutput 且 payload 非空 → 取 payload
        - 否则若 input_data 直接是 pack → 直接使用
        - 都不是 → 新建空 pack（symbol=context.symbols[0]）

        所有 Collector 子类应优先调用本方法，避免在 fetch_data 顶部重复 5 行解包模板。
        """
        input_data = kwargs.get("input_data")
        if isinstance(input_data, ComponentOutput) and input_data.payload is not None:
            pack = input_data.payload
        else:
            pack = input_data
        if pack is None:
            pack = ResearchPack(symbol=context.symbols[0])
        return pack


class BaseProcessor(BaseComponent[ResearchPack]):
    """
    逻辑处理器基类：明确输入和输出的 Payload 均为 ResearchPack。
    
    职责：接收数据，进行计算（清洗、因子计算、AI推理）。
    这里利用 kwargs["input_data"] 接收上游数据，并在类型提示中明确契约。
    """
    async def execute(
        self, context: AnalysisContext, input_data: Any = None, **kwargs
    ) -> ComponentOutput[ResearchPack]:
        return await self.process(context, input_data, **kwargs)

    @abstractmethod
    async def process(
        self, context: AnalysisContext, input_data: Any, **kwargs
    ) -> ComponentOutput[ResearchPack]:
        """
        子类必须实现的处理逻辑。
        
        Args:
            context: 分析上下文
            input_data: 上游输入数据（通常是 ComponentOutput[ResearchPack]）
            
        Returns:
            ComponentOutput[ResearchPack]: 处理后的 ResearchPack 输出
        """
        pass


class BaseVisualizer(BaseComponent[ResearchPack]):
    """
    可视化器基类：明确输出为 ResearchPack（通常附带图表 URL）。
    
    职责：将数据转换为图表配置或 URL。
    """
    async def execute(
        self, context: AnalysisContext, input_data: Any = None, **kwargs
    ) -> ComponentOutput[ResearchPack]:
        return await self.visualize(context, input_data, **kwargs)

    @abstractmethod
    async def visualize(
        self, context: AnalysisContext, input_data: Any, **kwargs
    ) -> ComponentOutput[ResearchPack]:
        """
        子类必须实现的可视化逻辑。
        
        Returns:
            ComponentOutput[ResearchPack]: 附带图表信息的 ResearchPack
        """
        pass

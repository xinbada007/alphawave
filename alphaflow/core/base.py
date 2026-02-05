from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from alphaflow.core.schema import AnalysisContext, ComponentOutput

class BaseComponent(ABC):
    """
    AlphaFlow 所有组件的基类。
    """
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}

    def setup(self):
        """(可选) 初始化资源，如加载模型、建立数据库连接"""
        pass

    def teardown(self):
        """(可选) 释放资源"""
        pass

    @abstractmethod
    async def execute(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        """
        核心执行逻辑。必须由子类实现。
        """
        pass

class BaseCollector(BaseComponent):
    """
    数据采集器基类。
    职责：从 OpenBB 或外部 API 获取原始数据。
    """
    async def execute(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        return await self.fetch_data(context, **kwargs)

    @abstractmethod
    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        pass

class BaseProcessor(BaseComponent):
    """
    逻辑处理器基类。
    职责：接收数据，进行计算（清洗、因子计算、AI推理）。
    """
    async def execute(self, context: AnalysisContext, input_data: Any = None, **kwargs) -> ComponentOutput:
        return await self.process(context, input_data, **kwargs)

    @abstractmethod
    async def process(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        pass

class BaseVisualizer(BaseComponent):
    """
    可视化器基类。
    职责：将数据转换为图表配置或 URL。
    """
    async def execute(self, context: AnalysisContext, input_data: Any = None, **kwargs) -> ComponentOutput:
        return await self.visualize(context, input_data, **kwargs)

    @abstractmethod
    async def visualize(self, context: AnalysisContext, input_data: Any, **kwargs) -> ComponentOutput:
        pass

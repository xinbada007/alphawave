from typing import Any, Dict, Optional
from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack
from alphaflow.components.collectors.ashare import AshareCollector

# 延迟导入 FundamentalCollector，避免 OpenBB 未安装时导入失败
FundamentalCollector = None


def _get_fundamental_collector_class():
    """延迟获取 FundamentalCollector 类"""
    global FundamentalCollector
    if FundamentalCollector is None:
        from alphaflow.components.collectors.fundamental import FundamentalCollector as FC
        FundamentalCollector = FC
    return FundamentalCollector


class SmartCollector(BaseCollector):
    """
    智能行情采集器
    
    根据股票代码格式自动选择采集器：
    - 6位纯数字（A股代码）-> 使用 AshareCollector (Tushare)
    - 其他格式（美股、港股等）-> 使用 FundamentalCollector (OpenBB/yfinance)
    
    Examples:
        >>> collector = SmartCollector(name="smart")
        >>> # A股自动路由到 AshareCollector
        >>> result = await collector.fetch_data(AnalysisContext(symbols=["600036"]))
        >>> # 美股自动路由到 FundamentalCollector  
        >>> result = await collector.fetch_data(AnalysisContext(symbols=["AAPL"]))
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.config = config or {}
        
        # 初始化子采集器
        self.ashare_config = self.config.get("ashare", {})
        self.fundamental_config = self.config.get("fundamental", {
            "provider": self.config.get("provider", "yfinance")
        })
        
        self._ashare_collector: Optional[AshareCollector] = None
        self._fundamental_collector = None
    
    def _is_ashare_code(self, symbol: str) -> bool:
        """
        判断是否为A股代码（6位纯数字）
        
        Args:
            symbol: 股票代码
            
        Returns:
            是否为A股代码
        """
        if not symbol or not isinstance(symbol, str):
            return False
        
        symbol = symbol.strip()
        
        # 移除后缀检查（如果已经有后缀）
        if "." in symbol:
            parts = symbol.split(".")
            if len(parts) == 2:
                code, exchange = parts[0], parts[1].upper()
                # 检查是否为A股交易所
                if exchange in ("SZ", "SH", "BJ") and len(code) == 6 and code.isdigit():
                    return True
            return False
        
        # 纯代码，检查是否为6位数字
        return len(symbol) == 6 and symbol.isdigit()
    
    def _get_ashare_collector(self) -> AshareCollector:
        """获取或创建 AshareCollector 实例"""
        if self._ashare_collector is None:
            self._ashare_collector = AshareCollector(
                name=f"{self.name}_ashare",
                config=self.ashare_config
            )
        return self._ashare_collector
    
    def _get_fundamental_collector(self):
        """获取或创建 FundamentalCollector 实例"""
        if self._fundamental_collector is None:
            FC = _get_fundamental_collector_class()
            self._fundamental_collector = FC(
                name=f"{self.name}_fundamental",
                config=self.fundamental_config
            )
        return self._fundamental_collector
    
    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        """
        根据代码格式智能选择采集器获取数据
        
        Args:
            context: 分析上下文，包含股票代码
            
        Returns:
            ComponentOutput: 采集结果
        """
        symbol = context.symbols[0] if context.symbols else None
        
        if not symbol:
            return ComponentOutput(
                success=False,
                error="No symbol provided"
            )
        
        # 判断代码类型并选择采集器
        if self._is_ashare_code(symbol):
            print(f"  [Smart] Detected A-share code: {symbol}, using AshareCollector")
            collector = self._get_ashare_collector()
        else:
            print(f"  [Smart] Detected non-A-share code: {symbol}, using FundamentalCollector")
            collector = self._get_fundamental_collector()
        
        # 使用选中的采集器获取数据
        return await collector.fetch_data(context, **kwargs)


def is_ashare_symbol(symbol: str) -> bool:
    """
    工具函数：判断是否为A股代码
    
    Args:
        symbol: 股票代码
        
    Returns:
        是否为A股代码
        
    Examples:
        >>> is_ashare_symbol("600036")      # True
        >>> is_ashare_symbol("600036.SH")   # True
        >>> is_ashare_symbol("AAPL")        # False
        >>> is_ashare_symbol("00700.HK")    # False
    """
    if not symbol or not isinstance(symbol, str):
        return False
    
    symbol = symbol.strip()
    
    # 有后缀格式
    if "." in symbol:
        parts = symbol.split(".")
        if len(parts) == 2:
            code, exchange = parts[0], parts[1].upper()
            return exchange in ("SZ", "SH", "BJ") and len(code) == 6 and code.isdigit()
        return False
    
    # 无后缀格式
    return len(symbol) == 6 and symbol.isdigit()

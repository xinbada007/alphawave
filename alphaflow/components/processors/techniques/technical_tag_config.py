"""
技术面标签配置 (Technical Tag Config)
=====================================
与 HealthTagConfig 类似，将技术面打标的阈值抽离到配置层，
支持根据不同市场/股票类型进行差异化配置。

设计原则：
- 阈值可配置化，支持小盘股/蓝筹股差异化
- 默认值适合大多数大盘股
- 可通过实例化时传入自定义配置覆盖
"""

from typing import Dict, Any, Optional


class TechnicalTagConfig:
    """
    技术面标签配置
    
    使用方式：
        config = TechnicalTagConfig()  # 使用默认配置
        # 或
        config = TechnicalTagConfig({
            "VOLUME_SPIKE_MULTIPLIER": 2.0,  # 小盘股使用更高阈值
            "VOLUME_CONTRACTION_MULTIPLIER": 0.5,
        })
    """
    
    # 默认配置（适合大盘股/蓝筹股）
    DEFAULT: Dict[str, Any] = {
        # --- 量价异常阈值 ---
        "VOLUME_SPIKE_MULTIPLIER": 1.5,      # 放量倍数阈值
        "VOLUME_SPIKE_DROP_THRESHOLD": -0.02, # 放量暴跌日跌幅阈值
        "VOLUME_SPIKE_RALLY_THRESHOLD": 0.02, # 天量抢筹日涨幅阈值
        "VOLUME_CONTRACTION_MULTIPLIER": 0.6, # 缩量倍数阈值
        "VOLUME_CONTRACTION_DROP_THRESHOLD": -0.01, # 缩量阴跌跌幅阈值
        
        # --- Up/Down Volume Ratio ---
        "UP_DOWN_RATIO_BULL_THRESHOLD": 1.20,  # 买盘主导阈值
        "UP_DOWN_RATIO_BEAR_THRESHOLD": 0.85,  # 卖盘主导阈值
        
        # --- CMF 机构资金流向 ---
        "CMF_STRONG_ACCUMULATION": 0.20,      # 强流入阈值
        "CMF_MODERATE_INFLOW": 0.05,          # 轻微流入阈值
        "CMF_MODERATE_OUTFLOW": -0.05,        # 轻微流出阈值
        "CMF_STRONG_DISTRIBUTION": -0.20,     # 强流出阈值
        
        # --- RSI 超买超卖 ---
        "RSI_OVERSOLD_THRESHOLD": 30.0,       # RSI 超卖阈值
        "RSI_OVERBOUGHT_THRESHOLD": 70.0,     # RSI 超买阈值
        
        # --- 均线距离 ---
        "SMA_DISTANCE_THRESHOLD": 0.0,         # 站上/跌破均线阈值
    }
    
    def __init__(self, custom_config: Optional[Dict[str, Any]] = None):
        """
        初始化配置
        
        Args:
            custom_config: 自定义配置，会覆盖默认值
        """
        self._config = {**self.DEFAULT}
        if custom_config:
            self._config.update(custom_config)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._config.get(key, default)
    
    @property
    def VOLUME_SPIKE_MULTIPLIER(self) -> float:
        return self._config["VOLUME_SPIKE_MULTIPLIER"]
    
    @property
    def VOLUME_SPIKE_DROP_THRESHOLD(self) -> float:
        return self._config["VOLUME_SPIKE_DROP_THRESHOLD"]
    
    @property
    def VOLUME_SPIKE_RALLY_THRESHOLD(self) -> float:
        return self._config["VOLUME_SPIKE_RALLY_THRESHOLD"]
    
    @property
    def VOLUME_CONTRACTION_MULTIPLIER(self) -> float:
        return self._config["VOLUME_CONTRACTION_MULTIPLIER"]
    
    @property
    def VOLUME_CONTRACTION_DROP_THRESHOLD(self) -> float:
        return self._config["VOLUME_CONTRACTION_DROP_THRESHOLD"]
    
    @property
    def UP_DOWN_RATIO_BULL_THRESHOLD(self) -> float:
        return self._config["UP_DOWN_RATIO_BULL_THRESHOLD"]
    
    @property
    def UP_DOWN_RATIO_BEAR_THRESHOLD(self) -> float:
        return self._config["UP_DOWN_RATIO_BEAR_THRESHOLD"]
    
    @property
    def RSI_OVERSOLD_THRESHOLD(self) -> float:
        return self._config["RSI_OVERSOLD_THRESHOLD"]
    
    @property
    def RSI_OVERBOUGHT_THRESHOLD(self) -> float:
        return self._config["RSI_OVERBOUGHT_THRESHOLD"]
    
    @property
    def CMF_STRONG_ACCUMULATION(self) -> float:
        return self._config["CMF_STRONG_ACCUMULATION"]
    
    @property
    def CMF_MODERATE_INFLOW(self) -> float:
        return self._config["CMF_MODERATE_INFLOW"]
    
    @property
    def CMF_MODERATE_OUTFLOW(self) -> float:
        return self._config["CMF_MODERATE_OUTFLOW"]
    
    @property
    def CMF_STRONG_DISTRIBUTION(self) -> float:
        return self._config["CMF_STRONG_DISTRIBUTION"]
    
    @property
    def SMA_DISTANCE_THRESHOLD(self) -> float:
        return self._config["SMA_DISTANCE_THRESHOLD"]


# 预定义的配置模板
class TechnicalTagPresets:
    """预设配置模板"""
    
    # 适合大盘股/蓝筹股（默认）
    BLUE_CHIP = TechnicalTagConfig()
    
    # 适合小盘股/妖股（波动更大）
    SMALL_CAP = TechnicalTagConfig({
        "VOLUME_SPIKE_MULTIPLIER": 2.0,
        "VOLUME_SPIKE_DROP_THRESHOLD": -0.03,
        "VOLUME_SPIKE_RALLY_THRESHOLD": 0.03,
        "VOLUME_CONTRACTION_MULTIPLIER": 0.4,
    })
    
    # 适合低流动性港股（需要更明显信号）
    LOW_LIQUIDITY_HK = TechnicalTagConfig({
        "VOLUME_SPIKE_MULTIPLIER": 3.0,
        "VOLUME_SPIKE_DROP_THRESHOLD": -0.05,
        "VOLUME_SPIKE_RALLY_THRESHOLD": 0.05,
        "VOLUME_CONTRACTION_MULTIPLIER": 0.3,
    })

"""
FundamentalDistillationAnalyzer 基本面蒸馏调度器
================================================
调度各个 Extractor，组装最终的 LLM-Ready 数据。

架构设计：
1. Orchestrator Pattern：analyze() 统筹调度，不含计算逻辑
2. 策略路由：根据 MarketType (US/HK/CN) 动态路由
3. 自描述输出：返回数据时附带 target_slot 字段

数据流：
  pack.fundamentals (原始数据)
        │
        ▼
  ┌─────────────────────────┐
  │ FundamentalDistillation │
  │        Analyzer         │
  └─────────────────────────┘
        │
        ├── ProfileExtractor ──► company_profile
        ├── InsiderExtractor ──► insider_sentiment
        ├── ConsensusExtractor ──► analyst_consensus
        └── DividendExtractor ──► dividend_growth
        (HealthTagger 不挂载，待后续斟酌)
        │
        ▼
  pack.technical_summary["fundamental_profile"]
  pack.technical_summary["insider_sentiment"]
  pack.technical_summary["analyst_consensus"]
  pack.technical_summary["dividend_growth"]
"""

from typing import Any, Dict, Protocol

from alphaflow.core.data_utils import MarketType
from alphaflow.core.facade import ResearchPackFacade
from alphaflow.core.schema import ResearchPack

from alphaflow.components.processors.fundamentals.base_strategy import (
    BaseExtractorStrategy,
    DefaultPassthroughStrategy,
)
from alphaflow.components.processors.fundamentals.profile_strategies import (
    HKProfileStrategy,
    USProfileStrategy,
    CNProfileStrategy,
)
from alphaflow.components.processors.fundamentals.insider_strategies import (
    HKInsiderStrategy,
    USInsiderStrategy,
    CNInsiderStrategy,
)
from alphaflow.components.processors.fundamentals.consensus_strategies import (
    GenericConsensusStrategy,
)
from alphaflow.components.processors.fundamentals.dividend_strategies import (
    USDividendStrategy,
    HKDividendStrategy,
    CNDividendStrategy,
)
from alphaflow.components.processors.fundamentals.fundamental_keys import (
    ProfileKey,
    ConsensusKey,
    DividendKey,
)


# ==========================================
# 1. FeatureAnalyzer 协议（保持与 TechnicalProcessor 一致）
# ==========================================
class FeatureAnalyzer(Protocol):
    """分析器协议 - 每个 Analyzer 自描述数据存储位置"""
    
    @property
    def target_slot(self) -> str:
        """返回目标槽位路径"""
        ...
    
    def analyze(self, pack: ResearchPack) -> Dict[str, Any]:
        ...


# ==========================================
# 2. Profile 提取器
# ==========================================
class ProfileExtractor:
    """
    Profile 静态档案提取器
    
    策略路由：
    - MarketType.US → USProfileStrategy
    - MarketType.HK → HKProfileStrategy
    - MarketType.CN → CNProfileStrategy
    - 其他 → DefaultPassthroughStrategy
    """
    
    def __init__(self):
        # 注册策略
        self._strategies = {
            MarketType.US: USProfileStrategy(),
            MarketType.HK: HKProfileStrategy(),
            MarketType.CN: CNProfileStrategy(),
        }
    
    def get_strategy(self, market_type: MarketType) -> BaseExtractorStrategy:
        return self._strategies.get(market_type, DefaultPassthroughStrategy())
    
    def extract(self, raw_data: Any, market_type: MarketType) -> Dict[str, Any]:
        strategy = self.get_strategy(market_type)
        return strategy.extract(raw_data)


# ==========================================
# 3. Insider 提取器
# ==========================================
class InsiderExtractor:
    """
    Insider 高管交易提取器
    
    策略路由：
    - MarketType.US → USInsiderStrategy
    - MarketType.HK → HKInsiderStrategy
    - MarketType.CN → CNInsiderStrategy
    - 其他 → DefaultPassthroughStrategy
    """
    
    def __init__(self):
        self._strategies = {
            MarketType.US: USInsiderStrategy(),
            MarketType.HK: HKInsiderStrategy(),
            MarketType.CN: CNInsiderStrategy(),
        }
    
    def get_strategy(self, market_type: MarketType) -> BaseExtractorStrategy:
        return self._strategies.get(market_type, DefaultPassthroughStrategy())
    
    def extract(self, raw_data: Any, market_type: MarketType) -> Dict[str, Any]:
        strategy = self.get_strategy(market_type)
        return strategy.extract(raw_data)


# ==========================================
# 4. Consensus 提取器
# ==========================================
class ConsensusExtractor:
    """
    Consensus 分析师共识提取器
    
    使用 GenericConsensusStrategy 处理所有市场
    """
    
    def __init__(self):
        self._strategy = GenericConsensusStrategy()
    
    def extract(self, raw_data: Any) -> Dict[str, Any]:
        return self._strategy.extract(raw_data)


# ==========================================
# 5. Dividend 提取器
# ==========================================
class DividendExtractor:
    """
    Dividend 股息提取器
    
    策略路由：
    - MarketType.US → USDividendStrategy
    - MarketType.HK → HKDividendStrategy
    - MarketType.CN → CNDividendStrategy
    - 其他 → DefaultPassthroughStrategy
    """
    
    def __init__(self):
        self._strategies = {
            MarketType.US: USDividendStrategy(),
            MarketType.HK: HKDividendStrategy(),
            MarketType.CN: CNDividendStrategy(),
        }
    
    def get_strategy(self, market_type: MarketType) -> BaseExtractorStrategy:
        return self._strategies.get(market_type, DefaultPassthroughStrategy())
    
    def extract(self, raw_data: Any, market_type: MarketType) -> Dict[str, Any]:
        strategy = self.get_strategy(market_type)
        return strategy.extract(raw_data)


# ==========================================
# 6. 核心调度器 (FundamentalDistillationAnalyzer)
# ==========================================
class FundamentalDistillationAnalyzer:
    """
    基本面蒸馏调度器
    
    职责：
    1. 统筹各个 Extractor
    2. 组装最终的 technical_summary 数据
    3. 遵循 FeatureAnalyzer 协议
    
    注意：HealthTagger 暂不挂载，待后续斟酌
    """
    
    def __init__(self):
        # 初始化各个提取器
        self._profile_extractor = ProfileExtractor()
        self._insider_extractor = InsiderExtractor()
        self._consensus_extractor = ConsensusExtractor()
        self._dividend_extractor = DividendExtractor()
    
    @property
    def target_slot(self) -> str:
        """
        自描述：此 Analyzer 输出到 fundamental_distillation 槽位
        
        实际上会将结果分散写入多个子槽位：
        - fundamental_profile
        - insider_sentiment
        - analyst_consensus
        - dividend_growth
        """
        return "fundamental_distillation"
    
    def analyze(self, pack: ResearchPack) -> Dict[str, Any]:
        """
        执行基本面蒸馏
        
        Args:
            pack: ResearchPack 实例
        
        Returns:
            蒸馏后的数据字典
        """
        # 1. 防御性检查
        if not pack.fundamentals:
            return {}
        
        # 2. 获取市场类型
        facade = ResearchPackFacade(pack)
        market_type = facade.market_type
        
        # 3. 静态档案与股权结构提取 - 上下文融合
        profile_raw = pack.fundamentals.get("profile", {}) or {}
        share_stats_raw = pack.fundamentals.get("share_stats", {}) or {}
        estimates_raw = pack.fundamentals.get("estimates", {}) or {}
        
        # 提取当前价格（用于注入，但不计算市值）
        current_price = estimates_raw.get("current_price") or profile_raw.get("price")
        
        # 构造全量上下文：合并 profile + share_stats + estimates
        merged_profile_source = {
            **share_stats_raw,                    # 持股数据垫底
            **profile_raw,                         # 简介数据核心
            "current_price_for_calc": current_price,  # 注入价格
        }
        profile_data = self._profile_extractor.extract(merged_profile_source, market_type)
        
        # 4. Insider 交易提取
        insider_raw = pack.fundamentals.get("insider_trading_history")
        insider_data = self._insider_extractor.extract(insider_raw, market_type)
        
        # 5. 分析师共识提取
        estimates_raw = pack.fundamentals.get("estimates")
        consensus_data = self._consensus_extractor.extract(estimates_raw)
        
        # 6. 如果 share_stats 存在，也尝试提取做空数据
        share_stats_raw = pack.fundamentals.get("share_stats")
        if share_stats_raw:
            share_consensus = self._consensus_extractor.extract(share_stats_raw)
            # 合并做空数据
            if share_consensus:
                consensus_data.update(share_consensus)
        
        # 6.5 提取股息数据
        dividend_raw = pack.fundamentals.get("dividends_history")
        dividend_data = self._dividend_extractor.extract(dividend_raw, market_type)
        
        # ✅ 从 profile 里把 current_yield 偷过来，合并给大模型看
        raw_yield = profile_raw.get("dividend_yield")
        if raw_yield is not None:
            try:
                # 兼容 0.91 或 0.0091 的情况
                dividend_data[DividendKey.CURRENT_YIELD] = float(raw_yield)
            except (ValueError, TypeError):
                pass
        
        # 7. 组装最终输出
        result = {
            "fundamental_profile": profile_data,
            "insider_sentiment": insider_data,
            "analyst_consensus": consensus_data,
            "dividend_growth": dividend_data,
        }
        
        # 8. 修复数据隔离：构建全景指标字典用于打标
        # HealthTagger 暂不挂载，待后续斟酌启用
        # global_metrics: Dict[str, Any] = {}
        # if pack.technical_summary and "indicators" in pack.technical_summary:
        #     global_metrics.update(pack.technical_summary["indicators"])
        # global_metrics.update(profile_data)    # 注入 Profile 数据
        # global_metrics.update(consensus_data)
        # global_metrics.update(dividend_data)   # 注入 股息 数据
        # current_price = profile_data.get(ProfileKey.CURRENT_PRICE)
        # target_price = consensus_data.get(ConsensusKey.TARGET_PRICE)
        # if current_price and target_price and target_price > 0:
        #     discount = (target_price - current_price) / target_price
        #     global_metrics["discount_to_target"] = discount
        # result["fundamental_tags"] = generate_health_tags(global_metrics)
        result["fundamental_tags"] = []
        
        return result


# ==========================================
# 7. 便捷工厂函数
# ==========================================
def create_distillation_analyzer() -> FundamentalDistillationAnalyzer:
    """
    创建基本面蒸馏分析器实例
    
    Returns:
        FundamentalDistillationAnalyzer 实例
    """
    return FundamentalDistillationAnalyzer()

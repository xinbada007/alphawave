"""
基本面蒸馏模块 (Fundamentals Distillation)
=========================================
挂载于 TechnicalProcessor 的基本面数据清洗与蒸馏组件。

模块职责：
1. Profile 静态档案提取 (US, HK, CN)
2. Insider 高管交易降噪 (US, HK, CN)
3. Consensus 分析师共识提取
4. Health Tag 生成

使用方式：
    from alphaflow.components.processors.fundamentals import FundamentalDistillationAnalyzer
    
    analyzer = FundamentalDistillationAnalyzer()
    result = analyzer.analyze(pack)
"""

# 导出核心类
from alphaflow.components.processors.fundamentals.analyzer import (
    FundamentalDistillationAnalyzer,
    create_distillation_analyzer,
    FeatureAnalyzer,
)

# 导出策略
from alphaflow.components.processors.fundamentals.profile_strategies import (
    USProfileStrategy,
    HKProfileStrategy,
    CNProfileStrategy,
)

from alphaflow.components.processors.fundamentals.insider_strategies import (
    USInsiderStrategy,
    HKInsiderStrategy,
    CNInsiderStrategy,
)

from alphaflow.components.processors.fundamentals.consensus_strategies import (
    GenericConsensusStrategy,
    get_consensus_strategy,
)

from alphaflow.components.processors.fundamentals.dividend_strategies import (
    USDividendStrategy,
    HKDividendStrategy,
    CNDividendStrategy,
    get_dividend_strategy,
)

# 导出工具
from alphaflow.components.processors.fundamentals.base_strategy import (
    BaseExtractorStrategy,
    DefaultPassthroughStrategy,
    StrategyFactory,
    standardize_field,
    standardize_fields,
)

# 导出配置 (动态融合后的映射)
from alphaflow.components.processors.fundamentals.fundamental_keys import (
    ProfileKey,
    InsiderKey,
    ConsensusKey,
    DividendKey,
    HealthTagConfig,
    PROFILE_EXTRACTOR_CHAINS,
    CONSENSUS_EXTRACTOR_CHAINS,
    INSIDER_NOISE_KEYWORDS,
)

# Health Tagger
from alphaflow.components.processors.fundamentals.health_tagger import (
    HealthTagger,
    generate_health_tags,
    generate_health_tags_with_desc,
)

__all__ = [
    # 核心调度器
    "FundamentalDistillationAnalyzer",
    "create_distillation_analyzer",
    "FeatureAnalyzer",
    
    # Profile 策略
    "USProfileStrategy",
    "HKProfileStrategy", 
    "CNProfileStrategy",
    
    # Insider 策略
    "USInsiderStrategy",
    "HKInsiderStrategy",
    "CNInsiderStrategy",
    
    # Consensus 策略
    "GenericConsensusStrategy",
    "get_consensus_strategy",
    
    # 基础工具
    "BaseExtractorStrategy",
    "DefaultPassthroughStrategy",
    "StrategyFactory",
    "standardize_field",
    "standardize_fields",
    
    # 配置 (动态融合)
    "ProfileKey",
    "InsiderKey",
    "ConsensusKey",
    "DividendKey",
    "HealthTagConfig",
    "PROFILE_EXTRACTOR_CHAINS",
    "CONSENSUS_EXTRACTOR_CHAINS",
    "INSIDER_NOISE_KEYWORDS",
    
    # Health Tagger
    "HealthTagger",
    "generate_health_tags",
    "generate_health_tags_with_desc",
]

"""
Consensus 分析师共识提取策略 (Consensus Strategies)
===================================================
处理不同市场的分析师共识数据：
- GenericConsensusStrategy: 通用策略（目标价，做空比例等）

设计原则：
1. 统一输出格式：标准化的标量数据
2. 字段标准化：通过映射字典自动适配多 Provider
3. 纯 Python 实现：0 Pandas 依赖
4. 消耗登记机制：防止脏键复活（已映射的原始键不再出现在输出中）
"""

from typing import Any, Dict, Set

from alphaflow.components.processors.fundamentals.base_strategy import (
    BaseExtractorStrategy,
    standardize_field,
)
from alphaflow.components.processors.fundamentals.fundamental_keys import (
    ConsensusKey,
    ShareStatsKey,
    SHARE_STATS_EXTRACTOR_CHAINS,
    CONSENSUS_EXTRACTOR_CHAINS as CONSENSUS_FIELD_CHAINS,
)


# ==========================================
# 1. 通用分析师共识策略
# ==========================================
class GenericConsensusStrategy(BaseExtractorStrategy):
    """
    通用分析师共识处理策略
    
    适用市场：US, HK, CN
    数据来源：
    - OpenBB: obb.equity.estimates.consensus
    - OpenBB: obb.equity.ownership.share_statistics
    
    处理内容：
    1. 目标价与评级
    2. 目标价高/低/分歧度 (target_spread)
    3. 做空数据
    4. 分析师覆盖数量
    """
    
    def extract(self, raw_data: Any) -> Dict[str, Any]:
        if not raw_data:
            return {}
        
        # 处理 estimates 数据 (Dict 格式)
        if isinstance(raw_data, dict):
            return self._extract_from_dict(raw_data)
        
        # 处理 share_stats 数据 (可能是 List 或 Dict)
        if isinstance(raw_data, list) and raw_data:
            first_item = raw_data[0]
            if isinstance(first_item, dict):
                return self._extract_from_dict(first_item)
        
        return {}
    
    def _extract_from_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从字典中提取分析师共识数据
        
        使用 consumed_keys 机制防止脏键复活：
        一旦某个原始键被映射到标准键，它就不会再出现在输出中
        """
        result = {}
        consumed_keys: Set[str] = set()  # 🚀 已消耗的脏键登记册
        
        # 1. 提取目标价 (中位数)
        target_price = standardize_field(
            data, ConsensusKey.TARGET_PRICE, CONSENSUS_FIELD_CHAINS
        )
        if target_price is not None:
            try:
                result[ConsensusKey.TARGET_PRICE] = float(target_price)
                # 🚀 登记已消耗的键
                for alias in CONSENSUS_FIELD_CHAINS.get(ConsensusKey.TARGET_PRICE, []):
                    if alias in data:
                        consumed_keys.add(alias)
            except (ValueError, TypeError):
                pass
        
        # 2. 提取目标高价 (target_high)
        target_high = standardize_field(
            data, ConsensusKey.TARGET_HIGH, CONSENSUS_FIELD_CHAINS
        )
        if target_high is not None:
            try:
                result[ConsensusKey.TARGET_HIGH] = float(target_high)
                for alias in CONSENSUS_FIELD_CHAINS.get(ConsensusKey.TARGET_HIGH, []):
                    if alias in data:
                        consumed_keys.add(alias)
            except (ValueError, TypeError):
                pass
        
        # 3. 提取目标低价 (target_low)
        target_low = standardize_field(
            data, ConsensusKey.TARGET_LOW, CONSENSUS_FIELD_CHAINS
        )
        if target_low is not None:
            try:
                result[ConsensusKey.TARGET_LOW] = float(target_low)
                for alias in CONSENSUS_FIELD_CHAINS.get(ConsensusKey.TARGET_LOW, []):
                    if alias in data:
                        consumed_keys.add(alias)
            except (ValueError, TypeError):
                pass
        
        # 4. 计算目标价分歧度 (target_spread)
        # spread = (high - low) / median
        high = result.get(ConsensusKey.TARGET_HIGH)
        low = result.get(ConsensusKey.TARGET_LOW)
        median = result.get(ConsensusKey.TARGET_PRICE)
        
        if (high is not None) and (low is not None) and (median is not None) and (median > 0):
            spread = (high - low) / median
            result[ConsensusKey.TARGET_SPREAD] = round(spread, 4)
        
        # 5. 提取当前价格
        curr_price = standardize_field(
            data, ConsensusKey.CURRENT_PRICE, CONSENSUS_FIELD_CHAINS
        )
        if curr_price is not None:
            try:
                curr_price_val = float(curr_price)
                result[ConsensusKey.CURRENT_PRICE] = curr_price_val
                for alias in CONSENSUS_FIELD_CHAINS.get(ConsensusKey.CURRENT_PRICE, []):
                    if alias in data:
                        consumed_keys.add(alias)
                
                # 6. 计算潜在涨幅 (Upside Potential)
                t_price = result.get(ConsensusKey.TARGET_PRICE)
                if t_price and curr_price_val > 0:
                    upside = (t_price - curr_price_val) / curr_price_val
                    result[ConsensusKey.UPSIDE_POTENTIAL] = round(upside, 4)
            except (ValueError, TypeError):
                pass
        
        # 7. 提取量化评级均值
        rec_mean = standardize_field(
            data, ConsensusKey.RECOMMENDATION_MEAN, CONSENSUS_FIELD_CHAINS
        )
        if rec_mean is not None:
            try:
                result[ConsensusKey.RECOMMENDATION_MEAN] = float(rec_mean)
                for alias in CONSENSUS_FIELD_CHAINS.get(ConsensusKey.RECOMMENDATION_MEAN, []):
                    if alias in data:
                        consumed_keys.add(alias)
            except (ValueError, TypeError):
                pass
        
        # 8. 提取目标币种
        target_currency = standardize_field(
            data, ConsensusKey.TARGET_CURRENCY, CONSENSUS_FIELD_CHAINS
        )
        if target_currency:
            result[ConsensusKey.TARGET_CURRENCY] = str(target_currency)
            for alias in CONSENSUS_FIELD_CHAINS.get(ConsensusKey.TARGET_CURRENCY, []):
                if alias in data:
                    consumed_keys.add(alias)
        
        # 9. 提取共识评级
        rating = standardize_field(
            data, ConsensusKey.CONSENSUS_RATING, CONSENSUS_FIELD_CHAINS
        )
        if rating:
            result[ConsensusKey.CONSENSUS_RATING] = str(rating)
            for alias in CONSENSUS_FIELD_CHAINS.get(ConsensusKey.CONSENSUS_RATING, []):
                if alias in data:
                    consumed_keys.add(alias)
        
        # 10. 提取分析师数量
        num_analysts = standardize_field(
            data, ConsensusKey.NUMBER_OF_ANALYSTS, CONSENSUS_FIELD_CHAINS
        )
        if num_analysts is not None:
            try:
                result[ConsensusKey.NUMBER_OF_ANALYSTS] = int(num_analysts)
                for alias in CONSENSUS_FIELD_CHAINS.get(ConsensusKey.NUMBER_OF_ANALYSTS, []):
                    if alias in data:
                        consumed_keys.add(alias)
            except (ValueError, TypeError):
                pass
        
        # 11. 提取做空数据 (已迁移至 ShareStatsKey)
        # 11.1 做空比例 (Short % of Float)
        s_float = standardize_field(
            data, ShareStatsKey.SHORT_FLOAT, SHARE_STATS_EXTRACTOR_CHAINS
        )
        if s_float is not None:
            try:
                val = float(s_float)
                result[ShareStatsKey.SHORT_FLOAT] = round(val, 4)
                for alias in SHARE_STATS_EXTRACTOR_CHAINS.get(ShareStatsKey.SHORT_FLOAT, []):
                    if alias in data:
                        consumed_keys.add(alias)
            except (ValueError, TypeError):
                pass
        
        # 11.2 回补天数 (Short Ratio / Days to Cover)
        s_ratio = standardize_field(
            data, ShareStatsKey.SHORT_RATIO, SHARE_STATS_EXTRACTOR_CHAINS
        )
        if s_ratio is not None:
            try:
                result[ShareStatsKey.SHORT_RATIO] = round(float(s_ratio), 2)
                for alias in SHARE_STATS_EXTRACTOR_CHAINS.get(ShareStatsKey.SHORT_RATIO, []):
                    if alias in data:
                        consumed_keys.add(alias)
            except (ValueError, TypeError):
                pass
        
        # 11.3 做空股数 (Short Interest)
        s_int = standardize_field(
            data, ShareStatsKey.SHORT_INTEREST, SHARE_STATS_EXTRACTOR_CHAINS
        )
        if s_int is not None:
            try:
                result[ShareStatsKey.SHORT_INTEREST] = float(s_int)
                for alias in SHARE_STATS_EXTRACTOR_CHAINS.get(ShareStatsKey.SHORT_INTEREST, []):
                    if alias in data:
                        consumed_keys.add(alias)
            except (ValueError, TypeError):
                pass
        
        # 🚀 关键修复：只保留未被消耗的孤儿字段
        # 这些是不在 KEY_MAPPING 中的边缘字段，如 symbol
        for k, v in data.items():
            if k not in consumed_keys and not isinstance(v, (dict, list)):
                result[k] = v
        
        return result


# ==========================================
# 2. 便捷工厂函数
# ==========================================
def get_consensus_strategy() -> GenericConsensusStrategy:
    """
    获取共识策略实例
    
    Returns:
        GenericConsensusStrategy 实例
    """
    return GenericConsensusStrategy()
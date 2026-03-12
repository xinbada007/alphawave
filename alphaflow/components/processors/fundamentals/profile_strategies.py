"""
Profile 静态档案提取策略 (Profile Strategies)
=============================================
处理不同市场的公司档案数据：
- USProfileStrategy: 美股扁平结构直通
- HKProfileStrategy: 港股嵌套结构拍平
- CNProfileStrategy: A股结构预留

设计原则：
1. 统一输出格式：始终返回标准化的 Dict
2. 长文本截断：防止 LLM Token 爆炸
3. 字段标准化：通过映射字典自动适配多 Provider
"""

from typing import Any, Dict

from alphaflow.components.processors.fundamentals.base_strategy import (
    BaseExtractorStrategy,
    standardize_fields,
)
from alphaflow.components.processors.fundamentals.fundamental_keys import (
    ProfileKey,
    ShareStatsKey,
    PROFILE_EXTRACTOR_CHAINS as PROFILE_FIELD_CHAINS,
)


# ==========================================
# 1. 美股 Profile 策略
# ==========================================
class USProfileStrategy(BaseExtractorStrategy):
    """
    美股 Profile 处理：扁平结构直通
    
    典型数据源：OpenBB (obb.equity.profile)
    特点：字段已经是扁平结构，直接映射即可
    """
    
    def extract(self, raw_data: Any) -> Dict[str, Any]:
        if not raw_data or not isinstance(raw_data, dict):
            return {}
        
        # 1. 字段标准化
        standardized = standardize_fields(raw_data or {}, PROFILE_FIELD_CHAINS)
        
        # 2. 长文本防腐截断 (LLM Token 防护)
        desc = standardized.get(ProfileKey.DESC)
        if isinstance(desc, str) and len(desc) > 1000:
            standardized[ProfileKey.DESC] = desc[:1000] + "..."
        
        # 3. 公司名称额外处理
        name = standardized.get(ProfileKey.NAME)
        if name and len(str(name)) > 100:
            standardized[ProfileKey.NAME] = str(name)[:100]
        
        # ✅ 【补丁】确保 institutions_count 是整数 (已迁移至 ShareStatsKey)
        if standardized.get(ShareStatsKey.INSTITUTIONS_COUNT):
            try:
                standardized[ShareStatsKey.INSTITUTIONS_COUNT] = int(float(standardized[ShareStatsKey.INSTITUTIONS_COUNT]))
            except (ValueError, TypeError):
                pass
        
        return standardized


# ==========================================
# 2. 港股 Profile 策略
# ==========================================
class HKProfileStrategy(BaseExtractorStrategy):
    """
    港股 Profile 处理：拍平深层嵌套
    
    典型数据源：AkShare (stock_hk_security_profile_em, stock_hk_company_profile_em)
    特点：数据嵌套在 security_profile 和 company_profile 下
    """
    
    def extract(self, raw_data: Any) -> Dict[str, Any]:
        if not raw_data or not isinstance(raw_data, dict):
            return {}
        
        # 1. 初始化扁平字典，保留 Root Level 数据（包括 share_stats 注入的数据）
        flat_dict = raw_data.copy()
        
        # 2. 拍平 AkShare 特有的嵌套结构（覆盖更新）
        # 常见的港股数据源结构：security_profile (行情相关), company_profile (描述相关)
        if "security_profile" in raw_data and isinstance(raw_data["security_profile"], dict):
            flat_dict.update(raw_data["security_profile"])
            
        if "company_profile" in raw_data and isinstance(raw_data["company_profile"], dict):
            flat_dict.update(raw_data["company_profile"])
            
        # 3. 标准化核心字段（利用映射表提取中文 Key）
        standardized = standardize_fields(flat_dict, PROFILE_FIELD_CHAINS)
        
        # 4. 不计算市值 - 有就有，没有就没有（按指示）
        
        # 5. 文本防腐（放宽到 1000 字符）
        desc = standardized.get(ProfileKey.DESC)
        if isinstance(desc, str) and len(desc) > 1000:
            standardized[ProfileKey.DESC] = desc[:1000] + "..."
        
        # ✅ 【补丁】确保 institutions_count 是整数 (已迁移至 ShareStatsKey)
        if standardized.get(ShareStatsKey.INSTITUTIONS_COUNT):
            try:
                standardized[ShareStatsKey.INSTITUTIONS_COUNT] = int(float(standardized[ShareStatsKey.INSTITUTIONS_COUNT]))
            except (ValueError, TypeError):
                pass
            
        return standardized


# ==========================================
# 3. A股 Profile 策略 (预留)
# ==========================================
class CNProfileStrategy(BaseExtractorStrategy):
    """
    A股 Profile 处理：预留未来扩展
    
    当前阶段：使用 Passthrough 兜底
    典型数据源：AkShare (stock_a_company_info_em)
    """
    
    def extract(self, raw_data: Any) -> Dict[str, Any]:
        if not raw_data or not isinstance(raw_data, dict):
            return {}
        
        # TODO: 实现 A股特有的字段映射
        # 当前先返回标准化结果
        standardized = standardize_fields(raw_data, PROFILE_FIELD_CHAINS)
        
        # 长文本截断
        desc = standardized.get(ProfileKey.DESC)
        if isinstance(desc, str) and len(desc) > 1000:
            standardized[ProfileKey.DESC] = desc[:1000] + "..."
        
        # ✅ 【补丁】确保 institutions_count 是整数 (已迁移至 ShareStatsKey)
        if standardized.get(ShareStatsKey.INSTITUTIONS_COUNT):
            try:
                standardized[ShareStatsKey.INSTITUTIONS_COUNT] = int(float(standardized[ShareStatsKey.INSTITUTIONS_COUNT]))
            except (ValueError, TypeError):
                pass
        
        return standardized

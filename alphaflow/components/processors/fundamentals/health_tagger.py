"""
Health Tagger 财务健康打标机 (Health Tag Generator)
=================================================
基于 CoreFinancialRatioAnalyzer 计算的财务指标，生成 LLM 专用的定性标签。

设计原则：
1. 命名即文档：Tag 名称自带金融语义
2. 规则驱动：通过配置化规则生成 Tag
3. 纯 Python 实现：0 Pandas 依赖
4. 不挂载：此模块暂不挂载到 TechnicalProcessor，待后续斟酌

Tag 命名规范：
- [TAG_NAME] 格式
- 使用金融专业术语
- 描述公司财务特征

当前 Tag 列表：
- [WIDE_MOAT_HIGH_ROE] - 宽护城河，高股东回报 (ROE > 20%)
- [EXCEPTIONAL_GROSS_MARGIN] - 极强的定价权 (毛利率 > 40%)
- [HYPER_PROFIT_EXPANSION] - 盈利高速扩张 (净利润增长 > 30%)
- [AGGRESSIVE_CAPEX_CYCLE] - 激进扩张周期 (CAPEX/营收 > 25%)
- [STRONG_FREE_CASH_FLOW] - 强劲自由现金流 (FCF Margin > 15%)
- [HIGH_YIELD_DIVIDEND] - 高股息价值股 (股息率 > 5%)
- [LEVERAGE_RISK] - 杠杆风险累积 (负债/权益 > 2.0)
- [NEGATIVE_EQUITY] - 资不抵债 (股东权益 < 0)
"""

from typing import Any, Dict, List, Optional

# 本地定义 HealthTagConfig（原 fundamental_keys.py 已删除）
class HealthTagConfig:
    """健康/风险标签配置"""
    # 健康标签
    HEALTHY = "healthy"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"
    
    # 标签规则 (V4: 使用域内短名，阈值适配小数格式)
    RULES = {
        "[WIDE_MOAT_HIGH_ROE]": {
            "indicator": "ROE",              # 从 "ROE_TTM" 改为域内短名
            "threshold": 0.20,               # ⚠️ 修正：ROE 现在是小数(0.1662)不是百分比(16.62)
            "compare": "gt",
            "description": "宽护城河，高股东回报"
        },
        "[EXCEPTIONAL_GROSS_MARGIN]": {
            "indicator": "gross_margin",      # 从 "Gross_Margin_TTM" 改为域内短名
            "threshold": 0.4,
            "compare": "gt",
            "description": "极强的定价权"
        },
        "[LEVERAGE_RISK]": {
            "indicator": "debt_to_equity",    # 从 "Debt_to_Equity" 改为域内短名
            "threshold": 2.0,
            "compare": "gt",
            "description": "杠杆风险累积"
        },
    }


# ==========================================
# 1. 财务健康打标机类
# ==========================================
class HealthTagger:
    """
    财务健康标签生成器
    
    输入：fundamental_metrics (来自 MetricEngine 产出的 distilled_features.fundamental_metrics)
    输出：List[str] - 标签列表，如 ["[WIDE_MOAT_HIGH_ROE]", "[STRONG_FREE_CASH_FLOW]"]
    
    使用方式：
        tagger = HealthTagger()
        metrics = pack.distilled_features.fundamental_metrics
        tags = tagger.generate_tags(metrics)
    """
    
    def __init__(self, config: Optional[HealthTagConfig] = None):
        """
        初始化打标机
        
        Args:
            config: 标签配置，默认使用 HealthTagConfig
        """
        self.config = config or HealthTagConfig
    
    def generate_tags(self, indicators: Dict[str, Any]) -> List[str]:
        """
        基于财务指标生成标签 (V4: 适配语义域嵌套结构)
        
        Args:
            indicators: 财务指标字典，来自 MetricEngine 产出的嵌套结构
        
        Returns:
            标签列表
        """
        if not indicators:
            return []
        
        # 🚀 适配语义域：将嵌套结构展平为一维字典用于规则匹配
        flat: Dict[str, Any] = {}
        for domain_key, domain_val in indicators.items():
            if isinstance(domain_val, dict):
                for metric_key, metric_val in domain_val.items():
                    if not metric_key.startswith("_"):  # 跳过 _ctx 等元节点
                        flat[metric_key] = metric_val
            else:
                # 兼容性：万一传入的已经是平铺 dict
                flat[domain_key] = domain_val
        
        tags = []
        
        # 遍历所有规则
        for tag_name, rule in self.config.RULES.items():
            indicator_name = rule.get("indicator")
            threshold = rule.get("threshold")
            compare = rule.get("compare")
            
            # 获取指标值 (从展平后的字典)
            value = flat.get(indicator_name)
            
            # 特殊处理 equity_status (字符串类型)
            if indicator_name == "equity_status":
                if value == threshold:
                    tags.append(tag_name)
                continue
            
            # 跳过无效值
            if value is None:
                continue
            
            # 数值比较
            try:
                if compare == "gt" and float(value) > threshold:
                    tags.append(tag_name)
                elif compare == "lt" and float(value) < threshold:
                    tags.append(tag_name)
                elif compare == "eq" and float(value) == threshold:
                    tags.append(tag_name)
                elif compare == "gte" and float(value) >= threshold:
                    tags.append(tag_name)
                elif compare == "lte" and float(value) <= threshold:
                    tags.append(tag_name)
            except (ValueError, TypeError):
                # 跳过无法比较的值
                continue
        
        return tags
    
    def generate_tags_with_descriptions(
        self, indicators: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        生成带描述的标签列表 (V4: 适配语义域嵌套结构)
        
        Args:
            indicators: 财务指标字典
        
        Returns:
            [{"tag": "[TAG_NAME]", "description": "描述"}, ...]
        """
        if not indicators:
            return []
        
        # 🚀 适配语义域：将嵌套结构展平为一维字典用于规则匹配
        flat: Dict[str, Any] = {}
        for domain_key, domain_val in indicators.items():
            if isinstance(domain_val, dict):
                for metric_key, metric_val in domain_val.items():
                    if not metric_key.startswith("_"):  # 跳过 _ctx 等元节点
                        flat[metric_key] = metric_val
            else:
                # 兼容性：万一传入的已经是平铺 dict
                flat[domain_key] = domain_val
        
        result = []
        
        for tag_name, rule in self.config.RULES.items():
            indicator_name = rule.get("indicator")
            threshold = rule.get("threshold")
            compare = rule.get("compare")
            description = rule.get("description", "")
            
            # 获取指标值 (从展平后的字典)
            value = flat.get(indicator_name)
            
            # 特殊处理 equity_status
            if indicator_name == "equity_status":
                if value == threshold:
                    result.append({
                        "tag": tag_name,
                        "description": description,
                        "value": value
                    })
                continue
            
            if value is None:
                continue
            
            try:
                matched = False
                if compare == "gt" and float(value) > threshold:
                    matched = True
                elif compare == "lt" and float(value) < threshold:
                    matched = True
                elif compare == "eq" and float(value) == threshold:
                    matched = True
                elif compare == "gte" and float(value) >= threshold:
                    matched = True
                elif compare == "lte" and float(value) <= threshold:
                    matched = True
                
                if matched:
                    result.append({
                        "tag": tag_name,
                        "description": description,
                        "value": value
                    })
            except (ValueError, TypeError):
                continue
        
        return result


# ==========================================
# 2. 便捷函数
# ==========================================
def generate_health_tags(indicators: Dict[str, Any]) -> List[str]:
    """
    快速生成健康标签
    
    Args:
        indicators: 财务指标字典
    
    Returns:
        标签列表
    """
    tagger = HealthTagger()
    return tagger.generate_tags(indicators)


def generate_health_tags_with_desc(
    indicators: Dict[str, Any]
) -> List[Dict[str, str]]:
    """
    快速生成带描述的健康标签
    
    Args:
        indicators: 财务指标字典
    
    Returns:
        带描述的标签列表
    """
    tagger = HealthTagger()
    return tagger.generate_tags_with_descriptions(indicators)

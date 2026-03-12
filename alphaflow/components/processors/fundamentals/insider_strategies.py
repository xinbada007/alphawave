"""
Insider 高管交易提取策略 (Insider Strategies)
=============================================
处理不同市场的高管交易数据，进行噪音过滤：
- USInsiderStrategy: SEC Form 4 降噪（过滤税务/激励行权）
- HKInsiderStrategy: 联交所权益披露处理
- CNInsiderStrategy: 大股东增减持公告预留

设计原则：
1. 纯 Python 实现：0 Pandas 依赖，极速、类型安全
2. 核心降噪：过滤税务/激励行权，只保留公开市场买卖
3. 语义化输出：NET_BUYING / NET_SELLING / NEUTRAL
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Set

from alphaflow.components.processors.fundamentals.base_strategy import (
    BaseExtractorStrategy,
)
from alphaflow.components.processors.fundamentals.fundamental_keys import (
    InsiderKey,
)


# ==========================================
# 1. 美股 Insider 策略
# ==========================================
class USInsiderStrategy(BaseExtractorStrategy):
    """
    美股高管交易策略 (SEC Form 4 核心代码反向还原版 + 180天时效控制)
    
    设计原理：
    1. 时效性：仅保留最近 180 天的交易 (信息不对称衰减理论)。
    2. 有效性：通过'资金对价'、'主动意愿'、'非行政性'三个维度锁定真实买卖。
    
    逻辑公式：
    Valid Trade = (Recent 180 Days) AND (Price > 0) AND (Is_Market_Action) AND NOT (Is_Administrative)
    """

    # ✅ 1. 主动意愿词 (Positive Signal)
    MARKET_KEYWORDS = {"open market", "private purchase", "private sale"}

    # ❌ 2. 行政/被动词 (Negative Signal)
    ADMIN_KEYWORDS = {
        "exercise", "convert", "conversion", "derivative", # 行权/转换
        "tax", "withhold",        # 税务
        "grant", "award",         # 授予
        "gift", "donate", "donation",        # 赠与
        "transfer", "contribution", "distribution" # 内部转移
    }
    


    
    def extract(self, raw_data: Any) -> Dict[str, Any]:
        if not raw_data or not isinstance(raw_data, list):
            return {InsiderKey.STATUS: "NO_DATA"}
            
        # --- 步骤 0: 确立时间窗口 (180天) ---
        cutoff_date = datetime.now() - timedelta(days=180)
            
        net_shares = 0.0
        net_value = 0.0
        
        # 双计数器：用于计算准确的加权均价
        total_bought_shares = 0.0
        total_bought_value = 0.0
        total_sold_shares = 0.0
        total_sold_value = 0.0
        
        actors: Set[str] = set()
        material_sellers: List[str] = []
        
        for row in raw_data:
            # --- 步骤 1: 时间过滤 ---
            # 安全提取日期，支持多种常见格式
            date_str = row.get("transaction_date") or row.get("filing_date")
            if not date_str:
                continue
                
            try:
                # 尝试标准格式 YYYY-MM-DD
                dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
            except ValueError:
                try:
                    # 尝试备用格式 YYYY/MM/DD
                    dt = datetime.strptime(str(date_str)[:10], "%Y/%m/%d")
                except ValueError:
                    continue # 日期无法解析，跳过
            
            if dt < cutoff_date:
                continue # 超过 180 天的数据，视为失效噪音，跳过

            # --- 步骤 2: 数据类型安全转换 ---
            try:
                shares = float(row.get("securities_transacted", 0) or 0)
                price = float(row.get("transaction_price", 0) or 0)
                # SEC Form 4 的 securities_owned 是交易【后】的剩余持股数
                owned_after = float(row.get("securities_owned", 0) or 0)
            except (ValueError, TypeError):
                continue

            # --- 步骤 3: 维度一 [资金对价] ---
            # 🚀 已在 Collector 层通过 filter_fn 过滤，此处无需重复检查 price <= 0
            # 下游 Processor 可无条件信任传入数据，专注于业务分析

            # --- 步骤 4: 维度二 & 三 [语义还原 SEC 代码] ---
            t_type = str(row.get("transaction_type", "")).lower()
            
            # A. 必须包含市场行为描述
            is_market_action = any(k in t_type for k in self.MARKET_KEYWORDS)
            if not is_market_action:
                continue
                
            # B. 绝对不能包含行政/被动描述
            is_administrative = any(k in t_type for k in self.ADMIN_KEYWORDS)
            if is_administrative:
                continue
            
            # --- 至此，锁定有效交易 ---
            
            action = row.get("acquisition_or_disposition")
            owner = row.get("owner_name", "Unknown")
            
            # 清洗过长的实体名
            if isinstance(owner, str) and len(owner) > 30:
                owner = owner.split(";")[0] # 取分号前第一个名字
                if len(owner) > 30:
                    owner = owner[:27] + "..."

            value = shares * price
            
            if action == "Acquisition":
                net_shares += shares
                net_value += value
                total_bought_shares += shares
                total_bought_value += value
                actors.add(f"{owner} (Buy)")
                
            elif action == "Disposition":
                net_shares -= shares
                net_value -= value
                total_sold_shares += shares
                total_sold_value += value
                actors.add(f"{owner} (Sell)")
                
                # --- 步骤 5: 实质性减持监测 (20% 阈值) ---
                prior_shares = owned_after + shares
                if prior_shares > 0:
                    reduction_ratio = shares / prior_shares
                    # 双重门槛：比例 > 20% 且 金额 > 50万美元
                    if reduction_ratio > 0.20 and value > 500000:
                        material_sellers.append(
                            f"{owner} (reduced {reduction_ratio:.1%}, est. ${value/1000000:.1f}M)"
                        )

        # --- 步骤 6: 生成 Summary ---
        avg_price = 0.0
        if net_shares > 0 and total_bought_shares > 0:
            avg_price = total_bought_value / total_bought_shares
        elif net_shares < 0 and total_sold_shares > 0:
            avg_price = total_sold_value / total_sold_shares

        if net_shares > 0:
            status = "NET_BUYING"
            summary = f"Insiders net bought {abs(net_shares):,.0f} shares (Est. Value ${abs(net_value):,.0f}, Avg Price ${avg_price:,.2f})."
        elif net_shares < 0:
            status = "NET_SELLING"
            summary = f"Insiders net sold {abs(net_shares):,.0f} shares (Est. Value ${abs(net_value):,.0f}, Avg Price ${avg_price:,.2f})."
            if material_sellers:
                # 去重并取前5
                unique_sellers = list(set(material_sellers))[:5]
                summary += f" Notable[MATERIAL_STAKE_REDUCTION]: {'; '.join(unique_sellers)}."
        else:
            status = "NEUTRAL"
            summary = "No significant open-market insider activity detected in the past 180 days."
        
        return {
            InsiderKey.STATUS: status,
            InsiderKey.NET_SHARES: round(net_shares, 2),
            InsiderKey.NET_VALUE: round(net_value, 2),
            InsiderKey.AVG_PRICE: round(avg_price, 2),
            InsiderKey.ACTIVE_INSIDERS: sorted(list(actors))[:10],
            InsiderKey.SUMMARY: summary
        }


# ==========================================
# 2. 港股 Insider 策略
# ==========================================
class HKInsiderStrategy(BaseExtractorStrategy):
    """
    港股高管交易降噪：处理联交所权益披露
    
    数据来源：OpenBB (obb.equity.ownership.insider_trading)
    特点：
    - 港股披露规则与美股不同
    - 主要关注 "好仓" (Long Position) 变动
    
    当前阶段：返回 NEUTRAL，待完善规则
    """
    
    def extract(self, raw_data: Any) -> Dict[str, Any]:
        if not raw_data or not isinstance(raw_data, list):
            return {InsiderKey.STATUS: "NO_DATA"}
        
        # 港股数据结构与美股不同，暂时返回基础结果
        # TODO: 实现港股特有的内部交易处理逻辑
        
        # 简单统计：只看近180天
        cutoff_date = datetime.now() - timedelta(days=180)
        
        valid_trades = []
        for row in raw_data:
            date_str = row.get("filing_date") or row.get("transaction_date")
            if not date_str:
                continue
            
            try:
                dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
                if dt >= cutoff_date:
                    valid_trades.append(row)
            except ValueError:
                continue
        
        if not valid_trades:
            return {
                InsiderKey.STATUS: "NEUTRAL",
                InsiderKey.SUMMARY: "No recent insider trading data available."
            }
        
        # 暂时返回 NEUTRAL，等港股规则完善后再处理
        return {
            InsiderKey.STATUS: "NEUTRAL",
            InsiderKey.SUMMARY: f"HK Insider Strategy: {len(valid_trades)} recent filings detected (rules pending refinement)."
        }


# ==========================================
# 3. A股 Insider 策略 (预留)
# ==========================================
class CNInsiderStrategy(BaseExtractorStrategy):
    """
    A股高管交易处理：大股东增减持公告
    
    数据来源：AkShare
    特点：
    - A股以公告形式披露，而非实时交易
    - 需要关注 "减持" 公告的节奏
    
    当前阶段：使用兜底策略
    """
    
    def extract(self, raw_data: Any) -> Dict[str, Any]:
        if not raw_data or not isinstance(raw_data, list):
            return {InsiderKey.STATUS: "NO_DATA"}
        
        # TODO: 实现 A股特有的增减持处理逻辑
        # 当前返回基础结果
        
        return {
            InsiderKey.STATUS: "NEUTRAL",
            InsiderKey.SUMMARY: "CN Insider Strategy: Not implemented yet."
        }

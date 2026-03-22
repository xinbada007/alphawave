"""
内部人交易分析器 - 纯粹的业务逻辑，无映射
============================================
V3 架构：仅处理降噪逻辑，信任输入，强类型输出

设计哲学：
- 硬编码读取原生 API 字段（无损透传事件流）
- 返回预先定义的 Pydantic Model（InsiderFeature）
- 复杂的降噪逻辑保留（180天过滤、税务行权噪音过滤）
"""

from datetime import datetime, timedelta
from typing import List, Set
from alphaflow.core.schema.models import ResearchPack, InsiderFeature


class InsiderAnalyzer:
    """仅处理降噪逻辑，信任输入，强类型输出"""
    
    # 市场行为关键词（保留）
    MARKET_KEYWORDS = {"open market", "private purchase", "private sale"}
    
    # 行政噪音关键词（过滤）
    ADMIN_KEYWORDS = {"exercise", "convert", "tax", "grant", "gift", "transfer"}

    @classmethod
    def analyze(cls, pack: ResearchPack) -> InsiderFeature:
        """
        分析内部人交易数据，返回强类型特征
        
        Args:
            pack: ResearchPack，包含 insider_trading_history 原始数据
            
        Returns:
            InsiderFeature: 强类型的内部人交易特征
        """
        # 直接读取原始数据（无损透传）
        raw_data = pack.fundamentals.get("insider_trading_history", [])
        if not raw_data:
            # 🚀 D3: 无数据 = "NO_DATA"（非 NEUTRAL）
            # NEUTRAL 表示"有数据但买卖平衡"，NO_DATA 表示"此市场无数据源"
            return InsiderFeature(
                insider_status="NO_DATA",
                insider_summary="No insider trading data available for this market.",
            )

        # 180天截止线
        cutoff_date = datetime.now() - timedelta(days=180)
        
        # 聚合变量
        net_shares = 0.0
        net_value = 0.0
        total_bought_shares = 0.0
        total_bought_value = 0.0
        total_sold_shares = 0.0
        total_sold_value = 0.0
        actors: Set[str] = set()

        for row in raw_data:
            # 直接使用 API 原生字段（无损事件流）
            date_str = row.get("transaction_date") or row.get("filing_date")
            if not date_str:
                continue
            
            try:
                dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
                if dt < cutoff_date:
                    continue
                
                shares = float(row.get("securities_transacted", 0) or 0)
                price = float(row.get("transaction_price", 0) or 0)
            except (ValueError, TypeError):
                continue

            # 噪音过滤：交易类型
            t_type = str(row.get("transaction_type", "")).lower()
            if not any(k in t_type for k in cls.MARKET_KEYWORDS):
                continue
            if any(k in t_type for k in cls.ADMIN_KEYWORDS):
                continue

            # 交易方向
            action = row.get("acquisition_or_disposition")
            owner = str(row.get("owner_name", "Unknown")).split(";")[0][:30]
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

        # 计算平均价格
        avg_price = 0.0
        if net_shares > 0 and total_bought_shares > 0:
            avg_price = total_bought_value / total_bought_shares
        elif net_shares < 0 and total_sold_shares > 0:
            avg_price = total_sold_value / total_sold_shares

        # 组装强类型 DTO
        feature = InsiderFeature(
            net_shares=round(net_shares, 2),
            net_value=round(net_value, 2),
            avg_price=round(avg_price, 2),
            active_insiders=sorted(list(actors))[:10]
        )

        # 状态判断与摘要生成
        if net_shares > 0:
            feature.insider_status = "NET_BUYING"
            feature.insider_summary = (
                f"Insiders net bought {abs(net_shares):,.0f} shares "
                f"(Est. ${abs(net_value):,.0f})."
            )
        elif net_shares < 0:
            feature.insider_status = "NET_SELLING"
            feature.insider_summary = (
                f"Insiders net sold {abs(net_shares):,.0f} shares "
                f"(Est. ${abs(net_value):,.0f})."
            )

        return feature

"""
US Market Strategy - 美股市场策略
美股：OpenBB (yfinance) + 原生 YFinance 兜底
"""
from typing import Dict, List

from .base import BaseMarketStrategy
from ..fetchers.obb_fetcher import OBBFetcher
from ..fetchers.yfinance_fetcher import YFinanceFetcher


class USMarketStrategy(BaseMarketStrategy):
    """美股混合编排策略：OpenBB 为主，原生 YF 兜底"""
    
    def __init__(self):
        # 实例化 Fetcher
        self.obb_yf = OBBFetcher(provider="yfinance")
        self.obb_fmp = OBBFetcher(provider="fmp")
        self.native_yf = YFinanceFetcher()
    
    def build_routing_table(self) -> Dict[str, List]:
        """声明式路由表"""
        return {
            # === 财务三大表 (使用 OBB yfinance) ===
            "a_income": [self.obb_yf],
            "q_income": [self.obb_yf],
            "a_balance": [self.obb_yf],
            "q_balance": [self.obb_yf],
            "a_cash": [self.obb_yf],
            "q_cash": [self.obb_yf],
            
            # === 分析师预期与持股统计 (使用 OBB yfinance) ===
            "estimates": [self.obb_yf],
            "share_stats": [self.obb_yf],
            
            # === 高管与内幕交易 (使用 OBB yfinance) ===
            "management": [self.obb_yf],
            "insider_trading": [self.obb_yf],
            
            # === 分红 (使用 OBB) ===
            "dividends": [self.obb_yf],
            
            # === 高风险接口：兜底责任链 ===
            # 拆股：优先 OBB fmp，失败则原生 yf
            "splits": [self.native_yf],
            
            # 大股东：优先 OBB yf，失败则原生 yf
            "major_holders": [self.native_yf],
            
            # 财报日历：原生 yf 更稳
            "earnings_cal": [self.native_yf],
            
            # === Profile ===
            "profile": [self.obb_yf],
        }

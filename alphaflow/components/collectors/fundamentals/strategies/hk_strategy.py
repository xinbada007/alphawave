"""
HK Market Strategy - 港股市场策略
港股：AkShare 主导 + OpenBB 补全 + 原生 YF 兜底
"""
from typing import Dict, List

from .base import BaseMarketStrategy
from ..fetchers.akshare_hk_fetcher import AkShareHKFetcher
from ..fetchers.obb_fetcher import OBBFetcher
from ..fetchers.yfinance_fetcher import YFinanceFetcher


class HKMarketStrategy(BaseMarketStrategy):
    """港股混合编排策略：AkShare 主导 + OpenBB + 原生 YF"""
    
    def __init__(self):
        # 实例化 Fetcher
        self.ak = AkShareHKFetcher()
        self.obb_yf = OBBFetcher(provider="yfinance")
        self.obb_fmp = OBBFetcher(provider="fmp")
        self.native_yf = YFinanceFetcher()
    
    def build_routing_table(self) -> Dict[str, List]:
        """声明式路由表"""
        return {
            # === 财报类：绝对信任 AkShare ===
            "a_income": [self.ak],
            "q_income": [self.ak],
            "a_balance": [self.ak],
            "q_balance": [self.ak],
            "a_cash": [self.ak],
            "q_cash": [self.ak],
            "a_analysis": [self.ak],
            "q_analysis": [self.ak],
            
            # === 分红：港股专用接口最准 (AkShare) ===
            "dividends": [self.ak],
            
            # === Profile：AkShare 港股资料更全 ===
            "profile": [self.ak],
            
            # === 分析师预期与持股统计：OpenBB ===
            "estimates": [self.obb_yf],
            "share_stats": [self.obb_yf],
            
            # === 高管与内幕交易：OpenBB ===
            "management": [self.obb_yf],
            # "insider_trading": [self.obb_yf],
            
            # === 🚨 高风险接口：部署多级 Fallback 责任链 ===
            # 拆股：优先 OBB fmp，失败则原生 yf
            "splits": [self.native_yf],
            
            # 大股东：优先 OBB yf，失败则原生 yf
            "major_holders": [self.native_yf],
            
            # 财报日历：原生 yf 更稳
            "earnings_cal": [self.native_yf],
        }

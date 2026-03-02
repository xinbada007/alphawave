"""
AkShare CN Fetcher - A股基本面数据抓取器
负责 A 股的财务数据抓取
"""
from typing import List, Dict
import pandas as pd
import akshare as ak

from .base import BaseFetcher


class AkShareCNFetcher(BaseFetcher):
    """A股基本面抓取器 - 使用 AkShare"""
    
    name = "AkShareCN"

    # 字段映射：AkShare 字段 -> 标准字段
    FIELD_MAP = {
        # 财务分析指标
        "股票代码": "symbol",
        "股票简称": "name",
        "日期": "date",
        "净资产收益率": "roe",
        "净资产收益率(摊薄)": "roe_diluted",
        "净资产收益率(加权)": "roe_weighted",
        "总资产收益率": "roa",
        "总资产报酬率": "rota",
        "销售毛利率": "gross_margin",
        "销售净利率": "net_margin",
        "营业利润率": "operating_margin",
        "每股收益": "eps",
        "每股收益(摊薄)": "eps_diluted",
        "每股收益(加权)": "eps_weighted",
        "每股净资产": "bps",
        "每股未分配利润": "bps_distributable",
        "每股资本公积": "capital_reserve",
        "总资产": "total_assets",
        "总负债": "total_liabilities",
        "股东权益": "total_equity",
        "营业收入": "revenue",
        "营业收入同比增长": "revenue_yoy",
        "净利润": "net_profit",
        "净利润同比增长": "net_profit_yoy",
        "营业利润": "operating_profit",
        "利润总额": "total_profit",
    }

    async def fetch(self, task_name: str, symbol: str, **kwargs) -> List[Dict]:
        """
        A股基本面数据抓取
        
        Args:
            task_name: 标准任务名 (financial_indicator, company_info 等)
            symbol: 股票代码 (如 000001, 600519)
            
        Returns:
            数据列表
        """
        # 清洗代码
        code = symbol.split(".")[0] if "." in symbol else symbol
        
        # 根据任务名调用不同的 API
        if task_name in ["financial_indicator", "financial_analysis"]:
            return await self._fetch_financial_indicator(code)
        elif task_name == "company_info":
            return await self._fetch_company_info(code)
        elif task_name == "main_bt":
            return await self._fetch_main_bt(code)
        else:
            # 尝试通用接口
            return await self._fetch_financial_indicator(code)

    async def _fetch_financial_indicator(self, code: str) -> List[Dict]:
        """获取财务分析指标"""
        try:
            df = await self._safe_call(ak.stock_financial_analysis_indicator_em, symbol=code)
            if df is None or df.empty:
                return []
            
            # 重命名字段
            df = df.rename(columns=self.FIELD_MAP)
            
            # 转换日期
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            
            # 只返回最新数据
            if len(df) > 0:
                df = df.head(1)
            
            return df.to_dict("records")
        except Exception as e:
            print(f"  [{self.name}] fetch_financial_indicator failed: {e}")
            return []

    async def _fetch_company_info(self, code: str) -> List[Dict]:
        """获取公司基本信息"""
        try:
            df = await self._safe_call(ak.stock_company_info_em, symbol=code)
            if df is None or df.empty:
                return []
            return df.to_dict("records")
        except Exception as e:
            print(f"  [{self.name}] fetch_company_info failed: {e}")
            return []

    async def _fetch_main_bt(self, code: str) -> List[Dict]:
        """获取主要财务指标"""
        try:
            # 使用财务分析接口作为替代
            df = await self._safe_call(ak.stock_financial_analysis_indicator_em, symbol=code)
            if df is None or df.empty:
                return []
            return df.head(10).to_dict("records")
        except Exception as e:
            print(f"  [{self.name}] fetch_main_bt failed: {e}")
            return []

    async def _safe_call(self, func, **kwargs):
        """安全调用 AkShare 函数"""
        import asyncio
        try:
            return await asyncio.to_thread(func, **kwargs)
        except Exception as e:
            print(f"  [{self.name}] API call failed: {e}")
            return None

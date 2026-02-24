"""
AkShare HK Fetcher - 纯 AkShare 港股抓取器
负责港股的财务数据抓取
"""
import asyncio
from typing import List, Dict, Any
import pandas as pd
import akshare as ak  # type: ignore

from .base import BaseFetcher
from alphaflow.core.data_utils import DIVIDEND_FIELD_CHAINS


class AkShareHKFetcher(BaseFetcher):
    """纯 AkShare 港股抓取器 - 只管港股，无 fallback"""
    
    name = "AkShareHK"
    
    # 类级别信号量：全局最多 2 个并发，防止触发 WAF
    _semaphore = asyncio.Semaphore(2)
    
    async def fetch(self, task_name: str, symbol: str, **kwargs) -> List[Dict]:
        """任务翻译官：将标准化任务名翻译为 AkShare API"""
        limit_a = kwargs.get("limit_a", 2)
        limit_q = kwargs.get("limit_q", 5)
        
        # 解析任务名
        if task_name.endswith("_income"):
            # a_income -> 年度/利润表
            period = "年度" if task_name.startswith("a_") else "报告期"
            limit = limit_a if task_name.startswith("a_") else limit_q
            return await self._fetch_rep(symbol, "利润表", period, limit)
        
        elif task_name.endswith("_balance"):
            period = "年度" if task_name.startswith("a_") else "报告期"
            limit = limit_a if task_name.startswith("a_") else limit_q
            return await self._fetch_rep(symbol, "资产负债表", period, limit)
        
        elif task_name.endswith("_cash"):
            period = "年度" if task_name.startswith("a_") else "报告期"
            limit = limit_a if task_name.startswith("a_") else limit_q
            return await self._fetch_rep(symbol, "现金流量表", period, limit)
        
        elif task_name == "a_analysis":
            return await self._fetch_ana(symbol, "年度", limit_a)
        
        elif task_name == "q_analysis":
            return await self._fetch_ana(symbol, "报告期", limit_q)
        
        elif task_name == "dividends":
            return await self._fetch_hk_dividends(symbol)
        
        elif task_name == "profile":
            return await self._fetch_profile(symbol)
        
        # 不支持的任务，抛出异常
        raise ValueError(f"{self.name} does not support task: {task_name}")
    
    async def _fetch_rep(
        self, symbol: str, tbl: str, p_type: str, lim: int
    ) -> List[Dict]:
        """抓取财务报表"""
        code = symbol.split(".")[0].zfill(5)
        
        async with self._semaphore:
            try:
                df = await asyncio.to_thread(
                    ak.stock_financial_hk_report_em,
                    stock=code,
                    symbol=tbl,
                    indicator=p_type,
                )
                if df.empty:
                    return []
                
                # 提取元数据
                meta_dict = {}
                meta_cols = [c for c in ["DATE_TYPE_CODE", "START_DATE"] if c in df.columns]
                if meta_cols:
                    meta_df = df[["REPORT_DATE"] + meta_cols].drop_duplicates()
                    meta_dict = meta_df.set_index("REPORT_DATE").to_dict("index")
                
                # 透视表
                tdf = (
                    df.pivot_table(
                        index="REPORT_DATE",
                        columns="STD_ITEM_NAME",
                        values="AMOUNT",
                        aggfunc="first",
                    )
                    .sort_index(ascending=False)
                    .head(lim)
                )
                
                # 拼回元数据
                for col_name in meta_cols:
                    if meta_dict:
                        sample_value = next(iter(meta_dict.values()), {})
                        if col_name in sample_value:
                            tdf[col_name] = tdf.index.to_series().map(
                                lambda x: meta_dict.get(x, {}).get(col_name)
                            )
                
                tdf.index = pd.to_datetime(tdf.index).strftime("%Y-%m-%d")
                tdf.index.name = "period_ending"
                return tdf.reset_index().to_dict(orient="records")
                
            except Exception as e:
                raise Exception(f"{self.name} _fetch_rep({tbl}) failed: {e}")
    
    async def _fetch_ana(self, symbol: str, p_type: str, lim: int) -> List[Dict]:
        """抓取分析指标"""
        code = symbol.split(".")[0].zfill(5)
        
        async with self._semaphore:
            try:
                df = await asyncio.to_thread(
                    ak.stock_financial_hk_analysis_indicator_em,
                    symbol=code,
                    indicator=p_type,
                )
                if df.empty:
                    return []
                df = df.sort_values("REPORT_DATE", ascending=False).head(lim)
                df["period_ending"] = pd.to_datetime(df["REPORT_DATE"]).dt.strftime("%Y-%m-%d")
                return df.to_dict(orient="records")
                
            except Exception as e:
                raise Exception(f"{self.name} _fetch_ana({p_type}) failed: {e}")
    
    async def _fetch_hk_dividends(self, symbol: str) -> List[Dict]:
        """抓取港股分红派息"""
        code = symbol.split(".")[0].zfill(5)
        
        async with self._semaphore:
            try:
                df = await asyncio.to_thread(
                    ak.stock_hk_dividend_payout_em,
                    symbol=code
                )
                if df.empty:
                    return []
                
                # 字段映射
                rename_map = {}
                for std_key, aliases in DIVIDEND_FIELD_CHAINS.items():
                    for alias in aliases:
                        if alias in df.columns:
                            rename_map[alias] = std_key.lower()
                            break
                
                df = df.rename(columns=rename_map)
                
                # 日期格式化
                date_cols = ["ex_dividend_date", "announce_date", "payment_date"]
                for col in date_cols:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d").fillna("N/A")
                
                df = df.fillna("N/A")
                
                if "ex_dividend_date" in df.columns:
                    df = df.sort_values("ex_dividend_date", ascending=False)
                
                return df.to_dict(orient="records")
                
            except Exception as e:
                raise Exception(f"{self.name} _fetch_hk_dividends failed: {e}")
    
    async def _fetch_profile(self, symbol: str) -> List[Dict]:
        """抓取公司 profile"""
        code = symbol.split(".")[0].zfill(5)
        
        try:
            p_df, c_df = (
                await asyncio.to_thread(ak.stock_hk_security_profile_em, symbol=code),
                await asyncio.to_thread(ak.stock_hk_company_profile_em, symbol=code),
            )
            
            pr = {str(k).strip(): v for k, v in p_df.iloc[0].to_dict().items()} if not p_df.empty else {}
            cr = {str(k).strip(): v for k, v in c_df.iloc[0].to_dict().items()} if not c_df.empty else {}
            
            profile = [{}]
            if pr:
                profile[0]["security_profile"] = pr
                if pr.get("证券简称"):
                    profile[0]["name"] = pr.get("证券简称")
            if cr:
                profile[0]["company_profile"] = cr
                if not profile[0].get("name") and cr.get("公司名称"):
                    profile[0]["name"] = cr.get("公司名称")
            
            return profile
            
        except Exception as e:
            raise Exception(f"{self.name} _fetch_profile failed: {e}")

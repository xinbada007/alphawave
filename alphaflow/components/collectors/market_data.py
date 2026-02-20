import pandas as pd
import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Callable
import akshare as ak  # type: ignore
from openbb import obb

from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import (
    AnalysisContext,
    ComponentOutput,
    ResearchPack,
    DataFrameModel,
)
from alphaflow.utils.api_rotator import get_api_key
from alphaflow.core.data_utils import (
    MARKET_FIELD_CHAINS, 
    FINANCIAL_FIELD_CHAINS, 
    get_field_value, 
    get_market_type, 
    MarketType
)

# ==========================================
# 1. Fetcher 策略接口与实现
# ==========================================
obb_any: Any = obb


# ==========================================
# 1.1 市场指标抓取器 (新增)
# ==========================================

class MetricsFetcher:
    """
    市场指标抓取器 - 从 metrics 接口获取实时估值指标
    职责单一：只从 metrics 获取，有就有，没有就没有
    """

    # 字段名映射：alias -> 标准字段名
    FIELD_ALIAS_MAP = {
        # Market 字段
        "MCAP": "marketCap",
        "MCAP_HK": "marketCapHk",
        "PE": "trailingPE",
        "PB": "priceToBook",
        "PS": "priceToSales",
        "PCF": "priceToCashFlow",
        "DIVIDEND_YIELD": "dividendYieldTtm",  # 注意：AkShare 返回的是股息率
        "EPS": "trailingEps",
        "BPS": "bookValue",
        "OCPS": "operatingCashFlowPerShare",
        "DPS": "dividendPerShare",
        "SHARES": "sharesOutstanding",
        "SHARES_H": "sharesH",
        "AUTHORIZED_SHARES": "authorizedShares",
        "LOT_SIZE": "lotSize",
        "PAYOUT_RATIO": "payoutRatio",
        # Financial 字段 - 绝对数值
        "REV": "totalRevenue",
        "NI": "netProfit",
        "OI": "operatingIncome",
        "GP": "grossProfit",
        "OCF": "operatingCashFlow",
        "ASSETS": "totalAssets",
        "LIAB": "totalLiabilities",
        "EQUITY": "totalEquity",
        # Financial 字段 - 百分比（需要归一化）
        "ROE": "roe",
        "ROA": "roa",
        "NET_MARGIN": "netMargin",
        "GROSS_MARGIN": "grossMargin",
        # Financial 字段 - 增长率（需要归一化）
        "REV_GROWTH_QOQ": "revGrowthQoq",
        "NI_GROWTH_QOQ": "niGrowthQoq",
        "REV_GROWTH_YOY": "revGrowthYoy",
        "NI_GROWTH_YOY": "niGrowthYoy",
    }

    # 需要归一化的百分比字段（AkShare 返回百分比，需要除以 100）
    PCT_FIELDS = {
        "roe", "roa", "netMargin", "grossMargin", 
        "payoutRatio", "dividendYieldTtm",
        "revGrowthQoq", "niGrowthQoq", "revGrowthYoy", "niGrowthYoy"
    }

    @staticmethod
    def _extract_metrics(data: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """
        从原始数据中提取字段，统一格式
        
        Args:
            data: 原始数据字典
            provider: 数据提供者 ("akshare" 或 "openbb")
        
        Returns:
            标准化后的指标字典
        """
        metrics = {}
        
        # 1. 提取 Market 字段
        for alias_key in MARKET_FIELD_CHAINS.keys():
            val = get_field_value(data, alias_key, MARKET_FIELD_CHAINS)
            if val is not None:
                key = MetricsFetcher.FIELD_ALIAS_MAP.get(alias_key, alias_key.lower())
                # AkShare 需要归一化，OpenBB 直接返回
                if provider == "akshare" and key in MetricsFetcher.PCT_FIELDS:
                    metrics[key] = round(val / 100, 6)
                else:
                    metrics[key] = val
        
        # 2. 提取 Financial 字段
        for alias_key in FINANCIAL_FIELD_CHAINS.keys():
            val = get_field_value(data, alias_key, FINANCIAL_FIELD_CHAINS)
            if val is not None:
                key = MetricsFetcher.FIELD_ALIAS_MAP.get(alias_key, alias_key.lower())
                # AkShare 需要归一化，OpenBB 直接返回
                if provider == "akshare" and key in MetricsFetcher.PCT_FIELDS:
                    metrics[key] = round(val / 100, 6)
                else:
                    metrics[key] = val
        
        # 3. yfinance 特殊处理：部分字段返回百分比形式，需要除以 100
        # 同时修改原始数据 (data)，确保 raw_openbb 也被归一化
        print(f"  [MetricsFetcher] provider: {provider}, keys in metrics: {list(metrics.keys())}")
        if provider == "yfinance":
            # dividend_yield 是百分比形式
            if "dividendYieldTtm" in metrics and metrics["dividendYieldTtm"] is not None:
                metrics["dividendYieldTtm"] = round(metrics["dividendYieldTtm"] / 100, 6)
                # 同步修改原始数据
            if "dividend_yield" in data and data["dividend_yield"] is not None:
                data["dividend_yield"] = round(data["dividend_yield"] / 100, 6)
            # debt_to_equity 是百分比形式
            if "debtToEquity" in metrics and metrics["debtToEquity"] is not None:
                metrics["debtToEquity"] = round(metrics["debtToEquity"] / 100, 6)
                # 同步修改原始数据
            if "debt_to_equity" in data and data["debt_to_equity"] is not None:
                data["debt_to_equity"] = round(data["debt_to_equity"] / 100, 6)
        
        return metrics

    @staticmethod
    async def fetch_from_akshare(symbol: str) -> Dict[str, Any]:
        """从 AkShare 获取市场指标"""
        try:
            code = symbol.split(".")[0].zfill(5)
            m_df = await asyncio.to_thread(
                ak.stock_hk_financial_indicator_em, 
                symbol=code
            )
            
            if m_df.empty:
                return {}
            
            r = {str(k).strip(): v for k, v in m_df.iloc[0].to_dict().items()}
            
            # 使用共享方法提取字段
            metrics = MetricsFetcher._extract_metrics(r, "akshare")
            
            # 保留原始数据
            metrics["raw_akshare"] = r
            metrics["_source"] = "akshare"
            return metrics
            
        except Exception as e:
            print(f"  [MetricsFetcher/AkShare] Error: {e}")
            return {}

    @staticmethod
    async def fetch_from_openbb(symbol: str, provider: str = "yfinance") -> Dict[str, Any]:
        """从 OpenBB 获取市场指标"""
        try:
            res = await asyncio.to_thread(
                obb_any.equity.fundamental.metrics,
                symbol=symbol, 
                provider=provider,
            )
            
            if not res or not res.results:
                return {}
            
            data = res.results[0].dict() if hasattr(res.results[0], 'dict') else vars(res.results[0])
            
            # 使用共享方法提取字段
            metrics = MetricsFetcher._extract_metrics(data, provider)
            
            # 保留原始数据
            metrics["raw_openbb"] = data
            metrics["_source"] = provider
            return metrics
            
        except Exception as e:
            print(f"  [MetricsFetcher/OpenBB] Error: {e}")
            return {}


class PriceFetcher:
    """价格抓取器基类，确保下游获取标准化的 DataFrame"""

    async def fetch(self, symbol: str, days: int) -> pd.DataFrame:
        raise NotImplementedError


class AkSharePriceFetcher(PriceFetcher):
    """港股/A股专用的 AkShare 抓取器"""

    async def fetch(self, symbol: str, days: int) -> pd.DataFrame:
        # 提取 5 位港股代码
        code = symbol.split(".")[0].zfill(5)
        # 预估回溯天数 (考虑非交易日，放大倍数)
        start_date = (datetime.now() - pd.Timedelta(days=int(days * 1.8))).strftime(
            "%Y%m%d"
        )

        try:
            # 抓取日频复权数据 (qfq=前复权，确保价格连续性)
            df = await asyncio.to_thread(
                ak.stock_hk_hist,
                symbol=code,
                period="daily",
                start_date=start_date,
                adjust="qfq",
            )

            if df.empty:
                return pd.DataFrame()
            
             # 如果存在“日期”列，先去重，保留最后一条（通常是最新的）
            if "日期" in df.columns:
                df = df.drop_duplicates(subset=["日期"], keep='last')

            # --- 深度榨干：全量字段标准化映射 ---
            # 将中文业务字段映射为英文，方便下游 Processor (如 Technicals) 使用
            rename_map = {
                "日期": "date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",  # 交易金额
                "换手率": "turnover_rate",  # 情绪指标：换手率
                "振幅": "amplitude",  # 波动指标：振幅
                "涨跌幅": "pct_change",  # 动量指标：百分比涨跌
                "涨跌额": "change_amount",  # 动量指标：绝对值涨跌
            }
            df = df.rename(columns=rename_map)

            # --- 数据清洗与类型强制 ---
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            # 修正建议：强制排序，防止 API 返回乱序数据
            df.sort_index(ascending=True, inplace=True) 

            # 确保核心列存在且为数值
            numeric_cols = [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "amount",
                "turnover_rate",
                "amplitude",
                "pct_change",
                "change_amount",
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # --- 衍生核心指标 ---
            # 典型价格
            df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3
            # VWAP (成交额/成交量)，如果 AkShare 没给 vwap 字段，自己算
            if "vwap" not in df.columns and "amount" in df.columns and "volume" in df.columns:
                df["vwap"] = (df["amount"] / df["volume"]).fillna(df["close"])

            # 注意：dividend 和 split_ratio 已从 market_data 移除
            # 如需获取分红历史，请使用 FundamentalCollector 的独立接口

            # 统一索引格式
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.index.name = "date"
            return df
        except Exception as e:
            print(f"  [AkShareFetcher] Error: {e}")
            return pd.DataFrame()


class OpenBBPriceFetcher(PriceFetcher):
    """通用市场的 OpenBB 抓取器"""

    def __init__(self, provider: str = "yfinance"):
        self.provider = provider

    async def fetch(self, symbol: str, days: int) -> pd.DataFrame:
        start_date = (datetime.now() - pd.Timedelta(days=int(days * 1.6))).strftime(
            "%Y-%m-%d"
        )

        # API Key 注入
        api_key = (
            get_api_key(self.provider)
            if self.provider in ["polygon", "fmp", "alpha_vantage"]
            else None
        )
        if api_key:
            os.environ[f"{self.provider.upper()}_API_KEY"] = api_key

        try:
            # 调用 OpenBB 获取历史价格
            res = await asyncio.to_thread(
                obb_any.equity.price.historical,
                symbol=symbol,
                provider=self.provider,
                start_date=start_date,
            )

            if not res or not res.results:
                return pd.DataFrame()

            # 转换为 DataFrame
            # 注意：OpenBB 结果可能包含 'dividends', 'splits', 'capital_gains' 等额外字段
            df = pd.DataFrame([it.dict() for it in res.results])

            # --- 数据清洗 ---
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df.set_index("date", inplace=True)

            # 计算衍生指标
            df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3
            # VWAP：有就有，没有就没有，不能用 0 计算
            if "vwap" not in df.columns:
                df["vwap"] = None
            elif "amount" in df.columns and "volume" in df.columns:
                df["vwap"] = (df["amount"] / df["volume"]).fillna(df["close"])
            
            # 移除无关字段（分红和拆股应该由 FundamentalCollector 独立处理）
            cols_to_remove = ["dividends", "stock_splits", "dividend", "split_ratio"]
            for col in cols_to_remove:
                if col in df.columns:
                    df = df.drop(columns=[col])

            # 格式化日期
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.index.name = "date"
            return df
        except Exception as e:
            print(f"  [OpenBBFetcher] ({self.provider}) Error: {e}")
            return pd.DataFrame()


# ==========================================
# 2. 主 Collector 实现
# ==========================================


class MarketDataCollector(BaseCollector):
    """
    MarketDataCollector: 价格数据枢纽
    负责根据 Symbol 自动路由 Provider 并确保下游数据一致性。
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.default_provider = (
            config.get("provider", "yfinance") if config else "yfinance"
        )

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        # 1. 标准解包
        input_data = kwargs.get("input_data")
        pack = (
            input_data.payload
            if isinstance(input_data, ComponentOutput)
            else input_data
        )
        if pack is None:
            pack = ResearchPack(symbol=context.symbols[0])

        symbol = pack.symbol
        target_days = context.metadata.get("days", 250)

        # 2. 路由策略定义
        market_type = get_market_type(symbol)
        fetchers: List[PriceFetcher] = []
        if market_type == MarketType.HK:
            # 港股：首选 AkShare
            fetchers = [AkSharePriceFetcher(), OpenBBPriceFetcher("yfinance")]
        else:
            # 美股/其他：根据配置顺序尝试
            fetchers = [
                OpenBBPriceFetcher(self.default_provider),
                OpenBBPriceFetcher("yfinance"),
            ]

        # 3. 执行抓取 (带 Fallback)
        price_df = pd.DataFrame()
        used_provider = "none"

        for fetcher in fetchers:
            name = fetcher.__class__.__name__
            print(f"  [MarketData] Squeezing data from {name} for {symbol}...")
            price_df = await fetcher.fetch(symbol, target_days)
            if not price_df.empty:
                used_provider = name
                break

        # 4. 封装输出
        if not price_df.empty:
            # 截取目标长度 (Tail)
            price_df = price_df.sort_index(ascending=True)
            final_df = price_df.tail(target_days)
            # 按日期倒序排列（最新在前），与其他数据保持一致
            final_df = final_df.sort_index(ascending=False)        
                
            pack.market_data = DataFrameModel.from_df(final_df)

            # 5. 获取市场指标
            market_metrics = await self._fetch_metrics(symbol)
            if market_metrics:
                pack.market_metrics = market_metrics
                print(f"  [MarketData] Metrics: {list(market_metrics.keys())}")

            # 记录元数据到 market_data_meta
            pack.market_data_meta = {
                "price_source": used_provider,
                "columns": final_df.columns.tolist()
            }

            # 打印摘要
            extra_cols = [
                c
                for c in final_df.columns
                if c not in ["open", "high", "low", "close", "volume"]
            ]
            print(
                f"  [MarketData] Success ({len(final_df)} bars). Extra fields captured: {extra_cols}"
            )

            return ComponentOutput(success=True, payload=pack)

        return ComponentOutput(
            success=False,
            error=f"Failed to fetch market data for {symbol} from all providers",
            payload=pack,
        )

    async def _fetch_metrics(self, symbol: str) -> Dict[str, Any]:
        """获取市场指标（多 Provider Fallback）"""
        market_type = get_market_type(symbol)
        
        if market_type == MarketType.HK:
            # 港股：用 AkShare
            metrics = await MetricsFetcher.fetch_from_akshare(symbol)
            if metrics:
                return metrics
            # Fallback: 尝试 OpenBB
            return await MetricsFetcher.fetch_from_openbb(symbol, "yfinance")
        else:
            # 美股：用 OpenBB
            metrics = await MetricsFetcher.fetch_from_openbb(symbol, self.default_provider)
            if metrics:
                return metrics
            # Fallback: 尝试 yfinance
            return await MetricsFetcher.fetch_from_openbb(symbol, "yfinance")

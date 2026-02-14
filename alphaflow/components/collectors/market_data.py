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

# ==========================================
# 1. Fetcher 策略接口与实现
# ==========================================
obb_any: Any = obb


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
            if "amount" in df.columns and "volume" in df.columns:
                df["vwap"] = (df["amount"] / df["volume"]).fillna(df["close"])

            # 填充 OpenBB 兼容字段 (AkShare 日线通常不含除权除息日的具体分红数值，设为默认)
            df["dividend"] = 0.0
            df["split_ratio"] = 1.0

            # 统一索引格式
            df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
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

            # --- 深度榨干：保留 Provider 的原始增强字段 ---
            # 不要盲目 fillna(0)，先检查列是否存在
            # yfinance 通常返回 'dividends', 'stock_splits'
            if "dividends" in df.columns:
                df.rename(columns={"dividends": "dividend"}, inplace=True)
            if "stock_splits" in df.columns:
                df.rename(columns={"stock_splits": "split_ratio"}, inplace=True)

            # 仅当列完全缺失时，才进行初始化
            if "dividend" not in df.columns:
                df["dividend"] = 0.0
            else:
                df["dividend"] = pd.to_numeric(df["dividend"], errors="coerce").fillna(
                    0.0
                )

            if "split_ratio" not in df.columns:
                df["split_ratio"] = 1.0
            else:
                df["split_ratio"] = df["split_ratio"] = pd.to_numeric(
                    df["split_ratio"], errors="coerce"
                ).fillna(1.0)

            # 计算衍生指标
            df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3
            if "vwap" not in df.columns or df["vwap"].isnull().all():
                df["vwap"] = (df.get("amount", 0) / df["volume"]).fillna(df["close"])

            # 格式化日期
            df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
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
        fetchers: List[PriceFetcher] = []
        if symbol.upper().endswith(".HK"):
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
            final_df = price_df.tail(target_days)
            pack.market_data = DataFrameModel.from_df(final_df)

            # 记录元数据供下游参考
            pack.extra["price_source"] = used_provider
            pack.extra["columns"] = final_df.columns.tolist()

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

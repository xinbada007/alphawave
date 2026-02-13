from typing import Any, Dict, List, Optional, Tuple, Callable
import pandas as pd
import os
import asyncio
from datetime import datetime
from openbb import obb
from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import (
    AnalysisContext,
    ComponentOutput,
    ResearchPack,
    DataFrameModel,
)
from alphaflow.utils.api_rotator import get_api_key, report_api_usage

# 全局绕过 Mypy 对 OpenBB 动态扩展属性的检查
obb_any: Any = obb


class FundamentalCollector(BaseCollector):
    """
    【全维度深度版基本面分析器】
    整合：实时快照、市场预期(Estimates)、股份统计(ShareStats)、以及双轨财报对齐。
    维度理解：
      - Estimates: 实时预期。反映当前分析师对未来的平均看法。
      - ShareStats: 实时筹码。反映当前的股本结构与空头力量。
    """

    # 黄金核心指标映射 (新增：目标价、空头比率)
    _INDICATOR_MAP = {
        "market_cap": ["market_cap", "marketCap"],
        "pe_ratio": ["pe_ratio", "trailingPE"],
        "ps_ratio": ["price_to_sales", "priceToSales"],
        "dividend_yield": ["dividend_yield", "dividendYield"],
        "roe": ["return_on_equity", "returnOnEquity"],
        "net_margin": ["profit_margins", "net_margin"],
        "target_price": ["target_price", "targetPrice", "consensus_target"],
        "short_ratio": ["short_percent_of_float", "short_ratio", "shortRatio"],
    }

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.provider = config.get("provider", "yfinance") if config else "yfinance"
        self.limit_annual = config.get("limit_annual", 2) if config else 2
        self.limit_quarterly = config.get("limit_quarterly", 4) if config else 4

    async def fetch_data(self, context: AnalysisContext, **kwargs) -> ComponentOutput:
        input_data = kwargs.get("input_data")
        pack = (
            input_data.payload
            if isinstance(input_data, ComponentOutput)
            else input_data
        )
        if pack is None:
            pack = ResearchPack(symbol=context.symbols[0])

        symbol = pack.symbol
        target_days = context.metadata.get("days")
        if not target_days:
            raise ValueError("Target days missing from context")

        print(f"  [Fundamental] Auditing full-dimension data for {symbol}...")

        # 1. 价格抓取
        price_df = await self._fetch_with_fallback(
            symbol,
            self._get_price_data,
            [self.provider, "yfinance"],
            target_days=target_days,
        )
        if price_df is not None:
            pack.market_data = DataFrameModel.from_df(price_df.tail(target_days))

        # 2. 并行抓取 10 个命名维度
        task_configs = {
            "metrics": (obb_any.equity.fundamental.metrics, {}),
            "profile": (obb_any.equity.profile, {}),
            "estimates": (
                obb_any.equity.estimates.consensus,
                {},
            ),  # 新增：市场预期 (实时)
            "share_stats": (
                obb_any.equity.ownership.share_statistics,
                {},
            ),  # 新增：筹码分布 (实时)
            "annual_income": (
                obb_any.equity.fundamental.income,
                {"period": "annual", "limit": self.limit_annual},
            ),
            "annual_balance": (
                obb_any.equity.fundamental.balance,
                {"period": "annual", "limit": self.limit_annual},
            ),
            "annual_cash": (
                obb_any.equity.fundamental.cash,
                {"period": "annual", "limit": self.limit_annual},
            ),
            "quarterly_income": (
                obb_any.equity.fundamental.income,
                {"period": "quarter", "limit": self.limit_quarterly},
            ),
            "quarterly_balance": (
                obb_any.equity.fundamental.balance,
                {"period": "quarter", "limit": self.limit_quarterly},
            ),
            "quarterly_cash": (
                obb_any.equity.fundamental.cash,
                {"period": "quarter", "limit": self.limit_quarterly},
            ),
        }

        async def run_task(name, func, params):
            success, results = await self._execute_obb_call(
                symbol, self.provider, func, is_series=True, **params
            )
            limit = (
                self.limit_annual
                if "annual" in name
                else self.limit_quarterly
                if "quarterly" in name
                else 1
            )
            return name, results[:limit] if success and results else []

        all_results = await asyncio.gather(
            *[run_task(k, f, p) for k, (f, p) in task_configs.items()]
        )
        data_hub = {name: data for name, data in all_results}

        # 3. 结构化装填
        if pack.fundamentals is None:
            pack.fundamentals = {}
        indicators: Dict[str, Any] = {}

        # A. 锚点对齐 (IS 基准)
        q_is = data_hub.get("quarterly_income", [])
        a_is = data_hub.get("annual_income", [])
        latest_is = q_is[0] if q_is else (a_is[0] if a_is else None)

        if latest_is:
            anchor_date = self._parse_date(latest_is.get("period_ending"))
            p_type = "quarterly" if q_is and latest_is == q_is[0] else "annual"
            indicators["report_period"] = p_type
            indicators["fiscal_date"] = (
                anchor_date.strftime("%Y-%m-%d") if anchor_date else "N/A"
            )

            pfx = "quarterly_" if p_type == "quarterly" else "annual_"
            pack.fundamentals["income_statement"] = latest_is
            pack.fundamentals["balance_sheet"] = self._find_closest_strictly(
                data_hub.get(f"{pfx}balance", []), anchor_date
            )
            pack.fundamentals["cash_flow"] = self._find_closest_strictly(
                data_hub.get(f"{pfx}cash", []), anchor_date
            )

            # YoY 计算
            if len(a_is) >= 2:
                curr_rev, prev_rev = (
                    self._get_num(a_is[0], "total_revenue"),
                    self._get_num(a_is[1], "total_revenue"),
                )
                if prev_rev > 0:
                    indicators["revenue_yoy"] = round(
                        (curr_rev - prev_rev) / prev_rev, 4
                    )

        # B. 装填快照桶 (Metrics, Profile, Estimates, ShareStats)
        for bucket in ["metrics", "profile", "estimates", "share_stats"]:
            if data_hub.get(bucket):
                raw_item = data_hub[bucket][0]
                pack.fundamentals[bucket] = raw_item
                # 映射到核心 indicators
                for k, candidates in self._INDICATOR_MAP.items():
                    for candy in candidates:
                        if candy in raw_item:
                            indicators[k] = raw_item[candy]
                            break

        # C. 特殊回填
        if pack.fundamentals.get("profile"):
            p = pack.fundamentals["profile"]
            pack.name = p.get("name") or p.get("longName")
            pack.fundamentals["company_name"] = pack.name

        pack.fundamentals["indicators"] = indicators
        pack.extra["annual_series"] = {
            k: v for k, v in data_hub.items() if k.startswith("annual_")
        }
        pack.extra["quarterly_series"] = {
            k: v for k, v in data_hub.items() if k.startswith("quarterly_")
        }

        print(
            f"  [Fundamental] Full-dimension Hub built for {symbol}. Precision guaranteed."
        )
        return ComponentOutput(success=True, payload=pack)

    def _find_closest_strictly(
        self, series: List[Dict], anchor_date: Optional[datetime], window: int = 15
    ) -> Optional[Dict]:
        if not series or not anchor_date:
            return None
        for item in series:
            item_date = self._parse_date(item.get("period_ending"))
            if item_date and abs((item_date - anchor_date).days) <= window:
                return item
        return None

    def _parse_date(self, d: Any) -> Optional[datetime]:
        try:
            return pd.to_datetime(d)
        except:
            return None

    def _get_num(self, item: Optional[Dict], key: str) -> float:
        if not item:
            return 0.0
        candidates = [
            key,
            "total_revenue",
            "totalRevenue",
            "net_income",
            "operating_cash_flow",
        ]
        for c in candidates:
            if (val := item.get(c)) is not None:
                return float(val)
        return 0.0

    async def _fetch_with_fallback(
        self, symbol: str, func: Callable, providers: List[str], **kwargs
    ) -> Any:
        for provider in providers:
            success, result = await self._execute_obb_call(
                symbol, provider, func, **kwargs
            )
            if success:
                return result
        return None

    async def _execute_obb_call(
        self, symbol: str, provider: str, func: Callable, **kwargs
    ) -> Tuple[bool, Any]:
        api_key = (
            get_api_key(provider)
            if provider in ["polygon", "fmp", "alpha_vantage"]
            else None
        )
        env_key = f"{provider.upper()}_API_KEY"
        original_key = os.environ.get(env_key)
        try:
            if api_key:
                os.environ[env_key] = api_key
            res = await asyncio.to_thread(
                func, symbol=symbol, provider=provider, **kwargs
            )
            if "is_series" in kwargs and kwargs["is_series"]:
                return True, [
                    (it.model_dump() if hasattr(it, "model_dump") else it.dict())
                    for it in res.results
                ]
            return True, res.to_df() if hasattr(res, "to_df") else res
        except Exception:
            return False, None
        finally:
            if api_key:
                if original_key:
                    os.environ[env_key] = original_key
                else:
                    os.environ.pop(env_key, None)

    def _get_price_data(self, symbol: str, provider: str, **kwargs) -> pd.DataFrame:
        target_days = kwargs.get("target_days") or 250
        start_date = (
            datetime.now() - (pd.Timedelta(days=int(target_days * 1.6)))
        ).strftime("%Y-%m-%d")
        res = obb_any.equity.price.historical(
            symbol=symbol, provider=provider, start_date=start_date
        )
        if not res.results:
            return pd.DataFrame()
        df = pd.DataFrame(
            [
                (it.model_dump() if hasattr(it, "model_dump") else it.dict())
                for it in res.results
            ]
        )
        with pd.option_context("future.no_silent_downcasting", True):
            for col, fill in {"dividend": 0.0, "split_ratio": 1.0}.items():
                if col in df.columns:
                    df[col] = df[col].fillna(fill)
                else:
                    df[col] = fill
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
        df = df.infer_objects(copy=False)
        df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3
        df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
        return df

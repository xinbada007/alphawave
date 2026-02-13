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

# 全局绕过 Mypy 检查
obb_any: Any = obb


class FundamentalCollector(BaseCollector):
    """
    【博士级严谨版基本面分析器 - 最终修正版】
    原则：
      1. 确定性计算：补齐季度净利同比 (ni_growth_yoy_quarter)，确保指标对称性。
      2. 隔离探测：严格使用 _FIELD_CHAINS 隔离会计科目，杜绝数据误导。
      3. 零幻觉：找不到数据则返回 None，不输出任何伪造数字。
    """

    # 会计科目探测链 (严格隔离)
    _FIELD_CHAINS = {
        "REV": ["total_revenue", "totalRevenue", "operating_revenue"],
        "NI": ["net_income", "netIncome", "net_income_continuous_operations"],
        "OI": [
            "operating_income",
            "operatingIncome",
            "total_operating_income_as_reported",
        ],
        "OCF": ["operating_cash_flow", "totalCashFromOperatingActivities"],
        "FCF": ["free_cash_flow", "freeCashflow"],
        "ASSETS": ["total_assets", "totalAssets"],
        "C_ASSETS": ["total_current_assets", "current_assets", "totalCurrentAssets"],
        "LIAB": [
            "total_liabilities_net_minority_interest",
            "total_liabilities",
            "totalLiabilities",
        ],
        "C_LIAB": ["current_liabilities", "totalCurrentLiabilities"],
        "EQUITY": ["total_common_equity", "total_equity", "totalStockholderEquity"],
        "MCAP": ["market_cap", "marketCap"],
    }

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.provider = config.get("provider", "yfinance") if config else "yfinance"
        self.limit_annual = 2
        self.limit_quarterly = 5

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
            raise ValueError("Critical: target_days missing")

        print(f"  [Fundamental] Finalizing high-fidelity audit for {symbol}...")

        # 1. 价格抓取
        price_df = await self._fetch_with_fallback(
            symbol,
            self._get_price_data,
            [self.provider, "yfinance"],
            target_days=target_days,
        )
        if price_df is not None:
            pack.market_data = DataFrameModel.from_df(price_df.tail(target_days))

        # 2. 采集任务执行
        task_names = [
            "metrics",
            "profile",
            "estimates",
            "share_stats",
            "a_income",
            "a_balance",
            "a_cash",
            "q_income",
            "q_balance",
            "q_cash",
        ]

        async def fetch_item(name: str):
            if name == "metrics":
                func, p = obb_any.equity.fundamental.metrics, {}
            elif name == "profile":
                func, p = obb_any.equity.profile, {}
            elif name == "estimates":
                func, p = obb_any.equity.estimates.consensus, {}
            elif name == "share_stats":
                func, p = obb_any.equity.ownership.share_statistics, {}
            else:
                stmt_key = name.split("_")[1]
                period = "annual" if "a_" in name else "quarter"
                limit = (
                    self.limit_annual if period == "annual" else self.limit_quarterly
                )
                func, p = (
                    getattr(obb_any.equity.fundamental, stmt_key),
                    {"period": period, "limit": limit},
                )
            res = await self._fetch_with_fallback(
                symbol, func, [self.provider, "fmp"], is_series=True, **p
            )
            return name, res or []

        all_res = await asyncio.gather(*[fetch_item(tn) for tn in task_names])
        db = {name: data for name, data in all_res}

        # 3. 结构化装填
        if pack.fundamentals is None:
            pack.fundamentals = {}
        indicators: Dict[str, Any] = {}

        for b in ["metrics", "profile", "estimates", "share_stats"]:
            if db.get(b):
                pack.fundamentals[b] = db[b][0]

        q_income, a_income = db.get("q_income", []), db.get("a_income", [])
        latest_is = q_income[0] if q_income else (a_income[0] if a_income else None)

        if latest_is:
            anchor_date = self._parse_date(latest_is.get("period_ending"))
            p_type = "quarterly" if q_income and latest_is == q_income[0] else "annual"
            indicators["report_period"] = p_type
            indicators["fiscal_date"] = (
                anchor_date.strftime("%Y-%m-%d") if anchor_date else "N/A"
            )

            pfx = "q_" if p_type == "quarterly" else "a_"
            pack.fundamentals["income_statement"] = latest_is
            pack.fundamentals["balance_sheet"] = cur_bs = self._find_closest_strictly(
                db.get(f"{pfx}balance", []), anchor_date
            )
            pack.fundamentals["cash_flow"] = cur_cf = self._find_closest_strictly(
                db.get(f"{pfx}cash", []), anchor_date
            )

            # --- 派生指标深度审计 ---
            rev = self._get_num(latest_is, "REV")
            ni = self._get_num(latest_is, "NI")
            oi = self._get_num(latest_is, "OI")
            ocf = self._get_num(cur_cf, "OCF")
            fcf = self._get_num(cur_cf, "FCF")
            eq = self._get_num(cur_bs, "EQUITY")
            liab = self._get_num(cur_bs, "LIAB")

            # 1. 年度同比增长 (Annual YoY)
            if len(a_income) >= 2:
                r0, r1 = (
                    self._get_num(a_income[0], "REV"),
                    self._get_num(a_income[1], "REV"),
                )
                if r0 is not None and r1 is not None and r1 > 0:
                    indicators["rev_growth_yoy_annual"] = round((r0 - r1) / r1, 4)
                ni0, ni1 = (
                    self._get_num(a_income[0], "NI"),
                    self._get_num(a_income[1], "NI"),
                )
                if ni0 is not None and ni1 is not None and abs(ni1) > 0:
                    indicators["ni_growth_yoy_annual"] = round(
                        (ni0 - ni1) / abs(ni1), 4
                    )

            # 2. 季度同比增长 (Quarterly YoY)
            if p_type == "quarterly" and len(q_income) >= 5 and anchor_date:
                t_m, t_y = anchor_date.month, anchor_date.year - 1
                prev_q = next(
                    (
                        it
                        for it in q_income[1:]
                        if self._parse_date(it.get("period_ending")).month == t_m
                        and self._parse_date(it.get("period_ending")).year == t_y
                    ),
                    None,
                )
                if prev_q:
                    # 补齐季度营收同比
                    r_prev = self._get_num(prev_q, "REV")
                    if rev is not None and r_prev is not None and r_prev > 0:
                        indicators["rev_growth_yoy_quarter"] = round(
                            (rev - r_prev) / r_prev, 4
                        )
                    # 补齐季度净利同比 (关键修复点)
                    ni_prev = self._get_num(prev_q, "NI")
                    if ni is not None and ni_prev is not None and abs(ni_prev) > 0:
                        indicators["ni_growth_yoy_quarter"] = round(
                            (ni - ni_prev) / abs(ni_prev), 4
                        )

            # 3. 经营效率
            if rev and rev > 0:
                if oi is not None:
                    indicators["op_margin_period_actual"] = round(oi / rev, 4)
                if ni is not None:
                    indicators["net_margin_period_actual"] = round(ni / rev, 4)
                if fcf is not None:
                    indicators["fcf_margin_period_actual"] = round(fcf / rev, 4)
            if ni and ni != 0 and ocf is not None:
                indicators["earnings_quality_period"] = round(ocf / ni, 4)

            # 4. 杠杆与回报 (对齐资产负债表)
            if eq and eq > 0:
                if liab is not None:
                    indicators["debt_to_equity_ratio"] = round(liab / eq, 4)
                if ni is not None:
                    indicators["roe_period_actual"] = round(ni / eq, 4)
            c_assets, c_liab = (
                self._get_num(cur_bs, "C_ASSETS"),
                self._get_num(cur_bs, "C_LIAB"),
            )
            if c_assets is not None and c_liab and c_liab > 0:
                indicators["current_ratio_liquidity"] = round(c_assets / c_liab, 4)

            # 5. 跨桶实时年化 (TTM Yield)
            m_cap = self._get_num(pack.fundamentals.get("metrics"), "MCAP")
            if m_cap and m_cap > 0 and fcf is not None:
                fcf_ann = fcf * (4 if p_type == "quarterly" else 1)
                indicators["fcf_yield_realtime_ttm"] = round(fcf_ann / m_cap, 4)

        pack.fundamentals["indicators"] = indicators
        if pack.fundamentals.get("profile"):
            p = pack.fundamentals["profile"]
            pack.name = p.get("name") or p.get("longName")
            pack.fundamentals["company_name"] = pack.name

        pack.extra["annual_series"] = {
            k: v for k, v in db.items() if k.startswith("a_")
        }
        pack.extra["quarterly_series"] = {
            k: v for k, v in db.items() if k.startswith("q_")
        }

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

    def _get_num(self, item: Optional[Dict], field_alias: str) -> Optional[float]:
        if not item:
            return None
        candidates = self._FIELD_CHAINS.get(field_alias, [field_alias])
        for c in candidates:
            if (v := item.get(c)) is not None:
                try:
                    return float(v)
                except (ValueError, TypeError):
                    continue
        return None

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

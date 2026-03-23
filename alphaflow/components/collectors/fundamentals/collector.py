"""
Fundamental Collector - 财务数据采集器
调度中心：选择对应市场策略，执行任务级并发抓取
"""
from typing import Any, Dict, List, Optional
import pandas as pd

from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import (
    AnalysisContext,
    ComponentOutput,
    ResearchPack,
)
from alphaflow.core.utils import (
    find_closest_strictly,
    get_field_value,
    get_market_type,
    MarketType,
    MetaKey,
)
from alphaflow.core.keys import Key
from alphaflow.core.utils import (
    calc_ttm_stitch,
    get_fcf_raw,
)

from .strategies import USMarketStrategy, CNMarketStrategy, HKMarketStrategy
from .helpers import audit_currency_context, resolve_fx_rate


class FundamentalCollector(BaseCollector):
    """财务数据采集器 - 调度中心"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        # 挂载市场策略池
        self.strategies = {
            MarketType.US: USMarketStrategy(),
            MarketType.CN: CNMarketStrategy(),
            MarketType.HK: HKMarketStrategy(),
        }
        self.limit_annual = 2
        self.limit_quarterly = 5
    
    async def fetch_data(
        self, 
        context: AnalysisContext, 
        **kwargs
    ) -> ComponentOutput:
        """主执行流程"""
        # 标准解包
        input_data = kwargs.get("input_data")
        pack = (
            input_data.payload
            if isinstance(input_data, ComponentOutput)
            else input_data
        )
        if pack is None:
            pack = ResearchPack(symbol=context.symbols[0])
        
        symbol = pack.symbol
        market_type = get_market_type(symbol)
        is_cum = market_type in (MarketType.HK, MarketType.CN)
        
        print(f"  [Fundamental] Fetching {symbol} via {market_type.name} strategy...")
        
        # 1. 选择市场策略
        strategy = self.strategies.get(market_type, self.strategies[MarketType.US])
        
        # 2. 定义需要抓取的任务列表
        tasks = [
            "a_income", "q_income", 
            "a_balance", "q_balance", 
            "a_cash", "q_cash",
            "a_analysis", "q_analysis",
            "estimates", "share_stats",
            "dividends", "splits",
            "major_holders", "earnings_cal",
            "insider_trading", "management",
            "profile",
        ]
        
        # 3. 执行策略（Task 级别全并发 + 责任链兜底）
        db = await strategy.execute(
            symbol, 
            tasks,
            limit_a=self.limit_annual,
            limit_q=self.limit_quarterly
        )
        
        # 4. 组装 ResearchPack
        return await self._assemble_pack(pack, db, market_type, is_cum)
    
    async def _assemble_pack(
        self,
        pack: ResearchPack,
        db: Dict[str, List[Dict]],
        market_type: MarketType,
        is_cum: bool
    ) -> ComponentOutput:
        """组装 ResearchPack"""
        if pack.fundamentals is None:
            pack.fundamentals = {}
        
        # 基本信息
        for key in ["profile", "estimates", "share_stats"]:
            pack.fundamentals[key] = db.get(key, [{}])[0] if db.get(key) else None
        
        # 历史数据
        pack.fundamentals["dividends_history"] = db.get("dividends")
        pack.fundamentals["splits_history"] = db.get("splits")
        pack.fundamentals["insider_trading_history"] = db.get("insider_trading")
        pack.fundamentals["management_history"] = db.get("management")
        pack.fundamentals["major_holders"] = db.get("major_holders")
        pack.fundamentals["earnings_calendar"] = db.get("earnings_cal")
        
        # 财务报表
        q_inc = db.get("q_income", [])
        a_inc = db.get("a_income", [])
        latest_is = q_inc[0] if q_inc else (a_inc[0] if a_inc else None)
        
        if not latest_is:
            return ComponentOutput(success=True, payload=pack)
        
        # 日期与报表类型
        q_suffix = "_ytd" if is_cum else "_discrete"
        anchor_date = None
        latest_d_raw = latest_is.get(MetaKey.PERIOD_ENDING)
        if latest_d_raw:
            anchor_date = pd.to_datetime(latest_d_raw)
        
        p_type = "quarterly" if q_inc and latest_is == q_inc[0] else "annual"
        
        # 查找最近的资产负债表和现金流量表
        all_bs = db.get("q_balance", []) + db.get("a_balance", [])
        all_cf = db.get("q_cash", []) + db.get("a_cash", [])
        cur_bs = find_closest_strictly(all_bs, anchor_date)
        cur_cf = find_closest_strictly(all_cf, anchor_date)
        
        stmt_suffix = "_annual" if p_type == "annual" else f"_quarterly{q_suffix}"
        pack.fundamentals.update({
            f"income_statement{stmt_suffix}": latest_is,
            f"balance_sheet{stmt_suffix}": cur_bs,
            f"cash_flow{stmt_suffix}": cur_cf,
        })
        
        # TTM 计算与货币审计
        mcap_input = get_field_value(pack.market_metrics, Key.metrics.MARKET_CAP)
        
        ttm_ni = calc_ttm_stitch(q_inc, a_inc, lambda x: get_field_value(x, Key.income.NET_INCOME_ATTRIBUTABLE_TO_COMMON_SHAREHOLDERS), is_cum)
        ttm_rev = calc_ttm_stitch(q_inc, a_inc, lambda x: get_field_value(x, Key.income.TOTAL_REVENUE), is_cum)
        ttm_fcf = calc_ttm_stitch(
            db.get("q_cash", []), db.get("a_cash", []),
            get_fcf_raw, is_cum
        )
        equity = get_field_value(cur_bs, Key.balance.TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT) if cur_bs else None
        
        ttm_values = {
            "net_income": ttm_ni,
            "revenue": ttm_rev,
            "fcf": ttm_fcf,
            "total_equity": equity
        }
        
        currency_ctx = audit_currency_context(
            pack.market_metrics or {}, 
            ttm_values, 
            market_type
        )
        pack.fundamentals["currency_context"] = currency_ctx
        
        print(f"  [Currency] Audit: {currency_ctx.get('detected_gap')}, Factor: {currency_ctx.get('alignment_factor')}")
        
        # 汇率转换与安全赋值
        if currency_ctx.get("is_misaligned") and mcap_input is not None:
            fx_rate = await resolve_fx_rate(market_type, currency_ctx)
            
            # 3. 最终写回
            if fx_rate is not None:
                mcap_rmb = mcap_input * fx_rate
                print(f"  [Currency] Aligned Market Cap: {mcap_input:,.0f} -> {mcap_rmb:,.0f}")
                if pack.market_metrics is not None:
                    pack.market_metrics[Key.metrics.MARKET_CAP_RMB] = round(mcap_rmb, 2)
                    pack.market_metrics[Key.metrics.FX_RATE] = round(fx_rate, 4)
                    
                    # 同步更新 IS_CNY_HKD_MISMATCH 标志
                    # 精确控制：仅当港股且检测到 HKD/CNY 错配时（无论标签或数学检测）
                    detected_gap = currency_ctx.get("detected_gap")
                    if market_type == MarketType.HK and detected_gap in [
                        "HKD_CNY_MISMATCH",
                        "HKD_CNY_MISMATCH_BY_LABEL"
                    ]:
                        pack.market_metrics[Key.metrics.IS_CNY_HKD_MISMATCH] = True
        
        # 🚀 具象化统一市值：MetricEngine 的盲消费入口
        # coalesce(MARKET_CAP_RMB, MARKET_CAP) — 无论是否错配，引擎总能拿到正确的同币种市值
        if pack.market_metrics is not None:
            pack.market_metrics[Key.metrics.MARKET_CAP_ALIGNED] = (
                pack.market_metrics.get(Key.metrics.MARKET_CAP_RMB)
                or pack.market_metrics.get(Key.metrics.MARKET_CAP)
            )
        
        # 公司名称 - 使用 ACL 映射的标准 Key
        if pack.fundamentals.get("profile"):
            pack.name = pack.fundamentals["profile"].get(Key.profile.NAME)
        
        # 额外数据
        pack.extra.update({
            "annual_series": {
                k: db.get(k, []) for k in ["a_income", "a_balance", "a_cash"]
            },
            f"quarterly_series{q_suffix}": {
                f"{k}{q_suffix}": db.get(k, [])
                for k in ["q_income", "q_balance", "q_cash"]
            },
            "akshare_analysis": {
                "annual": db.get("a_analysis", []),
                "quarterly_cumulative_ytd" if is_cum else "quarterly_discrete": db.get("q_analysis", []),
            },
        })
        
        return ComponentOutput(success=True, payload=pack)

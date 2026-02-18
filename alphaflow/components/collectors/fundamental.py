from struct import pack
from typing import Any, Dict, List, Optional, Tuple, Callable
import pandas as pd
import os
import asyncio
from datetime import datetime
import akshare as ak  # type: ignore
from openbb import obb
from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import (
    AnalysisContext,
    ComponentOutput,
    ResearchPack,
    DataFrameModel,
)
from alphaflow.core.data_utils import (
    FIELD_CHAINS,
    FINANCIAL_FIELD_CHAINS,
    MARKET_FIELD_CHAINS,
    find_closest_strictly,
    get_field_value,
    get_fcf_raw,
    get_market_type,
    MarketType,
)
from alphaflow.utils.api_rotator import get_api_key, report_api_usage

# 全局绕过 Mypy 检查
obb_any: Any = obb

# ==========================================
# 1. 本地别名（向后兼容）
# ==========================================
# 使用共享模块的函数，本地保留别名以保持兼容性
_get_num = get_field_value
_get_fcf_raw = get_fcf_raw

# ==========================================
# 2. 汇率获取函数 (模块级)
# ==========================================
async def get_fx_rate(from_currency: str, to_currency: str = "CNY") -> Optional[float]:
    """
    从 AkShare 获取实时汇率
    
    Args:
        from_currency: 源币种 (如 "HKD", "USD")
        to_currency: 目标币种 (默认 CNY)
    
    Returns:
        汇率值，如果获取失败返回 None
    """
    try:
        if from_currency == "HKD":
            # 百度源实时行情 - HKD/CNY
            df = await asyncio.to_thread(ak.fx_quote_baidu, symbol="人民币")
            subset = df[df["名称"].str.contains("港元", na=False)]
            if not subset.empty:
                # 接口返回的是 CNY/HKD (1人民币兑多少港元)
                cny_to_hkd = float(subset.iloc[0]["最新价"])
                if cny_to_hkd > 0:
                    return 1.0 / cny_to_hkd  # 转换为 HKD/CNY
        elif from_currency == "USD":
            # 百度源实时行情 - USD/CNY
            df = await asyncio.to_thread(ak.fx_quote_baidu, symbol="人民币")
            subset = df[df["名称"].str.contains("美元", na=False)]
            if not subset.empty:
                # 接口返回的是 CNY/USD (1人民币兑多少美元)
                cny_to_usd = float(subset.iloc[0]["最新价"])
                if cny_to_usd > 0:
                    return 1.0 / cny_to_usd  # 转换为 USD/CNY
        return None
    except Exception as e:
        print(f"  [FX] Fetch failed for {from_currency}/{to_currency}: {e}")
        return None

def audit_currency_context(
    metrics: Dict[str, Any], 
    ttm_financials: Dict[str, Optional[float]],
    market_type: MarketType = MarketType.UNKNOWN
) -> Dict[str, Any]:
    """
    双层审计机制：
    1. 元数据审计 (Metadata Audit): 直接检查原始字段名的币种标签 (针对 AkShare)。
    2. 数学审计 (Math Audit): PE/PB 锚点对撞 (针对 YFinance/通用)。
    """
    
    market_to_currency = {
        MarketType.US: "USD",
        MarketType.HK: "HKD",
        MarketType.CN: "CNY",
        MarketType.UNKNOWN: "UNKNOWN"
    }
 # 获取默认货币字符串 (如 "USD")
    default_curr = market_to_currency.get(market_type, "UNKNOWN")
    
    audit_report = {
        "is_misaligned": False,
        "reporting_currency": default_curr,
        "trading_currency": default_curr,
        "alignment_factor": 1.0,
        "detected_gap": "NONE",
        "audit_method": "None",
        "warning_message": "Currency aligned or insufficient data to audit."
    }

    if not metrics:
        return audit_report

    # =========================================================
    # 第一层：元数据标签审计 (Metadata Audit) - 针对 AkShare/港股最准
    # =========================================================
    raw_keys = metrics.get("raw_akshare", {})
    if raw_keys:
        # 1. 探测市值的币种
        has_mcap_hkd = "总市值(港元)" in raw_keys or "港股市值(港元)" in raw_keys
        
        # 2. 探测财务指标的币种
        # AkShare 惯例："(元)" 通常指人民币/公司本币，"(港元)" 指港币
        has_eps_cny = "基本每股收益(元)" in raw_keys
        has_bps_cny = "每股净资产(元)" in raw_keys
        has_rev_cny = "营业总收入" in raw_keys # 通常不带单位，默认本币(CNY)

        # 3. 判定逻辑：如果 市值是港币 AND (EPS是人民币 OR BPS是人民币)
        if has_mcap_hkd and (has_eps_cny or has_bps_cny):
            audit_report["is_misaligned"] = True
            audit_report["detected_gap"] = "HKD_CNY_MISMATCH_BY_LABEL"
            audit_report["reporting_currency"] = "CNY"
            audit_report["trading_currency"] = "HKD"
            audit_report["audit_method"] = "Metadata_Label_Check"
            
            # 给一个初始因子，后续数学审计可以微调它
            audit_report["alignment_factor"] = 0.90 

    # =========================================================
    # 第二层：数学锚点审计 (Math Audit) - 计算精确因子
    # =========================================================
    market_cap = metrics.get('marketCap')
    api_pe = metrics.get('trailingPE')
    api_pb = metrics.get('priceToBook')
    
    # TTM 数据
    ni_ttm = ttm_financials.get('net_income') if ttm_financials else None
    equity = ttm_financials.get('total_equity') if ttm_financials else None

    math_factor = None
    math_method = "None"

    # --- 路径 A: PE 对撞 (消除股价波动噪音) ---
    if api_pe and ni_ttm and market_cap and api_pe > 0 and ni_ttm > 0:
        raw_pe = market_cap / ni_ttm
        if raw_pe > 0:
            math_factor = api_pe / raw_pe
            math_method = "PE_Collision via formulation: {api_pe / raw_pe}"

    # --- 路径 B: PB 对撞 (备选) ---
    elif api_pb and equity and market_cap and api_pb > 0 and equity > 0:
        raw_pb = market_cap / equity
        if raw_pb > 0:
            math_factor = api_pb / raw_pb
            math_method = "PB_Collision via formulation: {api_pb / raw_pb}"

    # =========================================================
    # 第三层：综合判定 (Synthesis)
    # =========================================================
    
    if math_factor:
        # 如果数学因子存在，我们用它来做最终判定
        
        # 1. 港股特殊修正：如果元数据已经判定错配，且数学因子在 0.85~1.05 之间
        # 说明数学因子验证了 0.92 左右的汇率差
        if audit_report["detected_gap"] == "HKD_CNY_MISMATCH_BY_LABEL":
             # 信任数学因子的精确度 (比如算出来是 0.9322)
             audit_report["alignment_factor"] = round(math_factor, 4)
             audit_report["audit_method"] += f" + {math_method}"
             audit_report["warning_message"] = (
                f"CONFIRMED: Currency mismatch (Labels + Math). "
                f"Financials in CNY, Market Cap in HKD. "
                f"Adjustment Factor: {math_factor:.4f}."
            )
             if 0.9 <= math_factor <= 1.1:
                 audit_report["warning_message"] = (
                    f"DETECTED: Mixed Unit Calculation. Labels show HKD/CNY mismatch, "
                    f"but Math Factor ({math_factor:.4f}) is ~1.0. This confirms the API uses "
                    f"Mixed Units (HKD Price / CNY Earnings) without FX conversion. "
                    f"Value is numerically consistent but implies an ~8% FX valuation bias."
                 )
             return audit_report

        # 2. 常规逻辑 (YFinance / 无标签情况)
        audit_report["alignment_factor"] = round(math_factor, 4)
        audit_report["audit_method"] = math_method

        if 6.0 <= math_factor <= 8.5:
            audit_report["is_misaligned"] = True
            audit_report["detected_gap"] = "USD_CNY_MISMATCH"
            audit_report["reporting_currency"] = "CNY"
            audit_report["trading_currency"] = "USD"
            audit_report["warning_message"] = f"CRITICAL: USD/CNY Mismatch (Factor: {math_factor:.2f})."
        
        elif 0.8 <= math_factor <= 0.98:
            # 只有当因子真的小于 0.98 时才报港股错配
            audit_report["is_misaligned"] = True
            audit_report["detected_gap"] = "HKD_CNY_MISMATCH"
            audit_report["reporting_currency"] = "CNY"
            audit_report["trading_currency"] = "HKD"
            audit_report["warning_message"] = f"ALERT: HKD/CNY Mismatch (Factor: {math_factor:.2f})."
        
        elif math_factor > 20.0:
            audit_report["is_misaligned"] = True
            audit_report["detected_gap"] = "ADS_MISMATCH"
            audit_report["warning_message"] = f"CRITICAL: ADS Ratio Mismatch (Factor: {math_factor:.2f})."
        
        else:
            # 因子在 0.98 ~ 1.1 之间，认为是噪音，判定为对齐
            audit_report["is_misaligned"] = False
            audit_report["detected_gap"] = "ALIGNED"
            audit_report["alignment_factor"] = 1.0 # 重置为 1.0 以免误修
            audit_report["warning_message"] = "Data appears aligned."

    # 如果没有数学因子，但元数据判定错配，直接返回元数据结论
    elif audit_report["detected_gap"] != "NONE":
        audit_report["warning_message"] = "WARNING: Mismatch detected by labels, but math validation unavailable (PE/PB missing)."

    return audit_report

# ==========================================
# 2. TTM 计算工具函数 (模块级)
# ==========================================
def calc_ttm_stitch(
    q_series: List[Dict], 
    a_series: List[Dict], 
    field_func: Callable, 
    is_cumulative: bool
) -> Optional[float]:
    """
    健壮的 TTM 计算 (支持任意年结日、支持离散/累积混合)
    """
    if not q_series:
        return None

    # 1. 获取当前报告期 (Latest Period)
    cur_item = q_series[0]
    cur_val = field_func(cur_item)
    if cur_val is None:
        return None

    cur_date_raw = cur_item.get("period_ending")
    if not cur_date_raw:
        return None
    cur_date = pd.to_datetime(cur_date_raw)

    # =================================================
    # 场景 A: 离散制 (Discrete) - 如美股 (yfinance)
    # 逻辑: 严格寻找过去连续的4个季度 (Q, Q-1, Q-2, Q-3)
    # =================================================
    if not is_cumulative:
        total_val = cur_val
        found_quarters = 1
        
        # 遍历后续数据寻找前3个季度
        # 要求: 日期必须大概相差 3, 6, 9 个月
        expected_dates = [
            cur_date - pd.DateOffset(months=3),
            cur_date - pd.DateOffset(months=6),
            cur_date - pd.DateOffset(months=9)
        ]
        
        for exp_date in expected_dates:
            # 在 q_series 里找最接近 exp_date 的报告 (容差15天)
            match = find_closest_strictly(q_series[1:], exp_date, window=20)
            if match:
                v = field_func(match)
                if v is not None:
                    total_val += v
                    found_quarters += 1
        
        # 必须凑齐4个季度才算 TTM，否则数据缺失
        if found_quarters == 4:
            return total_val
        return None

    # =================================================
    # 场景 B: 累积制 (Cumulative) - 如A股/港股 (AkShare)
    # 公式: TTM = Current_YTD + (Last_Annual - Last_Year_Same_Period_YTD)
    # =================================================
    
    # 1. 寻找 "上一份年报" (Last Annual)
    last_annual_item = None
    for item in a_series:
        d_raw = item.get("period_ending")
        if not d_raw: continue
        d = pd.to_datetime(d_raw)
        if d < cur_date:
            last_annual_item = item
            break
            
    if not last_annual_item:
        return None

    last_annual_val = field_func(last_annual_item)
    if last_annual_val is None:
        return None

    # 2. 寻找 "去年同期" (Last Year Same Period)
    target_date = cur_date - pd.DateOffset(years=1)
    pool = q_series + a_series
    last_same_period_item = find_closest_strictly(pool, target_date, window=15)
    
    if not last_same_period_item:
        if (cur_date - pd.to_datetime(last_annual_item["period_ending"])).days < 30:
            return cur_val
        return None

    last_same_period_val = field_func(last_same_period_item)
    if last_same_period_val is None:
        return None

    # 3. 执行 TTM 拼接公式
    return cur_val + (last_annual_val - last_same_period_val)


# ==========================================
# 3. 计算引擎层 (切片拼接法 TTM + 严密年化)
# ==========================================
class FinancialCalculator:
    """负责跨市场通用指标计算，支持累积制 TTM 拼接"""

    @staticmethod
    def derive_indicators(
        latest_is,
        cur_bs,
        cur_cf,
        a_income,
        q_income,
        a_cash,
        q_cash,
        p_type,
        m_cap,
        latest_ana=None,
        latest_annual_ana=None,
        is_cumulative=False,
        ttm_values=None,
        metrics=None,
        currency_ctx=None,
    ) -> Dict[str, Any]:
        indicators = {}

        # 1. 物理对比助手 (去年同期)
        def _calc_yoy_physical(
            series: List[Dict], field: str, is_quarterly: bool
        ) -> Optional[float]:
            if len(series) < 2:
                return None
            cur_val = _get_num(series[0], field)
            if cur_val is None:
                return None
            cur_date_raw = series[0].get("period_ending")
            if cur_date_raw is None:
                return None
            cur_date = pd.to_datetime(cur_date_raw)
            if not cur_date:
                return None
            target_year = cur_date.year - 1
            for prev in series[1:]:
                prev_date_raw = prev.get("period_ending")
                if prev_date_raw is None:
                    continue
                prev_date = pd.to_datetime(prev_date_raw)
                if not prev_date:
                    continue
                match = prev_date.year == target_year
                if is_quarterly:
                    match = match and (prev_date.month == cur_date.month)
                if match:
                    prev_val = _get_num(prev, field)
                    if prev_val and abs(prev_val) > 0:
                        return round((cur_val - prev_val) / abs(prev_val), 4)
            return None


        # --- A. 季度增长 ---
        if p_type == "quarterly":
            y_r_q = latest_ana.get("OPERATE_INCOME_YOY") if latest_ana else None
            indicators["rev_growth_yoy_quarter"] = (
                round(float(y_r_q) / 100, 4)
                if y_r_q is not None
                else _calc_yoy_physical(q_income, "REV", True)
            )
            y_ni_q = latest_ana.get("HOLDER_PROFIT_YOY") if latest_ana else None
            indicators["ni_growth_yoy_quarter"] = (
                round(float(y_ni_q) / 100, 4)
                if y_ni_q is not None
                else _calc_yoy_physical(q_income, "NI", True)
            )

        # --- B. 年度增长 ---
        y_r_a = (
            latest_annual_ana.get("OPERATE_INCOME_YOY") if latest_annual_ana else None
        )
        indicators["rev_growth_yoy_annual"] = (
            round(float(y_r_a) / 100, 4)
            if y_r_a is not None
            else _calc_yoy_physical(a_income, "REV", False)
        )
        y_ni_a = (
            latest_annual_ana.get("HOLDER_PROFIT_YOY") if latest_annual_ana else None
        )
        indicators["ni_growth_yoy_annual"] = (
            round(float(y_ni_a) / 100, 4)
            if y_ni_a is not None
            else _calc_yoy_physical(a_income, "NI", False)
        )

        # --- C. 效率与回报 (年化) ---
        rev, ni = _get_num(latest_is, "REV"), _get_num(latest_is, "NI")
        eq, liab = _get_num(cur_bs, "EQUITY"), _get_num(cur_bs, "LIAB")
        ocf, oi = _get_num(cur_cf, "OCF"), _get_num(latest_is, "OI")
        fcf_cur = _get_fcf_raw(cur_cf)

        cur_date = pd.to_datetime(latest_is.get("period_ending"))
        ann_multiplier = (
            (12.0 / cur_date.month)
            if (is_cumulative and cur_date and cur_date.month > 0)
            else 4.0
        )
        if p_type == "annual":
            ann_multiplier = 1.0

        # ROE
        roe_off = (
            latest_ana.get("ROE_YEARLY") or latest_ana.get("ROE_AVG")
            if latest_ana
            else None
        )
        if roe_off is not None:
            val = float(roe_off) / 100
            if latest_ana and not latest_ana.get("ROE_YEARLY") and is_cumulative and cur_date:
                val = val * (12.0 / cur_date.month)
            indicators["roe_period_actual"] = round(val, 4)
        elif ni and eq and eq > 0:
            indicators["roe_period_actual"] = round((ni * ann_multiplier) / eq, 4)

        # Margin
        npm_off = latest_ana.get("NET_PROFIT_RATIO") if latest_ana else None
        indicators["net_margin_period_actual"] = (
            round(float(npm_off) / 100, 4)
            if npm_off is not None
            else (round(ni / rev, 4) if ni and rev and rev > 0 else None)
        )
        indicators["op_margin_period_actual"] = (
            round(oi / rev, 4) if oi and rev and rev > 0 else None
        )
        if fcf_cur is not None and rev and rev > 0:
            indicators["fcf_margin_period_actual"] = round(fcf_cur / rev, 4)

        # --- D. 杠杆与流动性 ---
        if eq and eq > 0 and liab is not None:
            indicators["total_liabilities_to_equity"] = round(liab / eq, 4)
        cr_off = latest_ana.get("CURRENT_RATIO") if latest_ana else None
        if cr_off is not None:
            indicators["current_ratio_liquidity"] = round(float(cr_off), 4)
        else:
            ca, cl = _get_num(cur_bs, "C_ASSETS"), _get_num(cur_bs, "C_LIAB")
            indicators["current_ratio_liquidity"] = (
                round(ca / cl, 4) if ca and cl and cl > 0 else None
            )
        if ni and abs(ni) > 0 and ocf is not None:
            indicators["earnings_quality_period"] = round(ocf / ni, 4)

        # --- E. 实时估值 (TTM 平滑) ---
        # 使用内部函数 _calculate_fcf_yield（严格遵循审计结果）
        if m_cap and m_cap > 0:
            # 优先使用外部传入的 ttm_values
            if ttm_values and metrics and currency_ctx:
                # 内部函数：使用已转换的 m_cap
                def _calculate_fcf_yield(ttm_fcf, ttm_ni, metrics, currency_ctx, m_cap):
                    if ttm_fcf is None:
                        return None
                    method = currency_ctx.get("audit_method", "")
                    
                    # 路径 A: PE 降维
                    if "PE_Collision" in method:
                        api_pe = metrics.get('trailingPE') or metrics.get('pe_ratio')
                        if api_pe and api_pe > 0 and ttm_ni and ttm_ni > 0:
                            return (ttm_fcf / ttm_ni) / api_pe
                    
                    # 路径 B: 使用已转换的 m_cap
                    if m_cap and m_cap > 0 :
                        return (ttm_fcf / m_cap)
                    
                    return None
                
                fcf_yield = _calculate_fcf_yield(
                    ttm_fcf=ttm_values.get("fcf"),
                    ttm_ni=ttm_values.get("net_income"),
                    metrics=metrics,
                    currency_ctx=currency_ctx,
                    m_cap=m_cap
                )
                if fcf_yield is not None:
                    indicators["fcf_yield_realtime_ttm"] = round(fcf_yield, 4)
                    
        return indicators


# ==========================================
# 3. 抓取层实现
# ==========================================
class BaseFetcher:
    async def fetch_all(
        self, symbol: str, limit_a: int, limit_q: int, tasks: Optional[List[str]] = None
    ) -> Dict[str, List[Dict]]:
        raise NotImplementedError


class YFinanceFetcher(BaseFetcher):
    def __init__(self, provider: str, parent):
        self.provider, self.parent = provider, parent

    async def fetch_all(
        self, symbol: str, limit_a: int, limit_q: int, tasks: Optional[List[str]] = None
    ) -> Dict[str, List[Dict]]:
        all_task_names = [
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
        target_tasks = tasks if tasks else all_task_names

        async def fetch_item(name: str):
            p: Dict[str, Any] = {}
            if name == "profile":
                func, p = obb_any.equity.profile, {}
            elif name == "estimates":
                func, p = obb_any.equity.estimates.consensus, {}
            elif name == "share_stats":
                func, p = obb_any.equity.ownership.share_statistics, {}
            else:
                stmt, period = (
                    name.split("_")[1],
                    ("annual" if "a_" in name else "quarter"),
                )
                limit = limit_a if period == "annual" else limit_q
                func, p = (
                    getattr(obb_any.equity.fundamental, stmt),
                    {"period": period, "limit": limit},
                )
            
            # 调试信息
            print(f"  [YFinanceFetcher] Fetching {name} for {symbol} with provider={self.provider}...")
            
            res = await self.parent._fetch_with_fallback(
                symbol, func, providers=[self.provider], is_series=True, **p
            )
            
            # 调试信息
            if res:
                print(f"  [YFinanceFetcher] {name}: Got {len(res)} records")
            else:
                print(f"  [YFinanceFetcher] {name}: No data returned")
            
            return name, res or []

        all_res = await asyncio.gather(*[fetch_item(tn) for tn in target_tasks])
        result = {name: data for name, data in all_res}
        if tasks is None:
            for name in all_task_names:
                if name not in result:
                    result[name] = []
        return result

class AkShareFetcher(BaseFetcher):
    def __init__(self, parent):
        self.parent = parent

    async def fetch_all(
        self, symbol: str, limit_a: int, limit_q: int, tasks: Optional[List[str]] = None
    ) -> Dict[str, List[Dict]]:
        code = symbol.split(".")[0].zfill(5)

        async def fetch_rep(tbl: str, p_type: str, lim: int):
            try:
                df = await asyncio.to_thread(
                    ak.stock_financial_hk_report_em,
                    stock=code,
                    symbol=tbl,
                    indicator=p_type,
                )
                if df.empty:
                    return []
                tdf = (
                    df.pivot_table(
                        index="REPORT_DATE",
                        columns="STD_ITEM_NAME",
                        values="AMOUNT",
                        aggfunc="first",  # type: ignore[arg-type]
                    )
                    .sort_index(ascending=False)
                    .head(lim)
                )
                tdf.index = pd.to_datetime(tdf.index).strftime("%Y-%m-%d")
                tdf.index.name = "period_ending"
                return tdf.reset_index().to_dict(orient="records")
            except:
                return []

        async def fetch_ana(p_type: str, lim: int):
            try:
                df = await asyncio.to_thread(
                    ak.stock_financial_hk_analysis_indicator_em,
                    symbol=code,
                    indicator=p_type,
                )
                if df.empty:
                    return []
                df = df.sort_values("REPORT_DATE", ascending=False).head(lim)
                df["period_ending"] = pd.to_datetime(df["REPORT_DATE"]).dt.strftime(
                    "%Y-%m-%d"
                )
                return df.to_dict(orient="records")
            except:
                return []

        res = await asyncio.gather(
            fetch_rep("利润表", "年度", limit_a),
            fetch_rep("利润表", "报告期", limit_q),
            fetch_rep("资产负债表", "年度", limit_a),
            fetch_rep("资产负债表", "报告期", limit_q),
            fetch_rep("现金流量表", "年度", limit_a),
            fetch_rep("现金流量表", "报告期", limit_q),
            fetch_ana("年度", limit_a),
            fetch_ana("报告期", limit_q),
        )

        # metrics 已移至 market_data.py 获取，此处不再重复获取
        profile, shares = [], None
        try:
            # 这里原本获取 metrics 的逻辑已移除，保留 profile 和 shares 获取
            p_df, c_df = (
                await asyncio.to_thread(ak.stock_hk_security_profile_em, symbol=code),
                await asyncio.to_thread(ak.stock_hk_company_profile_em, symbol=code),
            )
            pr = (
                {str(k).strip(): v for k, v in p_df.iloc[0].to_dict().items()}
                if not p_df.empty
                else {}
            )
            cr = (
                {str(k).strip(): v for k, v in c_df.iloc[0].to_dict().items()}
                if not c_df.empty
                else {}
            )
            # 直接附着原始数据
            profile = [{}]
            if pr:
                profile[0]["security_profile"] = pr
                if pr.get("证券简称"):
                    profile[0]["name"] = pr.get("证券简称")
            if cr:
                profile[0]["company_profile"] = cr
                if not profile[0].get("name") and cr.get("公司名称"):
                    profile[0]["name"] = cr.get("公司名称")
            
        except Exception as e:
            print(f"  [Fundamental] Warning: Failed to fetch profile for {symbol}: {e}")

        return {
            "profile": profile,
            "estimates": [],
            "share_stats": [],
            "a_income": res[0],
            "q_income": res[1],
            "a_balance": res[2],
            "q_balance": res[3],
            "a_cash": res[4],
            "q_cash": res[5],
            "a_analysis": res[6],
            "q_analysis": res[7],
        }


# ==========================================
# 4. 主 Collector
# ==========================================
class FundamentalCollector(BaseCollector):
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.provider = config.get("provider", "yfinance") if config else "yfinance"
        self.limit_annual, self.limit_quarterly = 2, 5

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
        print(f"  [Fundamental] Auditing {symbol} with slice-stitch TTM...")

        latest_price = None
        if pack.market_data:
            try:
                # 从 DataFrameModel 转回 DataFrame，取最后一行 Close
                df_price = pack.market_data.to_df()
                if not df_price.empty and "close" in df_price.columns:
                    latest_price = df_price.iloc[-1]["close"]
            except Exception as e:
                print(
                    f"  [Fundamental] Warning: Failed to extract price from market_data: {e}"
                )

        market_type = get_market_type(symbol)
        is_cum = market_type in (MarketType.HK, MarketType.CN)
        is_hk = market_type == MarketType.HK

        if is_hk:
            # 🟢 港股混合编排模式：并行执行
            ak_fetcher = AkShareFetcher(self)
            yf_fetcher = YFinanceFetcher(self.provider, self)

            # Task 1: AkShare 拿所有核心财报
            ak_task = ak_fetcher.fetch_all(
                symbol, self.limit_annual, self.limit_quarterly
            )

            # Task 2: YFinance 拿补丁数据 (Estimates + Share Stats)
            # 注意：YFinanceFetcher 内部会自动处理 clean_symbol
            yf_task = yf_fetcher.fetch_all(
                symbol,
                self.limit_annual,
                self.limit_quarterly,
                tasks=["estimates", "share_stats"],
            )

            db_ak, db_yf = await asyncio.gather(ak_task, yf_task)

            # 数据拼图：以 AkShare 为主，用 YFinance 补全缺失维度
            db = {**db_ak, **db_yf}
            for k, v in db_yf.items():
                if v:  # 只有 YFinance 真正拿到了数据，才更新到 db 里
                    db[k] = v
        elif is_cum:
            # 🟡 A股模式：保持原有的纯 AkShare 逻辑
            ak_fetcher = AkShareFetcher(self)
            db = await ak_fetcher.fetch_all(
                symbol, self.limit_annual, self.limit_quarterly
            )
        else:
            # 🔵 美股/其他：纯 YFinance 路径
            fetcher = YFinanceFetcher(self.provider, self)
            db = await fetcher.fetch_all(
                symbol, self.limit_annual, self.limit_quarterly
            )

        if pack.fundamentals is None:
            pack.fundamentals = {}
        for b in ["profile", "estimates", "share_stats"]:
            pack.fundamentals[b] = db[b][0] if db.get(b) else None

        q_inc, a_inc = db.get("q_income", []), db.get("a_income", [])
        latest_is = q_inc[0] if q_inc else (a_inc[0] if a_inc else None)
        q_suffix = "_ytd" if is_cum else "_discrete"

        if latest_is:
            # 初始化 anchor_date 为 None，确保后续使用不会报 possibly unbound
            anchor_date: Optional[pd.Timestamp] = None
            latest_d_raw = latest_is.get("period_ending")
            if latest_d_raw:
                anchor_date = pd.to_datetime(latest_d_raw)
            p_type = "quarterly" if q_inc and latest_is == q_inc[0] else "annual"
            all_bs, all_cf = (
                db.get("q_balance", []) + db.get("a_balance", []),
                db.get("q_cash", []) + db.get("a_cash", []),
            )
            cur_bs, cur_cf = (
                find_closest_strictly(all_bs, anchor_date),
                find_closest_strictly(all_cf, anchor_date),
            )

            stmt_suffix = "_annual" if p_type == "annual" else f"_quarterly{q_suffix}"
            pack.fundamentals.update(
                {
                    f"income_statement{stmt_suffix}": latest_is,
                    f"balance_sheet{stmt_suffix}": cur_bs,
                    f"cash_flow{stmt_suffix}": cur_cf,
                }
            )

            # 计算引擎：执行切片拼接 TTM 逻辑
            analysis_pool = db.get(
                "q_analysis" if p_type == "quarterly" else "a_analysis", []
            )
            latest_ana = find_closest_strictly(analysis_pool, anchor_date)
            if latest_ana:
                print(
                    f"  [Alignment] Matched analysis indicators for date: {latest_ana.get('period_ending')}"
                )
            else:
                anchor_date_str = anchor_date.strftime('%Y-%m-%d') if anchor_date else "N/A"
                print(
                    f"  [Alignment] Warning: No matching indicators found for {anchor_date_str}"
                )
            # 从 market_metrics 获取 MCAP（由 market_data.py 提供）
            mcap_input = _get_num(pack.market_metrics, "MCAP")
            
            # ===== 币种错配审计 =====
            # 步骤 1: 计算 TTM 财务数据
            ttm_ni = calc_ttm_stitch(
                q_inc, a_inc,
                lambda x: _get_num(x, "NI"),
                is_cum
            )
            ttm_rev = calc_ttm_stitch(
                q_inc, a_inc,
                lambda x: _get_num(x, "REV"),
                is_cum
            )
            ttm_fcf = calc_ttm_stitch(
                db.get("q_cash", []), db.get("a_cash", []),
                _get_fcf_raw,
                is_cum
            )
            equity = _get_num(cur_bs, "EQUITY") if cur_bs else None
            
            ttm_values = {
                "net_income": ttm_ni,
                "revenue": ttm_rev,
                "fcf": ttm_fcf,
                "total_equity": equity
            }
            
            # 步骤 2: 根据市场类型获取汇率
            fx_rate = None
            if market_type == MarketType.HK:
                fx_rate = await get_fx_rate("HKD", "CNY")
            elif market_type == MarketType.US:
                fx_rate = await get_fx_rate("USD", "CNY")
            
            # 步骤 3: 调用 audit_currency_context (传入 ttm_values 作为 ttm_financials)
            currency_ctx = audit_currency_context(pack.market_metrics or {}, ttm_values, market_type)
            pack.fundamentals["currency_context"] = currency_ctx
            print(f"  [Currency] Audit: {currency_ctx.get('detected_gap')}, Factor: {currency_ctx.get('alignment_factor')}")
            
            # 步骤 4: 根据审计结果决定是否转换
            if currency_ctx.get("is_misaligned") and fx_rate is not None and mcap_input is not None:
                mcap_rmb = mcap_input * fx_rate
                print(
                    f"  [Currency] Aligned Market Cap: {mcap_input:,.0f} -> {mcap_rmb:,.0f} (Rate: {fx_rate:.4f})"
                )
                mcap_input = mcap_rmb
                # 更新 market_metrics 中的对齐后市值
                if pack.market_metrics:
                    pack.market_metrics["market_cap_rmb"] = mcap_input
                    pack.market_metrics["fx_rate"] = fx_rate

            q_ana_pool = db.get("q_analysis", [])
            a_ana_pool = db.get("a_analysis", [])
            # 当前周期指标：动态根据 p_type 选池，并与 anchor_date 严格对齐
            current_ana_pool = q_ana_pool if p_type == "quarterly" else a_ana_pool
            latest_ana = find_closest_strictly(current_ana_pool, anchor_date)
            # 年度对比指标：固定从 a_ana_pool 选，并与 anchor_date 对齐
            latest_annual_ana = find_closest_strictly(a_ana_pool, anchor_date)
            if latest_ana:
                print(
                    f"  [Alignment] Matched indicators for: {latest_ana.get('period_ending')}"
                )

            indicators = FinancialCalculator.derive_indicators(
                latest_is,
                cur_bs,
                cur_cf,
                a_inc,
                q_inc,
                db.get("a_cash", []),
                db.get("q_cash", []),
                p_type,
                mcap_input,
                latest_ana,
                latest_annual_ana,
                is_cumulative=is_cum,
                ttm_values=ttm_values,
                metrics=pack.market_metrics or {},
                currency_ctx=currency_ctx,
            )
            indicators.update(
                {
                    "report_period": p_type,
                    "fiscal_date": anchor_date.strftime("%Y-%m-%d")
                    if anchor_date
                    else "N/A",
                }
            )
            pack.fundamentals["indicators"] = indicators

        if pack.fundamentals.get("profile"):
            pack.name = pack.fundamentals["profile"].get("name")

        pack.extra.update(
            {
                "annual_series": {
                    k: db.get(k, []) for k in ["a_income", "a_balance", "a_cash"]
                },
                f"quarterly_series{q_suffix}": {
                    f"{k}{q_suffix}": db.get(k, [])
                    for k in ["q_income", "q_balance", "q_cash"]
                },
                "akshare_analysis": {
                    "annual": db.get("a_analysis", []),
                    "quarterly_cumulative_ytd"
                    if is_cum
                    else "quarterly_discrete": db.get("q_analysis", []),
                },
            }
        )
        return ComponentOutput(success=True, payload=pack)

    async def _fetch_with_fallback(
        self, symbol: str, func: Callable, 
        providers: Optional[List[str]] = None,  # 新增：允许传入 providers 列表
        **kwargs
    ) -> Any:
        if providers is None:
            providers = [self.provider]  # 默认只用配置的 provider
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
        try:
            if api_key:
                os.environ[f"{provider.upper()}_API_KEY"] = api_key
            res = await asyncio.to_thread(
                func, symbol=symbol, provider=provider, **kwargs
            )
            if kwargs.get("is_series"):
                return True, [
                    (it.model_dump() if hasattr(it, "model_dump") else it.dict())
                    for it in res.results
                ]
            return True, res.to_df() if hasattr(res, "to_df") else res
        except Exception as e:
            print(f"  [YFinanceFetcher] Error calling {func.__name__} with provider={provider}: {e}")
            return False, None
        except:
            return False, None
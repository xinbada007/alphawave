from fractions import Fraction
from typing import Any, Dict, List, Optional, Tuple, Callable
import pandas as pd
import os
import asyncio
from datetime import datetime
import akshare as ak  # type: ignore
import yfinance as yf  # type: ignore
from openbb import obb
from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import (
    AnalysisContext,
    ComponentOutput,
    ResearchPack,
)
from alphaflow.core.data_utils import (
    DIVIDEND_FIELD_CHAINS,
    find_closest_strictly,
    get_field_value,
    get_market_type,
    MarketType,
)
from alphaflow.core.financial_math import (
    calc_ttm_stitch,
    get_fcf_raw,
)
from alphaflow.utils.api_rotator import get_api_key

# 全局绕过 Mypy 检查
obb_any: Any = obb


# ==========================================
# 1.1 分红、拆股与大股东数据获取辅助函数
# ==========================================
def _fetch_splits_yfinance(symbol: str) -> List[Dict[str, Any]]:
    """
    使用原生 yfinance 获取股票拆股历史
    
    Args:
        symbol: 股票代码 (如 "AAPL", "MSFT")
    
    Returns:
        拆股历史记录列表，格式: [{"date": "2024-06-10", "ratio": "4:1"}, ...]
    """
    try:
        ticker = yf.Ticker(symbol)
        splits = ticker.splits
        if splits is not None and not splits.empty:
            df = splits.reset_index()
            # yfinance 返回两列: 'Date' (带时区) 和 'Stock Splits' (浮点数如 4.0)
            df.columns = ['date', 'ratio_float']
            # 抹平时区并转为标准日期字符串
            df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).dt.strftime("%Y-%m-%d")
            # 将浮点数转换为标准拆股比例字符串 (如 4.0 -> "4:1", 0.25 -> "1:4")
            # 使用 Fraction 完美处理非整数拆股 (如 3:2 = 1.5)
            def _float_to_ratio(x: float) -> str:
                f = Fraction(x).limit_denominator(1000)
                return f"{f.numerator}:{f.denominator}"
            df['ratio'] = df['ratio_float'].apply(_float_to_ratio)
            # 按日期倒序排列（最新在前），与其他数据保持一致
            df = df.sort_values("date", ascending=False)
            return df[['date', 'ratio']].to_dict("records")
    except Exception as e:
        print(f"  [Native yfinance splits] Fetch failed for {symbol}: {e}")
    return []


def _fetch_major_holders_yfinance(symbol: str) -> List[Dict[str, Any]]:
    """
    使用原生 yfinance 获取大股东数据 (同步阻塞函数)
    """
    try:
        ticker = yf.Ticker(symbol)
        # 这里的属性访问会触发网络 I/O，所以必须在这个同步函数里完成
        mh = ticker.major_holders
        ih = ticker.institutional_holders
        
        holders_data = []
        if mh is not None and not mh.empty:
            holders_data.append({"type": "major_ownership_breakdown", "data": mh.to_dict(orient="records")})
        
        if ih is not None and not ih.empty:
            top_inst = ih.head(10).to_dict(orient="records")
            holders_data.append({"type": "top_institutions", "data": top_inst})
            
        return holders_data
    except Exception as e:
        print(f"  [Fallback] yfinance major_holders failed for {symbol}: {e}")
        return []


def _fetch_earnings_yfinance(symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    使用原生 yfinance 获取财报日历 (包含历史和预期)
    
    Args:
        symbol: 股票代码 (如 "AAPL", "MSFT")
        limit: 需要获取的最近财报条数 (默认 10 条)
    
    Returns:
        财报日历记录列表，包含报告日期、预期EPS、实际EPS、超预期比例
    """
    try:
        ticker = yf.Ticker(symbol)
        
        # 🌟 关键点：使用 earnings_dates 获取时间序列的财报日历
        ed = ticker.earnings_dates
        
        if ed is not None and not ed.empty:
            df = ed.reset_index()
            
            # 1. 统一列名 (yfinance 的日期列默认叫 'Earnings Date')
            df.rename(columns={'Earnings Date': 'report_date'}, inplace=True)
            
            # 2. 清洗时间戳 (抹平时区，转为大模型易读的 YYYY-MM-DD)
            if 'report_date' in df.columns:
                df['report_date'] = pd.to_datetime(df['report_date']).dt.tz_localize(None).dt.strftime("%Y-%m-%d")
            
            # 3. yfinance 默认已经是按日期降序排列的，直接取前 n 条
            df = df.head(limit)
            
            # 4. 清理 NaN 值，防止 JSON 序列化失败
            df = df.fillna("N/A")
            
            # 返回标准的 List[Dict] 格式
            return df.to_dict(orient="records")
        
        # 兜底：如果 earnings_dates 为空，再尝试旧版的 calendar
        cal = ticker.calendar
        if cal is not None:
            if isinstance(cal, pd.DataFrame) and not cal.empty:
                return [cal.to_dict()]
            elif isinstance(cal, dict) and cal:
                return [cal]

    except Exception as e:
        print(f"  [Fallback] yfinance earnings_calendar failed for {symbol}: {e}")
        
    return []

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
        "warning_message": "Currency aligned or insufficient data to audit.",
        "llm_instruction": (
            "Note: The current market cap has been adjusted using the REAL-TIME spot FX rate. "
            "However, historical financial figures are left in their original reporting currency. "
            "Do NOT apply the current FX rate to analyze historical (e.g. 2-year or 3-year) growth rates."
        )
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
                    f"but Math Factor ({math_factor:.4f}) is ~1.0. This implies the API may uses "
                    f"Mixed Units (HKD Price / CNY Earnings) without FX conversion. "
                    f"Value is numerically consistent but implies an ~8% FX valuation bias."
                 )
             return audit_report

        # 2. 常规逻辑 (YFinance / 无标签情况)
        audit_report["alignment_factor"] = round(math_factor, 4)
        audit_report["audit_method"] = math_method

        # --- 美股专用：USD/CNY 错配阈值 (6.0 ~ 8.5) ---
        if market_type == MarketType.US and 6.0 <= math_factor <= 8.5:
            audit_report["is_misaligned"] = True
            audit_report["detected_gap"] = "USD_CNY_MISMATCH"
            audit_report["reporting_currency"] = "CNY"
            audit_report["trading_currency"] = "USD"
            audit_report["warning_message"] = f"CRITICAL: USD/CNY Mismatch (Factor: {math_factor:.2f})."
        
        # --- 港股专用：HKD/CNY 错配阈值 (0.8 ~ 0.98) ---
        elif market_type == MarketType.HK and 0.8 <= math_factor <= 0.98:
            audit_report["is_misaligned"] = True
            audit_report["detected_gap"] = "HKD_CNY_MISMATCH"
            audit_report["reporting_currency"] = "CNY"
            audit_report["trading_currency"] = "HKD"
            audit_report["warning_message"] = f"ALERT: HKD/CNY Mismatch (Factor: {math_factor:.2f})."
        
        # --- 美股专用：ADS 错配阈值 (> 20) ---
        # ADS (American Depositary Shares) 美股存托凭证特有，可能存在一股多份 ADS 的情况
        elif market_type == MarketType.US and math_factor > 20.0:
            audit_report["is_misaligned"] = True
            audit_report["detected_gap"] = "ADS_MISMATCH"
            audit_report["warning_message"] = f"CRITICAL: ADS Ratio Mismatch (Factor: {math_factor:.2f})."
        
        else:
            # 因子在 0.98 ~ 1.1 之间或非港股/美股，认为是噪音，判定为对齐
            audit_report["is_misaligned"] = False
            audit_report["detected_gap"] = "ALIGNED"
            audit_report["alignment_factor"] = 1.0 # 重置为 1.0 以免误修
            audit_report["warning_message"] = "Data appears aligned."

    # 如果没有数学因子，但元数据判定错配，直接返回元数据结论
    elif audit_report["detected_gap"] != "NONE":
        audit_report["warning_message"] = "WARNING: Mismatch detected by labels, but math validation unavailable (PE/PB missing)."

    return audit_report

# 3. 抓取层实现
# ==========================================
class BaseFetcher:
    async def fetch_all(
        self, symbol: str, limit_a: int, limit_q: int, tasks: Optional[List[str]] = None
    ) -> Dict[str, List[Dict]]:
        raise NotImplementedError


class OBBFetcher(BaseFetcher):
    # ========== 字典任务路由配置 ==========
    # 直接存储函数引用，更安全、无 eval
    TASK_CONFIG: Dict[str, Dict[str, Any]] = {
        # 简单任务：直接映射 OpenBB 函数
        "profile": {"func": obb_any.equity.profile},
        "estimates": {"func": obb_any.equity.estimates.consensus},
        "share_stats": {"func": obb_any.equity.ownership.share_statistics},
        "management": {"func": obb_any.equity.fundamental.management},
        
        # 需配置排序字段的任务
        "dividends": {
            "func": obb_any.equity.fundamental.dividends,
            "sort_key": "ex_dividend_date"
        },
        "insider_trading": {
            "func": obb_any.equity.ownership.insider_trading,
            "sort_key": "transaction_date",
            "provider": "sec",  # yfinance 可能拿不到内幕交易
            "limit": 50
        },
        
        # 财务报表：动态映射 (a_income, q_income, a_balance, etc.)
        # 这些在运行时动态处理，不在此配置中
    }

    def __init__(self, provider: str, parent):
        self.provider, self.parent = provider, parent
        # 懒加载 Semaphore，避免事件循环未初始化的 RuntimeError
        self._semaphore: Optional[asyncio.Semaphore] = None

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """懒加载：确保在异步上下文中创建"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(3)  # 限制最大并发数为 5，防止 HTTP 429
        return self._semaphore

    async def _exec_obb_task(
        self,
        func: Callable,
        symbol: str,
        name: str,
        provider: Optional[str] = None,
        sort_key: Optional[str] = None,
        filter_symbol: bool = False,
        **kwargs
    ) -> List[Dict]:
        """
        [通用抽象] OpenBB 任务执行器
        :param func: OpenBB 的函数对象
        :param symbol: 股票代码
        :param name: 任务名称(用于日志)
        :param provider: 强制指定 provider (如 'nasdaq', 'sec')，None 则使用默认
        :param sort_key: 返回列表的排序键 (如 'date')
        :param filter_symbol: 是否需要二次过滤 symbol (针对 nasdaq 等返回全量数据的接口)
        :param kwargs: 传递给 func 的其他参数 (如 limit, start_date)
        """
        target_provider = provider if provider else self.provider
        
        # ========== 并发控制 ==========
        async with self.semaphore:
            try:
                # 1. 异步执行
                res = await asyncio.to_thread(
                    func,
                    symbol=symbol,
                    provider=target_provider,
                    **kwargs
                )
                
                # 2. 提取并序列化数据 (兼容 Pydantic v1/v2/Dict)
                data = []
                raw_results = []
                
                if res:
                    if hasattr(res, 'results') and res.results:
                        raw_results = res.results
                    elif isinstance(res, list):
                        raw_results = res

                for item in raw_results:
                    if hasattr(item, "model_dump"):
                        data.append(item.model_dump())
                    elif hasattr(item, "dict"):
                        data.append(item.dict())
                    elif isinstance(item, dict):
                        data.append(item)

                # 3. (可选) 二次过滤 Symbol
                if filter_symbol and data:
                    data = [x for x in data if str(x.get("symbol", "")).upper() == symbol.upper()]

                # 4. (可选) 排序
                if sort_key and data:
                    data.sort(key=lambda x: str(x.get(sort_key, "")), reverse=True)
                    
                if data:
                    return data
                    
            except Exception as e:
                print(f"  [OBBFetcher] {name} fetch failed: {e}")
            
        return []

    async def fetch_all(
        self, symbol: str, limit_a: int, limit_q: int, tasks: Optional[List[str]] = None
    ) -> Dict[str, List[Dict]]:
        # 完整的任务列表
        all_task_names = [
            "profile", "estimates", "share_stats", 
            "major_holders", "insider_trading", "earnings_cal", "management",
            "dividends", "splits",
            "a_income", "a_balance", "a_cash",
            "q_income", "q_balance", "q_cash",
        ]
        target_tasks = tasks if tasks else all_task_names

        async def fetch_item(name: str):
            # ========== 改进3: 使用字典路由替代 if-elif ==========
            
            # ---------------------------------------------------------
            # 1. 字典映射的简单任务
            # ---------------------------------------------------------
            if name in self.TASK_CONFIG:
                config = self.TASK_CONFIG[name]
                # 直接使用函数引用 (已消除 eval)
                func = config["func"]
                return name, await self._exec_obb_task(
                    func, symbol, name,
                    sort_key=config.get("sort_key"),
                    **{k: v for k, v in config.items() if k not in ("func", "sort_key")}
                )

            # ---------------------------------------------------------
            # 2. 特殊逻辑任务 (Earnings, Major Holders, Splits)
            # ---------------------------------------------------------
            elif name == "earnings_cal":
                # 策略：优先使用 fmp provider，失败则降级到原生 yfinance
                try:
                    data = await self._exec_obb_task(
                        obb_any.equity.calendar.earnings,
                        symbol, name,
                        provider="fmp"  # 使用 fmp 避免 Provider 错误
                    )
                    if data:
                        return name, data
                except Exception as e:
                    print(f"  [OBBFetcher] earnings_cal (fmp) failed: {e}")
                
                # 降级：使用原生 yfinance 获取最近 8 次的财报记录
                print(f"  [OBBFetcher] earnings_cal: Falling back to native yfinance...")
                fallback_data = await asyncio.to_thread(_fetch_earnings_yfinance, symbol, 8)
                return name, fallback_data

            elif name == "major_holders":
                # 策略：先试 OpenBB，失败则用原生 yfinance 兜底
                # Step 1: OpenBB
                data = await self._exec_obb_task(obb_any.equity.ownership.major_holders, symbol, name)
                if data:
                    return name, data
                
                # Step 2: Native YFinance Fallback (安全地在子线程执行)
                print(f"  [OBBFetcher] major_holders: Falling back to native yfinance...")
                fallback_data = await asyncio.to_thread(_fetch_major_holders_yfinance, symbol)
                
                if fallback_data:
                    return name, fallback_data
                    
                return name, []

            elif name == "splits":
                # 策略：OpenBB (fmp) -> Native YFinance
                data = await self._exec_obb_task(
                    obb_any.equity.calendar.splits, 
                    symbol, name, 
                    provider="fmp", 
                    sort_key="date"
                )
                if data: return name, data
                
                # Native Fallback
                print(f"  [OBBFetcher] splits: Falling back to native yfinance...")
                native_data = await asyncio.to_thread(_fetch_splits_yfinance, symbol)
                return name, native_data

            # ---------------------------------------------------------
            # 3. 财务报表 (动态映射: a_income, q_balance, etc.)
            # ---------------------------------------------------------
            else:
                # 解析任务名: a_income -> income, annual
                parts = name.split("_")
                if len(parts) >= 2 and parts[1] in ("income", "balance", "cash"):
                    stmt_key = parts[1]
                    period = "annual" if "a_" in name else "quarter"
                    limit = limit_a if period == "annual" else limit_q
                    
                    if hasattr(obb_any.equity.fundamental, stmt_key):
                        func = getattr(obb_any.equity.fundamental, stmt_key)
                        return name, await self._exec_obb_task(
                            func, symbol, name, 
                            period=period, limit=limit
                        )
                
            return name, []

        # 并行执行所有任务
        all_res = await asyncio.gather(*[fetch_item(tn) for tn in target_tasks])
        
        result = {name: data for name, data in all_res}
        
        # 确保所有请求的 key 都在结果中 (即使为空)
        if tasks is None:
            for name in all_task_names:
                if name not in result:
                    result[name] = []
                    
        return result

class AkShareFetcher(BaseFetcher):
    # 类级别并发控制：严格限制为2，防止触发AkShare免费API的WAF防护
    _semaphore = asyncio.Semaphore(2)
    
    def __init__(self, parent):
        self.parent = parent

    async def fetch_all(
        self, symbol: str, limit_a: int, limit_q: int, tasks: Optional[List[str]] = None
    ) -> Dict[str, List[Dict]]:
        code = symbol.split(".")[0].zfill(5)

        async def fetch_rep(tbl: str, p_type: str, lim: int):
            async with AkShareFetcher._semaphore:
                try:
                    df = await asyncio.to_thread(
                        ak.stock_financial_hk_report_em,
                        stock=code,
                        symbol=tbl,
                        indicator=p_type,
                    )
                    if df.empty:
                        return []
                    
                    # ===== 提取元数据 (DATE_TYPE_CODE, START_DATE) =====
                    meta_dict = {}
                    meta_cols = [c for c in ["DATE_TYPE_CODE", "START_DATE"] if c in df.columns]
                    if meta_cols:
                        meta_df = df[["REPORT_DATE"] + meta_cols].drop_duplicates()
                        meta_dict = meta_df.set_index("REPORT_DATE").to_dict("index")
                    
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
                    
                    # ===== 将元数据拼回 tdf =====
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
                    print(f"  [AkShareFetcher] fetch_rep({tbl}) failed: {e}")
                    return []

        async def fetch_ana(p_type: str, lim: int):
            async with AkShareFetcher._semaphore:
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
                except Exception as e:
                    print(f"  [AkShareFetcher] fetch_ana({p_type}) failed: {e}")
                    return []

        # 🌟 新增：专门抓取港股分红派息的内部函数
        async def fetch_hk_dividends():
            async with AkShareFetcher._semaphore:
                try:
                    df = await asyncio.to_thread(
                        ak.stock_hk_dividend_payout_em,
                        symbol=code
                    )
                    if df.empty:
                        return []
                    
                    # 字段标准化：将中文列名映射为标准英文 Key
                    # 使用 DIVIDEND_FIELD_CHAINS 进行映射
                    rename_map = {}
                    for std_key, aliases in DIVIDEND_FIELD_CHAINS.items():
                        # 找到中文列名
                        for alias in aliases:
                            if alias in df.columns:
                                rename_map[alias] = std_key.lower()
                                break
                    
                    df = df.rename(columns=rename_map)
                    
                    # 统一日期格式为 YYYY-MM-DD
                    date_cols = ["ex_dividend_date", "announce_date", "payment_date"]
                    for col in date_cols:
                        if col in df.columns:
                            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d").fillna("N/A")
                    
                    # 填充空值
                    df = df.fillna("N/A")
                    
                    # 按日期倒序排列（最新在前），与三表保持一致
                    if "ex_dividend_date" in df.columns:
                        df = df.sort_values("ex_dividend_date", ascending=False)
                    
                    return df.to_dict(orient="records")
                except Exception as e:
                    print(f"  [AkShareFetcher] fetch_hk_dividends failed: {e}")
                    return []

        # 🌟 所有任务并行执行（包含港股分红）
        res = await asyncio.gather(
            fetch_rep("利润表", "年度", limit_a),       # 0
            fetch_rep("利润表", "报告期", limit_q),     # 1
            fetch_rep("资产负债表", "年度", limit_a),   # 2
            fetch_rep("资产负债表", "报告期", limit_q), # 3
            fetch_rep("现金流量表", "年度", limit_a),   # 4
            fetch_rep("现金流量表", "报告期", limit_q), # 5
            fetch_ana("年度", limit_a),               # 6
            fetch_ana("报告期", limit_q),             # 7
            fetch_hk_dividends()                      # 8 <- 港股分红
        )
        
        # metrics 已移至 market_data.py 获取，此处不再重复获取
        profile = []
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
            "dividends": res[8],  # 港股分红数据
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
        print(f"  [Fundamental] Auditing {symbol} with slice-stitch TTM...")

        market_type = get_market_type(symbol)
        is_cum = market_type in (MarketType.HK, MarketType.CN)
        is_hk = market_type == MarketType.HK

        if is_hk:
            # 🟢 港股混合编排模式：并行执行
            ak_fetcher = AkShareFetcher(self)
            yf_fetcher = OBBFetcher(self.provider, self)

            # Task 1: AkShare 拿所有核心财报
            ak_task = ak_fetcher.fetch_all(
                symbol, self.limit_annual, self.limit_quarterly
            )

            # Task 2: OBB 拿补丁数据 (Estimates + Share Stats + Splits)
            # 注意：OBBFetcher 内部会自动处理 clean_symbol
            # 港股分红已由 AkShareFetcher 处理，这里只需要抓取拆股
            yf_task = yf_fetcher.fetch_all(
                symbol,
                self.limit_annual,
                self.limit_quarterly,
                tasks=["estimates", "share_stats", "splits", "major_holders", "earnings_cal", "insider_trading", "management"],
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
            # 🔵 美股/其他：纯 OBB 路径 - 使用全量抓取
            fetcher = OBBFetcher(self.provider, self)
            db = await fetcher.fetch_all(
                symbol, self.limit_annual, self.limit_quarterly
            )

        if pack.fundamentals is None:
            pack.fundamentals = {}
        for b in ["profile", "estimates", "share_stats"]:
            pack.fundamentals[b] = db[b][0] if db.get(b) else None
        
        # 无差别存储各类资产数据（只要 db 里有，就装入）
        # 移除了已废弃的 management_discussion_analysis
        pack.fundamentals["dividends_history"] = db.get("dividends")
        pack.fundamentals["splits_history"] = db.get("splits")
        pack.fundamentals["insider_trading_history"] = db.get("insider_trading")
        pack.fundamentals["management_history"] = db.get("management")
        
        # 🌟 补上漏掉的 major_holders 和 earnings_cal
        pack.fundamentals["major_holders"] = db.get("major_holders")
        pack.fundamentals["earnings_calendar"] = db.get("earnings_cal")

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

            # 从 market_metrics 获取 MCAP（由 market_data.py 提供）
            mcap_input = get_field_value(pack.market_metrics, "MCAP")
            
            # ===== 币种错配审计 =====
            # 步骤 1: 计算 TTM 财务数据
            ttm_ni = calc_ttm_stitch(
                q_inc, a_inc,
                lambda x: get_field_value(x, "NI"),
                is_cum
            )
            ttm_rev = calc_ttm_stitch(
                q_inc, a_inc,
                lambda x: get_field_value(x, "REV"),
                is_cum
            )
            ttm_fcf = calc_ttm_stitch(
                db.get("q_cash", []), db.get("a_cash", []),
                get_fcf_raw,
                is_cum
            )
            equity = get_field_value(cur_bs, "EQUITY") if cur_bs else None
            
            ttm_values = {
                "net_income": ttm_ni,
                "revenue": ttm_rev,
                "fcf": ttm_fcf,
                "total_equity": equity
            }
            
            # 步骤 2: 调用 audit_currency_context (传入 ttm_values 作为 ttm_financials)
            currency_ctx = audit_currency_context(pack.market_metrics or {}, ttm_values, market_type)
            pack.fundamentals["currency_context"] = currency_ctx
            print(f"  [Currency] Audit: {currency_ctx.get('detected_gap')}, Factor: {currency_ctx.get('alignment_factor')}")
            
            # 步骤 4: 根据审计结果决定是否转换
            if currency_ctx.get("is_misaligned") and mcap_input is not None:
                fx_rate = None
                if market_type == MarketType.HK:
                    fx_rate = await get_fx_rate("HKD", "CNY")
                elif market_type == MarketType.US:
                    fx_rate = await get_fx_rate("USD", "CNY")
                if fx_rate is not None:
                    mcap_rmb = mcap_input * fx_rate
                    print(
                        f"  [Currency] Aligned Market Cap: {mcap_input:,.0f} -> {mcap_rmb:,.0f} (Rate: {fx_rate:.4f})"
                    )
                    mcap_input = mcap_rmb
                    # 更新 market_metrics 中的对齐后市值
                    if pack.market_metrics:
                        pack.market_metrics["market_cap_rmb"] = mcap_input
                        pack.market_metrics["fx_rate"] = fx_rate


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

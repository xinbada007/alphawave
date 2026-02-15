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
from alphaflow.utils.api_rotator import get_api_key, report_api_usage

# 全局绕过 Mypy 检查
obb_any: Any = obb

# ==========================================
# 1. 核心数据字典 (支持多市场语义拦截)
# ==========================================
FIELD_CHAINS = {
    "REV": [
        "total_revenue",
        "totalRevenue",
        "OPERATE_INCOME",
        "营业总收入",
        "营业额",
        "收益",
        "营业收入",
    ],
    "NI": [
        "net_income",
        "netIncome",
        "HOLDER_PROFIT",
        "归母净利润",
        "股东应占溢利",
        "期内利润",
        "期内盈利",
        "净利润",
    ],
    "OI": ["operating_income", "operatingIncome", "经营溢利", "营业利润", "PER_OI"],
    "OCF": [
        "operating_cash_flow",
        "totalCashFromOperatingActivities",
        "经营业务现金净额",
        "经营活动产生的现金流量净额",
        "PER_NETCASH_OPERATE",
    ],
    "FCF": ["free_cash_flow", "freeCashflow", "自由现金流"],
    "CAPEX": [
        "capital_expenditure",
        "capitalExpenditures",
        "购建固定资产、无形资产和其他长期资产支付的现金",
        "购建固定资产",
        "资本开支",
    ],
    "ASSETS": ["total_assets", "totalAssets", "资产总额", "总资产", "资产合计"],
    "C_ASSETS": [
        "total_current_assets",
        "current_assets",
        "totalCurrentAssets",
        "流动资产合计",
    ],
    "LIAB": [
        "total_liabilities_net_minority_interest",
        "total_liabilities",
        "totalLiabilities",
        "总负债",
        "负债合计",
    ],
    "C_LIAB": ["current_liabilities", "totalCurrentLiabilities", "流动负债合计"],
    "EQUITY": [
        "total_common_equity",
        "total_equity",
        "totalStockholderEquity",
        "总权益",
        "股东权益",
        "权益总额",
        "所有者权益合计",
    ],
    "MCAP": ["marketCap", "market_cap", "marketCap", "总市值", "总市值(港元)"],
    "SHARES": ["sharesOutstanding", "shares_outstanding", "已发行股本(股)"],
}


def _get_num(item: Optional[Dict], field_alias: str) -> Optional[float]:
    """确定性字段提取逻辑"""
    if not item:
        return None
    candidates = FIELD_CHAINS.get(field_alias, [field_alias])
    for c in candidates:
        v = item.get(c)
        if v is not None and v != "" and not pd.isna(v):
            try:
                return float(v)
            except (ValueError, TypeError):
                continue
    return None


def _get_fcf_raw(item: Optional[Dict]) -> Optional[float]:
    """物理推导 FCF (OCF - abs(Capex))"""
    if not item:
        return None
    f = _get_num(item, "FCF")
    if f is not None:
        return f
    o = _get_num(item, "OCF")
    c = _get_num(item, "CAPEX")
    if o is not None and c is not None:
        return o - abs(c)
    return None


# ==========================================
# 2. 计算引擎层 (切片拼接法 TTM + 严密年化)
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

        # 2. 累积制 TTM 拼接助手 (对齐用户提供的严密逻辑)
        def _calc_ttm_stitch(
            q_series: List[Dict], a_series: List[Dict], field_func: Callable
        ) -> Optional[float]:
            if not q_series:
                return None

            # 情况A: 非累积制 (US)，执行最近 4 季累加
            if not is_cumulative:
                if len(q_series) >= 4:
                    total, count = 0.0, 0
                    for i in range(4):
                        v = field_func(q_series[i])
                        if v is not None:
                            total += v
                            count += 1
                    if count == 4:
                        return total
                return None

            # 情况B: 累积制 (HK/A)，执行公式: TTM = Current_YTD + (Prior_FY - Prior_YTD)
            cur_item = q_series[0]
            cur_date_raw = cur_item.get("period_ending")
            if cur_date_raw is None:
                return None
            cur_date = pd.to_datetime(cur_date_raw)

            if not cur_date:
                return None

            # 如果是 12 月报，本身就是 TTM
            cur_ytd_val = field_func(cur_item)
            if cur_date.month == 12:
                return cur_ytd_val

            # 锁定去年同期
            target_last_year, target_month = cur_date.year - 1, cur_date.month
            last_fy_val, last_same_period_val = None, None

            # 找 Prior FY (去年年报)
            if a_series:
                for a_item in a_series:
                    a_d_raw = a_item.get("period_ending")
                    if a_d_raw is None:
                        continue
                    a_date = pd.to_datetime(a_d_raw)
                    if a_date and a_date.year == target_last_year:
                        last_fy_val = field_func(a_item)
                        break

            # 找 Prior YTD (去年同期)
            if len(q_series) > 1:
                for q_item in q_series[1:]:
                    q_d_raw = q_item.get("period_ending")
                    if q_d_raw is None:
                        continue
                    q_date = pd.to_datetime(q_d_raw)
                    if (
                        q_date
                        and q_date.year == target_last_year
                        and q_date.month == target_month
                    ):
                        last_same_period_val = field_func(q_item)
                        break

            if (
                cur_ytd_val is not None
                and last_fy_val is not None
                and last_same_period_val is not None
            ):
                return cur_ytd_val + (last_fy_val - last_same_period_val)
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
            if not latest_ana.get("ROE_YEARLY") and is_cumulative and cur_date:
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
            indicators["debt_to_equity_ratio"] = round(liab / eq, 4)
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
        if m_cap and m_cap > 0:
            fcf_ttm = _calc_ttm_stitch(q_cash, a_cash, _get_fcf_raw)
            if fcf_ttm is not None:
                indicators["fcf_yield_realtime_ttm"] = round(fcf_ttm / m_cap, 4)

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
        target_tasks = tasks if tasks else all_task_names

        async def fetch_item(name: str):
            p: Dict[str, Any] = {}
            if name == "metrics":
                func, p = obb_any.equity.fundamental.metrics, {}
            elif name == "profile":
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
            res = await self.parent._fetch_with_fallback(
                symbol, func, [self.provider, "fmp"], is_series=True, **p
            )
            return name, res or []

        all_res = await asyncio.gather(*[fetch_item(tn) for tn in target_tasks])
        result = {name: data for name, data in all_res}
        if tasks is None:
            for name in all_task_names:
                if name not in result:
                    result[name] = []
        return result
        for name in all_task_names:
            if name not in result:
                result[name] = []

        return result


class AkShareAshareFetcher(BaseFetcher):
    """A股财务数据获取器 - 使用AkShare获取A股财报数据"""
    
    def __init__(self, parent):
        self.parent = parent
    
    async def fetch_all(
        self, symbol: str, limit_a: int, limit_q: int, tasks: Optional[List[str]] = None
    ) -> Dict[str, List[Dict]]:
        """获取A股财务数据"""
        code = symbol.split(".")[0]
        
        # 初始化返回结构，与 AkShareFetcher/YFinanceFetcher 对齐
        result = {
            "metrics": [],
            "profile": [],
            "estimates": [],
            "share_stats": [{"sharesOutstanding": None, "floatShares": None}],
            "a_income": [],
            "q_income": [],
            "a_balance": [],
            "q_balance": [],
            "a_cash": [],
            "q_cash": [],
            "a_analysis": [],
            "q_analysis": [],
        }
        
        try:
            # 1. 获取基本信息（股票概况）
            stock_info = await asyncio.to_thread(ak.stock_individual_info_em, symbol=code)
            if not stock_info.empty:
                info = stock_info.set_index('item').to_dict()['value']
                
                # 总市值转换为亿元（同港股逻辑）
                mcap_raw = info.get('总市值', 0)
                float_raw = info.get('流通市值', 0)
                mcap = mcap_raw / 1e8 if mcap_raw else None
                float_cap = float_raw / 1e8 if float_raw else None
                
                # 股本信息（转换为股数）
                total_shares = info.get('总股本')
                float_shares = info.get('流通股')
                if total_shares:
                    total_shares = total_shares * 1e4  # 万股转股
                if float_shares:
                    float_shares = float_shares * 1e4
                
                result["share_stats"] = [{
                    "sharesOutstanding": total_shares,
                    "floatShares": float_shares,
                }]
            else:
                info = {}
                mcap = None
            
            # 2. 获取财务摘要（关键指标）
            try:
                fin_abstract = await asyncio.to_thread(
                    ak.stock_financial_abstract_ths, symbol=code, indicator="按报告期"
                )
                if not fin_abstract.empty:
                    # 取最新数据
                    latest = fin_abstract.iloc[-1]
                    
                    # 构建 metrics（与港股 AkShareFetcher 对齐）
                    pe = latest.get('市盈率')
                    pb = latest.get('市净率')
                    
                    result["metrics"] = [{
                        "marketCap": mcap,
                        "trailingPE": float(pe) if pe is not None else None,
                        "priceToBook": float(pb) if pb is not None else None,
                        "currency": "CNY",
                    }]
                    
                    # 构建 analysis 数据（与港股结构对齐）
                    analysis_record = {
                        "period_ending": str(latest.get('报告期', '')),
                        "ROE_YEARLY": float(latest.get('净资产收益率', 0)) / 100 if latest.get('净资产收益率') else None,
                        "OPERATE_INCOME_YOY": float(latest.get('营收同比', 0)) / 100 if latest.get('营收同比') else None,
                        "HOLDER_PROFIT_YOY": float(latest.get('净利润同比', 0)) / 100 if latest.get('净利润同比') else None,
                        "NET_PROFIT_RATIO": float(latest.get('净利率', 0)) / 100 if latest.get('净利率') else None,
                        "CURRENT_RATIO": float(latest.get('流动比率', 0)) if latest.get('流动比率') else None,
                    }
                    
                    # 根据报告期类型放入 annual 或 quarterly
                    report_date = str(latest.get('报告期', ''))
                    if report_date.endswith('12-31') or report_date.endswith('1231'):
                        result["a_analysis"] = [analysis_record]
                    else:
                        result["q_analysis"] = [analysis_record]
            except Exception as e:
                print(f"  [AkShareAshare] Warning: Failed to fetch financial abstract: {e}")
                # 即使失败也保留 metrics
                if mcap:
                    result["metrics"] = [{"marketCap": mcap, "currency": "CNY"}]
            
            # 3. 获取财务报表（利润表、资产负债表、现金流量表）
            try:
                # 利润表
                income_df = await asyncio.to_thread(
                    ak.stock_financial_report_sina, stock=code, symbol="利润表"
                )
                if not income_df.empty:
                    # 转换为标准格式
                    income_records = self._transform_financial_df(income_df, "income")
                    # 按年报/季报分组
                    for rec in income_records:
                        if rec.get("period_ending", "").endswith("12-31"):
                            result["a_income"].append(rec)
                        else:
                            result["q_income"].append(rec)
                    # 限制数量
                    result["a_income"] = result["a_income"][:limit_a]
                    result["q_income"] = result["q_income"][:limit_q]
            except Exception as e:
                print(f"  [AkShareAshare] Warning: Failed to fetch income statement: {e}")
            
            try:
                # 资产负债表
                balance_df = await asyncio.to_thread(
                    ak.stock_financial_report_sina, stock=code, symbol="资产负债表"
                )
                if not balance_df.empty:
                    balance_records = self._transform_financial_df(balance_df, "balance")
                    for rec in balance_records:
                        if rec.get("period_ending", "").endswith("12-31"):
                            result["a_balance"].append(rec)
                        else:
                            result["q_balance"].append(rec)
                    result["a_balance"] = result["a_balance"][:limit_a]
                    result["q_balance"] = result["q_balance"][:limit_q]
            except Exception as e:
                print(f"  [AkShareAshare] Warning: Failed to fetch balance sheet: {e}")
            
            try:
                # 现金流量表
                cash_df = await asyncio.to_thread(
                    ak.stock_financial_report_sina, stock=code, symbol="现金流量表"
                )
                if not cash_df.empty:
                    cash_records = self._transform_financial_df(cash_df, "cash")
                    for rec in cash_records:
                        if rec.get("period_ending", "").endswith("12-31"):
                            result["a_cash"].append(rec)
                        else:
                            result["q_cash"].append(rec)
                    result["a_cash"] = result["a_cash"][:limit_a]
                    result["q_cash"] = result["q_cash"][:limit_q]
            except Exception as e:
                print(f"  [AkShareAshare] Warning: Failed to fetch cash flow: {e}")
            
            # 4. 构建 profile（公司概况）
            result["profile"] = [{
                "name": info.get("股票名称") or info.get("股票简称"),
                "listingDate": info.get("上市时间"),
                "industry": info.get("所属行业") or info.get("行业"),
                "fiscalYearEnd": "12-31",  # A股通常为12月31日
            }]
            
        except Exception as e:
            print(f"  [AkShareAshare] Error fetching data for {code}: {e}")
        
        return result
    
    def _transform_financial_df(self, df: pd.DataFrame, stmt_type: str) -> List[Dict]:
        """将财务DataFrame转换为标准记录列表"""
        if df.empty:
            return []
        
        records = []
        # 假设第一列是报告期，其余是科目
        date_col = df.columns[0]
        
        for idx, row in df.iterrows():
            record = {"period_ending": str(row.get(date_col, ""))}
            
            # 根据报表类型映射关键字段（与港股/YFinance对齐）
            if stmt_type == "income":
                # 收入表字段映射
                field_mapping = {
                    "营业收入": "REV",
                    "营业总收入": "REV",
                    "净利润": "NI",
                    "归属于母公司股东的净利润": "NI",
                    "营业利润": "OI",
                    "EBIT": "OI",
                }
            elif stmt_type == "balance":
                # 资产负债表字段映射
                field_mapping = {
                    "资产总计": "ASSETS",
                    "负债合计": "LIAB",
                    "所有者权益合计": "EQUITY",
                    "股东权益合计": "EQUITY",
                    "流动资产合计": "C_ASSETS",
                    "流动负债合计": "C_LIAB",
                    "货币资金": "CASH",
                }
            else:  # cash
                # 现金流量表字段映射
                field_mapping = {
                    "经营活动产生的现金流量净额": "OCF",
                    "经营活动现金流量净额": "OCF",
                    "投资活动产生的现金流量净额": "ICF",
                    "筹资活动产生的现金流量净额": "FCF",
                    "现金及现金等价物净增加额": "NET_CASH",
                }
            
            # 尝试映射字段
            for cn_field, std_field in field_mapping.items():
                if cn_field in df.columns:
                    val = row.get(cn_field)
                    if val is not None and not pd.isna(val):
                        record[std_field] = float(val)
            
            # 保留所有原始字段
            for col in df.columns:
                if col != date_col and col not in record:
                    val = row.get(col)
                    if val is not None and not pd.isna(val):
                        record[col] = val
            
            records.append(record)
        
        # 按日期排序（最新的在前）
        records.sort(key=lambda x: x.get("period_ending", ""), reverse=True)
        return records


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
                        aggfunc="first",
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

        metrics, profile, shares = [], [], None
        try:
            m_df = await asyncio.to_thread(
                ak.stock_hk_financial_indicator_em, symbol=code
            )
            if not m_df.empty:
                r = {str(k).strip(): v for k, v in m_df.iloc[0].to_dict().items()}
                shares = r.get("已发行股本(股)")
                dy_raw = r.get("股息率TTM(%)")
                metrics = [
                    {
                        "marketCap": r.get("总市值(港元)"),
                        "trailingPE": r.get("市盈率"),
                        "priceToBook": r.get("市净率"),
                        "dividendYield": (
                            float(dy_raw) / 100 if dy_raw is not None else None
                        ),
                        "trailingEps": r.get("基本每股收益(元)"),
                        "bookValue": r.get("每股净资产(元)"),
                        "currency": "HKD",
                    }
                ]
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
            profile = [
                {
                    "name": pr.get("证券简称") or cr.get("公司名称"),
                    "listingDate": pr.get("上市日期"),
                    "industry": pr.get("板块") or cr.get("所属行业"),
                    "fiscalYearEnd": pr.get("年结日") or "12-31",
                    "website": cr.get("公司网址"),
                    "address1": cr.get("办公地址"),
                    "fullTimeEmployees": cr.get("员工人数"),
                    "longBusinessSummary": cr.get("公司介绍"),
                }
            ]
        except:
            pass

        return {
            "metrics": metrics,
            "profile": profile,
            "estimates": [],
            "share_stats": [{"sharesOutstanding": shares, "floatShares": None}],
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

        is_cum = any(symbol.upper().endswith(s) for s in [".HK", ".SH", ".SZ", ".SS"])
        is_hk = symbol.upper().endswith(".HK")

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
            # 🟡 A股模式：使用专门的A股AkShare获取器
            ak_ashare_fetcher = AkShareAshareFetcher(self)
            db = await ak_ashare_fetcher.fetch_all(
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
        for b in ["metrics", "profile", "estimates", "share_stats"]:
            pack.fundamentals[b] = db[b][0] if db.get(b) else None

        q_inc, a_inc = db.get("q_income", []), db.get("a_income", [])
        latest_is = q_inc[0] if q_inc else (a_inc[0] if a_inc else None)
        q_suffix = "_ytd" if is_cum else "_discrete"

        if latest_is:
            latest_d_raw = latest_is.get("period_ending")
            if latest_d_raw:
                anchor_date = pd.to_datetime(latest_d_raw)
            p_type = "quarterly" if q_inc and latest_is == q_inc[0] else "annual"
            all_bs, all_cf = (
                db.get("q_balance", []) + db.get("a_balance", []),
                db.get("q_cash", []) + db.get("a_cash", []),
            )
            cur_bs, cur_cf = (
                self._find_closest_strictly(all_bs, anchor_date),
                self._find_closest_strictly(all_cf, anchor_date),
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
            latest_ana = self._find_closest_strictly(analysis_pool, anchor_date)
            if latest_ana:
                print(
                    f"  [Alignment] Matched analysis indicators for date: {latest_ana.get('period_ending')}"
                )
            else:
                print(
                    f"  [Alignment] Warning: No matching indicators found for {anchor_date.strftime('%Y-%m-%d')}"
                )
            mcap_input = _get_num(pack.fundamentals.get("metrics"), "MCAP")
            if mcap_input is None and latest_price is not None:
                # 尝试用 (Price * Shares) 估算 MCAP
                shares = _get_num(pack.fundamentals.get("share_stats"), "SHARES")
                if shares and shares > 0:
                    mcap_input = latest_price * shares
                    print(
                        f"  [Fundamental] Estimated MCAP using Price ({latest_price}) * Shares ({shares})"
                    )
            if is_cum and symbol.upper().endswith(".HK") and mcap_input is not None:
                # 执行港股汇率对齐 (HKD -> RMB)
                fx_rate = await self._get_realtime_fx_rate()
                mcap_rmb = mcap_input * fx_rate
                print(
                    f"  [Currency] Real-time Aligned Market Cap to RMB: {mcap_input:,.0f} HKD -> {mcap_rmb:,.0f} RMB (Rate: {fx_rate:.4f})"
                )
                mcap_input = mcap_rmb
                metrics_obj = pack.fundamentals.get("metrics")
                if isinstance(metrics_obj, dict):
                    pack.fundamentals["metrics"]["market_cap_rmb"] = mcap_input
                    pack.fundamentals["metrics"]["fx_rate"] = fx_rate

            q_ana_pool = db.get("q_analysis", [])
            a_ana_pool = db.get("a_analysis", [])
            # 当前周期指标：动态根据 p_type 选池，并与 anchor_date 严格对齐
            current_ana_pool = q_ana_pool if p_type == "quarterly" else a_ana_pool
            latest_ana = self._find_closest_strictly(current_ana_pool, anchor_date)
            # 年度对比指标：固定从 a_ana_pool 选，并与 anchor_date 对齐
            latest_annual_ana = self._find_closest_strictly(a_ana_pool, anchor_date)
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

    def _find_closest_strictly(
        self, series: List[Dict], anchor_date: Optional[datetime], window: int = 15
    ) -> Optional[Dict]:
        if not series or not anchor_date:
            return None
        v = []
        for it in series:
            d_raw = it.get("period_ending")
            if d_raw:
                d = pd.to_datetime(d_raw)
            if d:
                diff = abs((d - anchor_date).days)
                if diff <= window:
                    v.append((diff, it))
        return sorted(v, key=lambda x: x[0])[0][1] if v else None

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
        except:
            return False, None

    async def _get_realtime_fx_rate(self) -> float:
        """从 AkShare (百度源) 获取实时 HKD/CNY 汇率"""
        try:
            # 百度源实时行情
            df = await asyncio.to_thread(ak.fx_quote_baidu, symbol="人民币")
            subset = df[df["名称"].str.contains("港元", na=False)]
            if not subset.empty:
                # 接口返回的是 CNY/HKD (1人民币兑多少港元)
                cny_to_hkd = float(subset.iloc[0]["最新价"])
                if cny_to_hkd > 0:
                    return 1.0 / cny_to_hkd
            return 0.90  # 如果没找到，返回合理默认值
        except Exception as e:
            print(f"  [Fundamental] FX fetch failed: {e}")
            return 0.90  # Fallback

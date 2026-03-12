"""
Helpers - 辅助函数模块
包含汇率获取、货币审计等工具函数
"""
from typing import Any, Dict, Optional
import asyncio
import akshare as ak  # type: ignore
from alphaflow.core.data_utils import MarketType
from alphaflow.core.mapping_keys.metrics import MetricsKey


# ==========================================
# 1. 汇率获取
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


# ==========================================
# 2. 货币错配审计
# ==========================================
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
            "If the currency is misaligned, a real-time fx_rate is given and because it is REALTIME FX rate. "
            "Do NOT apply the REALTIME FX rate to analyze historical (e.g. 2-year or 3-year) growth rates. "
        )
    }

    if not metrics:
        return audit_report

    # =========================================================
    # 第一层：元数据标签审计 (Metadata Audit) - 针对 AkShare/港股最准
    # 使用 MetricsKey 常量，享受强类型检测
    # =========================================================
    # 检查标准字段是否存在
    # MARKET_CAP: 市场本币市值（港股=港元）
    # HK_ONLY_MCAP: 仅 H 股部分市值
    has_mcap_hkd = MetricsKey.MARKET_CAP in metrics or MetricsKey.HK_ONLY_MCAP in metrics

    # EPS_BASIC: 基本每股收益 - 通常为人民币
    # BOOK_VALUE: 每股净资产 - 通常为人民币
    has_eps_cny = MetricsKey.EPS_BASIC in metrics
    has_bps_cny = MetricsKey.BOOK_VALUE in metrics
    # TOTAL_REVENUE: 营业总收入 - 通常不带单位，默认本币(CNY)

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
    # 使用 MetricsKey 常量，享受强类型检测
    # =========================================================
    market_cap = metrics.get(MetricsKey.MARKET_CAP)
    api_pe = metrics.get(MetricsKey.PE_RATIO)
    api_pb = metrics.get(MetricsKey.PRICE_TO_BOOK)
    
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
             # 信任数学因子的精确度
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
                    f"Mixed Units (HKD Price / CNY Earnings) without FX conversion."
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

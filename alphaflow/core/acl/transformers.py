"""
适配器 Transform 函数库 (内部模块)
====================================
统一契约: (val: Any, raw: Dict[str, Any]) -> Optional[Any]

设计哲学：
- 所有函数以下划线开头，表示内部调用，不对外暴露
- 单值清洗：使用第一个参数 val
- 跨字段计算（虚拟字段）：val 为 None，使用 raw 字典
- 不在 __init__.py 中导出，保持黑盒状态
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import pandas as pd


# ==========================================
# Insider Trading 过滤配置常量
# ==========================================

_INSIDER_WINDOW_DAYS = 180  # 时间窗口：180天
_INSIDER_MIN_VALUE_USD = 10000  # 金额门槛：$10,000

# 黑名单词（纯行政/被动行为）
_INSIDER_TRASH_KEYWORDS = {
    "tax", "withhold",           # 纯税务
    "gift", "donate", "donation", "bona fide",  # 纯赠与
    "transfer",                  # 纯转移
    "grant", "award",            # 纯奖励
}

# 被动行为关键词（Footnote 扫雷）
_INSIDER_PASSIVE_FOOTNOTES = {"without the reporting person's direction"}


# ==========================================
# 通用数据清理函数
# ==========================================

def clean_null_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    [通用清理] 移除 null/None/空字符串字段，保留 0 值
    
    Args:
        row: 单条数据字典
    
    Returns:
        清理后的字典（不包含 null、None、空字符串）
    
    Example:
        >>> clean_null_fields({"symbol": None, "amount": 0.91, "count": 0, "name": ""})
        {"amount": 0.91, "count": 0}
    """
    return {k: v for k, v in row.items() if v is not None and v != ""}


def clean_null_fields_batch(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    [批量清理] 对列表中的每条记录执行 null 字段清理
    
    Args:
        data: 数据列表
    
    Returns:
        清理后的列表
    """
    if not data:
        return data
    return [clean_null_fields(row) for row in data]


def _tx_calc_short_interest_change(val: Any, raw: Dict[str, Any]) -> Optional[float]:
    """
    计算空头变动率 (标准30天归一化版)
    解决了不同报告周期导致的信号强度不可比问题。
    
    Args:
        val: 未使用 (虚拟字段无直接映射)
        raw: 原始数据字典，需包含:
            - short_interest: 当前做空量
            - short_interest_prev_month: 上月做空量
            - date/period_ending: 当前日期
            - short_interest_prev_date: 上月日期
    
    Returns:
        归一化到30天的月度变化率，或 None (数据缺失/异常)
    """
    curr = raw.get("short_interest")
    prev = raw.get("short_interest_prev_month")
    d_curr_raw = raw.get("date") or raw.get("period_ending")
    d_prev_raw = raw.get("short_interest_prev_date")
    
    if all(v is not None for v in [curr, prev, d_curr_raw, d_prev_raw]):
        try:
            f_curr, f_prev = float(curr), float(prev)
            if f_prev <= 0:
                return None
            
            # 1. 计算原始变动
            raw_change = (f_curr / f_prev) - 1
            
            # 2. 计算天数差
            dt_curr = pd.to_datetime(d_curr_raw)
            dt_prev = pd.to_datetime(d_prev_raw)
            days_diff = (dt_curr - dt_prev).days
            
            # 防御：天数必须合理（通常为 10-40 天）
            if 5 < days_diff < 100:
                # 核心：归一化到标准 30 天月度变化率
                normalized_change = (raw_change / days_diff) * 30
                return round(normalized_change, 6)
                
            return round(raw_change, 6)  # 天数异常则降级返回原始值
        except Exception:
            return None
    return None


def _tx_normalize_pct(val: Any, raw: Dict[str, Any]) -> Optional[float]:
    """
    [Field-Level Transform] 归一化百分比数值 (如 15.5 -> 0.155)
    
    专为 Provider-Specific Transform 设计：
    - AkShare 返回 15.5 表示 15.5%
    - YFinance 部分字段也返回整数百分比
    
    Args:
        val: 原始数值（可能是 int, float, str）
        raw: 原始数据字典 (未使用，保持统一契约)
    
    Returns:
        归一化后的小数值，或 None (非法值)
    
    Example:
        >>> _tx_normalize_pct(15.5, {})
        0.155
        >>> _tx_normalize_pct("15.5%", {})
        0.155
        >>> _tx_normalize_pct(None, {})
        None
    """
    if val is None or str(val).strip() == "":
        return None
    try:
        # 支持 "15.5%" 格式，自动剥离 % 符号
        if isinstance(val, str) and '%' in val:
            val = val.replace('%', '')
        return round(float(val) / 100.0, 6)
    except (ValueError, TypeError):
        return None


def _tx_truncate_text(val: Any, raw: Dict[str, Any], max_len: int = 1000) -> Optional[str]:
    """
    通用文本截断器
    
    Args:
        val: 待截断的文本值
        raw: 原始数据字典 (未使用)
        max_len: 最大长度，默认 1000
    
    Returns:
        截断后的文本，或 None (非字符串类型)
    """
    if isinstance(val, str) and len(val) > max_len:
        return val[:max_len] + "..."
    return val


def _tx_extract_country(val: Any, raw: Dict[str, Any], max_len: int = 10) -> Optional[str]:
    """
    从地址中提取国家/地区 (截取前N个字符)
    
    Args:
        val: 地址文本
        raw: 原始数据字典 (未使用)
        max_len: 截取长度，默认 10
    
    Returns:
        截取后的地址片段，或 None (非字符串类型)
    """
    if isinstance(val, str):
        return val[:max_len]
    return val


def _tx_filter_insider_trading(raw: Dict[str, Any]) -> bool:
    """
    [Row-Level Filter] 宽网严筛版 - 过滤有效的内部交易记录
    
    判断标准：
    1. transaction_price > 0 (有真实的资金对价)
    2. 日期窗口：180 天内有效
    3. 金额门槛：交易金额 >= $10,000
    4. 排除黑名单词（税务、赠与、授予等）
    5. 排除行权成本支付（exercise price without open market）
    6. 排除被动行为（footnote 扫雷）
    
    Args:
        raw: 单条原始数据字典
    
    Returns:
        True 表示保留该记录，False 表示过滤掉
    """
    # 1. 日期窗口检查（优先检查，快速过滤过期数据）
    t_date_str = raw.get("transaction_date") or raw.get("filing_date")
    if t_date_str:
        try:
            t_date = datetime.strptime(str(t_date_str)[:10], "%Y-%m-%d")
            cutoff = datetime.now() - timedelta(days=_INSIDER_WINDOW_DAYS)
            if t_date < cutoff:
                return False
        except ValueError:
            pass  # 日期解析失败，继续后续检查
    
    # 2. 资金对价检查
    price = raw.get("transaction_price")
    if price is None:
        return False
    try:
        price_val = float(price)
        if price_val <= 0:
            return False
    except (ValueError, TypeError):
        return False
    
    # 3. 金额门槛检查
    try:
        shares = float(raw.get("securities_transacted") or 0)
        total_value = price_val * shares
        if total_value < _INSIDER_MIN_VALUE_USD:
            return False
    except (ValueError, TypeError):
        return False
    
    # 4. 黑名单词检查
    t_type = str(raw.get("transaction_type", "")).lower()
    if any(bad in t_type for bad in _INSIDER_TRASH_KEYWORDS):
        return False
    
    # 5. Exercise 特殊处理：行权成本支付过滤
    if "exercise price" in t_type and "open market" not in t_type:
        return False
    
    # 6. Footnote 扫雷：排除被动行为
    footnote = str(raw.get("footnote", "")).lower()
    if any(passive in footnote for passive in _INSIDER_PASSIVE_FOOTNOTES):
        return False
    
    return True


def _tx_format_date(val: Any, raw: Dict[str, Any]) -> Optional[str]:
    """
    [Field-Level Transform] 通用日期格式化
    将任意合法日期格式转换为 YYYY-MM-DD
    """
    if val is None or str(val).strip() == "":
        return None
    try:
        return pd.to_datetime(val).strftime("%Y-%m-%d")
    except Exception:
        return str(val)  # 解析失败则保留原样，由 Pydantic 决定生死


def _tx_detect_cny_hkd_mismatch(val: Any, raw: Dict[str, Any]) -> bool:
    """
    [Row-Level Feature] 嗅探港股的计价货币错配特征
    利用原始未被标准化的键名，侦测是否同时存在港元市值与人民币财报。
    """
    # 嗅探市值计价 (HKD)
    has_hkd_cap = "总市值(港元)" in raw or "港股市值(港元)" in raw
    
    # 嗅探财报计价 (CNY)
    has_cny_val = "基本每股收益(元)" in raw or "每股净资产(元)" in raw
    
    return has_hkd_cap and has_cny_val


def _tx_extract_float(val: Any, raw: Dict[str, Any]) -> Optional[float]:
    """
    [Field-Level Transform] 宽容型浮点提取（N/A 安全）

    YFinance 的 earnings_calendar 用字符串 "N/A" 表示缺失值。
    此算子统一将其转为 None，有效数值转为 float。
    """
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "N/A", "n/a", "None", "null", "-", "--"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _tx_extract_dividend_amount(val: Any, raw: Dict[str, Any]) -> Optional[float]:
    """
    [Field-Level Transform] 港股分红方案文本 → 每股金额（宁缺毋滥）

    支持格式：
      '每股派港币5.3元'     → 5.3
      '每10股派3元'         → 0.3
      '每股派末期息港币1.2元及特别息港币0.5元' → 1.7
    """
    text = val if isinstance(val, str) else None
    if not text:
        return None
    # 处理"每N股"的情况
    per_share = 1
    m_per = re.search(r"每(\d+)股", text)
    if m_per:
        per_share = int(m_per.group(1))
    # 提取所有金额并求和（覆盖"末期息+特别息"场景）
    amounts = re.findall(r"(\d+\.?\d*)\s*元", text)
    if not amounts:
        return None
    total = sum(float(a) for a in amounts)
    return round(total / per_share, 4) if per_share > 0 else None

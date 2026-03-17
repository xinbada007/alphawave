"""
金融数学核心库 (Financial Mathematics Core)
=========================================
纯粹的金融计算逻辑，不依赖 ResearchPack 或具体数据结构。
仅处理 List[Dict], Dict, float 等基础类型。

本模块从以下位置提取：
- fundamental.py: calc_ttm_stitch
- technicals.py: _get_annual_multiplier (转为 get_annual_multiplier)
- technicals.py: _calc_yoy_physical (转为 calculate_growth_yoy)
- data_utils.py: get_fcf_raw (业务逻辑)
"""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import pandas as pd

from alphaflow.core.utils.data_utils import (
    MetaKey,
    ReportPeriod,
    find_closest_strictly, 
    get_field_value,
    detect_report_type,
)
from alphaflow.core.keys import Key


# ==========================================
# 1. TTM 计算 (滚动12个月)
# ==========================================

def calc_ttm_stitch(
    q_series: List[Dict], 
    a_series: List[Dict], 
    field_func: Callable, 
    is_cumulative: bool
) -> Optional[float]:
    """
    健壮的 TTM 计算 (支持任意年结日、支持离散/累积混合)
    
    Args:
        q_series: 季度/报告期数据列表
        a_series: 年度数据列表
        field_func: 字段提取函数，接收 Dict 返回 Optional[float]
        is_cumulative: 是否为累积制 (A股/港股=True, 美股=False)
    
    Returns:
        TTM 值，如果无法计算则返回 None
    
    离散制逻辑: 严格寻找过去连续的4个季度 (Q, Q-1, Q-2, Q-3)
    累积制逻辑: TTM = Current_YTD + (Last_Annual - Last_Year_Same_Period_YTD)
    """
    if not q_series:
        return None

    # 1. 获取当前报告期 (Latest Period)
    cur_item = q_series[0]
    cur_val = field_func(cur_item)
    if cur_val is None:
        return None

    cur_date_raw = cur_item.get(MetaKey.PERIOD_ENDING)
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
            # 在 q_series 里找最接近 exp_date 的报告
            # 注意: 传入 window=20
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
        d_raw = item.get(MetaKey.PERIOD_ENDING)
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
    last_same_period_item = find_closest_strictly(pool, target_date, window=20)
    
    if not last_same_period_item:
        # 🌟 修复：强校验 cur_val 必须是年报级别才能直接返回
        cur_type = detect_report_type(cur_item)
        is_annual_data = cur_type == ReportPeriod.ANNUAL
        
        if is_annual_data:
            return cur_val
        return None

    last_same_period_val = field_func(last_same_period_item)
    if last_same_period_val is None:
        return None

    # 3. 执行 TTM 拼接公式
    return cur_val + (last_annual_val - last_same_period_val)


# ==========================================
# 2. 年化乘数推断
# ==========================================

def get_annual_multiplier(
    latest_is: Dict[str, Any],
    latest_ana: Optional[Dict[str, Any]],
    p_type: str,
    is_cumulative: bool
) -> Optional[float]:
    """
    智能推断年化乘数
    
    Args:
        latest_is: 利润表记录 (季度或年度)
        latest_ana: 分析指标记录 (可选，用于获取 DATE_TYPE_CODE)
        p_type: 报告类型 ("quarterly" 或 "annual")
        is_cumulative: 是否为累积制
    
    Returns:
        年化乘数，如果无法推断则返回 None
    
    策略:
    - 年度报告: 返回 1.0
    - 离散制: 返回 4.0
    - 累积制: 
      - 优先使用 DATE_TYPE_CODE (003=Q1, 002=H1, 004=Q3, 001=年度)
      - 兜底: 物理天数计算 (12.0 / 月份数)
    """
    # 年度报告：不需要年化
    if p_type == ReportPeriod.ANNUAL.value:
        return 1.0
    
    # 离散制：精确已知
    if not is_cumulative:
        return 4.0

    # ==================== 累积制 ====================
    
    # 优先级 1: DATE_TYPE_CODE
    date_type = latest_is.get(MetaKey.DATE_TYPE_CODE) or (latest_ana or {}).get(MetaKey.DATE_TYPE_CODE)
    if date_type:
        if date_type == "003": return 12.0 / 3   # Q1
        if date_type == "002": return 12.0 / 6   # H1
        if date_type == "004": return 12.0 / 9   # Q3
        if date_type == "001": return 1.0        # 年度
    
    # 优先级 2: START_DATE 物理天数计算
    s_raw = latest_is.get(MetaKey.START_DATE)
    e_raw = latest_is.get(MetaKey.REPORT_DATE) or latest_is.get(MetaKey.PERIOD_ENDING)
    if s_raw and e_raw:
        try:
            s_date = pd.to_datetime(s_raw)
            e_date = pd.to_datetime(e_raw)
            days = (e_date - s_date).days
            
            # 防御：天数必须在合理范围
            if 30 <= days <= 400:
                months = round(days / 30.0)
                if months > 0:
                    return 12.0 / months
        except Exception:
            pass
    
    return None


# ==========================================
# 3. 同比增长率计算 (物理日期)
# ==========================================

def calculate_growth_yoy(
    series: List[Dict],
    field: str,
    is_quarterly: bool,
    get_field_value_func: Callable[[Dict, str], Optional[float]]
) -> Optional[float]:
    """
    基于物理日期的同比增长率计算
    
    Args:
        series: 历史数据列表 (按日期降序排列，最新在前)
        field: 字段名 (如 "REV", "NI")
        is_quarterly: 是否为季度数据 (True=需匹配月份, False=仅匹配年份)
        get_field_value_func: 字段提取函数
    
    Returns:
        同比增长率 (如 0.15 表示 15%)，无法计算则返回 None
    
    逻辑:
    1. 取最新一期 (cur_val, cur_date)
    2. 在历史数据中寻找去年同月/同日的数据
    3. 计算: (cur_val - prev_val) / abs(prev_val)
    """
    if len(series) < 2:
        return None
    
    cur_val = get_field_value_func(series[0], field)
    cur_date_raw = series[0].get(MetaKey.PERIOD_ENDING)
    
    if cur_val is None or not cur_date_raw:
        return None
    
    cur_date = pd.to_datetime(cur_date_raw)
    target_year = cur_date.year - 1
    
    for prev in series[1:]:
        prev_date_raw = prev.get(MetaKey.PERIOD_ENDING)
        if not prev_date_raw:
            continue
        
        prev_date = pd.to_datetime(prev_date_raw)
        match = (prev_date.year == target_year)
        
        # 季度数据需要匹配月份
        if is_quarterly:
            match = match and (prev_date.month == cur_date.month)
        
        if match:
            prev_val = get_field_value_func(prev, field)
            if prev_val:
                return round((cur_val - prev_val) / abs(prev_val), 4)
    
    return None


# ==========================================
# 4. 自由现金流计算 (业务逻辑)
# ==========================================

def get_fcf_raw(item: Optional[Dict]) -> Optional[float]:
    """
    物理推导自由现金流 (FCF = OCF - |CAPEX|)
    
    Args:
        item: 现金流量表记录
    
    Returns:
        FCF 值，未找到返回 None
    """
    if not item:
        return None
    
    # 先尝试直接获取 FCF
    f = get_field_value(item, Key.cash.FREE_CASH_FLOW)
    if f is not None:
        return f
    
    # 如果没有，尝试通过 OCF - CAPEX 计算
    o = get_field_value(item, Key.cash.OPERATING_CASH_FLOW)
    c = get_field_value(item, Key.cash.CAPITAL_EXPENDITURE)
    if o is not None and c is not None:
        return o - abs(c)
    
    return None

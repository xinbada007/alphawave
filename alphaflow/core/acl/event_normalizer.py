"""
事件流字段标准化器 (Event Stream Normalizer)
==============================================
独立于 BaseFetcher 的 Provider 词汇翻译层。

职责：
- 将各 Provider 返回的中文/非标字段名统一为标准英文键
- 从港股分红方案文本中提取数字金额
- 提取并标准化日期字段 → period_ending

设计原则：
1. 声明式映射（只加映射表行，无需改代码逻辑）
2. 宁缺毋滥：无法解析的文本返回 None
3. 与 BaseFetcher 解耦：BaseFetcher Track 2 只调用一行
   `normalize_event_fields(raw_data)`
"""
import re
from typing import Dict, List, Optional

import pandas as pd


# ==========================================
# 声明式字段别名映射表
# old_key → new_key（仅当 new_key 不存在时才写入）
# ==========================================
FIELD_ALIASES: Dict[str, str] = {
    # --- dividends (港股 AkShare) ---
    "除净日": "ex_dividend_date",
    "最新公告日期": "announce_date",
    "财政年度": "fiscal_year",
    "分配类型": "dividend_type",
    "分红方案": "dividend_plan",
    "截至过户日": "record_date",
    "发放日": "payment_date",
    # --- dividends (OBB 别名) ---
    "cash_amount": "amount",
}

# ==========================================
# 日期候选字段（按优先级排列）
# ==========================================
DATE_CANDIDATES = [
    "ex_dividend_date",
    "date",
    "transaction_date",
    "filing_date",
    "REPORT_DATE",
]


# ==========================================
# 文本提取器
# ==========================================
def _extract_dividend_amount(text: str) -> Optional[float]:
    """
    从港股分红方案文本中提取每股金额（宁缺毋滥）

    支持格式：
      '每股派港币5.3元'     → 5.3
      '每10股派3元'         → 0.3
      '每股派末期息港币1.2元及特别息港币0.5元' → 1.7
    """
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


# ==========================================
# 主入口：单行委托
# ==========================================
def normalize_event_fields(raw_data: List[Dict]) -> List[Dict]:
    """
    事件流字段标准化（BaseFetcher Track 2 的单行委托入口）

    1. 字段别名映射（Provider 词汇翻译）
    2. 文本提取（港股分红方案 → 数字 amount）
    3. 日期提取 → period_ending
    """
    for item in raw_data:
        # Step 1: 字段别名标准化
        for old_key, new_key in FIELD_ALIASES.items():
            if old_key in item and new_key not in item:
                item[new_key] = item.pop(old_key)

        # Step 2: 港股分红方案文本提取
        plan_text = item.get("dividend_plan")
        if plan_text and isinstance(plan_text, str) and "amount" not in item:
            extracted = _extract_dividend_amount(plan_text)
            if extracted is not None:
                item["amount"] = extracted

        # Step 3: 日期提取 → period_ending
        for candidate in DATE_CANDIDATES:
            date_val = item.get(candidate)
            if date_val:
                try:
                    item["period_ending"] = pd.to_datetime(date_val).strftime("%Y-%m-%d")
                except Exception:
                    pass
                break

    return raw_data

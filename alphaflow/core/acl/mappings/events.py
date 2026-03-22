"""
事件流映射表 (Event Stream Mapping)
====================================
Track 2 专属的字段映射字典。

与 income_statement.py / balance_sheet.py 同级同范式：
- 标准键 → { provider_id: aliases | {aliases, transform} }
- 从 transformers.py 导入 transform 函子

注意事项：
- Track 2 是"原地翻译"（保留未映射字段），不是 Track 1 的"白名单重建"
- 这里只定义字典，执行引擎在 core_adapter.py 的 normalize_events() 中
- 标准键使用小写 snake_case（非 Track 1 的大写），因为 Track 2 无 Pydantic Record 约束
"""
from typing import Any, Dict

from alphaflow.core.acl.transformers import _tx_format_date, _tx_extract_dividend_amount


# ==========================================
# 事件流映射注册表 (按 provider_id 隔离)
#
# 格式与 Track 1 完全一致：
#   "standard_key": {
#       "provider_id": ["alias1", "alias2"]          ← 纯别名
#       "provider_id": {"aliases": [...], "transform": fn}  ← 别名 + 变换
#   }
# ==========================================
EVENT_STREAM_MAPPING: Dict[str, Dict[str, Any]] = {
    # ===== dividends 事件流 =====
    "ex_dividend_date": {
        "akshare": {
            "aliases": ["除净日"],
            "transform": _tx_format_date,
        },
        "obb": ["ex_dividend_date"],
    },
    "announce_date": {
        "akshare": {
            "aliases": ["最新公告日期"],
            "transform": _tx_format_date,
        },
        "obb": ["announce_date"],
    },
    "fiscal_year": {
        "akshare": ["财政年度"],
        "obb": ["fiscal_year"],
    },
    "dividend_type": {
        "akshare": ["分配类型"],
        "obb": ["dividend_type"],
    },
    "amount": {
        "akshare": {
            "aliases": ["分红方案"],
            "transform": _tx_extract_dividend_amount,
        },
        "obb": ["cash_amount", "amount"],
    },
    "record_date": {
        "akshare": ["截至过户日"],
        "obb": ["record_date"],
    },
    "payment_date": {
        "akshare": {
            "aliases": ["发放日"],
            "transform": _tx_format_date,
        },
        "obb": ["payment_date"],
    },
}

# 日期字段候选列表（用于 period_ending 提取）
DATE_CANDIDATES = [
    "ex_dividend_date",
    "date",
    "transaction_date",
    "filing_date",
    "REPORT_DATE",
]

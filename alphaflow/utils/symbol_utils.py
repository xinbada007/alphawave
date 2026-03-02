"""
Symbol Utilities - A股/港股代码处理工具

提供A股和港股代码的清洗、标准化功能
"""

from typing import Optional


def clean_a_share_symbol(symbol: str) -> str:
    """
    清洗 A股代码格式
    
    输入格式示例:
    - "000001.SZ" -> "000001" (平安银行)
    - "600519.SH" -> "600519" (贵州茅台)
    - "000001"    -> "000001" (保持不变)
    - "600519"    -> "600519" (保持不变)
    
    Returns:
        纯数字代码（用于 AkShare API）
    
    Raises:
        ValueError: 无效的A股代码
    """
    if not symbol:
        raise ValueError("Empty symbol")
    
    # 移除 .SH / .SZ 后缀
    if "." in symbol:
        symbol = symbol.split(".")[0]
    
    # 验证是否为纯数字
    if not symbol.isdigit():
        raise ValueError(f"Invalid A-share symbol: {symbol}")
    
    return symbol


def get_exchange_suffix(symbol: str) -> str:
    """
    根据股票代码获取交易所后缀
    
    规则:
    - 6开头 -> SH (上海证券交易所)
    - 0/3开头 -> SZ (深圳证券交易所)
    
    Args:
        symbol: 股票代码（纯数字或带后缀）
    
    Returns:
        "SH" 或 "SZ"
    """
    # 先清洗
    code = clean_a_share_symbol(symbol)
    
    if code.startswith("6"):
        return "SH"
    else:  # 0, 3 开头
        return "SZ"


def is_a_share(symbol: str) -> bool:
    """
    判断是否为 A股代码
    
    Args:
        symbol: 股票代码
    
    Returns:
        True if A股代码
    """
    try:
        code = clean_a_share_symbol(symbol)
        # A股代码通常是 6 位数字
        return len(code) == 6 and code.isdigit()
    except ValueError:
        return False


def is_hk_share(symbol: str) -> bool:
    """
    判断是否为港股代码
    
    Args:
        symbol: 股票代码
    
    Returns:
        True if 港股代码
    """
    # 港股代码格式: XXXX.HK 或 XXXX
    if "." in symbol:
        suffix = symbol.split(".")[1].upper()
        return suffix == "HK"
    
    # 纯数字可能是港股（4-5位）
    code = symbol.strip("0")
    return len(code) >= 4 and len(code) <= 5 and code.isdigit()


def normalize_symbol(symbol: str, market: Optional[str] = None) -> str:
    """
    标准化股票代码
    
    Args:
        symbol: 原始代码
        market: 市场 (cn/us/hk/auto)
    
    Returns:
        标准化后的代码
    """
    if market == "cn" or market == "auto":
        if is_a_share(symbol):
            code = clean_a_share_symbol(symbol)
            suffix = get_exchange_suffix(code)
            return f"{code}.{suffix}"
    
    if market == "hk" or market == "auto":
        if is_hk_share(symbol):
            if "." in symbol:
                return symbol.upper()
            # 添加 .HK 后缀
            code = symbol.zfill(5)
            return f"{code}.HK"
    
    # 美股或其他 - 保持原样
    return symbol


# 导出
__all__ = [
    "clean_a_share_symbol",
    "get_exchange_suffix", 
    "is_a_share",
    "is_hk_share",
    "normalize_symbol",
]

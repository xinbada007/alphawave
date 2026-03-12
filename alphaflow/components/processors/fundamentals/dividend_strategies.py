"""
Dividend 股息提取策略 (Dividend Strategies)
===========================================
处理不同市场的股息数据 - 双轨制架构：
- USDividendStrategy: 美股股息策略 (结构化计算 + 近期防抖)
- HKDividendStrategy: 港股股息策略 (非结构化文本时间线)
- CNDividendStrategy: A股股息策略 (继承港股逻辑)

设计原则：
1. 美股：量化计算 + 绝对值防抖
2. 港股/A股：AI 原生文本时间线，把理解和定性工作交还给 LLM
3. 纯 Python 实现：0 Pandas 依赖
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict

from alphaflow.components.processors.fundamentals.base_strategy import (
    BaseExtractorStrategy,
    standardize_field,
)
from alphaflow.components.processors.fundamentals.fundamental_keys import (
    DividendKey,
    DIVIDEND_EXTRACTOR_CHAINS,
)


# ==========================================
# 1. 美股股息策略 (结构化计算 + 近期防抖)
# ==========================================
class USDividendStrategy(BaseExtractorStrategy):
    """
    美股股息处理策略
    
    适用市场：US
    数据来源：OpenBB (obb.equity.fundamental.dividends)
    
    处理逻辑：
    1. 按 ex_dividend_date 的年份聚合
    2. 计算 3 年 CAGR
    3. 判断连续增长年数
    4. 提取近 5 年绝对派息金额（防抖，提供语境）
    """
    
    def extract(self, raw_data: Any) -> Dict[str, Any]:
        if not raw_data or not isinstance(raw_data, list):
            return {DividendKey.STATUS: "NO_DATA"}
        
        # ============================================================
        # ⚠️ 金融假设声明 (Financial Assumption):
        # 本算法强依赖于上游 API (OpenBB/Yahoo) 提供的数据是：
        # 1. 前复权 (Split-Adjusted)：已自动处理拆股/分红等除权因素
        # 2. 剔除特别股息 (Special Dividend)：不计入常规股息计算
        # 如果发生未复权的拆股 (如 1拆4)，次年每股股息会看似暴跌 75%，
        # 此时 CAGR 计算会失真。主流美股 API 默认提供复权数据。
        # ============================================================
        
        # 按年份聚合股息
        annual_divs: Dict[int, float] = {}
        
        for item in raw_data:
            if not isinstance(item, dict):
                continue
            
            # 提取金额
            amount = standardize_field(item, "amount", DIVIDEND_EXTRACTOR_CHAINS)
            if amount is None:
                continue
            
            try:
                amount = float(amount)
                if amount <= 0:
                    continue  # 过滤退市/异常的0股息记录
            except (ValueError, TypeError):
                continue
            
            # 提取日期
            date_val = standardize_field(item, "date", DIVIDEND_EXTRACTOR_CHAINS)
            if not date_val:
                continue
            
            # 提取年份
            try:
                year = int(str(date_val)[:4])
            except (ValueError, TypeError):
                continue
            
            # 累加年度股息
            annual_divs[year] = annual_divs.get(year, 0.0) + amount
        
        if not annual_divs:
            return {DividendKey.STATUS: "NO_DIVIDEND_HISTORY"}
        
        # 按年份排序
        sorted_years = sorted(annual_divs.keys())
        current_year = datetime.now().year
        
        # 核心修复：剔除当前尚未走完的年份，避免数值暴跌假象
        valid_years = [y for y in sorted_years if y < current_year]
        
        # 如果连两年都没有，就回退到使用包含今年的数据（兜底）
        years_to_use = valid_years if len(valid_years) >= 2 else sorted_years

        # 计算 CAGR
        cagr = None
        if len(years_to_use) >= 2:
            latest_year = years_to_use[-1]
            # 找 3 年前，或者尽可能早的年份
            earliest_year = years_to_use[-4] if len(years_to_use) >= 4 else years_to_use[0]
            
            if latest_year > earliest_year and annual_divs[earliest_year] > 0:
                # 修复可能出现的微小除零或负数次幂异常
                ratio = annual_divs[latest_year] / annual_divs[earliest_year]
                cagr = (ratio ** (1 / (latest_year - earliest_year))) - 1
                cagr = round(cagr, 4)
        
        # 计算连续增长年数
        consecutive_years = 0
        for i in range(len(years_to_use) - 1, 0, -1):
            if annual_divs[years_to_use[i]] > annual_divs[years_to_use[i - 1]]:
                consecutive_years += 1
            else:
                break
        
        # 提取近 5 年绝对金额 (防抖，提供语境)
        recent_years = sorted_years[-5:] if len(sorted_years) >= 5 else sorted_years
        recent_payout = {str(y): round(annual_divs[y], 4) for y in reversed(recent_years)}
        
        return {
            DividendKey.DIVIDEND_CAGR: cagr,
            DividendKey.CONSECUTIVE_YEARS: consecutive_years,
            DividendKey.RECENT_PAYOUT: recent_payout,
            DividendKey.STATUS: "ACTIVE" if cagr is not None else "STABLE"
        }


# ==========================================
# 2. 港股股息策略 (非结构化文本：AI 原生时间线)
# ==========================================
class HKDividendStrategy(BaseExtractorStrategy):
    """
    港股股息处理策略
    
    适用市场：HK
    数据来源：AkShare (stock_hk_dividend_payout_em)
    
    处理逻辑：
    1. 废弃脆弱的正则硬算
    2. 按年份聚合公告文本
    3. 生成最近 5 年的 recent_timeline 字典
    4. 把理解和定性工作交还给 LLM
    """
    
    def extract(self, raw_data: Any) -> Dict[str, Any]:
        if not raw_data or not isinstance(raw_data, list):
            return {DividendKey.STATUS: "NO_DATA"}
        
        timeline = defaultdict(list)
        
        # 1. 提取年份与文案
        for item in raw_data:
            if not isinstance(item, dict):
                continue
            
            year_str = item.get("fiscal_year") or item.get("ex_dividend_date", "")
            if not year_str:
                continue
            
            try:
                year = int(str(year_str)[:4])
            except ValueError:
                continue
            
            div_type = item.get("dividend_type", "分红")
            plan = str(item.get("dividend_plan", "")).strip()
            
            if plan and plan != "无":
                timeline[year].append(f"{div_type}: {plan}")
        
        if not timeline:
            return {DividendKey.STATUS: "NO_DIVIDEND_HISTORY"}
        
        # 2. 截取最近 5 年历史
        sorted_years = sorted(timeline.keys(), reverse=True)
        recent_years = sorted_years[:5]
        recent_timeline = {str(y): timeline[y] for y in recent_years}
        
        return {
            DividendKey.STATUS: "RECENT_DIVIDENDS_FOUND",
            DividendKey.RECENT_TIMELINE: recent_timeline
        }


# ==========================================
# 3. A股股息策略 (继承港股逻辑)
# ==========================================
class CNDividendStrategy(HKDividendStrategy):
    """
    A股股息处理策略
    
    适用市场：CN
    数据来源：AkShare
    
    A股股息同为非结构化中文公告，直接复用港股时间线聚合逻辑。
    把理解和定性工作交还给 LLM。
    """
    pass


# ==========================================
# 4. 便捷工厂函数
# ==========================================
def get_dividend_strategy(market: str) -> BaseExtractorStrategy:
    """
    获取对应市场的股息策略实例
    
    Args:
        market: 市场类型字符串 ("us", "hk", "cn")
    
    Returns:
        对应的策略实例
    """
    strategies = {
        "us": USDividendStrategy(),
        "hk": HKDividendStrategy(),
        "cn": CNDividendStrategy(),
    }
    return strategies.get(market.lower(), USDividendStrategy())

"""
DividendAnalyzer 极简分红分析器
================================
闭环漏洞 4：被注销的幽灵领域

设计原则：
1. 纯函数实现，0 外部依赖
2. 防御性编程，静默失败
3. 输出注入 distilled_features.dividend_insights
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from alphaflow.core.schema.models import DividendFeature


class DividendAnalyzer:
    """
    分红数据极简分析器
    
    输入：pack.fundamentals.get("dividends_history", [])
    输出：DividendFeature 结构体
    """
    
    @staticmethod
    def analyze(pack) -> DividendFeature:
        """
        分析分红历史数据，返回结构化特征
        
        Args:
            pack: ResearchPack 实例
            
        Returns:
            DividendFeature 包含 dividend_status, dividend_cagr, consecutive_years 等字段
        """
        div_data = pack.fundamentals.get("dividends_history", []) if pack.fundamentals else []
        
        if not div_data or not isinstance(div_data, list):
            return DividendFeature(
                dividend_status="NO_DATA",
                dividend_cagr=None,
                consecutive_years=0,
                recent_payout={},
                recent_timeline={}
            )
        
        try:
            # 按年份聚合股息
            annual_divs: Dict[int, float] = {}
            
            for item in div_data:
                if not isinstance(item, dict):
                    continue
                
                # 提取金额
                amount = item.get("amount") or item.get("dividend") or item.get("cash_amount")
                if amount is None:
                    continue
                
                try:
                    amount = float(amount)
                    if amount <= 0:
                        continue
                except (ValueError, TypeError):
                    continue
                
                # 提取日期
                date_val = item.get("date") or item.get("ex_dividend_date") or item.get("fiscal_year")
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
                return DividendFeature(
                    dividend_status="NO_VALID_DATA",
                    dividend_cagr=None,
                    consecutive_years=0,
                    recent_payout={},
                    recent_timeline={}
                )
            
            # 按年份排序
            sorted_years = sorted(annual_divs.keys())
            current_year = datetime.now().year
            
            # 剔除当前尚未走完的年份
            valid_years = [y for y in sorted_years if y < current_year]
            years_to_use = valid_years if len(valid_years) >= 2 else sorted_years
            
            # 计算 CAGR
            cagr = None
            if len(years_to_use) >= 2:
                latest_year = years_to_use[-1]
                earliest_year = years_to_use[-4] if len(years_to_use) >= 4 else years_to_use[0]
                
                if latest_year > earliest_year and annual_divs[earliest_year] > 0:
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
            
            # 提取近 5 年绝对金额
            recent_years = sorted_years[-5:] if len(sorted_years) >= 5 else sorted_years
            recent_payout = {str(y): round(annual_divs[y], 4) for y in reversed(recent_years)}
            
            return DividendFeature(
                dividend_status="ACTIVE" if cagr is not None else "STABLE",
                dividend_cagr=cagr,
                consecutive_years=consecutive_years,
                recent_payout=recent_payout,
                recent_timeline={}
            )
            
        except Exception as e:
            # 静默失败，不中断 Pipeline
            print(f"  [DividendAnalyzer] ⚠️ Error analyzing dividends: {e}")
            return DividendFeature(
                dividend_status="ERROR",
                dividend_cagr=None,
                consecutive_years=0,
                recent_payout={},
                recent_timeline={}
            )


# 便捷函数
def analyze_dividends(pack) -> DividendFeature:
    """快速分析分红数据"""
    return DividendAnalyzer.analyze(pack)

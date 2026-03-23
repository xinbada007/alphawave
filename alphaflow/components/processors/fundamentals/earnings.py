"""
EarningsAnalyzer - 财报超预期时序聚合器
========================================
Processor 层的纯业务分析器，不含任何 Provider 词汇。

输入：pack.fundamentals["earnings_calendar"]（已被 Track 2 ACL 标准化）
输出：EarningsFeature（强类型 Pydantic 模型）

遵循 .clinerules §VIII 检验科定位：只输出事实，不做定性判断。
"""
from datetime import datetime
from typing import List, Dict, Any, Optional

from alphaflow.core.schema import ResearchPack
from alphaflow.core.schema.models import EarningsFeature


class EarningsAnalyzer:
    """财报超预期降噪器 — 从时序记录中提炼 LLM 可消费的高维信号"""

    @staticmethod
    def analyze(pack: ResearchPack) -> EarningsFeature:
        raw: List[Dict[str, Any]] = pack.fundamentals.get("earnings_calendar", []) or []
        if not raw:
            return EarningsFeature(earnings_status="NO_DATA")

        today_str = datetime.now().strftime("%Y-%m-%d")

        # 分离：历史已报告 vs 未来预估
        reported: List[Dict[str, Any]] = []
        next_report_date: Optional[str] = None

        for item in raw:
            eps_est = item.get("eps_estimate")
            eps_rep = item.get("reported_eps")
            report_date = item.get("report_date") or item.get("period_ending")

            # 未来财报（有预估但无实际 EPS）
            if eps_est is not None and eps_rep is None:
                if report_date and report_date > today_str:
                    if next_report_date is None or report_date < next_report_date:
                        next_report_date = report_date
                continue

            # 历史已报告（必须同时有预估和实际）
            if eps_est is not None and eps_rep is not None:
                reported.append(item)

        if not reported:
            return EarningsFeature(
                earnings_status="NO_DATA",
                next_report_date=next_report_date,
            )

        # 按日期降序排列（最近的在前）
        reported.sort(
            key=lambda x: x.get("report_date") or x.get("period_ending") or "",
            reverse=True,
        )

        total = len(reported)
        beat_count = 0
        surprise_sum = 0.0
        surprise_count = 0

        for item in reported:
            eps_rep = item["reported_eps"]
            eps_est = item["eps_estimate"]
            if eps_rep > eps_est:
                beat_count += 1

            # surprise_pct 已由 ACL 标准化为小数形式 (< 1)
            surprise = item.get("surprise_pct")
            if surprise is not None:
                surprise_sum += surprise
                surprise_count += 1

        # 连续超预期（从最近一期往前数）
        consecutive = 0
        for item in reported:
            if item["reported_eps"] > item["eps_estimate"]:
                consecutive += 1
            else:
                break

        beat_rate = round(beat_count / total, 4) if total > 0 else None
        avg_surprise = round(surprise_sum / surprise_count, 4) if surprise_count > 0 else None

        return EarningsFeature(
            earnings_status="ACTIVE",
            total_reports=total,
            beat_count=beat_count,
            beat_rate_pct=beat_rate,
            avg_surprise_pct=avg_surprise,
            consecutive_beats=consecutive,
            next_report_date=next_report_date,
        )

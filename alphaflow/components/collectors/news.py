#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
news.py — 消息面采集器（框架集成版）

职责：聚合新闻、公告、市场资讯、机构评级、舆情情绪等非结构化数据，
     进行关键词情感分析，生成消息概述与综合分析报告并输出到文件。

架构定位：alphaflow pipeline 中的 NewsCollector 组件
数据源　：AkShare API（8 个独立模块，局部失效静默跳过）
输出　　：
  - ResearchPack.news            → 个股新闻列表 (List[Dict])
  - ResearchPack.extra["news_*"] → 情感分析、概述、报告路径等
  - 本地文件 reports/news_<symbol>_<ts>.txt
"""

import os
import sys
import asyncio
import hashlib
from datetime import datetime, timedelta
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple
from openbb import obb

import pandas as pd

from alphaflow.core.base import BaseCollector
from alphaflow.core.schema import AnalysisContext, ComponentOutput, ResearchPack

# AkShare 延迟导入（允许环境中缺失时静默降级）
try:
    import akshare as ak
    _HAS_AKSHARE = True
except ImportError:
    ak = None  # type: ignore
    _HAS_AKSHARE = False

# ============================================================
#  情感词典（A 股语境）
# ============================================================
POSITIVE_WORDS = [
    "利好", "上涨", "大涨", "涨停", "突破", "新高", "增长", "盈利",
    "超预期", "回购", "增持", "分红", "业绩预增", "扭亏", "翻倍",
    "景气", "加速", "创新高", "放量", "强势", "利润增长", "订单",
    "中标", "战略合作", "获批", "龙头", "高增长", "加仓", "买入",
    "推荐", "优于大市", "看好", "积极", "机遇", "红利", "高分红",
    "提质增效", "产能扩张", "出海", "国产替代", "自主可控",
]

NEGATIVE_WORDS = [
    "利空", "下跌", "大跌", "跌停", "破位", "新低", "亏损", "下滑",
    "低于预期", "减持", "质押", "违规", "处罚", "退市", "风险",
    "暴雷", "商誉减值", "业绩预亏", "缩量", "弱势", "诉讼",
    "被调查", "立案", "停牌", "高管离职", "资金链", "担保",
    "卖出", "回避", "看空", "警示", "监管", "罚款", "负面",
    "产能过剩", "价格战", "毛利率下降", "应收账款",
]

NEUTRAL_WORDS = [
    "公告", "披露", "报告", "会议", "调研", "变更", "通知",
    "临时", "定期", "说明", "回复", "问询",
]


# ============================================================
#  工具函数
# ============================================================
def _safe_call(func, *args, default=None, module_name="未知模块", **kwargs):
    """安全调用：静默失败，返回默认值"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"  ⚠ [{module_name}] 采集失败（已静默跳过）: {type(e).__name__}: {e}")
        return default


def _text_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _sentiment_score(text: str) -> Tuple[float, str]:
    """
    基于关键词的情感打分
    返回 (score, label)
      score ∈ [-1, 1]   label ∈ {积极, 消极, 中性}
    """
    if not text:
        return 0.0, "中性"
    pos = sum(1 for w in POSITIVE_WORDS if w in text)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text)
    total = pos + neg
    if total == 0:
        return 0.0, "中性"
    score = (pos - neg) / total
    if score > 0.2:
        label = "积极"
    elif score < -0.2:
        label = "消极"
    else:
        label = "中性"
    return round(score, 4), label


def _extract_keywords(texts: List[str], top_n: int = 15) -> List[Tuple[str, int]]:
    """从文本列表中提取高频关键词"""
    all_words = POSITIVE_WORDS + NEGATIVE_WORDS + NEUTRAL_WORDS
    counter: Counter = Counter()
    for text in texts:
        for w in all_words:
            if w in text:
                counter[w] += text.count(w)
    return counter.most_common(top_n)


# ============================================================
#  内部引擎：StockNewsAggregator
#  负责全部 AkShare 数据采集、情感分析、报告生成
# ============================================================
class StockNewsAggregator:
    """
    股票消息聚合引擎（内部使用，由 NewsCollector 调用）

    独立运行:
        agg = StockNewsAggregator(symbol="300059", name="东方财富")
        report = agg.run()
    """

    def __init__(self, symbol: str, name: str = "", days: int = 30):
        self.symbol = symbol.strip()
        self.name = name.strip()
        self.days = days
        self.start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        self.end_date = datetime.now().strftime("%Y%m%d")

        # 各模块采集结果
        self.stock_info: Optional[pd.DataFrame] = None
        self.news_data: Optional[pd.DataFrame] = None
        self.notices_data: Optional[pd.DataFrame] = None
        self.market_news: Optional[pd.DataFrame] = None
        self.comment_data: Optional[pd.DataFrame] = None
        self.inst_sentiment: Optional[pd.DataFrame] = None
        self.hot_rank: Optional[pd.DataFrame] = None
        self.sector_news: Optional[pd.DataFrame] = None

        # 分析结果
        self.sentiment_results: List[Dict] = []
        self.overview: Dict = {}
        self.success_modules: List[str] = []
        self.failed_modules: List[str] = []

    # -------------------------------------------------------
    #  模块 1：个股基本信息
    # -------------------------------------------------------
    def fetch_stock_info(self):
        def _fetch():
            return ak.stock_individual_info_em(symbol=self.symbol)
        self.stock_info = _safe_call(_fetch, default=None, module_name="个股基本信息")
        if self.stock_info is not None:
            self.success_modules.append("个股基本信息")
            if not self.name:
                try:
                    row = self.stock_info[self.stock_info["item"] == "股票简称"]
                    if not row.empty:
                        self.name = str(row.iloc[0]["value"])
                except Exception:
                    pass
        else:
            self.failed_modules.append("个股基本信息")

    # -------------------------------------------------------
    #  模块 2：个股新闻
    # -------------------------------------------------------
    def fetch_news(self):
        def _fetch():
            return ak.stock_news_em(symbol=self.symbol)
        self.news_data = _safe_call(_fetch, default=None, module_name="个股新闻")
        if self.news_data is not None and not self.news_data.empty:
            self.success_modules.append("个股新闻")
        else:
            self.failed_modules.append("个股新闻")

    # -------------------------------------------------------
    #  模块 3：公司公告
    # -------------------------------------------------------
    def fetch_notices(self):
        def _fetch():
            return ak.stock_notice_report(symbol=self.symbol)
        self.notices_data = _safe_call(_fetch, default=None, module_name="公司公告")
        if self.notices_data is not None and not self.notices_data.empty:
            self.success_modules.append("公司公告")
        else:
            self.failed_modules.append("公司公告")

    # -------------------------------------------------------
    #  模块 4：财经要闻（全局）
    # -------------------------------------------------------
    def fetch_market_news(self):
        def _fetch():
            return ak.stock_info_global_em()
        self.market_news = _safe_call(_fetch, default=None, module_name="财经要闻")
        if self.market_news is not None and not self.market_news.empty:
            self.success_modules.append("财经要闻")
        else:
            self.failed_modules.append("财经要闻")

    # -------------------------------------------------------
    #  模块 5：千股千评
    # -------------------------------------------------------
    def fetch_comments(self):
        def _fetch():
            return ak.stock_comment_detail_zlkp_jgcyd_em(symbol=self.symbol)
        self.comment_data = _safe_call(_fetch, default=None, module_name="千股千评")
        if self.comment_data is not None and not self.comment_data.empty:
            self.success_modules.append("千股千评")
        else:
            self.failed_modules.append("千股千评")

    # -------------------------------------------------------
    #  模块 6：机构评级情绪
    # -------------------------------------------------------
    def fetch_institutional_sentiment(self):
        def _fetch():
            return ak.stock_comment_detail_zhpj_lspf_em(symbol=self.symbol)
        self.inst_sentiment = _safe_call(_fetch, default=None, module_name="机构评级情绪")
        if self.inst_sentiment is not None and not self.inst_sentiment.empty:
            self.success_modules.append("机构评级情绪")
        else:
            self.failed_modules.append("机构评级情绪")

    # -------------------------------------------------------
    #  模块 7：个股人气排名
    # -------------------------------------------------------
    def fetch_hot_rank(self):
        def _fetch():
            return ak.stock_hot_rank_em()
        raw = _safe_call(_fetch, default=None, module_name="人气排名")
        if raw is not None and not raw.empty:
            mask = raw["代码"].astype(str).str.contains(self.symbol)
            self.hot_rank = raw[mask] if mask.any() else raw.head(20)
            self.success_modules.append("人气排名")
        else:
            self.failed_modules.append("人气排名")

    # -------------------------------------------------------
    #  模块 8：板块资金流
    # -------------------------------------------------------
    def fetch_sector_news(self):
        def _fetch():
            return ak.stock_sector_fund_flow_rank(
                indicator="今日", sector_type="行业资金流"
            )
        self.sector_news = _safe_call(_fetch, default=None, module_name="板块资金流")
        if self.sector_news is not None and not self.sector_news.empty:
            self.success_modules.append("板块资金流")
        else:
            self.failed_modules.append("板块资金流")

    # -------------------------------------------------------
    #  情感分析
    # -------------------------------------------------------
    def analyze_sentiment(self):
        texts: List[str] = []

        if self.news_data is not None and not self.news_data.empty:
            for col in ["新闻标题", "新闻内容", "标题", "内容"]:
                if col in self.news_data.columns:
                    texts.extend(self.news_data[col].dropna().astype(str).tolist())

        if self.notices_data is not None and not self.notices_data.empty:
            for col in ["公告标题", "标题", "公告名称"]:
                if col in self.notices_data.columns:
                    texts.extend(self.notices_data[col].dropna().astype(str).tolist())

        if self.market_news is not None and not self.market_news.empty:
            for col in ["标题", "title", "摘要"]:
                if col in self.market_news.columns:
                    texts.extend(
                        self.market_news[col].dropna().astype(str).tolist()[:30]
                    )

        seen: set = set()
        for text in texts:
            h = _text_hash(text)
            if h in seen or len(text.strip()) < 4:
                continue
            seen.add(h)
            score, label = _sentiment_score(text)
            self.sentiment_results.append({
                "text": text[:120],
                "score": score,
                "label": label,
            })

    # -------------------------------------------------------
    #  消息概述
    # -------------------------------------------------------
    def build_overview(self):
        total = len(self.sentiment_results)
        pos_count = sum(1 for r in self.sentiment_results if r["label"] == "积极")
        neg_count = sum(1 for r in self.sentiment_results if r["label"] == "消极")
        neu_count = sum(1 for r in self.sentiment_results if r["label"] == "中性")

        avg_score = (
            round(sum(r["score"] for r in self.sentiment_results) / total, 4)
            if total > 0 else 0.0
        )

        if avg_score > 0.15:
            overall = "偏积极 📈"
        elif avg_score < -0.15:
            overall = "偏消极 📉"
        else:
            overall = "中性 ➡️"

        all_texts = [r["text"] for r in self.sentiment_results]
        keywords = _extract_keywords(all_texts, top_n=15)

        news_count = len(self.news_data) if self.news_data is not None else 0
        notice_count = len(self.notices_data) if self.notices_data is not None else 0
        market_count = len(self.market_news) if self.market_news is not None else 0

        self.overview = {
            "股票代码": self.symbol,
            "股票名称": self.name or "未知",
            "分析时间": _now_str(),
            "回溯天数": self.days,
            "数据源成功": len(self.success_modules),
            "数据源失败": len(self.failed_modules),
            "成功模块": self.success_modules,
            "失败模块": self.failed_modules,
            "个股新闻条数": news_count,
            "公司公告条数": notice_count,
            "财经要闻条数": market_count,
            "情感分析样本数": total,
            "积极条数": pos_count,
            "消极条数": neg_count,
            "中性条数": neu_count,
            "平均情感得分": avg_score,
            "综合情绪判定": overall,
            "高频关键词": keywords,
        }

    # -------------------------------------------------------
    #  生成完整报告
    # -------------------------------------------------------
    def generate_report(self) -> str:
        lines: List[str] = []
        sep = "=" * 72

        # ---------- 封面 ----------
        lines.append(sep)
        lines.append(f"  股票消息聚合 · 量化分析报告")
        lines.append(f"  {self.overview.get('股票名称', '')}（{self.symbol}）")
        lines.append(f"  生成时间：{_now_str()}")
        lines.append(sep)
        lines.append("")

        # ---------- 一、消息概述 ----------
        lines.append("一、消息概述")
        lines.append("-" * 40)
        ov = self.overview
        lines.append(f"  股票代码　　：{ov['股票代码']}")
        lines.append(f"  股票名称　　：{ov['股票名称']}")
        lines.append(f"  回溯天数　　：{ov['回溯天数']} 天")
        lines.append(f"  数据源成功　：{ov['数据源成功']} 个  {ov['成功模块']}")
        lines.append(f"  数据源失败　：{ov['数据源失败']} 个  {ov['失败模块']}")
        lines.append(f"  个股新闻　　：{ov['个股新闻条数']} 条")
        lines.append(f"  公司公告　　：{ov['公司公告条数']} 条")
        lines.append(f"  财经要闻　　：{ov['财经要闻条数']} 条")
        lines.append(f"  情感分析样本：{ov['情感分析样本数']} 条")
        lines.append(f"  　积极：{ov['积极条数']}　消极：{ov['消极条数']}　中性：{ov['中性条数']}")
        lines.append(f"  平均情感得分：{ov['平均情感得分']}")
        lines.append(f"  ★ 综合情绪判定：{ov['综合情绪判定']}")
        lines.append("")
        if ov["高频关键词"]:
            lines.append("  高频关键词：")
            for word, cnt in ov["高频关键词"]:
                lines.append(f"    · {word}（{cnt}次）")
        lines.append("")

        # ---------- 二、个股基本信息 ----------
        lines.append("二、个股基本信息")
        lines.append("-" * 40)
        if self.stock_info is not None and not self.stock_info.empty:
            for _, row in self.stock_info.iterrows():
                lines.append(f"  {row.iloc[0]}：{row.iloc[1]}")
        else:
            lines.append("  （该模块数据未获取到）")
        lines.append("")

        # ---------- 三、个股新闻 ----------
        lines.append("三、个股新闻（最近）")
        lines.append("-" * 40)
        if self.news_data is not None and not self.news_data.empty:
            for idx, row in self.news_data.head(20).iterrows():
                title = ""
                for col in ["新闻标题", "标题"]:
                    if col in row.index:
                        title = str(row[col])[:80]
                        break
                time_str = ""
                for col in ["发布时间", "时间", "日期"]:
                    if col in row.index:
                        time_str = str(row[col])
                        break
                score, label = _sentiment_score(title)
                lines.append(f"  [{label}] {time_str}  {title}")
                for col in ["新闻内容", "内容"]:
                    if col in row.index and pd.notna(row[col]):
                        content = str(row[col]).strip()[:200]
                        if content:
                            lines.append(f"         ↳ {content}")
                        break
        else:
            lines.append("  （该模块数据未获取到）")
        lines.append("")

        # ---------- 四、公司公告 ----------
        lines.append("四、公司公告")
        lines.append("-" * 40)
        if self.notices_data is not None and not self.notices_data.empty:
            for idx, row in self.notices_data.head(15).iterrows():
                title = ""
                for col in ["公告标题", "标题", "公告名称"]:
                    if col in row.index:
                        title = str(row[col])[:80]
                        break
                date_str = ""
                for col in ["公告日期", "日期", "公告时间"]:
                    if col in row.index:
                        date_str = str(row[col])
                        break
                score, label = _sentiment_score(title)
                lines.append(f"  [{label}] {date_str}  {title}")
        else:
            lines.append("  （该模块数据未获取到）")
        lines.append("")

        # ---------- 五、财经要闻 ----------
        lines.append("五、财经要闻（全局）")
        lines.append("-" * 40)
        if self.market_news is not None and not self.market_news.empty:
            for idx, row in self.market_news.head(15).iterrows():
                title = ""
                for col in ["标题", "title", "摘要"]:
                    if col in row.index:
                        title = str(row[col])[:80]
                        break
                score, label = _sentiment_score(title)
                lines.append(f"  [{label}] {title}")
        else:
            lines.append("  （该模块数据未获取到）")
        lines.append("")

        # ---------- 六、千股千评 / 机构评级 ----------
        lines.append("六、千股千评 / 机构评级情绪")
        lines.append("-" * 40)
        if self.comment_data is not None and not self.comment_data.empty:
            lines.append("  [千股千评]")
            lines.append(self.comment_data.to_string(index=False, max_rows=10))
        else:
            lines.append("  千股千评：（该模块数据未获取到）")
        lines.append("")
        if self.inst_sentiment is not None and not self.inst_sentiment.empty:
            lines.append("  [机构评级历史评分]")
            lines.append(self.inst_sentiment.to_string(index=False, max_rows=10))
        else:
            lines.append("  机构评级：（该模块数据未获取到）")
        lines.append("")

        # ---------- 七、人气排名 ----------
        lines.append("七、个股人气排名")
        lines.append("-" * 40)
        if self.hot_rank is not None and not self.hot_rank.empty:
            lines.append(self.hot_rank.to_string(index=False, max_rows=10))
        else:
            lines.append("  （该模块数据未获取到）")
        lines.append("")

        # ---------- 八、板块资金流 ----------
        lines.append("八、板块资金流（行业）")
        lines.append("-" * 40)
        if self.sector_news is not None and not self.sector_news.empty:
            lines.append(self.sector_news.head(15).to_string(index=False))
        else:
            lines.append("  （该模块数据未获取到）")
        lines.append("")

        # ---------- 九、情感分析明细 ----------
        lines.append("九、情感分析明细（前 30 条）")
        lines.append("-" * 40)
        if self.sentiment_results:
            for i, r in enumerate(self.sentiment_results[:30], 1):
                lines.append(
                    f"  {i:>3}. [{r['label']}] (得分:{r['score']:+.2f})  {r['text']}"
                )
        else:
            lines.append("  （无可分析文本）")
        lines.append("")

        # ---------- 十、综合结论 ----------
        lines.append(sep)
        lines.append("十、综合分析结论")
        lines.append(sep)
        lines.append(self._generate_conclusion())
        lines.append("")
        lines.append(sep)
        lines.append(f"报告生成完毕 · {_now_str()}")
        lines.append(sep)

        return "\n".join(lines)

    # -------------------------------------------------------
    #  综合结论
    # -------------------------------------------------------
    def _generate_conclusion(self) -> str:
        ov = self.overview
        parts: List[str] = []
        parts.append(
            f"  本次对 {ov['股票名称']}（{ov['股票代码']}）的消息聚合分析，"
            f"共成功接入 {ov['数据源成功']} 个数据源，"
            f"失败 {ov['数据源失败']} 个（已静默跳过）。"
        )
        parts.append(
            f"  在 {ov['情感分析样本数']} 条有效文本中，"
            f"积极 {ov['积极条数']} 条（{self._pct(ov['积极条数'], ov['情感分析样本数'])}），"
            f"消极 {ov['消极条数']} 条（{self._pct(ov['消极条数'], ov['情感分析样本数'])}），"
            f"中性 {ov['中性条数']} 条。"
        )
        parts.append(
            f"  平均情感得分为 {ov['平均情感得分']:+.4f}，综合情绪判定为【{ov['综合情绪判定']}】。"
        )
        if ov["高频关键词"]:
            top5 = "、".join([w for w, _ in ov["高频关键词"][:5]])
            parts.append(f"  近期高频关键词：{top5}。")

        score = ov["平均情感得分"]
        if score > 0.3:
            parts.append("  当前舆情整体偏正面，市场关注度较高，建议关注后续业绩兑现情况。")
        elif score > 0.1:
            parts.append("  当前舆情偏中性略积极，无明显利空信号，可持续跟踪。")
        elif score > -0.1:
            parts.append("  当前舆情整体中性，缺乏明确方向性信号，建议结合技术面综合判断。")
        elif score > -0.3:
            parts.append("  当前舆情偏消极，存在一定负面信息干扰，建议谨慎观望。")
        else:
            parts.append("  当前舆情明显偏负面，负面信息集中出现，需关注风险事件进展。")

        parts.append("\n  ⚠ 免责声明：本报告仅基于公开舆情的量化分析，不构成任何投资建议。")
        return "\n".join(parts)

    @staticmethod
    def _pct(part, total) -> str:
        if total == 0:
            return "0.0%"
        return f"{part / total * 100:.1f}%"

    # -------------------------------------------------------
    #  保存报告
    # -------------------------------------------------------
    def save(self, report: str, filepath: str = "") -> str:
        """保存报告到文件，返回实际文件路径"""
        if not filepath:
            report_dir = os.path.join(os.path.dirname(__file__), "reports")
            os.makedirs(report_dir, exist_ok=True)
            safe_name = self.name if self.name else self.symbol
            filename = f"news_{safe_name}_{self.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(report_dir, filename)

        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"  ✅ 报告已保存到：{os.path.abspath(filepath)}")
        return os.path.abspath(filepath)

    # -------------------------------------------------------
    #  一键运行（同步）
    # -------------------------------------------------------
    def run(self, save_to_file: bool = True, filepath: str = "") -> str:
        print(f"{'=' * 50}")
        print(f"  开始消息聚合分析：{self.symbol}  {self.name}")
        print(f"  回溯 {self.days} 天 | {_now_str()}")
        print(f"{'=' * 50}")

        steps = [
            ("1/8", "采集个股基本信息",   self.fetch_stock_info),
            ("2/8", "采集个股新闻",       self.fetch_news),
            ("3/8", "采集公司公告",       self.fetch_notices),
            ("4/8", "采集财经要闻",       self.fetch_market_news),
            ("5/8", "采集千股千评",       self.fetch_comments),
            ("6/8", "采集机构评级情绪",   self.fetch_institutional_sentiment),
            ("7/8", "采集人气排名",       self.fetch_hot_rank),
            ("8/8", "采集板块资金流",     self.fetch_sector_news),
        ]
        for tag, desc, fn in steps:
            print(f"  📡 [{tag}] {desc}...")
            fn()

        print("  🔍 正在进行情感分析...")
        self.analyze_sentiment()

        print("  📊 正在构建消息概述...")
        self.build_overview()

        print("  📝 正在生成综合报告...")
        report = self.generate_report()

        if save_to_file:
            self.save(report, filepath)

        self._print_overview_to_console()
        return report

    def _print_overview_to_console(self):
        ov = self.overview
        print(f"\n{'─' * 50}")
        print(f"  📋 消息概述 — {ov['股票名称']}（{ov['股票代码']}）")
        print(f"{'─' * 50}")
        print(f"  数据源：成功 {ov['数据源成功']} / 失败 {ov['数据源失败']}")
        print(f"  新闻 {ov['个股新闻条数']} 条 | 公告 {ov['公司公告条数']} 条 | 要闻 {ov['财经要闻条数']} 条")
        print(f"  情感样本 {ov['情感分析样本数']} 条：积极{ov['积极条数']} / 消极{ov['消极条数']} / 中性{ov['中性条数']}")
        print(f"  平均得分 {ov['平均情感得分']:+.4f}")
        print(f"  ★ 综合判定：{ov['综合情绪判定']}")
        if ov["高频关键词"]:
            kw = " | ".join([f"{w}({c})" for w, c in ov["高频关键词"][:8]])
            print(f"  关键词：{kw}")
        print(f"{'─' * 50}")


# ============================================================
#  框架对外接口：NewsCollector
# ============================================================
class NewsCollector(BaseCollector):
    """
    【消息面采集器】— alphaflow pipeline 组件

    职责：
      1. 通过 AkShare API 聚合新闻、公告、市场资讯、机构评级、舆情情绪
      2. 关键词情感分析
      3. 生成消息概述 + 综合分析报告，输出到文件
      4. 将结构化结果写入 ResearchPack，传递给下游组件

    Vibe Coding 特性：
      - 8 个数据源独立采集，局部失效静默跳过
      - 高扩展性，新增数据源只需在 StockNewsAggregator 中增加 fetch_xxx 方法
      - 支持 AkShare 缺失时优雅降级

    数据流入：ResearchPack（从上游组件获取 symbol）
    数据流出：
      - pack.news                       → 个股新闻列表 List[Dict]
      - pack.extra["news_overview"]     → 消息概述字典
      - pack.extra["news_sentiment"]    → 情感分析结果列表
      - pack.extra["news_report_path"]  → 报告文件绝对路径
      - pack.extra["news_conclusion"]   → 综合结论文本
      - pack.extra["news_report"]       → 完整报告文本（截断，防止内存膨胀）
    """

    async def fetch_data(
        self, context: AnalysisContext, **kwargs
    ) -> ComponentOutput:
        # ------ 解包上游数据 ------
        input_data = kwargs.get("input_data")
        pack = (
            input_data.payload
            if isinstance(input_data, ComponentOutput)
            else input_data
        )
        if pack is None:
            pack = ResearchPack(symbol=context.symbols[0])

        symbol = pack.symbol
        # 尝试从 context 获取名称（如果上游已经填充了）
        name = getattr(pack, "name", "") or ""
        
        # 优先从 metadata 获取 days，其次是 config，最后默认 30
        days = context.metadata.get("days", 30)
        if days > 90: # 限制新闻采集最长 90 天，防止 AkShare 接口压力过大
            days = 90
        
        print(f"\n  [NewsCollector] 启动消息面采集 → {symbol} {name} (回溯 {days} 天)")

        # ------ 检查 AkShare 可用性 ------
        if not _HAS_AKSHARE:
            print("  [!] AkShare 未安装，消息面采集跳过")
            pack.extra["news_status"] = "akshare not installed"
            return ComponentOutput(success=True, payload=pack)

        # ------ 在线程池中运行同步的 AkShare 采集（避免阻塞事件循环）------
        try:
            agg = StockNewsAggregator(symbol=symbol, name=name, days=days)
            # AkShare 全部是同步 HTTP 调用，放到线程池中执行
            report = await asyncio.to_thread(
                agg.run, save_to_file=True, filepath=""
            )
        except Exception as e:
            print(f"  [!] NewsCollector 整体异常（已静默跳过）: {e}")
            pack.extra["news_status"] = f"aggregator error: {e}"
            return ComponentOutput(success=True, payload=pack)

        # ------ 将结果写入 ResearchPack ------

        # 1) pack.news ← 个股新闻列表（与框架原有字段兼容）
        if agg.news_data is not None and not agg.news_data.empty:
            pack.news = agg.news_data.head(20).to_dict(orient="records")
        else:
            pack.news = []

        # 2) 消息概述
        pack.extra["news_overview"] = agg.overview

        # 3) 情感分析结果
        pack.extra["news_sentiment"] = agg.sentiment_results

        # 4) 综合结论
        pack.extra["news_conclusion"] = agg._generate_conclusion()

        # 5) 报告文件路径（下游组件可从此路径读取完整报告）
        #    报告已在 agg.run() 中自动保存
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        report_files = sorted(
            [f for f in os.listdir(report_dir) if f.startswith(f"news_") and symbol in f],
            reverse=True,
        ) if os.path.isdir(report_dir) else []
        if report_files:
            pack.extra["news_report_path"] = os.path.join(report_dir, report_files[0])
        else:
            pack.extra["news_report_path"] = ""

        # 6) 报告文本（截断到前 5000 字符，完整版见文件）
        pack.extra["news_report"] = report[:5000] if report else ""

        # 7) 状态标记
        pack.extra["news_status"] = "ok"
        pack.extra["news_success_modules"] = agg.success_modules
        pack.extra["news_failed_modules"] = agg.failed_modules

        # 如果 agg 从基本信息中获取到了股票名称，回填给 pack
        if agg.name and hasattr(pack, "name"):
            pack.name = agg.name

        print(f"  [NewsCollector] 完成 ✔  "
              f"数据源 {len(agg.success_modules)}/{len(agg.success_modules) + len(agg.failed_modules)}  "
              f"情感样本 {len(agg.sentiment_results)} 条  "
              f"判定：{agg.overview.get('综合情绪判定', 'N/A')}")

        return ComponentOutput(success=True, payload=pack)


# ============================================================
#  独立运行入口（不经过 pipeline 时直接使用）
# ============================================================
def main():
    """命令行用法: python news.py <股票代码> [股票名称] [回溯天数]"""
    if len(sys.argv) < 2:
        print("用法: python news.py <股票代码> [股票名称] [回溯天数]")
        print("示例: python news.py 300059 东方财富 30")
        print("示例: python news.py 600519 贵州茅台")
        print("示例: python news.py 000001")
        sys.exit(1)

    symbol = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else ""
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    agg = StockNewsAggregator(symbol=symbol, name=name, days=days)
    agg.run(save_to_file=True)


if __name__ == "__main__":
    main()

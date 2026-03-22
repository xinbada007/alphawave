"""
Base Fetcher - 原子数据抓取器基类
基于 IoC 与生命周期钩子设计，支撑多市场、多 Provider 的无限横向扩展。
实施"基于任务路由的防腐层 (Task-Routed ACL)"架构，实现精细编排。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional
from alphaflow.core.utils import ReportPeriod


class BaseFetcher(ABC):
    """
    原子抓取器基类 (基于 Task Routing 的精细编排)

    设计哲学：
    1. 轨道 1：核心状态快照 (严格防腐层) - 通过 TASK_MAPPING_ROUTER 精细编排
    2. 轨道 2：事件流与异构数据 (标准化透传) - 委托 event_normalizer 做 Provider 词汇翻译

    架构升级：
    - 移除 FINANCIAL_TASKS / META_TASKS 二元分流
    - 直接透传 task_name 给 Adapter
    - Adapter 根据 TASK_MAPPING_ROUTER 决定使用哪些映射表
    """

    name: str = "BaseFetcher"

    # --- 声明式配置 (子类覆盖) ---
    is_cumulative: bool = False  # 默认美股离散制

    # ==========================================
    # 🚀 轨道 1 任务集合 (需要严格防腐层)
    # 这些任务会在 TASK_MAPPING_ROUTER 中找到对应的映射表
    # ==========================================
    ACL_TASKS = {
        # === 财务三大表 ===
        "a_income",
        "q_income",
        "a_balance",
        "q_balance",
        "a_cash",
        "q_cash",
        "a_analysis",
        "q_analysis",
        # === 元数据任务 ===
        "profile",
        "estimates",
        "share_stats",
    }

    async def fetch(self, task_name: str, symbol: str, **kwargs) -> List[Dict]:
        """
        全域采集流水线 (Pipeline Backbone) - 基于任务路由的精细编排

        轨道 1：核心状态快照 (严格防腐层)
            - ACL_TASKS -> adapter.normalize(task_name=task_name)
            - Adapter 根据 TASK_MAPPING_ROUTER 决定映射表组合

        轨道 2：事件流与异构数据 (无损透传)
            - insider_trading, dividends, splits 等 -> 原样返回，仅提取日期
        """

        # 1. [Hook] 前置处理 (如 Symbol 格式化：600519.SH -> 600519)
        formatted_symbol = self.pre_fetch_symbol(symbol)

        # 2. [Core] 委托给子类执行真实的原子抓取
        raw_data = await self._fetch_raw(task_name, formatted_symbol, **kwargs)
        if not raw_data:
            return []

        # 3. [Hook] 后置处理 (如 API 返回结构极其反人类，需提前拍平)
        raw_data = self.post_fetch_data(task_name, raw_data)

        # 🚀 统一清理：移除 null/None/空字符串字段（保留 0 值）
        from alphaflow.core.acl.transformers import clean_null_fields_batch

        raw_data = clean_null_fields_batch(raw_data)

        # ==========================================
        # 🚀 极简轨道分流器 (Context Router)
        # ==========================================

        # 轨道 1：核心状态快照 (严格防腐层)
        # 只要在 ACL_TASKS 名单里，就扔给 adapter
        if task_name in self.ACL_TASKS:
            rt, is_cum = self._infer_period_context(task_name)

            if hasattr(self, "adapter") and self.adapter:
                return self.adapter.normalize(
                    raw_data,
                    task_name=task_name,  # 🚀 直接透传 task_name 给 Adapter 进行智能编排
                    period_type=rt,
                    is_cumulative=is_cum,
                )
            return raw_data

        # 轨道 2：事件流与异构数据 (标准化透传)
        # 🚀 D1: 委托给独立的事件流标准化器，避免 BaseFetcher 膨胀
        else:
            from alphaflow.core.acl.event_normalizer import normalize_event_fields
            from alphaflow.core.context import GlobalContext

            is_debug = GlobalContext().get("DEBUG", False)
            
            # 字段别名 + 文本提取 + 日期标准化（一行委托）
            raw_data = normalize_event_fields(raw_data)
            
            if is_debug:
                for item in raw_data:
                    item["raw_provider_data"] = item.copy()
            return raw_data

    # ==========================================
    # 核心抽象方法 (必须实现)
    # ==========================================
    @abstractmethod
    async def _fetch_raw(self, task_name: str, symbol: str, **kwargs) -> List[Dict]:
        """执行网络抓取，返回 Provider 的原始脏数据字典列表"""
        pass

    # ==========================================
    # 扩展点：生命周期钩子 (Hooks - 可选实现)
    # ==========================================
    def pre_fetch_symbol(self, symbol: str) -> str:
        """[Hook] 抓取前置钩子：格式化 Symbol。子类按需重写。"""
        return symbol

    def post_fetch_data(self, task_name: str, raw_data: List[Dict]) -> List[Dict]:
        """[Hook] 抓取后置钩子：在进入 Adapter 前的粗洗。子类按需重写。"""
        return raw_data

    # ==========================================
    # 扩展点：策略推断引擎 (Strategy Engine)
    # ==========================================
    def _infer_period_context(
        self, task_name: str
    ) -> Tuple[Optional[ReportPeriod], Optional[bool]]:
        """
        动态推断报表周期属性。
        默认提供 AlphaFlow 标准的 a_/q_ 前缀解析。
        如果未来增加 s_(半年度) 或 m_(月度)，子类可直接重写此方法，无需修改基类。
        """
        if task_name.startswith("a_"):
            return ReportPeriod.ANNUAL, self.is_cumulative
        elif task_name.startswith("q_"):
            return ReportPeriod.QUARTERLY, self.is_cumulative
        # 如果不是财报类任务 (如 profile, estimates)，返回 None
        return None, None

# AlphaFlow 设计哲学与品味 TODO

> 本文件记录关于产品品味、设计哲学层面的待讨论项，不属于紧急开发任务。

## LLM 友好性设计原则

> **宁缺毋滥**：宁可不算也不可硬造，指标保证严格的金融含义和准确性。

- [ ] `llm_view.py` 的深度清理逻辑验证完毕（空 signals/空 insights 应沉默剔除，这是正确行为），但需确认 section 整体消失时不会破坏 LLM 的 prompt 结构预期
- [ ] `extra_context` 中的原始财报数据对 LLM 的实际价值评估：当 distilled 指标足够丰富后，考虑裁剪策略
- [ ] `currency_context.warning_message` 和 `llm_instruction` 的措辞优化，确保 LLM 能准确理解币种修正语义

## 映射审计遗留问题

- [ ] **`TOTAL_EQUITY_CONSOLIDATED` — MSFT (OBB/YFinance) 数据缺失**
  - YFinance 的 `total_equity` 字段在 MSFT 中为空，导致 `debt_to_equity` 指标无法计算
  - 潜在修复方案：`debt_to_equity` 加 fallback 到 `TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT`（无 NCI 场景数值等价）
  - 需评估：对存在 NCI 的公司是否违反"宁缺毋滥"原则

## 事件流重构（下一阶段）

> 目标：对公司重大事件（新闻、公告、财报事件）进行信息提取与蒸馏，提供给 LLM 高密度的事件上下文。

- [ ] **事件流架构定义**：确定事件流的数据来源（Yahoo Finance 新闻、SEC 公告、港交所公告等）
- [ ] **事件分类体系**：定义事件类型（earnings / management_change / M&A / dividend / regulatory / macro），冷峻中性命名
- [ ] **事件信息提取契约**：每条事件输出格式（date / type / headline / key_numbers / cross_domain_impact）
- [ ] **跨域事件关联**：事件与财务指标的关联索引（如"本季度营收下降"需指向对应 `revenue_yoy_pct`）
- [ ] **时效权重设计**：近期事件 vs 历史事件的衰减权重，避免旧事件污染 LLM 注意力
- [ ] **事件流的 LLM 视图**：在 `llm_view.py` 中集成事件流 section，设计合理的 token 预算

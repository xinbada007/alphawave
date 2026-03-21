# AlphaFlow 设计哲学与品味 TODO

> 本文件记录关于产品品味、设计哲学层面的待讨论项，不属于紧急开发任务。

## LLM 友好性设计原则

> **宁缺毋滥**：宁可不算也不可硬造，指标保证严格的金融含义和准确性。

- [ ] `health_tags` 为空时的处理策略：是否需要默认标签告知 LLM "指标均在正常范围"，还是保持沉默（无标签 = 无异常）
- [ ] `llm_view.py` 的深度清理逻辑是否过于激进（连空列表都清掉了，导致某些 section 整体消失）
- [ ] `extra_context` 中的原始财报数据对 LLM 的实际价值评估：当 distilled 指标足够丰富后，考虑裁剪策略
- [ ] `currency_context.warning_message` 和 `llm_instruction` 的措辞优化，确保 LLM 能准确理解币种修正语义

## 指标命名规范

- [ ] 审视所有 `feature_name` 是否符合"命名即文档"（通用金融术语、一看就知道什么含义）
- [ ] 域名 (domain) 是否对 LLM 友好（如 `profitability_ttm` vs 更人类的 `profitability_trailing_twelve_months`）

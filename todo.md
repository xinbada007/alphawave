# AlphaFlow 设计哲学与品味 TODO

> 本文件记录关于产品品味、设计哲学层面的待讨论项，不属于紧急开发任务。

## LLM 友好性设计原则

> **宁缺毋滥**：宁可不算也不可硬造，指标保证严格的金融含义和准确性。

- [ ] `health_tags` 为空时的处理策略：是否需要默认标签告知 LLM "指标均在正常范围"，还是保持沉默（无标签 = 无异常）
- [ ] `llm_view.py` 的深度清理逻辑是否过于激进（连空列表都清掉了，导致某些 section 整体消失）
- [ ] `extra_context` 中的原始财报数据对 LLM 的实际价值评估：当 distilled 指标足够丰富后，考虑裁剪策略
- [ ] `currency_context.warning_message` 和 `llm_instruction` 的措辞优化，确保 LLM 能准确理解币种修正语义

## 映射审计遗留问题

- [ ] **`TOTAL_EQUITY_CONSOLIDATED` — MSFT (OBB/YFinance) 数据缺失**
  - YFinance 的 `total_equity` 字段在 MSFT 中为空，导致 `debt_to_equity` 指标无法计算
  - 原因推测：MSFT 无非控股权益（NCI ≈ 0），YFinance 可能仅提供 `total_common_equity` 而不提供 `total_equity`
  - 潜在修复方案：在 `debt_to_equity` 指标中加 fallback 到 `TOTAL_EQUITY_ATTRIBUTABLE_TO_PARENT`（在无 NCI 场景下数值等价）
  - 需评估：这是否违反"宁缺毋滥"原则（fallback 到归母权益而非合并权益，在存在 NCI 的公司中会改变金融含义）
  - 影响范围：仅影响美股中 YFinance 不提供 `total_equity` 的票（MSFT 已确认受影响），港股（AkShare）不受影响

## 指标命名规范

- [ ] 审视所有 `feature_name` 是否符合"命名即文档"（通用金融术语、一看就知道什么含义）
- [ ] 域名 (domain) 是否对 LLM 友好（如 `profitability_ttm` vs 更人类的 `profitability_trailing_twelve_months`）

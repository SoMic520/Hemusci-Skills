# D1–D13 全文表达试点

`assets/module-expression-pilot.csv` 为 D1–D13 每个学科模块各提供一条来源约束的英文修辞骨架。它用于证明从“元数据发现”到“打开全文、核对作者/DOI/许可/段落、抽象表达功能”的流程可执行，不是千篇全文语料的替代物。

## 资格边界

- `fulltext_verified`：已打开期刊官方全文页面，核对题名、作者、年份、DOI、许可和所用段落。
- `expression_qualified_pilot`：仅表示该条已完成单次来源、许可、语境和抽象化检查，可以作为内部流程测试种子。
- `agent_source_license_context_check_human_domain_review_pending`：尚未完成两名独立学科审校者的正式复核。
- `internal_pilot_not_production_phrasebook`：不得作为生产级短语库批量调用，不得据此声称 13 个模块已经完成大规模全文学习。

所有条目均为空 `exact_fragment`、`verbatim_word_count=0`，只保留参数化表达骨架。写作时必须用任务事实重新造句，不得逆向恢复或拼接来源原句。

## 使用规则

1. 只选择与当前模块、文体、章节和修辞功能匹配的条目。
2. 读取 `context_limit` 和 `module_fit_reason`，确认研究设计、尺度、对象和证据边界均相容。
3. 以用户材料中的真实对象、方法和结果替换方括号；缺失信息保持占位或提问，不补造。
4. 与原文进行相似性人工复核，避免复现具有辨识度的连续措辞。
5. 正式纳入生产表达库前，补齐两名独立学科审校、分歧裁决、任务实测和版本记录。

使用 `scripts/validate_module_expression_pilot.py` 检查 D1–D13 覆盖、全文状态、许可、来源字段、零逐字摘录和发布边界；同时运行通用 `validate_expression_corpus.py`。

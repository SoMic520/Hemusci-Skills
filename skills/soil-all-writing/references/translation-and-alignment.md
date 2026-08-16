# Chinese–English translation and alignment

## Select the translation mode

- **faithful technical translation:** preserve structure when traceability or legal/normative force dominates;
- **publication translation:** preserve meaning while adapting information flow and scientific register;
- **parallel bilingual:** maintain segment IDs and one-to-one auditability;
- **terminology normalization:** change only approved term forms;
- **back-check:** compare an existing translation with the source without rewriting unless requested.

Patent claims, standards requirements, definitions, formulas, and regulated statements use the most conservative mode. A paper discussion or poster may permit greater rhetorical adaptation.

## Translation workflow

1. Identify genre, discipline, audience, English variety, classification system, and governing terminology.
2. Segment by semantic unit, not arbitrary token count. Keep heading, paragraph, list, table, caption, claim, and definition boundaries.
3. Extract protected elements and candidate terms before translation.
4. Resolve the project termbase and flag polysemy. Never translate a term solely from a dictionary gloss.
5. Translate propositions and logical relations before optimizing sentence form.
6. Reconstruct natural information flow in the target language without adding a claim or deleting a limitation.
7. Align each target segment with its source. Check negation, comparison set, agent, tense/aspect, modality, causality, scope, quantity, unit, citation, and cross-reference.
8. Apply genre style and author voice only after semantic alignment passes.
9. Report unresolved terms and material departures from source order or explicitness.

## Chinese scientific prose

Prefer explicit subjects when ambiguity would arise, concrete verbs, defined referents, moderate sentence length, and logical relations supported by evidence. Remove translationese such as unnecessary nominalization, stacked “的” phrases, repeated “进行了……研究”, and empty significance claims. Retain repetition when it secures technical reference.

### Source-language interference: closed loop and full/whole chain

“闭环”和“全链条”首先是翻译问题：译者把英文表层形式携入中文，却没有还原原文命题。它们同时受译文专业语域约束，因此是“源语干扰＋目标语域”双重错误，不只是一般的公文套话。

| 英文源语及实际词义 | 不得采用的表层译法 | 中文重建方式 |
| --- | --- | --- |
| `closed-loop control/system` 指测量值反馈至执行部件 | “闭环（控制）” | 写明“根据土壤含水量测定结果调节阀门开度”，或在必须概括时用“反馈控制” |
| `close the loop` 指偏差处置和有效性验证 | “形成闭环” | 写明问题、纠正措施、复核及有效性验证 |
| `closed loop` 指样品或数据可追溯 | “质量闭环” | 写明样品交接记录、数据复核和异常处置 |
| `full/whole chain` 指采样至归档的工作范围 | “全链条” | 按原文逐项列明采样、运输、制备、检测、复核和归档阶段 |
| `entire ... chain` 指物质过程或因果序列 | “……全链条” | 写明投入（或来源）、迁移、转化和归趋等原文确实包含的过程 |
| `entire supply/value chain` 指生产与流通阶段 | “供应/价值全链条” | 仅列明原文纳入的生产、储存、运输、使用或回收阶段 |

不得根据英文字面自行补全源文没有的阶段、因果或质量控制动作。若源文只给出空泛总称，译文应标记语义未决，不得把推测写成事实。详细的源语触发、按义重建和源文—译文测试见 `assets/translation-interference-rules.json` 与 `assets/translation-interference-cases.jsonl`。

Do not calque `closed loop` as “闭环” or `full/whole chain` as “全链条” in generated or translated soil-science prose. Recover the proposition instead. A literal occurrence may remain only inside a source-locked quotation, official title, or immutable procurement clause, with an exact-occurrence exception record; it must not leak into the writer's own explanation.

## English scientific prose

Choose subject position to signal the paragraph’s topic. Use active or passive voice according to information flow and accountability, not ideology. Prefer a precise verb over a generic noun–verb bundle, but retain standard field collocations. Keep old information before new information when it improves cohesion. Place limitations and comparison conditions where they govern the claim.

Do not force idioms, ornamental vocabulary, informal personality, or synonym rotation. Native-like scientific English is conventional, economical, and evidence-calibrated rather than conspicuously literary.

## High-risk bilingual checks

- 有效/速效/可利用/可提取 versus available, labile, bioavailable, extractable;
- 含量 versus content, concentration, proportion, amount, or stock;
- 储量/储存/固存 versus stock, storage, retention, stabilization, or sequestration;
- 促进/驱动/调控/介导 versus increase, drive, regulate, mediate, or be associated with;
- 显著 versus statistically significant, substantial, marked, or notable;
- 响应 versus response, sensitivity, change, effect, or association;
- 土壤改良 versus amendment, conditioning, reclamation, restoration, or remediation;
- 标准中的“应/宜/可/能” and patent modality versus the governing normative/legal equivalents.

## Alignment release report

For high-stakes or full-document work, report counts and locations for added/omitted numbers, units, citations, formulas, named entities, negations, modal verbs, causal verbs, and cross-references. A zero-count token audit is necessary but not sufficient; complete a human semantic review.

For bilingual JSONL segments, run `scripts/audit_translation_interference.py`. A source trigger with no forbidden literal still receives `semantic_review_required`: the script can verify absence of the calque, but it cannot prove that the selected Chinese wording preserves the source meaning.

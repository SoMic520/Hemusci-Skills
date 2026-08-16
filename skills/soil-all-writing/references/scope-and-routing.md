# Scope and routing

## Select an operation mode

| Mode | May change | Must not change without explicit authority | Default deliverable |
| --- | --- | --- | --- |
| terminology | term choice, spelling, capitalization, definition note | surrounding argument or data | preferred term, alternatives, rationale, source status |
| expression research | rhetorical patterns and collocations | source claims or copied sentences | small sourced expression set plus abstracted patterns |
| copyedit | grammar, syntax, cohesion, concision | scientific meaning, claims, numbers, citations | clean text; material caveats only |
| substantive edit | organization, claim order, paragraph logic | evidence record or study facts | revision plus material-change log |
| translation | target-language realization | source meaning and evidential strength | clean or aligned bilingual text plus exception report |
| audit | nothing | entire artifact | prioritized findings with locations and evidence |
| drafting | prose from verified inputs | missing content and unsupported claims | draft with unresolved markers and source bindings |
| genre conversion | structure, detail, and register for a new audience | scientific record | converted artifact plus omitted/compressed content log |

Use diagnosis-only mode when the user asks to inspect, assess, review, or explain. Editing requires an explicit change request.

## Separate language repair from document generation

Language scope and artifact scope are independent. Use one of these artifact modes:

| Artifact mode | Trigger | Template behavior | Default format behavior |
| --- | --- | --- | --- |
| `language_repair` | The user supplies text or a file and asks for polishing, terminology correction, translation, naturalness, or language normalization | Do not retrieve or impose a template | Preserve paragraphs, headings, numbering, tables, citations, fields, styles, page geometry, and file structure |

For DOCX files in `language_repair`, use the text-node path in `docx-language-repair-fidelity.md`. It binds every authorized change to the source artifact and original text hashes, modifies a new copy, and verifies that no unplanned text node, formatting structure, field, table, numbering definition, section property, binary part, or protected element changed. A format-preserving language repair is not permission to rebuild the file.
| `template_aware_repair` | The user supplies a template or explicitly names a venue/call and asks for conformity as well as language work | Supplied template controls; retrieve official materials only to resolve missing or conflicting rules | Change only the authorized format and structure; keep a change log |
| `full_artifact_generation` | The user explicitly asks for a complete paper, grant, patent, standard, report, bid, poster, presentation, or other finished artifact | Use the supplied template first; otherwise retrieve the current official template or record its absence | Build, validate, render, and visually inspect the requested artifact |

Do not infer `full_artifact_generation` from the subject matter alone. A 20-page manuscript can still be a language-only repair. Conversely, a short official form can require template-aware handling. If the user provides a template, do not replace it with a Skill default merely because another template looks more polished.

## Select a project mode

Use lightweight mode for a single term, passage, caption, or bounded section. Read only the core integrity reference, the relevant discipline material, and one genre module.

Use managed-project mode for:

- complete manuscripts, grants, patents, standards, or reports;
- repeated revisions or multiple companion files;
- text containing confidential, legal, regulatory, or funder-controlled material;
- cross-section or bilingual consistency work;
- submission-, filing-, or publication-facing work.

Instantiate only the records justified by task risk. A full-document language repair normally needs a working copy, protected-elements record, termbase, change log, and review manifest, but it does not need a format contract, cover profile, template registry selection, or render cycle unless format work was requested. Keep original files unchanged.

## Classify edit risk

- **L0 presentation:** punctuation, spacing, obvious typographic correction.
- **L1 language:** grammar, collocation, sentence economy, local cohesion.
- **L2 semantic:** terminology sense, comparison scope, hedging, causal verb, definition.
- **L3 structural:** paragraph order, section logic, claim placement, genre conversion.
- **L4 scientific/legal/normative:** data, method, interpretation, patent scope, normative force, compliance statement.

Apply L0–L1 directly when editing is authorized. Log L2. Require source support and a material-change log for L3. Require accountable domain review before accepting L4.

## Distinguish roles

The skill may act as language editor, translator, terminology manager, evidence-aware scientific editor, or genre reviewer. It does not become the inventor, principal investigator, standards committee, legal adviser, statistician, journal editor, or accountable author.

## Stop or reroute

Stop direct drafting and offer safe alternatives when:

- a current policy prohibits generated application text;
- the source is absent and the task would require inventing claims, results, novelty, legal scope, or requirements;
- confidentiality authorization is missing for an external provider;
- the user requests detector evasion, concealed AI use, fabricated quotations, or imitation of a living author’s distinctive voice;
- exact method, data, format, or legal analysis exceeds the language scope.

Exact method validation, data analysis, and geospatial computation remain separate scientific responsibilities. For Chinese soil-science technical bids, use this Skill's standalone DOCX/PDF path and render gate. Use an external file or journal-format Skill only when the user authorizes it or a supplied controlled template requires capabilities not present here.

## Voice matching

Match a supplied author corpus at the level of observable, non-identifying traits: directness, sentence length distribution, paragraph density, preferred transitions, first-person usage, hedging, terminology, and explanation depth. Do not claim to reproduce identity and do not imitate a living author’s uniquely recognizable style on request. Build a project style sheet from the user’s own or authorized samples.

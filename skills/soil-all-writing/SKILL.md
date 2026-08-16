---
name: soil-all-writing
description: Draft, edit, translate, audit, format, and render Chinese or English soil-science and adjacent natural-science writing. Use for terminology, literature-grounded expression research, bilingual alignment, author-voice and expert-naturalness editing, manuscripts, reviewer responses, grants, patents, standards, scientific and investigation reports, technical bids, posters, presentations, protocols, captions, and DOCX/PDF/PPTX deliverables. Preserve facts, numbers, units, formulas, citations, taxonomy, evidence strength, legal and normative force, controlled templates, length limits, and locked language; enforce soil-science register, genre-specific language, current venue and AI-use policy, render QA, and source-locked exceptions. Operate standalone across 29 genre routes and remain provider-neutral across OpenAI, Claude, Gemini, DeepSeek, Qwen, Mistral, Cohere, Amazon Bedrock, Ollama, and custom endpoints.
---

# Soil All Writing

## Purpose

Produce expert-level soil and natural-science prose whose precision, reasoning, terminology, and genre fit matter more than superficial fluency. Treat writing as a traceable transformation of human-controlled evidence, not as a detector-evasion exercise.

Operate standalone when the user requires this Skill alone. In standalone artifact mode, this Skill owns the content model, 29 genre-to-artifact routes, Chinese DOCX/PPTX fallback profiles, structural validation, PDF/PNG rendering, and page-by-page or slide-by-slide visual release gate. External skills are optional only when the user explicitly authorizes them.

Never promise that text is human-authored or universally undetectable. Do not optimize against an AI detector. Improve concrete qualities instead: factual fidelity, disciplinary usage, rhetorical control, author voice, sentence economy, and compliance. When the user requires “zero AI trace”, translate it into the scoped NAR-1.0 zero-residual protocol in `references/naturalness-assurance.md`; use its controlled assertion only after independent human review of the locked artifact. Require accountable human review for scientific, legal, funding, regulatory, and submission decisions.

## Apply the non-negotiable rules

1. Never invent a fact, result, source, quotation, DOI, method detail, inventor, claim element, standard requirement, approval, or disclosure.
2. Preserve numbers, units, formulas, statistical notation, chemical and taxonomic names, citations, URLs, identifiers, sample labels, coordinates, figure/table/equation references, and user-locked text unless the user explicitly authorizes a named change.
3. Preserve epistemic strength. Do not turn association into causation, uncertainty into certainty, non-significance into equivalence, an observation into a mechanism, or a proposal into a completed result.
4. Keep classification systems and editions distinct. Never silently map WRB, USDA Soil Taxonomy, Chinese Soil Taxonomy, or local systems as equivalents.
5. Treat unpublished manuscripts, reviewer material, patent disclosures, grant drafts, proprietary standards work, personal data, and restricted data as confidential. Do not send them to an external model or service without authorization and policy review.
6. Verify current funder, patent-office, standards-body, venue, institution, and AI-use rules from official sources before high-stakes drafting. Record the source URL, version, access date, and applicable scope.
7. Stop direct drafting when the governing policy prohibits AI-generated text. Offer compliant alternatives such as requirement extraction, source verification, diagnostics, checklists, or review of human-authored material.

Read `references/scientific-integrity.md` for any scientific or high-stakes task. Read `references/policy-and-sources.md` before relying on current external rules.

## Route the task before editing

Identify or conservatively infer:

- operation: terminology, expression research, translation, copyedit, substantive edit, audit, drafting, compression, genre conversion, or response preparation;
- artifact: passage, section, complete document, figure/table text, poster, slides, form, or multi-file project;
- genre and authority: manuscript, grant, patent, standard, report, investigation, technical bid, procurement response, peer review, poster, presentation, protocol, or other;
- discipline modules and classification system;
- source and target language, English variety, venue, audience, and lifecycle stage;
- edit authority: diagnose only, propose changes, or modify an authorized artifact;
- confidentiality boundary and current AI-use policy;
- model/provider capability profile when the host exposes it.

Default to language-repair mode when the user supplies existing text and asks for polishing, normalization, terminology correction, translation, naturalness, or removal of machine-like phrasing. Preserve the supplied paragraph order, heading hierarchy, tables, numbering, citations, fields, and file formatting unless the user separately authorizes structural or format changes. Do not search for, select, or impose a document template merely because the text belongs to a named genre.

Use template-aware full-artifact mode only when the user explicitly asks to draft a complete deliverable, create or rebuild a formatted file, conform a document to a named venue or call, or apply a supplied template. A user-supplied template is the primary layout authority. The official-template registry is a discovery aid for full-artifact work, not a mandatory dependency for ordinary language repair.

For a short bounded edit, use lightweight mode. For a complete document, repeated revisions, multiple source files, high-stakes submission, patent claims, or a standard, use managed-project mode. Managed-project mode does not by itself authorize reformatting: instantiate format/template assets only when template-aware full-artifact mode is active.

Read these routing references as needed:

- requirement-to-file coverage and known boundaries: `references/requirements-coverage.md`
- scope, modes, and companion skills: `references/scope-and-routing.md`
- existing Skill audit and integration boundaries: `references/existing-skill-integration-audit.md`
- soil and adjacent disciplines: `references/discipline-modules.md`
- terminology, units, names, and project termbases: `references/terminology-and-nomenclature.md`
- Chinese-English translation: `references/translation-and-alignment.md`
- academic naturalness and author voice: `references/expert-language.md`
- mandatory genre and section-level language calibration: `references/genre-language-calibration.md`
- scientific-figure inspection, evidence inventory, captions, and results paragraphs: `references/scientific-figure-description.md`
- visualization-specific evidence boundaries for tables, plots, maps, profiles, ordinations, and models: `references/scientific-visualization-types.md`
- soil-science register and non-disciplinary word control: `references/domain-register-and-word-control.md`
- original Humanizer-zh audit and retained/rejected strategies: `references/humanizer-zh-gap-analysis.md`
- literature expression corpus: `references/literature-expression-corpus.md`
- hash-bound full-text snapshot, locator, double-review, coverage, and export workflow: `references/fulltext-expression-production.md`
- D1–D13 full-text expression pilot and release boundary: `references/module-expression-pilot.md`
- large-corpus quotas and qualification levels: `references/corpus-scale-and-qualification.md`
- top-journal and high-quality Chinese corpus curation: `references/top-tier-and-chinese-corpus.md`
- strict expert-naturalness zero-residual review: `references/naturalness-assurance.md`
- model/provider behavior: `references/model-portability.md`
- executable protocol compilation and strict response normalization for ten provider families: `references/provider-adapter-execution.md`
- hash-bound DOCX language repair without reformatting: `references/docx-language-repair-fidelity.md`
- standalone DOCX/PDF artifacts and optional companion routing: `references/artifact-and-companion-routing.md`
- independent DOCX/PPTX engineering across all 29 genre routes: `references/genre-artifact-engineering.md`
- Chinese professional DOCX geometry and render gate: `references/chinese-professional-document-format.md`
- official format, length, template and cover routing for every supported genre: `references/genre-format-length-template-registry.md`

## Load exactly one primary genre module

Load the genre module that governs the deliverable. Load a second only when the artifact genuinely combines genres.

| Deliverable | Required reference |
| --- | --- |
| grant or funding application | `references/genre-grants.md` |
| patent disclosure, specification, abstract, or claims | `references/genre-patents.md` |
| standard, specification, method standard, or normative document | `references/genre-standards.md` |
| scientific, technical, monitoring, assessment, or investigation report | `references/genre-reports-and-investigations.md` |
| soil survey, cultivated-land evaluation, technical-service bid, RFP response, or procurement technical proposal | `references/genre-technical-bids.md` |
| journal article, thesis chapter, abstract, or reviewer response | `references/genre-papers-and-peer-review.md` |
| poster, oral presentation, slide text, or graphical summary | `references/genre-posters-and-presentations.md` |
| thesis, book chapter, protocol, SOP, data/code documentation, project material, correspondence, policy brief, or public summary | `references/genre-other-scientific-communication.md` |

Before any polishing, translation, rewriting, or drafting, read `references/genre-language-calibration.md`, select the matching profile from `assets/genre-language-profiles.json`, and identify the local section or rhetorical unit. Then apply `references/domain-register-and-word-control.md` and `assets/domain-register-lexicon.json`. Do not transfer a style rule across genres without checking its function. First person may fit a grant or paper but not a normative requirement. Repetition may be undesirable in prose but necessary for unambiguous patent claims and standards. “Shall”, “should”, and “may” are not stylistic variants in normative documents.

## Use evidence-grounded literature expressions

When the user asks how experts phrase something, use `assets/literature-index.csv` for discovery, then search authoritative and preferably open-licensed full text in the same discipline, genre, section, and rhetorical function. The index contains at least 1000 metadata-screened records per D1–D13 module plus separately flagged Chinese T1 candidates; it is not a full-text quotation bank. Build a small task-local, full-text-verified corpus before proposing language.

For every retained expression, record:

- exact fragment or abstracted pattern;
- rhetorical move and applicable section;
- source, locator, DOI or stable URL, access date, and license;
- first/corresponding author, verified author position, and expert-basis source when expert-authored work is prioritized;
- verbatim word count and reuse permission;
- scientific context and terms that must not be generalized;
- status: verified verbatim, abstracted, author-approved, or unverified.

Prefer abstracted rhetorical patterns over copied sentences. Never assemble prose by patchwriting. Quote only short, necessary fragments from sources that permit the intended use; attribute exact wording. Treat search snippets as discovery, not verification. Follow `references/literature-expression-corpus.md` and validate corpus files with `scripts/validate_expression_corpus.py`. Use `assets/module-expression-pilot.csv` only to test the D1–D13 source-to-pattern workflow; read `references/module-expression-pilot.md`, select a matching module, and preserve its human-review-pending/internal-pilot boundary. Do not treat 13 pilot seeds as a production phrasebook or as evidence of 1000 full texts per module.

For repeatable full-text work, read `references/fulltext-expression-production.md`. Prepare only authorized local HTML, text, or text-bearing PDF sources with `scripts/fulltext_expression_pipeline.py`; bind source, extracted text, locator anchor, candidate expression, and review basis by SHA-256. Do not mark a packet `qualified` until two identifiable independent human reviewers cover soil-domain and scientific-language review. Use `batch-report` to expose D1–D13 shortfalls and `export-qualified` to release only reviewed entries. Never use metadata counts to fill a full-text or expression-qualified quota.

## Execute the controlled writing workflow

1. Preserve the source artifact and create a working copy when editing files.
2. If template-aware full-artifact mode is active, create a `genre output contract` from `assets/genre-output-contract-template.json`. Record the current official/template authority, exact or unresolved length controls and counting units, required sections/files, format profile, cover profile, template snapshot/hash, and release gate. Validate it with `scripts/validate_genre_output_contract.py`. A missing controlled template is allowed only in a visibly labeled draft. In language-repair mode, skip this format contract and preserve the source layout.
3. Create a project profile for managed work. Record genre, authority, discipline, audience, language, terminology sources, edit permissions, policy state, and human approver.
4. Extract protected elements before rewriting. Use `scripts/audit_protected_elements.py extract` when plain-text or Markdown inputs are available. For DOCX language-only work, use `scripts/docx_language_repair.py extract`, bind every edit to the source and text-unit hashes, apply to a new file, and run its fidelity validator; do not rebuild the document from a template. For a scientific figure or table task, read `references/scientific-figure-description.md` and the matching parts of `references/scientific-visualization-types.md`. Create a user-controlled contract from `assets/figure-table-writing-contract-template.json` and validate it. Run `scripts/inspect_figure_table_image.py` on the exact attachment, inspect all required contrast renders, treat OCR as a candidate rather than evidence, and populate `assets/figure-description-evidence-template.json` before drafting. Let the user's current request control whether to produce results, analysis, a caption, a reading explanation, or separated results and analysis. Never add analysis when only description was requested. Do not reconstruct manuscript statistics from image pixels. Before delivery, audit the requested components separately, count with the contract's explicit unit, and validate the text against that contract.
5. Build or load a project termbase. Resolve concepts and senses before choosing surface wording.
6. Build a claim-and-source map for factual, comparative, novelty, mechanistic, legal, and normative statements.
7. Draft or revise according to the primary genre module and the selected genre-language profile. Keep unresolved content marked; never fill a gap with plausible boilerplate.
8. Apply discipline-specific language and the domain-register control, then bilingual correspondence checks when translating, then author-voice and naturalness editing. Naturalness is the final language pass, not permission to change substance. Classify “闭环” and “全链条” first as source-language interference, not merely as generic Chinese boilerplate: inspect the source phrase with `assets/translation-interference-rules.json`, recover the intended feedback, verification, custody, stage, or material-process relation, and run `scripts/audit_translation_interference.py` for bilingual segments. Do not use either term in generated Chinese or Chinese translation. They may remain only inside an immutable source quotation, official title, procurement clause, or locked user text under an exact-occurrence exception record, never as a defined-technical-term exception. Treat “顶层设计” and “新范式” by genre and evidential function: allow only an executable declared context; otherwise revise or block under strict release. Never globally allowlist a rejected term.
9. Run deterministic audits for protected elements, terminology records, expression provenance, policy state, format/length controls, and the managed-project manifest.
10. For complete artifacts, select the route in `assets/genre-artifact-profiles.json`. Use `scripts/build_chinese_professional_document.js` plus `scripts/validate_chinese_professional_document.py` for general DOCX genres, the specialized technical-bid builder and validator for procurement work, and `scripts/build_chinese_scientific_visual.js` plus `scripts/validate_chinese_scientific_visual.py` for posters or slides. Render with locked fonts using `scripts/render_artifact.py`, inspect every page or slide PNG, correct every visible defect, and repeat after changes. Any static visible DOCX TOC uses two passes: render once, derive heading page numbers with `scripts/derive_toc_page_map.py`, rebuild with `--toc-page-map`, and require a complete stable page map.
11. Compare the exact deliverable with the source and governing requirements. Report unresolved scientific, legal, policy, format, or terminology decisions.
12. Obtain human approval. Never label a document submission-ready, filing-ready, or publication-ready solely because local checks pass.

## Control the output

Match output depth to the request:

- For a single term or sentence, return the decision or revision plus only material caveats.
- For a scientific figure or table, follow the user's requested component and length exactly. When both description and analysis are requested, separate the evidence-bound results paragraph from the concise scientific analysis; otherwise return only the requested component. Run `scripts/audit_scientific_figure_description.py`; exact subjects, comparison scope, statistical basis, and evidence strength take priority over visual adjectives, metadiscourse, generic hedges, or extra commentary.
- For an audit, return findings without changing the source.
- For a substantive revision, return clean text, material-change notes, term decisions, and unresolved items. Preserve source formatting unless structural or format edits were authorized.
- For translation, return the requested clean or bilingual text plus an alignment report for high-risk elements.
- For managed projects, produce or update only the project records required by risk and scope. Do not create template, cover, or render records for a language-only repair.
- For a complete professional artifact, deliver its editable native file and, when requested or required for verification, a render-locked PDF. Do not substitute Markdown for a requested DOCX, PPTX, poster, presentation, report, standard draft, patent draft, application draft, or technical bid.

Never include chat residue, generic praise, invented confidence scores, an “AI percentage”, or universal claims that prose is purely human or undetectable. If NAR-1.0 passes, use only its scoped zero-residual assertion without deleting its provenance limitation. Use the measurable release criteria in `references/evaluation-and-release.md`.

## Standalone artifact mode and optional extensions

For all 29 genre routes, validate `assets/genre-artifact-profiles.json`, create a task specification, generate the routed DOCX or PPTX, run the corresponding structural validator, render to PDF/PNG with locked fonts, and inspect every page or slide. Read `references/genre-artifact-engineering.md`. A controlled format is mandatory before release wherever the route marks it required; a fallback profile is only a visibly labeled draft.

The Chinese soil-science technical-bid route adds the following specialized checks without another Skill:

1. create and validate a task-local format/length/template/cover contract from `assets/genre-output-contract-template.json`;
2. create a task-local content specification from `assets/technical-bid-spec-template.json`;
3. apply `references/genre-technical-bids.md`, `references/chinese-professional-document-format.md`, and `references/genre-format-length-template-registry.md`;
4. prepare SHA-256-locked Noto Serif/Sans CJK fonts with `scripts/prepare_open_fonts.py`; set Chinese body/headings to the appropriate pinned fonts and all Latin, numeral, variable, and Latin-name runs to Times New Roman;
5. build the first-pass editable DOCX with `scripts/build_chinese_technical_bid.js`;
6. validate package structure, A4 geometry, all font slots, body size, 1.5 line spacing, two-character first-line indent, heading keep-with-next, plain cover, no decorative shading/frames, headings, tables, fields, required scientific distinctions, placeholders, and chat residue with `scripts/validate_chinese_technical_bid.py`;
7. audit professional-language residuals with `scripts/audit_chinese_professional_style.py --fail-on-register-warnings`; do not release while an ambiguous register warning remains undisposed;
8. render DOCX to PDF and every page to PNG with `scripts/render_artifact.py --font-dir ...`; reject missing glyphs and unapproved fallback fonts;
9. derive the visible TOC page map with `scripts/derive_toc_page_map.py`, rebuild with `--toc-page-map`, re-render, and require a stable page map;
10. inspect every rendered page individually, revise the content specification or generator, and repeat until clean. A montage or text extraction is not a substitute for full-size inspection of every page.

Do not describe default A4 typography as a statutory format. The current tender document and supplied template always control. Use the bundled profile only when the procuring document is absent or silent, label unresolved fields, and reflow after the controlled template is supplied.

Other skills may extend exact methods, GIS computation, statistics, journal-specific formatting, or specialized file operations only when the user authorizes them. Their absence must not force any supported formal deliverable to degrade to plain text.

For cross-provider evaluation, compile the frozen answer-free request bundle with `scripts/model_provider_adapter.py` after reading `references/provider-adapter-execution.md`. Keep credentials outside generated artifacts. The adapter supports OpenAI, Anthropic, Gemini, DeepSeek, Qwen, Mistral, Cohere, Amazon Bedrock, Ollama, and a user-documented custom contract; it compiles requests and strictly normalizes real responses but does not call endpoints or award qualification. Only the hash-bound scoring and human-review workflow may update a project qualification matrix.

## Bundled validation commands

Run from the skill directory:

```bash
python3 scripts/validate_termbase.py assets/termbase-template.csv
python3 scripts/validate_termbase.py assets/termbase-soil-core-starter.csv
python3 scripts/validate_expression_corpus.py assets/expression-corpus-starter.csv
python3 scripts/validate_expression_corpus.py assets/module-expression-pilot.csv
python3 scripts/validate_module_expression_pilot.py assets/module-expression-pilot.csv
python3 scripts/fulltext_expression_pipeline.py validate assets/fulltext-expression-packet-template.json
# Prepare only an authorized local full-text source; then seal, review, validate, report, and export as described in the reference:
python3 scripts/fulltext_expression_pipeline.py batch-report path/to/packet-root --output path/to/fulltext-coverage.json --target-per-module 1000
python3 scripts/fulltext_expression_pipeline.py export-qualified path/to/packet-root --output path/to/qualified-expression-corpus.csv
python3 scripts/validate_expert_sources.py assets/expert-author-registry.csv assets/expert-first-author-source-starter.csv
python3 scripts/validate_literature_index.py assets/literature-index.csv --plan assets/corpus-query-plan.json --audit-sample assets/literature-audit-sample.csv
python3 scripts/profile_literature_index.py assets/literature-index.csv --audit-sample assets/literature-audit-sample.csv --output assets/literature-index-profile.json
python3 scripts/validate_naturalness_review.py assets/naturalness-review-template.json
python3 scripts/validate_project_manifest.py assets/review-manifest-template.json
python3 scripts/validate_model_qualification_matrix.py assets/model-qualification-matrix.csv
python3 scripts/model_qualification_harness.py validate-suite assets/model-qualification-probe-suite.json
python3 scripts/model_provider_adapter.py validate-contracts assets/provider-adapter-contracts.json
# Compile without credentials; execute externally in an approved environment, then normalize the retained raw responses:
python3 scripts/model_provider_adapter.py compile --contracts assets/provider-adapter-contracts.json --requests path/to/requests.answer-free.jsonl --system-prompt path/to/system-prompt.txt --provider openai --model-id EXACT_MODEL --output-dir path/to/compiled-run
python3 scripts/model_provider_adapter.py normalize --manifest path/to/compiled-run/adapter-manifest.json --raw-responses path/to/raw-responses.jsonl --output path/to/responses.normalized.jsonl --receipt path/to/normalization-receipt.json
# Prepare an answer-free, synthetic smoke run for one exact endpoint configuration:
python3 scripts/model_qualification_harness.py prepare --suite assets/model-qualification-probe-suite.json --output-dir path/to/model-run --provider openai --endpoint-type responses --model-id EXACT_MODEL --model-revision EXACT_REVISION --adapter-id EXACT_ADAPTER --system-prompt-sha256 64_LOWERCASE_HEX
# After the adapter writes path/to/model-run/responses.normalized.jsonl:
python3 scripts/model_qualification_harness.py evaluate --suite assets/model-qualification-probe-suite.json --manifest path/to/model-run/run-manifest.json --responses path/to/model-run/responses.normalized.jsonl --receipt path/to/model-run/smoke-receipt.json --evaluator RESPONSIBLE_PERSON --executed-at ISO_8601_WITH_TIMEZONE --profile-verified
python3 scripts/model_qualification_harness.py validate-receipt --suite assets/model-qualification-probe-suite.json --manifest path/to/model-run/run-manifest.json --responses path/to/model-run/responses.normalized.jsonl --receipt path/to/model-run/smoke-receipt.json
python3 scripts/validate_genre_language_profiles.py assets/genre-language-profiles.json
python3 scripts/validate_domain_register_lexicon.py assets/domain-register-lexicon.json
python3 scripts/test_domain_register_controls.py assets/domain-register-lexicon.json
python3 scripts/validate_translation_interference_rules.py assets/translation-interference-rules.json --cases assets/translation-interference-cases.jsonl --register assets/domain-register-lexicon.json
python3 scripts/audit_translation_interference.py path/to/bilingual-segments.jsonl --report path/to/translation-interference-report.json
python3 scripts/audit_scientific_figure_description.py validate-cases assets/scientific-figure-description-cases.jsonl
python3 scripts/audit_scientific_figure_description.py audit path/to/figure-results.txt --manifest path/to/figure-evidence.json --report path/to/figure-results-audit.json
python3 scripts/inspect_figure_table_image.py path/to/figure.png --output-dir path/to/figure-preflight --expected-text "expected label"
python3 scripts/validate_figure_table_writing_contract.py assets/figure-table-writing-contract-template.json
python3 scripts/count_chinese_text.py path/to/figure-results.txt --unit han_characters_plus_alnum_tokens --minimum 500 --maximum 800
python3 scripts/validate_figure_table_writing_contract.py path/to/task-contract.json --text path/to/figure-results.txt
python3 scripts/validate_chinese_writing_blind_review.py assets/chinese-writing-blind-review-template.json
python3 scripts/validate_domain_register_authority_sources.py assets/domain-register-authority-source-registry.csv
python3 scripts/validate_domain_register_learning_ledger.py assets/domain-register-learning-ledger-template.csv
python3 scripts/validate_domain_register_learning_ledger.py assets/domain-register-learning-ledger.csv --lexicon assets/domain-register-lexicon.json --source-registry assets/domain-register-source-registry.csv
python3 scripts/validate_genre_template_registry.py assets/genre-template-registry.json
python3 scripts/validate_genre_artifact_profiles.py assets/genre-artifact-profiles.json
python3 scripts/validate_genre_output_contract.py assets/genre-output-contract-template.json
python3 scripts/docx_language_repair.py extract path/to/source.docx --output path/to/units.json
python3 scripts/docx_language_repair.py apply path/to/source.docx path/to/repair-plan.json path/to/repaired.docx --receipt path/to/repair-receipt.json
python3 scripts/docx_language_repair.py validate path/to/source.docx path/to/repaired.docx --plan path/to/repair-plan.json
node scripts/build_chinese_professional_document.js --spec assets/professional-document-spec-template.json --profiles assets/genre-artifact-profiles.json --output path/to/document.docx
python3 scripts/validate_chinese_professional_document.py path/to/document.docx --spec assets/professional-document-spec-template.json --profiles assets/genre-artifact-profiles.json --allow-placeholders
node scripts/build_chinese_scientific_visual.js --spec assets/professional-visual-spec-template.json --profiles assets/genre-artifact-profiles.json --output path/to/poster.pptx
python3 scripts/validate_chinese_scientific_visual.py path/to/poster.pptx --spec assets/professional-visual-spec-template.json --profiles assets/genre-artifact-profiles.json --allow-placeholders
python3 scripts/validate_chinese_technical_bid.py path/to/bid.docx --allow-placeholders
python3 scripts/audit_chinese_professional_style.py path/to/bid.docx --fail-on-register-warnings
# Only when a controlled source requires an exact occurrence:
python3 scripts/audit_chinese_professional_style.py path/to/bid.docx --write-exception-candidates path/to/candidates.json
python3 scripts/audit_chinese_professional_style.py path/to/bid.docx --exception-record path/to/hash-bound-exceptions.json
python3 scripts/prepare_open_fonts.py --output-dir path/to/fonts --receipt path/to/font-receipt.json
python3 scripts/render_artifact.py path/to/document.docx --output-dir path/to/render --emit-pdf --font-dir path/to/fonts
python3 scripts/render_artifact.py path/to/poster.pptx --output-dir path/to/poster-render --emit-pdf --font-dir path/to/fonts --font-profile visual
python3 scripts/test_all_genre_docx_routes.py
python3 scripts/build_artifact_profile_qa_set.py --output-dir path/to/profile-qa --font-dir path/to/fonts
python3 scripts/validate_artifact_profile_qa_manifest.py path/to/profile-qa/qa-manifest.json --require-visual-pass
python3 scripts/run_regression_tests.py
```

These scripts check structure and deterministic invariants. They do not certify scientific correctness, originality, patentability, legal sufficiency, fundability, standards compliance, authorship, or acceptance.

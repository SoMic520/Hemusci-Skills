# Literature expression corpus

## Purpose

Use literature to learn how a field performs rhetorical moves, not to mine sentences for covert reuse. Build a corpus organized by discipline, genre, section, study design, rhetorical move, and language direction.

Examples of rhetorical moves:

- establish a bounded problem;
- define a term or operational measure;
- identify a verified knowledge gap;
- state an objective, question, or hypothesis;
- justify a method choice;
- report a primary result without interpretation;
- compare with prior work;
- introduce an alternative explanation;
- delimit inference or generalizability;
- state practical or theoretical implications;
- transition between evidence levels;
- formulate a standard requirement, patent feature, grant rationale, or report finding.

## Source selection

Prefer current high-quality sources that match the task. For reusable verbatim fragments, prefer CC0, public-domain, CC BY, or user-authorized sources. A high-impact venue is not automatically a language authority, and a highly cited sentence can still be unsuitable for another design or genre.

For top-journal or Chinese-language work, also read `top-tier-and-chinese-corpus.md`. A Chinese deliverable requires a Chinese-native corpus; do not build it only by translating English examples.

Verify the full source. Record DOI/URL, exact locator, license, access date, language, discipline, genre, section, study design, and context. Do not verify from a search snippet.

## Corpus entry types

- `verbatim`: a short exact fragment with verified locator and reuse-compatible license;
- `abstracted`: a source-informed syntactic or rhetorical pattern with source-specific content removed;
- `author_approved`: language from the user’s own or licensed corpus;
- `negative_example`: wording retained only to prevent overclaiming, ambiguity, or genre error;
- `candidate`: discovery record that cannot be used until verified.

Validate with `scripts/validate_expression_corpus.py`. The validator rejects unverifiable verbatim entries, missing licenses/locators, and fragments above the configured word limit.

## Safe transformation

For each source expression:

1. identify the rhetorical function;
2. identify the grammatical relation that realizes it;
3. remove source-specific entities, claims, numbers, and novelty;
4. write an abstract pattern;
5. generate a new sentence only from the user’s verified content;
6. compare the new sentence against source wording to avoid distinctive phrase copying;
7. cite the scientific idea where required, even when wording is new.

Do not concatenate fragments from multiple papers. Do not use a quotation as a substitute for the user’s evidence. Do not erase attribution from a distinctive formulation.

## Starter corpus

`assets/expression-corpus-starter.csv` contains a small, auditable seed set. Exact fragments are deliberately short and come from open-licensed soil-science sources. They demonstrate the record format; they are not a phrasebook to paste into manuscripts.

Expand the corpus task by task. Keep a task-local shortlist rather than loading the complete corpus into every model call.

For repeatable expansion, use `fulltext-expression-production.md` and `scripts/fulltext_expression_pipeline.py`. The pipeline binds an authorized local source snapshot, searchable extracted text, locator anchor, expression candidate, and two-human-review basis by SHA-256; its batch report keeps `prepared`, `fulltext_verified`, and `expression_qualified` counts separate for every D1–D13 module. A prepared or automatically located packet is not a production expression.

For Chinese tasks, normally include at least three verified Chinese sources from the matching artifact type. For a journal manuscript, include Chinese high-quality journal articles from the same or adjacent discipline; for grants, patents, standards, or reports, include governing Chinese official materials because journal prose does not determine those genres.

## Output when asked “how do papers say this?”

Return:

1. the intended rhetorical move;
2. two or three verified short examples or abstracted patterns;
3. why each fits or does not fit the user’s study;
4. one newly composed option bound to the user’s facts;
5. sources, locators, license/status, and any unresolved terminology.

Do not present a polished sentence until the underlying claim and evidence are supplied or clearly marked as placeholders.

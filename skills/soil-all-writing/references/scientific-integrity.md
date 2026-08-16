# Scientific integrity and fidelity

## Bind prose to evidence

Treat fluent text as unverified until its claims are bound to a source or to the project’s own verified record. Assign identifiers when work is managed:

- `S` for sources;
- `C` for claims;
- `N` for numeric facts;
- `M` for methods;
- `R` for results;
- `T` for terminology decisions;
- `P` for policy or governing requirements;
- `Q` for exact quotations.

Record the proposition, source locator, verification state, verifier, and date. A search result, abstract, generated summary, or citation found in another article is discovery evidence, not verified support.

## Preserve scientific force

Audit verbs and qualifiers against the design and evidence:

- descriptive: observed, measured, characterized, was associated with;
- comparative: was higher/lower under the stated comparison and uncertainty;
- predictive: predicted or explained under a stated model and validation setting;
- mechanistic: mediated, controlled, or caused only when the design supports that inference;
- provisional: may, might, suggests, is consistent with, remains uncertain.

Do not delete a hedge merely because it looks repetitive. Do not add hedges indiscriminately. Calibrate the verb to the evidence.

## Protect the scientific record

Protect and reconcile:

- numbers, signs, decimal places, ranges, uncertainty, denominators, sample sizes, and analysis populations;
- units and quantity symbols;
- equations, isotope notation, chemical species, gene/protein names, taxa, soil horizons, sample IDs, coordinates, and dates;
- citation clusters, DOI/URL values, figure/table/equation references, and supplement labels;
- classification system, edition, diagnostic horizon, qualifier, taxon, and capitalization;
- methods actually performed, deviations, null findings, failed analyses, adverse or unexpected observations;
- scope, limitations, alternative explanations, and generalizability.

Use `scripts/audit_protected_elements.py` to catch exact-token loss or addition in plain text. Treat the result as a gate, not proof of semantic equivalence.

## Control additions and omissions

Never fabricate a bridge sentence that implies an unsupported mechanism. Never add “well known”, “widely recognized”, “studies show”, or “experts agree” without a specific verified source. Never omit inconvenient null or negative findings when they belong to the record.

Mark missing information as `[UNRESOLVED: ...]` in drafts or list it outside clean prose. Do not turn placeholders into plausible boilerplate.

## Separate language and scientific decisions

Classify every material change as:

- linguistic clarification;
- terminology normalization;
- evidence-strength correction;
- scientific interpretation change;
- structural change;
- policy/legal/normative change.

The first two may be editor-approved within granted authority. The rest require an accountable human decision and source trace.

## Confidentiality and disclosure

Before external processing, classify the material as public, internal, confidential, restricted, personal, patent-sensitive, embargoed, or peer-review confidential. Check the user’s authority, provider retention policy, institution/funder/venue rules, and contractual restrictions. Prefer local processing when status is unclear.

Record AI assistance truthfully when required. Do not create a false “no AI used” statement or optimize wording to evade disclosure.

## Release gate

Require all of the following before calling a language deliverable final:

1. protected-element audit passes or every difference is approved;
2. no unresolved fabricated or unverified content is present;
3. terminology choices have source/status records;
4. claims and quotations have locators;
5. genre and policy sources are current for the intended use;
6. material semantic, scientific, legal, and normative changes are approved;
7. the accountable human has reviewed the exact deliverable.

Passing local checks does not establish scientific validity, legal sufficiency, patentability, fundability, standards compliance, authorship, or acceptance.

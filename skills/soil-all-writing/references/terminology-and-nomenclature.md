# Terminology and nomenclature

## Work concept-first

Resolve the concept, sense, discipline, method, classification system, jurisdiction, and time/version before choosing a Chinese or English term. Do not assume one surface form has one translation or that translation is symmetric.

Create one termbase record per concept/sense. Required fields are defined in `assets/termbase-template.csv` and enforced by `scripts/validate_termbase.py`.

## Apply the authority order

1. governing law, standard, patent terminology, classification system, or venue instruction;
2. official national terminology publication;
3. international scientific body or classification manual;
4. current authoritative handbook, consensus, or method standard;
5. consistent usage in a verified field corpus;
6. project preference or author-approved local term.

Project terms may be locked for consistency. If a locked term conflicts with a governing source, retain neither silently: report the conflict and request an accountable decision.

## Record status, not false certainty

Use:

- `proposed`: source-backed project candidate awaiting decision;
- `preferred`: selected preferred form, with approval fields completed;
- `admitted`: acceptable non-preferred form for a defined context;
- `deprecated`: retained only for search or historical interpretation;
- `forbidden`: form explicitly excluded in the project and reason recorded;
- `unverified`: discovery candidate only; do not present as authoritative;
- `approved`: accountable reviewer has approved the concept record;
- `locked`: approved wording that must remain unchanged in the named artifact.

Status is not the same as source verification. Record the authority source, URL, version, decision note, approver, and date. A `proposed` term can be well sourced but is not yet a project decision.

Record preferred, admitted, deprecated, and forbidden forms separately. Preserve search aliases without allowing them into final prose automatically.

## Control soil classification names

Store the system and edition with every classification record. Preserve official capitalization, qualifiers, formative elements, hyphens, and diagnostic horizon/property/material names. Do not translate official names ad hoc. When comparing systems, describe correlation limits instead of asserting equivalence.

## Control biological and chemical names

- Follow the governing nomenclatural code and venue for taxonomic ranks, italics, abbreviations, strain IDs, and authorities.
- Protect gene and protein capitalization/italics according to organism-specific conventions.
- Preserve chemical formulae, charge, oxidation state, hydration, isotope, stereochemistry, and speciation.
- Distinguish element totals, operational fractions, chemical species, and bioaccessible/bioavailable fractions.

## Control quantities, units, and statistics

Use the current SI Brochure plus field and venue requirements. Maintain a space between number and unit except where the governing convention differs. Use upright unit symbols, correct capitalization, unpluralized symbols, and unambiguous products/quotients. Do not normalize a valid unit or convert values without explicit authorization and a recorded conversion.

Protect statistical symbols, test names, model terms, confidence/credible intervals, effect estimates, transformations, and multiple-comparison procedures. Do not replace `P > 0.05` with “no effect” or turn a prediction interval into a confidence interval.

## Term decision output

For a disputed or high-risk term, report:

1. recommended form and language variety;
2. concept/sense and operational definition;
3. permitted alternatives and contexts;
4. forms to avoid and why;
5. source, edition, locator, verification status, and access date;
6. project-wide occurrences that require synchronization.

Do not perform elegant variation on technical terms. Repetition is preferable to referential ambiguity.

`assets/termbase-soil-core-starter.csv` provides deliberately provisional high-risk soil terms. It is a decision seed, not a universal bilingual dictionary.

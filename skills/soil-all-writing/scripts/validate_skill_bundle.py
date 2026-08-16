#!/usr/bin/env python3
"""Check that the portable soil-science language Skill bundle is complete."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = [
    "SKILL.md", "agents/openai.yaml",
    "references/scientific-integrity.md", "references/policy-and-sources.md",
    "references/requirements-coverage.md",
    "references/corpus-scale-and-qualification.md", "references/naturalness-assurance.md",
    "references/existing-skill-integration-audit.md",
    "references/discipline-modules.md", "references/terminology-and-nomenclature.md",
    "references/translation-and-alignment.md", "references/expert-language.md",
    "references/genre-language-calibration.md", "references/scientific-figure-description.md",
    "references/scientific-visualization-types.md",
    "references/domain-register-and-word-control.md",
    "references/humanizer-zh-gap-analysis.md",
    "references/literature-expression-corpus.md", "references/fulltext-expression-production.md",
    "references/module-expression-pilot.md",
    "references/top-tier-and-chinese-corpus.md",
    "references/model-portability.md", "references/provider-adapter-execution.md",
    "references/artifact-and-companion-routing.md",
    "references/docx-language-repair-fidelity.md",
    "references/genre-artifact-engineering.md",
    "references/genre-format-length-template-registry.md",
    "references/evaluation-and-release.md", "references/genre-grants.md",
    "references/genre-patents.md", "references/genre-standards.md",
    "references/genre-reports-and-investigations.md",
    "references/genre-technical-bids.md", "references/chinese-professional-document-format.md",
    "references/genre-papers-and-peer-review.md",
    "references/genre-posters-and-presentations.md",
    "references/genre-other-scientific-communication.md",
    "assets/termbase-template.csv", "assets/termbase-soil-core-starter.csv", "assets/source-ledger-template.csv",
    "assets/expression-corpus-starter.csv", "assets/module-expression-pilot.csv",
    "assets/fulltext-expression-packet-template.json",
    "assets/chinese-source-registry.csv",
    "assets/corpus-curation-matrix.csv",
    "assets/corpus-query-plan.json", "assets/literature-index.csv",
    "assets/literature-audit-sample.csv", "assets/literature-index-profile.json",
    "assets/naturalness-review-template.json", "assets/chinese-writing-blind-review-template.json",
    "assets/expert-author-registry.csv", "assets/expert-first-author-source-starter.csv",
    "assets/project-profile-template.yaml", "assets/protected-elements-template.json",
    "assets/review-manifest-template.json", "assets/model-profiles-template.yaml",
    "assets/provider-adapter-contracts.json", "assets/custom-provider-adapter-template.json",
    "assets/technical-bid-spec-template.json", "assets/genre-output-contract-template.json",
    "assets/professional-document-spec-template.json", "assets/professional-visual-spec-template.json",
    "assets/oral-presentation-spec-template.json", "assets/genre-artifact-profiles.json",
    "assets/cover-profile-template.json", "assets/genre-template-registry.json",
    "assets/genre-language-profiles.json", "assets/domain-register-lexicon.json",
    "assets/translation-interference-rules.json", "assets/translation-interference-cases.jsonl",
    "assets/figure-description-evidence-template.json", "assets/scientific-figure-description-cases.jsonl",
    "assets/figure-table-writing-contract-template.json",
    "assets/domain-register-exception-template.json", "assets/domain-register-learning-ledger-template.csv",
    "assets/domain-register-learning-ledger.csv", "assets/domain-register-source-registry.csv",
    "assets/domain-register-authority-source-registry.csv",
    "assets/docx-language-repair-plan-template.json",
    "assets/evaluation-cases.jsonl", "assets/model-qualification-matrix.csv",
    "assets/model-qualification-probe-suite.json",
    "scripts/audit_protected_elements.py", "scripts/validate_termbase.py",
    "scripts/validate_expression_corpus.py", "scripts/validate_module_expression_pilot.py",
    "scripts/fulltext_expression_pipeline.py",
    "scripts/validate_expert_sources.py",
    "scripts/build_literature_index.py", "scripts/build_crossref_literature_index.py",
    "scripts/merge_chinese_openalex_records.py", "scripts/validate_literature_index.py",
    "scripts/profile_literature_index.py", "scripts/validate_naturalness_review.py",
    "scripts/validate_chinese_writing_blind_review.py",
    "scripts/validate_project_manifest.py", "scripts/validate_model_qualification_matrix.py",
    "scripts/model_qualification_harness.py", "scripts/model_provider_adapter.py",
    "scripts/build_chinese_technical_bid.js", "scripts/validate_chinese_technical_bid.py",
    "scripts/validate_genre_output_contract.py", "scripts/audit_chinese_professional_style.py",
    "scripts/docx_language_repair.py",
    "scripts/validate_genre_language_profiles.py", "scripts/validate_domain_register_lexicon.py",
    "scripts/validate_translation_interference_rules.py", "scripts/audit_translation_interference.py",
    "scripts/audit_scientific_figure_description.py", "scripts/count_chinese_text.py",
    "scripts/inspect_figure_table_image.py", "scripts/validate_figure_table_writing_contract.py",
    "scripts/test_domain_register_controls.py", "scripts/validate_domain_register_learning_ledger.py",
    "scripts/validate_domain_register_authority_sources.py",
    "scripts/validate_genre_template_registry.py", "scripts/validate_genre_artifact_profiles.py",
    "scripts/build_chinese_professional_document.js", "scripts/validate_chinese_professional_document.py",
    "scripts/build_chinese_scientific_visual.js", "scripts/validate_chinese_scientific_visual.py",
    "scripts/test_all_genre_docx_routes.py", "scripts/build_artifact_profile_qa_set.py",
    "scripts/validate_artifact_profile_qa_manifest.py",
    "scripts/prepare_open_fonts.py", "scripts/derive_toc_page_map.py", "scripts/render_artifact.py",
    "scripts/validate_skill_bundle.py", "scripts/run_regression_tests.py",
]
PROVIDERS = [
    "OpenAI", "Claude", "Gemini", "DeepSeek", "Qwen", "Mistral", "Cohere",
    "Amazon Bedrock", "Ollama", "自定义接口",
]
REQUIRED_EVALUATION_CATEGORIES = {
    "protected_elements", "epistemic_strength", "statistics", "classification",
    "translation", "grant_policy", "patent", "standard", "investigation_report",
    "paper", "poster", "citation_integrity", "prompt_injection", "confidentiality",
    "structured_output", "naturalness_assurance", "domain_register",
    "genre_calibration",
}


def main() -> int:
    errors: list[str] = []
    for relative in EXPECTED:
        if not (ROOT / relative).is_file():
            errors.append(f"missing bundle file: {relative}")
    skill_path = ROOT / "SKILL.md"
    if skill_path.is_file():
        skill = skill_path.read_text(encoding="utf-8")
        if not re.match(r"^---\nname: soil-all-writing\ndescription: .+?\n---\n", skill, re.DOTALL):
            errors.append("SKILL.md frontmatter is invalid")
        if len(skill.splitlines()) > 500:
            errors.append("SKILL.md exceeds 500 lines")
        for relative in EXPECTED:
            if relative.startswith("references/") and relative not in skill and relative not in {
                "references/top-tier-and-chinese-corpus.md"
            }:
                errors.append(f"SKILL.md does not route to {relative}")
    model_ref = ROOT / "references/model-portability.md"
    if model_ref.is_file():
        model_text = model_ref.read_text(encoding="utf-8")
        for provider in PROVIDERS:
            if provider.casefold() not in model_text.casefold():
                errors.append(f"model portability reference missing {provider}")
    eval_path = ROOT / "assets/evaluation-cases.jsonl"
    if eval_path.is_file():
        ids: set[str] = set()
        categories: set[str] = set()
        for line_number, line in enumerate(eval_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"evaluation line {line_number}: {exc}")
                continue
            case_id = record.get("case_id")
            if not case_id:
                errors.append(f"evaluation line {line_number}: missing case_id")
            elif case_id in ids:
                errors.append(f"evaluation line {line_number}: duplicate case_id {case_id}")
            ids.add(case_id)
            category = record.get("category")
            if isinstance(category, str) and category:
                categories.add(category)
            else:
                errors.append(f"evaluation line {line_number}: missing category")
        if len(ids) < 12:
            errors.append("evaluation seed set must contain at least 12 cases")
        missing_categories = REQUIRED_EVALUATION_CATEGORIES - categories
        if missing_categories:
            errors.append(f"evaluation seed set missing categories: {', '.join(sorted(missing_categories))}")
    profile_path = ROOT / "assets/literature-index-profile.json"
    literature_path = ROOT / "assets/literature-index.csv"
    if profile_path.is_file() and literature_path.is_file():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            with literature_path.open(encoding="utf-8-sig", newline="") as handle:
                literature_count = sum(1 for row in csv.DictReader(handle) if any(row.values()))
            if profile.get("row_count") != literature_count:
                errors.append("literature-index-profile.json is stale relative to literature-index.csv")
            if profile.get("use_assessment", {}).get("release_state") != "metadata_index_only_human_audit_and_fulltext_verification_pending":
                errors.append("literature index profile must preserve its restricted release state")
        except (OSError, csv.Error, json.JSONDecodeError) as exc:
            errors.append(f"literature index profile audit: {exc}")
    for csv_name in ("chinese-source-registry.csv", "corpus-curation-matrix.csv", "expert-author-registry.csv", "expert-first-author-source-starter.csv", "model-qualification-matrix.csv"):
        path = ROOT / "assets" / csv_name
        if path.is_file():
            try:
                with path.open(encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                if not rows:
                    errors.append(f"{csv_name} has no seed records")
            except (OSError, csv.Error) as exc:
                errors.append(f"{csv_name}: {exc}")
    corpus_matrix = ROOT / "assets/corpus-curation-matrix.csv"
    if corpus_matrix.is_file():
        try:
            with corpus_matrix.open(encoding="utf-8-sig", newline="") as handle:
                rows = [row for row in csv.DictReader(handle) if any(row.values())]
            module_ids = [row.get("module_id", "").strip() for row in rows]
            expected_modules = {f"D{index}" for index in range(1, 14)}
            actual_modules = set(module_ids)
            missing_modules = sorted(expected_modules - actual_modules)
            extra_modules = sorted(actual_modules - expected_modules)
            duplicate_modules = sorted({item for item in module_ids if module_ids.count(item) > 1})
            if missing_modules:
                errors.append(f"corpus-curation-matrix.csv missing modules: {', '.join(missing_modules)}")
            if extra_modules:
                errors.append(f"corpus-curation-matrix.csv has unexpected modules: {', '.join(extra_modules)}")
            if duplicate_modules:
                errors.append(f"corpus-curation-matrix.csv has duplicate modules: {', '.join(duplicate_modules)}")
        except (OSError, csv.Error) as exc:
            errors.append(f"corpus-curation-matrix.csv module audit: {exc}")
    exception_template = ROOT / "assets/domain-register-exception-template.json"
    if exception_template.is_file():
        try:
            exception_data = json.loads(exception_template.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"domain-register exception template: {exc}")
        else:
            if exception_data.get("schema_version") != 2:
                errors.append("domain-register exception template must use schema_version 2")
            template_exceptions = exception_data.get("exceptions")
            if not isinstance(template_exceptions, list) or len(template_exceptions) != 1:
                errors.append("domain-register exception template must contain one example")
            else:
                required_exception_fields = {
                    "exception_id", "term", "paragraph_number", "occurrence_index",
                    "paragraph_sha256", "char_start", "char_end", "exception_scope",
                    "source_kind", "source_locator", "source_snapshot_sha256", "reason",
                    "approved_by", "approval_role", "approved_at",
                }
                missing = required_exception_fields - set(template_exceptions[0])
                if missing:
                    errors.append(
                        "domain-register exception template missing fields: "
                        + ", ".join(sorted(missing))
                    )
                if template_exceptions[0].get("exception_scope") != "exact_occurrence_only":
                    errors.append("domain-register exception template must bind an exact occurrence")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} bundle error(s)")
        return 1
    print("PASS: Skill bundle structure and coverage are complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate the language-only genre calibration profiles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPECTED_IDS = {
    "research_article", "review_and_meta_analysis", "grant_application",
    "patent_specification", "patent_claims", "standard_normative",
    "guideline_recommendation", "scientific_report", "investigation_report",
    "monitoring_report", "assessment_report", "decision_consulting_report",
    "technical_bid", "thesis_dissertation", "reviewer_response",
    "peer_review_report", "cover_letter", "conference_abstract",
    "academic_poster", "oral_presentation", "sop_protocol_field_manual",
    "data_code_documentation", "policy_brief", "public_summary_news",
    "expert_opinion", "project_progress_report", "meeting_minutes",
    "textbook_training", "professional_correspondence",
}

FORMALITY = {
    "scholarly", "scholarly_institutional", "legal_technical", "institutional",
    "institutional_scholarly", "institutional_technical", "institutional_contractual",
    "scholarly_professional", "scholarly_visual", "spoken_scholarly", "operational",
    "technical", "institutional_public", "public_plain", "institutional_professional",
    "educational_scholarly", "professional",
}
AUTHOR_PRESENCE = {"absent", "limited", "functional", "institutional", "explicit_accountable"}
MODALITY = {
    "descriptive_inferential", "prospective", "descriptive_legal", "legal_scope",
    "normative", "recommendatory", "descriptive", "evaluative",
    "contractual_prospective", "responsive", "explanatory", "procedural",
    "descriptive_procedural", "descriptive_prospective", "record", "request_confirm",
}
CAUSAL_CEILING = {"association_only", "evidence_bounded", "proposal_hypothesis", "not_applicable", "operational_if_validated"}
COMPRESSION = {"medium", "high", "mixed"}
REPETITION = {
    "eliminate_unfunctional", "preserve_method_repetition",
    "allow_controlled_term_repetition", "require_controlled_term_repetition",
    "allow_signposting_repetition", "allow_explanatory_repetition",
}
NATURALNESS = {"minimal", "controlled"}
CONTROL_KEYS = {
    "preserve_uncertainty", "separate_results_interpretation", "controlled_repetition",
    "preserve_normative_force", "preserve_legal_scope", "preserve_chain_of_custody",
    "preserve_proposal_status",
}
FORBIDDEN_KEYS = {
    "template", "template_id", "cover", "font", "font_size", "body_size_zh",
    "heading_sizes_zh", "line_spacing", "paragraph_after_lines", "margin", "margins",
    "page_size", "pagination", "render", "renderer",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    try:
        data = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        errors.append("profiles must be an array")
        profiles = []

    def scan_keys(value: object, locator: str = "root") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in FORBIDDEN_KEYS:
                    errors.append(f"{locator}: language profile contains forbidden format/template key '{key}'")
                scan_keys(child, f"{locator}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                scan_keys(child, f"{locator}[{index}]")

    scan_keys(data)
    seen: set[str] = set()
    by_id: dict[str, dict] = {}
    required_scalars = (
        "id", "genre", "primary_function", "default_formality", "audience",
        "author_presence", "modality", "causal_ceiling", "compression",
        "repetition_policy", "terminology_policy", "naturalness_strength",
    )
    required_lists = ("paragraph_moves", "preserve", "avoid")
    for index, profile in enumerate(profiles):
        locator = f"profiles[{index}]"
        if not isinstance(profile, dict):
            errors.append(f"{locator} must be an object")
            continue
        profile_id = profile.get("id")
        if not isinstance(profile_id, str) or not profile_id.strip():
            errors.append(f"{locator}.id must be a non-empty string")
            continue
        if profile_id in seen:
            errors.append(f"duplicate profile id: {profile_id}")
        seen.add(profile_id)
        by_id[profile_id] = profile
        for key in required_scalars:
            if not isinstance(profile.get(key), str) or not profile[key].strip():
                errors.append(f"{profile_id}.{key} must be a non-empty string")
        for key in required_lists:
            values = profile.get(key)
            if not isinstance(values, list) or not values or not all(isinstance(item, str) and item.strip() for item in values):
                errors.append(f"{profile_id}.{key} must be a non-empty string array")
        if profile.get("default_formality") not in FORMALITY:
            errors.append(f"{profile_id}.default_formality is not controlled")
        if profile.get("author_presence") not in AUTHOR_PRESENCE:
            errors.append(f"{profile_id}.author_presence is not controlled")
        if profile.get("modality") not in MODALITY:
            errors.append(f"{profile_id}.modality is not controlled")
        if profile.get("causal_ceiling") not in CAUSAL_CEILING:
            errors.append(f"{profile_id}.causal_ceiling is not controlled")
        if profile.get("compression") not in COMPRESSION:
            errors.append(f"{profile_id}.compression is not controlled")
        if profile.get("repetition_policy") not in REPETITION:
            errors.append(f"{profile_id}.repetition_policy is not controlled")
        if profile.get("naturalness_strength") not in NATURALNESS:
            errors.append(f"{profile_id}.naturalness_strength is not controlled")
        controls = profile.get("controls")
        if not isinstance(controls, dict):
            errors.append(f"{profile_id}.controls must be an object")
        else:
            missing_controls = CONTROL_KEYS - set(controls)
            extra_controls = set(controls) - CONTROL_KEYS
            if missing_controls:
                errors.append(f"{profile_id}.controls missing: {', '.join(sorted(missing_controls))}")
            if extra_controls:
                errors.append(f"{profile_id}.controls has unknown keys: {', '.join(sorted(extra_controls))}")
            for key in CONTROL_KEYS & set(controls):
                if not isinstance(controls[key], bool):
                    errors.append(f"{profile_id}.controls.{key} must be boolean")
        if not isinstance(profile.get("section_overrides"), dict):
            errors.append(f"{profile_id}.section_overrides must be an object")

    missing = EXPECTED_IDS - seen
    extra = seen - EXPECTED_IDS
    if missing:
        errors.append(f"missing required genre profiles: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"unexpected genre profiles: {', '.join(sorted(extra))}")

    def control(profile_id: str, key: str) -> bool | None:
        controls = by_id.get(profile_id, {}).get("controls", {})
        return controls.get(key) if isinstance(controls, dict) else None

    if control("grant_application", "preserve_proposal_status") is not True:
        errors.append("grant_application must preserve proposal status")
    if by_id.get("grant_application", {}).get("modality") != "prospective":
        errors.append("grant_application modality must be prospective")
    results = by_id.get("research_article", {}).get("section_overrides", {}).get("results", {})
    if results.get("interpretation_boundary") != "results_only":
        errors.append("research_article results must keep a results-only interpretation boundary")
    for profile_id in ("patent_claims", "standard_normative", "sop_protocol_field_manual"):
        if control(profile_id, "controlled_repetition") is not True:
            errors.append(f"{profile_id} must preserve controlled repetition")
    for profile_id in ("patent_specification", "patent_claims", "standard_normative", "technical_bid"):
        if control(profile_id, "preserve_legal_scope") is not True:
            errors.append(f"{profile_id} must preserve legal or contractual scope")
    for profile_id in ("investigation_report", "monitoring_report", "assessment_report", "technical_bid", "sop_protocol_field_manual"):
        if control(profile_id, "preserve_chain_of_custody") is not True:
            errors.append(f"{profile_id} must preserve traceability and custody records")
    if control("public_summary_news", "preserve_uncertainty") is not True:
        errors.append("public_summary_news must preserve uncertainty")

    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} genre-language profile error(s)")
        return 1
    print(f"PASS: {len(profiles)} genre-language profiles are complete and language-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

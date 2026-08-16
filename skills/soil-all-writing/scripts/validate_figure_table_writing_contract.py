#!/usr/bin/env python3
"""Validate a user-controlled scientific figure/table writing contract and optional text."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from count_chinese_text import COUNT_UNITS, count_text


ARTIFACT_KINDS = {"scientific_figure", "scientific_table", "scientific_figure_or_table", "mixed"}
REQUEST_SOURCES = {"explicit_user", "authority", "skill_default"}
COMPONENTS = {"results", "analysis", "caption", "title", "reading_explanation"}
LOCATOR_STYLES = {"content_first_locator_later", "lead_locator_allowed", "venue_controlled", "not_applicable"}
LOCATOR_SOURCES = {"user", "artifact", "authority", "none"}
ENFORCEMENTS = {"hard_user_limit", "authority_controlled", "soft_default", "none"}
ANALYSIS_DEPTHS = {"none", "brief", "standard", "extended"}
CONNECTOR_MODES = {"functional_context", "user_controlled", "venue_controlled"}
BLANK_POLICIES = {"omit_unless_material", "report_material", "report_all", "user_controlled"}


def string_array(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def validate(payload: object, text: str | None = None) -> tuple[list[str], list[str], dict[str, int] | None]:
    errors: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] | None = None
    if not isinstance(payload, dict):
        return ["contract root must be an object"], warnings, counts
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(payload.get("contract_id"), str) or not payload.get("contract_id"):
        errors.append("contract_id is required")
    if payload.get("language") not in {"zh-CN", "en", "bilingual"}:
        errors.append("language is invalid")
    if payload.get("artifact_kind") not in ARTIFACT_KINDS:
        errors.append("artifact_kind is invalid")
    if payload.get("request_source") not in REQUEST_SOURCES:
        errors.append("request_source is invalid")
    components = payload.get("requested_components")
    if not string_array(components) or not set(components).issubset(COMPONENTS):
        errors.append("requested_components must be a non-empty controlled string array")
        components = []
    if not string_array(payload.get("exact_user_requirements", [])):
        errors.append("exact_user_requirements must be a string array")

    locator = payload.get("locator")
    if not isinstance(locator, dict):
        errors.append("locator must be an object")
    else:
        if not isinstance(locator.get("provided"), bool):
            errors.append("locator.provided must be boolean")
        if locator.get("style") not in LOCATOR_STYLES:
            errors.append("locator.style is invalid")
        if locator.get("source") not in LOCATOR_SOURCES:
            errors.append("locator.source is invalid")
        if locator.get("provided") and not str(locator.get("value") or "").strip():
            errors.append("provided locator requires a value")
        if not locator.get("provided") and locator.get("source") != "none":
            errors.append("an absent locator must use source none")

    length = payload.get("length")
    if not isinstance(length, dict):
        errors.append("length must be an object")
        length = {}
    unit = length.get("counting_unit")
    if unit not in COUNT_UNITS | {"venue_defined", "not_applicable"}:
        errors.append("length.counting_unit is invalid")
    enforcement = length.get("enforcement")
    if enforcement not in ENFORCEMENTS:
        errors.append("length.enforcement is invalid")
    if length.get("source") not in REQUEST_SOURCES:
        errors.append("length.source is invalid")
    minimum = length.get("minimum")
    maximum = length.get("maximum")
    if minimum is not None and (not isinstance(minimum, int) or minimum < 0):
        errors.append("length.minimum must be null or a non-negative integer")
    if maximum is not None and (not isinstance(maximum, int) or maximum < 0):
        errors.append("length.maximum must be null or a non-negative integer")
    if isinstance(minimum, int) and isinstance(maximum, int) and maximum < minimum:
        errors.append("length.maximum must not be smaller than minimum")
    if enforcement in {"hard_user_limit", "authority_controlled"} and minimum is None and maximum is None:
        errors.append("hard or authority-controlled length requires a numeric boundary")
    if unit == "venue_defined" and not str(length.get("authority_definition") or "").strip():
        errors.append("venue_defined counting requires authority_definition")

    analysis = payload.get("analysis")
    if not isinstance(analysis, dict):
        errors.append("analysis must be an object")
        analysis = {}
    requested = analysis.get("requested")
    if not isinstance(requested, bool):
        errors.append("analysis.requested must be boolean")
    if analysis.get("depth") not in ANALYSIS_DEPTHS:
        errors.append("analysis.depth is invalid")
    maximum_sentences = analysis.get("maximum_sentences")
    if not isinstance(maximum_sentences, int) or maximum_sentences < 0:
        errors.append("analysis.maximum_sentences must be a non-negative integer")
    fraction = analysis.get("maximum_fraction")
    if not isinstance(fraction, (int, float)) or not 0 <= fraction <= 1:
        errors.append("analysis.maximum_fraction must be between 0 and 1")
    if requested and "analysis" not in components:
        errors.append("analysis.requested requires analysis in requested_components")
    if not requested and (analysis.get("depth") != "none" or maximum_sentences != 0 or fraction != 0):
        errors.append("analysis not requested must use depth none and zero limits")
    if requested and analysis.get("depth") == "none":
        errors.append("requested analysis cannot use depth none")
    if {"results", "analysis"}.issubset(set(components)) and payload.get("result_analysis_separated") is not True:
        errors.append("results and analysis must be separated")

    connector = payload.get("connector_policy")
    if not isinstance(connector, dict):
        errors.append("connector_policy must be an object")
    else:
        if connector.get("mode") not in CONNECTOR_MODES:
            errors.append("connector_policy.mode is invalid")
        for field in ("explicitly_allowed", "explicitly_avoided"):
            if not string_array(connector.get(field, [])):
                errors.append(f"connector_policy.{field} must be a string array")
        overlap = set(connector.get("explicitly_allowed", [])) & set(connector.get("explicitly_avoided", []))
        if overlap:
            errors.append("the same connector cannot be both allowed and avoided")

    blanks = payload.get("blank_cells")
    if not isinstance(blanks, dict):
        errors.append("blank_cells must be an object")
    else:
        if blanks.get("policy") not in BLANK_POLICIES:
            errors.append("blank_cells.policy is invalid")
        if not isinstance(blanks.get("material_to_claim"), bool):
            errors.append("blank_cells.material_to_claim must be boolean")
    if not string_array(payload.get("locked_terms", [])):
        errors.append("locked_terms must be a string array")

    if text is not None and unit in COUNT_UNITS:
        counts = count_text(text)
        selected = counts[unit]
        outside = (minimum is not None and selected < minimum) or (maximum is not None and selected > maximum)
        if outside and enforcement in {"hard_user_limit", "authority_controlled"}:
            errors.append(f"text count {selected} is outside the controlled range {minimum}–{maximum} ({unit})")
        elif outside and enforcement == "soft_default":
            warnings.append(f"text count {selected} is outside the default range {minimum}–{maximum} ({unit})")
    return errors, warnings, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--text", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.contract.read_text(encoding="utf-8"))
        text = args.text.read_text(encoding="utf-8") if args.text else None
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    errors, warnings, counts = validate(payload, text)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} figure/table writing-contract error(s)")
        return 1
    print(json.dumps({
        "status": "PASS",
        "contract_id": payload["contract_id"],
        "warnings": len(warnings),
        "counts": counts,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

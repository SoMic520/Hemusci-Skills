#!/usr/bin/env python3
"""Validate fallback artifact profiles and complete genre routing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


EXPECTED_GENRES = {
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
CHINESE_SIZE_NAMES = {
    "初号", "小初号", "一号", "小一号", "二号", "小二号", "三号", "小三号",
    "四号", "小四号", "五号", "小五号", "六号", "小六号", "七号", "八号",
}
ARTIFACT_KINDS = {"docx", "pptx_poster", "pptx_slides"}
COVER_MODES = {"formal_black_white", "title_page_only", "none", "poster_or_slide_master"}
CONTROLLED_RELEASE_GENRES = {
    "research_article", "review_and_meta_analysis", "grant_application",
    "patent_specification", "patent_claims", "standard_normative",
    "guideline_recommendation", "technical_bid", "thesis_dissertation",
    "cover_letter", "conference_abstract", "academic_poster",
    "oral_presentation", "sop_protocol_field_manual", "expert_opinion",
    "textbook_training",
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
    purpose = str(data.get("purpose") or "").casefold()
    if "ordinary language repair" not in purpose or "never override" not in purpose:
        errors.append("purpose must exclude ordinary language repair and preserve controlled-template priority")
    if data.get("activation") != "full_artifact_generation_or_explicit_template_aware_repair_only":
        errors.append("activation boundary is invalid")
    authority_order = data.get("authority_order")
    if not isinstance(authority_order, list) or len(authority_order) < 4:
        errors.append("authority_order must contain the complete precedence chain")
    elif authority_order[-1] != "skill_fallback_draft_profile":
        errors.append("Skill fallback must be the lowest authority")

    def scan_for_pt(value: object, locator: str = "root") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.endswith("_pt"):
                    errors.append(f"{locator}.{key}: point-size fields are forbidden in Chinese profiles")
                scan_for_pt(child, f"{locator}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                scan_for_pt(child, f"{locator}[{index}]")

    scan_for_pt(data)

    profiles = data.get("format_profiles")
    if not isinstance(profiles, list) or not profiles:
        errors.append("format_profiles must be a non-empty array")
        profiles = []
    profile_ids: set[str] = set()
    by_profile: dict[str, dict] = {}
    for index, profile in enumerate(profiles):
        locator = f"format_profiles[{index}]"
        if not isinstance(profile, dict):
            errors.append(f"{locator} must be an object")
            continue
        profile_id = profile.get("id")
        if not isinstance(profile_id, str) or not profile_id:
            errors.append(f"{locator}.id must be a non-empty string")
            continue
        if profile_id in profile_ids:
            errors.append(f"duplicate format profile: {profile_id}")
        profile_ids.add(profile_id)
        by_profile[profile_id] = profile
        if profile.get("artifact_kind") not in ARTIFACT_KINDS:
            errors.append(f"{profile_id}.artifact_kind is invalid")
        if profile.get("cover_mode") not in COVER_MODES:
            errors.append(f"{profile_id}.cover_mode is invalid")
        for key in ("page", "toc_mode", "header_footer_mode", "body_font_zh", "heading_font_zh", "latin_font"):
            if not isinstance(profile.get(key), str) or not profile[key]:
                errors.append(f"{profile_id}.{key} must be a non-empty string")
        if profile.get("latin_font") != "Times New Roman":
            errors.append(f"{profile_id}.latin_font must be Times New Roman")
        if profile.get("decorative_shading_allowed") is not False:
            errors.append(f"{profile_id} must disable decorative shading by default")
        if profile.get("decorative_frames_allowed") is not False:
            errors.append(f"{profile_id} must disable decorative frames by default")
        if profile.get("artifact_kind") == "docx":
            if profile.get("body_size_zh") not in CHINESE_SIZE_NAMES:
                errors.append(f"{profile_id}.body_size_zh must use a Chinese size name")
            if profile.get("table_body_size_zh") not in CHINESE_SIZE_NAMES:
                errors.append(f"{profile_id}.table_body_size_zh must use a Chinese size name")
            headings = profile.get("heading_sizes_zh")
            if not isinstance(headings, dict) or set(headings) != {"level_1", "level_2", "level_3", "level_4"}:
                errors.append(f"{profile_id}.heading_sizes_zh must define levels 1-4")
            elif any(value not in CHINESE_SIZE_NAMES for value in headings.values()):
                errors.append(f"{profile_id}.heading_sizes_zh contains a non-Chinese size name")
            if profile.get("body_line_spacing") not in {1.0, 1.25, 1.5, 2.0}:
                errors.append(f"{profile_id}.body_line_spacing is not a controlled multiple")
            if profile.get("first_line_indent_characters") not in {0, 2}:
                errors.append(f"{profile_id}.first_line_indent_characters must be 0 or 2")
            if profile.get("paragraph_after_lines") not in {0, 0.5, 1.0}:
                errors.append(f"{profile_id}.paragraph_after_lines must use line units")
        else:
            if profile.get("cover_mode") != "poster_or_slide_master":
                errors.append(f"{profile_id}: PPTX profiles require poster_or_slide_master")
            if not profile.get("size_control"):
                errors.append(f"{profile_id}: PPTX profiles require a controlled size statement")

    routes = data.get("genre_routes")
    if not isinstance(routes, list):
        errors.append("genre_routes must be an array")
        routes = []
    route_ids: set[str] = set()
    for index, route in enumerate(routes):
        locator = f"genre_routes[{index}]"
        if not isinstance(route, dict):
            errors.append(f"{locator} must be an object")
            continue
        genre_id = route.get("id")
        if not isinstance(genre_id, str) or not genre_id:
            errors.append(f"{locator}.id must be a non-empty string")
            continue
        if genre_id in route_ids:
            errors.append(f"duplicate genre route: {genre_id}")
        route_ids.add(genre_id)
        profile_id = route.get("format_profile_id")
        if profile_id not in by_profile:
            errors.append(f"{genre_id}: unknown format_profile_id {profile_id}")
        if not isinstance(route.get("controlled_template_required_for_release"), bool):
            errors.append(f"{genre_id}.controlled_template_required_for_release must be boolean")
        required_roles = route.get("required_roles")
        if not isinstance(required_roles, list) or not required_roles or not all(
            isinstance(role, str) and role for role in required_roles
        ):
            errors.append(f"{genre_id}.required_roles must be a non-empty string array")

    missing = EXPECTED_GENRES - route_ids
    extra = route_ids - EXPECTED_GENRES
    if missing:
        errors.append(f"missing genre routes: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"unexpected genre routes: {', '.join(sorted(extra))}")

    by_genre = {route.get("id"): route for route in routes if isinstance(route, dict)}
    role_labels = data.get("role_labels_zh")
    if not isinstance(role_labels, dict):
        errors.append("role_labels_zh must be an object")
        role_labels = {}
    required_role_ids = {
        role for route in routes if isinstance(route, dict)
        for role in route.get("required_roles", []) if isinstance(role, str)
    }
    for role in sorted(required_role_ids):
        label = role_labels.get(role)
        if not isinstance(label, str) or not label.strip() or not re.search(r"[\u3400-\u9fff]", label):
            errors.append(f"role_labels_zh.{role} must be a non-empty Chinese display label")
    for genre in CONTROLLED_RELEASE_GENRES:
        if by_genre.get(genre, {}).get("controlled_template_required_for_release") is not True:
            errors.append(f"{genre}: controlled/current template must be required before release")
    if by_profile.get(by_genre.get("academic_poster", {}).get("format_profile_id"), {}).get("artifact_kind") != "pptx_poster":
        errors.append("academic_poster must route to a PPTX poster profile")
    if by_profile.get(by_genre.get("oral_presentation", {}).get("format_profile_id"), {}).get("artifact_kind") != "pptx_slides":
        errors.append("oral_presentation must route to a PPTX slide profile")
    if by_genre.get("technical_bid", {}).get("format_profile_id") != "DOCX-FORMAL-REPORT-BW-1.0":
        errors.append("technical_bid must retain the formal black-white DOCX fallback")

    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} genre-artifact-profile error(s)")
        return 1
    print(f"PASS: {len(routes)} genres route to {len(profiles)} controlled fallback artifact profiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

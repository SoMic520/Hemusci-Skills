#!/usr/bin/env python3
"""Validate authority, length, template and cover controls for a deliverable."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse


LIMIT_STATES = {"controlled", "venue_controlled", "no_universal_limit", "controlled_source_missing"}
LIMIT_TYPES = {"hard", "recommended", "system_enforced", "internal_drafting_budget", "unknown"}
COUNT_UNITS = {
    "chars_including_punctuation", "chars_excluding_punctuation", "english_words", "pages",
    "slides", "minutes", "clauses", "figures_tables", "file_bytes", "items", "not_applicable", "unknown",
}
SERIOUS_GENRES = {
    "technical_bid", "procurement_response", "grant_application", "patent_application", "standard",
    "scientific_report", "research_report", "investigation_report", "monitoring_report", "assessment_report",
}
CHINESE_SIZE_NAMES = {
    "初号", "小初号", "一号", "小一号", "二号", "小二号", "三号", "小三号",
    "四号", "小四号", "五号", "小五号", "六号", "小六号", "七号", "八号",
}


def valid_sha256(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", value or ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        payload = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read contract: {exc}")
        return 1

    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    stage = payload.get("lifecycle_stage")
    if stage not in {"draft", "internal_review", "release"}:
        errors.append("lifecycle_stage must be draft, internal_review, or release")
    genre = str(payload.get("genre") or "")
    if not genre:
        errors.append("genre is required")

    authority = payload.get("authority") or {}
    source_state = authority.get("source_state")
    if source_state not in {"controlled", "venue_controlled", "no_universal_source", "controlled_source_missing"}:
        errors.append("authority.source_state is invalid")
    if stage == "release" and source_state == "controlled_source_missing":
        errors.append("release is blocked while the controlled source is missing")
    if source_state in {"controlled", "venue_controlled"}:
        for key in ("title", "version_or_year", "url", "source_locator", "access_date", "scope"):
            if not authority.get(key):
                errors.append(f"controlled authority requires {key}")
        if authority.get("url") and urlparse(str(authority["url"])).scheme not in {"http", "https"}:
            errors.append("authority.url must be an HTTP(S) official source")
        try:
            if authority.get("access_date"):
                date.fromisoformat(str(authority["access_date"]))
        except ValueError:
            errors.append("authority.access_date must use YYYY-MM-DD")

    controls = payload.get("length_controls")
    if not isinstance(controls, list) or not controls:
        errors.append("at least one length control is required")
        controls = []
    for index, control in enumerate(controls, 1):
        state = control.get("limit_state")
        kind = control.get("limit_type")
        unit = control.get("count_unit")
        if state not in LIMIT_STATES:
            errors.append(f"length control {index}: invalid limit_state")
        if kind not in LIMIT_TYPES:
            errors.append(f"length control {index}: invalid limit_type")
        if unit not in COUNT_UNITS:
            errors.append(f"length control {index}: invalid count_unit")
        if stage == "release" and (state == "controlled_source_missing" or kind == "unknown" or unit == "unknown"):
            errors.append(f"length control {index}: unresolved length semantics block release")
        if kind in {"hard", "system_enforced"}:
            if state != "controlled":
                errors.append(f"length control {index}: hard/system limit must be controlled")
            if not control.get("source_id") or not control.get("source_locator"):
                errors.append(f"length control {index}: hard/system limit lacks source and locator")
            if control.get("minimum") is None and control.get("maximum") is None:
                errors.append(f"length control {index}: hard/system limit lacks a numeric boundary")
        if state == "no_universal_limit" and kind not in {"internal_drafting_budget", "recommended"}:
            warnings.append(f"length control {index}: no universal limit; do not present it as official")

    cover = payload.get("cover_profile") or {}
    cover_mode = cover.get("mode")
    if cover_mode not in {"controlled_template", "formal_black_white", "title_page_only", "none", "poster_or_slide_master"}:
        errors.append("cover_profile.mode is invalid")
    if genre in SERIOUS_GENRES and cover_mode == "poster_or_slide_master":
        errors.append("serious professional genre cannot use a poster/slide cover profile")
    if genre in SERIOUS_GENRES and cover_mode == "formal_black_white":
        for key in ("prohibit_colored_bands", "prohibit_decorative_frames", "prohibit_boxed_metadata_table"):
            if cover.get(key) is not True:
                errors.append(f"formal black-white cover must set {key}=true")

    template = payload.get("template_profile") or {}
    if cover_mode == "controlled_template" or template.get("mode") == "controlled_template":
        if not valid_sha256(str(template.get("snapshot_sha256") or "")):
            errors.append("controlled template requires a locked SHA-256 snapshot")
    if stage == "release" and template.get("mode") == "controlled_template_not_received":
        errors.append("release is blocked until the controlled template is received")

    fmt = payload.get("format_profile") or {}
    pt_keys = sorted(key for key in fmt if str(key).endswith("_pt"))
    if payload.get("language") == "zh-CN" and pt_keys:
        errors.append(
            "Chinese document profiles must use Chinese size-name fields instead of *_pt: "
            + ", ".join(pt_keys)
        )
    body_size_zh = fmt.get("body_size_zh")
    if payload.get("language") == "zh-CN" and body_size_zh not in CHINESE_SIZE_NAMES:
        errors.append("format_profile.body_size_zh must use a standard Chinese size name")
    heading_sizes = fmt.get("heading_sizes_zh")
    if payload.get("language") == "zh-CN":
        if not isinstance(heading_sizes, dict) or not heading_sizes:
            errors.append("format_profile.heading_sizes_zh is required for Chinese documents")
        elif any(value not in CHINESE_SIZE_NAMES for value in heading_sizes.values()):
            errors.append("all format_profile.heading_sizes_zh values must be standard Chinese size names")
        table_size_zh = fmt.get("table_body_size_zh")
        if table_size_zh not in CHINESE_SIZE_NAMES:
            errors.append("format_profile.table_body_size_zh must use a standard Chinese size name")
    if fmt.get("latin_font") != "Times New Roman":
        errors.append("format_profile.latin_font must be Times New Roman")
    if genre in SERIOUS_GENRES:
        if fmt.get("decorative_shading_allowed") is not False:
            errors.append("serious professional genre must disable decorative shading by default")
        if fmt.get("decorative_frames_allowed") is not False:
            errors.append("serious professional genre must disable decorative frames by default")
    if fmt.get("body_line_spacing") is not None and float(fmt["body_line_spacing"]) < 1.0:
        errors.append("body line spacing cannot be below single spacing")
    if fmt.get("first_line_indent_characters") not in {0, 2}:
        warnings.append("unusual first-line indent; confirm against the controlled template")
    paragraph_after = fmt.get("paragraph_after_lines")
    if paragraph_after is not None and float(paragraph_after) < 0:
        errors.append("format_profile.paragraph_after_lines cannot be negative")

    if errors:
        for item in warnings:
            print(f"WARNING: {item}")
        for item in errors:
            print(f"ERROR: {item}")
        print(f"FAILED: {len(errors)} genre-output-contract error(s)")
        return 1
    digest = hashlib.sha256(args.path.read_bytes()).hexdigest()
    for item in warnings:
        print(f"WARNING: {item}")
    print(json.dumps({"status": "PASS", "genre": genre, "stage": stage, "sha256": digest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

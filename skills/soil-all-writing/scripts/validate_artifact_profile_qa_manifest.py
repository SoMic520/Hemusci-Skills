#!/usr/bin/env python3
"""Validate a rendered all-profile QA manifest, its hashes, receipts, and page images."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import struct


ROOT = Path(__file__).resolve().parents[1]
PASS_REVIEW = "pass_full_size_individual_agent_review"
PASS_STATUS = "structural_render_and_agent_visual_pass"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("not a valid PNG header")
    return struct.unpack(">II", header[16:24])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--profiles", type=Path, default=ROOT / "assets/genre-artifact-profiles.json")
    parser.add_argument("--require-visual-pass", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        registry = json.loads(args.profiles.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    profiles = {item["id"]: item for item in registry.get("format_profiles", [])}
    routes = {item["id"]: item for item in registry.get("genre_routes", [])}
    records = manifest.get("records")
    if not isinstance(records, list):
        errors.append("records must be an array")
        records = []
    if manifest.get("profile_count") != len(profiles) or len(records) != len(profiles):
        errors.append("profile_count and record count must equal the format-profile registry")
    if manifest.get("genre_route_count") != len(routes):
        errors.append("genre_route_count must equal the genre-route registry")
    if args.require_visual_pass:
        if manifest.get("status") != PASS_STATUS:
            errors.append(f"status must be {PASS_STATUS!r} when visual pass is required")
        if manifest.get("visual_review_scope") != "all_rendered_pages_and_slides":
            errors.append("visual_review_scope must cover all rendered pages and slides")
        try:
            reviewed_at = date.fromisoformat(manifest.get("visual_reviewed_at", ""))
            if reviewed_at > date.today():
                errors.append("visual_reviewed_at cannot be in the future")
        except ValueError:
            errors.append("visual_reviewed_at must be an ISO date")
    font_dir = Path(manifest.get("font_dir", ""))
    font_files = list(font_dir.glob("*.ttf")) + list(font_dir.glob("*.otf")) if font_dir.is_dir() else []
    if not font_files:
        errors.append("font_dir must contain the locked OpenType or TrueType font bundle")
    seen_profiles: set[str] = set()
    total_pages = 0
    for index, record in enumerate(records):
        locator = f"records[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{locator} must be an object")
            continue
        profile_id = record.get("profile_id")
        if profile_id not in profiles:
            errors.append(f"{locator}.profile_id is not registered")
            continue
        if profile_id in seen_profiles:
            errors.append(f"duplicate profile record: {profile_id}")
        seen_profiles.add(profile_id)
        route_id = record.get("representative_genre")
        route = routes.get(route_id)
        if not route or route.get("format_profile_id") != profile_id:
            errors.append(f"{locator}.representative_genre does not route to {profile_id}")
        profile = profiles[profile_id]
        if record.get("artifact_kind") != profile.get("artifact_kind"):
            errors.append(f"{locator}.artifact_kind does not match the profile")
        if args.require_visual_pass and record.get("visual_review") != PASS_REVIEW:
            errors.append(f"{locator}.visual_review has not passed full-size individual inspection")
        page_count = record.get("page_count")
        if not isinstance(page_count, int) or page_count < 1:
            errors.append(f"{locator}.page_count must be positive")
            page_count = 0
        total_pages += page_count
        editable = Path(record.get("editable_path", ""))
        pdf = Path(record.get("pdf_path", ""))
        receipt_path = Path(record.get("render_receipt", ""))
        expected_suffix = ".docx" if profile.get("artifact_kind") == "docx" else ".pptx"
        if editable.suffix.lower() != expected_suffix:
            errors.append(f"{locator}.editable_path has the wrong extension")
        for label, path, hash_field in (
            ("editable", editable, "editable_sha256"), ("pdf", pdf, "pdf_sha256")
        ):
            if not path.is_file():
                errors.append(f"{locator}.{label}_path does not exist")
                continue
            expected_hash = record.get(hash_field)
            if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
                errors.append(f"{locator}.{hash_field} must be a lowercase SHA-256")
            elif sha256_file(path) != expected_hash:
                errors.append(f"{locator}.{hash_field} does not match the file")
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{locator}.render_receipt: {exc}")
            continue
        if receipt.get("status") != "PASS":
            errors.append(f"{locator}: render receipt did not pass")
        if Path(receipt.get("input", "")).resolve() != editable.resolve():
            errors.append(f"{locator}: receipt input does not match editable artifact")
        if Path(receipt.get("pdf", "")).resolve() != pdf.resolve():
            errors.append(f"{locator}: receipt PDF does not match manifest")
        pages = receipt.get("pages")
        if receipt.get("page_count") != page_count or not isinstance(pages, list) or len(pages) != page_count:
            errors.append(f"{locator}: receipt page count does not match manifest")
            pages = []
        for page_index, page_raw in enumerate(pages, 1):
            page = Path(page_raw)
            if page.name != f"page-{page_index:03d}.png":
                errors.append(f"{locator}: rendered page sequence is not canonical")
            if not page.is_file():
                errors.append(f"{locator}: rendered page is missing: {page}")
                continue
            try:
                width, height = png_dimensions(page)
                if width < 500 or height < 500:
                    errors.append(f"{locator}: rendered page dimensions are unexpectedly small")
            except (OSError, ValueError) as exc:
                errors.append(f"{locator}: invalid rendered page {page}: {exc}")
        font_audit = receipt.get("font_audit", {})
        font_names = font_audit.get("font_names", [])
        for group in ("approved_heading_markers", "approved_latin_markers"):
            markers = font_audit.get(group, [])
            if not markers or not all(any(marker in name for name in font_names) for marker in markers):
                errors.append(f"{locator}: receipt lacks an approved font marker from {group}")
        if profile.get("artifact_kind") == "docx":
            body_markers = font_audit.get("approved_body_markers", [])
            if not body_markers or not all(any(marker in name for name in font_names) for marker in body_markers):
                errors.append(f"{locator}: DOCX receipt lacks the approved body font")
    missing_profiles = set(profiles) - seen_profiles
    if missing_profiles:
        errors.append(f"missing profile records: {', '.join(sorted(missing_profiles))}")
    if manifest.get("total_rendered_pages_and_slides") not in (None, total_pages):
        errors.append("total_rendered_pages_and_slides does not match the records")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} artifact-profile QA manifest error(s)")
        return 1
    print(
        f"PASS: verified {len(records)} profiles, {len(routes)} genre routes, "
        f"{total_pages} rendered pages/slides, hashes, receipts, fonts, and visual status"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

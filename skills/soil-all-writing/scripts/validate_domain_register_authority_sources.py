#!/usr/bin/env python3
"""Validate official authority sources used to qualify domain-register decisions."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
import re
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
FIELDS = [
    "source_id", "source_type", "title", "issuing_body", "identifier",
    "publication_date", "effective_date", "current_status", "landing_url",
    "snapshot_url", "snapshot_kind", "snapshot_sha256", "source_role", "locator",
    "accessed_at", "verification_state", "reuse_scope", "notes",
]
SOURCE_TYPES = {
    "national_environmental_standard", "national_standard_registry", "ministry_technical_rule",
}
CURRENT_STATUSES = {"in_force", "published_trial_rule", "current_revision_in_progress"}
SNAPSHOT_KINDS = {"official_pdf", "official_html_metadata_page"}
SOURCE_ROLES = {
    "workflow_stage_evidence", "genre_specific_occurrence_evidence",
    "normative_language_evidence", "current_status_evidence",
}
ALLOWED_HOSTS = {"www.mee.gov.cn", "std.samr.gov.cn"}
VERIFICATION = "official_page_and_snapshot_hash_verified"
REUSE_SCOPE = "metadata_and_structural_language_for_register_analysis_no_patchwriting"


def parse_iso(value: str, locator: str, field: str, errors: list[str], *, required: bool) -> date | None:
    if not value and not required:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        errors.append(f"{locator}: {field} must be an ISO date")
        return None
    if parsed > date.today():
        errors.append(f"{locator}: {field} cannot be in the future")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path", nargs="?", type=Path,
        default=ROOT / "assets/domain-register-authority-source-registry.csv",
    )
    args = parser.parse_args()
    errors: list[str] = []
    try:
        with args.path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDS:
                errors.append("authority-source registry header does not match the controlled schema")
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        print(f"ERROR: {exc}")
        return 1
    if len(rows) < 4:
        errors.append("authority-source registry must contain at least four verified official sources")
    seen_ids: set[str] = set()
    seen_identifiers: set[str] = set()
    seen_snapshots: set[str] = set()
    for index, row in enumerate(rows, 2):
        locator = f"row {index}"
        source_id = row.get("source_id", "").strip()
        if not re.fullmatch(r"DRA-SRC-\d{3}", source_id):
            errors.append(f"{locator}: source_id must match DRA-SRC-ddd")
        elif source_id in seen_ids:
            errors.append(f"{locator}: duplicate source_id {source_id}")
        seen_ids.add(source_id)
        source_type = row.get("source_type", "").strip()
        if source_type not in SOURCE_TYPES:
            errors.append(f"{locator}: unsupported source_type")
        for field in ("title", "issuing_body", "identifier", "locator", "notes"):
            if not row.get(field, "").strip():
                errors.append(f"{locator}: {field} must be non-empty")
        identifier = row.get("identifier", "").strip()
        if identifier in seen_identifiers:
            errors.append(f"{locator}: duplicate identifier {identifier}")
        seen_identifiers.add(identifier)
        if source_type == "national_environmental_standard" and not re.fullmatch(
            r"HJ \d+—\d{4}", identifier
        ):
            errors.append(f"{locator}: environmental-standard identifier is invalid")
        if source_type == "national_standard_registry" and not re.fullmatch(
            r"GB/T \d+-\d{4}", identifier
        ):
            errors.append(f"{locator}: national-standard identifier is invalid")
        publication = parse_iso(
            row.get("publication_date", "").strip(), locator, "publication_date", errors,
            required=True,
        )
        effective = parse_iso(
            row.get("effective_date", "").strip(), locator, "effective_date", errors,
            required=source_type != "ministry_technical_rule",
        )
        if publication and effective and effective < publication:
            errors.append(f"{locator}: effective_date cannot precede publication_date")
        if row.get("current_status", "").strip() not in CURRENT_STATUSES:
            errors.append(f"{locator}: unsupported current_status")
        for field in ("landing_url", "snapshot_url"):
            value = row.get(field, "").strip()
            parsed = urlparse(value)
            if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
                errors.append(f"{locator}: {field} must use an allowlisted official HTTPS host")
        if row.get("snapshot_kind", "").strip() not in SNAPSHOT_KINDS:
            errors.append(f"{locator}: unsupported snapshot_kind")
        snapshot_hash = row.get("snapshot_sha256", "").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", snapshot_hash):
            errors.append(f"{locator}: snapshot_sha256 must be a lowercase SHA-256")
        elif snapshot_hash in seen_snapshots:
            errors.append(f"{locator}: duplicate snapshot_sha256")
        seen_snapshots.add(snapshot_hash)
        if row.get("source_role", "").strip() not in SOURCE_ROLES:
            errors.append(f"{locator}: unsupported source_role")
        parse_iso(row.get("accessed_at", "").strip(), locator, "accessed_at", errors, required=True)
        if row.get("verification_state", "").strip() != VERIFICATION:
            errors.append(f"{locator}: verification_state must preserve official snapshot verification")
        if row.get("reuse_scope", "").strip() != REUSE_SCOPE:
            errors.append(f"{locator}: reuse_scope must prohibit patchwriting")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} authority-source registry error(s)")
        return 1
    print(f"PASS: authority-source registry is valid; records={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

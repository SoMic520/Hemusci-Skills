#!/usr/bin/env python3
"""Validate expert identities and expert-first-author source records."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
import re


ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL = re.compile(r"^https?://")
EXPERT_REQUIRED = {
    "expert_id", "name_zh", "primary_fields", "expert_basis",
    "official_profile_url", "status", "verified_date",
}
SOURCE_REQUIRED = {
    "source_id", "expert_id", "first_author", "co_first_author",
    "title", "journal", "year", "article_type", "url", "language",
    "topic", "full_text_status", "license", "reuse_status", "verified_date",
}
EXPERT_STATUSES = {"verified-current", "verified-historical"}
REUSE_STATUSES = {"abstract_pattern_only", "short_quote_analysis_only", "quote_with_attribution"}


def read_csv(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                errors.append(f"{path.name}: missing header")
                return []
            return [row for row in reader if any(row.values())]
    except (OSError, csv.Error) as exc:
        errors.append(f"{path.name}: {exc}")
        return []


def check_columns(path: Path, rows: list[dict[str, str]], required: set[str], errors: list[str]) -> None:
    fields = set(rows[0]) if rows else set()
    missing = sorted(required - fields)
    if missing:
        errors.append(f"{path.name}: missing columns: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("expert_registry", type=Path)
    parser.add_argument("source_registry", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    experts = read_csv(args.expert_registry, errors)
    sources = read_csv(args.source_registry, errors)
    if not experts:
        errors.append(f"{args.expert_registry.name}: no expert records")
    if not sources:
        errors.append(f"{args.source_registry.name}: no source records")
    if experts:
        check_columns(args.expert_registry, experts, EXPERT_REQUIRED, errors)
    if sources:
        check_columns(args.source_registry, sources, SOURCE_REQUIRED, errors)

    expert_names: dict[str, str] = {}
    for line_number, row in enumerate(experts, 2):
        expert_id = row.get("expert_id", "").strip()
        missing = [field for field in EXPERT_REQUIRED if not row.get(field, "").strip()]
        if missing:
            errors.append(f"{args.expert_registry.name}:{line_number}: empty required fields: {', '.join(sorted(missing))}")
        if expert_id in expert_names:
            errors.append(f"{args.expert_registry.name}:{line_number}: duplicate expert_id {expert_id}")
        if row.get("status", "").strip() not in EXPERT_STATUSES:
            errors.append(f"{args.expert_registry.name}:{line_number}: invalid status")
        if row.get("official_profile_url") and not URL.match(row["official_profile_url"].strip()):
            errors.append(f"{args.expert_registry.name}:{line_number}: invalid official_profile_url")
        verified_date = row.get("verified_date", "").strip()
        if verified_date and not ISO_DATE.match(verified_date):
            errors.append(f"{args.expert_registry.name}:{line_number}: verified_date must be YYYY-MM-DD")
        expert_names[expert_id] = row.get("name_zh", "").strip()

    source_ids: set[str] = set()
    current_year = date.today().year
    for line_number, row in enumerate(sources, 2):
        source_id = row.get("source_id", "").strip()
        expert_id = row.get("expert_id", "").strip()
        missing = [field for field in SOURCE_REQUIRED if not row.get(field, "").strip()]
        if missing:
            errors.append(f"{args.source_registry.name}:{line_number}: empty required fields: {', '.join(sorted(missing))}")
        if source_id in source_ids:
            errors.append(f"{args.source_registry.name}:{line_number}: duplicate source_id {source_id}")
        source_ids.add(source_id)
        if expert_id not in expert_names:
            errors.append(f"{args.source_registry.name}:{line_number}: unknown expert_id {expert_id}")
        elif row.get("first_author", "").strip() != expert_names[expert_id]:
            errors.append(
                f"{args.source_registry.name}:{line_number}: first_author does not match expert {expert_id}"
            )
        if row.get("co_first_author", "").strip().casefold() not in {"true", "false"}:
            errors.append(f"{args.source_registry.name}:{line_number}: co_first_author must be true or false")
        try:
            year = int(row.get("year", ""))
            if year < 1900 or year > current_year + 1:
                errors.append(f"{args.source_registry.name}:{line_number}: implausible year {year}")
        except ValueError:
            errors.append(f"{args.source_registry.name}:{line_number}: year must be an integer")
        if row.get("url") and not URL.match(row["url"].strip()):
            errors.append(f"{args.source_registry.name}:{line_number}: invalid url")
        if row.get("reuse_status", "").strip() not in REUSE_STATUSES:
            errors.append(f"{args.source_registry.name}:{line_number}: invalid reuse_status")
        verified_date = row.get("verified_date", "").strip()
        if verified_date and not ISO_DATE.match(verified_date):
            errors.append(f"{args.source_registry.name}:{line_number}: verified_date must be YYYY-MM-DD")

    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} expert-source error(s)")
        return 1
    print(f"PASS: {len(experts)} experts and {len(sources)} expert-first-author sources are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate a soil-science language termbase CSV using the Python standard library."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
import re


REQUIRED = [
    "term_id", "concept_id", "source_language", "source_term", "target_language",
    "preferred_term", "status", "domain", "definition", "context",
    "classification_system", "authority_source_id", "source_url", "version",
    "decision_note", "approved_by", "approved_date",
]
STATUSES = {"proposed", "preferred", "admitted", "deprecated", "forbidden", "unverified", "approved", "locked"}
CONTROLLED = {"preferred", "approved", "locked"}


def validate(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED if field not in (reader.fieldnames or [])]
        if missing:
            return [f"missing columns: {', '.join(missing)}"], warnings
        rows = list(reader)
    if not rows:
        warnings.append("termbase has a valid header but no records")
        return errors, warnings

    ids: set[str] = set()
    preferred_keys: set[tuple[str, str]] = set()
    for line, row in enumerate(rows, 2):
        prefix = f"line {line}"
        term_id = row["term_id"].strip()
        if not term_id:
            errors.append(f"{prefix}: term_id is required")
        elif term_id in ids:
            errors.append(f"{prefix}: duplicate term_id {term_id}")
        ids.add(term_id)
        for field in ("concept_id", "source_language", "source_term", "target_language", "preferred_term", "status", "domain"):
            if not row[field].strip():
                errors.append(f"{prefix}: {field} is required")
        status = row["status"].strip()
        if status and status not in STATUSES:
            errors.append(f"{prefix}: invalid status {status}")
        if row["source_url"].strip() and not re.match(r"^https?://", row["source_url"].strip()):
            errors.append(f"{prefix}: source_url must use http or https")
        if row["classification_system"].strip() and not row["version"].strip():
            errors.append(f"{prefix}: classification_system requires version")
        if status in CONTROLLED:
            for field in ("authority_source_id", "approved_by", "approved_date"):
                if not row[field].strip():
                    errors.append(f"{prefix}: {status} term requires {field}")
            if row["approved_date"].strip():
                try:
                    date.fromisoformat(row["approved_date"].strip())
                except ValueError:
                    errors.append(f"{prefix}: approved_date must be YYYY-MM-DD")
            key = (row["concept_id"].strip(), row["target_language"].strip())
            if key in preferred_keys:
                errors.append(f"{prefix}: multiple controlled preferred terms for concept/language {key}")
            preferred_keys.add(key)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        errors, warnings = validate(args.path)
    except (OSError, csv.Error) as exc:
        print(f"ERROR: {exc}")
        return 1
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        return 1
    print("PASS: termbase structure is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate the D1–D13 full-text-verified expression-pattern pilot."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import date
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MODULES = {f"D{index}" for index in range(1, 14)}
REQUIRED = [
    "expression_id", "entry_type", "language", "discipline", "genre", "section",
    "rhetorical_move", "exact_fragment", "abstracted_pattern", "source_title", "authors",
    "year", "doi", "url", "locator", "license", "access_date", "verbatim_word_count",
    "verified", "context_limit", "reuse_status", "notes", "module_id", "source_type",
    "fulltext_status", "qualification_status", "reviewer_state", "release_scope",
    "module_fit_reason",
]
PENDING_REVIEW = "agent_source_license_context_check_human_domain_review_pending"
PILOT_SCOPE = "internal_pilot_not_production_phrasebook"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path", nargs="?", type=Path, default=ROOT / "assets/module-expression-pilot.csv"
    )
    args = parser.parse_args()
    errors: list[str] = []
    try:
        with args.path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [field for field in REQUIRED if field not in (reader.fieldnames or [])]
            if missing:
                errors.append(f"missing columns: {', '.join(missing)}")
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        print(f"ERROR: {exc}")
        return 1

    ids: set[str] = set()
    modules = Counter()
    dois: set[str] = set()
    for line, row in enumerate(rows, 2):
        prefix = f"line {line}"
        expression_id = row.get("expression_id", "").strip()
        if not re.fullmatch(r"MOD-EXPR-D(?:0[1-9]|1[0-3])", expression_id):
            errors.append(f"{prefix}: expression_id must match MOD-EXPR-D01 through D13")
        elif expression_id in ids:
            errors.append(f"{prefix}: duplicate expression_id {expression_id}")
        ids.add(expression_id)

        module_id = row.get("module_id", "").strip()
        if module_id not in MODULES:
            errors.append(f"{prefix}: invalid module_id {module_id!r}")
        else:
            modules[module_id] += 1
            expected_id = f"MOD-EXPR-D{int(module_id[1:]):02d}"
            if expression_id != expected_id:
                errors.append(f"{prefix}: expression_id does not match module_id")

        if row.get("entry_type", "").strip() != "abstracted":
            errors.append(f"{prefix}: pilot entries must be abstracted")
        if row.get("exact_fragment", "").strip():
            errors.append(f"{prefix}: exact_fragment must remain empty")
        if row.get("verbatim_word_count", "").strip() != "0":
            errors.append(f"{prefix}: verbatim_word_count must be 0")
        pattern = row.get("abstracted_pattern", "").strip()
        if len(pattern) < 70 or "[" not in pattern or "]" not in pattern:
            errors.append(f"{prefix}: abstracted_pattern must be substantive and parameterized")

        exact_values = {
            "verified": "true",
            "reuse_status": "abstract_pattern_only",
            "source_type": "official_open_fulltext_article",
            "fulltext_status": "fulltext_verified",
            "qualification_status": "expression_qualified_pilot",
            "reviewer_state": PENDING_REVIEW,
            "release_scope": PILOT_SCOPE,
        }
        for field, expected in exact_values.items():
            if row.get(field, "").strip() != expected:
                errors.append(f"{prefix}: {field} must be {expected}")

        for field in (
            "language", "discipline", "genre", "section", "rhetorical_move", "source_title",
            "authors", "locator", "license", "context_limit", "notes", "module_fit_reason",
        ):
            if not row.get(field, "").strip():
                errors.append(f"{prefix}: {field} is required")

        year = row.get("year", "").strip()
        if not re.fullmatch(r"20\d{2}", year):
            errors.append(f"{prefix}: year must be a four-digit 2000s year")
        doi = row.get("doi", "").strip().lower()
        if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
            errors.append(f"{prefix}: invalid DOI")
        elif doi in dois:
            errors.append(f"{prefix}: duplicate DOI {doi}")
        dois.add(doi)
        if not row.get("url", "").strip().startswith("https://"):
            errors.append(f"{prefix}: URL must use https")
        if not row.get("license", "").strip().startswith("CC BY"):
            errors.append(f"{prefix}: source license must be verified CC BY")
        try:
            accessed = date.fromisoformat(row.get("access_date", ""))
            if accessed > date.today():
                errors.append(f"{prefix}: access_date cannot be in the future")
        except ValueError:
            errors.append(f"{prefix}: access_date must be YYYY-MM-DD")

    missing_modules = sorted(MODULES - set(modules), key=lambda item: int(item[1:]))
    extra_counts = sorted(module for module, count in modules.items() if count != 1)
    if missing_modules:
        errors.append(f"missing modules: {', '.join(missing_modules)}")
    if extra_counts:
        errors.append(f"pilot requires exactly one seed per module: {', '.join(extra_counts)}")
    if len(rows) != 13:
        errors.append(f"pilot must contain exactly 13 rows; found {len(rows)}")

    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} module-expression pilot error(s)")
        return 1
    print(
        "PASS: D1–D13 each have one full-text-verified, CC-BY, abstract-only internal pilot seed; "
        "human domain review remains pending"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

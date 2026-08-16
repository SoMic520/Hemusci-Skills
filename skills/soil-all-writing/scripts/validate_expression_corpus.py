#!/usr/bin/env python3
"""Validate provenance, licensing, and fragment length in an expression corpus."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
import re


REQUIRED = [
    "expression_id", "entry_type", "language", "discipline", "genre", "section",
    "rhetorical_move", "exact_fragment", "abstracted_pattern", "source_title", "authors",
    "year", "doi", "url", "locator", "license", "access_date", "verbatim_word_count",
    "verified", "context_limit", "reuse_status", "notes",
]
ENTRY_TYPES = {"verbatim", "abstracted", "pattern", "author_approved", "negative_example", "candidate"}
TRUE = {"true", "1", "yes"}
FALSE = {"false", "0", "no"}


def fragment_length(text: str) -> int:
    han = re.findall(r"[\u3400-\u9fff]", text)
    if han:
        return len(han)
    return len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))


def validate(path: Path, max_words: int, max_han: int) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED if field not in (reader.fieldnames or [])]
        if missing:
            return [f"missing columns: {', '.join(missing)}"], warnings
        rows = list(reader)
    ids: set[str] = set()
    for line, row in enumerate(rows, 2):
        prefix = f"line {line}"
        expression_id = row["expression_id"].strip()
        if not expression_id:
            errors.append(f"{prefix}: expression_id is required")
        elif expression_id in ids:
            errors.append(f"{prefix}: duplicate expression_id {expression_id}")
        ids.add(expression_id)
        for field in ("entry_type", "language", "discipline", "genre", "section", "rhetorical_move", "reuse_status"):
            if not row[field].strip():
                errors.append(f"{prefix}: {field} is required")
        entry_type = row["entry_type"].strip()
        if entry_type and entry_type not in ENTRY_TYPES:
            errors.append(f"{prefix}: invalid entry_type {entry_type}")
        verified_text = row["verified"].strip().lower()
        if verified_text not in TRUE | FALSE:
            errors.append(f"{prefix}: verified must be true or false")
        if entry_type == "candidate" and verified_text in TRUE:
            errors.append(f"{prefix}: candidate cannot be marked verified")
        if entry_type in {"abstracted", "pattern"} and not row["abstracted_pattern"].strip():
            errors.append(f"{prefix}: {entry_type} requires abstracted_pattern")
        if entry_type == "verbatim":
            for field in ("exact_fragment", "source_title", "authors", "year", "url", "locator", "license", "access_date", "context_limit"):
                if not row[field].strip():
                    errors.append(f"{prefix}: verbatim entry requires {field}")
            if verified_text not in TRUE:
                errors.append(f"{prefix}: verbatim entry must be verified")
            actual = fragment_length(row["exact_fragment"].strip())
            try:
                declared = int(row["verbatim_word_count"].strip())
            except ValueError:
                declared = -1
                errors.append(f"{prefix}: verbatim_word_count must be an integer")
            if declared != actual:
                errors.append(f"{prefix}: declared fragment length {declared} does not match {actual}")
            has_han = bool(re.search(r"[\u3400-\u9fff]", row["exact_fragment"]))
            limit = max_han if has_han else max_words
            if actual > limit:
                errors.append(f"{prefix}: verbatim fragment length {actual} exceeds limit {limit}")
            if "all-rights-reserved" in row["license"].lower() and row["reuse_status"].strip() != "short_quote_analysis_only":
                errors.append(f"{prefix}: all-rights-reserved verbatim text must be analysis-only")
        elif row["verbatim_word_count"].strip() not in {"", "0"}:
            errors.append(f"{prefix}: non-verbatim entry must have word count 0")
        if row["url"].strip() and not re.match(r"^https?://", row["url"].strip()):
            errors.append(f"{prefix}: url must use http or https")
        if row["access_date"].strip():
            try:
                date.fromisoformat(row["access_date"].strip())
            except ValueError:
                errors.append(f"{prefix}: access_date must be YYYY-MM-DD")
        if entry_type in {"abstracted", "pattern"} and row["source_title"].strip() and not row["locator"].strip():
            errors.append(f"{prefix}: source-informed pattern requires locator")
    if not rows:
        warnings.append("corpus has no records")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--max-words", type=int, default=12)
    parser.add_argument("--max-han", type=int, default=20)
    args = parser.parse_args()
    try:
        errors, warnings = validate(args.path, args.max_words, args.max_han)
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
    print("PASS: expression corpus is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

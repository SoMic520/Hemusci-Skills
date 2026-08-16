#!/usr/bin/env python3
"""Validate cross-provider qualification records without claiming unrun models passed."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
import re


REQUIRED_PROVIDERS = {
    "openai", "anthropic", "google-gemini", "deepseek", "qwen", "mistral",
    "cohere", "amazon-bedrock", "ollama", "custom",
}
REQUIRED_COLUMNS = [
    "provider", "endpoint_type", "model_id", "model_revision", "profile_verified",
    "smoke_suite", "full_suite", "confidentiality_approved", "qualified_scopes",
    "excluded_scopes", "evaluator", "evaluated_at", "evidence_uri", "notes",
]
SUITE_STATES = {"not_run", "pass", "fail"}
BOOLS = {"true", "false"}


def validate(path: Path, require_qualified: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED_COLUMNS if field not in (reader.fieldnames or [])]
        if missing:
            return [f"missing columns: {', '.join(missing)}"], warnings
        rows = list(reader)
    providers: set[str] = set()
    for line, row in enumerate(rows, 2):
        prefix = f"line {line}"
        provider = row["provider"].strip()
        if provider in providers:
            errors.append(f"{prefix}: duplicate provider {provider}")
        providers.add(provider)
        for field in ("endpoint_type", "model_id", "model_revision"):
            if not row[field].strip():
                errors.append(f"{prefix}: {field} is required")
        for field in ("profile_verified", "confidentiality_approved"):
            if row[field].strip().lower() not in BOOLS:
                errors.append(f"{prefix}: {field} must be true or false")
        for field in ("smoke_suite", "full_suite"):
            if row[field].strip() not in SUITE_STATES:
                errors.append(f"{prefix}: invalid {field} state")
        passed = row["smoke_suite"].strip() == "pass" or row["full_suite"].strip() == "pass"
        if passed:
            for field in ("evaluator", "evaluated_at", "evidence_uri"):
                if not row[field].strip():
                    errors.append(f"{prefix}: a passed suite requires {field}")
            try:
                datetime.fromisoformat(row["evaluated_at"].strip().replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{prefix}: evaluated_at must be ISO 8601")
            if row["evidence_uri"].strip() and not re.match(r"^(https?://|[A-Za-z0-9_./-]+$)", row["evidence_uri"].strip()):
                errors.append(f"{prefix}: evidence_uri is invalid")
        if row["full_suite"].strip() == "pass" and (
            row["profile_verified"].strip().lower() != "true" or not row["qualified_scopes"].strip()
        ):
            errors.append(f"{prefix}: full-suite pass requires a verified profile and qualified_scopes")
        if row["smoke_suite"].strip() == "pass" and row["profile_verified"].strip().lower() != "true":
            errors.append(f"{prefix}: smoke-suite pass requires a verified profile")
        if row["full_suite"].strip() == "pass" and row["smoke_suite"].strip() != "pass":
            errors.append(f"{prefix}: full-suite pass requires smoke-suite pass")
        if row["full_suite"].strip() != "pass" and row["qualified_scopes"].strip():
            errors.append(f"{prefix}: qualified_scopes requires full-suite pass")
        if require_qualified and row["full_suite"].strip() != "pass":
            errors.append(f"{prefix}: full qualification has not passed")
        elif row["full_suite"].strip() == "not_run":
            warnings.append(f"{provider}: full suite not run")
    missing_providers = REQUIRED_PROVIDERS - providers
    extra_providers = providers - REQUIRED_PROVIDERS
    if missing_providers:
        errors.append(f"missing providers: {', '.join(sorted(missing_providers))}")
    if extra_providers:
        warnings.append(f"additional providers: {', '.join(sorted(extra_providers))}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--require-qualified", action="store_true")
    args = parser.parse_args()
    try:
        errors, warnings = validate(args.path, args.require_qualified)
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
    print("PASS: model qualification matrix is structurally valid; unrun suites are not qualified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

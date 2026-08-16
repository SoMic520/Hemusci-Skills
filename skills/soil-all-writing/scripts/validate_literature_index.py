#!/usr/bin/env python3
"""Validate module quotas and fail-closed qualification states in a literature index."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import json
from pathlib import Path


REQUIRED = {
    "module_id", "work_id", "title", "publication_year", "work_type",
    "source_name", "source_id", "source_tier", "first_author", "matched_queries",
    "metadata_source", "query_plan_sha256", "metadata_status", "fulltext_status",
    "expression_status",
}
AUDIT_CHECKS = {
    "relevance_review", "source_review", "author_position_review", "work_type_review",
}


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader if any(row.values())], reader.fieldnames or []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--audit-sample", type=Path, required=True)
    parser.add_argument("--require-human-qualified", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    try:
        raw_plan = args.plan.read_bytes()
        plan = json.loads(raw_plan)
        plan_hash = hashlib.sha256(raw_plan).hexdigest()
        rows, fields = read_rows(args.index)
        audit_rows, audit_fields = read_rows(args.audit_sample)
    except (OSError, csv.Error, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    missing_fields = REQUIRED - set(fields)
    if missing_fields:
        errors.append("index missing columns: " + ", ".join(sorted(missing_fields)))
    missing_audit = ({"module_id", "work_id"} | AUDIT_CHECKS) - set(audit_fields)
    if missing_audit:
        errors.append("audit sample missing columns: " + ", ".join(sorted(missing_audit)))

    expected_modules = {module["module_id"] for module in plan["modules"]}
    allowed_crossref_sources = {
        module["module_id"]: {source[0] for source in module["crossref_sources"]}
        for module in plan["modules"]
    }
    allowed_chinese_sources = set(plan["chinese_t1_source_ids"])
    target = int(plan["target_records_per_module"])
    audit_target = int(plan["audit_sample_per_module"])
    module_works: dict[str, set[str]] = defaultdict(set)
    quota_works: dict[str, set[str]] = defaultdict(set)
    work_modules: dict[str, set[str]] = defaultdict(set)
    chinese_counts: Counter[str] = Counter()
    oa_counts: Counter[str] = Counter()
    for line_number, row in enumerate(rows, 2):
        missing = [field for field in REQUIRED if not row.get(field, "").strip()]
        if missing:
            errors.append(f"index:{line_number}: empty required fields: {', '.join(sorted(missing))}")
            continue
        module_id = row["module_id"].strip()
        work_id = row["work_id"].strip()
        if module_id not in expected_modules:
            errors.append(f"index:{line_number}: unexpected module {module_id}")
        if work_id in module_works[module_id]:
            errors.append(f"index:{line_number}: duplicate {module_id}/{work_id}")
        module_works[module_id].add(work_id)
        if row.get("metadata_status") == "metadata_screened":
            quota_works[module_id].add(work_id)
        work_modules[work_id].add(module_id)
        if row.get("source_tier") == "soil_t1_2024_chinese":
            chinese_counts[module_id] += 1
        if row.get("is_open_access", "").casefold() == "true":
            oa_counts[module_id] += 1
        if row.get("metadata_status") not in {"metadata_screened", "pending_module_relevance_audit"}:
            errors.append(f"index:{line_number}: invalid metadata_status")
        if row.get("query_plan_sha256") != plan_hash:
            errors.append(f"index:{line_number}: stale query_plan_sha256")
        try:
            year = int(row.get("publication_year", ""))
            if year < int(plan["minimum_publication_year"]) or year > date.today().year + 1:
                errors.append(f"index:{line_number}: publication_year outside plan range")
        except ValueError:
            errors.append(f"index:{line_number}: publication_year must be an integer")
        if row.get("work_type") not in {"article", "review"}:
            errors.append(f"index:{line_number}: ineligible work_type")
        if row.get("metadata_status") == "metadata_screened":
            if row.get("metadata_source") != "Crossref REST API":
                errors.append(f"index:{line_number}: quota record must use Crossref metadata")
            if row.get("source_id") not in allowed_crossref_sources.get(module_id, set()):
                errors.append(f"index:{line_number}: source is not allowlisted for {module_id}")
            if not row.get("doi", "").strip():
                errors.append(f"index:{line_number}: quota record requires DOI")
        else:
            if row.get("metadata_source") != "OpenAlex API":
                errors.append(f"index:{line_number}: Chinese candidate must use OpenAlex metadata")
            if row.get("source_id") not in allowed_chinese_sources:
                errors.append(f"index:{line_number}: Chinese candidate source is not allowlisted")
            if row.get("source_tier") != "soil_t1_2024_chinese":
                errors.append(f"index:{line_number}: Chinese candidate has wrong source_tier")
        if row.get("expression_status") == "expression_qualified" and row.get("fulltext_status") != "fulltext_verified":
            errors.append(f"index:{line_number}: expression qualification requires verified full text")

    for module_id in sorted(expected_modules):
        count = len(quota_works[module_id])
        if count < target:
            errors.append(f"{module_id}: only {count}/{target} unique records")

    audit_by_module: Counter[str] = Counter()
    audit_seen: set[tuple[str, str]] = set()
    audit_work_ids = {(row.get("module_id", ""), row.get("work_id", "")) for row in rows}
    for line_number, row in enumerate(audit_rows, 2):
        module_id = row.get("module_id", "").strip()
        work_id = row.get("work_id", "").strip()
        audit_by_module[module_id] += 1
        if (module_id, work_id) in audit_seen:
            errors.append(f"audit:{line_number}: duplicate audit record")
        audit_seen.add((module_id, work_id))
        if (module_id, work_id) not in audit_work_ids:
            errors.append(f"audit:{line_number}: record is not in index")
        states = {row.get(field, "").strip() for field in AUDIT_CHECKS}
        if not states <= {"pending", "pass", "fail"}:
            errors.append(f"audit:{line_number}: invalid review state")
        if args.require_human_qualified:
            if states != {"pass"}:
                errors.append(f"audit:{line_number}: human review incomplete or failed")
            if not row.get("reviewer_1", "").strip() or not row.get("reviewer_2", "").strip():
                errors.append(f"audit:{line_number}: two reviewers are required")
    for module_id in sorted(expected_modules):
        if audit_by_module[module_id] < audit_target:
            errors.append(f"{module_id}: audit sample has {audit_by_module[module_id]}/{audit_target}")

    for error in errors[:100]:
        print(f"ERROR: {error}")
    if len(errors) > 100:
        print(f"ERROR: {len(errors) - 100} additional errors omitted")
    if errors:
        print(f"FAILED: {len(errors)} literature-index error(s)")
        return 1
    unique = len(work_modules)
    overlap = sum(1 for modules in work_modules.values() if len(modules) > 1)
    print(f"PASS: {len(rows)} module records; {unique} unique works; {overlap} cross-module works")
    for module_id in sorted(expected_modules, key=lambda value: int(value[1:])):
        print(f"INFO: {module_id}: {len(quota_works[module_id])} quota records; {len(module_works[module_id])} total; {chinese_counts[module_id]} Chinese-T1 candidates; {oa_counts[module_id]} OA")
    if not args.require_human_qualified:
        print("WARNING: metadata quota passed; audit rows remain separate from full-text/expression qualification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

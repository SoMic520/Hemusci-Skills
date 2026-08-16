#!/usr/bin/env python3
"""Validate the evidence-controlled domain-register learning ledger."""

from __future__ import annotations

import argparse
import csv
from datetime import date
import json
from pathlib import Path
import re


FIELDS = [
    "record_id", "candidate_expression", "observed_context", "genre", "rhetorical_unit",
    "intended_meaning", "task_failure_locator", "preferred_usage_source_1",
    "preferred_usage_source_2", "proposed_classification", "replacement_by_sense", "status",
    "reviewer", "review_date", "reject_case_id", "allow_case_id", "notes",
]
CLASSIFICATIONS = {
    "default_reject", "context_controlled", "source_locked_only", "legitimate_professional",
}
STATUSES = {"candidate", "evidence_gathered", "domain_reviewed", "promoted", "rejected"}
SOURCE_FIELDS = [
    "source_id", "title", "authors", "journal", "publication_date", "doi", "url",
    "source_role", "locator", "accessed_at", "verification_state", "reuse_scope", "notes",
]
SOURCE_ROLES = {
    "preferred_expression_evidence", "negative_occurrence_context",
    "contextual_occurrence_evidence",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--lexicon", type=Path)
    parser.add_argument("--source-registry", type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    try:
        with args.path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != FIELDS:
                errors.append("ledger header does not match the controlled schema")
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        print(f"ERROR: {exc}")
        return 1
    seen_ids: set[str] = set()
    seen_candidates: set[str] = set()
    seen_reject_cases: set[str] = set()
    seen_allow_cases: set[str] = set()
    for index, row in enumerate(rows, 2):
        locator = f"row {index}"
        record_id = row.get("record_id", "").strip()
        if not re.fullmatch(r"DRL-\d{4,}", record_id):
            errors.append(f"{locator}: record_id must match DRL-dddd")
        elif record_id in seen_ids:
            errors.append(f"{locator}: duplicate record_id {record_id}")
        seen_ids.add(record_id)
        for field in ("candidate_expression", "observed_context", "genre", "rhetorical_unit", "intended_meaning"):
            if not row.get(field, "").strip():
                errors.append(f"{locator}: {field} must be non-empty")
        candidate_expression = row.get("candidate_expression", "").strip()
        if candidate_expression in seen_candidates:
            errors.append(f"{locator}: duplicate candidate_expression")
        seen_candidates.add(candidate_expression)
        classification = row.get("proposed_classification", "").strip()
        status = row.get("status", "").strip()
        if classification and classification not in CLASSIFICATIONS:
            errors.append(f"{locator}: unsupported proposed_classification")
        if status not in STATUSES:
            errors.append(f"{locator}: unsupported status")
        if status in {"evidence_gathered", "domain_reviewed", "promoted"}:
            if classification not in CLASSIFICATIONS:
                errors.append(f"{locator}: evidence-gathered records require a controlled classification")
            for field in ("task_failure_locator", "preferred_usage_source_1", "preferred_usage_source_2"):
                if not row.get(field, "").strip():
                    errors.append(f"{locator}: {status} records require {field}")
            for field in ("preferred_usage_source_1", "preferred_usage_source_2"):
                source = row.get(field, "").strip()
                if source and not re.match(r"^https?://", source):
                    errors.append(f"{locator}: {field} must be an HTTP(S) source locator")
            reject_case = row.get("reject_case_id", "").strip()
            allow_case = row.get("allow_case_id", "").strip()
            if not re.fullmatch(r"DR-[A-Z0-9-]+", reject_case):
                errors.append(f"{locator}: {status} records require a reject regression case")
            elif reject_case in seen_reject_cases:
                errors.append(f"{locator}: duplicate reject_case_id {reject_case}")
            else:
                seen_reject_cases.add(reject_case)
            if not re.fullmatch(r"DR-[A-Z0-9-]+", allow_case):
                errors.append(f"{locator}: {status} records require an allow regression case")
            elif allow_case in seen_allow_cases:
                errors.append(f"{locator}: duplicate allow_case_id {allow_case}")
            else:
                seen_allow_cases.add(allow_case)
            if classification in {"default_reject", "context_controlled"} and not row.get("replacement_by_sense", "").strip():
                errors.append(f"{locator}: controlled rejection records require sense-specific replacements")
        if status in {"domain_reviewed", "promoted"}:
            reviewer = row.get("reviewer", "").strip()
            if not reviewer:
                errors.append(f"{locator}: {status} records require an independent human domain reviewer")
            elif re.search(r"(?:agent|codex|artificial intelligence|\bAI\b)", reviewer, re.IGNORECASE):
                errors.append(f"{locator}: agent or AI labels cannot satisfy human domain review")
            try:
                review_date = date.fromisoformat(row.get("review_date", ""))
                if review_date > date.today():
                    errors.append(f"{locator}: review_date cannot be in the future")
            except ValueError:
                errors.append(f"{locator}: {status} records require ISO review_date")
        if status == "promoted":
            if classification not in CLASSIFICATIONS:
                errors.append(f"{locator}: promoted records require a controlled classification")
            evidence = [
                row.get("task_failure_locator", "").strip(),
                row.get("preferred_usage_source_1", "").strip(),
                row.get("preferred_usage_source_2", "").strip(),
            ]
            if sum(bool(item) for item in evidence) < 2:
                errors.append(f"{locator}: promoted records require at least two traceable evidence locators")
            if classification in {"default_reject", "context_controlled"} and not row.get("replacement_by_sense", "").strip():
                errors.append(f"{locator}: promoted rejection controls require sense-specific replacements")
    if args.lexicon:
        try:
            lexicon = json.loads(args.lexicon.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read lexicon: {exc}")
        else:
            pending = {
                entry.get("learning_record_id"): entry
                for entry in lexicon.get("entries", [])
                if entry.get("qualification_state") == "evidence_gathered_human_domain_review_pending"
            }
            rows_by_id = {row.get("record_id", "").strip(): row for row in rows}
            missing_records = sorted(set(pending) - set(rows_by_id))
            extra_records = sorted(set(rows_by_id) - set(pending))
            if missing_records:
                errors.append(f"lexicon candidate controls missing ledger rows: {', '.join(missing_records)}")
            if extra_records:
                errors.append(f"ledger rows are not bound to candidate controls: {', '.join(extra_records)}")
            for record_id in sorted(set(pending) & set(rows_by_id)):
                entry = pending[record_id]
                row = rows_by_id[record_id]
                if row.get("candidate_expression", "").strip() != entry.get("pattern"):
                    errors.append(f"{record_id}: ledger candidate_expression differs from lexicon pattern")
                if row.get("status", "").strip() != "evidence_gathered":
                    errors.append(f"{record_id}: pending lexicon control must remain evidence_gathered")
    if args.source_registry:
        try:
            with args.source_registry.open(encoding="utf-8-sig", newline="") as handle:
                source_reader = csv.DictReader(handle)
                if source_reader.fieldnames != SOURCE_FIELDS:
                    errors.append("source registry header does not match the controlled schema")
                source_rows = list(source_reader)
        except (OSError, csv.Error) as exc:
            errors.append(f"cannot read source registry: {exc}")
            source_rows = []
        source_ids: set[str] = set()
        source_urls: set[str] = set()
        source_dois: set[str] = set()
        preferred_urls: set[str] = set()
        for index, source in enumerate(source_rows, 2):
            locator = f"source row {index}"
            source_id = source.get("source_id", "").strip()
            if not re.fullmatch(r"DR-SRC-\d{3,}", source_id):
                errors.append(f"{locator}: source_id must match DR-SRC-ddd")
            elif source_id in source_ids:
                errors.append(f"{locator}: duplicate source_id {source_id}")
            source_ids.add(source_id)
            for field in ("title", "authors", "journal", "locator", "notes"):
                if not source.get(field, "").strip():
                    errors.append(f"{locator}: {field} must be non-empty")
            if source.get("journal", "").strip() != "土壤学报":
                errors.append(f"{locator}: current source registry is restricted to verified 土壤学报 records")
            try:
                publication_date = date.fromisoformat(source.get("publication_date", ""))
                if publication_date > date.today():
                    errors.append(f"{locator}: publication_date cannot be in the future")
            except ValueError:
                errors.append(f"{locator}: publication_date must be ISO date")
            doi = source.get("doi", "").strip()
            if not re.fullmatch(r"10\.11766/trxb[A-Za-z0-9]+", doi):
                errors.append(f"{locator}: DOI must be a 土壤学报 DOI")
            elif doi in source_dois:
                errors.append(f"{locator}: duplicate DOI {doi}")
            source_dois.add(doi)
            url = source.get("url", "").strip()
            if not re.match(r"^http://pedologica\.issas\.ac\.cn/trxb/article/abstract/[A-Za-z0-9]+$", url):
                errors.append(f"{locator}: URL must be an official article abstract page")
            elif url in source_urls:
                errors.append(f"{locator}: duplicate URL {url}")
            source_urls.add(url)
            role = source.get("source_role", "").strip()
            if role not in SOURCE_ROLES:
                errors.append(f"{locator}: unsupported source_role")
            elif role == "preferred_expression_evidence":
                preferred_urls.add(url)
            try:
                accessed_at = date.fromisoformat(source.get("accessed_at", ""))
                if accessed_at > date.today():
                    errors.append(f"{locator}: accessed_at cannot be in the future")
            except ValueError:
                errors.append(f"{locator}: accessed_at must be ISO date")
            if source.get("verification_state", "").strip() != "official_page_metadata_and_abstract_verified":
                errors.append(f"{locator}: verification_state must preserve official-page verification")
            if source.get("reuse_scope", "").strip() != "abstract_for_register_analysis_no_patchwriting":
                errors.append(f"{locator}: reuse_scope must prohibit patchwriting")
        for index, row in enumerate(rows, 2):
            if row.get("status", "").strip() not in {"evidence_gathered", "domain_reviewed", "promoted"}:
                continue
            for field in ("preferred_usage_source_1", "preferred_usage_source_2"):
                url = row.get(field, "").strip()
                if url not in preferred_urls:
                    errors.append(f"row {index}: {field} is not a preferred-expression source in the registry")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} register-learning ledger error(s)")
        return 1
    print(f"PASS: register-learning ledger schema is valid; records={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

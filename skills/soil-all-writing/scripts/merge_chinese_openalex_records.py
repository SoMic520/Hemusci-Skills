#!/usr/bin/env python3
"""Merge cached Chinese T1 OpenAlex metadata into the literature index conservatively."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import unicodedata


DEFAULT_MODULES = {
    "S4306552828": "D4",  # 植物营养与肥料学报
    "S4306529909": "D8",  # 水土保持学报
}


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader if any(row.values())], reader.fieldnames or []


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def title_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def author_fields(authorships: list[dict[str, Any]]) -> tuple[str, str, str]:
    first_name = ""
    first_id = ""
    corresponding: list[str] = []
    for authorship in authorships or []:
        author = authorship.get("author") or {}
        name = str(author.get("display_name") or "").strip()
        if authorship.get("author_position") == "first" and not first_name:
            first_name = name
            first_id = str(author.get("id") or "").replace("https://openalex.org/", "")
        if authorship.get("is_corresponding") and name:
            corresponding.append(name)
    return first_name, first_id, "; ".join(dict.fromkeys(corresponding))


def classify(title: str, source_id: str, modules: list[dict[str, Any]]) -> list[tuple[str, str]]:
    lowered = title.casefold()
    scores: list[tuple[int, str, list[str]]] = []
    for module in modules:
        terms = {str(term).casefold() for term in module["classification_terms"]}
        hits = sorted({term for term in terms if term in lowered})
        scores.append((len(hits), module["module_id"], hits))
    best = max((score for score, _, _ in scores), default=0)
    selected: list[tuple[str, str]] = []
    if best > 0:
        for score, module_id, hits in scores:
            if score == best:
                selected.append((module_id, ";".join(hits)))
    elif source_id in DEFAULT_MODULES:
        selected.append((DEFAULT_MODULES[source_id], "source-scope fallback"))
    return selected[:2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--audit-sample", type=Path, required=True)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--chinese-audit-per-module", type=int, default=30)
    args = parser.parse_args()

    raw_plan = args.plan.read_bytes()
    plan = json.loads(raw_plan)
    plan_hash = hashlib.sha256(raw_plan).hexdigest()
    modules = {module["module_id"]: module for module in plan["modules"]}
    index_rows, index_fields = read_csv(args.index)
    audit_rows, audit_fields = read_csv(args.audit_sample)
    existing = {(row["module_id"], row["work_id"]) for row in index_rows}
    existing_titles = {(row["module_id"], title_key(row["title"])) for row in index_rows}
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    additions: list[dict[str, Any]] = []
    unclassified = 0

    for path in args.input:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for work in payload.get("results", []):
            if work.get("is_retracted"):
                continue
            work_id = str(work.get("id") or "").replace("https://openalex.org/", "")
            title = " ".join(str(work.get("title") or "").split())
            location = work.get("primary_location") or {}
            source = location.get("source") or {}
            source_id = str(source.get("id") or "").replace("https://openalex.org/", "")
            first_author, first_author_id, corresponding = author_fields(work.get("authorships") or [])
            if not all([work_id, title, work.get("publication_year"), source.get("display_name"), first_author]):
                continue
            assignments = classify(title, source_id, plan["modules"])
            if not assignments:
                unclassified += 1
                continue
            oa = work.get("open_access") or {}
            for module_id, hits in assignments:
                normalized_title = title_key(title)
                if (module_id, work_id) in existing or (module_id, normalized_title) in existing_titles:
                    continue
                record = {
                    "module_id": module_id,
                    "module_name": modules[module_id]["name"],
                    "module_rank": 0,
                    "work_id": work_id,
                    "doi": str(work.get("doi") or "").removeprefix("https://doi.org/"),
                    "title": title,
                    "publication_year": work.get("publication_year"),
                    "publication_date": work.get("publication_date") or "",
                    "language": work.get("language") or "zh",
                    "work_type": work.get("type") or "article",
                    "source_name": source.get("display_name") or "",
                    "source_id": source_id,
                    "issn_l": source.get("issn_l") or "",
                    "source_tier": "soil_t1_2024_chinese",
                    "first_author": first_author,
                    "first_author_id": first_author_id,
                    "corresponding_authors": corresponding,
                    "is_open_access": str(bool(oa.get("is_oa"))).lower(),
                    "oa_url": oa.get("oa_url") or "",
                    "cited_by_count": int(work.get("cited_by_count") or 0),
                    "matched_queries": f"title-keyword classification: {hits}",
                    "metadata_source": "OpenAlex API",
                    "retrieved_at": retrieved_at,
                    "query_plan_sha256": plan_hash,
                    "metadata_status": "pending_module_relevance_audit",
                    "fulltext_status": "not_verified",
                    "expression_status": "not_eligible",
                }
                additions.append(record)
                existing.add((module_id, work_id))
                existing_titles.add((module_id, normalized_title))

    index_rows.extend(additions)
    index_rows.sort(key=lambda row: (int(row["module_id"][1:]), 0 if row["metadata_status"] == "metadata_screened" else 1, -int(row.get("cited_by_count") or 0), row["work_id"]))
    for module_id in modules:
        rank = 0
        for row in index_rows:
            if row["module_id"] == module_id:
                rank += 1
                row["module_rank"] = rank
    write_csv(args.index, index_fields, index_rows)

    sample_additions: list[dict[str, Any]] = []
    for module_id in modules:
        candidates = [row for row in additions if row["module_id"] == module_id]
        candidates.sort(key=lambda row: hashlib.sha256(
            f"zh:{module_id}:{row['work_id']}:{plan_hash}".encode("utf-8")
        ).hexdigest())
        for row in candidates[:args.chinese_audit_per_module]:
            sample_additions.append({
                "module_id": module_id, "work_id": row["work_id"], "title": row["title"],
                "source_name": row["source_name"], "first_author": row["first_author"],
                "matched_queries": row["matched_queries"], "metadata_status": row["metadata_status"],
                "relevance_review": "pending", "source_review": "pending",
                "author_position_review": "pending", "work_type_review": "pending",
                "reviewer_1": "", "reviewer_2": "", "adjudicator": "",
                "reviewed_at": "", "notes": "Chinese T1 supplemental audit",
            })
    audit_rows.extend(sample_additions)
    write_csv(args.audit_sample, audit_fields, audit_rows)
    print(f"PASS: added {len(additions)} Chinese-T1 module candidates; {len(sample_additions)} audit rows; {unclassified} records unclassified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

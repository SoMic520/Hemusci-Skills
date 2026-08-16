#!/usr/bin/env python3
"""Build a reproducible, metadata-only D1-D13 literature index from OpenAlex."""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any
import re
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API = "https://api.openalex.org/works"
SELECT = ",".join([
    "id", "doi", "title", "publication_year", "publication_date", "language",
    "type", "cited_by_count", "primary_location", "authorships", "open_access",
    "is_retracted",
])
FIELDS = [
    "module_id", "module_name", "module_rank", "work_id", "doi", "title",
    "publication_year", "publication_date", "language", "work_type",
    "source_name", "source_id", "issn_l", "source_tier", "first_author",
    "first_author_id", "corresponding_authors", "is_open_access", "oa_url",
    "cited_by_count", "matched_queries", "metadata_source", "retrieved_at",
    "query_plan_sha256", "metadata_status", "fulltext_status",
    "expression_status",
]
AUDIT_FIELDS = [
    "module_id", "work_id", "title", "source_name", "first_author",
    "matched_queries", "metadata_status", "relevance_review",
    "source_review", "author_position_review", "work_type_review",
    "reviewer_1", "reviewer_2", "adjudicator", "reviewed_at", "notes",
]


def load_plan(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    plan = json.loads(raw)
    return plan, hashlib.sha256(raw).hexdigest()


def request_json(params: dict[str, str], user_agent: str, retries: int = 4) -> dict[str, Any]:
    url = f"{API}?{urlencode(params)}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
            with urlopen(request, timeout=45) as response:
                return json.load(response)
        except Exception as exc:  # network/API errors are retried and surfaced
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OpenAlex request failed after {retries} attempts: {last_error}")


def fetch_query(
    module_id: str,
    query: str,
    source_policy: str,
    limit: int,
    plan: dict[str, Any],
    user_agent: str,
) -> tuple[str, str, str, list[dict[str, Any]]]:
    filters = [
        f"from_publication_date:{plan['minimum_publication_year']}-01-01",
        "type:article|review",
    ]
    if source_policy == "core":
        filters.append("primary_location.source.is_core:true")
    elif source_policy == "chinese_t1":
        filters.append("primary_location.source.id:" + "|".join(plan["chinese_t1_source_ids"]))
    else:
        raise ValueError(f"unknown source policy: {source_policy}")

    records: list[dict[str, Any]] = []
    cursor = "*"
    while len(records) < limit:
        params = {
            "filter": ",".join(filters),
            "search": query,
            "sort": "cited_by_count:desc",
            "per-page": str(min(100, limit - len(records))),
            "cursor": cursor,
            "select": SELECT,
        }
        payload = request_json(params, user_agent)
        page = payload.get("results", [])
        if not page:
            break
        records.extend(page)
        cursor = payload.get("meta", {}).get("next_cursor")
        if not cursor:
            break
    return module_id, query, source_policy, records[:limit]


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


def normalize_work(
    work: dict[str, Any],
    module: dict[str, Any],
    query: str,
    source_policy: str,
    retrieved_at: str,
    plan_hash: str,
) -> dict[str, Any] | None:
    if work.get("is_retracted"):
        return None
    work_id = str(work.get("id") or "").replace("https://openalex.org/", "")
    title = " ".join(str(work.get("title") or "").split())
    year = work.get("publication_year")
    location = work.get("primary_location") or {}
    source = location.get("source") or {}
    first_author, first_author_id, corresponding = author_fields(work.get("authorships") or [])
    if not all([work_id, title, year, source.get("display_name"), first_author]):
        return None
    open_access = work.get("open_access") or {}
    return {
        "module_id": module["module_id"],
        "module_name": module["name"],
        "module_rank": 0,
        "work_id": work_id,
        "doi": str(work.get("doi") or "").removeprefix("https://doi.org/"),
        "title": title,
        "publication_year": year,
        "publication_date": work.get("publication_date") or "",
        "language": work.get("language") or "unknown",
        "work_type": work.get("type") or "",
        "source_name": source.get("display_name") or "",
        "source_id": str(source.get("id") or "").replace("https://openalex.org/", ""),
        "issn_l": source.get("issn_l") or "",
        "source_tier": "soil_t1_2024_chinese" if source_policy == "chinese_t1" else "openalex_core",
        "first_author": first_author,
        "first_author_id": first_author_id,
        "corresponding_authors": corresponding,
        "is_open_access": str(bool(open_access.get("is_oa"))).lower(),
        "oa_url": open_access.get("oa_url") or "",
        "cited_by_count": int(work.get("cited_by_count") or 0),
        "matched_queries": query,
        "metadata_source": "OpenAlex API",
        "retrieved_at": retrieved_at,
        "query_plan_sha256": plan_hash,
        "metadata_status": "metadata_screened",
        "fulltext_status": "not_verified",
        "expression_status": "not_eligible",
    }


def merge_record(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    queries = set(existing["matched_queries"].split(" || ")) | set(incoming["matched_queries"].split(" || "))
    existing["matched_queries"] = " || ".join(sorted(query for query in queries if query))
    if incoming["source_tier"] == "soil_t1_2024_chinese":
        existing["source_tier"] = incoming["source_tier"]


def title_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-sample-output", type=Path, required=True)
    parser.add_argument("--mailto", default="")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    plan, plan_hash = load_plan(args.plan)
    user_agent = "soil-all-writing-skill/1.0"
    if args.mailto:
        user_agent += f" (mailto:{args.mailto})"
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    modules = {module["module_id"]: module for module in plan["modules"]}
    jobs: list[tuple[str, str, str, int]] = []
    for module in plan["modules"]:
        for query in module["core_queries"]:
            jobs.append((module["module_id"], query, "core", int(plan["core_query_limit"])))
        jobs.append((module["module_id"], module["chinese_query"], "chinese_t1", int(plan["chinese_query_limit"])))

    raw_results: list[tuple[str, str, str, list[dict[str, Any]]]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 8))) as pool:
        futures = [
            pool.submit(fetch_query, module_id, query, policy, limit, plan, user_agent)
            for module_id, query, policy, limit in jobs
        ]
        for future in as_completed(futures):
            raw_results.append(future.result())

    by_module: dict[str, dict[str, dict[str, Any]]] = {module_id: {} for module_id in modules}
    for module_id, query, source_policy, works in raw_results:
        module = modules[module_id]
        for work in works:
            record = normalize_work(work, module, query, source_policy, retrieved_at, plan_hash)
            if record is None:
                continue
            existing = by_module[module_id].get(record["work_id"])
            if existing:
                merge_record(existing, record)
            else:
                by_module[module_id][record["work_id"]] = record

    target = int(plan["target_records_per_module"])
    all_rows: list[dict[str, Any]] = []
    deficits: list[str] = []
    for module_id in sorted(modules, key=lambda value: int(value[1:])):
        candidates = list(by_module[module_id].values())
        candidates.sort(key=lambda row: (
            0 if row["source_tier"] == "soil_t1_2024_chinese" else 1,
            -int(row["cited_by_count"]),
            -int(row["publication_year"]),
            row["work_id"],
        ))
        deduplicated: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for row in candidates:
            key = title_key(row["title"])
            if key in seen_titles:
                continue
            seen_titles.add(key)
            deduplicated.append(row)
        selected = deduplicated[:target]
        if len(selected) < target:
            deficits.append(f"{module_id}: {len(selected)}/{target}")
        for rank, row in enumerate(selected, 1):
            row["module_rank"] = rank
        all_rows.extend(selected)

    if deficits:
        print("ERROR: insufficient unique records: " + "; ".join(deficits))
        return 1
    write_csv(args.output, FIELDS, all_rows)

    sample_size = int(plan["audit_sample_per_module"])
    audit_rows: list[dict[str, Any]] = []
    for module_id in sorted(modules, key=lambda value: int(value[1:])):
        module_rows = [row for row in all_rows if row["module_id"] == module_id]
        module_rows.sort(key=lambda row: hashlib.sha256(
            f"{module_id}:{row['work_id']}:{plan_hash}".encode("utf-8")
        ).hexdigest())
        for row in module_rows[:sample_size]:
            audit_rows.append({
                "module_id": module_id,
                "work_id": row["work_id"],
                "title": row["title"],
                "source_name": row["source_name"],
                "first_author": row["first_author"],
                "matched_queries": row["matched_queries"],
                "metadata_status": row["metadata_status"],
                "relevance_review": "pending",
                "source_review": "pending",
                "author_position_review": "pending",
                "work_type_review": "pending",
                "reviewer_1": "",
                "reviewer_2": "",
                "adjudicator": "",
                "reviewed_at": "",
                "notes": "",
            })
    write_csv(args.audit_sample_output, AUDIT_FIELDS, audit_rows)
    unique_works = len({row["work_id"] for row in all_rows})
    print(f"PASS: wrote {len(all_rows)} module records ({unique_works} unique works) and {len(audit_rows)} audit rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build the D1-D13 metadata index from allowlisted Crossref journal endpoints."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any
import unicodedata
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


BASE = "https://api.crossref.org/journals"
INDEX_FIELDS = [
    "module_id", "module_name", "module_rank", "work_id", "doi", "title",
    "publication_year", "publication_date", "language", "work_type",
    "source_name", "source_id", "issn_l", "source_tier", "first_author",
    "first_author_id", "corresponding_authors", "is_open_access", "oa_url",
    "cited_by_count", "matched_queries", "metadata_source", "retrieved_at",
    "query_plan_sha256", "metadata_status", "fulltext_status", "expression_status",
]
AUDIT_FIELDS = [
    "module_id", "work_id", "title", "source_name", "first_author",
    "matched_queries", "metadata_status", "relevance_review", "source_review",
    "author_position_review", "work_type_review", "reviewer_1", "reviewer_2",
    "adjudicator", "reviewed_at", "notes",
]
SELECT = ",".join([
    "DOI", "title", "author", "published", "published-print", "published-online",
    "container-title", "ISSN", "URL", "type", "license", "link",
    "is-referenced-by-count",
])


def fetch(url: str, user_agent: str, cache_path: Path, delay: float) -> dict[str, Any]:
    if cache_path.is_file():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
            with urlopen(request, timeout=60) as response:
                payload = json.load(response)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            time.sleep(delay)
            return payload
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504}:
                break
            retry_after = int(exc.headers.get("Retry-After", "0") or 0)
            time.sleep(max(retry_after, 2 ** attempt))
        except Exception as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Crossref request failed: {last_error}")


def date_parts(item: dict[str, Any]) -> tuple[str, str]:
    for field in ("published-print", "published-online", "published"):
        parts = (((item.get(field) or {}).get("date-parts") or [[]])[0])
        if parts:
            year = str(parts[0])
            month = int(parts[1]) if len(parts) > 1 else 1
            day = int(parts[2]) if len(parts) > 2 else 1
            return year, f"{int(year):04d}-{month:02d}-{day:02d}"
    return "", ""


def first_author(item: dict[str, Any]) -> str:
    authors = item.get("author") or []
    if not authors:
        return ""
    author = authors[0]
    return " ".join(part for part in [author.get("given", ""), author.get("family", "")] if part).strip()


def title_text(item: dict[str, Any]) -> str:
    titles = item.get("title") or []
    return " ".join(str(titles[0] if titles else "").split())


def title_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def oa_fields(item: dict[str, Any]) -> tuple[str, str]:
    licenses = item.get("license") or []
    open_license = any(
        "creativecommons.org" in str(license_record.get("URL", "")).casefold()
        for license_record in licenses
    )
    return str(open_license).lower(), (item.get("URL") or "") if open_license else ""


def normalize(
    item: dict[str, Any], module: dict[str, Any], source_issn: str,
    source_label: str, retrieved_at: str, plan_hash: str,
) -> dict[str, Any] | None:
    doi = str(item.get("DOI") or "").strip().lower()
    title = title_text(item)
    author = first_author(item)
    year, publication_date = date_parts(item)
    containers = item.get("container-title") or []
    container = str(containers[0] if containers else source_label).strip()
    if not all([doi, title, author, year, container]):
        return None
    if item.get("type") != "journal-article":
        return None
    is_oa, oa_url = oa_fields(item)
    return {
        "module_id": module["module_id"],
        "module_name": module["name"],
        "module_rank": 0,
        "work_id": doi,
        "doi": doi,
        "title": title,
        "publication_year": year,
        "publication_date": publication_date,
        "language": "unknown",
        "work_type": "article",
        "source_name": container,
        "source_id": source_issn,
        "issn_l": source_issn,
        "source_tier": "discipline_high_quality_seed",
        "first_author": author,
        "first_author_id": "",
        "corresponding_authors": "",
        "is_open_access": is_oa,
        "oa_url": oa_url,
        "cited_by_count": int(item.get("is-referenced-by-count") or 0),
        "matched_queries": module["crossref_query"],
        "metadata_source": "Crossref REST API",
        "retrieved_at": retrieved_at,
        "query_plan_sha256": plan_hash,
        "metadata_status": "metadata_screened",
        "fulltext_status": "not_verified",
        "expression_status": "not_eligible",
    }


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
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--mailto", default="")
    parser.add_argument("--rows-per-source", type=int, default=300)
    parser.add_argument("--delay", type=float, default=0.2)
    args = parser.parse_args()

    raw_plan = args.plan.read_bytes()
    plan = json.loads(raw_plan)
    plan_hash = hashlib.sha256(raw_plan).hexdigest()
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    user_agent = "soil-all-writing-skill/1.0"
    if args.mailto:
        user_agent += f" (mailto:{args.mailto})"

    by_module: dict[str, dict[str, dict[str, Any]]] = {}
    for module in plan["modules"]:
        records: dict[str, dict[str, Any]] = {}
        for source_issn, source_label in module["crossref_sources"]:
            params = {
                "filter": f"from-pub-date:{plan['minimum_publication_year']}-01-01,type:journal-article",
                "query.bibliographic": module["crossref_query"],
                "rows": str(args.rows_per_source),
                "select": SELECT,
            }
            url = f"{BASE}/{quote(source_issn)}/works?{urlencode(params)}"
            cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()
            payload = fetch(url, user_agent, args.cache_dir / f"{cache_key}.json", args.delay)
            items = payload.get("message", {}).get("items", [])
            for item in items:
                record = normalize(item, module, source_issn, source_label, retrieved_at, plan_hash)
                if record:
                    records.setdefault(record["work_id"], record)
        by_module[module["module_id"]] = records

    target = int(plan["target_records_per_module"])
    all_rows: list[dict[str, Any]] = []
    deficits: list[str] = []
    for module in plan["modules"]:
        candidates = list(by_module[module["module_id"]].values())
        candidates.sort(key=lambda row: (-int(row["cited_by_count"]), -int(row["publication_year"]), row["work_id"]))
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
            deficits.append(f"{module['module_id']}: {len(selected)}/{target}")
        for rank, row in enumerate(selected, 1):
            row["module_rank"] = rank
        all_rows.extend(selected)
    if deficits:
        print("ERROR: insufficient unique records: " + "; ".join(deficits))
        return 1
    write_csv(args.output, INDEX_FIELDS, all_rows)

    sample_size = int(plan["audit_sample_per_module"])
    audit_rows: list[dict[str, Any]] = []
    for module in plan["modules"]:
        module_rows = [row for row in all_rows if row["module_id"] == module["module_id"]]
        module_rows.sort(key=lambda row: hashlib.sha256(
            f"{module['module_id']}:{row['work_id']}:{plan_hash}".encode("utf-8")
        ).hexdigest())
        for row in module_rows[:sample_size]:
            audit_rows.append({
                "module_id": row["module_id"], "work_id": row["work_id"],
                "title": row["title"], "source_name": row["source_name"],
                "first_author": row["first_author"], "matched_queries": row["matched_queries"],
                "metadata_status": row["metadata_status"], "relevance_review": "pending",
                "source_review": "pending", "author_position_review": "pending",
                "work_type_review": "pending", "reviewer_1": "", "reviewer_2": "",
                "adjudicator": "", "reviewed_at": "", "notes": "",
            })
    write_csv(args.audit_sample_output, AUDIT_FIELDS, audit_rows)
    unique_works = len({row["work_id"] for row in all_rows})
    print(f"PASS: wrote {len(all_rows)} module records ({unique_works} unique works) and {len(audit_rows)} audit rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

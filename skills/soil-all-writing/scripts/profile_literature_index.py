#!/usr/bin/env python3
"""Create an inspectable data-quality profile for the literature index."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import statistics
import unicodedata


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [row for row in csv.DictReader(handle) if any(row.values())]


def normalized_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def rate(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--audit-sample", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = read_rows(args.index)
    audit = read_rows(args.audit_sample)
    modules = sorted({row["module_id"] for row in rows}, key=lambda value: int(value[1:]))
    unique_works = {row["work_id"] for row in rows}
    pair_counts = Counter((row["module_id"], row["work_id"]) for row in rows)
    title_counts = Counter((row["module_id"], normalized_title(row["title"])) for row in rows)
    years = [int(row["publication_year"]) for row in rows if row.get("publication_year", "").isdigit()]
    null_fields = ["doi", "language", "first_author_id", "corresponding_authors", "oa_url"]

    module_profiles: dict[str, object] = {}
    for module_id in modules:
        subset = [row for row in rows if row["module_id"] == module_id]
        quota = [row for row in subset if row["metadata_status"] == "metadata_screened"]
        candidates = [row for row in subset if row["metadata_status"] == "pending_module_relevance_audit"]
        sources = Counter(row["source_name"] for row in subset)
        module_years = [int(row["publication_year"]) for row in subset]
        audit_subset = [row for row in audit if row["module_id"] == module_id]
        audit_pending = sum(
            any(row[field] == "pending" for field in ("relevance_review", "source_review", "author_position_review", "work_type_review"))
            for row in audit_subset
        )
        top_source, top_count = sources.most_common(1)[0]
        module_profiles[module_id] = {
            "records": len(subset),
            "quota_records": len(quota),
            "chinese_t1_pending_candidates": len(candidates),
            "unique_sources": len(sources),
            "top_source": top_source,
            "top_source_share": rate(top_count, len(subset)),
            "year_min": min(module_years),
            "year_median": statistics.median(module_years),
            "year_max": max(module_years),
            "open_access_records": sum(row["is_open_access"].casefold() == "true" for row in subset),
            "audit_rows": len(audit_subset),
            "audit_pending_rows": audit_pending,
        }

    audit_pending_total = sum(
        any(row[field] == "pending" for field in ("relevance_review", "source_review", "author_position_review", "work_type_review"))
        for row in audit
    )
    profile = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataset": str(args.index),
        "intended_grain": "one module_id/work_id assignment per row",
        "row_count": len(rows),
        "unique_work_count": len(unique_works),
        "module_count": len(modules),
        "duplicate_grain_rows": sum(count - 1 for count in pair_counts.values() if count > 1),
        "normalized_title_duplicates_within_module": sum(count - 1 for count in title_counts.values() if count > 1),
        "publication_year": {
            "min": min(years), "median": statistics.median(years), "max": max(years)
        },
        "null_rates": {
            field: rate(sum(not row.get(field, "").strip() or row.get(field, "").strip().casefold() == "unknown" for row in rows), len(rows))
            for field in null_fields
        },
        "status_counts": dict(Counter(row["metadata_status"] for row in rows)),
        "source_tier_counts": dict(Counter(row["source_tier"] for row in rows)),
        "fulltext_status_counts": dict(Counter(row["fulltext_status"] for row in rows)),
        "expression_status_counts": dict(Counter(row["expression_status"] for row in rows)),
        "audit": {
            "rows": len(audit),
            "pending_rows": audit_pending_total,
            "pending_rate": rate(audit_pending_total, len(audit)),
        },
        "modules": module_profiles,
        "use_assessment": {
            "safe_for": ["source discovery", "module quota tracking", "task-local full-text retrieval planning"],
            "not_safe_for": ["direct quotation", "expression reuse", "scientific claim verification", "provenance inference"],
            "release_state": "metadata_index_only_human_audit_and_fulltext_verification_pending",
        },
        "findings": [
            {
                "severity": "high",
                "finding": "No large-index record is full-text verified or expression-qualified.",
                "impact": "The index cannot serve as a quotation bank or evidence source without task-local verification."
            },
            {
                "severity": "high",
                "finding": "All deterministic audit-sample rows remain pending human review.",
                "impact": "Module precision and metadata defect rates have not been empirically estimated by human reviewers."
            },
            {
                "severity": "medium",
                "finding": "Crossref does not supply language or stable author IDs for most quota records.",
                "impact": "Language segmentation and expert-identity matching require enrichment from journal pages or another authority."
            },
            {
                "severity": "medium",
                "finding": "Chinese T1 additions are explicitly pending module-relevance audit.",
                "impact": "They improve discovery coverage but do not count toward the 1000-record qualified quota."
            }
        ]
    }
    args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: wrote data-quality profile for {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

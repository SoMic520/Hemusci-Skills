#!/usr/bin/env python3
"""Search and validate the bundled scientific-figure catalog."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CATALOG = SKILL_ROOT / "references" / "figure-catalog.tsv"
SOURCES = SKILL_ROOT / "references" / "sources.md"
REQUIRED_COLUMNS = (
    "id",
    "name_en",
    "name_zh",
    "aliases",
    "primary_family",
    "tasks",
    "designs",
    "domains",
    "r_packages",
    "r_functions",
    "maturity",
    "cautions",
    "source_keys",
)
ALLOWED_MATURITY = {
    "canonical",
    "domain-standard",
    "composite",
    "recent-method",
    "recent-domain-use",
    "recent-software",
    "revived-composite",
    "niche",
    "caution",
}
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SOURCE_KEY_RE = re.compile(r"^\|\s*`([A-Z][A-Z0-9-]+)`\s*\|", re.MULTILINE)


def split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def load_rows() -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    if not CATALOG.is_file():
        return [], [f"missing catalog: {CATALOG}"]
    with CATALOG.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != list(REQUIRED_COLUMNS):
            errors.append(
                "catalog columns differ from schema: "
                f"expected={list(REQUIRED_COLUMNS)!r} actual={reader.fieldnames!r}"
            )
        rows = list(reader)
    return rows, errors


def known_source_keys() -> set[str]:
    if not SOURCES.is_file():
        return set()
    return set(SOURCE_KEY_RE.findall(SOURCES.read_text(encoding="utf-8")))


def validate_catalog() -> tuple[list[dict[str, str]], list[str], list[str]]:
    rows, errors = load_rows()
    warnings: list[str] = []
    seen: set[str] = set()
    sources = known_source_keys()
    if not sources:
        errors.append(f"no source keys parsed from {SOURCES}")

    for line_no, row in enumerate(rows, start=2):
        missing = [column for column in REQUIRED_COLUMNS if not (row.get(column) or "").strip()]
        if missing:
            errors.append(f"line {line_no}: empty required fields: {', '.join(missing)}")
        row_id = (row.get("id") or "").strip()
        if row_id in seen:
            errors.append(f"line {line_no}: duplicate id: {row_id}")
        seen.add(row_id)
        if row_id and not ID_RE.fullmatch(row_id):
            errors.append(f"line {line_no}: invalid id: {row_id}")
        maturity = (row.get("maturity") or "").strip()
        if maturity and maturity not in ALLOWED_MATURITY:
            errors.append(f"line {line_no}: unsupported maturity: {maturity}")
        for key in split_values(row.get("source_keys") or ""):
            if key not in sources:
                errors.append(f"line {line_no}: unknown source key: {key}")
        if row.get("maturity") == "caution" and "caution" not in row.get("cautions", "").casefold():
            warnings.append(f"line {line_no}: caution entry should state a concrete limitation: {row_id}")

    if len(rows) < 150:
        warnings.append(f"catalog has only {len(rows)} entries; expected broad domain coverage")
    return rows, errors, warnings


def row_haystack(row: dict[str, str]) -> str:
    return " ".join(row.get(column, "") for column in REQUIRED_COLUMNS).casefold()


def query_tokens(query: str) -> list[str]:
    return [token for token in re.split(r"[\s,，/|]+", query.casefold()) if token]


def score_row(row: dict[str, str], tokens: list[str], filters: dict[str, str] | None = None) -> int:
    fields = {
        "id": 5,
        "name_en": 5,
        "name_zh": 5,
        "aliases": 4,
        "tasks": 4,
        "designs": 4,
        "domains": 4,
        "primary_family": 3,
        "r_packages": 2,
        "r_functions": 2,
        "cautions": 1,
    }
    score = 0
    for token in tokens:
        token_score = 0
        for field, weight in fields.items():
            if token in row.get(field, "").casefold():
                token_score = max(token_score, weight)
        if not token_score:
            return 0
        score += token_score
    if filters:
        filter_fields = {
            "tasks": ("tasks", "primary_family"),
            "designs": ("designs",),
            "domains": ("domains",),
        }
        for field, value in filters.items():
            candidates = filter_fields.get(field, (field,))
            if value and any(
                value.casefold() in row.get(candidate, "").casefold()
                for candidate in candidates
            ):
                score += 8
            elif value:
                return 0
    return score


def compact_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "id": row["id"],
        "en": row["name_en"],
        "zh": row["name_zh"],
        "family": row["primary_family"],
        "tasks": row["tasks"],
        "designs": row["designs"],
        "domains": row["domains"],
        "packages": row["r_packages"],
        "maturity": row["maturity"],
        "cautions": row["cautions"],
    }


def output_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Validate and summarize the catalog")
    sub.add_parser("validate", help="Validate catalog schema, IDs, maturity, and source keys")
    sub.add_parser("families", help="List figure families and counts")
    sub.add_parser("stats", help="Show counts by family and maturity")

    search = sub.add_parser("search", help="Search all catalog fields")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)

    recommend = sub.add_parser("recommend", help="Filter by task, design, and domain")
    recommend.add_argument("--task", default="")
    recommend.add_argument("--design", default="")
    recommend.add_argument("--domain", default="")
    recommend.add_argument("--query", default="")
    recommend.add_argument("--limit", type=int, default=20)

    show = sub.add_parser("show", help="Show one entry by stable ID")
    show.add_argument("id")

    args = parser.parse_args()
    rows, errors, warnings = validate_catalog()

    if args.command in {"status", "validate"}:
        payload = {
            "runtimeReady": not errors,
            "catalog": str(CATALOG),
            "sources": str(SOURCES),
            "entries": len(rows),
            "families": len({row.get("primary_family", "") for row in rows}),
            "errors": errors,
            "warnings": warnings,
        }
        output_json(payload)
        return 0 if not errors else 1

    if errors:
        output_json({"runtimeReady": False, "errors": errors})
        return 1

    if args.command == "families":
        output_json(Counter(row["primary_family"] for row in rows).most_common())
        return 0

    if args.command == "stats":
        output_json(
            {
                "entries": len(rows),
                "families": dict(Counter(row["primary_family"] for row in rows).most_common()),
                "maturity": dict(Counter(row["maturity"] for row in rows).most_common()),
                "source_keys": len(known_source_keys()),
            }
        )
        return 0

    if args.command == "show":
        found = next((row for row in rows if row["id"] == args.id), None)
        if not found:
            output_json({"found": False, "id": args.id})
            return 2
        output_json(found)
        return 0

    if args.command == "search":
        tokens = query_tokens(args.query)
        ranked = sorted(
            ((score_row(row, tokens), row) for row in rows),
            key=lambda item: (-item[0], item[1]["id"]),
        )
        result = [compact_row(row) for score, row in ranked if score > 0][: max(1, args.limit)]
        output_json({"query": args.query, "matches": len(result), "results": result})
        return 0


    filters = {"tasks": args.task, "designs": args.design, "domains": args.domain}
    tokens = query_tokens(args.query)
    ranked = sorted(
        ((score_row(row, tokens, filters), row) for row in rows),
        key=lambda item: (-item[0], item[1]["id"]),
    )
    result = [compact_row(row) for score, row in ranked if score > 0][: max(1, args.limit)]
    output_json({"filters": filters, "query": args.query, "matches": len(result), "results": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

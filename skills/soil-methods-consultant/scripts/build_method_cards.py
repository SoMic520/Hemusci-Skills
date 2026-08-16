#!/usr/bin/env python3
"""Build structured method cards from verified corrected pages and outline trees."""

from __future__ import annotations

import csv
import gzip
import json
import os
import re
from pathlib import Path
from typing import Any

from corrected_corpus import load_corrected_page, render_corrected_page


SKILL_ROOT = Path(__file__).resolve().parents[1]
INDEX = SKILL_ROOT / "references" / "index"
OUTPUT = INDEX / "method-cards.json.gz"
JSON_OUTPUT = INDEX / "method-cards.json"

COMPONENT_ROLES = {
    "scope",
    "principle",
    "sampling",
    "preparation",
    "materials",
    "reagents",
    "apparatus",
    "procedure",
    "measurement",
    "calibration",
    "calculation",
    "quality_control",
    "precision",
    "results",
    "interference",
    "caution",
    "safety",
    "notes",
}

METHOD_TERMS = re.compile(
    r"方法|法(?:\s|$|（)|测定|分析|提取|消解|培养|采样|采集|"
    r"分离|分级|估算|检测|滴定|色谱|光谱|核磁|PCR|DGGE|入渗",
    re.IGNORECASE,
)

PRECISION_MARKER = re.compile(
    r"(?:\d|[=≈≤≥±∑√×·^%‰℃°μµ₀-₉⁰-⁹]|"
    r"\b(?:mg|kg|g|ml|mL|L|mol|mmol|cm|mm|nm|ha|MPa|kPa|Pa|min|rpm|pH)\b|"
    r"公式|方程|式中|计算)",
    re.IGNORECASE,
)


def load_json_gz(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def section_role(title: str) -> str:
    rules = (
        ("适用范围", "scope"),
        ("原理", "principle"),
        ("采样", "sampling"),
        ("样品采集", "sampling"),
        ("预处理", "preparation"),
        ("材料", "materials"),
        ("试剂", "reagents"),
        ("仪器", "apparatus"),
        ("设备", "apparatus"),
        ("装置", "apparatus"),
        ("步骤", "procedure"),
        ("操作", "procedure"),
        ("计算", "calculation"),
        ("质量控制", "quality_control"),
        ("精确度", "precision"),
        ("准确度", "precision"),
        ("结果", "results"),
        ("干扰", "interference"),
        ("安全", "safety"),
        ("注意", "caution"),
        ("注释", "notes"),
        ("参考文献", "references"),
        ("进一步阅读", "references"),
    )
    for needle, role in rules:
        if needle in title:
            return role
    if re.match(r"^第\s*\d+\s*章", title):
        return "chapter"
    if re.match(r"^第[一二三四五六七八九十]+篇", title):
        return "part"
    if "引言" in title:
        return "introduction"
    return "section"


def component_role(title: str, fallback: str) -> str:
    if fallback != "section":
        return fallback
    rules = (
        ("制备", "preparation"),
        ("处理", "preparation"),
        ("标定", "calibration"),
        ("校准", "calibration"),
        ("提取", "procedure"),
        ("浸提", "procedure"),
        ("消解", "procedure"),
        ("熏蒸", "procedure"),
        ("测定", "measurement"),
    )
    for needle, role in rules:
        if needle in title:
            return role
    return fallback


def outline_records(volume: int, book: dict[str, Any]) -> list[dict[str, Any]]:
    outline = book.get("outline", [])
    records: list[dict[str, Any]] = []
    stack: dict[int, dict[str, Any]] = {}
    for index, entry in enumerate(outline):
        depth = int(entry.get("depth", 0))
        page = int(entry["page"])
        title = str(entry["title"])
        for old_depth in [value for value in stack if value >= depth]:
            del stack[old_depth]
        parent = stack.get(depth - 1)
        path = [str(stack[value]["title"]) for value in sorted(stack) if value < depth] + [title]
        end_page = page
        for later in outline[index + 1 :]:
            if int(later.get("depth", 0)) <= depth:
                end_page = max(end_page, int(later["page"]) - 1)
                break
            end_page = max(end_page, int(later["page"]))
        record = {
            "id": f"v{volume}-s{index + 1:04d}",
            "parentId": parent["id"] if parent else None,
            "volume": volume,
            "depth": depth,
            "title": title,
            "role": section_role(title),
            "startPage": page,
            "endPage": end_page,
            "path": path,
        }
        records.append(record)
        stack[depth] = record
    return records


def load_review_statuses() -> dict[tuple[int, int], str]:
    result: dict[tuple[int, int], str] = {}
    path = INDEX / "page-review-status.csv.gz"
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            volume = int(str(row["book_id"]).removeprefix("volume-"))
            result[(volume, int(row["pdf_page"]))] = str(row["review_priority"])
    return result


def is_method_root(record: dict[str, Any], descendants: list[dict[str, Any]]) -> bool:
    if record["role"] == "chapter":
        return True
    if record["role"] != "section" or int(record["depth"]) < 2:
        return False
    has_components = any(
        child["role"] in COMPONENT_ROLES and int(child["depth"]) == int(record["depth"]) + 1
        for child in descendants
    )
    return has_components or bool(METHOD_TERMS.search(str(record["title"])))


def build_cards() -> dict[str, Any]:
    review_statuses = load_review_statuses()
    cards: list[dict[str, Any]] = []
    stats: dict[str, Any] = {"volumes": {}}
    for volume in (1, 2):
        book = load_json_gz(INDEX / f"volume-{volume}-book.json.gz")
        page_count = int(book["pageCount"])
        page_texts = {
            page: render_corrected_page(load_corrected_page(volume, page))
            for page in range(1, page_count + 1)
        }
        records = outline_records(volume, book)
        by_parent: dict[str | None, list[dict[str, Any]]] = {}
        for record in records:
            by_parent.setdefault(record["parentId"], []).append(record)

        volume_cards = 0
        for record in records:
            descendants = [
                child
                for child in records
                if len(child["path"]) > len(record["path"])
                and child["path"][: len(record["path"])] == record["path"]
            ]
            if not is_method_root(record, descendants):
                continue
            start = int(record["startPage"])
            end = int(record["endPage"])
            pages = [
                {"page": page, "text": page_texts.get(page, "")}
                for page in range(start, end + 1)
            ]
            component_nodes = [
                {
                    "id": child["id"],
                    "role": component_role(str(child["title"]), str(child["role"])),
                    "title": child["title"],
                    "startPage": child["startPage"],
                    "endPage": child["endPage"],
                    "path": child["path"],
                }
                for child in descendants
                if child["role"] not in {"references", "introduction", "part", "chapter"}
            ]
            priorities = [review_statuses.get((volume, page), "unknown") for page in range(start, end + 1)]
            priority_counts = {value: priorities.count(value) for value in sorted(set(priorities))}
            cards.append(
                {
                    "id": record["id"],
                    "kind": "chapter" if record["role"] == "chapter" else "method",
                    "volume": volume,
                    "volumeLabel": "上册" if volume == 1 else "下册",
                    "title": record["title"],
                    "path": record["path"],
                    "startPage": start,
                    "endPage": end,
                    "components": component_nodes,
                    "pages": pages,
                    "precisionSensitivePages": [
                        item["page"] for item in pages if PRECISION_MARKER.search(item["text"])
                    ],
                    "reviewPriorityCounts": priority_counts,
                }
            )
            volume_cards += 1
        stats["volumes"][str(volume)] = {
            "pageCount": int(book["pageCount"]),
            "outlineNodeCount": len(records),
            "methodCardCount": volume_cards,
        }
    stats["methodCardCount"] = len(cards)
    return {
        "schema": "soil-methods-consultant.method-cards.v1",
        "source": "verified corrected content of 《土壤采样与分析方法》上下册",
        "stats": stats,
        "cards": cards,
    }


def main() -> None:
    payload = build_cards()
    temporary = OUTPUT.with_suffix(OUTPUT.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    os.replace(temporary, OUTPUT)
    json_temporary = JSON_OUTPUT.with_suffix(JSON_OUTPUT.suffix + ".tmp")
    with json_temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    os.replace(json_temporary, JSON_OUTPUT)
    print(json.dumps(payload["stats"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

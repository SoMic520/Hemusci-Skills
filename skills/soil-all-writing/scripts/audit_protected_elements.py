#!/usr/bin/env python3
"""Extract and compare candidate protected elements in UTF-8 text.

This is a conservative regex audit. It reports candidates for human review and
does not establish scientific equivalence.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata


NUMBER = r"(?:\d{1,3}(?:[ ,]\d{3})+|\d+(?:\.\d+)?|\.\d+)(?:[eE][+−-]?\d+)?"
RANGE = rf"{NUMBER}(?:\s*[–—−~-]\s*{NUMBER})?"
MEASURE = rf"(?:{NUMBER}\s*±\s*{NUMBER}|(?:[<>≤≥≈~]\s*)?{RANGE})"
NUMBER_RE = re.compile(rf"(?<![A-Za-z0-9_.])(?:[<>≤≥≈~±]\s*)?{RANGE}\s*%?(?![A-Za-z0-9_.])")
UNIT_RE = re.compile(
    rf"(?<![A-Za-z0-9_]){MEASURE}\s*"
    r"(?:%|°C|K|Pa|kPa|MPa|bar|pH|"
    r"(?:n|µ|μ|m|c|d|h|k|M)?g|(?:n|µ|μ|m|c|d|h|k)?mol|"
    r"mm|cm|dm|km|µm|μm|nm|m|ha|hm[²2]|"
    r"µL|μL|mL|L|s|min|h|d|a|yr)"
    r"(?:\s*[·⋅/]?\s*(?:C|N|P|soil|CO2|CO₂))?"
    r"(?:\s*(?:kg|g|m|cm|mm|ha|hm|L|mol|s|d|h|a|yr)"
    r"(?:\s*[−–-]?\s*[¹²³0-9]+)?)?",
    re.IGNORECASE,
)
CITATION_RES = [
    re.compile(r"\[[0-9]+(?:\s*[-–,]\s*[0-9]+)*\]"),
    re.compile(r"\((?:[^()]{0,80}?\b(?:19|20)\d{2}[a-z]?[^()]*)\)"),
    re.compile(r"（(?:[^（）]{0,80}?(?:19|20)\d{2}[a-z]?[^（）]*)）"),
]
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s<>\]\[\"'，。；;）)]+", re.IGNORECASE)
IDENTIFIER_RE = re.compile(
    r"\b(?:ISBN(?:-1[03])?|ISSN|ORCID|PMID|PMCID|SRA|BioProject|GenBank|"
    r"CAS|GB/T|ISO|ASTM|HJ|NY/T)\s*[:：]?\s*[A-Z0-9][A-Z0-9._:/()−–-]*",
    re.IGNORECASE,
)
CROSS_REF_RE = re.compile(
    r"\b(?:Fig(?:ure)?|Table|Eq(?:uation)?|Section|Appendix|Supplement(?:ary)?)\.?\s*"
    r"[A-Z]?[0-9]+(?:[.−–-][0-9A-Z]+)*\b|"
    r"(?:图|表|式|公式|方程|章节|附录)\s*[A-Z]?[0-9一二三四五六七八九十]+",
    re.IGNORECASE,
)
STAT_RE = re.compile(
    rf"\b(?:p|P|n|N|R2|R²|r|F|t|χ2|χ²|df|CI|RMSE)\s*(?:=|<|>|≤|≥)\s*{NUMBER}\b"
)
CHEM_RE = re.compile(
    r"\b(?:CO2|CO₂|CH4|CH₄|N2O|N₂O|NH4\+?|NH₄\+?|NO3-?|NO₃-?|"
    r"PO4|PO₄|CaCO3|CaCO₃|Fe2\+|Fe3\+|Al3\+)\b"
)


def canonical(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = value.replace("μ", "µ").replace("−", "-").replace("–", "-").replace("—", "-")
    value = re.sub(r"\s+", " ", value.strip())
    return value


def matches(regexes: list[re.Pattern[str]] | re.Pattern[str], text: str) -> list[str]:
    if isinstance(regexes, re.Pattern):
        regexes = [regexes]
    found: list[tuple[int, str]] = []
    for regex in regexes:
        found.extend((m.start(), m.group(0)) for m in regex.finditer(text))
    return [value for _, value in sorted(found)]


def summarize(values: list[str]) -> list[dict[str, object]]:
    raw_by_normalized: dict[str, str] = {}
    counts: Counter[str] = Counter()
    for value in values:
        normalized = canonical(value)
        counts[normalized] += 1
        raw_by_normalized.setdefault(normalized, value)
    return [
        {"value": raw_by_normalized[key], "normalized": key, "count": counts[key]}
        for key in sorted(counts)
    ]


def extract(text: str, source_name: str | None = None) -> dict[str, object]:
    elements = {
        "numbers": summarize(matches(NUMBER_RE, text)),
        "number_unit_pairs": summarize(matches(UNIT_RE, text)),
        "citations": summarize(matches(CITATION_RES, text)),
        "identifiers": summarize(matches([DOI_RE, IDENTIFIER_RE], text)),
        "urls": summarize(matches(URL_RE, text)),
        "cross_references": summarize(matches(CROSS_REF_RE, text)),
        "chemical_or_statistical_tokens": summarize(matches([STAT_RE, CHEM_RE], text)),
    }
    return {
        "schema_version": 1,
        "source": source_name,
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elements": elements,
        "limitations": [
            "Regex extraction produces candidates; it can miss domain-specific notation and can include false positives.",
            "A zero-difference result does not prove semantic or scientific equivalence.",
        ],
    }


def counters(record: dict[str, object]) -> dict[str, Counter[str]]:
    output: dict[str, Counter[str]] = {}
    elements = record.get("elements", {})
    if not isinstance(elements, dict):
        return output
    for category, items in elements.items():
        counter: Counter[str] = Counter()
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("normalized"), str):
                    counter[item["normalized"]] += int(item.get("count", 1))
        output[str(category)] = counter
    return output


def compare(source: str, target: str, source_name: str, target_name: str) -> dict[str, object]:
    source_record = extract(source, source_name)
    target_record = extract(target, target_name)
    source_counters = counters(source_record)
    target_counters = counters(target_record)
    differences: dict[str, dict[str, dict[str, int]]] = {}
    for category in sorted(set(source_counters) | set(target_counters)):
        missing = source_counters.get(category, Counter()) - target_counters.get(category, Counter())
        added = target_counters.get(category, Counter()) - source_counters.get(category, Counter())
        if missing or added:
            differences[category] = {"missing": dict(missing), "added": dict(added)}
    return {
        "schema_version": 1,
        "source_sha256": source_record["source_sha256"],
        "target_sha256": target_record["source_sha256"],
        "passed": not differences,
        "differences": differences,
        "limitations": source_record["limitations"],
    }


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def emit(record: dict[str, object], output: str | None) -> None:
    payload = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    if output:
        Path(output).write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    extract_parser = subparsers.add_parser("extract", help="extract candidate protected elements")
    extract_parser.add_argument("input")
    extract_parser.add_argument("-o", "--output")
    compare_parser = subparsers.add_parser("compare", help="compare protected elements")
    compare_parser.add_argument("source")
    compare_parser.add_argument("target")
    compare_parser.add_argument("-o", "--output")
    args = parser.parse_args()

    if args.command == "extract":
        emit(extract(read_text(args.input), args.input), args.output)
        return 0
    record = compare(read_text(args.source), read_text(args.target), args.source, args.target)
    emit(record, args.output)
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

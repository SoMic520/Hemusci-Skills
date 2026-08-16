#!/usr/bin/env python3
"""Audit bilingual segments for literal Chinese renderings of controlled source phrases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"line {line_number} must be an object")
        records.append(record)
    return records


def audit_segments(segments: list[dict], rules: list[dict]) -> dict:
    findings: list[dict] = []
    source_risks = 0
    for index, segment in enumerate(segments, 1):
        segment_id = segment.get("segment_id") or segment.get("case_id") or f"SEG-{index:04d}"
        source = segment.get("source")
        target = segment.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            findings.append({
                "segment_id": segment_id,
                "severity": "error",
                "issue": "invalid_segment",
                "message": "source and target must both be strings",
            })
            continue
        for rule in rules:
            matches_source = [
                pattern for pattern in rule["source_patterns"]
                if re.search(pattern, source, re.IGNORECASE)
            ]
            if matches_source:
                source_risks += 1
            if rule["forbidden_target"] in target:
                findings.append({
                    "segment_id": segment_id,
                    "severity": "error",
                    "issue": "literal_translation_interference",
                    "rule_id": rule["id"],
                    "forbidden_target": rule["forbidden_target"],
                    "source_triggered": bool(matches_source),
                    "message": rule["release_rule"],
                    "resolution_by_sense": rule["resolution_by_sense"],
                })
            elif matches_source:
                findings.append({
                    "segment_id": segment_id,
                    "severity": "review",
                    "issue": "source_phrase_requires_semantic_alignment_review",
                    "rule_id": rule["id"],
                    "source_triggered": True,
                    "message": "Literal interference is absent; a human reviewer must still confirm that the selected Chinese wording preserves the source proposition.",
                    "resolution_by_sense": rule["resolution_by_sense"],
                })
    errors = sum(item["severity"] == "error" for item in findings)
    reviews = sum(item["severity"] == "review" for item in findings)
    return {
        "schema_version": 1,
        "segment_count": len(segments),
        "source_risk_count": source_risks,
        "error_count": errors,
        "manual_review_count": reviews,
        "release_status": "blocked" if errors else "semantic_review_required" if reviews else "clear",
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segments", type=Path, help="JSONL with segment_id, source, and target")
    parser.add_argument(
        "--rules", type=Path,
        default=ROOT / "assets/translation-interference-rules.json",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        segments = load_jsonl(args.segments)
        rule_data = json.loads(args.rules.read_text(encoding="utf-8"))
        report = audit_segments(segments, rule_data["rules"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 1 if report["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

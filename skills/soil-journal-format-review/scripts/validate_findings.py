#!/usr/bin/env python3
"""Validate structured format-only findings and their target fingerprints."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from scope_policy import require_format_category, validate_format_only_payload

TOP_KEYS = {"schema_version", "document", "scope", "profile_sha256", "source_document_sha256", "findings"}
FINDING_KEYS = {
    "issue_id",
    "story",
    "note_id",
    "paragraph_index",
    "location",
    "category",
    "rule_id",
    "current_format",
    "required_format",
    "action",
    "status",
    "scope",
    "expected_text_sha256",
    "comment",
}
ALLOWED_STORIES = {"document", "footnotes", "endnotes"}
ALLOWED_ACTIONS = {"FIX", "COMMENT", "MANUAL_VERIFY", "NONE"}
ALLOWED_STATUSES = {"OPEN", "FIXED", "COMMENTED", "MANUAL_CHECK", "NOT_APPLICABLE"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,63}$")
STRICT_CONTENT_DOMAIN_RE = re.compile(
    r"(?:方法(?:学)?|统计(?:学)?|结论|研究结果|创新(?:性)?|科学(?:性)?|论文质量|数据质量|可信(?:度)?|"
    r"试验设计|实验设计|methodology|methods?|statistics?|conclusions?|research results?|novelty|"
    r"scientific validity|manuscript quality|data quality|credibility)",
    re.I,
)


def rendered_comment(finding: dict[str, Any]) -> str:
    """Build a bounded comment from validated, format-only fields."""
    issue_id = str(finding["issue_id"])
    return (
        f"{issue_id}｜排版问题：{str(finding['current_format']).strip()}\n"
        f"期刊格式要求：{str(finding['required_format']).strip()}\n"
        f"处理状态：{str(finding['status']).strip()}\n"
        f"规则依据：{str(finding['rule_id']).strip()}"
    )


def validate_findings_payload(payload: Any, *, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return {"status": "FAIL", "errors": ["Findings root must be an object"], "warnings": []}
    for key in sorted(set(payload) - TOP_KEYS):
        errors.append(f"$: unsupported key {key!r}")
    errors.extend(validate_format_only_payload(payload))
    if payload.get("schema_version") != "2.0":
        errors.append("schema_version must be '2.0'")
    if payload.get("scope") != "FORMAT_ONLY":
        errors.append("scope must be FORMAT_ONLY")
    for key in ("profile_sha256", "source_document_sha256"):
        if not SHA256_RE.fullmatch(str(payload.get(key, "")).lower()):
            errors.append(f"{key} must be a SHA-256 hex digest")
    if not str(payload.get("document", "")).strip():
        errors.append("document is required")

    profile_rules = {
        str(rule.get("rule_id")): rule
        for rule in (profile or {}).get("rules", [])
        if isinstance(rule, dict)
    }
    findings = payload.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be a list")
        findings = []
    seen_issues: set[str] = set()
    seen_targets: set[tuple[str, str | None, int]] = set()
    for index, finding in enumerate(findings):
        label = f"findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{label} must be an object")
            continue
        for key in sorted(set(finding) - FINDING_KEYS):
            errors.append(f"{label}: unsupported key {key!r}")
        required = {
            "issue_id",
            "story",
            "paragraph_index",
            "location",
            "category",
            "rule_id",
            "current_format",
            "required_format",
            "action",
            "status",
            "scope",
            "expected_text_sha256",
        }
        missing = [key for key in required if key not in finding or str(finding.get(key, "")).strip() == ""]
        if missing:
            errors.append(f"{label} missing fields: {', '.join(sorted(missing))}")
            continue
        issue_id = str(finding["issue_id"])
        if not ID_RE.fullmatch(issue_id):
            errors.append(f"{label}.issue_id has an invalid form")
        if issue_id in seen_issues:
            errors.append(f"Duplicate issue_id: {issue_id}")
        seen_issues.add(issue_id)
        story = str(finding["story"])
        if story not in ALLOWED_STORIES:
            errors.append(f"{label}.story must be one of {sorted(ALLOWED_STORIES)}")
        note_id = str(finding.get("note_id")) if finding.get("note_id") is not None else None
        if story in {"footnotes", "endnotes"} and note_id is None:
            errors.append(f"{label}.note_id is required for note stories")
        if story == "document" and note_id is not None:
            errors.append(f"{label}.note_id is only valid for note stories")
        paragraph_index = finding.get("paragraph_index")
        if not isinstance(paragraph_index, int) or isinstance(paragraph_index, bool) or paragraph_index < 0:
            errors.append(f"{label}.paragraph_index must be a non-negative integer")
            continue
        target = (story, note_id, paragraph_index)
        if target in seen_targets:
            errors.append(f"{label}: consolidate findings that share one comment target")
        seen_targets.add(target)
        try:
            category = require_format_category(finding["category"], label)
        except ValueError as exc:
            errors.append(str(exc))
            category = ""
        if finding.get("scope") != "FORMAT_ONLY":
            errors.append(f"{label}.scope must be FORMAT_ONLY")
        if finding.get("action") not in ALLOWED_ACTIONS:
            errors.append(f"{label}.action must be one of {sorted(ALLOWED_ACTIONS)}")
        if finding.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{label}.status must be one of {sorted(ALLOWED_STATUSES)}")
        if not SHA256_RE.fullmatch(str(finding.get("expected_text_sha256", "")).lower()):
            errors.append(f"{label}.expected_text_sha256 must be a SHA-256 hex digest")
        rule_id = str(finding.get("rule_id", ""))
        if profile is not None and rule_id not in profile_rules:
            errors.append(f"{label}.rule_id {rule_id!r} is absent from the journal profile")
        elif profile is not None and category and str(profile_rules[rule_id].get("category", "")).upper() != category:
            errors.append(f"{label}.category does not match profile rule {rule_id}")
        supplied = finding.get("comment")
        if supplied is not None and str(supplied).strip() != rendered_comment(finding):
            errors.append(f"{label}.comment must equal the deterministic format-only rendering")
        for field in ("location", "current_format", "required_format", "comment"):
            value = str(finding.get(field, ""))
            if STRICT_CONTENT_DOMAIN_RE.search(value):
                errors.append(
                    f"{label}.{field} contains a content-review domain term; rephrase strictly as an observable format issue"
                )
    return {
        "status": "FAIL" if errors else "PASS",
        "schema_version": "2.0",
        "finding_count": len(findings),
        "issue_ids": sorted(seen_issues),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("findings", type=Path)
    parser.add_argument("--journal-profile", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.findings.read_text(encoding="utf-8"))
        profile = json.loads(args.journal_profile.read_text(encoding="utf-8")) if args.journal_profile else None
        result = validate_findings_payload(payload, profile=profile)
    except (OSError, json.JSONDecodeError) as exc:
        result = {"status": "ERROR", "errors": [str(exc)], "warnings": []}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())

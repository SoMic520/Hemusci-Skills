#!/usr/bin/env python3
"""Validate a source-backed, format-only journal profile (fail closed)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scope_policy import ALLOWED_CATEGORIES, validate_format_only_payload

ALLOWED_STATUS = {"VERIFIED", "INFERRED", "UNVERIFIED"}
ALLOWED_AUTOMATION = {"AUTO_FIX", "COMMENT_ONLY"}
ALLOWED_SOURCE_KINDS = {
    "official_journal_guide",
    "official_template",
    "publisher_guide",
    "cited_standard",
    "user_notice",
    "inferred_recent_articles",
}
TOP_LEVEL_KEYS = {"schema_version", "journal", "scope_statement", "rules"}
JOURNAL_KEYS = {
    "name",
    "article_type",
    "submission_stage",
    "language",
    "accessed_at",
    "official_domain",
    "publisher",
}
RULE_KEYS = {
    "rule_id",
    "category",
    "requirement",
    "applies_to",
    "article_type",
    "source_title",
    "source_url",
    "source_locator",
    "source_kind",
    "source_sha256",
    "source_snapshot",
    "accessed_at",
    "verification_status",
    "automation",
    "notes",
}
REQUIRED_RULE_FIELDS = RULE_KEYS - {"notes", "source_sha256", "source_snapshot"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RULE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{2,63}$")


def _unknown_keys(value: dict[str, Any], allowed: set[str], label: str) -> list[str]:
    return [f"{label}: unsupported key {key!r}" for key in sorted(set(value) - allowed)]


def _parse_date(value: Any, label: str, errors: list[str]) -> date | None:
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError:
        errors.append(f"{label} must be a real date in YYYY-MM-DD form")
        return None
    if parsed > date.today():
        errors.append(f"{label} cannot be in the future")
    return parsed


def _host_matches(host: str, official_domain: str) -> bool:
    host = host.lower().rstrip(".")
    official_domain = official_domain.lower().strip().rstrip(".")
    return bool(host and official_domain and (host == official_domain or host.endswith(f".{official_domain}")))


def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(profile, dict):
        return {"status": "FAIL", "errors": ["Profile root must be an object"], "warnings": []}

    errors.extend(_unknown_keys(profile, TOP_LEVEL_KEYS, "$"))
    errors.extend(validate_format_only_payload(profile))
    if profile.get("schema_version") != "2.0":
        errors.append("schema_version must be '2.0'")

    journal = profile.get("journal")
    if not isinstance(journal, dict):
        errors.append("journal must be an object")
        journal = {}
    else:
        errors.extend(_unknown_keys(journal, JOURNAL_KEYS, "journal"))
    for field in ("name", "article_type", "submission_stage", "language", "accessed_at", "official_domain"):
        if not str(journal.get(field, "")).strip():
            errors.append(f"journal.{field} is required")
    if journal.get("accessed_at"):
        _parse_date(journal["accessed_at"], "journal.accessed_at", errors)
    official_domain = str(journal.get("official_domain", "")).strip()

    scope_statement = str(profile.get("scope_statement", ""))
    if "FORMAT_ONLY" not in scope_statement.upper():
        errors.append("scope_statement must explicitly include FORMAT_ONLY")
    if not any(phrase in scope_statement for phrase in ("不审查", "No scientific-content", "no scientific-content")):
        warnings.append("scope_statement should explicitly exclude scientific-content review")

    rules = profile.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("rules must be a non-empty list")
        rules = []
    seen_ids: set[str] = set()
    for index, rule in enumerate(rules):
        prefix = f"rules[{index}]"
        if not isinstance(rule, dict):
            errors.append(f"{prefix} must be an object")
            continue
        errors.extend(_unknown_keys(rule, RULE_KEYS, prefix))
        missing = [field for field in REQUIRED_RULE_FIELDS if not str(rule.get(field, "")).strip()]
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(sorted(missing))}")
        rule_id = str(rule.get("rule_id", ""))
        if not RULE_ID_RE.fullmatch(rule_id):
            errors.append(f"{prefix}.rule_id must match {RULE_ID_RE.pattern}")
        if rule_id in seen_ids:
            errors.append(f"Duplicate rule_id: {rule_id}")
        seen_ids.add(rule_id)

        category = str(rule.get("category", "")).upper()
        if category not in ALLOWED_CATEGORIES:
            errors.append(f"{prefix}.category is not a format-only category")
        status = str(rule.get("verification_status", ""))
        if status not in ALLOWED_STATUS:
            errors.append(f"{prefix}.verification_status must be one of {sorted(ALLOWED_STATUS)}")
        automation = str(rule.get("automation", ""))
        if automation not in ALLOWED_AUTOMATION:
            errors.append(f"{prefix}.automation must be one of {sorted(ALLOWED_AUTOMATION)}")
        if status != "VERIFIED" and automation == "AUTO_FIX":
            errors.append(f"{prefix}: only VERIFIED rules may use AUTO_FIX")

        source_kind = str(rule.get("source_kind", ""))
        if source_kind not in ALLOWED_SOURCE_KINDS:
            errors.append(f"{prefix}.source_kind must be one of {sorted(ALLOWED_SOURCE_KINDS)}")
        if status == "INFERRED" and source_kind != "inferred_recent_articles":
            errors.append(f"{prefix}: INFERRED rules must use source_kind inferred_recent_articles")
        if source_kind == "inferred_recent_articles" and automation != "COMMENT_ONLY":
            errors.append(f"{prefix}: inferred rules are comment-only")

        source_url = str(rule.get("source_url", ""))
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{prefix}.source_url must be an absolute HTTP(S) URL")
        elif source_kind in {
            "official_journal_guide",
            "official_template",
            "publisher_guide",
        } and not _host_matches(parsed.hostname or "", official_domain):
            errors.append(f"{prefix}.source_url host does not match journal.official_domain")
        if parsed.scheme == "http":
            warnings.append(f"{prefix}.source_url uses HTTP; preserve a local hashed snapshot")

        if rule.get("accessed_at"):
            accessed_date = _parse_date(rule["accessed_at"], f"{prefix}.accessed_at", errors)
            if accessed_date and (date.today() - accessed_date).days > 365:
                warnings.append(f"{prefix}.accessed_at is more than 365 days old; re-check the official source")
        source_sha = str(rule.get("source_sha256", "")).lower()
        if status in {"VERIFIED", "INFERRED"} and not SHA256_RE.fullmatch(source_sha):
            errors.append(f"{prefix}.source_sha256 is required for VERIFIED/INFERRED rules")
        if status in {"VERIFIED", "INFERRED"} and not str(rule.get("source_snapshot", "")).strip():
            errors.append(f"{prefix}.source_snapshot is required for VERIFIED/INFERRED rules")
        if str(rule.get("article_type", "")) not in {str(journal.get("article_type", "")), "ALL"}:
            errors.append(f"{prefix}.article_type does not match journal.article_type or ALL")

    return {
        "status": "FAIL" if errors else "PASS",
        "schema_version": "2.0",
        "rule_ids": sorted(seen_ids),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        result = validate_profile(profile)
    except (OSError, json.JSONDecodeError) as exc:
        result = {"status": "ERROR", "errors": [str(exc)], "warnings": []}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())

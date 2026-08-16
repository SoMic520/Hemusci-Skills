#!/usr/bin/env python3
"""Validate the context-aware soil-science register-control lexicon."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re


REQUIRED_LITERAL_ERRORS = {
    "口径", "闭环", "全链条", "赋能", "抓手", "打通", "拉通", "底层逻辑", "组合拳",
    "赛道", "痛点", "卡点", "颗粒度", "反哺", "落地", "对齐", "链路", "场景",
    "全链路", "复盘", "打法", "触达", "盘活", "护城河", "卡位", "破局", "一站式",
    "兜底", "加码", "压实责任", "高位推动", "打造", "助力", "数字底座", "颠覆性",
    "降维打击", "协同发力", "前瞻布局", "抢占制高点",
    "画像", "数智化", "引领",
}
LEGITIMATE_TECHNICAL_LITERALS = {"生态", "矩阵", "沉淀", "路径", "机制", "体系", "输出"}
GENRE_PROFILES = Path(__file__).resolve().parents[1] / "assets/genre-language-profiles.json"
JOURNAL_SOURCE_REGISTRY = Path(__file__).resolve().parents[1] / "assets/domain-register-source-registry.csv"
AUTHORITY_SOURCE_REGISTRY = Path(__file__).resolve().parents[1] / "assets/domain-register-authority-source-registry.csv"
TRANSLATION_INTERFERENCE_BINDINGS = {"DR002": "TRI001", "DR026": "TRI002"}


def load_source_ids(paths: tuple[Path, ...], errors: list[str]) -> set[str]:
    source_ids: set[str] = set()
    for path in paths:
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except (OSError, csv.Error) as exc:
            errors.append(f"cannot load context-rule source registry {path.name}: {exc}")
            continue
        for row in rows:
            source_id = row.get("source_id", "").strip()
            if not source_id:
                errors.append(f"{path.name}: source row is missing source_id")
            elif source_id in source_ids:
                errors.append(f"duplicate context-rule source_id across registries: {source_id}")
            source_ids.add(source_id)
    return source_ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    try:
        data = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(data.get("lexicon_version"), str) or not data["lexicon_version"].strip():
        errors.append("lexicon_version must be a non-empty string")
    entries = data.get("entries")
    if not isinstance(entries, list):
        errors.append("entries must be an array")
        entries = []
    if len(entries) < 120:
        errors.append("lexicon must contain at least 120 established or evidence-gathered controls")
    review_boundary = data.get("review_boundary")
    if not isinstance(review_boundary, str) or "human soil-domain review" not in review_boundary:
        errors.append("review_boundary must disclose the independent human soil-domain review status")
    known_source_ids = load_source_ids(
        (JOURNAL_SOURCE_REGISTRY, AUTHORITY_SOURCE_REGISTRY), errors
    )
    seen_ids: set[str] = set()
    seen_patterns: set[tuple[str, str]] = set()
    seen_allow_rule_ids: set[str] = set()
    seen_learning_records: set[str] = set()
    literal_errors: set[str] = set()
    for index, entry in enumerate(entries):
        locator = f"entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{locator} must be an object")
            continue
        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not re.fullmatch(r"DR\d{3}", entry_id):
            errors.append(f"{locator}.id must match DRddd")
            entry_id = locator
        elif entry_id in seen_ids:
            errors.append(f"duplicate entry id: {entry_id}")
        seen_ids.add(entry_id)
        pattern = entry.get("pattern")
        match_type = entry.get("match_type")
        severity = entry.get("severity")
        if not isinstance(pattern, str) or not pattern:
            errors.append(f"{entry_id}.pattern must be non-empty")
            continue
        if match_type not in {"literal", "regex"}:
            errors.append(f"{entry_id}.match_type must be literal or regex")
        expression = re.escape(pattern) if match_type == "literal" else pattern
        try:
            compiled = re.compile(expression)
        except re.error as exc:
            errors.append(f"{entry_id}.pattern is invalid: {exc}")
            compiled = None
        pattern_key = (match_type, pattern)
        if pattern_key in seen_patterns:
            errors.append(f"duplicate register pattern: {match_type} {pattern}")
        seen_patterns.add(pattern_key)
        if severity not in {"error", "warning"}:
            errors.append(f"{entry_id}.severity must be error or warning")
        genres = entry.get("genres")
        if not isinstance(genres, list) or not genres or not all(isinstance(item, str) and item for item in genres):
            errors.append(f"{entry_id}.genres must be a non-empty string array")
        allowed = entry.get("allowed_context_patterns")
        if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
            errors.append(f"{entry_id}.allowed_context_patterns must be a string array")
        else:
            if len(set(allowed)) != len(allowed):
                errors.append(f"{entry_id}.allowed_context_patterns contains duplicates")
            for allowed_pattern in allowed:
                try:
                    re.compile(allowed_pattern)
                except re.error as exc:
                    errors.append(f"{entry_id}.allowed context pattern is invalid: {exc}")
                if compiled is not None and not compiled.search(allowed_pattern):
                    errors.append(
                        f"{entry_id}.allowed context does not contain a match of the controlled expression: "
                        f"{allowed_pattern}"
                    )
        rules = entry.get("allowed_context_rules", [])
        if not isinstance(rules, list):
            errors.append(f"{entry_id}.allowed_context_rules must be an array")
            rules = []
        for rule_index, rule in enumerate(rules):
            rule_locator = f"{entry_id}.allowed_context_rules[{rule_index}]"
            if not isinstance(rule, dict):
                errors.append(f"{rule_locator} must be an object")
                continue
            rule_id = rule.get("id")
            if not isinstance(rule_id, str) or not re.fullmatch(rf"{re.escape(entry_id)}-A\d{{2}}", rule_id):
                errors.append(f"{rule_locator}.id must match {entry_id}-Add")
            elif rule_id in seen_allow_rule_ids:
                errors.append(f"duplicate allowed-context rule id: {rule_id}")
            else:
                seen_allow_rule_ids.add(rule_id)
            rule_pattern = rule.get("pattern")
            example = rule.get("example")
            rule_genres = rule.get("genres")
            allowed_terms = rule.get("allowed_terms")
            source_ids = rule.get("source_ids")
            rationale = rule.get("rationale")
            if not isinstance(rule_pattern, str) or not rule_pattern:
                errors.append(f"{rule_locator}.pattern must be non-empty")
                continue
            try:
                compiled_rule = re.compile(rule_pattern)
            except re.error as exc:
                errors.append(f"{rule_locator}.pattern is invalid: {exc}")
                continue
            if not isinstance(example, str) or not example.strip():
                errors.append(f"{rule_locator}.example must be non-empty")
            elif compiled_rule.search(example) is None:
                errors.append(f"{rule_locator}.example does not match its context pattern")
            elif compiled is not None:
                controlled_matches = list(compiled.finditer(example))
                allowed_matches = list(compiled_rule.finditer(example))
                if not any(
                    allow.start() <= control.start() and allow.end() >= control.end()
                    for control in controlled_matches for allow in allowed_matches
                ):
                    errors.append(
                        f"{rule_locator}.example does not bind an occurrence of the controlled expression"
                    )
            if not isinstance(rule_genres, list) or not rule_genres or not all(
                isinstance(item, str) and item for item in rule_genres
            ):
                errors.append(f"{rule_locator}.genres must be a non-empty string array")
            if not isinstance(allowed_terms, list) or not allowed_terms or not all(
                isinstance(item, str) and item for item in allowed_terms
            ):
                errors.append(f"{rule_locator}.allowed_terms must be a non-empty string array")
            elif len(set(allowed_terms)) != len(allowed_terms):
                errors.append(f"{rule_locator}.allowed_terms contains duplicates")
            elif compiled is not None:
                for allowed_term in allowed_terms:
                    if compiled.fullmatch(allowed_term) is None:
                        errors.append(
                            f"{rule_locator}.allowed_terms contains a term outside the controlled expression: "
                            f"{allowed_term}"
                        )
            if not isinstance(source_ids, list) or not source_ids or not all(
                isinstance(item, str) and item for item in source_ids
            ):
                errors.append(f"{rule_locator}.source_ids must be a non-empty string array")
            elif len(set(source_ids)) != len(source_ids):
                errors.append(f"{rule_locator}.source_ids contains duplicates")
            else:
                unknown_sources = set(source_ids) - known_source_ids
                if unknown_sources:
                    errors.append(
                        f"{rule_locator}.source_ids are not registered: "
                        f"{', '.join(sorted(unknown_sources))}"
                    )
            if not isinstance(rationale, str) or not rationale.strip():
                errors.append(f"{rule_locator}.rationale must be non-empty")
        if not isinstance(entry.get("problem"), str) or not entry["problem"].strip():
            errors.append(f"{entry_id}.problem must be non-empty")
        if entry_id in TRANSLATION_INTERFERENCE_BINDINGS:
            if entry.get("issue_class") != "translation_interference_and_target_register":
                errors.append(
                    f"{entry_id}.issue_class must identify translation interference and target register"
                )
            if entry.get("translation_rule_id") != TRANSLATION_INTERFERENCE_BINDINGS[entry_id]:
                errors.append(
                    f"{entry_id}.translation_rule_id must be "
                    f"{TRANSLATION_INTERFERENCE_BINDINGS[entry_id]}"
                )
            if entry.get("allowed_context_patterns") or entry.get("allowed_context_rules"):
                errors.append(f"{entry_id}: translation-interference target must have no context allowlist")
        replacements = entry.get("preferred_by_sense")
        if not isinstance(replacements, list) or not replacements or not all(isinstance(item, str) and item.strip() for item in replacements):
            errors.append(f"{entry_id}.preferred_by_sense must be a non-empty string array")
        if match_type == "literal" and severity == "error":
            literal_errors.add(pattern)
        numeric_id = int(entry_id[2:]) if re.fullmatch(r"DR\d{3}", entry_id) else 0
        if numeric_id >= 91:
            if severity != "warning":
                errors.append(f"{entry_id}: human-review-pending controls must remain warnings")
            if entry.get("qualification_state") != "evidence_gathered_human_domain_review_pending":
                errors.append(f"{entry_id}: invalid or missing qualification_state")
            learning_id = entry.get("learning_record_id")
            expected_learning_id = f"DRL-{numeric_id:04d}"
            if learning_id != expected_learning_id:
                errors.append(f"{entry_id}: learning_record_id must be {expected_learning_id}")
            elif learning_id in seen_learning_records:
                errors.append(f"{entry_id}: duplicate learning_record_id {learning_id}")
            else:
                seen_learning_records.add(learning_id)
    expected_ids = {f"DR{index:03d}" for index in range(1, len(entries) + 1)}
    missing_ids = expected_ids - seen_ids
    extra_ids = seen_ids - expected_ids
    if missing_ids:
        errors.append(f"entry IDs are not contiguous; missing: {', '.join(sorted(missing_ids))}")
    if extra_ids:
        errors.append(f"entry IDs exceed the contiguous range: {', '.join(sorted(extra_ids))}")
    missing = REQUIRED_LITERAL_ERRORS - literal_errors
    if missing:
        errors.append(f"missing required literal error controls: {', '.join(sorted(missing))}")
    overbroad = LEGITIMATE_TECHNICAL_LITERALS & literal_errors
    if overbroad:
        errors.append(f"legitimate technical literals must not be globally banned: {', '.join(sorted(overbroad))}")
    by_pattern = {entry.get("pattern"): entry for entry in entries if isinstance(entry, dict)}
    if by_pattern.get("口径", {}).get("allowed_context_patterns"):
        errors.append("口径 must require an explicit source-locked exception")
    try:
        profile_data = json.loads(GENRE_PROFILES.read_text(encoding="utf-8"))
        known_genres = {profile.get("id") for profile in profile_data.get("profiles", [])}
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot load genre-language profiles: {exc}")
        known_genres = set()
    for entry in entries:
        for rule in entry.get("allowed_context_rules", []) if isinstance(entry, dict) else []:
            if not isinstance(rule, dict) or not isinstance(rule.get("genres"), list):
                continue
            unknown = set(rule["genres"]) - known_genres - {"*"}
            if unknown:
                errors.append(
                    f"{rule.get('id', entry.get('id', 'DR???'))}: unknown genres: "
                    f"{', '.join(sorted(unknown))}"
                )

    context_sensitive_requirements = {
        "DR091": "顶层设计", "DR100": "全域覆盖", "DR105": "新范式",
    }
    by_id = {entry.get("id"): entry for entry in entries if isinstance(entry, dict)}
    for entry_id, expression_name in context_sensitive_requirements.items():
        if not by_id.get(entry_id, {}).get("allowed_context_rules"):
            errors.append(f"{entry_id} {expression_name} must declare executable context rules")

    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} domain-register lexicon error(s)")
        return 1
    print(f"PASS: {len(entries)} domain-register controls are structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

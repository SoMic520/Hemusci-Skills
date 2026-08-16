#!/usr/bin/env python3
"""Validate source-aware translation-interference controls and their case corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "TRI001": ("闭环", "DR002"),
    "TRI002": ("全链条", "DR026"),
}


def read_jsonl(path: Path, errors: list[str]) -> list[dict]:
    records: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        errors.append(f"cannot read case corpus: {exc}")
        return records
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"case line {line_number}: {exc}")
            continue
        if not isinstance(record, dict):
            errors.append(f"case line {line_number}: record must be an object")
            continue
        records.append(record)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "rules", nargs="?", type=Path,
        default=ROOT / "assets/translation-interference-rules.json",
    )
    parser.add_argument(
        "--cases", type=Path,
        default=ROOT / "assets/translation-interference-cases.jsonl",
    )
    parser.add_argument(
        "--register", type=Path,
        default=ROOT / "assets/domain-register-lexicon.json",
    )
    args = parser.parse_args()
    errors: list[str] = []
    try:
        data = json.loads(args.rules.read_text(encoding="utf-8"))
        register = json.loads(args.register.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(data.get("rules_version"), str) or not data["rules_version"].strip():
        errors.append("rules_version must be a non-empty string")
    if "technical-sense label is not an exception" not in data.get("literal_exception_policy", ""):
        errors.append("literal_exception_policy must reject technical-sense exceptions")
    register_entries = {
        entry.get("id"): entry for entry in register.get("entries", []) if isinstance(entry, dict)
    }
    rules = data.get("rules")
    if not isinstance(rules, list):
        errors.append("rules must be an array")
        rules = []
    rule_map: dict[str, dict] = {}
    for index, rule in enumerate(rules):
        locator = f"rules[{index}]"
        if not isinstance(rule, dict):
            errors.append(f"{locator} must be an object")
            continue
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not re.fullmatch(r"TRI\d{3}", rule_id):
            errors.append(f"{locator}.id must match TRIddd")
            continue
        if rule_id in rule_map:
            errors.append(f"duplicate rule id: {rule_id}")
        rule_map[rule_id] = rule
        if rule.get("issue_class") != "translation_interference":
            errors.append(f"{rule_id}.issue_class must be translation_interference")
        source_patterns = rule.get("source_patterns")
        if not isinstance(source_patterns, list) or not source_patterns:
            errors.append(f"{rule_id}.source_patterns must be a non-empty array")
            source_patterns = []
        for pattern in source_patterns:
            try:
                re.compile(pattern, re.IGNORECASE)
            except (TypeError, re.error) as exc:
                errors.append(f"{rule_id}: invalid source pattern: {exc}")
        resolutions = rule.get("resolution_by_sense")
        if not isinstance(resolutions, list) or len(resolutions) < 2:
            errors.append(f"{rule_id}.resolution_by_sense must contain at least two senses")
            resolutions = []
        senses: set[str] = set()
        for resolution in resolutions:
            if not isinstance(resolution, dict):
                errors.append(f"{rule_id}: resolution must be an object")
                continue
            sense = resolution.get("sense")
            if not isinstance(sense, str) or not sense:
                errors.append(f"{rule_id}: resolution sense must be non-empty")
            elif sense in senses:
                errors.append(f"{rule_id}: duplicate resolution sense {sense}")
            senses.add(sense)
            if not isinstance(resolution.get("diagnostic_question"), str) or not resolution["diagnostic_question"].strip():
                errors.append(f"{rule_id}/{sense}: diagnostic_question must be non-empty")
            targets = resolution.get("preferred_target_realizations")
            if not isinstance(targets, list) or not targets or not all(
                isinstance(item, str) and item.strip() for item in targets
            ):
                errors.append(f"{rule_id}/{sense}: preferred_target_realizations must be non-empty")
            elif rule.get("forbidden_target") and any(rule["forbidden_target"] in item for item in targets):
                errors.append(f"{rule_id}/{sense}: preferred target repeats the forbidden literal")
        related_id = rule.get("related_register_entry_id")
        register_entry = register_entries.get(related_id)
        if register_entry is None:
            errors.append(f"{rule_id}: related register entry is missing")
        elif register_entry.get("pattern") != rule.get("forbidden_target"):
            errors.append(f"{rule_id}: forbidden target does not match its register entry")
        elif register_entry.get("severity") != "error" or register_entry.get("allowed_context_patterns"):
            errors.append(f"{rule_id}: related register entry must be an unconditional error")
    if set(rule_map) != set(REQUIRED):
        errors.append(f"rules must be exactly {', '.join(sorted(REQUIRED))}")
    for rule_id, (term, register_id) in REQUIRED.items():
        rule = rule_map.get(rule_id, {})
        if rule.get("forbidden_target") != term or rule.get("related_register_entry_id") != register_id:
            errors.append(f"{rule_id}: required target/register binding is invalid")

    cases = read_jsonl(args.cases, errors)
    seen_cases: set[str] = set()
    status_by_rule: dict[str, set[str]] = {rule_id: set() for rule_id in REQUIRED}
    count_by_rule: dict[str, int] = {rule_id: 0 for rule_id in REQUIRED}
    for index, case in enumerate(cases):
        locator = f"cases[{index}]"
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"{locator}.case_id must be non-empty")
        elif case_id in seen_cases:
            errors.append(f"duplicate case id: {case_id}")
        seen_cases.add(case_id)
        rule_id = case.get("rule_id")
        rule = rule_map.get(rule_id)
        if rule is None:
            errors.append(f"{locator}.rule_id is not registered")
            continue
        count_by_rule[rule_id] += 1
        source = case.get("source")
        target = case.get("target")
        if not isinstance(source, str) or not source.strip() or not isinstance(target, str) or not target.strip():
            errors.append(f"{case_id}: source and target must be non-empty")
            continue
        triggered = any(re.search(pattern, source, re.IGNORECASE) for pattern in rule["source_patterns"])
        if triggered is not case.get("source_trigger_expected"):
            errors.append(f"{case_id}: source trigger result differs from expected")
        status = case.get("target_status")
        if status not in {"error", "allow"}:
            errors.append(f"{case_id}: target_status must be error or allow")
            continue
        status_by_rule[rule_id].add(status)
        contains_forbidden = rule["forbidden_target"] in target
        if (status == "error") is not contains_forbidden:
            errors.append(f"{case_id}: target status does not match forbidden-target occurrence")
        senses = {item.get("sense") for item in rule.get("resolution_by_sense", [])}
        if case.get("sense") not in senses:
            errors.append(f"{case_id}: sense is not declared by {rule_id}")
    for rule_id in REQUIRED:
        if count_by_rule[rule_id] < 6:
            errors.append(f"{rule_id}: at least six source-target cases are required")
        if status_by_rule[rule_id] != {"error", "allow"}:
            errors.append(f"{rule_id}: cases must include both error and allow targets")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} translation-interference validation error(s)")
        return 1
    print(
        f"PASS: {len(rule_map)} source-aware translation rules and {len(cases)} source-target cases are valid"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed validation for a managed-project review manifest."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re


POLICY_STATES = {"allowed", "allowed_with_conditions", "diagnosis_only", "prohibited", "unknown"}
CHECK_STATES = {"pending", "pass", "fail", "not_applicable"}
RELEASE_STATES = {"draft", "review_required", "blocked", "approved_for_delivery", "approved_for_submission"}
REQUIRED_CHECKS = {
    "protected_elements", "terminology", "expression_provenance", "evidence_strength",
    "genre_rules", "naturalness_assurance", "confidentiality", "file_integrity",
}
APPROVAL_ROLES = {"discipline", "genre", "language", "file", "final"}


def valid_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", value))


def validate(record: object) -> list[str]:
    if not isinstance(record, dict):
        return ["manifest root must be an object"]
    errors: list[str] = []
    required = [
        "schema_version", "project_id", "artifact_id", "artifact_sha256", "policy_state",
        "requested_operation", "submission_prose_generated", "checks", "unresolved_items",
        "human_approvals", "release_state", "updated_at",
    ]
    for field in required:
        if field not in record:
            errors.append(f"missing field: {field}")
    if errors:
        return errors
    if record["schema_version"] != 1:
        errors.append("schema_version must be 1")
    if not isinstance(record["project_id"], str) or not record["project_id"].strip():
        errors.append("project_id must be non-empty")
    if not isinstance(record["artifact_id"], str) or not record["artifact_id"].strip():
        errors.append("artifact_id must be non-empty")
    policy = record["policy_state"]
    if policy not in POLICY_STATES:
        errors.append(f"invalid policy_state: {policy}")
    if not isinstance(record["submission_prose_generated"], bool):
        errors.append("submission_prose_generated must be boolean")
    if record["submission_prose_generated"] and policy in {"diagnosis_only", "prohibited", "unknown"}:
        errors.append(f"submission prose cannot be generated when policy_state is {policy}")
    checks = record["checks"]
    if not isinstance(checks, dict):
        errors.append("checks must be an object")
        checks = {}
    else:
        missing_checks = REQUIRED_CHECKS - set(checks)
        if missing_checks:
            errors.append(f"missing checks: {', '.join(sorted(missing_checks))}")
        for name, state in checks.items():
            if state not in CHECK_STATES:
                errors.append(f"invalid check state for {name}: {state}")
    if not isinstance(record["unresolved_items"], list):
        errors.append("unresolved_items must be an array")
    approvals = record["human_approvals"]
    if not isinstance(approvals, list):
        errors.append("human_approvals must be an array")
        approvals = []
    valid_approved_roles: set[str] = set()
    for index, approval in enumerate(approvals):
        label = f"human_approvals[{index}]"
        if not isinstance(approval, dict):
            errors.append(f"{label} must be an object")
            continue
        role = approval.get("role")
        if role not in APPROVAL_ROLES:
            errors.append(f"{label} has invalid role")
        if approval.get("approved") is not True:
            continue
        for field in ("name", "approved_at", "artifact_sha256"):
            if not approval.get(field):
                errors.append(f"{label} approved record requires {field}")
        if approval.get("artifact_sha256") != record["artifact_sha256"]:
            errors.append(f"{label} approval hash does not match artifact")
        try:
            datetime.fromisoformat(str(approval.get("approved_at", "")).replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"{label} approved_at must be ISO 8601")
        if isinstance(role, str):
            valid_approved_roles.add(role)
    release = record["release_state"]
    if release not in RELEASE_STATES:
        errors.append(f"invalid release_state: {release}")
    if record["updated_at"] is not None:
        try:
            datetime.fromisoformat(str(record["updated_at"]).replace("Z", "+00:00"))
        except ValueError:
            errors.append("updated_at must be ISO 8601 or null")

    if release in {"approved_for_delivery", "approved_for_submission"}:
        if not valid_sha256(record["artifact_sha256"]):
            errors.append(f"{release} requires artifact_sha256")
        if policy not in {"allowed", "allowed_with_conditions"}:
            errors.append(f"{release} requires an allowed policy state")
        failed = [name for name, state in checks.items() if state not in {"pass", "not_applicable"}]
        if failed:
            errors.append(f"{release} requires completed checks: {', '.join(sorted(failed))}")
        if record["unresolved_items"]:
            errors.append(f"{release} cannot contain unresolved_items")
        if "final" not in valid_approved_roles:
            errors.append(f"{release} requires final human approval")
    if release == "approved_for_submission":
        for role in ("discipline", "genre", "language", "final"):
            if role not in valid_approved_roles:
                errors.append(f"approved_for_submission requires {role} approval")
    if release == "blocked" and not (
        policy in {"prohibited", "unknown"}
        or any(state == "fail" for state in checks.values())
        or bool(record["unresolved_items"])
    ):
        errors.append("blocked state requires a policy block, failed check, or unresolved item")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        record = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    errors = validate(record)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        return 1
    print("PASS: project manifest is valid for its declared release state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

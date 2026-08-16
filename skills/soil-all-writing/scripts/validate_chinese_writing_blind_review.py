#!/usr/bin/env python3
"""Validate origin-blinded Chinese scientific-writing A/B review records."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys


DIMENSIONS = {
    "scientific_accuracy",
    "evidence_calibration",
    "terminology",
    "genre_fit",
    "logic_and_cohesion",
    "chinese_naturalness",
}
ROLES = {"soil_science", "chinese_language", "genre_specialist", "statistics"}


def sha256(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def validate(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["review root must be an object"]
    errors: list[str] = []
    required = {
        "schema_version", "evaluation_id", "status", "language", "genre",
        "task_prompt_sha256", "source_material_sha256", "origin_blinded",
        "candidate_origin_names_stored", "randomization_record_sha256", "dimensions",
        "candidates", "reviewers", "minimum_reviewers", "unblinding_receipt_sha256",
    }
    missing = required - set(payload)
    if missing:
        return ["missing fields: " + ", ".join(sorted(missing))]
    if payload["schema_version"] != 1:
        errors.append("schema_version must be 1")
    if payload["status"] not in {"draft", "completed"}:
        errors.append("status must be draft or completed")
    if payload["language"] not in {"zh-CN", "bilingual"}:
        errors.append("language must be zh-CN or bilingual")
    if payload["origin_blinded"] is not True:
        errors.append("origin_blinded must be true")
    if payload["candidate_origin_names_stored"] is not False:
        errors.append("candidate origin names must not be stored in the blinded record")
    dimensions = payload["dimensions"]
    if not isinstance(dimensions, list) or set(dimensions) != DIMENSIONS:
        errors.append("dimensions must contain the six controlled review dimensions exactly once")
        dimensions = []
    minimum_reviewers = payload["minimum_reviewers"]
    if not isinstance(minimum_reviewers, int) or minimum_reviewers < 3:
        errors.append("minimum_reviewers must be an integer of at least 3")

    candidates = payload["candidates"]
    if not isinstance(candidates, list):
        errors.append("candidates must be an array")
        candidates = []
    labels: set[str] = set()
    for index, candidate in enumerate(candidates):
        label = f"candidates[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{label} must be an object")
            continue
        candidate_label = candidate.get("candidate_label")
        if not isinstance(candidate_label, str) or not re.fullmatch(r"[A-Z]", candidate_label):
            errors.append(f"{label}.candidate_label must be one capital letter")
        elif candidate_label in labels:
            errors.append(f"duplicate candidate_label {candidate_label}")
        labels.add(str(candidate_label))
        if not sha256(candidate.get("artifact_sha256")):
            errors.append(f"{label}.artifact_sha256 must be SHA-256")
        if candidate.get("complete") is not True:
            errors.append(f"{label}.complete must be true")

    reviewers = payload["reviewers"]
    if not isinstance(reviewers, list):
        errors.append("reviewers must be an array")
        reviewers = []
    reviewer_ids: set[str] = set()
    roles: set[str] = set()
    for index, reviewer in enumerate(reviewers):
        label = f"reviewers[{index}]"
        if not isinstance(reviewer, dict):
            errors.append(f"{label} must be an object")
            continue
        reviewer_id = str(reviewer.get("reviewer_id") or "")
        if not reviewer_id or reviewer_id in reviewer_ids:
            errors.append(f"{label} requires a unique reviewer_id")
        reviewer_ids.add(reviewer_id)
        role = reviewer.get("role")
        if role not in ROLES:
            errors.append(f"{label}.role is invalid")
        roles.add(str(role))
        if reviewer.get("human") is not True or reviewer.get("origin_blinded") is not True:
            errors.append(f"{label} must be a human origin-blinded reviewer")
        try:
            datetime.fromisoformat(str(reviewer.get("reviewed_at", "")).replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"{label}.reviewed_at must be ISO 8601")
        scores = reviewer.get("scores")
        if not isinstance(scores, dict) or set(scores) != labels:
            errors.append(f"{label}.scores must cover every candidate label")
            continue
        for candidate_label, candidate_scores in scores.items():
            if not isinstance(candidate_scores, dict) or set(candidate_scores) != set(dimensions):
                errors.append(f"{label}.scores.{candidate_label} must cover every dimension")
                continue
            if any(not isinstance(value, int) or not 1 <= value <= 5 for value in candidate_scores.values()):
                errors.append(f"{label}.scores.{candidate_label} values must be integers from 1 to 5")
        if reviewer.get("preferred_candidate") not in labels:
            errors.append(f"{label}.preferred_candidate is invalid")
        if not isinstance(reviewer.get("evidence_comments"), list) or not reviewer.get("evidence_comments"):
            errors.append(f"{label}.evidence_comments must be a non-empty array")

    if payload["status"] == "completed":
        for field in ("task_prompt_sha256", "source_material_sha256", "randomization_record_sha256", "unblinding_receipt_sha256"):
            if not sha256(payload[field]):
                errors.append(f"completed review requires {field} as SHA-256")
        if len(candidates) < 2:
            errors.append("completed review requires at least two candidates")
        if isinstance(minimum_reviewers, int) and len(reviewers) < minimum_reviewers:
            errors.append("completed review has fewer reviewers than minimum_reviewers")
        if not {"soil_science", "chinese_language"}.issubset(roles):
            errors.append("completed review requires soil_science and chinese_language reviewers")
    elif candidates or reviewers:
        errors.append("draft template must not contain partially completed candidates or reviewers")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    errors = validate(payload)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} blind-review error(s)")
        return 1
    print(f"PASS: Chinese writing blind-review record is valid for state {payload['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

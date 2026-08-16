#!/usr/bin/env python3
"""Validate NAR-1.0 naturalness review records without inferring text provenance."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re


FEATURE_IDS = {f"N{index:02d}" for index in range(1, 13)}
FEATURE_STATES = {"pending", "absent", "present", "not_assessable"}
FINAL_STATES = {"draft", "review_required", "failed", "zero_confirmed_residual_features_within_scope"}
ALLOWED_ASSERTION_SCOPE = "NAR-1.0_zero_confirmed_residual_features_only_not_provenance"


def sha256(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", value))


def validate(record: object) -> list[str]:
    if not isinstance(record, dict):
        return ["review root must be an object"]
    errors: list[str] = []
    required = {
        "schema_version", "protocol_id", "artifact_sha256", "language", "genre",
        "review_scope", "author_style_corpus_ids", "detector_scores_used",
        "provenance_claim", "reviewers", "features", "raw_percent_agreement",
        "cohens_kappa", "disagreements", "adjudication_completed",
        "unresolved_items", "final_status", "assertion_scope",
    }
    missing = required - set(record)
    if missing:
        return ["missing fields: " + ", ".join(sorted(missing))]
    if record["schema_version"] != 1 or record["protocol_id"] != "NAR-1.0":
        errors.append("schema_version/protocol_id must identify NAR-1.0")
    if record["detector_scores_used"] is not False:
        errors.append("detector_scores_used must be false")
    if record["provenance_claim"] is not False:
        errors.append("provenance_claim must be false")
    if not isinstance(record["review_scope"], list) or not record["review_scope"]:
        errors.append("review_scope must be a non-empty array")
    if not isinstance(record["unresolved_items"], list):
        errors.append("unresolved_items must be an array")

    features = record["features"]
    feature_states: dict[str, str] = {}
    if not isinstance(features, list):
        errors.append("features must be an array")
        features = []
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            errors.append(f"features[{index}] must be an object")
            continue
        feature_id = feature.get("feature_id")
        status = feature.get("status")
        if feature_id in feature_states:
            errors.append(f"duplicate feature_id {feature_id}")
        if feature_id not in FEATURE_IDS:
            errors.append(f"invalid feature_id {feature_id}")
        if status not in FEATURE_STATES:
            errors.append(f"invalid status for {feature_id}: {status}")
        if not isinstance(feature.get("evidence_locators"), list):
            errors.append(f"{feature_id} evidence_locators must be an array")
        if isinstance(feature_id, str):
            feature_states[feature_id] = status
    missing_features = FEATURE_IDS - set(feature_states)
    if missing_features:
        errors.append("missing features: " + ", ".join(sorted(missing_features)))

    reviewers = record["reviewers"]
    if not isinstance(reviewers, list):
        errors.append("reviewers must be an array")
        reviewers = []
    valid_reviewers: list[dict[str, object]] = []
    reviewer_ids: set[str] = set()
    for index, reviewer in enumerate(reviewers):
        label = f"reviewers[{index}]"
        if not isinstance(reviewer, dict):
            errors.append(f"{label} must be an object")
            continue
        reviewer_id = str(reviewer.get("reviewer_id") or "").strip()
        if not reviewer_id or reviewer_id in reviewer_ids:
            errors.append(f"{label} requires a unique reviewer_id")
        reviewer_ids.add(reviewer_id)
        if reviewer.get("role") not in {"discipline", "language", "adjudicator"}:
            errors.append(f"{label} has invalid role")
        if reviewer.get("independent") is not True or reviewer.get("origin_blinded") is not True:
            errors.append(f"{label} must be independent and origin_blinded")
        if reviewer.get("artifact_sha256") != record["artifact_sha256"]:
            errors.append(f"{label} artifact hash mismatch")
        try:
            datetime.fromisoformat(str(reviewer.get("reviewed_at", "")).replace("Z", "+00:00"))
        except ValueError:
            errors.append(f"{label} reviewed_at must be ISO 8601")
        valid_reviewers.append(reviewer)

    final_status = record["final_status"]
    if final_status not in FINAL_STATES:
        errors.append("invalid final_status")
    if final_status == "zero_confirmed_residual_features_within_scope":
        if not sha256(record["artifact_sha256"]):
            errors.append("zero-residual status requires artifact_sha256")
        roles = {reviewer.get("role") for reviewer in valid_reviewers}
        primary_reviewers = [reviewer for reviewer in valid_reviewers if reviewer.get("role") in {"discipline", "language"}]
        if len(primary_reviewers) < 2 or not {"discipline", "language"} <= roles:
            errors.append("zero-residual status requires distinct discipline and language reviewers")
        if any(status != "absent" for status in feature_states.values()):
            errors.append("zero-residual status requires all N01-N12 features absent")
        if record["unresolved_items"]:
            errors.append("zero-residual status cannot contain unresolved_items")
        if record["disagreements"] and record["adjudication_completed"] is not True:
            errors.append("all disagreements require completed adjudication")
        if record["assertion_scope"] != ALLOWED_ASSERTION_SCOPE:
            errors.append("zero-residual status requires the controlled assertion_scope")
        agreement = record["raw_percent_agreement"]
        if not isinstance(agreement, (int, float)) or not 0 <= agreement <= 100:
            errors.append("zero-residual status requires raw_percent_agreement from 0 to 100")
    elif record["assertion_scope"] is not None:
        errors.append("assertion_scope must be null unless zero-residual status is achieved")
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
        print(f"FAILED: {len(errors)} naturalness-review error(s)")
        return 1
    print(f"PASS: NAR-1.0 review record is valid for state {record['final_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

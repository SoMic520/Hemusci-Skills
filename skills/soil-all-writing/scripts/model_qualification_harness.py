#!/usr/bin/env python3
"""Prepare, score, validate, and record provider-neutral model smoke tests."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = {
    "openai", "anthropic", "google-gemini", "deepseek", "qwen", "mistral",
    "cohere", "amazon-bedrock", "ollama", "custom",
}
DECISIONS = {"preserve", "revise", "flag", "refuse"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPLACE_RE = re.compile(r"(^|[_-])REPLACE($|[_-])", re.IGNORECASE)


class QualificationError(ValueError):
    """Raised when a qualification artifact violates the frozen contract."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualificationError(f"cannot read JSON {path}: {exc}") from exc


def write_json_new(path: Path, payload: Any) -> None:
    if path.exists():
        raise QualificationError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise QualificationError(f"cannot hash {path}: {exc}") from exc


def skill_bundle_sha256() -> str:
    digest = hashlib.sha256()
    excluded_names = {".DS_Store"}
    files = [
        path for path in ROOT.rglob("*")
        if path.is_file()
        and path.name not in excluded_names
        and not path.name.startswith("._")
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    ]
    for path in sorted(files, key=lambda item: item.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def iso_datetime(value: str, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QualificationError(f"{field} must be ISO 8601") from exc
    if parsed.tzinfo is None:
        raise QualificationError(f"{field} must include a timezone")
    return value


def string_list(value: Any, field: str, probe_id: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise QualificationError(f"{probe_id}: {field} must be a list of non-empty strings")
    return value


def validate_suite_data(suite: Any) -> list[dict[str, Any]]:
    if not isinstance(suite, dict):
        raise QualificationError("suite must be a JSON object")
    required_top = {
        "schema_version", "suite_id", "suite_version", "suite_level", "content_class",
        "release_scope", "answer_leakage_control", "allowed_decisions", "probes",
    }
    missing = sorted(required_top - set(suite))
    if missing:
        raise QualificationError(f"suite missing fields: {', '.join(missing)}")
    if suite["schema_version"] != 1 or suite["suite_level"] != "smoke":
        raise QualificationError("suite must use schema_version 1 and suite_level smoke")
    if suite["content_class"] != "synthetic_non_sensitive":
        raise QualificationError("smoke suite must contain synthetic non-sensitive content only")
    if suite["release_scope"] != "endpoint_behavior_screen_only_not_full_qualification":
        raise QualificationError("suite release_scope must preserve the smoke-only boundary")
    if set(suite["allowed_decisions"]) != DECISIONS:
        raise QualificationError("allowed_decisions does not match the harness decision contract")
    probes = suite["probes"]
    if not isinstance(probes, list) or len(probes) < 12:
        raise QualificationError("smoke suite must contain at least 12 probes")
    ids: set[str] = set()
    categories: set[str] = set()
    for index, probe in enumerate(probes, 1):
        if not isinstance(probe, dict):
            raise QualificationError(f"probe {index} must be an object")
        required = {
            "probe_id", "category", "capability_level", "instruction", "source_text",
            "expected_decision", "must_preserve", "must_include", "forbidden_literals",
            "forbidden_regex", "output_json_required", "required_json_fields",
        }
        missing_probe = sorted(required - set(probe))
        if missing_probe:
            raise QualificationError(f"probe {index} missing fields: {', '.join(missing_probe)}")
        probe_id = probe["probe_id"]
        if not isinstance(probe_id, str) or not re.fullmatch(r"MQ-\d{2,}", probe_id):
            raise QualificationError(f"probe {index}: invalid probe_id")
        if probe_id in ids:
            raise QualificationError(f"duplicate probe_id: {probe_id}")
        ids.add(probe_id)
        category = probe["category"]
        if not isinstance(category, str) or not category:
            raise QualificationError(f"{probe_id}: category is required")
        categories.add(category)
        if probe["capability_level"] not in {"P0", "P1", "P2", "P3", "P4"}:
            raise QualificationError(f"{probe_id}: invalid capability_level")
        for field in ("instruction", "source_text"):
            if not isinstance(probe[field], str) or not probe[field].strip():
                raise QualificationError(f"{probe_id}: {field} is required")
        if probe["expected_decision"] not in DECISIONS:
            raise QualificationError(f"{probe_id}: invalid expected_decision")
        for field in ("must_preserve", "must_include", "forbidden_literals", "forbidden_regex", "required_json_fields"):
            string_list(probe[field], field, probe_id)
        for pattern in probe["forbidden_regex"]:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise QualificationError(f"{probe_id}: invalid forbidden_regex {pattern!r}: {exc}") from exc
        if not isinstance(probe["output_json_required"], bool):
            raise QualificationError(f"{probe_id}: output_json_required must be boolean")
        if probe["output_json_required"] and not probe["required_json_fields"]:
            raise QualificationError(f"{probe_id}: structured output requires fields")
        if not probe["output_json_required"] and probe["required_json_fields"]:
            raise QualificationError(f"{probe_id}: non-JSON output cannot require JSON fields")
        minimum = probe.get("min_chars")
        maximum = probe.get("max_chars")
        if minimum is not None and (not isinstance(minimum, int) or minimum < 0):
            raise QualificationError(f"{probe_id}: min_chars must be a non-negative integer")
        if maximum is not None and (not isinstance(maximum, int) or maximum < 0):
            raise QualificationError(f"{probe_id}: max_chars must be a non-negative integer")
        if minimum is not None and maximum is not None and maximum < minimum:
            raise QualificationError(f"{probe_id}: max_chars must not be smaller than min_chars")
    required_categories = {
        "protected_elements", "citation_integrity", "epistemic_strength", "statistics",
        "classification", "standard", "domain_register", "prompt_injection",
        "confidentiality", "truncation", "structured_output", "grant_policy",
    }
    missing_categories = sorted(required_categories - categories)
    if missing_categories:
        raise QualificationError(f"suite missing categories: {', '.join(missing_categories)}")
    return probes


def validate_suite(path: Path) -> dict[str, Any]:
    suite = read_json(path)
    validate_suite_data(suite)
    return suite


def validate_provider_metadata(args: argparse.Namespace) -> None:
    if args.provider not in PROVIDERS:
        raise QualificationError(f"unsupported provider: {args.provider}")
    for field in ("endpoint_type", "model_id", "model_revision", "adapter_id"):
        value = getattr(args, field)
        if not value or REPLACE_RE.search(value):
            raise QualificationError(f"{field} must identify the exact tested configuration, not a placeholder")
    if args.provider == "amazon-bedrock" and not args.region:
        raise QualificationError("amazon-bedrock runs require --region")
    if not SHA256_RE.fullmatch(args.system_prompt_sha256):
        raise QualificationError("system_prompt_sha256 must be 64 lowercase hexadecimal characters")


def prepare(args: argparse.Namespace) -> None:
    suite = validate_suite(args.suite)
    validate_provider_metadata(args)
    output_dir = args.output_dir
    manifest_path = output_dir / "run-manifest.json"
    request_path = output_dir / "requests.answer-free.jsonl"
    response_path = output_dir / "responses.normalized.jsonl"
    for target in (manifest_path, request_path, response_path):
        if target.exists():
            raise QualificationError(f"refusing to overwrite existing run artifact: {target}")
    output_dir.mkdir(parents=True, exist_ok=True)
    prepared_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    suite_hash = sha256_file(args.suite)
    run_seed = "|".join([
        suite_hash, args.provider, args.endpoint_type, args.model_id, args.model_revision,
        args.region or "", args.adapter_id, args.system_prompt_sha256, prepared_at,
    ])
    run_id = "SAW-MQ-" + hashlib.sha256(run_seed.encode("utf-8")).hexdigest()[:16]
    request_records = []
    for probe in suite["probes"]:
        request_records.append({
            "probe_id": probe["probe_id"],
            "category": probe["category"],
            "capability_level": probe["capability_level"],
            "instruction": probe["instruction"],
            "source_text": probe["source_text"],
            "response_contract": {
                "type": "object",
                "required": ["probe_id", "decision", "output_text", "complete"],
                "properties": {
                    "probe_id": {"const": probe["probe_id"]},
                    "decision": {"enum": suite["allowed_decisions"]},
                    "output_text": {"type": "string"},
                    "complete": {"const": True},
                },
                "additionalProperties": False,
            },
        })
    request_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in request_records),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "status": "prepared_not_executed",
        "prepared_at": prepared_at,
        "suite_id": suite["suite_id"],
        "suite_version": suite["suite_version"],
        "suite_level": "smoke",
        "suite_sha256": suite_hash,
        "request_bundle_sha256": sha256_file(request_path),
        "skill_bundle_sha256": skill_bundle_sha256(),
        "system_prompt_sha256": args.system_prompt_sha256,
        "provider": args.provider,
        "endpoint_type": args.endpoint_type,
        "model_id": args.model_id,
        "model_revision": args.model_revision,
        "region": args.region or "not_applicable",
        "adapter_id": args.adapter_id,
        "request_bundle": request_path.name,
        "normalized_responses": response_path.name,
        "response_contract": "one JSON object per line; no markdown fences; exact probe coverage",
        "release_scope": "smoke_only_not_full_qualification",
    }
    write_json_new(manifest_path, manifest)
    print(f"PASS: prepared {len(request_records)} answer-free probes in {output_dir}")
    print("NEXT: execute requests through the named adapter, then write responses.normalized.jsonl")


def read_responses(path: Path, expected_ids: list[str]) -> dict[str, dict[str, Any]]:
    responses: dict[str, dict[str, Any]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise QualificationError(f"cannot read responses {path}: {exc}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise QualificationError(f"response line {line_number}: invalid JSON: {exc}") from exc
        if not isinstance(item, dict):
            raise QualificationError(f"response line {line_number}: object required")
        if set(item) - {"probe_id", "decision", "output_text", "complete", "raw_response_ref"}:
            raise QualificationError(f"response line {line_number}: unexpected fields")
        for field in ("probe_id", "decision", "output_text", "complete"):
            if field not in item:
                raise QualificationError(f"response line {line_number}: missing {field}")
        probe_id = item["probe_id"]
        if probe_id in responses:
            raise QualificationError(f"duplicate response for {probe_id}")
        if item["decision"] not in DECISIONS:
            raise QualificationError(f"{probe_id}: invalid decision")
        if not isinstance(item["output_text"], str):
            raise QualificationError(f"{probe_id}: output_text must be a string")
        if not isinstance(item["complete"], bool):
            raise QualificationError(f"{probe_id}: complete must be boolean")
        responses[probe_id] = item
    expected = set(expected_ids)
    actual = set(responses)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise QualificationError(f"response coverage mismatch; missing={missing}; extra={extra}")
    return responses


def validate_manifest(manifest: Any, suite_path: Path, suite: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise QualificationError("manifest must be a schema_version 1 object")
    required = {
        "run_id", "status", "prepared_at", "suite_id", "suite_version", "suite_level",
        "suite_sha256", "request_bundle_sha256", "skill_bundle_sha256", "system_prompt_sha256",
        "provider", "endpoint_type", "model_id", "model_revision", "region", "adapter_id",
        "request_bundle", "normalized_responses", "release_scope",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise QualificationError(f"manifest missing fields: {', '.join(missing)}")
    if manifest["status"] != "prepared_not_executed":
        raise QualificationError("manifest status must remain prepared_not_executed; execution is recorded in the receipt")
    if manifest["suite_id"] != suite["suite_id"] or manifest["suite_version"] != suite["suite_version"]:
        raise QualificationError("manifest suite identity does not match suite")
    if manifest["suite_level"] != "smoke" or manifest["release_scope"] != "smoke_only_not_full_qualification":
        raise QualificationError("manifest must preserve the smoke-only release boundary")
    if manifest["suite_sha256"] != sha256_file(suite_path):
        raise QualificationError("manifest suite hash does not match the current suite")
    if manifest["skill_bundle_sha256"] != skill_bundle_sha256():
        raise QualificationError("current Skill bundle differs from the bundle bound at prepare time")
    if manifest["provider"] not in PROVIDERS:
        raise QualificationError("manifest provider is unsupported")
    for field in ("suite_sha256", "request_bundle_sha256", "skill_bundle_sha256", "system_prompt_sha256"):
        if not isinstance(manifest[field], str) or not SHA256_RE.fullmatch(manifest[field]):
            raise QualificationError(f"manifest {field} is not a SHA-256 value")
    iso_datetime(manifest["prepared_at"], "prepared_at")
    return manifest


def score_responses(
    suite: dict[str, Any], responses: dict[str, dict[str, Any]], profile_verified: bool,
) -> tuple[list[dict[str, Any]], int]:
    results: list[dict[str, Any]] = []
    failures = 0
    for probe in suite["probes"]:
        response = responses[probe["probe_id"]]
        output = response["output_text"]
        failed: list[str] = []
        if response["decision"] != probe["expected_decision"]:
            failed.append("decision_mismatch")
        if not response["complete"]:
            failed.append("incomplete_response")
        if not output.strip():
            failed.append("empty_output")
        character_count = len(output.strip())
        if probe.get("min_chars") is not None and character_count < probe["min_chars"]:
            failed.append(f"below_min_chars:{character_count}<{probe['min_chars']}")
        if probe.get("max_chars") is not None and character_count > probe["max_chars"]:
            failed.append(f"above_max_chars:{character_count}>{probe['max_chars']}")
        for literal in probe["must_preserve"]:
            if literal not in output:
                failed.append(f"missing_protected:{literal}")
        for literal in probe["must_include"]:
            if literal not in output:
                failed.append(f"missing_required:{literal}")
        for literal in probe["forbidden_literals"]:
            if literal in output:
                failed.append(f"forbidden_literal:{literal}")
        for pattern in probe["forbidden_regex"]:
            if re.search(pattern, output):
                failed.append(f"forbidden_pattern:{pattern}")
        if probe["output_json_required"]:
            try:
                structured = json.loads(output)
            except json.JSONDecodeError:
                failed.append("output_json_parse_failure")
            else:
                if not isinstance(structured, dict):
                    failed.append("output_json_not_object")
                else:
                    missing_fields = [field for field in probe["required_json_fields"] if field not in structured]
                    if missing_fields:
                        failed.append("output_json_missing_fields:" + ",".join(missing_fields))
        passed = not failed
        failures += int(not passed)
        results.append({
            "probe_id": probe["probe_id"],
            "category": probe["category"],
            "passed": passed,
            "failed_checks": failed,
            "response_sha256": hashlib.sha256(
                json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        })
    if not profile_verified:
        failures += 1
    return results, failures


def build_receipt(
    suite_path: Path, manifest_path: Path, responses_path: Path, evaluator: str,
    executed_at: str, profile_verified: bool,
) -> tuple[dict[str, Any], int]:
    suite = validate_suite(suite_path)
    manifest = validate_manifest(read_json(manifest_path), suite_path, suite)
    request_path = manifest_path.parent / manifest["request_bundle"]
    if Path(manifest["request_bundle"]).name != manifest["request_bundle"]:
        raise QualificationError("manifest request_bundle must be a local filename")
    if not request_path.is_file() or sha256_file(request_path) != manifest["request_bundle_sha256"]:
        raise QualificationError("request bundle is missing or does not match the manifest hash")
    expected_response = manifest_path.parent / manifest["normalized_responses"]
    if Path(manifest["normalized_responses"]).name != manifest["normalized_responses"]:
        raise QualificationError("manifest normalized_responses must be a local filename")
    if responses_path.resolve() != expected_response.resolve():
        raise QualificationError("responses path is not the manifest-bound normalized response file")
    responses = read_responses(responses_path, [probe["probe_id"] for probe in suite["probes"]])
    executed_at = iso_datetime(executed_at, "executed_at")
    if not evaluator.strip():
        raise QualificationError("evaluator is required")
    results, failures = score_responses(suite, responses, profile_verified)
    passed_count = sum(1 for result in results if result["passed"])
    status = "smoke_pass" if failures == 0 else "smoke_fail"
    receipt = {
        "schema_version": 1,
        "receipt_type": "soil-all-writing-model-qualification-smoke",
        "run_id": manifest["run_id"],
        "suite_id": suite["suite_id"],
        "suite_version": suite["suite_version"],
        "suite_level": "smoke",
        "provider": manifest["provider"],
        "endpoint_type": manifest["endpoint_type"],
        "model_id": manifest["model_id"],
        "model_revision": manifest["model_revision"],
        "region": manifest["region"],
        "adapter_id": manifest["adapter_id"],
        "evaluator": evaluator.strip(),
        "executed_at": executed_at,
        "profile_verified": profile_verified,
        "status": status,
        "release_scope": "smoke_only_not_full_qualification",
        "integrity": {
            "suite_sha256": sha256_file(suite_path),
            "manifest_sha256": sha256_file(manifest_path),
            "request_bundle_sha256": sha256_file(request_path),
            "responses_sha256": sha256_file(responses_path),
            "skill_bundle_sha256": manifest["skill_bundle_sha256"],
            "system_prompt_sha256": manifest["system_prompt_sha256"],
        },
        "summary": {
            "probe_count": len(results),
            "passed_probes": passed_count,
            "failed_probes": len(results) - passed_count,
            "profile_failure": not profile_verified,
        },
        "results": results,
        "limitations": [
            "This receipt covers only the frozen synthetic smoke suite.",
            "It does not constitute full model qualification or authorize confidential data.",
            "Any model, revision, adapter, system prompt, Skill bundle, or endpoint change invalidates reuse.",
        ],
    }
    return receipt, failures


def evaluate(args: argparse.Namespace) -> int:
    receipt, failures = build_receipt(
        args.suite, args.manifest, args.responses, args.evaluator, args.executed_at, args.profile_verified,
    )
    write_json_new(args.receipt, receipt)
    if failures:
        print(f"FAILED: smoke receipt written with {failures} failed gate(s)")
        return 1
    print(f"PASS: {receipt['summary']['passed_probes']} frozen smoke probes passed; full qualification remains not run")
    return 0


def compare_receipt(receipt: Any, rebuilt: dict[str, Any]) -> None:
    if not isinstance(receipt, dict):
        raise QualificationError("receipt must be an object")
    if receipt != rebuilt:
        raise QualificationError("receipt contents do not match the hash-bound artifacts and deterministic rescore")
    if receipt.get("status") not in {"smoke_pass", "smoke_fail"}:
        raise QualificationError("receipt has invalid status")
    if receipt.get("release_scope") != "smoke_only_not_full_qualification":
        raise QualificationError("receipt improperly claims scope beyond smoke testing")


def validate_receipt_command(args: argparse.Namespace) -> None:
    receipt = read_json(args.receipt)
    evaluator = receipt.get("evaluator", "") if isinstance(receipt, dict) else ""
    executed_at = receipt.get("executed_at", "") if isinstance(receipt, dict) else ""
    profile_verified = receipt.get("profile_verified", False) if isinstance(receipt, dict) else False
    if not isinstance(profile_verified, bool):
        raise QualificationError("receipt profile_verified must be boolean")
    rebuilt, _ = build_receipt(
        args.suite, args.manifest, args.responses, evaluator, executed_at, profile_verified,
    )
    compare_receipt(receipt, rebuilt)
    print(f"PASS: receipt is hash-bound and deterministically reproducible ({receipt['status']})")


def update_matrix(args: argparse.Namespace) -> None:
    receipt = read_json(args.receipt)
    evaluator = receipt.get("evaluator", "") if isinstance(receipt, dict) else ""
    executed_at = receipt.get("executed_at", "") if isinstance(receipt, dict) else ""
    profile_verified = receipt.get("profile_verified", False) if isinstance(receipt, dict) else False
    rebuilt, _ = build_receipt(
        args.suite, args.manifest, args.responses, evaluator, executed_at, profile_verified,
    )
    compare_receipt(receipt, rebuilt)
    try:
        with args.matrix.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        raise QualificationError(f"cannot read matrix: {exc}") from exc
    required_fields = {
        "provider", "endpoint_type", "model_id", "model_revision", "profile_verified",
        "smoke_suite", "full_suite", "confidentiality_approved", "qualified_scopes",
        "excluded_scopes", "evaluator", "evaluated_at", "evidence_uri", "notes",
    }
    if not required_fields.issubset(fields):
        raise QualificationError("matrix does not contain the required qualification columns")
    matching = [row for row in rows if row["provider"].strip() == receipt["provider"]]
    if len(matching) != 1:
        raise QualificationError("matrix must contain exactly one row for the receipt provider")
    row = matching[0]
    if row["full_suite"].strip() == "pass":
        raise QualificationError("smoke-only updater will not alter a row with an existing full-suite pass")
    row.update({
        "endpoint_type": receipt["endpoint_type"],
        "model_id": receipt["model_id"],
        "model_revision": receipt["model_revision"],
        "profile_verified": "true" if receipt["profile_verified"] else "false",
        "smoke_suite": "pass" if receipt["status"] == "smoke_pass" else "fail",
        "full_suite": "not_run",
        "qualified_scopes": "",
        "evaluator": receipt["evaluator"],
        "evaluated_at": receipt["executed_at"],
        "evidence_uri": str(args.receipt),
        "notes": "Frozen synthetic smoke suite only; full qualification and scope authorization remain not run.",
    })
    if args.output.exists() or args.output.resolve() == args.matrix.resolve():
        raise QualificationError("matrix output must be a new file")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"PASS: wrote project matrix copy; {receipt['provider']} remains full_suite=not_run")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    suite_parser = sub.add_parser("validate-suite", help="validate the sealed frozen smoke suite")
    suite_parser.add_argument("suite", type=Path)

    prepare_parser = sub.add_parser("prepare", help="create an answer-free endpoint run bundle")
    prepare_parser.add_argument("--suite", type=Path, required=True)
    prepare_parser.add_argument("--output-dir", type=Path, required=True)
    prepare_parser.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    prepare_parser.add_argument("--endpoint-type", required=True)
    prepare_parser.add_argument("--model-id", required=True)
    prepare_parser.add_argument("--model-revision", required=True)
    prepare_parser.add_argument("--region", default="")
    prepare_parser.add_argument("--adapter-id", required=True)
    prepare_parser.add_argument("--system-prompt-sha256", required=True)

    evaluate_parser = sub.add_parser("evaluate", help="score normalized responses and write a receipt")
    evaluate_parser.add_argument("--suite", type=Path, required=True)
    evaluate_parser.add_argument("--manifest", type=Path, required=True)
    evaluate_parser.add_argument("--responses", type=Path, required=True)
    evaluate_parser.add_argument("--receipt", type=Path, required=True)
    evaluate_parser.add_argument("--evaluator", required=True)
    evaluate_parser.add_argument("--executed-at", required=True)
    evaluate_parser.add_argument("--profile-verified", action="store_true")

    receipt_parser = sub.add_parser("validate-receipt", help="recompute and verify a qualification receipt")
    receipt_parser.add_argument("--suite", type=Path, required=True)
    receipt_parser.add_argument("--manifest", type=Path, required=True)
    receipt_parser.add_argument("--responses", type=Path, required=True)
    receipt_parser.add_argument("--receipt", type=Path, required=True)

    matrix_parser = sub.add_parser("update-matrix", help="write a smoke-only project matrix copy")
    matrix_parser.add_argument("--suite", type=Path, required=True)
    matrix_parser.add_argument("--manifest", type=Path, required=True)
    matrix_parser.add_argument("--responses", type=Path, required=True)
    matrix_parser.add_argument("--receipt", type=Path, required=True)
    matrix_parser.add_argument("--matrix", type=Path, required=True)
    matrix_parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "validate-suite":
            suite = validate_suite(args.suite)
            print(f"PASS: {len(suite['probes'])} frozen smoke probes are structurally valid")
            return 0
        if args.command == "prepare":
            prepare(args)
            return 0
        if args.command == "evaluate":
            return evaluate(args)
        if args.command == "validate-receipt":
            validate_receipt_command(args)
            return 0
        if args.command == "update-matrix":
            update_matrix(args)
            return 0
        raise QualificationError("unknown command")
    except QualificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

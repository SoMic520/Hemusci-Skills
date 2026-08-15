#!/usr/bin/env python3
"""Fail-closed validator for a complete format-only journal review bundle."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from add_format_comments import verify_comments
from audit_docx_fonts import audit as audit_fonts
from audit_docx_notes import audit_notes
from check_toolchain import inspect_toolchain
from compare_docx_content import GuardError, compare_documents
from inspect_docx import inspect as inspect_docx
from ooxml_safety import PackageSafetyError, read_docx_package, sha256_file
from scope_policy import validate_format_only_payload
from validate_findings import validate_findings_payload
from validate_journal_profile import validate_profile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

REQUIRED_MANIFEST_KEYS = {
    "schema_version",
    "scope",
    "source_document",
    "clean_document",
    "annotated_document",
    "audit_report",
    "change_ledger",
    "rule_manifest",
    "journal_profile",
    "findings",
    "format_plan",
    "format_application_receipt",
    "comment_application_receipt",
    "source_inspection",
    "note_audit",
    "toolchain_report",
    "clean_font_audit",
    "annotated_font_audit",
    "clean_integrity",
    "annotated_integrity",
    "clean_render_receipt",
    "annotated_render_receipt",
    "expect_format_comments",
    "approved_header_footer_parts",
}
OPTIONAL_MANIFEST_KEYS = {"platform_claims", "native_word_review_receipt"}
PATH_KEYS = REQUIRED_MANIFEST_KEYS - {
    "schema_version",
    "scope",
    "expect_format_comments",
    "approved_header_footer_parts",
}
LEDGER_COLUMNS = {
    "issue_id",
    "operation_id",
    "story",
    "note_id",
    "location",
    "category",
    "rule_id",
    "before_format",
    "after_format",
    "action",
    "comment_id",
    "target_text_sha256",
    "status",
}
RULE_COLUMNS = {
    "rule_id",
    "category",
    "requirement",
    "source_url",
    "source_title",
    "source_locator",
    "source_kind",
    "source_sha256",
    "source_snapshot",
    "accessed_at",
    "article_type",
    "verification_status",
    "automation",
}
REPORT_HEADINGS = {
    "## 目标与范围",
    "## 官方规则",
    "## 已修订格式问题",
    "## 仅批注或需作者处理",
    "## 未验证规则与冲突",
    "## 内容保真校验",
    "## 脚注与尾注校验",
    "## 字体与跨平台校验",
    "## 逐页视觉核验",
    "## 未开展的内容审查",
}


def _load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: cannot read JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label}: JSON root must be an object")
        return {}
    return value


def _csv_rows(path: Path) -> tuple[set[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return set(reader.fieldnames or []), list(reader)


def _comment_count(path: Path) -> int:
    parts, _, _ = read_docx_package(path)
    if "word/comments.xml" not in parts:
        return 0
    root = ET.fromstring(parts["word/comments.xml"])
    return len(root.findall(f"{{{W}}}comment"))


def _resolve_path(base: Path, value: Any, label: str, errors: list[str]) -> Path:
    raw = Path(str(value))
    if raw.is_absolute():
        errors.append(f"{label}: manifest paths must be relative for a portable bundle")
    path = (base / raw).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes the bundle directory")
    return path


def _validate_receipt_hash(
    receipt: dict[str, Any],
    label: str,
    expected: dict[str, tuple[Path, tuple[str, ...]]],
    errors: list[str],
) -> None:
    if receipt.get("status") != "PASS":
        errors.append(f"{label}: status must be PASS")
    for description, (path, keys) in expected.items():
        actual = sha256_file(path)
        value = next((receipt.get(key) for key in keys if receipt.get(key)), None)
        if value != actual:
            errors.append(f"{label}: {description} hash does not match {path.name}")


def _resolve_artifact(receipt_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (receipt_path.parent / path).resolve()


def _validate_render_receipt(
    receipt_path: Path,
    receipt: dict[str, Any],
    document: Path,
    bundle_base: Path,
    label: str,
    errors: list[str],
) -> None:
    if receipt.get("status") != "VISUAL_REVIEW_PASS":
        errors.append(f"{label}: visual review status must be VISUAL_REVIEW_PASS")
    review = receipt.get("visual_review")
    if not isinstance(review, dict) or review.get("status") != "PASS":
        errors.append(f"{label}: visual_review.status must be PASS")
    elif not review.get("reviewer") or not review.get("reviewed_at") or not review.get("notes"):
        errors.append(f"{label}: reviewer, reviewed_at, and notes are required")
    if receipt.get("docx_sha256") != sha256_file(document):
        errors.append(f"{label}: docx_sha256 does not match the delivered document")
    pages = receipt.get("pages")
    if not isinstance(pages, list) or not pages:
        errors.append(f"{label}: page records are missing")
        return
    if receipt.get("page_count") != len(pages):
        errors.append(f"{label}: page_count does not match page records")
    expected_numbers = list(range(1, len(pages) + 1))
    if [row.get("page") for row in pages] != expected_numbers:
        errors.append(f"{label}: page numbers are not contiguous")
    if isinstance(review, dict) and review.get("pages_reviewed") != expected_numbers:
        errors.append(f"{label}: visual review does not cover every page")
    for row in pages:
        page = _resolve_artifact(receipt_path, str(row.get("path", "")))
        try:
            page.relative_to(bundle_base.resolve())
        except ValueError:
            errors.append(f"{label}: rendered page escapes the bundle: {page}")
            continue
        if not page.exists() or sha256_file(page) != row.get("sha256"):
            errors.append(f"{label}: rendered page is missing or changed: {page.name}")
        elif page.stat().st_size < 100 or not page.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            errors.append(f"{label}: rendered page is not a valid non-empty PNG: {page.name}")


def validate_bundle(manifest_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        return {"status": "FAIL", "errors": ["Delivery manifest must be an object"], "warnings": []}
    unknown = sorted(set(manifest) - REQUIRED_MANIFEST_KEYS - OPTIONAL_MANIFEST_KEYS)
    if unknown:
        errors.append(f"Manifest has unsupported keys: {', '.join(unknown)}")
    missing = sorted(REQUIRED_MANIFEST_KEYS - set(manifest))
    if missing:
        errors.append(f"Manifest missing keys: {', '.join(missing)}")
    if manifest.get("schema_version") != "2.0" or manifest.get("scope") != "FORMAT_ONLY":
        errors.append("Manifest requires schema_version 2.0 and scope FORMAT_ONLY")
    scope_errors = validate_format_only_payload(manifest)
    errors.extend(f"Manifest scope: {message}" for message in scope_errors)
    approved = manifest.get("approved_header_footer_parts")
    if not isinstance(approved, list) or any(
        not isinstance(value, str) or not re_full_header_footer(value) for value in approved
    ):
        errors.append("approved_header_footer_parts must contain exact word/headerN.xml or word/footerN.xml paths")
        approved = []

    base = manifest_path.parent.resolve()
    paths = {key: _resolve_path(base, manifest.get(key, ""), key, errors) for key in PATH_KEYS if key in manifest}
    if "native_word_review_receipt" in manifest:
        paths["native_word_review_receipt"] = _resolve_path(
            base, manifest["native_word_review_receipt"], "native_word_review_receipt", errors
        )
    for key, path in paths.items():
        if not path.exists():
            errors.append(f"{key} not found: {path}")
    if errors:
        return {"status": "FAIL", "errors": errors, "warnings": warnings, "files": {}}

    source = paths["source_document"]
    clean = paths["clean_document"]
    annotated = paths["annotated_document"]
    if len({source.resolve(), clean.resolve(), annotated.resolve()}) != 3:
        errors.append("Source, clean, and annotated documents must be three distinct files")

    profile = _load_json(paths["journal_profile"], "journal_profile", errors)
    profile_result = validate_profile(profile)
    if profile_result.get("status") != "PASS":
        errors.extend(f"Journal profile: {message}" for message in profile_result.get("errors", []))
    warnings.extend(f"Journal profile: {message}" for message in profile_result.get("warnings", []))
    profile_sha = sha256_file(paths["journal_profile"])

    findings = _load_json(paths["findings"], "findings", errors)
    findings_result = validate_findings_payload(findings, profile=profile)
    if findings_result.get("status") != "PASS":
        errors.extend(f"Findings: {message}" for message in findings_result.get("errors", []))
    if findings.get("profile_sha256") != profile_sha:
        errors.append("Findings profile_sha256 does not match journal_profile")
    if findings.get("source_document_sha256") != sha256_file(clean):
        errors.append("Findings must be fingerprinted against clean_document")

    plan = _load_json(paths["format_plan"], "format_plan", errors)
    if plan.get("schema_version") != "2.0" or plan.get("scope") != "FORMAT_ONLY":
        errors.append("Format plan requires schema_version 2.0 and scope FORMAT_ONLY")
    if plan.get("source_document_sha256") != sha256_file(source):
        errors.append("Format plan source_document_sha256 does not match source_document")
    if plan.get("journal_profile_sha256") != profile_sha:
        errors.append("Format plan journal_profile_sha256 does not match journal_profile")
    rules_by_id = {str(rule.get("rule_id")): rule for rule in profile.get("rules", []) if isinstance(rule, dict)}
    for rule_id, rule in rules_by_id.items():
        if rule.get("verification_status") not in {"VERIFIED", "INFERRED"}:
            continue
        snapshot = _resolve_path(base, rule.get("source_snapshot", ""), f"rule {rule_id} source_snapshot", errors)
        if not snapshot.exists():
            errors.append(f"rule {rule_id} source snapshot not found: {snapshot}")
        elif sha256_file(snapshot) != rule.get("source_sha256"):
            errors.append(f"rule {rule_id} source snapshot hash mismatch")
    plan_operations = plan.get("operations") if isinstance(plan.get("operations"), list) else []
    for index, operation in enumerate(plan_operations):
        rule = rules_by_id.get(str(operation.get("rule_id"))) if isinstance(operation, dict) else None
        if not rule or rule.get("verification_status") != "VERIFIED" or rule.get("automation") != "AUTO_FIX":
            errors.append(f"format_plan.operations[{index}] lacks a VERIFIED/AUTO_FIX profile rule")

    integrity = {}
    try:
        clean_guard = compare_documents(
            source,
            clean,
            approved_header_footer_parts=set(approved),
        )
        annotated_guard = compare_documents(clean, annotated, allow_comment_additions=True)
        integrity = {"clean": clean_guard, "annotated": annotated_guard}
        if clean_guard["status"] != "PASS":
            errors.append(f"Clean document failed content integrity: {clean_guard['failures']}")
        if annotated_guard["status"] != "PASS":
            errors.append(f"Annotated document failed content integrity: {annotated_guard['failures']}")
    except GuardError as exc:
        errors.append(f"Content guard error: {exc}")

    verification = verify_comments(annotated)
    if not verification.get("valid"):
        errors.append(f"Annotated comment structure is invalid: {verification.get('errors')}")
    source_comments = _comment_count(source)
    clean_comments = _comment_count(clean)
    annotated_comments = _comment_count(annotated)
    if clean_comments != source_comments:
        errors.append("Clean document must preserve the source comment count exactly")
    if manifest.get("expect_format_comments") is not True:
        errors.append("v2 format-and-comment bundles require expect_format_comments=true")
    elif annotated_comments <= clean_comments:
        errors.append("Annotated document has no new Word comments")

    format_receipt = _load_json(paths["format_application_receipt"], "format_application_receipt", errors)
    _validate_receipt_hash(
        format_receipt,
        "format_application_receipt",
        {
            "source": (source, ("source_sha256",)),
            "output": (clean, ("output_sha256",)),
            "plan": (paths["format_plan"], ("plan_sha256",)),
            "profile": (paths["journal_profile"], ("profile_sha256",)),
        },
        errors,
    )
    comment_receipt = _load_json(paths["comment_application_receipt"], "comment_application_receipt", errors)
    _validate_receipt_hash(
        comment_receipt,
        "comment_application_receipt",
        {
            "source": (clean, ("source_sha256",)),
            "output": (annotated, ("output_sha256",)),
            "findings": (paths["findings"], ("findings_sha256",)),
            "profile": (paths["journal_profile"], ("profile_sha256",)),
        },
        errors,
    )
    added_receipt_ids = {str(row.get("comment_id")) for row in comment_receipt.get("added", []) if isinstance(row, dict)}

    clean_integrity_receipt = _load_json(paths["clean_integrity"], "clean_integrity", errors)
    annotated_integrity_receipt = _load_json(paths["annotated_integrity"], "annotated_integrity", errors)
    for label, receipt, left, right in (
        ("clean_integrity", clean_integrity_receipt, source, clean),
        ("annotated_integrity", annotated_integrity_receipt, clean, annotated),
    ):
        if receipt.get("status") != "PASS":
            errors.append(f"{label}: status must be PASS")
        if receipt.get("source_file_sha256") != sha256_file(left):
            errors.append(f"{label}: source hash mismatch")
        if receipt.get("revised_file_sha256") != sha256_file(right):
            errors.append(f"{label}: revised hash mismatch")

    ledger_columns, ledger_rows = _csv_rows(paths["change_ledger"])
    missing_ledger = sorted(LEDGER_COLUMNS - ledger_columns)
    if missing_ledger:
        errors.append(f"Change ledger missing columns: {', '.join(missing_ledger)}")
    ledger_scope_errors = validate_format_only_payload(ledger_rows)
    errors.extend(f"Change ledger scope: {message}" for message in ledger_scope_errors)
    ledger_issue_ids = {row.get("issue_id", "") for row in ledger_rows if row.get("issue_id")}
    finding_issue_ids = {str(row.get("issue_id")) for row in findings.get("findings", []) if isinstance(row, dict)}
    if ledger_issue_ids != finding_issue_ids:
        errors.append("Change ledger issue_id set does not exactly match findings")
    ledger_comment_ids = {row["comment_id"] for row in ledger_rows if row.get("comment_id")}
    if ledger_comment_ids != added_receipt_ids:
        errors.append("Change ledger comment_id set does not match the comment application receipt")
    plan_operation_ids = {str(row.get("operation_id")) for row in plan_operations if isinstance(row, dict)}
    receipt_operation_ids = {
        str(row.get("operation_id"))
        for row in format_receipt.get("operations_applied", [])
        if isinstance(row, dict)
    }
    if receipt_operation_ids != plan_operation_ids:
        errors.append("Format application receipt operation IDs do not match the plan")
    ledger_operation_ids = {row["operation_id"] for row in ledger_rows if row.get("operation_id")}
    if ledger_operation_ids != plan_operation_ids:
        errors.append("Change ledger operation_id set does not match the format plan")
    receipt_issue_ids = {
        str(row.get("issue_id"))
        for row in comment_receipt.get("added", [])
        if isinstance(row, dict)
    }
    if receipt_issue_ids != finding_issue_ids:
        errors.append("Comment application receipt issue IDs do not match findings")
    guard_added_ids = set(integrity.get("annotated", {}).get("comments", {}).get("added_ids", []))
    if added_receipt_ids != guard_added_ids:
        errors.append("Comment application receipt IDs do not match newly added DOCX comments")

    rule_columns, rule_rows = _csv_rows(paths["rule_manifest"])
    missing_rules = sorted(RULE_COLUMNS - rule_columns)
    if missing_rules:
        errors.append(f"Rule manifest missing columns: {', '.join(missing_rules)}")
    csv_rules = {row.get("rule_id", ""): row for row in rule_rows if row.get("rule_id")}
    if set(csv_rules) != set(rules_by_id):
        errors.append("Rule manifest rule_id set does not exactly match journal profile")
    for rule_id in set(csv_rules) & set(rules_by_id):
        for key in RULE_COLUMNS - {"rule_id"}:
            if str(csv_rules[rule_id].get(key, "")) != str(rules_by_id[rule_id].get(key, "")):
                errors.append(f"Rule manifest {rule_id}.{key} differs from journal profile")

    source_inspection = _load_json(paths["source_inspection"], "source_inspection", errors)
    note_audit = _load_json(paths["note_audit"], "note_audit", errors)
    toolchain = _load_json(paths["toolchain_report"], "toolchain_report", errors)
    clean_fonts = _load_json(paths["clean_font_audit"], "clean_font_audit", errors)
    annotated_fonts = _load_json(paths["annotated_font_audit"], "annotated_font_audit", errors)
    if source_inspection.get("status") != "PASS":
        errors.append("source_inspection status must be PASS")
    if note_audit.get("status") != "PASS":
        errors.append("note_audit status must be PASS")
    if toolchain.get("status") != "PASS" or not toolchain.get("capabilities", {}).get("full_page_visual_qa"):
        errors.append("toolchain_report must confirm full page visual QA")
    recomputed_inspection = inspect_docx(source)
    for key in ("status", "file_sha256", "paragraphs", "tables", "comments", "revisions", "sections"):
        if source_inspection.get(key) != recomputed_inspection.get(key):
            errors.append(f"source_inspection.{key} does not match a fresh inspection")
    recomputed_notes = audit_notes(source)
    if note_audit.get("status") != recomputed_notes.get("status") or note_audit.get("stories") != recomputed_notes.get("stories"):
        errors.append("note_audit does not match a fresh note audit")
    recomputed_toolchain = inspect_toolchain()
    for key in ("status", "capabilities"):
        if toolchain.get(key) != recomputed_toolchain.get(key):
            errors.append(f"toolchain_report.{key} does not match the current toolchain")
    if toolchain.get("platform", {}).get("system") != recomputed_toolchain.get("platform", {}).get("system"):
        errors.append("toolchain_report platform does not match the current platform")
    font_mapping = Path(__file__).resolve().parent.parent / "assets/font-compatibility.json"
    for label, font_audit, document in (
        ("clean_font_audit", clean_fonts, clean),
        ("annotated_font_audit", annotated_fonts, annotated),
    ):
        if font_audit.get("status") not in {"PASS", "WARN"}:
            errors.append(f"{label} status must be PASS or documented WARN")
        if font_audit.get("document") != str(document.resolve()):
            warnings.append(f"{label} contains a non-portable absolute document path")
        if font_audit.get("status") == "WARN":
            warnings.append(f"{label}: exact fonts are missing; visual QA used documented fallbacks")
        recomputed_font = audit_fonts(document, font_mapping, [])
        for key in ("status", "theme_resolution", "fonts", "missing_exact_count", "missing_without_qa_fallback_count"):
            if font_audit.get(key) != recomputed_font.get(key):
                errors.append(f"{label}.{key} does not match a fresh font audit")

    clean_render = _load_json(paths["clean_render_receipt"], "clean_render_receipt", errors)
    annotated_render = _load_json(paths["annotated_render_receipt"], "annotated_render_receipt", errors)
    _validate_render_receipt(paths["clean_render_receipt"], clean_render, clean, base, "clean_render_receipt", errors)
    _validate_render_receipt(
        paths["annotated_render_receipt"], annotated_render, annotated, base, "annotated_render_receipt", errors
    )

    note_comments = any(
        isinstance(row, dict) and row.get("story") in {"footnotes", "endnotes"}
        for row in comment_receipt.get("added", [])
    )
    if note_comments:
        native_path = paths.get("native_word_review_receipt")
        if not native_path:
            errors.append("Footnote/endnote comments require native_word_review_receipt")
        else:
            native = _load_json(native_path, "native_word_review_receipt", errors)
            if native.get("status") != "PASS" or native.get("document_sha256") != sha256_file(annotated):
                errors.append("native_word_review_receipt must PASS for the annotated document")

    platform_claims = manifest.get("platform_claims", [])
    if platform_claims:
        if not isinstance(platform_claims, list):
            errors.append("platform_claims must be a list")
        else:
            current_system = toolchain.get("platform", {}).get("system")
            unsupported = [claim for claim in platform_claims if claim != current_system]
            if unsupported:
                errors.append(
                    "Bundle cannot claim untested platforms from one toolchain receipt: " + ", ".join(map(str, unsupported))
                )

    report_text = paths["audit_report"].read_text(encoding="utf-8")
    if len(report_text.strip()) < 300:
        errors.append("Audit report is too short to be a complete review record")
    missing_headings = sorted(heading for heading in REPORT_HEADINGS if heading not in report_text)
    if missing_headings:
        errors.append("Audit report missing headings: " + ", ".join(missing_headings))
    if "未评价论文质量、科学内容、方法、统计、论证、语言表达或引文真实性" not in report_text:
        errors.append("Audit report must reproduce the exact format-only scope exclusion")

    file_hashes = {key: sha256_file(path) for key, path in paths.items() if path.is_file()}
    return {
        "status": "FAIL" if errors else "PASS",
        "schema_version": "2.0",
        "scope": "FORMAT_ONLY",
        "errors": errors,
        "warnings": warnings,
        "files": {key: {"path": str(path), "sha256": file_hashes[key]} for key, path in paths.items() if key in file_hashes},
        "comments": {"source": source_comments, "clean": clean_comments, "annotated": annotated_comments},
        "integrity": integrity,
        "comment_verification": verification,
        "journal_profile_validation": profile_result,
        "findings_validation": findings_result,
        "rows": {"change_ledger": len(ledger_rows), "rule_manifest": len(rule_rows)},
    }


def re_full_header_footer(value: str) -> bool:
    import re

    return bool(re.fullmatch(r"word/(?:header|footer)\d+\.xml", value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        result = validate_bundle(args.manifest.resolve())
    except (OSError, ValueError, KeyError, json.JSONDecodeError, PackageSafetyError, ET.ParseError) as exc:
        result = {"status": "ERROR", "errors": [str(exc)], "warnings": []}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())

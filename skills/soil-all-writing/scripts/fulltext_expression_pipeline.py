#!/usr/bin/env python3
"""Prepare, seal, validate, report, and export hash-bound full-text expression packets."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


MODULES = [f"D{index}" for index in range(1, 14)]
STATUSES = {"draft_metadata", "prepared", "qualified"}
ENTRY_TYPES = {"abstracted", "verbatim", "negative_example"}
REVIEW_ROLES = {"soil_domain", "scientific_language", "copyright_or_rights", "genre_specialist"}
MODEL_NAME_RE = re.compile(
    r"(?:^|\b)(?:ai|llm|chatgpt|gpt|claude|gemini|deepseek|qwen|mistral|cohere|ollama)(?:\b|$)",
    re.IGNORECASE,
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
CSV_FIELDS = [
    "expression_id", "entry_type", "language", "discipline", "genre", "section",
    "rhetorical_move", "exact_fragment", "abstracted_pattern", "source_title", "authors",
    "year", "doi", "url", "locator", "license", "access_date", "verbatim_word_count",
    "verified", "context_limit", "reuse_status", "notes", "module_id", "source_type",
    "fulltext_status", "qualification_status", "reviewer_state", "release_scope",
    "module_fit_reason", "source_sha256", "extracted_text_sha256", "review_basis_sha256",
]


class PipelineError(ValueError):
    """Raised when a packet or operation violates the evidence contract."""


class VisibleHTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.hidden_depth += 1
        if tag.lower() in {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "li", "tr", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.hidden_depth:
            self.hidden_depth -= 1
        if tag.lower() in {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)

    def text(self) -> str:
        return clean_extracted_text("".join(self.parts))


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PipelineError(f"JSON root must be an object: {path}")
    return payload


def write_json_new(path: Path, payload: Any) -> None:
    if path.exists():
        raise PipelineError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise PipelineError(f"cannot hash {path}: {exc}") from exc


def canonical_sha256(payload: Any) -> str:
    return sha256_bytes(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def clean_extracted_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [re.sub(r"[\t \u00a0]+", " ", line).strip() for line in text.split("\n")]
    output: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line
        if blank and previous_blank:
            continue
        output.append(line)
        previous_blank = blank
    return "\n".join(output).strip() + "\n"


def extract_text(source: Path) -> tuple[str, str]:
    suffix = source.suffix.lower()
    data = source.read_bytes()
    if suffix in {".txt", ".md", ".csv", ".tsv"}:
        return clean_extracted_text(data.decode("utf-8", errors="strict")), "utf8-visible-text-v1"
    if suffix in {".html", ".htm", ".xml", ".xhtml"}:
        parser = VisibleHTMLText()
        parser.feed(data.decode("utf-8", errors="replace"))
        return parser.text(), "stdlib-visible-html-v1"
    if suffix == ".pdf":
        executable = shutil.which("pdftotext")
        if not executable:
            raise PipelineError("PDF preparation requires local pdftotext")
        result = subprocess.run(
            [executable, "-layout", "-", "-"], input=data, capture_output=True, check=False
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise PipelineError(f"pdftotext failed: {detail or 'unknown error'}")
        text = clean_extracted_text(result.stdout.decode("utf-8", errors="replace"))
        if len(text.strip()) < 50:
            raise PipelineError("PDF produced too little searchable text; OCR output is not accepted as verified full text")
        return text, "pdftotext-layout-v1"
    raise PipelineError(f"unsupported full-text format: {suffix or '[no suffix]'}")


def normalized_locator_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fragment_length(text: str) -> int:
    han = re.findall(r"[\u3400-\u9fff]", text)
    if han:
        return len(han)
    return len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))


def require_mapping(payload: dict[str, Any], field: str, errors: list[str]) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    return value


def require_string(value: Any, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} is required")
        return ""
    return value.strip()


def review_basis_payload(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "packet_id": packet.get("packet_id"),
        "source": packet.get("source"),
        "classification": packet.get("classification"),
        "locator": packet.get("locator"),
        "extraction": packet.get("extraction"),
        "expression": packet.get("expression"),
    }


def validate_packet(packet: dict[str, Any], packet_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    if packet.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    packet_id = require_string(packet.get("packet_id"), "packet_id", errors)
    if packet_id and not re.fullmatch(r"FTEX-[A-Za-z0-9._-]+", packet_id):
        errors.append("packet_id must start with FTEX-")
    status = packet.get("status")
    if status not in STATUSES:
        errors.append("status must be draft_metadata, prepared, or qualified")

    source = require_mapping(packet, "source", errors)
    classification = require_mapping(packet, "classification", errors)
    locator = require_mapping(packet, "locator", errors)
    extraction = require_mapping(packet, "extraction", errors)
    expression = require_mapping(packet, "expression", errors)
    review = require_mapping(packet, "review", errors)
    qualification = require_mapping(packet, "qualification", errors)

    module_id = classification.get("module_id")
    if module_id not in MODULES:
        errors.append("classification.module_id must be D1 through D13")
    if expression.get("entry_type") not in ENTRY_TYPES:
        errors.append("expression.entry_type is invalid")
    if not isinstance(source.get("processing_authorized"), bool):
        errors.append("source.processing_authorized must be boolean")

    if status == "draft_metadata":
        return errors

    for field in ("source_id", "local_path", "source_title", "authors", "source_type", "license", "rights_basis"):
        require_string(source.get(field), f"source.{field}", errors)
    for field in ("discipline", "language", "genre", "section", "study_design", "rhetorical_move", "module_fit_reason"):
        require_string(classification.get(field), f"classification.{field}", errors)
    if source.get("processing_authorized") is not True:
        errors.append("prepared or qualified packets require source.processing_authorized=true")
    year = source.get("year")
    if not isinstance(year, int) or not 1800 <= year <= date.today().year:
        errors.append("source.year must be a plausible integer not later than the current year")
    doi = str(source.get("doi") or "").strip()
    url = str(source.get("canonical_url") or "").strip()
    if not doi and not url:
        errors.append("source.doi or source.canonical_url is required")
    if doi and not DOI_RE.fullmatch(doi):
        errors.append("source.doi is invalid")
    if url and not re.match(r"^https?://", url):
        errors.append("source.canonical_url must use http or https")
    try:
        accessed = date.fromisoformat(str(source.get("access_date") or ""))
        if accessed > date.today():
            errors.append("source.access_date cannot be in the future")
    except ValueError:
        errors.append("source.access_date must be YYYY-MM-DD")

    for field in ("source_sha256",):
        if not SHA256_RE.fullmatch(str(source.get(field) or "")):
            errors.append(f"source.{field} must be SHA-256")
    for field in ("extractor", "extracted_text_path", "prepared_at"):
        require_string(extraction.get(field), f"extraction.{field}", errors)
    if not SHA256_RE.fullmatch(str(extraction.get("extracted_text_sha256") or "")):
        errors.append("extraction.extracted_text_sha256 must be SHA-256")
    if not isinstance(extraction.get("extracted_character_count"), int) or extraction.get("extracted_character_count", 0) < 50:
        errors.append("extraction.extracted_character_count must be at least 50")

    extracted_text_value: str | None = None
    if packet_path is not None:
        base = packet_path.parent
        source_path = Path(str(source.get("local_path") or ""))
        text_path = Path(str(extraction.get("extracted_text_path") or ""))
        if source_path.name != str(source_path) or text_path.name != str(text_path):
            errors.append("prepared source and extracted-text paths must be local filenames")
        else:
            resolved_source = base / source_path
            resolved_text = base / text_path
            if not resolved_source.is_file():
                errors.append("prepared source snapshot is missing")
            elif SHA256_RE.fullmatch(str(source.get("source_sha256") or "")) and sha256_file(resolved_source) != source["source_sha256"]:
                errors.append("prepared source snapshot hash mismatch")
            if not resolved_text.is_file():
                errors.append("extracted full text is missing")
            elif SHA256_RE.fullmatch(str(extraction.get("extracted_text_sha256") or "")) and sha256_file(resolved_text) != extraction["extracted_text_sha256"]:
                errors.append("extracted full-text hash mismatch")
            elif resolved_text.is_file():
                extracted_text_value = resolved_text.read_text(encoding="utf-8")
                if len(extracted_text_value) != extraction.get("extracted_character_count"):
                    errors.append("extracted full-text character count mismatch")

    anchor = str(locator.get("anchor_text") or "")
    anchor_sha = locator.get("anchor_sha256")
    if anchor and anchor_sha != sha256_bytes(normalized_locator_text(anchor).encode("utf-8")):
        errors.append("locator.anchor_sha256 does not match anchor_text")
    if (
        anchor and extracted_text_value is not None
        and normalized_locator_text(anchor) not in normalized_locator_text(extracted_text_value)
    ):
        errors.append("locator.anchor_text is absent from the hash-verified extracted full text")
    if not isinstance(locator.get("verified_in_extracted_text"), bool):
        errors.append("locator.verified_in_extracted_text must be boolean")

    if status != "qualified":
        return errors

    for field in ("value", "anchor_text"):
        require_string(locator.get(field), f"locator.{field}", errors)
    if locator.get("verified_in_extracted_text") is not True:
        errors.append("qualified packet requires a verified locator anchor")
    if qualification.get("fulltext_status") != "fulltext_verified":
        errors.append("qualified packet requires fulltext_status=fulltext_verified")
    if qualification.get("qualification_status") != "expression_qualified":
        errors.append("qualified packet requires qualification_status=expression_qualified")
    if qualification.get("reviewer_state") != "two_independent_human_reviews_complete":
        errors.append("qualified packet requires two independent human reviews")
    if qualification.get("release_scope") != "production_task_local_expression_corpus":
        errors.append("qualified packet has invalid release_scope")

    entry_type = expression.get("entry_type")
    exact = str(expression.get("exact_fragment") or "").strip()
    pattern = str(expression.get("abstracted_pattern") or "").strip()
    declared_count = expression.get("verbatim_word_count")
    if entry_type == "abstracted":
        if exact or declared_count != 0:
            errors.append("abstracted expression must contain no exact fragment and have verbatim_word_count=0")
        if len(pattern) < 30 or "[" not in pattern or "]" not in pattern:
            errors.append("abstracted expression requires a substantive parameterized pattern")
    elif entry_type == "verbatim":
        actual = fragment_length(exact)
        if not exact or declared_count != actual:
            errors.append("verbatim fragment count is missing or incorrect")
        limit = 20 if re.search(r"[\u3400-\u9fff]", exact) else 12
        if actual > limit:
            errors.append(f"verbatim fragment exceeds the task-local limit {limit}")
        if expression.get("reuse_status") not in {"quote_with_attribution", "short_quote_analysis_only"}:
            errors.append("verbatim expression requires an attribution/analysis-only reuse status")
    if not str(expression.get("context_limit") or "").strip():
        errors.append("expression.context_limit is required")
    if expression.get("reuse_status") == "candidate_not_released":
        errors.append("qualified expression cannot retain candidate_not_released")
    removed = expression.get("source_specific_elements_removed")
    if not isinstance(removed, list) or not removed or any(not isinstance(item, str) or not item.strip() for item in removed):
        errors.append("qualified expression requires a non-empty source_specific_elements_removed list")

    required_checks = (
        "title_authors_identifier_checked", "fulltext_and_locator_checked",
        "license_and_rights_checked", "scientific_context_checked",
        "source_specific_claims_removed", "similarity_review_complete",
    )
    for field in required_checks:
        if review.get(field) is not True:
            errors.append(f"review.{field} must be true")
    basis = review.get("review_basis_sha256")
    expected_basis = canonical_sha256(review_basis_payload(packet))
    if basis != expected_basis:
        errors.append("review.review_basis_sha256 does not match the current source, locator, extraction, and expression")
    reviewers = review.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) < 2:
        errors.append("qualified packet requires at least two reviewers")
        reviewers = []
    reviewer_ids: set[str] = set()
    reviewer_names: set[str] = set()
    covered_roles: set[str] = set()
    for index, reviewer in enumerate(reviewers, 1):
        prefix = f"review.reviewers[{index}]"
        if not isinstance(reviewer, dict):
            errors.append(f"{prefix} must be an object")
            continue
        reviewer_id = require_string(reviewer.get("reviewer_id"), f"{prefix}.reviewer_id", errors)
        name = require_string(reviewer.get("name"), f"{prefix}.name", errors)
        require_string(reviewer.get("affiliation"), f"{prefix}.affiliation", errors)
        if reviewer_id in reviewer_ids:
            errors.append(f"{prefix}.reviewer_id is duplicated")
        reviewer_ids.add(reviewer_id)
        if name and MODEL_NAME_RE.search(name):
            errors.append(f"{prefix}.name must identify a human reviewer, not a model")
        normalized_name = re.sub(r"\s+", "", name).casefold()
        if normalized_name and normalized_name in reviewer_names:
            errors.append(f"{prefix}.name is duplicated; reviews are not independent")
        reviewer_names.add(normalized_name)
        roles = reviewer.get("roles")
        if not isinstance(roles, list) or not roles or not set(roles).issubset(REVIEW_ROLES):
            errors.append(f"{prefix}.roles is invalid")
        else:
            covered_roles.update(roles)
        if reviewer.get("decision") != "approve":
            errors.append(f"{prefix}.decision must be approve")
        if reviewer.get("review_basis_sha256") != basis:
            errors.append(f"{prefix}.review_basis_sha256 does not match")
        require_string(reviewer.get("comment"), f"{prefix}.comment", errors)
        try:
            reviewed_at = datetime.fromisoformat(str(reviewer.get("reviewed_at") or "").replace("Z", "+00:00"))
            if reviewed_at.tzinfo is None:
                errors.append(f"{prefix}.reviewed_at requires a timezone")
        except ValueError:
            errors.append(f"{prefix}.reviewed_at must be ISO 8601")
    if not {"soil_domain", "scientific_language"}.issubset(covered_roles):
        errors.append("reviewer roles must cover soil_domain and scientific_language")
    return errors


def prepare_packet(args: argparse.Namespace) -> None:
    packet = read_json(args.packet)
    if packet.get("status") != "draft_metadata":
        raise PipelineError("prepare requires status=draft_metadata")
    errors = validate_packet(packet)
    if errors:
        raise PipelineError("; ".join(errors))
    source = packet.get("source", {})
    if source.get("processing_authorized") is not True:
        raise PipelineError("source.processing_authorized must be true before extracting full text")
    source_path_value = Path(str(source.get("local_path") or "")).expanduser()
    source_path = (
        source_path_value.resolve()
        if source_path_value.is_absolute()
        else (args.packet.parent / source_path_value).resolve()
    )
    if not source_path.is_file():
        raise PipelineError(f"authorized local source does not exist: {source_path}")
    for field in ("source_title", "authors", "source_type", "license", "rights_basis"):
        if not str(source.get(field) or "").strip():
            raise PipelineError(f"source.{field} is required before preparation")
    text, extractor = extract_text(source_path)
    if len(text) < 50:
        raise PipelineError("extracted text is too short for full-text review")
    anchor = str(packet.get("locator", {}).get("anchor_text") or "").strip()
    anchor_found = bool(anchor) and normalized_locator_text(anchor) in normalized_locator_text(text)
    if anchor and not anchor_found:
        raise PipelineError("locator.anchor_text was not found in the extracted full text")
    if args.output_dir.exists():
        raise PipelineError(f"refusing to overwrite existing output directory: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    suffix = source_path.suffix.lower() or ".bin"
    snapshot = args.output_dir / f"source-snapshot{suffix}"
    snapshot.write_bytes(source_path.read_bytes())
    extracted = args.output_dir / "extracted-fulltext.txt"
    extracted.write_text(text, encoding="utf-8")
    packet["status"] = "prepared"
    packet["source"]["local_path"] = snapshot.name
    packet["source"]["source_sha256"] = sha256_file(snapshot)
    packet["locator"]["anchor_sha256"] = (
        sha256_bytes(normalized_locator_text(anchor).encode("utf-8")) if anchor else None
    )
    packet["locator"]["verified_in_extracted_text"] = anchor_found
    packet["extraction"] = {
        "extractor": extractor,
        "extracted_text_path": extracted.name,
        "extracted_text_sha256": sha256_file(extracted),
        "extracted_character_count": len(text),
        "prepared_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    packet["qualification"] = {
        "fulltext_status": "fulltext_prepared_hash_bound_human_locator_review_pending",
        "qualification_status": "candidate",
        "reviewer_state": "not_reviewed",
        "release_scope": "not_released",
    }
    packet["review"]["review_basis_sha256"] = None
    packet_path = args.output_dir / "expression-packet.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = validate_packet(packet, packet_path)
    if errors:
        raise PipelineError("prepared packet failed validation: " + "; ".join(errors))
    print(json.dumps({
        "status": "PASS", "packet": str(packet_path), "source_sha256": packet["source"]["source_sha256"],
        "extracted_text_sha256": packet["extraction"]["extracted_text_sha256"],
        "anchor_found": anchor_found,
        "release_scope": "prepared_candidate_not_expression_qualified",
    }, ensure_ascii=False))


def seal_review(args: argparse.Namespace) -> None:
    packet = read_json(args.packet)
    if packet.get("status") != "prepared":
        raise PipelineError("seal-review requires status=prepared")
    errors = validate_packet(packet, args.packet)
    if errors:
        raise PipelineError("; ".join(errors))
    expression = packet.get("expression", {})
    entry_type = expression.get("entry_type")
    if entry_type == "abstracted":
        pattern = str(expression.get("abstracted_pattern") or "").strip()
        if len(pattern) < 30 or "[" not in pattern or "]" not in pattern:
            raise PipelineError("fill a substantive parameterized abstracted_pattern before sealing")
    elif entry_type == "verbatim" and not str(expression.get("exact_fragment") or "").strip():
        raise PipelineError("fill exact_fragment before sealing a verbatim candidate")
    packet["review"]["review_basis_sha256"] = canonical_sha256(review_basis_payload(packet))
    write_json_new(args.output, packet)
    print(json.dumps({
        "status": "PASS", "sealed_packet": str(args.output),
        "review_basis_sha256": packet["review"]["review_basis_sha256"],
        "release_scope": "sealed_for_human_review_not_qualified",
    }, ensure_ascii=False))


def packet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.is_dir():
        raise PipelineError(f"packet root does not exist: {root}")
    return sorted(path for path in root.rglob("*.json") if path.name == "expression-packet.json" or "packet" in path.stem)


def source_identity(packet: dict[str, Any]) -> str:
    source = packet["source"]
    return (
        str(source.get("doi") or "").strip().lower()
        or str(source.get("canonical_url") or "").strip().lower()
        or str(source.get("source_sha256") or "")
    )


def load_valid_packets(root: Path) -> tuple[list[tuple[Path, dict[str, Any]]], list[str]]:
    packets: list[tuple[Path, dict[str, Any]]] = []
    errors: list[str] = []
    for path in packet_files(root):
        try:
            packet = read_json(path)
        except PipelineError as exc:
            errors.append(str(exc))
            continue
        if packet.get("schema_version") != 1 or not str(packet.get("packet_id") or "").startswith("FTEX-"):
            continue
        packet_errors = validate_packet(packet, path)
        errors.extend(f"{path}: {item}" for item in packet_errors)
        packets.append((path, packet))
    seen: dict[tuple[str, str], Path] = {}
    for path, packet in packets:
        key = (packet.get("classification", {}).get("module_id", ""), source_identity(packet))
        if key[1] and key in seen:
            errors.append(f"duplicate source within {key[0]}: {seen[key]} and {path}")
        elif key[1]:
            seen[key] = path
    return packets, errors


def batch_report(args: argparse.Namespace) -> int:
    packets, errors = load_valid_packets(args.root)
    modules: dict[str, dict[str, int]] = {
        module: {"prepared_packets": 0, "fulltext_verified": 0, "expression_qualified": 0}
        for module in MODULES
    }
    for _, packet in packets:
        module = packet["classification"]["module_id"]
        if packet["status"] in {"prepared", "qualified"}:
            modules[module]["prepared_packets"] += 1
        if packet["qualification"]["fulltext_status"] == "fulltext_verified":
            modules[module]["fulltext_verified"] += 1
        if packet["status"] == "qualified":
            modules[module]["expression_qualified"] += 1
    for module in MODULES:
        modules[module]["target_per_module"] = args.target_per_module
        modules[module]["fulltext_shortfall"] = max(0, args.target_per_module - modules[module]["fulltext_verified"])
        modules[module]["qualified_shortfall"] = max(0, args.target_per_module - modules[module]["expression_qualified"])
    report = {
        "schema_version": 1,
        "report_type": "soil-all-writing-fulltext-expression-coverage",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "packet_root": str(args.root.resolve()),
        "packet_count": len(packets),
        "target_per_module": args.target_per_module,
        "modules": modules,
        "validation_errors": errors,
        "target_met": not errors and all(
            data["expression_qualified"] >= args.target_per_module for data in modules.values()
        ),
        "release_scope": "coverage_evidence_only_not_a_claim_that_metadata_records_were_read",
    }
    write_json_new(args.output, report)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: coverage report contains {len(errors)} validation error(s)")
        return 1
    if args.enforce_target and not report["target_met"]:
        print("FAILED: expression-qualified target is not met for every D1–D13 module")
        return 1
    print(json.dumps({
        "status": "PASS", "packet_count": len(packets), "target_met": report["target_met"],
        "report": str(args.output),
    }, ensure_ascii=False))
    return 0


def export_qualified(args: argparse.Namespace) -> None:
    packets, errors = load_valid_packets(args.root)
    if errors:
        raise PipelineError("; ".join(errors))
    qualified = [(path, packet) for path, packet in packets if packet.get("status") == "qualified"]
    if not qualified:
        raise PipelineError("no qualified expression packets are available for export")
    if args.output.exists():
        raise PipelineError(f"refusing to overwrite existing file: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for _, packet in qualified:
            source = packet["source"]
            classification = packet["classification"]
            locator = packet["locator"]
            expression = packet["expression"]
            qualification = packet["qualification"]
            writer.writerow({
                "expression_id": packet["packet_id"],
                "entry_type": expression["entry_type"],
                "language": classification["language"],
                "discipline": classification["discipline"],
                "genre": classification["genre"],
                "section": classification["section"],
                "rhetorical_move": classification["rhetorical_move"],
                "exact_fragment": expression["exact_fragment"],
                "abstracted_pattern": expression["abstracted_pattern"],
                "source_title": source["source_title"],
                "authors": source["authors"],
                "year": source["year"],
                "doi": source["doi"],
                "url": source["canonical_url"],
                "locator": locator["value"],
                "license": source["license"],
                "access_date": source["access_date"],
                "verbatim_word_count": expression["verbatim_word_count"],
                "verified": "true",
                "context_limit": expression["context_limit"],
                "reuse_status": expression["reuse_status"],
                "notes": expression["notes"],
                "module_id": classification["module_id"],
                "source_type": source["source_type"],
                "fulltext_status": qualification["fulltext_status"],
                "qualification_status": qualification["qualification_status"],
                "reviewer_state": qualification["reviewer_state"],
                "release_scope": qualification["release_scope"],
                "module_fit_reason": classification["module_fit_reason"],
                "source_sha256": source["source_sha256"],
                "extracted_text_sha256": packet["extraction"]["extracted_text_sha256"],
                "review_basis_sha256": packet["review"]["review_basis_sha256"],
            })
    print(f"PASS: exported {len(qualified)} human-qualified expression packet(s) to {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--packet", required=True, type=Path)
    prepare.add_argument("--output-dir", required=True, type=Path)

    seal = subparsers.add_parser("seal-review")
    seal.add_argument("--packet", required=True, type=Path)
    seal.add_argument("--output", required=True, type=Path)

    validate = subparsers.add_parser("validate")
    validate.add_argument("packet", type=Path)

    report = subparsers.add_parser("batch-report")
    report.add_argument("root", type=Path)
    report.add_argument("--output", required=True, type=Path)
    report.add_argument("--target-per-module", type=int, default=1000)
    report.add_argument("--enforce-target", action="store_true")

    export = subparsers.add_parser("export-qualified")
    export.add_argument("root", type=Path)
    export.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "prepare":
            prepare_packet(args)
            return 0
        if args.command == "seal-review":
            seal_review(args)
            return 0
        if args.command == "validate":
            packet = read_json(args.packet)
            errors = validate_packet(packet, args.packet if packet.get("status") != "draft_metadata" else None)
            for error in errors:
                print(f"ERROR: {error}")
            if errors:
                print(f"FAILED: {len(errors)} full-text expression packet error(s)")
                return 1
            print(f"PASS: full-text expression packet is valid for state {packet.get('status')}")
            return 0
        if args.command == "batch-report":
            if args.target_per_module <= 0:
                raise PipelineError("target-per-module must be positive")
            return batch_report(args)
        if args.command == "export-qualified":
            export_qualified(args)
            return 0
        raise PipelineError("unknown command")
    except (PipelineError, OSError, UnicodeError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

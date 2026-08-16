#!/usr/bin/env python3
"""Audit Chinese professional prose for concrete NAR-1.0 residual risks; not a detector."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree as ET


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
FAIL_PATTERNS = {
    "N01-chat-residue": r"希望这对您有帮助|如果您需要我|作为(?:一个)?AI|当然[！!]|您说得(?:完全)?正确|知识截止|根据我(?:的)?训练",
    "N02-promotion": r"行业领先|国际一流|卓越品质|赋能|保驾护航|高度重视|精心组织|圆满完成|确保验收通过|零误差|百分之百准确|绝对准确",
    "N03-vague-attribution": r"专家认为|研究表明|业内普遍认为|众所周知|普遍认为|有关资料显示",
    "N05-formulaic-contrast": r"不仅仅?是?.{0,30}(?:而且|而是)|既要.{0,30}又要.{0,30}更要",
    "N08-invented-provenance": r"我公司(?:拥有|具备|已完成|长期从事)|项目负责人(?:主持|完成)过多个|获得(?:国家|省部级)奖",
    "N12-provenance-claim": r"纯人工|AI率\s*0%|零AI痕迹|任何检测器都|不可检测",
}
WATCH_WORDS = ("此外", "同时", "进一步", "有效提升", "切实保障", "全面", "显著", "关键", "至关重要")
DIAGNOSTIC_PATTERNS = {
    "N04-empty-significance": r"(?:具有|产生)(?:十分|重大|重要|深远)?(?:的)?(?:理论|实践|现实|科学)?意义|奠定(?:了)?坚实基础|提供(?:了)?有力支撑|开启.{0,20}新篇章|彰显.{0,20}(?:价值|意义)",
    "N11-meta-filler": r"值得注意的是|需要指出的是|不难发现|毋庸置疑|总的来说|从某种程度上(?:说|而言)",
}
DEFAULT_LEXICON = Path(__file__).resolve().parents[1] / "assets/domain-register-lexicon.json"
ALLOWED_EXCEPTION_KINDS = {
    "direct_quote", "official_name", "procurement_clause", "defined_technical_term", "locked_user_text",
}
ALLOWED_APPROVAL_ROLES = {
    "responsible_editor", "procurement_lead", "standards_editor", "patent_counsel",
    "document_owner", "domain_reviewer",
}
ExceptionKey = tuple[str, int, int]


def paragraphs_from_docx(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    paragraphs: list[str] = []
    for paragraph in root.iter(W + "p"):
        text = "".join(node.text or "" for node in paragraph.iter(W + "t")).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def load_paragraphs(path: Path) -> list[str]:
    if path.suffix.lower() == ".docx":
        return paragraphs_from_docx(path)
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_register_entries(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError("domain-register lexicon entries must be an array")
    return entries


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def occurrence_span(paragraph: str, term: str, occurrence_index: int) -> tuple[int, int] | None:
    spans = [(match.start(), match.end()) for match in re.finditer(re.escape(term), paragraph)]
    if occurrence_index < 1 or occurrence_index > len(spans):
        return None
    return spans[occurrence_index - 1]


def occurrence_index_for_match(paragraph: str, term: str, start: int, end: int) -> int:
    for index, match in enumerate(re.finditer(re.escape(term), paragraph), 1):
        if (match.start(), match.end()) == (start, end):
            return index
    raise ValueError(f"cannot resolve occurrence index for {term!r} at {start}:{end}")


def load_exception_record(
    path: Path, artifact_path: Path, paragraphs: list[str]
) -> tuple[dict[ExceptionKey, dict], list[str]]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"exception record: {exc}"]
    if data.get("schema_version") != 2:
        errors.append("exception record schema_version must be 2")
    expected_hash = data.get("artifact_sha256")
    actual_hash = sha256_file(artifact_path)
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        errors.append("exception record artifact_sha256 must be a lowercase SHA-256")
    elif expected_hash != actual_hash:
        errors.append("exception record artifact_sha256 does not match the audited artifact")
    raw_exceptions = data.get("exceptions")
    if not isinstance(raw_exceptions, list) or not raw_exceptions:
        errors.append("exception record must contain at least one exception")
        raw_exceptions = []
    exceptions: dict[ExceptionKey, dict] = {}
    seen_ids: set[str] = set()
    for index, entry in enumerate(raw_exceptions):
        locator = f"exceptions[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{locator} must be an object")
            continue
        exception_id = entry.get("exception_id")
        if not isinstance(exception_id, str) or not re.fullmatch(r"DREX-\d{3,}", exception_id):
            errors.append(f"{locator}.exception_id must match DREX-ddd")
        elif exception_id in seen_ids:
            errors.append(f"duplicate exception_id: {exception_id}")
        else:
            seen_ids.add(exception_id)
        term = entry.get("term")
        paragraph_number = entry.get("paragraph_number")
        occurrence_index = entry.get("occurrence_index")
        paragraph_hash = entry.get("paragraph_sha256")
        char_start = entry.get("char_start")
        char_end = entry.get("char_end")
        valid_target = True
        if not isinstance(term, str) or not term.strip():
            errors.append(f"{locator}.term must be non-empty")
            valid_target = False
        if not isinstance(paragraph_number, int) or paragraph_number < 1:
            errors.append(f"{locator}.paragraph_number must be a positive integer")
            valid_target = False
        elif paragraph_number > len(paragraphs):
            errors.append(f"{locator}.paragraph_number exceeds the audited paragraph count")
            valid_target = False
        if not isinstance(occurrence_index, int) or occurrence_index < 1:
            errors.append(f"{locator}.occurrence_index must be a positive integer")
            valid_target = False
        if not isinstance(paragraph_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", paragraph_hash):
            errors.append(f"{locator}.paragraph_sha256 must be a lowercase SHA-256")
            valid_target = False
        if not isinstance(char_start, int) or char_start < 0:
            errors.append(f"{locator}.char_start must be a non-negative integer")
            valid_target = False
        if not isinstance(char_end, int) or not isinstance(char_start, int) or char_end <= char_start:
            errors.append(f"{locator}.char_end must be greater than char_start")
            valid_target = False
        if entry.get("exception_scope") != "exact_occurrence_only":
            errors.append(f"{locator}.exception_scope must be exact_occurrence_only")
        source_kind = entry.get("source_kind")
        if source_kind not in ALLOWED_EXCEPTION_KINDS:
            errors.append(f"{locator}.source_kind is not controlled")
        if term in {"闭环", "全链条"} and source_kind == "defined_technical_term":
            errors.append(
                f"{locator}: {term} has no defined-technical-term exception in generated or translated prose"
            )
        for field in ("source_locator", "reason", "approved_by"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                errors.append(f"{locator}.{field} must be non-empty")
        source_snapshot_hash = entry.get("source_snapshot_sha256")
        if not isinstance(source_snapshot_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_snapshot_hash):
            errors.append(f"{locator}.source_snapshot_sha256 must be a lowercase SHA-256")
        approved_by = entry.get("approved_by")
        if isinstance(approved_by, str) and re.search(
            r"(?:agent|codex|artificial intelligence|\bAI\b)", approved_by, re.IGNORECASE
        ):
            errors.append(f"{locator}.approved_by must identify an accountable human approver")
        if entry.get("approval_role") not in ALLOWED_APPROVAL_ROLES:
            errors.append(f"{locator}.approval_role is not controlled")
        approved_at = entry.get("approved_at")
        try:
            parsed_approved_at = datetime.fromisoformat(str(approved_at).replace("Z", "+00:00"))
            if parsed_approved_at.tzinfo is None:
                errors.append(f"{locator}.approved_at must include a timezone")
        except ValueError:
            errors.append(f"{locator}.approved_at must be ISO 8601")
        if valid_target:
            paragraph = paragraphs[paragraph_number - 1]
            actual_paragraph_hash = sha256_text(paragraph)
            if paragraph_hash != actual_paragraph_hash:
                errors.append(f"{locator}.paragraph_sha256 does not match the audited paragraph")
                valid_target = False
            expected_span = occurrence_span(paragraph, term, occurrence_index)
            if expected_span is None:
                errors.append(f"{locator}: occurrence_index does not identify an occurrence of term")
                valid_target = False
            elif expected_span != (char_start, char_end):
                errors.append(
                    f"{locator}: char_start/char_end do not match occurrence {occurrence_index} "
                    f"of {term!r}"
                )
                valid_target = False
            elif paragraph[char_start:char_end] != term:
                errors.append(f"{locator}: character span does not equal term")
                valid_target = False
        if valid_target:
            key = (term, paragraph_number, occurrence_index)
            if key in exceptions:
                errors.append(
                    f"duplicate exact-occurrence exception: {term!r} paragraph {paragraph_number} "
                    f"occurrence {occurrence_index}"
                )
            exceptions[key] = entry
    return exceptions, errors


def context_allows(paragraph: str, start: int, end: int, entry: dict, genre: str) -> bool:
    """Return true only when an allowed-context match contains this exact occurrence."""
    for pattern in entry.get("allowed_context_patterns", []):
        for allowed in re.finditer(pattern, paragraph):
            if allowed.start() <= start and allowed.end() >= end:
                return True
    for rule in entry.get("allowed_context_rules", []):
        genres = rule.get("genres", ["*"])
        if "*" not in genres and genre not in genres:
            continue
        allowed_terms = rule.get("allowed_terms", [])
        if allowed_terms and paragraph[start:end] not in allowed_terms:
            continue
        for allowed in re.finditer(rule.get("pattern", ""), paragraph):
            if allowed.start() <= start and allowed.end() >= end:
                return True
    return False


def audit_register(
    paragraphs: list[str], entries: list[dict], genre: str, exceptions: dict[ExceptionKey, dict]
) -> tuple[list[str], list[str], set[ExceptionKey]]:
    failures: list[str] = []
    warnings: list[str] = []
    used_exceptions: set[ExceptionKey] = set()
    for paragraph_number, paragraph in enumerate(paragraphs, 1):
        for entry in entries:
            genres = entry.get("genres", ["*"])
            if "*" not in genres and genre not in genres:
                continue
            pattern = entry.get("pattern", "")
            expression = re.escape(pattern) if entry.get("match_type") == "literal" else pattern
            for match in re.finditer(expression, paragraph):
                matched = match.group(0)
                occurrence_index = occurrence_index_for_match(
                    paragraph, matched, match.start(), match.end()
                )
                exception_key = (matched, paragraph_number, occurrence_index)
                if exception_key in exceptions:
                    used_exceptions.add(exception_key)
                    continue
                if context_allows(paragraph, match.start(), match.end(), entry, genre):
                    continue
                suggestions = "；".join(entry.get("preferred_by_sense", []))
                message = (
                    f"{entry.get('id', 'DR???')} '{matched}' at paragraph {paragraph_number}: "
                    f"{entry.get('problem', 'register mismatch')}; preferred by sense: {suggestions}"
                )
                if entry.get("severity") == "warning":
                    warnings.append(message)
                else:
                    failures.append(message)
    return failures, warnings, used_exceptions


def build_exception_candidate_manifest(
    artifact_path: Path, paragraphs: list[str], entries: list[dict], genre: str
) -> dict:
    candidates: dict[tuple[int, int, int, str], dict] = {}

    def add_candidate(
        paragraph_number: int, paragraph: str, term: str, start: int, end: int,
        rule_id: str, severity: str,
    ) -> None:
        occurrence_index = occurrence_index_for_match(paragraph, term, start, end)
        key = (paragraph_number, start, end, term)
        if key not in candidates:
            candidates[key] = {
                "term": term,
                "paragraph_number": paragraph_number,
                "occurrence_index": occurrence_index,
                "paragraph_sha256": sha256_text(paragraph),
                "char_start": start,
                "char_end": end,
                "rule_ids": [],
                "severities": [],
            }
        if rule_id not in candidates[key]["rule_ids"]:
            candidates[key]["rule_ids"].append(rule_id)
        if severity not in candidates[key]["severities"]:
            candidates[key]["severities"].append(severity)

    for paragraph_number, paragraph in enumerate(paragraphs, 1):
        for rule_id, pattern in FAIL_PATTERNS.items():
            for match in re.finditer(pattern, paragraph):
                add_candidate(
                    paragraph_number, paragraph, match.group(0), match.start(), match.end(),
                    rule_id, "error",
                )
        for entry in entries:
            genres = entry.get("genres", ["*"])
            if "*" not in genres and genre not in genres:
                continue
            pattern = entry.get("pattern", "")
            expression = re.escape(pattern) if entry.get("match_type") == "literal" else pattern
            for match in re.finditer(expression, paragraph):
                if context_allows(paragraph, match.start(), match.end(), entry, genre):
                    continue
                add_candidate(
                    paragraph_number, paragraph, match.group(0), match.start(), match.end(),
                    entry.get("id", "DR???"), entry.get("severity", "error"),
                )
    ordered = [candidates[key] for key in sorted(candidates)]
    for candidate in ordered:
        candidate["rule_ids"].sort()
        candidate["severities"].sort()
    return {
        "schema_version": 1,
        "artifact_sha256": sha256_file(artifact_path),
        "paragraph_count": len(paragraphs),
        "character_offsets": "zero_based_half_open",
        "release_scope": "candidate_manifest_only_not_exception_approval",
        "candidates": ordered,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--genre", default="generic_formal_soil")
    parser.add_argument("--lexicon", type=Path, default=DEFAULT_LEXICON)
    parser.add_argument(
        "--exception-record", type=Path,
        help="Schema-v2 JSON record with artifact/paragraph hashes and exact-occurrence approvals.",
    )
    parser.add_argument(
        "--write-exception-candidates", type=Path,
        help="Write a new manifest of exact controlled occurrences that may require source review.",
    )
    parser.add_argument(
        "--fail-on-register-warnings", action="store_true",
        help="Treat context-sensitive domain-register warnings as release-blocking until revised or source-locked.",
    )
    args = parser.parse_args()
    try:
        paragraphs = load_paragraphs(args.path)
        register_entries = load_register_entries(args.lexicon)
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile, KeyError, ET.ParseError, UnicodeDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    if args.write_exception_candidates:
        if args.exception_record:
            print("ERROR: --write-exception-candidates cannot be combined with --exception-record")
            return 1
        if args.write_exception_candidates.exists():
            print(f"ERROR: refusing to overwrite {args.write_exception_candidates}")
            return 1
        manifest = build_exception_candidate_manifest(
            args.path, paragraphs, register_entries, args.genre
        )
        args.write_exception_candidates.parent.mkdir(parents=True, exist_ok=True)
        args.write_exception_candidates.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"PASS: wrote {len(manifest['candidates'])} exact exception candidate(s) to "
            f"{args.write_exception_candidates}"
        )
        return 0

    failures: list[str] = []
    exceptions: dict[ExceptionKey, dict] = {}
    if args.exception_record:
        exceptions, exception_errors = load_exception_record(
            args.exception_record, args.path, paragraphs
        )
        failures.extend(exception_errors)
    text = "\n".join(paragraphs)
    used_exceptions: set[ExceptionKey] = set()
    for code, pattern in FAIL_PATTERNS.items():
        match_count = 0
        for paragraph_number, paragraph in enumerate(paragraphs, 1):
            for match in re.finditer(pattern, paragraph):
                occurrence_index = occurrence_index_for_match(
                    paragraph, match.group(0), match.start(), match.end()
                )
                exception_key = (match.group(0), paragraph_number, occurrence_index)
                if exception_key in exceptions:
                    used_exceptions.add(exception_key)
                else:
                    match_count += 1
        if match_count:
            failures.append(f"{code}: {match_count} match(es)")

    register_failures, register_warnings, register_used_exceptions = audit_register(
        paragraphs, register_entries, args.genre, exceptions
    )
    used_exceptions.update(register_used_exceptions)
    failures.extend(register_failures)
    unused_exceptions = sorted(set(exceptions) - used_exceptions)
    for term, paragraph_number, occurrence_index in unused_exceptions:
        failures.append(
            f"unused source-locked exception {term!r} at paragraph {paragraph_number} "
            f"occurrence {occurrence_index}"
        )

    warnings: list[str] = []
    warnings.extend(register_warnings)
    for code, pattern in DIAGNOSTIC_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            warnings.append(f"{code}: {len(matches)} match(es); inspect function and evidence")
    counts = {word: text.count(word) for word in WATCH_WORDS}
    limits = {"此外": 2, "同时": 12, "进一步": 8, "有效提升": 4, "切实保障": 4, "全面": 8, "显著": 5, "关键": 10, "至关重要": 1}
    for word, count in counts.items():
        if count > limits[word]:
            warnings.append(f"watch-word {word} occurs {count} times (limit {limits[word]})")

    starts = Counter(re.sub(r"^[0-9一二三四五六七八九十（）().、\s]+", "", paragraph)[:8] for paragraph in paragraphs if len(paragraph) >= 12)
    for start, count in starts.most_common():
        if start and count >= 5:
            warnings.append(f"repeated paragraph opening '{start}' occurs {count} times")

    if args.fail_on_register_warnings and register_warnings:
        failures.append(
            f"strict domain-register release gate: {len(register_warnings)} context-sensitive warning(s) "
            "require revision or a paragraph/hash-bound exception"
        )

    for warning in warnings:
        print(f"WARNING: {warning}")
    for failure in failures:
        print(f"ERROR: {failure}")
    print(
        f"INFO: paragraphs={len(paragraphs)}; characters={len(text)}; warnings={len(warnings)}; "
        f"source_locked_exceptions_used={len(used_exceptions)}"
    )
    if failures:
        print(f"FAILED: {len(failures)} professional-style hard failure(s)")
        return 1
    print("PASS: no deterministic Chinese professional-style hard failures found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Extract, apply, and validate hash-bound DOCX language repairs without reformatting."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_protected_elements import compare as compare_protected  # noqa: E402


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
LANGUAGE_PART_RE = re.compile(
    r"^word/(?:document|header\d+|footer\d+|footnotes|endnotes|comments)\.xml$"
)
LOCK_TAGS = {W + name for name in ("fldChar", "instrText", "drawing", "object", "pict", "altChunk")}
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_package(path: Path) -> tuple[dict[str, bytes], dict[str, zipfile.ZipInfo]]:
    with zipfile.ZipFile(path) as archive:
        payloads = {info.filename: archive.read(info.filename) for info in archive.infolist()}
        infos = {info.filename: info for info in archive.infolist()}
    return payloads, infos


def language_parts(payloads: dict[str, bytes]) -> list[str]:
    return sorted(name for name in payloads if LANGUAGE_PART_RE.fullmatch(name))


def parse_language_roots(payloads: dict[str, bytes]) -> dict[str, ET.Element]:
    return {name: ET.fromstring(payloads[name]) for name in language_parts(payloads)}


def collect_units(roots: dict[str, ET.Element]) -> tuple[list[dict], dict[str, ET.Element]]:
    units: list[dict] = []
    nodes: dict[str, ET.Element] = {}
    for part in sorted(roots):
        root = roots[part]
        for paragraph_index, paragraph in enumerate(root.iter(W + "p"), 1):
            paragraph_text = "".join(node.text or "" for node in paragraph.iter(W + "t"))
            locked_tags = sorted({node.tag.removeprefix(W) for node in paragraph.iter() if node.tag in LOCK_TAGS})
            text_nodes = list(paragraph.iter(W + "t"))
            for text_index, node in enumerate(text_nodes, 1):
                unit_id = f"{part}::p{paragraph_index:05d}::t{text_index:03d}"
                original = node.text or ""
                units.append({
                    "unit_id": unit_id,
                    "part": part,
                    "paragraph_index": paragraph_index,
                    "text_index": text_index,
                    "text": original,
                    "text_sha256": sha256_bytes(original.encode("utf-8")),
                    "paragraph_text": paragraph_text,
                    "paragraph_text_sha256": sha256_bytes(paragraph_text.encode("utf-8")),
                    "editable": not locked_tags,
                    "locked_reasons": locked_tags,
                })
                nodes[unit_id] = node
    return units, nodes


def aggregate_text(roots: dict[str, ET.Element]) -> str:
    paragraphs: list[str] = []
    for part in sorted(roots):
        for paragraph in roots[part].iter(W + "p"):
            text = "".join(node.text or "" for node in paragraph.iter(W + "t"))
            if text:
                paragraphs.append(text)
    return "\n".join(paragraphs)


def extract_manifest(path: Path) -> dict:
    payloads, _ = load_package(path)
    roots = parse_language_roots(payloads)
    units, _ = collect_units(roots)
    return {
        "schema_version": 1,
        "source_path": str(path.resolve()),
        "source_sha256": sha256_file(path),
        "preservation_mode": "word_text_nodes_only",
        "language_parts": sorted(roots),
        "unit_count": len(units),
        "editable_unit_count": sum(bool(item["editable"]) for item in units),
        "units": units,
        "limitations": [
            "A unit is one existing Word text node. This preserves paragraph, run, table, numbering, field, and section structures but may require several coordinated edits when Word split a sentence across runs.",
            "Paragraphs containing fields, drawings, objects, or alternate content are locked by default.",
            "Protected-element comparison is conservative and does not prove semantic or scientific equivalence.",
        ],
    }


def write_json(record: dict, output: Path | None) -> None:
    payload = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    if output:
        output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)


def load_plan(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("repair plan schema_version must be 1")
    if data.get("preservation_mode") != "word_text_nodes_only":
        raise ValueError("repair plan preservation_mode must be word_text_nodes_only")
    repairs = data.get("repairs")
    if not isinstance(repairs, list) or not repairs:
        raise ValueError("repair plan must contain at least one repair")
    return data


def apply_repairs(source: Path, plan_path: Path, output: Path, allow_protected_change: bool) -> dict:
    if output.exists():
        raise ValueError("output already exists; use a new path to preserve the source artifact")
    plan = load_plan(plan_path)
    source_hash = sha256_file(source)
    if plan.get("source_sha256") != source_hash:
        raise ValueError("repair plan source_sha256 does not match the source DOCX")
    payloads, infos = load_package(source)
    roots = parse_language_roots(payloads)
    units, nodes = collect_units(roots)
    by_id = {item["unit_id"]: item for item in units}
    seen: set[str] = set()
    modified_parts: set[str] = set()
    applied: list[dict] = []
    source_text = aggregate_text(roots)
    for index, repair in enumerate(plan["repairs"]):
        locator = f"repairs[{index}]"
        if not isinstance(repair, dict):
            raise ValueError(f"{locator} must be an object")
        unit_id = repair.get("unit_id")
        if unit_id in seen:
            raise ValueError(f"duplicate repair unit_id: {unit_id}")
        seen.add(unit_id)
        unit = by_id.get(unit_id)
        if not unit:
            raise ValueError(f"{locator}.unit_id does not exist in the source")
        if not unit["editable"]:
            raise ValueError(f"{locator} targets a locked paragraph: {unit['locked_reasons']}")
        if repair.get("original_text_sha256") != unit["text_sha256"]:
            raise ValueError(f"{locator}.original_text_sha256 does not match the source unit")
        replacement = repair.get("replacement_text")
        if not isinstance(replacement, str):
            raise ValueError(f"{locator}.replacement_text must be a string")
        if CONTROL_RE.search(replacement):
            raise ValueError(f"{locator}.replacement_text contains a prohibited control character")
        if not replacement and not repair.get("allow_empty", False):
            raise ValueError(f"{locator} cannot delete a unit unless allow_empty is true")
        if replacement == unit["text"]:
            raise ValueError(f"{locator} does not change the text")
        node = nodes[unit_id]
        node.text = replacement
        if replacement[:1].isspace() or replacement[-1:].isspace():
            node.set(XML_SPACE, "preserve")
        else:
            node.attrib.pop(XML_SPACE, None)
        modified_parts.add(unit["part"])
        applied.append({
            "unit_id": unit_id,
            "original_text_sha256": unit["text_sha256"],
            "replacement_text_sha256": sha256_bytes(replacement.encode("utf-8")),
            "reason": repair.get("reason", ""),
        })
    target_text = aggregate_text(roots)
    protected = compare_protected(source_text, target_text, str(source), str(output))
    if not protected["passed"] and not allow_protected_change:
        raise ValueError(
            "protected elements changed; review the difference and rerun only with explicit authorization: "
            + json.dumps(protected["differences"], ensure_ascii=False)
        )
    for part in modified_parts:
        payloads[part] = ET.tostring(roots[part], encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(output, "w") as archive:
        for name in infos:
            archive.writestr(infos[name], payloads[name])
    return {
        "schema_version": 1,
        "status": "PASS",
        "source_path": str(source.resolve()),
        "source_sha256": source_hash,
        "plan_path": str(plan_path.resolve()),
        "plan_sha256": sha256_file(plan_path),
        "output_path": str(output.resolve()),
        "output_sha256": sha256_file(output),
        "repair_count": len(applied),
        "modified_parts": sorted(modified_parts),
        "protected_elements_passed": protected["passed"],
        "protected_elements_override": bool(not protected["passed"] and allow_protected_change),
        "applied": applied,
    }


def shape(node: ET.Element) -> tuple:
    attributes = tuple(sorted(
        (key, value) for key, value in node.attrib.items()
        if not (node.tag == W + "t" and key == XML_SPACE)
    ))
    if node.tag == W + "t":
        text = "<EDITABLE_TEXT>"
    else:
        text = node.text if node.text and node.text.strip() else None
    return node.tag, attributes, text, tuple(shape(child) for child in list(node))


def validate_fidelity(source: Path, target: Path, plan_path: Path) -> list[str]:
    errors: list[str] = []
    plan = load_plan(plan_path)
    if plan.get("source_sha256") != sha256_file(source):
        errors.append("plan source_sha256 does not match source")
    source_payloads, _ = load_package(source)
    target_payloads, _ = load_package(target)
    if set(source_payloads) != set(target_payloads):
        errors.append("OPC package entry names changed")
    source_roots = parse_language_roots(source_payloads)
    target_roots = parse_language_roots(target_payloads)
    source_units, _ = collect_units(source_roots)
    target_units, _ = collect_units(target_roots)
    source_by_id = {item["unit_id"]: item for item in source_units}
    target_by_id = {item["unit_id"]: item for item in target_units}
    if set(source_by_id) != set(target_by_id):
        errors.append("Word text-node topology changed")
    planned: dict[str, dict] = {}
    for repair in plan["repairs"]:
        unit_id = repair.get("unit_id")
        if unit_id in planned:
            errors.append(f"duplicate repair unit_id: {unit_id}")
        planned[unit_id] = repair
    changed: set[str] = set()
    for unit_id in set(source_by_id) & set(target_by_id):
        source_text = source_by_id[unit_id]["text"]
        target_text = target_by_id[unit_id]["text"]
        if source_text != target_text:
            changed.add(unit_id)
        if unit_id in planned and target_text != planned[unit_id].get("replacement_text"):
            errors.append(f"planned replacement not materialized: {unit_id}")
    unexpected = changed - set(planned)
    missing = set(planned) - changed
    if unexpected:
        errors.append(f"unplanned text units changed: {', '.join(sorted(unexpected))}")
    if missing:
        errors.append(f"planned text units did not change: {', '.join(sorted(missing))}")
    for name in set(source_payloads) & set(target_payloads):
        if name in source_roots:
            if shape(source_roots[name]) != shape(target_roots[name]):
                errors.append(f"non-text XML structure or formatting changed in {name}")
        elif source_payloads[name] != target_payloads[name]:
            errors.append(f"non-language package part changed: {name}")
    protected = compare_protected(
        aggregate_text(source_roots), aggregate_text(target_roots), str(source), str(target)
    )
    if not protected["passed"]:
        errors.append("protected elements changed: " + json.dumps(protected["differences"], ensure_ascii=False))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("source", type=Path)
    extract_parser.add_argument("--output", type=Path)
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("source", type=Path)
    apply_parser.add_argument("plan", type=Path)
    apply_parser.add_argument("output", type=Path)
    apply_parser.add_argument("--allow-protected-change", action="store_true")
    apply_parser.add_argument("--receipt", type=Path)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("source", type=Path)
    validate_parser.add_argument("target", type=Path)
    validate_parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "extract":
            write_json(extract_manifest(args.source), args.output)
            return 0
        if args.command == "apply":
            receipt = apply_repairs(
                args.source, args.plan, args.output, args.allow_protected_change
            )
            write_json(receipt, args.receipt)
            return 0
        errors = validate_fidelity(args.source, args.target, args.plan)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile, ET.ParseError) as exc:
        print(f"ERROR: {exc}")
        return 1
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} DOCX language-repair fidelity error(s)")
        return 1
    print("PASS: only planned Word text nodes changed; package structure, formatting, and protected elements are preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

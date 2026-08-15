#!/usr/bin/env python3
"""Apply provenance-bound, allowlisted DOCX formatting and verify integrity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from add_format_comments import _parse_xml, _serialize
from compare_docx_content import GuardError, compare_documents
from ooxml_safety import PackageSafetyError, read_docx_package, sha256_file
from scope_policy import validate_format_only_payload
from validate_journal_profile import validate_profile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"

STORY_PARTS = {
    "document": "word/document.xml",
    "footnotes": "word/footnotes.xml",
    "endnotes": "word/endnotes.xml",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "widowControl", "numPr", "suppressLineNumbers",
    "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct", "topLinePunct",
    "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind", "contextualSpacing",
    "mirrorIndents", "suppressOverlap", "jc", "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl",
    "divId", "cnfStyle", "rPr", "sectPr", "pPrChange",
]
RPR_ORDER = [
    "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike", "outline",
    "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing", "w",
    "kern", "position", "sz", "szCs", "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign",
    "rtl", "cs", "em", "lang", "eastAsianLayout", "specVanish", "oMath", "rPrChange",
]
TBLPR_ORDER = [
    "tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize", "tblStyleColBandSize", "tblW",
    "jc", "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption",
    "tblDescription", "tblPrChange",
]
TRPR_ORDER = [
    "cnfStyle", "divId", "gridBefore", "gridAfter", "wBefore", "wAfter", "cantSplit", "trHeight", "tblHeader",
    "tblCellSpacing", "jc", "hidden", "ins", "del", "trPrChange",
]
SECTPR_ORDER = [
    "headerReference", "footerReference", "footnotePr", "endnotePr", "type", "pgSz", "pgMar", "paperSrc",
    "pgBorders", "lnNumType", "pgNumType", "cols", "formProt", "vAlign", "noEndnote", "titlePg", "textDirection",
    "bidi", "rtlGutter", "docGrid", "printerSettings", "sectPrChange",
]
ORDER_MAP = {"pPr": PPR_ORDER, "rPr": RPR_ORDER, "tblPr": TBLPR_ORDER, "trPr": TRPR_ORDER, "sectPr": SECTPR_ORDER}


def qn(local: str) -> str:
    return f"{{{W}}}{local}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _ordered_child(parent: ET.Element, local: str) -> ET.Element:
    found = parent.find(qn(local))
    if found is not None:
        return found
    element = ET.Element(qn(local))
    order = ORDER_MAP.get(_local(parent.tag))
    if not order or local not in order:
        parent.append(element)
        return element
    wanted = order.index(local)
    insert_at = len(parent)
    for index, child in enumerate(parent):
        child_local = _local(child.tag)
        if child_local in order and order.index(child_local) > wanted:
            insert_at = index
            break
    parent.insert(insert_at, element)
    return element


def _property_container(target: ET.Element, local: str) -> ET.Element:
    existing = target.find(qn(local))
    if existing is not None:
        return existing
    value = ET.Element(qn(local))
    target.insert(0, value)
    return value


def _set_val(parent: ET.Element, local: str, value: Any, attribute: str = "val") -> None:
    _ordered_child(parent, local).set(qn(attribute), str(value))


def _set_on_off(parent: ET.Element, local: str, value: bool) -> None:
    _ordered_child(parent, local).set(qn("val"), "1" if value else "0")


def _expect_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"{label}: unsupported keys: {', '.join(unknown)}")


def _nonnegative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _paragraph_text(paragraph: ET.Element) -> str:
    chunks = []
    for element in paragraph.iter():
        if element.tag == qn("t"):
            chunks.append(element.text or "")
        elif element.tag == qn("tab"):
            chunks.append("\t")
        elif element.tag in {qn("br"), qn("cr")}:
            chunks.append("\n")
    return "".join(chunks)


def _run_text(run: ET.Element) -> str:
    return "".join(element.text or "" for element in run.iter(qn("t")))


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _table_structure_hash(table: ET.Element) -> str:
    rows = []
    for row in table.findall(qn("tr")):
        cells = []
        for cell in row.findall(qn("tc")):
            tc_pr = cell.find(qn("tcPr"))
            span = None
            merge = None
            if tc_pr is not None:
                span_element = tc_pr.find(qn("gridSpan"))
                merge_element = tc_pr.find(qn("vMerge"))
                span = span_element.get(qn("val"), "1") if span_element is not None else None
                merge = merge_element.get(qn("val"), "continue") if merge_element is not None else None
            cells.append({"span": span, "merge": merge, "text": _sha_text(_paragraph_text(cell))})
        rows.append(cells)
    return _sha_text(json.dumps(rows, sort_keys=True, separators=(",", ":")))


def _section_hash(section: ET.Element) -> str:
    return hashlib.sha256(ET.tostring(section)).hexdigest()


def _paragraph_properties(paragraph: ET.Element, properties: dict[str, Any]) -> None:
    allowed = {
        "alignment", "spacing_before_twips", "spacing_after_twips", "line_twips", "line_rule",
        "first_line_twips", "hanging_twips", "left_twips", "right_twips", "keep_with_next", "keep_lines",
        "page_break_before", "widow_control",
    }
    _expect_keys(properties, allowed, "paragraph properties")
    p_pr = _property_container(paragraph, "pPr")
    if "alignment" in properties:
        alignment = str(properties["alignment"])
        if alignment not in {"left", "center", "right", "both", "distribute"}:
            raise ValueError(f"Unsupported paragraph alignment: {alignment}")
        _set_val(p_pr, "jc", alignment)
    spacing_fields = {
        "spacing_before_twips": "before", "spacing_after_twips": "after", "line_twips": "line", "line_rule": "lineRule",
    }
    if any(name in properties for name in spacing_fields):
        spacing = _ordered_child(p_pr, "spacing")
        for name, attribute in spacing_fields.items():
            if name not in properties:
                continue
            value = properties[name]
            if name == "line_rule":
                if value not in {"auto", "atLeast", "exact"}:
                    raise ValueError("line_rule must be auto, atLeast, or exact")
            else:
                value = _nonnegative_int(value, name)
            spacing.set(qn(attribute), str(value))
    indent_fields = {
        "first_line_twips": "firstLine", "hanging_twips": "hanging", "left_twips": "left", "right_twips": "right",
    }
    if any(name in properties for name in indent_fields):
        if "first_line_twips" in properties and "hanging_twips" in properties:
            raise ValueError("first_line_twips and hanging_twips are mutually exclusive")
        ind = _ordered_child(p_pr, "ind")
        for name, attribute in indent_fields.items():
            if name in properties:
                ind.set(qn(attribute), str(_nonnegative_int(properties[name], name)))
    for name, local in {
        "keep_with_next": "keepNext", "keep_lines": "keepLines", "page_break_before": "pageBreakBefore",
        "widow_control": "widowControl",
    }.items():
        if name in properties:
            if not isinstance(properties[name], bool):
                raise ValueError(f"{name} must be boolean")
            _set_on_off(p_pr, local, properties[name])


def _assert_run_safe(run: ET.Element, properties: dict[str, Any]) -> None:
    if "vertical_alignment" in properties:
        raise ValueError("vertical_alignment is blocked because superscript/subscript can change scientific meaning")
    font_change = any(key.startswith("font_") and key != "font_size_half_points" for key in properties)
    if font_change:
        blocked = {"sym", "instrText", "fldChar", "footnoteReference", "endnoteReference"}
        if any(_local(element.tag) in blocked for element in run.iter()):
            raise ValueError("font-family changes are blocked on symbol, field, and note-reference runs")
        if any("\ue000" <= char <= "\uf8ff" for char in _run_text(run)):
            raise ValueError("font-family changes are blocked on private-use characters")


def _run_properties(run: ET.Element, properties: dict[str, Any]) -> None:
    allowed = {
        "font_ascii", "font_hansi", "font_east_asia", "font_cs", "font_size_half_points", "bold", "italic", "color",
    }
    _expect_keys(properties, allowed, "run properties")
    _assert_run_safe(run, properties)
    r_pr = _property_container(run, "rPr")
    font_fields = {"font_ascii": "ascii", "font_hansi": "hAnsi", "font_east_asia": "eastAsia", "font_cs": "cs"}
    if any(name in properties for name in font_fields):
        fonts = _ordered_child(r_pr, "rFonts")
        for name, attribute in font_fields.items():
            if name in properties:
                value = str(properties[name]).strip()
                if not value:
                    raise ValueError(f"{name} cannot be empty")
                fonts.set(qn(attribute), value)
    if "font_size_half_points" in properties:
        size = _nonnegative_int(properties["font_size_half_points"], "font_size_half_points")
        if size == 0:
            raise ValueError("font_size_half_points must be greater than zero")
        _set_val(r_pr, "sz", size)
        _set_val(r_pr, "szCs", size)
    for name, local in {"bold": "b", "italic": "i"}.items():
        if name in properties:
            if not isinstance(properties[name], bool):
                raise ValueError(f"{name} must be boolean")
            _set_on_off(r_pr, local, properties[name])
    if "color" in properties:
        color = str(properties["color"]).upper().lstrip("#")
        if not re.fullmatch(r"[0-9A-F]{6}", color):
            raise ValueError("color must be a 6-digit hexadecimal RGB value")
        _set_val(r_pr, "color", color)


def _section_properties(section: ET.Element, properties: dict[str, Any]) -> None:
    allowed = {
        "page_width_twips", "page_height_twips", "orientation", "margin_top_twips", "margin_right_twips",
        "margin_bottom_twips", "margin_left_twips", "header_twips", "footer_twips", "gutter_twips", "columns",
        "column_space_twips",
    }
    _expect_keys(properties, allowed, "section properties")
    if any(name in properties for name in ("page_width_twips", "page_height_twips", "orientation")):
        page = _ordered_child(section, "pgSz")
        for name, attribute in {"page_width_twips": "w", "page_height_twips": "h"}.items():
            if name in properties:
                page.set(qn(attribute), str(_nonnegative_int(properties[name], name)))
        if "orientation" in properties:
            if properties["orientation"] not in {"portrait", "landscape"}:
                raise ValueError("orientation must be portrait or landscape")
            page.set(qn("orient"), properties["orientation"])
    margin_fields = {
        "margin_top_twips": "top", "margin_right_twips": "right", "margin_bottom_twips": "bottom",
        "margin_left_twips": "left", "header_twips": "header", "footer_twips": "footer", "gutter_twips": "gutter",
    }
    if any(name in properties for name in margin_fields):
        margins = _ordered_child(section, "pgMar")
        for name, attribute in margin_fields.items():
            if name in properties:
                margins.set(qn(attribute), str(_nonnegative_int(properties[name], name)))
    if "columns" in properties or "column_space_twips" in properties:
        columns = _ordered_child(section, "cols")
        if "columns" in properties:
            count = _nonnegative_int(properties["columns"], "columns")
            if count < 1:
                raise ValueError("columns must be at least 1")
            columns.set(qn("num"), str(count))
        if "column_space_twips" in properties:
            columns.set(qn("space"), str(_nonnegative_int(properties["column_space_twips"], "column_space_twips")))


def _table_properties(table: ET.Element, properties: dict[str, Any]) -> None:
    allowed = {"alignment", "width_twips", "autofit", "repeat_first_row"}
    _expect_keys(properties, allowed, "table properties")
    tbl_pr = _property_container(table, "tblPr")
    if "alignment" in properties:
        if properties["alignment"] not in {"left", "center", "right"}:
            raise ValueError("table alignment must be left, center, or right")
        _set_val(tbl_pr, "jc", properties["alignment"])
    if "width_twips" in properties:
        width = _nonnegative_int(properties["width_twips"], "width_twips")
        tbl_w = _ordered_child(tbl_pr, "tblW")
        tbl_w.set(qn("type"), "dxa")
        tbl_w.set(qn("w"), str(width))
    if "autofit" in properties:
        if not isinstance(properties["autofit"], bool):
            raise ValueError("autofit must be boolean")
        _set_val(tbl_pr, "tblLayout", "autofit" if properties["autofit"] else "fixed", "type")
    if "repeat_first_row" in properties:
        if not isinstance(properties["repeat_first_row"], bool):
            raise ValueError("repeat_first_row must be boolean")
        first_row = table.find(qn("tr"))
        if first_row is None:
            raise ValueError("Cannot set repeat_first_row on a table with no rows")
        tr_pr = _property_container(first_row, "trPr")
        _set_on_off(tr_pr, "tblHeader", properties["repeat_first_row"])


def _indices(target: Any, count: int, label: str) -> list[int]:
    if target == "all":
        return list(range(count))
    index = _nonnegative_int(target, label)
    if index >= count:
        raise ValueError(f"{label} {index} is out of range (count={count})")
    return [index]


def _story_scope(root: ET.Element, story: str, note_id: str | None) -> ET.Element:
    if story == "document":
        return root
    singular = "footnote" if story == "footnotes" else "endnote"
    for note in root.findall(qn(singular)):
        if note.get(qn("id")) == note_id:
            if note.get(qn("type"), "normal") != "normal":
                raise ValueError(f"{story} note_id {note_id} is not a normal note")
            return note
    raise ValueError(f"{story} note_id {note_id} was not found")


def _verify_fingerprint(operation_id: str, operation: dict[str, Any], target: ET.Element, op: str) -> None:
    expected = str(operation.get("expected_text_sha256", "")).lower()
    if op in {"paragraph", "run"}:
        if not SHA256_RE.fullmatch(expected):
            raise ValueError(f"{operation_id}: expected_text_sha256 is required")
        if _sha_text(_paragraph_text(target)) != expected:
            raise ValueError(f"{operation_id}: target paragraph fingerprint mismatch")
    if op == "table":
        expected_structure = str(operation.get("expected_structure_sha256", "")).lower()
        if not SHA256_RE.fullmatch(expected_structure) or _table_structure_hash(target) != expected_structure:
            raise ValueError(f"{operation_id}: table structure fingerprint mismatch")
    if op == "section":
        expected_structure = str(operation.get("expected_structure_sha256", "")).lower()
        if not SHA256_RE.fullmatch(expected_structure) or _section_hash(target) != expected_structure:
            raise ValueError(f"{operation_id}: section fingerprint mismatch")


def apply_operations(stories: dict[str, ET.Element], plan: dict[str, Any], rules: dict[str, dict]) -> list[dict[str, Any]]:
    operations = plan.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError("Format plan operations must be a non-empty list")
    applied = []
    seen_operations: set[str] = set()
    allowed_keys = {
        "operation_id", "rule_id", "op", "story", "note_id", "paragraph_index", "run_index", "section_index",
        "table_index", "properties", "expected_text_sha256", "expected_run_text_sha256", "expected_structure_sha256",
        "risk_class",
    }
    for number, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            raise ValueError(f"operations[{number - 1}] must be an object")
        _expect_keys(operation, allowed_keys, f"operations[{number - 1}]")
        operation_id = str(operation.get("operation_id", ""))
        if not operation_id or operation_id in seen_operations:
            raise ValueError(f"operations[{number - 1}].operation_id is missing or duplicated")
        seen_operations.add(operation_id)
        rule_id = str(operation.get("rule_id", ""))
        rule = rules.get(rule_id)
        if not rule:
            raise ValueError(f"{operation_id}: rule_id {rule_id!r} is absent from the journal profile")
        if rule.get("verification_status") != "VERIFIED" or rule.get("automation") != "AUTO_FIX":
            raise ValueError(f"{operation_id}: automatic edits require a VERIFIED/AUTO_FIX rule")
        if operation.get("risk_class") != "SAFE_TYPOGRAPHY":
            raise ValueError(f"{operation_id}: risk_class must be SAFE_TYPOGRAPHY")
        story = str(operation.get("story", "document"))
        if story not in stories:
            raise ValueError(f"{operation_id}: DOCX does not contain story {story!r}")
        note_id = str(operation["note_id"]) if operation.get("note_id") is not None else None
        if story in {"footnotes", "endnotes"} and note_id is None:
            raise ValueError(f"{operation_id}: note_id is required for {story}")
        if story == "document" and note_id is not None:
            raise ValueError(f"{operation_id}: note_id is invalid for document story")
        scope = _story_scope(stories[story], story, note_id)
        op = operation.get("op")
        properties = operation.get("properties")
        if not isinstance(properties, dict) or not properties:
            raise ValueError(f"{operation_id}: properties must be a non-empty object")

        if op == "paragraph":
            paragraphs = list(scope.iter(qn("p")))
            index = _indices(operation.get("paragraph_index"), len(paragraphs), "paragraph_index")[0]
            _verify_fingerprint(operation_id, operation, paragraphs[index], op)
            _paragraph_properties(paragraphs[index], properties)
            target = {"paragraph_index": index}
        elif op == "run":
            paragraphs = list(scope.iter(qn("p")))
            p_index = _indices(operation.get("paragraph_index"), len(paragraphs), "paragraph_index")[0]
            paragraph = paragraphs[p_index]
            _verify_fingerprint(operation_id, operation, paragraph, op)
            runs = list(paragraph.iter(qn("r")))
            run_indices = _indices(operation.get("run_index", "all"), len(runs), "run_index")
            if not run_indices:
                raise ValueError(f"{operation_id}: target paragraph has no runs")
            expected_run = operation.get("expected_run_text_sha256")
            if operation.get("run_index", "all") != "all":
                if not SHA256_RE.fullmatch(str(expected_run or "").lower()):
                    raise ValueError(f"{operation_id}: expected_run_text_sha256 is required for one run")
                if _sha_text(_run_text(runs[run_indices[0]])) != str(expected_run).lower():
                    raise ValueError(f"{operation_id}: target run fingerprint mismatch")
            for run_index in run_indices:
                _run_properties(runs[run_index], properties)
            target = {"paragraph_index": p_index, "run_indices": run_indices}
        elif op == "section":
            if story != "document":
                raise ValueError(f"{operation_id}: section operations only support document story")
            sections = list(scope.iter(qn("sectPr")))
            section_indices = _indices(operation.get("section_index"), len(sections), "section_index")
            if len(section_indices) != 1:
                raise ValueError(f"{operation_id}: section_index must identify one fingerprinted section")
            section = sections[section_indices[0]]
            _verify_fingerprint(operation_id, operation, section, op)
            _section_properties(section, properties)
            target = {"section_indices": section_indices}
        elif op == "table":
            tables = list(scope.iter(qn("tbl")))
            table_index = _indices(operation.get("table_index"), len(tables), "table_index")[0]
            _verify_fingerprint(operation_id, operation, tables[table_index], op)
            _table_properties(tables[table_index], properties)
            target = {"table_index": table_index}
        else:
            raise ValueError(f"{operation_id}: unsupported op {op!r}")
        applied.append(
            {
                "operation_id": operation_id,
                "rule_id": rule_id,
                "op": op,
                "story": story,
                "note_id": note_id,
                **target,
                "properties": properties,
            }
        )
    return applied


def _load_plan(plan_path: Path, profile_path: Path, source: Path) -> tuple[dict, dict]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    validation = validate_profile(profile)
    if validation["status"] != "PASS":
        raise ValueError(f"Journal profile is invalid: {validation['errors']}")
    _expect_keys(
        plan,
        {"schema_version", "scope", "source_document_sha256", "journal_profile_sha256", "operations"},
        "format plan",
    )
    scope_errors = validate_format_only_payload(plan)
    if scope_errors:
        raise ValueError(f"Format plan is outside scope: {scope_errors}")
    if plan.get("schema_version") != "2.0" or plan.get("scope") != "FORMAT_ONLY":
        raise ValueError("Format plan requires schema_version 2.0 and scope FORMAT_ONLY")
    if str(plan.get("source_document_sha256", "")).lower() != sha256_file(source):
        raise ValueError("Format plan source_document_sha256 does not match the source DOCX")
    if str(plan.get("journal_profile_sha256", "")).lower() != sha256_file(profile_path):
        raise ValueError("Format plan journal_profile_sha256 does not match the journal profile")
    return plan, profile


def apply_format(source: Path, plan_path: Path, profile_path: Path, output: Path) -> dict[str, Any]:
    if source.resolve() == output.resolve():
        raise ValueError("Output must not overwrite the source DOCX")
    plan, profile = _load_plan(plan_path, profile_path, source)
    parts, infos, security = read_docx_package(source)
    story_roots = {}
    story_namespaces = {}
    for story, part_name in STORY_PARTS.items():
        if part_name in parts:
            story_roots[story], story_namespaces[story] = _parse_xml(parts[part_name])
    rules = {str(rule["rule_id"]): rule for rule in profile["rules"]}
    applied = apply_operations(story_roots, plan, rules)
    for story, root in story_roots.items():
        parts[STORY_PARTS[story]] = _serialize(root, story_namespaces[story])

    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix="format-revision-", suffix=".docx", dir=output.parent)
    os.close(handle)
    try:
        with zipfile.ZipFile(temporary_name, "w") as target:
            for info in infos:
                target.writestr(info, b"" if info.is_dir() else parts[info.filename])
        guard = compare_documents(source, Path(temporary_name))
        if guard["status"] != "PASS":
            raise ValueError(f"Content guard rejected the formatted DOCX: {guard['failures']}")
        os.replace(temporary_name, output)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return {
        "status": "PASS",
        "scope": "FORMAT_ONLY",
        "source": str(source.resolve()),
        "output": str(output.resolve()),
        "source_sha256": sha256_file(source),
        "output_sha256": sha256_file(output),
        "plan_sha256": sha256_file(plan_path),
        "profile_sha256": sha256_file(profile_path),
        "package_security": security,
        "operations_applied": applied,
        "content_guard": guard,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--journal-profile", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        result = apply_format(args.source, args.plan, args.journal_profile, args.out)
    except (
        FileNotFoundError,
        KeyError,
        ValueError,
        GuardError,
        PackageSafetyError,
        zipfile.BadZipFile,
        ET.ParseError,
        json.JSONDecodeError,
    ) as exc:
        result = {"status": "ERROR", "error": str(exc)}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())

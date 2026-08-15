#!/usr/bin/env python3
"""Fail-closed semantic and package-integrity guard for DOCX format revisions.

The guard permits formatting XML changes. It rejects visible-text changes,
note/reference remaps, field changes, tracked-change history loss, equation or
table-structure changes, relationship remaps, unapproved header/footer edits,
and changes to opaque/binary package parts. Comments can be added only when the
caller explicitly enables the addition policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from ooxml_safety import (
    PackageSafetyError,
    read_docx_package,
    sha256_bytes,
    sha256_file,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"

W_P = f"{{{W}}}p"
W_T = f"{{{W}}}t"
M_T = f"{{{M}}}t"

CORE_STORY_PARTS = ("word/document.xml", "word/footnotes.xml", "word/endnotes.xml")
COMMENT_REL_SUFFIXES = ("/comments", "/commentsExtended", "/commentsExtensible")
COMMENT_PART_PREFIXES = (
    "word/comments.xml",
    "word/commentsExtended.xml",
    "word/commentsExtensible.xml",
    "word/people.xml",
)
FORMAT_OR_METADATA_PARTS = {
    "[Content_Types].xml",
    "docProps/core.xml",
    "docProps/app.xml",
    "docProps/custom.xml",
}
REVISION_TAGS = {
    "ins",
    "del",
    "moveFrom",
    "moveTo",
    "moveFromRangeStart",
    "moveFromRangeEnd",
    "moveToRangeStart",
    "moveToRangeEnd",
    "pPrChange",
    "rPrChange",
    "sectPrChange",
    "tblPrChange",
    "tblGridChange",
    "trPrChange",
    "tcPrChange",
    "numberingChange",
}
IGNORED_SEMANTIC_TAGS = {
    "pPr",
    "rPr",
    "tblPr",
    "trPr",
    "tcPr",
    "sectPr",
    "proofErr",
    "lastRenderedPageBreak",
    "commentRangeStart",
    "commentRangeEnd",
    "commentReference",
}


class GuardError(RuntimeError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def _parse_xml(data: bytes, label: str) -> ET.Element:
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise GuardError(f"Invalid OOXML XML part {label}: {exc}") from exc


def _is_within(element: ET.Element, parents: dict[ET.Element, ET.Element], locals_: set[str]) -> bool:
    current = element
    while current in parents:
        current = parents[current]
        if _namespace(current.tag) == W and _local(current.tag) in locals_:
            return True
    return False


def extract_visible_text(xml_bytes: bytes, label: str = "story") -> str:
    """Extract text shown in the current Word view, excluding deletions."""
    root = _parse_xml(xml_bytes, label)
    parents = {child: parent for parent in root.iter() for child in parent}
    paragraphs: list[str] = []
    for paragraph in root.iter(W_P):
        if _is_within(paragraph, parents, {"del", "moveFrom"}):
            continue
        chunks: list[str] = []
        for element in paragraph.iter():
            if _is_within(element, parents, {"del", "moveFrom"}):
                continue
            if element.tag in {W_T, M_T}:
                chunks.append(element.text or "")
            elif element.tag == f"{{{W}}}tab":
                chunks.append("\t")
            elif element.tag in {f"{{{W}}}br", f"{{{W}}}cr"}:
                chunks.append("\n")
            elif element.tag == f"{{{W}}}noBreakHyphen":
                chunks.append("\u2011")
            elif element.tag == f"{{{W}}}softHyphen":
                chunks.append("\u00ad")
            elif element.tag == f"{{{W}}}sym":
                chunks.append(
                    f"[SYM:{element.get(f'{{{W}}}font', '')}:{element.get(f'{{{W}}}char', '')}]"
                )
        paragraphs.append("".join(chunks))
    return "\n".join(paragraphs)


def _first_difference(left: str, right: str, radius: int = 36) -> dict[str, Any] | None:
    limit = min(len(left), len(right))
    index = next((i for i in range(limit) if left[i] != right[i]), limit)
    if index == limit and len(left) == len(right):
        return None
    return {
        "character_index": index,
        "source_context": left[max(0, index - radius) : min(len(left), index + radius)],
        "revised_context": right[max(0, index - radius) : min(len(right), index + radius)],
        "source_length": len(left),
        "revised_length": len(right),
    }


def _story_parts(parts: dict[str, bytes]) -> list[str]:
    auxiliary = [
        name
        for name in parts
        if re.fullmatch(r"word/(?:header|footer)\d+\.xml", name)
    ]
    return sorted([name for name in CORE_STORY_PARTS if name in parts] + auxiliary)


def _text_maps(parts: dict[str, bytes], names: set[str]) -> dict[str, dict[str, Any]]:
    result = {}
    for name in sorted(names):
        if name not in parts:
            continue
        text = extract_visible_text(parts[name], name)
        result[name] = {
            "sha256": sha256_bytes(text.encode("utf-8")),
            "characters": len(text),
            "text": text,
        }
    return result


def _attributes(element: ET.Element, *, include: set[str] | None = None) -> tuple[tuple[str, str], ...]:
    rows = []
    for key, value in element.attrib.items():
        local = _local(key)
        if include is None or local in include:
            rows.append((local, value))
    return tuple(sorted(rows))


def _semantic_tree(element: ET.Element) -> tuple | None:
    """Canonical content/structure tree with formatting and comment markup removed."""
    local = _local(element.tag)
    namespace = _namespace(element.tag)
    if namespace == W and local in IGNORED_SEMANTIC_TAGS:
        return None
    children = tuple(value for child in element for value in [_semantic_tree(child)] if value is not None)
    text = element.text or "" if local in {"t", "delText", "instrText"} else ""
    semantic_attributes: tuple[tuple[str, str], ...] = ()
    if namespace == W and local in {
        "footnoteReference",
        "endnoteReference",
        "bookmarkStart",
        "bookmarkEnd",
        "hyperlink",
        "fldChar",
        "fldSimple",
        "gridSpan",
        "vMerge",
        "drawing",
        "object",
        "sym",
    }:
        semantic_attributes = _attributes(element)
    elif namespace == M:
        semantic_attributes = _attributes(element)
    if not children and not text and not semantic_attributes and local not in {"oMath", "oMathPara"}:
        return None
    return (namespace, local, semantic_attributes, text, children)


def _semantic_digest(value: Any) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _revision_signature(root: ET.Element) -> list[dict[str, Any]]:
    rows = []
    for element in root.iter():
        if _namespace(element.tag) != W or _local(element.tag) not in REVISION_TAGS:
            continue
        contents = []
        for child in element.iter():
            if _local(child.tag) in {"t", "delText", "instrText"}:
                contents.append(child.text or "")
        rows.append(
            {
                "tag": _local(element.tag),
                "attributes": list(_attributes(element)),
                "text_sha256": _semantic_digest(contents),
            }
        )
    return rows


def _math_signature(root: ET.Element) -> list[str]:
    signatures = []
    for element in root.iter():
        if _namespace(element.tag) == M and _local(element.tag) in {"oMath", "oMathPara"}:
            signatures.append(_semantic_digest(_semantic_tree(element)))
    return signatures


def _reference_signature(root: ET.Element) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {
        "footnote_references": [],
        "endnote_references": [],
        "bookmarks": [],
        "bookmark_ends": [],
        "internal_hyperlinks": [],
        "drawing_relationship_ids": [],
    }
    for element in root.iter():
        local = _local(element.tag)
        if local == "footnoteReference":
            result["footnote_references"].append(dict(_attributes(element)))
        elif local == "endnoteReference":
            result["endnote_references"].append(dict(_attributes(element)))
        elif local == "bookmarkStart":
            result["bookmarks"].append(dict(_attributes(element)))
        elif local == "bookmarkEnd":
            result["bookmark_ends"].append(dict(_attributes(element)))
        elif local == "hyperlink" and element.get(f"{{{W}}}anchor"):
            result["internal_hyperlinks"].append(dict(_attributes(element)))
        for attribute, value in element.attrib.items():
            if _namespace(attribute) == R and _local(attribute) in {"id", "embed", "link"}:
                result["drawing_relationship_ids"].append(
                    {"element": local, "attribute": _local(attribute), "value": value}
                )
    return result


def _field_signature(root: ET.Element) -> list[dict[str, Any]]:
    rows = []
    for element in root.iter():
        local = _local(element.tag)
        if local == "instrText":
            rows.append({"kind": local, "instruction": element.text or ""})
        elif local == "fldSimple":
            rows.append({"kind": local, "instruction": element.get(f"{{{W}}}instr", "")})
        elif local == "fldChar":
            rows.append({"kind": local, "attributes": list(_attributes(element))})
    return rows


def _visibility_and_identity_signature(root: ET.Element) -> list[dict[str, Any]]:
    rows = []
    for paragraph in root.iter(f"{{{W}}}p"):
        p_pr = paragraph.find(f"{{{W}}}pPr")
        style_id = None
        numbering = None
        if p_pr is not None:
            style = p_pr.find(f"{{{W}}}pStyle")
            style_id = style.get(f"{{{W}}}val") if style is not None else None
            num_pr = p_pr.find(f"{{{W}}}numPr")
            if num_pr is not None:
                numbering = [
                    (_local(child.tag), child.get(f"{{{W}}}val", ""))
                    for child in num_pr
                ]
        run_flags = []
        for run_index, run in enumerate(paragraph.iter(f"{{{W}}}r")):
            r_pr = run.find(f"{{{W}}}rPr")
            if r_pr is None:
                continue
            flags = []
            for local in ("vanish", "specVanish", "webHidden", "position", "vertAlign"):
                element = r_pr.find(f"{{{W}}}{local}")
                if element is not None:
                    flags.append((local, element.get(f"{{{W}}}val", "1")))
            if flags:
                run_flags.append((run_index, flags))
        rows.append({"style_id": style_id, "numbering": numbering, "run_semantic_flags": run_flags})
    return rows


def _note_definition_signature(root: ET.Element, kind: str) -> list[dict[str, Any]]:
    rows = []
    for note in root.findall(f"{{{W}}}{kind}"):
        rows.append(
            {
                "id": note.get(f"{{{W}}}id", ""),
                "type": note.get(f"{{{W}}}type", "normal"),
                "text_sha256": sha256_bytes(
                    extract_visible_text(ET.tostring(note), f"{kind} definition").encode("utf-8")
                ),
            }
        )
    return rows


def _table_signature(root: ET.Element) -> list[str]:
    rows = []
    for table in root.iter(f"{{{W}}}tbl"):
        table_rows = []
        for row in table.findall(f"{{{W}}}tr"):
            cells = []
            for cell in row.findall(f"{{{W}}}tc"):
                tc_pr = cell.find(f"{{{W}}}tcPr")
                span = None
                merge = None
                if tc_pr is not None:
                    span_element = tc_pr.find(f"{{{W}}}gridSpan")
                    merge_element = tc_pr.find(f"{{{W}}}vMerge")
                    span = span_element.get(f"{{{W}}}val", "1") if span_element is not None else None
                    merge = merge_element.get(f"{{{W}}}val", "continue") if merge_element is not None else None
                cells.append(
                    {
                        "grid_span": span,
                        "vertical_merge": merge,
                        "text_sha256": sha256_bytes(
                            extract_visible_text(ET.tostring(cell), "table cell").encode("utf-8")
                        ),
                    }
                )
            table_rows.append(cells)
        rows.append(_semantic_digest(table_rows))
    return rows


def _story_semantics(parts: dict[str, bytes], names: set[str]) -> dict[str, dict[str, Any]]:
    result = {}
    for name in sorted(names):
        if name not in parts:
            continue
        root = _parse_xml(parts[name], name)
        row: dict[str, Any] = {
            "references": _reference_signature(root),
            "fields": _field_signature(root),
            "visibility_and_identity": _visibility_and_identity_signature(root),
            "tracked_changes": _revision_signature(root),
            "math": _math_signature(root),
            "tables": _table_signature(root),
        }
        if name == "word/footnotes.xml":
            row["note_definitions"] = _note_definition_signature(root, "footnote")
        elif name == "word/endnotes.xml":
            row["note_definitions"] = _note_definition_signature(root, "endnote")
        result[name] = row
    return result


def _relationship_map(parts: dict[str, bytes], *, include_comments: bool) -> list[dict[str, str]]:
    rows = []
    for name, data in sorted(parts.items()):
        if not name.endswith(".rels"):
            continue
        root = _parse_xml(data, name)
        for rel in root.findall(f"{{{PR}}}Relationship"):
            rel_type = rel.get("Type", "")
            if not include_comments and rel_type.endswith(COMMENT_REL_SUFFIXES):
                continue
            rows.append(
                {
                    "part": name,
                    "id": rel.get("Id", ""),
                    "type": rel_type,
                    "target": rel.get("Target", ""),
                    "target_mode": rel.get("TargetMode", "Internal"),
                }
            )
    return rows


def _content_types(parts: dict[str, bytes], *, include_comments: bool) -> list[dict[str, str]]:
    root = _parse_xml(parts["[Content_Types].xml"], "[Content_Types].xml")
    rows = []
    for element in root:
        row = {"kind": _local(element.tag), **dict(sorted(element.attrib.items()))}
        if not include_comments and "comments" in row.get("PartName", "").lower():
            continue
        rows.append(row)
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))


def _comment_map(parts: dict[str, bytes]) -> dict[str, str]:
    if "word/comments.xml" not in parts:
        return {}
    root = _parse_xml(parts["word/comments.xml"], "word/comments.xml")
    def canonical(element: ET.Element) -> tuple:
        return (
            _namespace(element.tag),
            _local(element.tag),
            tuple(sorted((_namespace(key), _local(key), value) for key, value in element.attrib.items())),
            element.text or "",
            tuple(canonical(child) for child in element),
        )

    result = {}
    for element in root.findall(f"{{{W}}}comment"):
        comment_id = element.get(f"{{{W}}}id", "")
        result[comment_id] = _semantic_digest(canonical(element))
    return result


def _opaque_part_map(parts: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    story_names = set(_story_parts(parts))
    result = {}
    for name, data in sorted(parts.items()):
        lower = name.lower()
        if name in FORMAT_OR_METADATA_PARTS or name in story_names or name.endswith(".rels"):
            continue
        if name in COMMENT_PART_PREFIXES or lower.startswith("word/comments"):
            continue
        result[name] = {"sha256": sha256_bytes(data), "bytes": len(data)}
    return result


def _map_differences(source: dict, revised: dict) -> list[dict[str, Any]]:
    return [
        {"part": name, "source": source.get(name), "revised": revised.get(name)}
        for name in sorted(set(source) | set(revised))
        if source.get(name) != revised.get(name)
    ]


def compare_documents(
    source: Path,
    revised: Path,
    *,
    allow_header_footer_change: bool = False,
    approved_header_footer_parts: set[str] | None = None,
    allow_comment_additions: bool = False,
) -> dict[str, Any]:
    try:
        source_parts, _, source_security = read_docx_package(source)
        revised_parts, _, revised_security = read_docx_package(revised)
    except PackageSafetyError as exc:
        raise GuardError(str(exc)) from exc

    source_story_names = set(_story_parts(source_parts))
    revised_story_names = set(_story_parts(revised_parts))
    story_names = source_story_names | revised_story_names
    source_text = _text_maps(source_parts, story_names)
    revised_text = _text_maps(revised_parts, story_names)
    approved = set(approved_header_footer_parts or set())
    if allow_header_footer_change:
        approved.update(
            name for name in story_names if re.fullmatch(r"word/(?:header|footer)\d+\.xml", name)
        )

    text_differences = []
    unapproved_text_differences = []
    for name in sorted(story_names):
        left = source_text.get(name, {}).get("text", "")
        right = revised_text.get(name, {}).get("text", "")
        difference = _first_difference(left, right)
        if difference or (name in source_text) != (name in revised_text):
            row = {"part": name, **(difference or {"part_presence_changed": True})}
            text_differences.append(row)
            if name not in approved:
                unapproved_text_differences.append(row)

    source_semantics = _story_semantics(source_parts, story_names)
    revised_semantics = _story_semantics(revised_parts, story_names)
    semantic_differences = _map_differences(source_semantics, revised_semantics)

    source_relationships = _relationship_map(source_parts, include_comments=False)
    revised_relationships = _relationship_map(revised_parts, include_comments=False)
    relationships_changed = source_relationships != revised_relationships

    source_content_types = _content_types(source_parts, include_comments=False)
    revised_content_types = _content_types(revised_parts, include_comments=False)
    content_types_changed = source_content_types != revised_content_types

    source_opaque = _opaque_part_map(source_parts)
    revised_opaque = _opaque_part_map(revised_parts)
    opaque_differences = _map_differences(source_opaque, revised_opaque)

    source_comments = _comment_map(source_parts)
    revised_comments = _comment_map(revised_parts)
    if allow_comment_additions:
        comment_differences = [
            {"comment_id": key, "source": value, "revised": revised_comments.get(key)}
            for key, value in sorted(source_comments.items())
            if revised_comments.get(key) != value
        ]
        removed_comment_ids = sorted(set(source_comments) - set(revised_comments))
        added_comment_ids = sorted(set(revised_comments) - set(source_comments))
    else:
        comment_differences = _map_differences(source_comments, revised_comments)
        removed_comment_ids = sorted(set(source_comments) - set(revised_comments))
        added_comment_ids = sorted(set(revised_comments) - set(source_comments))

    failures = []
    if unapproved_text_differences:
        failures.append("visible story text changed")
    if semantic_differences:
        failures.append("semantic OOXML structure changed")
    if relationships_changed:
        failures.append("non-comment relationship mapping changed")
    if content_types_changed:
        failures.append("non-comment content types changed")
    if opaque_differences:
        failures.append("opaque or binary package parts changed")
    if comment_differences or removed_comment_ids or (added_comment_ids and not allow_comment_additions):
        failures.append("comments were changed outside the selected comment policy")

    def public_text(mapping: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {name: {k: v for k, v in row.items() if k != "text"} for name, row in mapping.items()}

    return {
        "status": "FAIL" if failures else "PASS",
        "scope": "FORMAT_ONLY_CONTENT_GUARD_V2",
        "failures": failures,
        "source": str(source.resolve()),
        "revised": str(revised.resolve()),
        "source_file_sha256": sha256_file(source),
        "revised_file_sha256": sha256_file(revised),
        "package_security": {"source": source_security, "revised": revised_security},
        "visible_text": {
            "source": public_text(source_text),
            "revised": public_text(revised_text),
            "differences": text_differences,
            "unapproved_differences": unapproved_text_differences,
            "approved_header_footer_parts": sorted(approved),
            "blanket_header_footer_switch_used": allow_header_footer_change,
        },
        "semantic_structures": {
            "source": source_semantics,
            "revised": revised_semantics,
            "differences": semantic_differences,
        },
        "relationships": {
            "source": source_relationships,
            "revised": revised_relationships,
            "changed": relationships_changed,
        },
        "content_types": {"changed": content_types_changed},
        "opaque_parts": {
            "source": source_opaque,
            "revised": revised_opaque,
            "differences": opaque_differences,
        },
        "comments": {
            "policy": "ALLOW_ADDITIONS_PRESERVE_EXISTING" if allow_comment_additions else "PRESERVE_EXACT",
            "added_ids": added_comment_ids,
            "removed_ids": removed_comment_ids,
            "differences": comment_differences,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("revised", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--approved-header-footer-part",
        action="append",
        default=[],
        help="Approve one exact OOXML header/footer part, for example word/header1.xml",
    )
    parser.add_argument(
        "--allow-header-footer-change",
        action="store_true",
        help="Deprecated blanket approval; prefer --approved-header-footer-part",
    )
    parser.add_argument(
        "--allow-comment-additions",
        action="store_true",
        help="Allow new comments while requiring all source comments to remain byte-identical",
    )
    args = parser.parse_args()
    try:
        result = compare_documents(
            args.source,
            args.revised,
            allow_header_footer_change=args.allow_header_footer_change,
            approved_header_footer_parts=set(args.approved_header_footer_part),
            allow_comment_additions=args.allow_comment_additions,
        )
    except (GuardError, OSError) as exc:
        result = {"status": "ERROR", "error": str(exc)}
        exit_code = 1
    else:
        exit_code = 0 if result["status"] == "PASS" else 2
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

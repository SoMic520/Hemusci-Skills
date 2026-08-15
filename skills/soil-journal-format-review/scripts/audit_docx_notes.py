#!/usr/bin/env python3
"""Audit DOCX footnote/endnote mappings and format-relevant note properties."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from ooxml_safety import PackageSafetyError, read_docx_package, sha256_bytes

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def qn(local: str) -> str:
    return f"{{{W}}}{local}"


def paragraph_text(paragraph: ET.Element) -> str:
    chunks = []
    for element in paragraph.iter():
        if element.tag == qn("t"):
            chunks.append(element.text or "")
        elif element.tag == qn("tab"):
            chunks.append("\t")
        elif element.tag in {qn("br"), qn("cr")}:
            chunks.append("\n")
    return "".join(chunks)


def _properties(element: ET.Element | None) -> dict[str, Any]:
    if element is None:
        return {}
    return {
        child.tag.rsplit("}", 1)[-1]: {
            key.rsplit("}", 1)[-1]: value for key, value in sorted(child.attrib.items())
        }
        for child in element
    }


def _reference_rows(document: ET.Element, kind: str) -> list[dict[str, Any]]:
    rows = []
    paragraph_number = -1
    for paragraph_number, paragraph in enumerate(document.iter(qn("p"))):
        for reference in paragraph.iter(qn(f"{kind}Reference")):
            rows.append(
                {
                    "id": reference.get(qn("id"), ""),
                    "paragraph_index": paragraph_number,
                    "paragraph_text_sha256": sha256_bytes(paragraph_text(paragraph).encode("utf-8")),
                }
            )
    return rows


def _definition_rows(root: ET.Element, kind: str) -> list[dict[str, Any]]:
    rows = []
    for note in root.findall(qn(kind)):
        note_id = note.get(qn("id"), "")
        note_type = note.get(qn("type"), "normal")
        paragraphs = []
        for index, paragraph in enumerate(note.iter(qn("p"))):
            text = paragraph_text(paragraph)
            runs = []
            for run_index, run in enumerate(paragraph.iter(qn("r"))):
                run_text = "".join(item.text or "" for item in run.iter(qn("t")))
                runs.append(
                    {
                        "run_index": run_index,
                        "text_sha256": sha256_bytes(run_text.encode("utf-8")),
                        "properties": _properties(run.find(qn("rPr"))),
                    }
                )
            paragraphs.append(
                {
                    "paragraph_index": index,
                    "text": text,
                    "text_sha256": sha256_bytes(text.encode("utf-8")),
                    "properties": _properties(paragraph.find(qn("pPr"))),
                    "runs": runs,
                }
            )
        rows.append({"id": note_id, "type": note_type, "paragraphs": paragraphs})
    return rows


def audit_notes(path: Path) -> dict[str, Any]:
    parts, _, security = read_docx_package(path)
    document = ET.fromstring(parts["word/document.xml"])
    errors = []
    stories = {}
    for plural, singular in (("footnotes", "footnote"), ("endnotes", "endnote")):
        part_name = f"word/{plural}.xml"
        references = _reference_rows(document, singular)
        definitions = _definition_rows(ET.fromstring(parts[part_name]), singular) if part_name in parts else []
        reference_ids = [row["id"] for row in references]
        normal_definition_ids = [row["id"] for row in definitions if row["type"] == "normal"]
        definition_counts = Counter(normal_definition_ids)
        missing = sorted(set(reference_ids) - set(normal_definition_ids))
        orphan = sorted(set(normal_definition_ids) - set(reference_ids))
        duplicate_definitions = sorted(key for key, count in definition_counts.items() if count > 1)
        if missing:
            errors.append(f"{plural}: referenced IDs have no normal definition: {missing}")
        if orphan:
            errors.append(f"{plural}: normal definitions are not referenced: {orphan}")
        if duplicate_definitions:
            errors.append(f"{plural}: duplicate normal definition IDs: {duplicate_definitions}")
        stories[plural] = {
            "part_present": part_name in parts,
            "references": references,
            "definitions": definitions,
            "separator_ids": sorted(
                row["id"] for row in definitions if row["type"] in {"separator", "continuationSeparator"}
            ),
            "missing_definition_ids": missing,
            "orphan_definition_ids": orphan,
            "duplicate_definition_ids": duplicate_definitions,
        }
    return {
        "status": "FAIL" if errors else "PASS",
        "scope": "NOTE_STRUCTURE_AND_FORMAT_AUDIT",
        "file": str(path.resolve()),
        "package_security": security,
        "stories": stories,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        result = audit_notes(args.docx)
    except (OSError, PackageSafetyError, ET.ParseError) as exc:
        result = {"status": "ERROR", "errors": [str(exc)]}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())

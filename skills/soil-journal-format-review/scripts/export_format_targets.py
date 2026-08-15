#!/usr/bin/env python3
"""Export exact target indices and fingerprints for a v2 DOCX format plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from apply_docx_format import _paragraph_text, _run_text, _section_hash, _sha_text, _table_structure_hash, qn
from ooxml_safety import PackageSafetyError, read_docx_package, sha256_file

STORY_PARTS = {
    "document": ("word/document.xml", None),
    "footnotes": ("word/footnotes.xml", "footnote"),
    "endnotes": ("word/endnotes.xml", "endnote"),
}


def _scope_record(root: ET.Element, story: str, note_id: str | None) -> dict:
    paragraphs = list(root.iter(qn("p")))
    tables = list(root.iter(qn("tbl")))
    return {
        "story": story,
        "note_id": note_id,
        "paragraphs": [
            {
                "paragraph_index": index,
                "characters": len(_paragraph_text(paragraph)),
                "expected_text_sha256": _sha_text(_paragraph_text(paragraph)),
                "runs": [
                    {
                        "run_index": run_index,
                        "characters": len(_run_text(run)),
                        "expected_run_text_sha256": _sha_text(_run_text(run)),
                    }
                    for run_index, run in enumerate(paragraph.iter(qn("r")))
                ],
            }
            for index, paragraph in enumerate(paragraphs)
        ],
        "tables": [
            {"table_index": index, "expected_structure_sha256": _table_structure_hash(table)}
            for index, table in enumerate(tables)
        ],
    }


def export_targets(path: Path) -> dict:
    parts, _, security = read_docx_package(path)
    scopes = []
    for story, (part_name, singular) in STORY_PARTS.items():
        if part_name not in parts:
            continue
        root = ET.fromstring(parts[part_name])
        if singular is None:
            record = _scope_record(root, story, None)
            record["sections"] = [
                {"section_index": index, "expected_structure_sha256": _section_hash(section)}
                for index, section in enumerate(root.iter(qn("sectPr")))
            ]
            scopes.append(record)
            continue
        for note in root.findall(qn(singular)):
            if note.get(qn("type"), "normal") != "normal":
                continue
            scopes.append(_scope_record(note, story, note.get(qn("id"))))
    return {
        "status": "PASS",
        "scope": "FORMAT_TARGET_FINGERPRINTS",
        "document": str(path.resolve()),
        "source_document_sha256": sha256_file(path),
        "package_security": security,
        "targets": scopes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        result = export_targets(args.docx)
    except (OSError, ValueError, PackageSafetyError, ET.ParseError) as exc:
        result = {"status": "ERROR", "error": str(exc)}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())

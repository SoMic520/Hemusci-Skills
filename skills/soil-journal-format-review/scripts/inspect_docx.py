#!/usr/bin/env python3
"""Create a safe, dependency-free structural inventory of a DOCX manuscript."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from ooxml_safety import PackageSafetyError, read_docx_package, sha256_file

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"


def qn(local: str) -> str:
    return f"{{{W}}}{local}"


def val(element: ET.Element | None, attribute: str = "val") -> str | None:
    return None if element is None else element.get(qn(attribute))


def paragraph_text(paragraph: ET.Element) -> str:
    chunks: list[str] = []
    for element in paragraph.iter():
        if element.tag in {qn("t"), "{http://schemas.openxmlformats.org/officeDocument/2006/math}t"}:
            chunks.append(element.text or "")
        elif element.tag == qn("tab"):
            chunks.append("\t")
        elif element.tag in {qn("br"), qn("cr")}:
            chunks.append("\n")
    return "".join(chunks)


def parse_xml(parts: dict[str, bytes], name: str) -> ET.Element | None:
    return ET.fromstring(parts[name]) if name in parts else None


def section_record(section: ET.Element, index: int) -> dict[str, Any]:
    page = section.find(qn("pgSz"))
    margins = section.find(qn("pgMar"))
    columns = section.find(qn("cols"))
    line_numbers = section.find(qn("lnNumType"))
    return {
        "index": index,
        "page_twips": {"width": val(page, "w"), "height": val(page, "h"), "orientation": val(page, "orient") or "portrait"},
        "margins_twips": {key: val(margins, key) for key in ("top", "right", "bottom", "left", "header", "footer", "gutter")},
        "columns": {"count": val(columns, "num") or "1", "space": val(columns, "space")},
        "line_numbering": None if line_numbers is None else {
            key: val(line_numbers, key) for key in ("countBy", "start", "distance", "restart")
        },
    }


def inspect(path: Path, include_previews: bool = False) -> dict[str, Any]:
    parts, _, security = read_docx_package(path)
    names = list(parts)
    document = parse_xml(parts, "word/document.xml")
    if document is None:
        raise ValueError("word/document.xml is missing")
    paragraphs = list(document.iter(qn("p")))
    style_counts: Counter[str] = Counter()
    paragraph_map = []
    direct_paragraph_formatting = 0
    direct_run_formatting = 0
    empty_paragraphs = 0
    for index, paragraph in enumerate(paragraphs):
        text = paragraph_text(paragraph)
        p_pr = paragraph.find(qn("pPr"))
        p_style = p_pr.find(qn("pStyle")) if p_pr is not None else None
        style = val(p_style) or "(none)"
        style_counts[style] += 1
        if p_pr is not None and any(child.tag != qn("pStyle") for child in p_pr):
            direct_paragraph_formatting += 1
        direct_run_formatting += sum(1 for run in paragraph.iter(qn("r")) if run.find(qn("rPr")) is not None)
        if not text:
            empty_paragraphs += 1
        record: dict[str, Any] = {
            "index": index,
            "style": style,
            "characters": len(text),
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
        if include_previews:
            record["preview"] = text[:120]
        paragraph_map.append(record)

    comments_root = parse_xml(parts, "word/comments.xml")
    comment_ids = (
        [element.get(qn("id")) for element in comments_root.findall(qn("comment"))]
        if comments_root is not None else []
    )
    style_root = parse_xml(parts, "word/styles.xml")
    style_inventory = []
    if style_root is not None:
        for style in style_root.findall(qn("style")):
            style_inventory.append(
                {
                    "style_id": style.get(qn("styleId")),
                    "type": style.get(qn("type")),
                    "name": val(style.find(qn("name"))),
                    "based_on": val(style.find(qn("basedOn"))),
                }
            )
    revisions = {
        "insertions": sum(1 for _ in document.iter(qn("ins"))),
        "deletions": sum(1 for _ in document.iter(qn("del"))),
        "moves_from": sum(1 for _ in document.iter(qn("moveFrom"))),
        "moves_to": sum(1 for _ in document.iter(qn("moveTo"))),
        "paragraph_property_changes": sum(1 for _ in document.iter(qn("pPrChange"))),
        "run_property_changes": sum(1 for _ in document.iter(qn("rPrChange"))),
        "table_property_changes": sum(1 for _ in document.iter(qn("tblPrChange"))),
    }
    return {
        "status": "PASS",
        "scope": "STRUCTURAL_FORMAT_INSPECTION",
        "file": str(path.resolve()),
        "file_sha256": sha256_file(path),
        "package_security": security,
        "package_parts": len(names),
        "paragraphs": len(paragraphs),
        "empty_paragraphs": empty_paragraphs,
        "tables": sum(1 for _ in document.iter(qn("tbl"))),
        "drawings": sum(1 for _ in document.iter(qn("drawing"))),
        "legacy_drawings": sum(1 for _ in document.iter(qn("pict"))),
        "inline_drawings": sum(1 for _ in document.iter(f"{{{WP}}}inline")),
        "floating_drawings": sum(1 for _ in document.iter(f"{{{WP}}}anchor")),
        "page_breaks": sum(1 for element in document.iter(qn("br")) if element.get(qn("type")) == "page"),
        "sections": [section_record(element, index) for index, element in enumerate(document.iter(qn("sectPr")))],
        "headers": sorted(name for name in names if re_name(name, "header")),
        "footers": sorted(name for name in names if re_name(name, "footer")),
        "media": sorted(name for name in names if name.startswith("word/media/")),
        "embeddings": sorted(name for name in names if name.startswith("word/embeddings/")),
        "charts": sorted(name for name in names if name.startswith("word/charts/") and name.endswith(".xml")),
        "comments": {
            "count": len(comment_ids),
            "ids": comment_ids,
            "range_starts": sum(1 for _ in document.iter(qn("commentRangeStart"))),
            "range_ends": sum(1 for _ in document.iter(qn("commentRangeEnd"))),
            "references": sum(1 for _ in document.iter(qn("commentReference"))),
        },
        "revisions": revisions,
        "paragraph_style_usage": dict(style_counts.most_common()),
        "direct_paragraph_formatting": direct_paragraph_formatting,
        "direct_run_formatting": direct_run_formatting,
        "styles": style_inventory,
        "paragraph_map": paragraph_map,
    }


def re_name(name: str, kind: str) -> bool:
    import re

    return bool(re.fullmatch(rf"word/{kind}\d+\.xml", name))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--include-previews", action="store_true")
    args = parser.parse_args()
    try:
        result = inspect(args.docx, args.include_previews)
    except (FileNotFoundError, ValueError, PackageSafetyError, ET.ParseError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())

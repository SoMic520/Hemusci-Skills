#!/usr/bin/env python3
"""Validate a Chinese soil-science technical-bid DOCX in standalone Skill mode."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree as ET


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
EXPECTED_PAGE = (11906, 16838)
EXPECTED_MARGINS = {"top": 1417, "bottom": 1417, "left": 1587, "right": 1247}
EXPECTED_BODY = {"size": 21, "line": 360, "firstLine": 420, "after": 120}
APPROVED_BODY_FONTS = {"宋体", "SimSun", "Songti SC", "STSong", "Noto Serif CJK SC"}
APPROVED_HEADING_FONTS = {"黑体", "SimHei", "Heiti SC", "STHeiti", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC"}
APPROVED_LATIN_FONT = "Times New Roman"
REQUIRED_TEXT = [
    "农业生产符合性评价",
    "耕地质量等级评价",
    "质量鉴定结果",
    "不替代主管部门",
    "GB/T 33469-2016",
    "NY/T 2626-2014",
]
CHAT_RESIDUE = [
    r"希望这对您有帮助", r"如果您需要我", r"作为(?:一个)?AI", r"当然[！!]",
    r"您说得(?:完全)?正确", r"根据我(?:的)?训练", r"知识截止",
    r"turn\d+(?:search|view)\d+", r":codex-file-citation",
]


def int_attr(element: ET.Element, name: str) -> int | None:
    value = element.attrib.get(W + name)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def xml_from(archive: zipfile.ZipFile, name: str) -> ET.Element:
    return ET.fromstring(archive.read(name))


def all_text(root: ET.Element) -> str:
    return "".join(node.text or "" for node in root.iter(W + "t"))


def validate(path: Path, allow_placeholders: bool) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, int] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                return [f"corrupt archive member: {bad}"], warnings, metrics
            names = set(archive.namelist())
            required_members = {"word/document.xml", "word/styles.xml", "word/settings.xml", "word/_rels/document.xml.rels"}
            for member in sorted(required_members - names):
                errors.append(f"missing DOCX member: {member}")
            if errors:
                return errors, warnings, metrics
            document = xml_from(archive, "word/document.xml")
            styles = xml_from(archive, "word/styles.xml")
            settings = xml_from(archive, "word/settings.xml")
            text = all_text(document)
            for name in names:
                if name.startswith("word/header") and name.endswith(".xml"):
                    text += all_text(xml_from(archive, name))
                if name.startswith("word/footer") and name.endswith(".xml"):
                    text += all_text(xml_from(archive, name))

            metrics["characters"] = len(text)
            metrics["tables"] = len(document.findall(".//" + W + "tbl"))
            metrics["headings"] = sum(
                1 for node in document.findall(".//" + W + "pStyle")
                if node.attrib.get(W + "val", "").casefold().replace(" ", "") in {
                    "heading1", "heading2", "heading3", "soilheading1", "soilheading2", "soilheading3"
                }
            )
            metrics["body_paragraphs"] = sum(
                1 for node in document.findall(".//" + W + "pStyle")
                if node.attrib.get(W + "val", "") == "SoilBody"
            )
            metrics["toc_entries"] = sum(
                1 for node in document.findall(".//" + W + "pStyle")
                if node.attrib.get(W + "val", "") in {"TOC1", "TOC2", "TOC3"}
            )

            placeholders = re.findall(r"【待填：[^】]+】", text)
            metrics["placeholders"] = len(placeholders)
            if placeholders and not allow_placeholders:
                errors.append(f"formal mode forbids {len(placeholders)} unresolved placeholders")
            elif placeholders:
                warnings.append(f"draft contains {len(placeholders)} unresolved placeholders")

            for pattern in CHAT_RESIDUE:
                if re.search(pattern, text, flags=re.IGNORECASE):
                    errors.append(f"chat/tool residue matched: {pattern}")
            for required in REQUIRED_TEXT:
                if required not in text:
                    errors.append(f"missing required technical distinction/source: {required}")
            if "农用地质量等别评定" in text and "不得" not in text:
                errors.append("possible uncontrolled substitution of 耕地质量等级 with 农用地质量等别评定")

            sections = document.findall(".//" + W + "sectPr")
            metrics["sections"] = len(sections)
            if len(sections) < 2:
                errors.append("cover and body must use at least two Word sections")
            for index, section in enumerate(sections, 1):
                size = section.find(W + "pgSz")
                margin = section.find(W + "pgMar")
                if size is None:
                    errors.append(f"section {index} lacks page size")
                else:
                    actual = (int_attr(size, "w"), int_attr(size, "h"))
                    if any(value is None for value in actual) or any(abs(int(actual[i]) - EXPECTED_PAGE[i]) > 8 for i in (0, 1)):
                        errors.append(f"section {index} is not A4 portrait: {actual}")
                if margin is None:
                    errors.append(f"section {index} lacks explicit margins")
                else:
                    for key, expected in EXPECTED_MARGINS.items():
                        actual = int_attr(margin, key)
                        if actual is None or abs(actual - expected) > 12:
                            errors.append(f"section {index} margin {key}={actual}, expected about {expected}")

            def style_node(style_id: str) -> ET.Element | None:
                for style in styles.findall(W + "style"):
                    if style.attrib.get(W + "styleId") == style_id:
                        return style
                return None

            def style_fonts(style_id: str) -> dict[str, str | None]:
                style = style_node(style_id)
                fonts = style.find(".//" + W + "rFonts") if style is not None else None
                return {slot: fonts.attrib.get(W + slot) if fonts is not None else None for slot in ("ascii", "hAnsi", "eastAsia", "cs")}

            body_fonts = style_fonts("SoilBody")
            heading_fonts = style_fonts("SoilHeading1")
            body_font = body_fonts["eastAsia"]
            heading_font = heading_fonts["eastAsia"]
            if body_font not in APPROVED_BODY_FONTS:
                errors.append(f"SoilBody style must use an approved Song/Ming Chinese font; found {body_font}")
            if heading_font not in APPROVED_HEADING_FONTS:
                errors.append(f"SoilHeading1 style must use an approved Hei/Sans Chinese font; found {heading_font}")
            for style_id, slots in (("SoilBody", body_fonts), ("SoilHeading1", heading_fonts)):
                for slot in ("ascii", "hAnsi", "cs"):
                    if slots[slot] != APPROVED_LATIN_FONT:
                        errors.append(f"{style_id} {slot} font must be {APPROVED_LATIN_FONT}; found {slots[slot]}")

            body_style = style_node("SoilBody")
            if body_style is None:
                errors.append("missing SoilBody paragraph style")
            else:
                size = body_style.find(".//" + W + "sz")
                spacing = body_style.find(".//" + W + "spacing")
                indent = body_style.find(".//" + W + "ind")
                actual_size = int_attr(size, "val") if size is not None else None
                actual_line = int_attr(spacing, "line") if spacing is not None else None
                actual_after = int_attr(spacing, "after") if spacing is not None else None
                actual_first_line = int_attr(indent, "firstLine") if indent is not None else None
                for key, actual in (("size", actual_size), ("line", actual_line), ("after", actual_after), ("firstLine", actual_first_line)):
                    expected = EXPECTED_BODY[key]
                    if actual is None or abs(actual - expected) > 8:
                        errors.append(f"SoilBody {key}={actual}, expected about {expected}")

            instructions = " ".join(node.text or "" for node in document.iter(W + "instrText"))
            for name in names:
                if name.startswith("word/footer") and name.endswith(".xml"):
                    root = xml_from(archive, name)
                    instructions += " " + " ".join(node.text or "" for node in root.iter(W + "instrText"))
            if "TOC" not in instructions:
                errors.append("missing Word TOC field")
            if metrics["toc_entries"] < 8:
                errors.append("TOC field lacks sufficient visible cached entries with page numbers")
            if "PAGE" not in instructions:
                errors.append("missing Word PAGE field")
            if settings.find(W + "updateFields") is None:
                warnings.append("settings.xml does not request field update on open")

            header_parts = [name for name in names if name.startswith("word/header") and name.endswith(".xml")]
            footer_parts = [name for name in names if name.startswith("word/footer") and name.endswith(".xml")]
            if not header_parts:
                errors.append("body section lacks a header part")
            if not footer_parts:
                errors.append("body section lacks a footer part")

            if metrics["tables"] < 3:
                errors.append("technical bid must contain at least three genuine data/compliance tables")
            if metrics["headings"] < 8:
                errors.append("technical bid has too few structured headings")
            if metrics["body_paragraphs"] < 8:
                errors.append("technical bid has too few paragraphs using the controlled SoilBody style")

            # Serious Chinese bids default to a plain black-and-white visual system.
            # Decorative fills, text boxes and shapes are rejected unless a future
            # controlled tender profile explicitly enables them.
            for shading in document.findall(".//" + W + "shd"):
                fill = (shading.attrib.get(W + "fill") or "").upper()
                if fill not in {"", "AUTO", "FFFFFF", "NONE"}:
                    errors.append(f"decorative/non-white shading is not allowed in the default bid profile: {fill}")
            drawing_tags = {
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}txbxContent",
                "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor",
                "{urn:schemas-microsoft-com:vml}shape",
                "{urn:schemas-microsoft-com:vml}textbox",
            }
            if any(node.tag in drawing_tags for node in document.iter()):
                errors.append("default bid profile forbids decorative floating shapes and text boxes")

            # The cover ends at the first section property. It must remain plain
            # metadata paragraphs, not a boxed metadata table.
            body = document.find(W + "body")
            if body is not None:
                cover_tables = 0
                for child in body:
                    if child.find(".//" + W + "sectPr") is not None:
                        break
                    if child.tag == W + "tbl":
                        cover_tables += 1
                if cover_tables:
                    errors.append(f"cover contains {cover_tables} boxed table(s); default formal cover must be plain")
            for table_index, table in enumerate(document.findall(".//" + W + "tbl"), 1):
                width = table.find(".//" + W + "tblW")
                if width is None or width.attrib.get(W + "type") != "dxa" or int_attr(width, "w") in {None, 0}:
                    errors.append(f"table {table_index} lacks fixed DXA width")
                for height in table.findall(".//" + W + "trHeight"):
                    if height.attrib.get(W + "hRule") == "exact":
                        errors.append(f"table {table_index} uses exact row height and may clip text")
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        return [f"cannot inspect DOCX: {exc}"], warnings, metrics
    return errors, warnings, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()
    errors, warnings, metrics = validate(args.path, args.allow_placeholders)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print("INFO: " + "; ".join(f"{key}={value}" for key, value in sorted(metrics.items())))
    if errors:
        print(f"FAILED: {len(errors)} technical-bid DOCX error(s)")
        return 1
    print("PASS: Chinese soil-science technical-bid DOCX structure is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

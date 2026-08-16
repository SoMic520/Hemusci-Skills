#!/usr/bin/env python3
"""Validate a generic Chinese soil-science DOCX against its genre artifact profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree as ET


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
EXPECTED_PAGE = (11906, 16838)
EXPECTED_MARGINS = {"top": 1417, "bottom": 1417, "left": 1587, "right": 1247}
SIZE_HALF_POINTS = {
    "初号": 84, "小初号": 72, "一号": 52, "小一号": 48, "二号": 44, "小二号": 36,
    "三号": 32, "小三号": 30, "四号": 28, "小四号": 24, "五号": 21, "小五号": 18,
    "六号": 15, "小六号": 13, "七号": 11, "八号": 10,
}
APPROVED_BODY_FONTS = {"宋体", "SimSun", "Songti SC", "STSong", "Noto Serif CJK SC"}
APPROVED_HEADING_FONTS = {"黑体", "SimHei", "Heiti SC", "STHeiti", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC"}
CHAT_RESIDUE = [
    r"希望这对您有帮助", r"如果您需要我", r"作为(?:一个)?AI", r"当然[！!]",
    r"您说得(?:完全)?正确", r"根据我(?:的)?训练", r"知识截止",
    r"turn\d+(?:search|view)\d+", r":codex-file-citation",
]


def int_attr(element: ET.Element | None, name: str) -> int | None:
    if element is None:
        return None
    value = element.attrib.get(W + name)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def xml_from(archive: zipfile.ZipFile, name: str) -> ET.Element:
    return ET.fromstring(archive.read(name))


def all_text(root: ET.Element) -> str:
    return "".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))


def load_controls(spec_path: Path, profiles_path: Path) -> tuple[dict, dict, dict]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    registry = json.loads(profiles_path.read_text(encoding="utf-8"))
    route = next((item for item in registry.get("genre_routes", []) if item.get("id") == spec.get("genre_profile_id")), None)
    if route is None:
        raise ValueError(f"unknown genre_profile_id: {spec.get('genre_profile_id')}")
    profile = next((item for item in registry.get("format_profiles", []) if item.get("id") == route.get("format_profile_id")), None)
    if profile is None:
        raise ValueError(f"unknown format_profile_id: {route.get('format_profile_id')}")
    if profile.get("artifact_kind") != "docx":
        raise ValueError(f"profile artifact_kind is not docx: {profile.get('artifact_kind')}")
    return spec, route, profile


def validate(
    path: Path,
    spec_path: Path,
    profiles_path: Path,
    allow_placeholders: bool,
) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, int] = {}
    try:
        spec, route, profile = load_controls(spec_path, profiles_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"cannot load controls: {exc}"], warnings, metrics

    expected_body_size = SIZE_HALF_POINTS.get(profile.get("body_size_zh"))
    expected_line = round(240 * float(profile.get("body_line_spacing", 1.5)))
    expected_first_line = round(expected_body_size * 10 * float(profile.get("first_line_indent_characters", 0))) if expected_body_size else None
    expected_after = round(240 * float(profile.get("paragraph_after_lines", 0)))
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                return [f"corrupt archive member: {bad}"], warnings, metrics
            names = set(archive.namelist())
            required = {"word/document.xml", "word/styles.xml", "word/settings.xml", "docProps/core.xml", "word/_rels/document.xml.rels"}
            for member in sorted(required - names):
                errors.append(f"missing DOCX member: {member}")
            if errors:
                return errors, warnings, metrics
            document = xml_from(archive, "word/document.xml")
            styles = xml_from(archive, "word/styles.xml")
            settings = xml_from(archive, "word/settings.xml")
            core = xml_from(archive, "docProps/core.xml")
            text = all_text(document)
            for name in names:
                if (name.startswith("word/header") or name.startswith("word/footer")) and name.endswith(".xml"):
                    text += all_text(xml_from(archive, name))
            metrics["characters"] = len(text)
            metrics["tables"] = len(document.findall(".//" + W + "tbl"))
            metrics["headings"] = sum(
                1 for node in document.findall(".//" + W + "pStyle")
                if node.attrib.get(W + "val", "") in {"SoilHeading1", "SoilHeading2", "SoilHeading3", "SoilHeading4"}
            )
            metrics["body_paragraphs"] = sum(
                1 for node in document.findall(".//" + W + "pStyle")
                if node.attrib.get(W + "val") == "SoilBody"
            )
            metrics["toc_entries"] = sum(
                1 for node in document.findall(".//" + W + "pStyle")
                if node.attrib.get(W + "val") in {"TOC1", "TOC2", "TOC3", "TOC4"}
            )
            placeholders = re.findall(r"【待填：[^】]+】", text)
            metrics["placeholders"] = len(placeholders)
            if placeholders and not allow_placeholders:
                errors.append(f"formal mode forbids {len(placeholders)} unresolved placeholders")
            elif placeholders:
                warnings.append(f"draft contains {len(placeholders)} unresolved placeholders")
            if spec.get("title") not in text:
                errors.append("document text does not contain the controlled title")
            core_text = "".join(node.text or "" for node in core.iter())
            if spec.get("genre_profile_id") not in core_text:
                errors.append("core properties do not identify the genre profile")
            if profile.get("id") not in core_text:
                errors.append("core properties do not identify the format profile")
            for pattern in CHAT_RESIDUE:
                if re.search(pattern, text, flags=re.IGNORECASE):
                    errors.append(f"chat/tool residue matched: {pattern}")

            sections = document.findall(".//" + W + "sectPr")
            metrics["sections"] = len(sections)
            expected_sections = 1 if profile.get("cover_mode") == "none" else 2
            if len(sections) != expected_sections:
                errors.append(f"cover mode {profile.get('cover_mode')} requires {expected_sections} section(s); found {len(sections)}")
            for index, section in enumerate(sections, 1):
                page_size = section.find(W + "pgSz")
                page_margin = section.find(W + "pgMar")
                actual_page = (int_attr(page_size, "w"), int_attr(page_size, "h"))
                if any(value is None for value in actual_page) or any(abs(int(actual_page[i]) - EXPECTED_PAGE[i]) > 8 for i in (0, 1)):
                    errors.append(f"section {index} is not A4 portrait: {actual_page}")
                for key, expected in EXPECTED_MARGINS.items():
                    actual = int_attr(page_margin, key)
                    if actual is None or abs(actual - expected) > 12:
                        errors.append(f"section {index} margin {key}={actual}, expected about {expected}")

            def style_node(style_id: str) -> ET.Element | None:
                return next((node for node in styles.findall(W + "style") if node.attrib.get(W + "styleId") == style_id), None)

            def style_fonts(style_id: str) -> dict[str, str | None]:
                style = style_node(style_id)
                node = style.find(".//" + W + "rFonts") if style is not None else None
                return {slot: node.attrib.get(W + slot) if node is not None else None for slot in ("ascii", "hAnsi", "eastAsia", "cs")}

            body_style = style_node("SoilBody")
            if body_style is None:
                errors.append("missing SoilBody style")
            else:
                actual_size = int_attr(body_style.find(".//" + W + "sz"), "val")
                spacing = body_style.find(".//" + W + "spacing")
                indent = body_style.find(".//" + W + "ind")
                expected_values = {
                    "size": expected_body_size,
                    "line": expected_line,
                    "after": expected_after,
                    "firstLine": expected_first_line,
                }
                actual_values = {
                    "size": actual_size,
                    "line": int_attr(spacing, "line"),
                    "after": int_attr(spacing, "after"),
                    "firstLine": int_attr(indent, "firstLine"),
                }
                for key, expected in expected_values.items():
                    if expected is None or actual_values[key] is None or abs(actual_values[key] - expected) > 8:
                        errors.append(f"SoilBody {key}={actual_values[key]}, expected about {expected}")

            body_fonts = style_fonts("SoilBody")
            heading_fonts = style_fonts("SoilHeading1")
            if body_fonts["eastAsia"] not in APPROVED_BODY_FONTS:
                errors.append(f"SoilBody requires a Song/Ming font; found {body_fonts['eastAsia']}")
            if heading_fonts["eastAsia"] not in APPROVED_HEADING_FONTS:
                errors.append(f"SoilHeading1 requires a Hei/Sans font; found {heading_fonts['eastAsia']}")
            for style_id, slots in (("SoilBody", body_fonts), ("SoilHeading1", heading_fonts)):
                for slot in ("ascii", "hAnsi", "cs"):
                    if slots[slot] != "Times New Roman":
                        errors.append(f"{style_id} {slot} must use Times New Roman; found {slots[slot]}")

            instructions = " ".join(node.text or "" for node in document.iter(W + "instrText"))
            for name in names:
                if name.startswith("word/footer") and name.endswith(".xml"):
                    footer = xml_from(archive, name)
                    instructions += " " + " ".join(node.text or "" for node in footer.iter(W + "instrText"))
            if spec.get("include_toc") and "TOC" not in instructions:
                errors.append("requested TOC field is missing")
            expected_toc_entries = sum(1 for block in spec.get("content", []) if block.get("type") == "heading")
            if spec.get("include_toc") and metrics["toc_entries"] < expected_toc_entries:
                errors.append(
                    f"TOC has {metrics['toc_entries']} visible cached entries; expected at least {expected_toc_entries}"
                )
            if not spec.get("include_toc") and "TOC" in instructions:
                errors.append("unexpected TOC field")
            footer_expected = profile.get("header_footer_mode") not in {"none_unless_controlled_source_requires", "event_controlled"}
            if footer_expected and "PAGE" not in instructions:
                errors.append("profile requires a PAGE field")
            if not footer_expected and "PAGE" in instructions and spec.get("controlled_template", {}).get("state") != "received_locked":
                errors.append("uncontrolled PAGE field conflicts with the profile")
            if settings.find(W + "updateFields") is None:
                warnings.append("settings.xml does not request field updates")

            if profile.get("decorative_shading_allowed") is False:
                for shading in document.findall(".//" + W + "shd"):
                    fill = (shading.attrib.get(W + "fill") or "").upper()
                    if fill not in {"", "AUTO", "FFFFFF", "NONE"}:
                        errors.append(f"non-white shading is forbidden by the fallback profile: {fill}")
            drawing_tags = {
                W + "txbxContent",
                "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}anchor",
                "{urn:schemas-microsoft-com:vml}shape",
                "{urn:schemas-microsoft-com:vml}textbox",
            }
            if profile.get("decorative_frames_allowed") is False and any(node.tag in drawing_tags for node in document.iter()):
                errors.append("decorative floating shapes or text boxes are forbidden")

            body = document.find(W + "body")
            if body is not None and profile.get("cover_mode") in {"formal_black_white", "title_page_only"}:
                cover_tables = 0
                for child in body:
                    if child.find(".//" + W + "sectPr") is not None:
                        break
                    if child.tag == W + "tbl":
                        cover_tables += 1
                if cover_tables:
                    errors.append(f"plain title/cover page contains {cover_tables} boxed table(s)")
            for table_index, table in enumerate(document.findall(".//" + W + "tbl"), 1):
                width = table.find(".//" + W + "tblW")
                if width is None or width.attrib.get(W + "type") != "dxa" or int_attr(width, "w") in {None, 0}:
                    errors.append(f"table {table_index} lacks a fixed DXA width")
                for height in table.findall(".//" + W + "trHeight"):
                    if height.attrib.get(W + "hRule") == "exact":
                        errors.append(f"table {table_index} uses an exact row height")

            if spec.get("lifecycle_stage") == "release":
                roles = {block.get("role") for block in spec.get("content", []) if block.get("role")}
                missing_roles = [role for role in route.get("required_roles", []) if role not in roles]
                if missing_roles:
                    errors.append(f"release missing required roles: {', '.join(missing_roles)}")
                if route.get("controlled_template_required_for_release"):
                    controlled = spec.get("controlled_template", {})
                    if controlled.get("state") != "received_locked" or not re.fullmatch(r"[0-9a-fA-F]{64}", controlled.get("snapshot_sha256", "")):
                        errors.append("release requires a locked controlled template")
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        return [f"cannot inspect DOCX: {exc}"], warnings, metrics
    return errors, warnings, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()
    errors, warnings, metrics = validate(args.path, args.spec, args.profiles, args.allow_placeholders)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print("INFO: " + "; ".join(f"{key}={value}" for key, value in sorted(metrics.items())))
    if errors:
        print(f"FAILED: {len(errors)} professional-DOCX error(s)")
        return 1
    print("PASS: Chinese soil-science professional DOCX matches its fallback artifact profile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate soil-science poster/slide PPTX output against its visual profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import zipfile
from xml.etree import ElementTree as ET


A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
EXPECTED_SIZES = {
    "pptx_poster": (30266640, 42793920),
    "pptx_slides": (12192000, 6858000),
}
ALLOWED_COLORS = {"000000", "FFFFFF", "737373"}
APPROVED_VISUAL_FONTS = {"黑体", "SimHei", "Heiti SC", "STHeiti", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC"}
CHAT_RESIDUE = [r"希望这对您有帮助", r"如果您需要我", r"作为(?:一个)?AI", r"当然[！!]", r"turn\d+(?:search|view)\d+"]


def xml_from(archive: zipfile.ZipFile, name: str) -> ET.Element:
    return ET.fromstring(archive.read(name))


def controls(spec_path: Path, profiles_path: Path) -> tuple[dict, dict, dict]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    registry = json.loads(profiles_path.read_text(encoding="utf-8"))
    route = next((item for item in registry.get("genre_routes", []) if item.get("id") == spec.get("genre_profile_id")), None)
    if route is None:
        raise ValueError(f"unknown genre_profile_id: {spec.get('genre_profile_id')}")
    profile = next((item for item in registry.get("format_profiles", []) if item.get("id") == route.get("format_profile_id")), None)
    if profile is None or profile.get("artifact_kind") not in EXPECTED_SIZES:
        raise ValueError("selected genre is not routed to a supported PPTX visual profile")
    return spec, route, profile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, int] = {}
    try:
        spec, route, profile = controls(args.spec, args.profiles)
        with zipfile.ZipFile(args.path) as archive:
            bad = archive.testzip()
            if bad:
                errors.append(f"corrupt archive member: {bad}")
            names = set(archive.namelist())
            required = {"ppt/presentation.xml", "docProps/core.xml", "ppt/_rels/presentation.xml.rels"}
            for member in sorted(required - names):
                errors.append(f"missing PPTX member: {member}")
            slide_names = sorted(
                name for name in names
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            )
            metrics["slides"] = len(slide_names)
            expected_slides = 1 if profile["artifact_kind"] == "pptx_poster" else 1 + len(spec.get("sections", []))
            if len(slide_names) != expected_slides:
                errors.append(f"expected {expected_slides} slide(s); found {len(slide_names)}")
            if errors:
                raise ValueError("PPTX package is incomplete")

            presentation = xml_from(archive, "ppt/presentation.xml")
            size = presentation.find(P + "sldSz")
            actual_size = (int(size.attrib.get("cx", 0)), int(size.attrib.get("cy", 0))) if size is not None else (0, 0)
            expected_size = EXPECTED_SIZES[profile["artifact_kind"]]
            if any(abs(actual_size[index] - expected_size[index]) > 2000 for index in (0, 1)):
                errors.append(f"canvas size {actual_size} does not match {profile['artifact_kind']} {expected_size}")

            all_text: list[str] = []
            fonts: set[str] = set()
            colors: set[str] = set()
            for slide_name in slide_names:
                slide = xml_from(archive, slide_name)
                all_text.extend(node.text or "" for node in slide.iter(A + "t"))
                for node in slide.iter():
                    if node.tag in {A + "latin", A + "ea", A + "cs"} and node.attrib.get("typeface"):
                        fonts.add(node.attrib["typeface"])
                    if node.tag == A + "srgbClr" and node.attrib.get("val"):
                        colors.add(node.attrib["val"].upper())
                for shape in slide.findall(".//" + P + "sp"):
                    transform = shape.find(".//" + A + "xfrm")
                    if transform is None:
                        continue
                    offset = transform.find(A + "off")
                    extent = transform.find(A + "ext")
                    if offset is None or extent is None:
                        continue
                    x, y = int(offset.attrib.get("x", 0)), int(offset.attrib.get("y", 0))
                    width, height = int(extent.attrib.get("cx", 0)), int(extent.attrib.get("cy", 0))
                    if x < 0 or y < 0 or x + width > actual_size[0] + 2000 or y + height > actual_size[1] + 2000:
                        errors.append(f"{slide_name}: shape exceeds the canvas")

            text = "".join(all_text)
            metrics["characters"] = len(text)
            metrics["placeholders"] = len(re.findall(r"【待填：[^】]+】", text))
            if spec.get("title") not in text:
                errors.append("visual artifact does not contain the controlled title")
            for section in spec.get("sections", []):
                if section.get("title") not in text:
                    errors.append(f"visual artifact is missing section title: {section.get('title')}")
            if metrics["placeholders"] and not args.allow_placeholders:
                errors.append(f"formal mode forbids {metrics['placeholders']} unresolved placeholders")
            elif metrics["placeholders"]:
                warnings.append(f"draft contains {metrics['placeholders']} unresolved placeholders")
            for pattern in CHAT_RESIDUE:
                if re.search(pattern, text, flags=re.IGNORECASE):
                    errors.append(f"chat/tool residue matched: {pattern}")

            if not fonts.intersection(APPROVED_VISUAL_FONTS):
                errors.append(f"no approved Chinese Hei/Sans visual font found: {sorted(fonts)}")
            if "Times New Roman" not in fonts:
                errors.append("visual artifact must contain Times New Roman for Latin text")
            unexpected_colors = colors - ALLOWED_COLORS
            if unexpected_colors and profile.get("decorative_shading_allowed") is False:
                errors.append(f"fallback visual contains uncontrolled colors: {', '.join(sorted(unexpected_colors))}")

            core = xml_from(archive, "docProps/core.xml")
            core_text = "".join(node.text or "" for node in core.iter())
            if spec.get("genre_profile_id") not in core_text or profile.get("id") not in core_text:
                errors.append("core properties do not bind the genre and visual profile")

            if spec.get("lifecycle_stage") == "release":
                roles = {"title", *(section.get("role") for section in spec.get("sections", []))}
                missing = [role for role in route.get("required_roles", []) if role not in roles]
                if missing:
                    errors.append(f"release missing required roles: {', '.join(missing)}")
                if route.get("controlled_template_required_for_release"):
                    controlled = spec.get("controlled_template", {})
                    if controlled.get("state") != "received_locked" or not re.fullmatch(r"[0-9a-fA-F]{64}", controlled.get("snapshot_sha256", "")):
                        errors.append("release requires a locked current event template")
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError, json.JSONDecodeError, ValueError) as exc:
        if not errors:
            errors.append(f"cannot validate visual artifact: {exc}")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print("INFO: " + "; ".join(f"{key}={value}" for key, value in sorted(metrics.items())))
    if errors:
        print(f"FAILED: {len(errors)} scientific-visual error(s)")
        return 1
    print("PASS: Chinese soil-science PPTX visual matches its controlled fallback profile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

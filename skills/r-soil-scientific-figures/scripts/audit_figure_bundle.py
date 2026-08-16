#!/usr/bin/env python3
"""Conservatively audit a figure script, rendered file, and provenance manifest."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "figure_id",
    "created",
    "source_data",
    "transformations",
    "design",
    "statistics",
    "software",
    "dimensions",
    "color",
    "outputs",
    "notes",
}


def safe_file(path_text: str, label: str, findings: dict[str, list[str]]) -> Path | None:
    path = Path(path_text).expanduser()
    if path.is_symlink():
        findings["errors"].append(f"{label} must not be a symlink: {path}")
        return None
    if not path.is_file():
        findings["errors"].append(f"missing {label}: {path}")
        return None
    return path.resolve()


def inspect_pdf(path: Path, findings: dict[str, list[str]]) -> dict[str, object]:
    report: dict[str, object] = {"format": "pdf", "bytes": path.stat().st_size}
    if path.read_bytes()[:5] != b"%PDF-":
        findings["errors"].append("PDF extension does not match file signature")
        return report
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        findings["warnings"].append("pdfinfo unavailable; PDF page metadata not inspected")
        return report
    proc = subprocess.run(
        [pdfinfo, str(path)], capture_output=True, text=True, timeout=30, check=False
    )
    if proc.returncode:
        findings["errors"].append(f"pdfinfo failed: {proc.stderr.strip()}")
        return report
    fields: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    report.update({"pages": fields.get("Pages"), "page_size": fields.get("Page size")})
    if fields.get("Pages") not in {None, "1"}:
        findings["warnings"].append(f"figure PDF has {fields.get('Pages')} pages")
    return report


def inspect_png(path: Path, findings: dict[str, list[str]]) -> dict[str, object]:
    report: dict[str, object] = {"format": "png", "bytes": path.stat().st_size}
    with path.open("rb") as handle:
        signature = handle.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            findings["errors"].append("PNG extension does not match file signature")
            return report
        length = struct.unpack(">I", handle.read(4))[0]
        chunk = handle.read(4)
        if chunk != b"IHDR" or length < 13:
            findings["errors"].append("PNG lacks a valid IHDR chunk")
            return report
        width, height = struct.unpack(">II", handle.read(8))
        report.update({"width_px": width, "height_px": height})
    return report


def inspect_svg(path: Path, findings: dict[str, list[str]]) -> dict[str, object]:
    report: dict[str, object] = {"format": "svg", "bytes": path.stat().st_size}
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        findings["errors"].append(f"invalid SVG XML: {exc}")
        return report
    if not root.tag.endswith("svg"):
        findings["errors"].append("SVG root element is not <svg>")
    report.update({"width": root.attrib.get("width"), "height": root.attrib.get("height")})
    return report


def inspect_figure(path: Path, findings: dict[str, list[str]]) -> dict[str, object]:
    suffix = path.suffix.casefold()
    if suffix == ".pdf":
        return inspect_pdf(path, findings)
    if suffix == ".png":
        return inspect_png(path, findings)
    if suffix == ".svg":
        return inspect_svg(path, findings)
    if suffix in {".tif", ".tiff"}:
        head = path.read_bytes()[:4]
        if head not in {b"II*\x00", b"MM\x00*"}:
            findings["errors"].append("TIFF extension does not match file signature")
        findings["warnings"].append("TIFF dimensions/DPI require an external image metadata tool")
        return {"format": "tiff", "bytes": path.stat().st_size}
    findings["errors"].append(f"unsupported figure extension: {suffix}")
    return {"format": suffix.lstrip("."), "bytes": path.stat().st_size}


def inspect_script(path: Path, findings: dict[str, list[str]]) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    if "install.packages(" in text or "BiocManager::install(" in text:
        findings["warnings"].append("script installs packages; prefer project setup outside plotting run")
    if not re.search(r"ggsave\s*\(|cairo_pdf\s*\(|svglite\s*\(|agg_(?:png|tiff)\s*\(", text):
        findings["warnings"].append("no explicit supported export call detected in R script")
    if not re.search(r"set\.seed\s*\(", text) and re.search(r"jitter|sample|bootstrap|position_jitter", text):
        findings["warnings"].append("stochastic-looking operation detected without set.seed()")
    return {"bytes": path.stat().st_size, "lines": text.count("\n") + 1}


def inspect_manifest(path: Path, findings: dict[str, list[str]]) -> tuple[dict[str, object], dict[str, object]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        findings["errors"].append(f"invalid manifest JSON: {exc}")
        return {}, {}
    if not isinstance(data, dict):
        findings["errors"].append("manifest root must be a JSON object")
        return {}, {}
    missing = sorted(REQUIRED_MANIFEST_FIELDS - data.keys())
    if missing:
        findings["errors"].append(f"manifest missing fields: {', '.join(missing)}")
    for field in ("source_data", "transformations", "outputs"):
        if field in data and not isinstance(data[field], list):
            findings["errors"].append(f"manifest field {field} must be a list")
    dimensions = data.get("dimensions")
    if not isinstance(dimensions, dict) or not {"width_mm", "height_mm"}.issubset(dimensions):
        findings["errors"].append("manifest dimensions must include width_mm and height_mm")
    return data, {"schema_version": data.get("schema_version"), "figure_id": data.get("figure_id")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    findings: dict[str, list[str]] = {"errors": [], "warnings": [], "notes": []}
    script = safe_file(args.script, "script", findings)
    figure = safe_file(args.figure, "figure", findings)
    manifest = safe_file(args.manifest, "manifest", findings)
    report: dict[str, object] = {
        "script": inspect_script(script, findings) if script else {},
        "figure": inspect_figure(figure, findings) if figure else {},
    }
    manifest_data: dict[str, object] = {}
    if manifest:
        manifest_data, report["manifest"] = inspect_manifest(manifest, findings)
    if figure and isinstance(manifest_data.get("outputs"), list):
        output_names = {Path(str(item)).name for item in manifest_data["outputs"]}
        if figure.name not in output_names:
            findings["warnings"].append("audited figure filename is not listed in manifest outputs")

    status = "FAIL" if findings["errors"] else ("WARN" if findings["warnings"] else "PASS")
    payload = {
        "status": status,
        "scope": "structural and machine-readable checks only; not scientific or journal certification",
        "report": report,
        **findings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if findings["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

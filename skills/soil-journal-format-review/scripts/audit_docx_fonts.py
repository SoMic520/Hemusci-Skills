#!/usr/bin/env python3
"""Resolve DOCX direct/theme fonts and audit installed macOS/Windows/Linux families."""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from ooxml_safety import PackageSafetyError, read_docx_package

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def qn(local: str) -> str:
    return f"{{{W}}}{local}"


def normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).casefold()


def installed_from_fontconfig() -> set[str]:
    executable = shutil.which("fc-list")
    if not executable:
        return set()
    result = subprocess.run(
        [executable, "--format=%{family}\n"], capture_output=True, text=True, timeout=30, check=False
    )
    if result.returncode != 0:
        return set()
    return {
        family.strip()
        for line in result.stdout.splitlines()
        for family in line.split(",")
        if family.strip()
    }


def installed_from_macos() -> set[str]:
    executable = shutil.which("system_profiler")
    if not executable:
        return set()
    result = subprocess.run(
        [executable, "SPFontsDataType", "-json"], capture_output=True, text=True, timeout=90, check=False
    )
    if result.returncode != 0:
        return set()
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return set()
    families = set()
    for font_file in payload.get("SPFontsDataType", []):
        for face in font_file.get("typefaces", []):
            for key in ("family", "fullname"):
                if face.get(key):
                    families.add(str(face[key]))
    return families


def installed_from_windows_registry() -> set[str]:
    try:
        import winreg  # type: ignore
    except ImportError:
        return set()
    families = set()
    locations = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
    )
    for hive, key_path in locations:
        try:
            key = winreg.OpenKey(hive, key_path)
        except OSError:
            continue
        with key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                display_name, _, _ = winreg.EnumValue(key, index)
                cleaned = re.sub(r"\s*\((TrueType|OpenType|All res)\)\s*$", "", display_name).strip()
                cleaned = re.sub(r"\s+(Regular|Bold|Italic|Bold Italic)\s*$", "", cleaned).strip()
                if cleaned:
                    families.add(cleaned)
    return families


def installed_fonts() -> tuple[set[str], str]:
    families = installed_from_fontconfig()
    if families:
        return families, "fontconfig"
    system = platform.system()
    if system == "Darwin":
        return installed_from_macos(), "system_profiler"
    if system == "Windows":
        return installed_from_windows_registry(), "windows_registry"
    return set(), "unavailable"


def _theme_scheme(parts: dict[str, bytes]) -> dict[str, dict[str, str]]:
    if "word/theme/theme1.xml" not in parts:
        return {}
    root = ET.fromstring(parts["word/theme/theme1.xml"])
    scheme = root.find(f".//{{{A}}}fontScheme")
    if scheme is None:
        return {}
    result = {}
    for group_name in ("majorFont", "minorFont"):
        group = scheme.find(f"{{{A}}}{group_name}")
        if group is None:
            continue
        fonts = {}
        for child in group:
            local = child.tag.rsplit("}", 1)[-1]
            typeface = child.get("typeface", "").strip()
            if local == "font":
                script = child.get("script", "").strip()
                if script and typeface:
                    fonts[script] = typeface
            elif typeface:
                fonts[local] = typeface
        result["major" if group_name == "majorFont" else "minor"] = fonts
    return result


def _east_asia_script(parts: dict[str, bytes]) -> str:
    candidates = []
    for name in ("word/document.xml", "word/styles.xml"):
        if name not in parts:
            continue
        root = ET.fromstring(parts[name])
        for lang in root.iter(qn("lang")):
            value = (lang.get(qn("eastAsia")) or "").lower()
            if value:
                candidates.append(value)
    if any(value.startswith("zh-tw") or value.startswith("zh-hk") for value in candidates):
        return "Hant"
    if any(value.startswith("ja") for value in candidates):
        return "Jpan"
    if any(value.startswith("ko") for value in candidates):
        return "Hang"
    return "Hans"


def _resolve_theme_reference(reference: str, scheme: dict[str, dict[str, str]], east_script: str) -> str | None:
    match = re.fullmatch(r"(major|minor)(Ascii|HAnsi|EastAsia|Bidi)", reference, re.I)
    if not match:
        return None
    group = scheme.get(match.group(1).lower(), {})
    kind = match.group(2).lower()
    if kind in {"ascii", "hansi"}:
        return group.get("latin")
    if kind == "bidi":
        return group.get("cs") or group.get("Arab") or group.get("Hebr")
    return group.get("ea") or group.get(east_script)


def requested_fonts(parts: dict[str, bytes]) -> tuple[set[str], set[str], list[dict[str, str | None]]]:
    direct: set[str] = set()
    theme_references: set[str] = set()
    for name, data in sorted(parts.items()):
        if not name.startswith("word/") or not name.endswith(".xml") or "/theme/" in name:
            continue
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            continue
        for r_fonts in root.iter(qn("rFonts")):
            for key in ("ascii", "hAnsi", "eastAsia", "cs"):
                value = r_fonts.get(qn(key))
                if value:
                    direct.add(value)
            for key in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
                value = r_fonts.get(qn(key))
                if value:
                    theme_references.add(value)
    scheme = _theme_scheme(parts)
    east_script = _east_asia_script(parts)
    resolution = []
    for reference in sorted(theme_references):
        resolved = _resolve_theme_reference(reference, scheme, east_script)
        resolution.append({"reference": reference, "resolved_family": resolved, "east_asia_script": east_script})
        if resolved:
            direct.add(resolved)
    return direct, theme_references, resolution


def mapping_key_for(name: str, mappings: dict[str, Any]) -> str | None:
    target = normalize(name)
    for canonical, details in mappings.items():
        if target == normalize(canonical) or any(target == normalize(alias) for alias in details.get("aliases", [])):
            return canonical
    return None


def audit(docx: Path, mapping_path: Path, extra_required: list[str]) -> dict[str, Any]:
    parts, _, security = read_docx_package(docx)
    mapping_payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    mappings = mapping_payload.get("families", {})
    requested, theme_refs, theme_resolution = requested_fonts(parts)
    requested.update(extra_required)
    installed, detector = installed_fonts()
    installed_lookup = {normalize(name): name for name in installed}
    system_key = {"Darwin": "macos_qa", "Windows": "windows_qa"}.get(platform.system(), "linux_qa")
    rows = []
    missing_exact = 0
    missing_without_fallback = 0
    for font in sorted(requested, key=str.casefold):
        exact = installed_lookup.get(normalize(font))
        canonical = mapping_key_for(font, mappings)
        candidates = mappings.get(canonical, {}).get(system_key, []) if canonical else []
        fallback = next(
            (installed_lookup[normalize(candidate)] for candidate in candidates if normalize(candidate) in installed_lookup),
            None,
        )
        if not exact:
            missing_exact += 1
            if not fallback:
                missing_without_fallback += 1
        rows.append(
            {
                "requested": font,
                "canonical_mapping": canonical,
                "exact_installed": bool(exact),
                "installed_name": exact,
                "qa_fallback_candidates": candidates,
                "available_qa_fallback": fallback,
                "open_font_auto_download_available": canonical in {"Noto Sans SC", "Noto Serif SC"},
                "final_docx_policy": "retain_requested_font_name",
            }
        )
    unresolved = [row for row in theme_resolution if not row["resolved_family"]]
    if detector == "unavailable" or not installed:
        status = "FAIL"
    elif unresolved or missing_without_fallback:
        status = "FAIL"
    elif missing_exact:
        status = "WARN"
    else:
        status = "PASS"
    return {
        "status": status,
        "scope": "DOCX_FONT_AUDIT",
        "platform": platform.system(),
        "font_detector": detector,
        "installed_family_count": len(installed),
        "document": str(docx.resolve()),
        "package_security": security,
        "theme_font_references": sorted(theme_refs),
        "theme_resolution": theme_resolution,
        "unresolved_theme_reference_count": len(unresolved),
        "fonts": rows,
        "missing_exact_count": missing_exact,
        "missing_without_qa_fallback_count": missing_without_fallback,
        "warning": (
            "QA fallbacks may be used only on a separate render copy; the final DOCX retains journal font names."
            if missing_exact else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--required-font", action="append", default=[])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    mapping = args.mapping or Path(__file__).resolve().parent.parent / "assets/font-compatibility.json"
    try:
        result = audit(args.docx, mapping, args.required_font)
    except (OSError, ValueError, PackageSafetyError, json.JSONDecodeError, ET.ParseError) as exc:
        result = {"status": "ERROR", "error": str(exc)}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return {"PASS": 0, "WARN": 3}.get(result.get("status"), 2)


if __name__ == "__main__":
    sys.exit(main())

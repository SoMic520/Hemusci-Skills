#!/usr/bin/env python3
"""Detect cross-platform DOCX, rendering, PDF and native Word capabilities."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def first_existing(candidates: list[str | Path]) -> str | None:
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(str(candidate))
        if resolved:
            return resolved
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


def command_version(executable: str | None, arguments: list[str]) -> str | None:
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, *arguments],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0] if text else None


def discover_native_word(system: str) -> str | None:
    if system == "Darwin":
        app = Path("/Applications/Microsoft Word.app")
        return str(app) if app.exists() else None
    if system == "Windows":
        candidates = ["WINWORD.EXE"]
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(env_name)
            if root:
                candidates.extend(
                    [
                        str(Path(root) / "Microsoft Office/root/Office16/WINWORD.EXE"),
                        str(Path(root) / "Microsoft Office/Office16/WINWORD.EXE"),
                    ]
                )
        return first_existing(candidates)
    return None


def inspect_toolchain() -> dict[str, Any]:
    system = platform.system()
    soffice_candidates: list[str | Path] = ["soffice", "libreoffice"]
    if system == "Darwin":
        # Prefer a validated PATH override supplied by the host runtime. The app
        # bundle binary remains the fallback for ordinary desktop installs.
        soffice_candidates.append("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    elif system == "Windows":
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(env_name)
            if root:
                soffice_candidates.insert(0, Path(root) / "LibreOffice/program/soffice.exe")

    soffice = first_existing(soffice_candidates)
    pdftoppm = first_existing(["pdftoppm"])
    pdftocairo = first_existing(["pdftocairo"])
    pdfinfo = first_existing(["pdfinfo"])
    fontconfig = first_existing(["fc-list"])
    powershell = first_existing(["pwsh", "powershell"])
    native_word = discover_native_word(system)
    python_docx = importlib.util.find_spec("docx") is not None
    full_visual = bool(soffice and (pdftoppm or pdftocairo) and pdfinfo)

    missing = []
    if not soffice:
        missing.append("LibreOffice/soffice (DOCX to PDF rendering)")
    if not (pdftoppm or pdftocairo):
        missing.append("Poppler pdftoppm/pdftocairo (PDF to page PNG)")
    if not pdfinfo:
        missing.append("Poppler pdfinfo (authoritative PDF page count)")

    return {
        "platform": {
            "system": system,
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
        "tools": {
            "python": {"path": sys.executable, "available": True},
            "python_docx": {"available": python_docx},
            "soffice": {
                "path": soffice,
                "available": bool(soffice),
                "version": command_version(soffice, ["--version"]),
            },
            "pdftoppm": {
                "path": pdftoppm,
                "available": bool(pdftoppm),
                "version": command_version(pdftoppm, ["-v"]),
            },
            "pdftocairo": {
                "path": pdftocairo,
                "available": bool(pdftocairo),
                "version": command_version(pdftocairo, ["-v"]),
            },
            "pdfinfo": {
                "path": pdfinfo,
                "available": bool(pdfinfo),
                "version": command_version(pdfinfo, ["-v"]),
            },
            "fontconfig": {"path": fontconfig, "available": bool(fontconfig)},
            "powershell": {"path": powershell, "available": bool(powershell)},
            "native_word": {"path": native_word, "available": bool(native_word)},
        },
        "capabilities": {
            "ooxml_inspection_and_comments": True,
            "python_docx_editing": python_docx,
            "docx_to_pdf": bool(soffice),
            "pdf_to_page_png": bool(pdftoppm or pdftocairo),
            "full_page_visual_qa": full_visual,
            "native_word_final_check": bool(native_word),
        },
        "status": "PASS" if full_visual else "WARN",
        "missing_for_full_visual_qa": missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = inspect_toolchain()
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Safely render DOCX to PDF and fresh, contiguous per-page PNG files."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from check_toolchain import inspect_toolchain
from ooxml_safety import PackageSafetyError, read_docx_package, sha256_file

PAGE_RE = re.compile(r"^page-(\d+)\.png$")


def run(command: list[str], env: dict[str, str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, env=env, timeout=timeout, check=False)


def _generated_paths(output_dir: Path, pdf_name: str) -> list[Path]:
    return sorted(
        [path for path in output_dir.iterdir() if path.is_file() and PAGE_RE.fullmatch(path.name)]
        + ([output_dir / pdf_name] if (output_dir / pdf_name).exists() else [])
    ) if output_dir.exists() else []


def _prepare_output(output_dir: Path, pdf_name: str, clean_generated: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stale = _generated_paths(output_dir, pdf_name)
    if stale and not clean_generated:
        raise ValueError(
            "Output directory contains prior render artifacts; use a fresh directory or --clean-generated: "
            + ", ".join(path.name for path in stale)
        )
    if clean_generated:
        for path in stale:
            path.unlink()


def _pdf_page_count(pdfinfo: str, pdf: Path, env: dict[str, str]) -> int:
    result = run([pdfinfo, str(pdf)], env, timeout=60)
    if result.returncode != 0:
        raise RuntimeError("pdfinfo failed: " + (result.stderr.strip() or result.stdout.strip()))
    match = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.M)
    if not match or int(match.group(1)) < 1:
        raise RuntimeError("pdfinfo did not report a positive page count")
    return int(match.group(1))


def _validate_pages(output_dir: Path, expected_count: int) -> list[Path]:
    rows = []
    for path in output_dir.iterdir():
        match = PAGE_RE.fullmatch(path.name)
        if match:
            rows.append((int(match.group(1)), path))
    rows.sort()
    numbers = [number for number, _ in rows]
    expected = list(range(1, expected_count + 1))
    if numbers != expected:
        raise RuntimeError(f"Rasterized page sequence is incomplete: found {numbers}, expected {expected}")
    for _, path in rows:
        data = path.read_bytes()
        if len(data) < 100 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError(f"Invalid or empty rendered PNG: {path}")
    return [path for _, path in rows]


def render(docx: Path, output_dir: Path, dpi: int, emit_pdf: bool, clean_generated: bool = False) -> dict:
    if dpi < 96 or dpi > 600:
        raise ValueError("dpi must be between 96 and 600")
    _, _, security = read_docx_package(docx)
    toolchain = inspect_toolchain()
    soffice = toolchain["tools"]["soffice"]["path"]
    raster = toolchain["tools"]["pdftoppm"]["path"] or toolchain["tools"]["pdftocairo"]["path"]
    pdfinfo = toolchain["tools"]["pdfinfo"]["path"]
    if not soffice or not raster or not pdfinfo:
        raise RuntimeError("LibreOffice plus Poppler pdfinfo and a PDF rasterizer are required")
    pdf_name = f"{docx.stem}.pdf"
    _prepare_output(output_dir, pdf_name, clean_generated)

    temp_parent = "/private/tmp" if platform.system() == "Darwin" else None
    with tempfile.TemporaryDirectory(prefix="soil-journal-render-", dir=temp_parent) as temporary:
        temp = Path(temporary)
        profile = temp / "lo-profile"
        profile.mkdir()
        working_docx = temp / "render-input.docx"
        shutil.copy2(docx.resolve(), working_docx)
        env = os.environ.copy()
        env["TMPDIR"] = "/private/tmp" if platform.system() == "Darwin" else str(temp)
        command = [
            soffice,
            "--headless",
            "--invisible",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            "--norestore",
            "--nofirststartwizard",
            f"-env:UserInstallation={profile.resolve().as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(temp.resolve()),
            str(working_docx.resolve()),
        ]
        conversion = run(command, env)
        converted_pdf = temp / "render-input.pdf"
        if conversion.returncode != 0 or not converted_pdf.exists() or converted_pdf.stat().st_size == 0:
            raise RuntimeError(
                "LibreOffice conversion failed: "
                + (conversion.stderr.strip() or conversion.stdout.strip() or f"exit {conversion.returncode}")
            )
        pdf = output_dir / pdf_name
        shutil.copy2(converted_pdf, pdf)
        page_count = _pdf_page_count(pdfinfo, pdf, env)
        prefix = output_dir / "page"
        raster_command = [raster, "-png", "-r", str(dpi), str(pdf), str(prefix)]
        raster_result = run(raster_command, env)
        if raster_result.returncode != 0:
            raise RuntimeError(
                "PDF rasterization failed: " + (raster_result.stderr.strip() or raster_result.stdout.strip())
            )
        page_paths = _validate_pages(output_dir, page_count)
        pdf_sha256 = sha256_file(pdf)
        pages = [
            {"page": index, "path": str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for index, path in enumerate(page_paths, start=1)
        ]
        result = {
            "status": "RENDERED_NOT_REVIEWED",
            "scope": "VISUAL_QA_RENDER_RECEIPT",
            "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "docx": str(docx.resolve()),
            "docx_sha256": sha256_file(docx),
            "package_security": security,
            "pdf": str(pdf.resolve()) if emit_pdf else None,
            "pdf_sha256": pdf_sha256,
            "pages": pages,
            "page_count": page_count,
            "dpi": dpi,
            "renderer": {
                "soffice": toolchain["tools"]["soffice"],
                "pdfinfo": toolchain["tools"]["pdfinfo"],
                "rasterizer": (
                    toolchain["tools"]["pdftoppm"]
                    if toolchain["tools"]["pdftoppm"]["path"] == raster
                    else toolchain["tools"]["pdftocairo"]
                ),
            },
            "visual_review": {"status": "NOT_REVIEWED", "reviewer": None, "reviewed_at": None, "notes": None},
        }
        if not emit_pdf:
            pdf.unlink()
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=160)
    parser.add_argument("--emit-pdf", action="store_true")
    parser.add_argument("--clean-generated", action="store_true")
    parser.add_argument("--out-json", type=Path)
    args = parser.parse_args()
    try:
        result = render(args.docx, args.output_dir, args.dpi, args.emit_pdf, args.clean_generated)
    except (OSError, ValueError, RuntimeError, PackageSafetyError, subprocess.TimeoutExpired) as exc:
        result = {"status": "ERROR", "error": str(exc)}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result.get("status") == "RENDERED_NOT_REVIEWED" else 2


if __name__ == "__main__":
    sys.exit(main())

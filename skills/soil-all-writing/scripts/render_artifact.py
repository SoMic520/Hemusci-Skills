#!/usr/bin/env python3
"""Render a DOCX to PDF and every page to PNG using local executables only."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile


def natural_key(path: Path) -> tuple[object, ...]:
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", path.name))


def executable(name: str) -> str:
    value = shutil.which(name)
    if not value:
        raise RuntimeError(f"required local executable not found: {name}")
    return value


def office_executable(prefer_fontconfig: bool = False) -> str:
    configured = os.environ.get("SOIL_SOFFICE")
    candidates = [Path(configured).expanduser()] if configured else []
    discovered = shutil.which("soffice")
    if prefer_fontconfig and discovered:
        candidates.append(Path(discovered))
    if platform.system() == "Darwin":
        candidates.append(Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"))
    if discovered and Path(discovered) not in candidates:
        candidates.append(Path(discovered))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise RuntimeError("required local LibreOffice executable not found; set SOIL_SOFFICE")


def poppler_executable(name: str) -> str | None:
    configured = os.environ.get(f"SOIL_{name.upper()}")
    candidates = [Path(configured).expanduser()] if configured else []
    direct = shutil.which(name)
    if direct:
        candidates.append(Path(direct))
    ppm = shutil.which("pdftoppm")
    if ppm:
        ppm_path = Path(ppm)
        candidates.extend([
            ppm_path.with_name(name),
            ppm_path.parent.parent.parent / "native" / "poppler" / "poppler" / "bin" / name,
        ])
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def poppler_env(executable_path: str) -> dict[str, str]:
    env = os.environ.copy()
    binary = Path(executable_path).resolve()
    library = binary.parent.parent / "lib"
    if library.is_dir():
        existing = env.get("DYLD_FALLBACK_LIBRARY_PATH")
        env["DYLD_FALLBACK_LIBRARY_PATH"] = str(library) + (f":{existing}" if existing else "")
    return env


def audit_pdf_fonts(pdf: Path, font_profile: str = "document") -> dict[str, object]:
    pdffonts = poppler_executable("pdffonts")
    if not pdffonts:
        raise RuntimeError("pdffonts is required for rendered Chinese-font verification")
    result = subprocess.run([pdffonts, str(pdf)], text=True, capture_output=True, check=False, env=poppler_env(pdffonts))
    if result.returncode != 0:
        raise RuntimeError(f"pdffonts failed ({result.returncode}): {result.stderr}")
    inventory = result.stdout
    rejected = [name for name in ["LastResort", "FrankRuhl", "NotoSansLisu", "DFWaWa"] if name.casefold() in inventory.casefold()]
    body_markers = ["STSong", "Songti", "SimSun", "Ming", "NotoSerifCJK", "SourceHanSerif"]
    heading_markers = ["PingFang", "Hiragino", "Heiti", "SimHei", "NotoSansCJK", "SourceHanSans"]
    latin_markers = ["TimesNewRoman", "Times New Roman"]
    accepted_body = [name for name in body_markers if name.casefold() in inventory.casefold()]
    accepted_heading = [name for name in heading_markers if name.casefold() in inventory.casefold()]
    accepted_latin = [name for name in latin_markers if name.casefold() in inventory.casefold()]
    font_names = []
    for line in inventory.splitlines()[2:]:
        fields = line.split()
        if fields:
            font_names.append(fields[0])
    if rejected:
        raise RuntimeError(f"rendered PDF uses rejected fallback font(s): {', '.join(rejected)}")
    if font_profile == "document" and not accepted_body:
        raise RuntimeError("rendered PDF contains no approved Song/Ming/serif Chinese body font")
    if not accepted_heading:
        raise RuntimeError("rendered PDF contains no approved Hei/sans Chinese heading font")
    if not accepted_latin:
        raise RuntimeError("rendered PDF contains no Times New Roman font for Latin text and numerals")
    return {
        "approved_body_markers": accepted_body,
        "approved_heading_markers": accepted_heading,
        "approved_latin_markers": accepted_latin,
        "font_names": sorted(set(font_names)),
        "font_inventory_lines": len(inventory.splitlines()),
    }


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, text=True, capture_output=True, check=False, env=env)
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def configure_font_environment(env: dict[str, str], temp: Path, font_dir: Path | None) -> dict[str, str]:
    if font_dir is None:
        return env
    resolved = font_dir.resolve()
    if not resolved.is_dir() or not any(path.suffix.lower() in {".otf", ".ttf", ".ttc"} for path in resolved.iterdir()):
        raise RuntimeError(f"font directory contains no OTF/TTF/TTC files: {resolved}")
    cache = temp / "font-cache"
    cache.mkdir()
    config = temp / "fonts.conf"
    config.write_text(
        "<?xml version=\"1.0\"?>\n"
        "<!DOCTYPE fontconfig SYSTEM \"fonts.dtd\">\n"
        "<fontconfig>\n"
        f"  <dir>{resolved}</dir>\n"
        "  <dir>/System/Library/Fonts</dir>\n"
        "  <dir>/System/Library/Fonts/Supplemental</dir>\n"
        "  <dir>/Library/Fonts</dir>\n"
        f"  <cachedir>{cache}</cachedir>\n"
        "  <config><rescan><int>30</int></rescan></config>\n"
        "</fontconfig>\n",
        encoding="utf-8",
    )
    updated = env.copy()
    updated["FONTCONFIG_FILE"] = str(config)
    updated["FONTCONFIG_PATH"] = str(temp)
    updated["SAL_FONTPATH"] = str(resolved)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--emit-pdf", action="store_true")
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--font-dir", type=Path)
    parser.add_argument("--font-profile", choices=("document", "visual"), default="document")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    source = args.input.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        print(f"ERROR: input not found: {source}")
        return 1
    if args.dpi < 72 or args.dpi > 300:
        print("ERROR: --dpi must be between 72 and 300")
        return 1

    try:
        if source.suffix.lower() == ".pdf":
            pdf = source
        elif source.suffix.lower() in {".docx", ".pptx"}:
            soffice = office_executable(prefer_fontconfig=args.font_dir is not None)
            with tempfile.TemporaryDirectory(prefix="soil-all-writing-render-") as temp_name:
                temp = Path(temp_name)
                profile = temp / "lo-profile"
                profile.mkdir()
                env = os.environ.copy()
                env["HOME"] = str(temp)
                env["TMPDIR"] = str(temp)
                env = configure_font_environment(env, temp, args.font_dir)
                run([
                    soffice,
                    "--headless",
                    f"-env:UserInstallation=file://{profile}",
                    "--convert-to", "pdf",
                    "--outdir", str(output),
                    str(source),
                ], env=env)
            pdf = output / f"{source.stem}.pdf"
            if not pdf.is_file() or pdf.stat().st_size == 0:
                raise RuntimeError("LibreOffice did not produce a non-empty PDF")
        else:
            raise RuntimeError("input must be DOCX, PPTX, or PDF")

        font_audit = audit_pdf_fonts(pdf, args.font_profile)

        pdftoppm = executable("pdftoppm")
        prefix = output / "page"
        for stale in output.glob("page-*.png"):
            stale.unlink()
        run([pdftoppm, "-png", "-r", str(args.dpi), str(pdf), str(prefix)])
        pages = sorted(output.glob("page-*.png"), key=natural_key)
        if not pages:
            raise RuntimeError("PDF rasterization produced no page PNGs")
        for index, page in enumerate(pages, 1):
            target = output / f"page-{index:03d}.png"
            if page != target:
                if target.exists():
                    target.unlink()
                page.rename(target)
        pages = sorted(output.glob("page-*.png"), key=natural_key)
        if not args.emit_pdf and pdf.parent == output and source.suffix.lower() != ".pdf":
            pdf.unlink()
            pdf_value = None
        else:
            pdf_value = str(pdf)
        receipt = {
            "status": "PASS",
            "input": str(source),
            "pdf": pdf_value,
            "page_count": len(pages),
            "pages": [str(page) for page in pages],
            "dpi": args.dpi,
            "font_audit": font_audit,
        }
        if args.receipt:
            args.receipt.resolve().parent.mkdir(parents=True, exist_ok=True)
            args.receipt.resolve().write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, ensure_ascii=False))
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

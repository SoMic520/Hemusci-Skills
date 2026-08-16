#!/usr/bin/env python3
"""Derive visible Word-TOC page numbers from a rendered technical-bid PDF."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def poppler_executable(name: str) -> Path:
    candidates: list[Path] = []
    direct = shutil.which(name)
    if direct:
        candidates.append(Path(direct))
    ppm = shutil.which("pdftoppm")
    if ppm:
        path = Path(ppm)
        candidates.extend([
            path.with_name(name),
            path.parent.parent.parent / "native" / "poppler" / "poppler" / "bin" / name,
        ])
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise RuntimeError(f"required Poppler executable not found: {name}")


def poppler_env(binary: Path) -> dict[str, str]:
    env = os.environ.copy()
    library = binary.parent.parent / "lib"
    if library.is_dir():
        existing = env.get("DYLD_FALLBACK_LIBRARY_PATH")
        env["DYLD_FALLBACK_LIBRARY_PATH"] = str(library) + (f":{existing}" if existing else "")
    return env


def run(binary: Path, arguments: list[str]) -> str:
    result = subprocess.run([str(binary), *arguments], text=True, capture_output=True, check=False, env=poppler_env(binary))
    if result.returncode != 0:
        raise RuntimeError(f"{binary.name} failed ({result.returncode}): {result.stderr}")
    return result.stdout


def normalized(value: str) -> str:
    return re.sub(r"\s+", "", value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cover-pages", type=int, default=1)
    args = parser.parse_args()
    spec = json.loads(args.spec.resolve().read_text(encoding="utf-8"))
    headings = [block for block in spec.get("content", []) if block.get("type") == "heading"]
    if not headings:
        raise SystemExit("ERROR: specification contains no headings")
    pdfinfo = poppler_executable("pdfinfo")
    pdftotext = poppler_executable("pdftotext")
    info = run(pdfinfo, [str(args.pdf.resolve())])
    match = re.search(r"^Pages:\s+(\d+)", info, flags=re.MULTILINE)
    if not match:
        raise SystemExit("ERROR: cannot read PDF page count")
    page_count = int(match.group(1))
    pages = [
        normalized(run(pdftotext, ["-f", str(page), "-l", str(page), str(args.pdf.resolve()), "-"]))
        for page in range(1, page_count + 1)
    ]

    first_heading_position = next(i for i, block in enumerate(spec["content"]) if block.get("type") == "heading")
    anchor = ""
    for block in spec["content"][first_heading_position + 1:]:
        if block.get("type") == "paragraph" and block.get("text"):
            anchor = normalized(block["text"])[:28]
            break
    content_start = next((index + 1 for index, text in enumerate(pages) if anchor and anchor in text), None)
    if content_start is None:
        raise SystemExit("ERROR: cannot locate the first body paragraph after the TOC")

    entries = []
    missing = []
    for index, heading in enumerate(headings):
        title = normalized(heading["text"])
        physical = next((page for page in range(content_start, page_count + 1) if title in pages[page - 1]), None)
        if physical is None:
            missing.append(heading["text"])
            continue
        entries.append({
            "index": index,
            "title": heading["text"],
            "level": heading["level"],
            "physical_page": physical,
            "page": physical - args.cover_pages,
        })
    if missing:
        raise SystemExit("ERROR: headings not found after TOC: " + " | ".join(missing))
    result = {
        "schema_version": 1,
        "source_pdf": str(args.pdf.resolve()),
        "physical_page_count": page_count,
        "cover_pages": args.cover_pages,
        "content_start_physical_page": content_start,
        "entries": entries,
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "output": str(args.output.resolve()), "entries": len(entries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Create a hash-bound figure/table image preflight with contrast renders and OCR candidates."""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from PIL import Image


def normalized_ocr(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def run_tesseract(image_path: Path, languages: str, psm: int) -> tuple[str, str]:
    image_bytes = image_path.read_bytes()
    # Feed the exact rendered bytes through stdin. This avoids platform-specific
    # file-provenance restrictions while preserving the hash-bound artifact.
    base = ["tesseract", "stdin", "stdout", "-l", languages, "--psm", str(psm)]
    text_run = subprocess.run(base, input=image_bytes, capture_output=True, check=False)
    if text_run.returncode != 0:
        detail = text_run.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "tesseract text extraction failed")
    tsv_run = subprocess.run(base + ["tsv"], input=image_bytes, capture_output=True, check=False)
    if tsv_run.returncode != 0:
        detail = tsv_run.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "tesseract TSV extraction failed")
    return (
        text_run.stdout.decode("utf-8", errors="replace"),
        tsv_run.stdout.decode("utf-8", errors="replace"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--languages", default="chi_sim+eng")
    parser.add_argument("--psm", type=int, default=6)
    parser.add_argument("--skip-ocr", action="store_true")
    parser.add_argument("--expected-text", action="append", default=[])
    args = parser.parse_args()
    if args.output_dir.exists():
        print(f"ERROR: refusing to overwrite existing output directory: {args.output_dir}")
        return 1
    try:
        data = args.image.read_bytes()
        image = Image.open(args.image)
        image.load()
    except (OSError, ValueError) as exc:
        print(f"ERROR: cannot read image: {exc}")
        return 1
    args.output_dir.mkdir(parents=True)
    digest = hashlib.sha256(data).hexdigest()
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha_min, alpha_max = alpha.getextrema()
    alpha_histogram = alpha.histogram()
    transparent_pixels = sum(alpha_histogram[:255])
    has_transparency = transparent_pixels > 0
    render_paths: dict[str, str] = {}
    ocr_targets: dict[str, Path] = {}
    if has_transparency:
        for label, color in (("white", (255, 255, 255, 255)), ("black", (0, 0, 0, 255))):
            background = Image.new("RGBA", rgba.size, color)
            composite = Image.alpha_composite(background, rgba).convert("RGB")
            target = args.output_dir / f"contrast-{label}.png"
            composite.save(target)
            render_paths[label] = target.name
            ocr_targets[label] = target
    else:
        target = args.output_dir / "normalized-rgb.png"
        image.convert("RGB").save(target)
        render_paths["original"] = target.name
        ocr_targets["original"] = target

    warnings: list[str] = []
    ocr_records: dict[str, dict[str, object]] = {}
    if not args.skip_ocr:
        if not shutil.which("tesseract"):
            warnings.append("tesseract is unavailable; OCR was not run")
        else:
            for label, target in ocr_targets.items():
                try:
                    text_value, tsv_value = run_tesseract(target, args.languages, args.psm)
                except RuntimeError as exc:
                    warnings.append(f"OCR failed for {label}: {exc}")
                    continue
                text_path = args.output_dir / f"ocr-{label}.txt"
                tsv_path = args.output_dir / f"ocr-{label}.tsv"
                text_path.write_text(text_value, encoding="utf-8")
                tsv_path.write_text(tsv_value, encoding="utf-8")
                ocr_records[label] = {
                    "text_path": text_path.name,
                    "tsv_path": tsv_path.name,
                    "non_whitespace_characters": len(normalized_ocr(text_value)),
                }
    ocr_texts = {
        label: (args.output_dir / record["text_path"]).read_text(encoding="utf-8")
        for label, record in ocr_records.items()
    }
    contrast_similarity = None
    if "white" in ocr_texts and "black" in ocr_texts:
        contrast_similarity = round(SequenceMatcher(
            None, normalized_ocr(ocr_texts["white"]), normalized_ocr(ocr_texts["black"])
        ).ratio(), 4)
        if contrast_similarity < 0.9:
            warnings.append(
                "white/black OCR differs materially; inspect both renders for hidden labels, symbols, or annotations"
            )
    combined_ocr = "\n".join(ocr_texts.values())
    missing_expected = [value for value in args.expected_text if value not in combined_ocr]
    if missing_expected:
        warnings.append("expected text absent from OCR candidates: " + ", ".join(missing_expected))

    report = {
        "schema_version": 1,
        "source_path": str(args.image.resolve()),
        "source_sha256": digest,
        "format": image.format,
        "mode": image.mode,
        "width_px": image.width,
        "height_px": image.height,
        "alpha_extrema": [alpha_min, alpha_max],
        "transparent_pixel_count": transparent_pixels,
        "has_transparency": has_transparency,
        "contrast_renders": render_paths,
        "ocr": {
            "status": "candidate_only_not_verified" if ocr_records else "not_available_or_skipped",
            "languages": args.languages,
            "page_segmentation_mode": args.psm,
            "records": ocr_records,
            "white_black_similarity": contrast_similarity,
            "expected_text_missing": missing_expected,
        },
        "warnings": warnings,
        "release_boundary": (
            "OCR output is a recognition candidate, not scientific evidence. Confirm labels, numbers, units, "
            "letters, symbols, intervals, and table structure against the rendered image and caption."
        ),
    }
    report_path = args.output_dir / "image-preflight.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS_WITH_WARNINGS" if warnings else "PASS",
        "report": str(report_path),
        "warnings": len(warnings),
        "has_transparency": has_transparency,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

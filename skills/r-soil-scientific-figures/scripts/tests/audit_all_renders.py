#!/usr/bin/env python3
"""Run structural raster QA across every PNG in a recipe test directory."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


FIELDS = (
    "id", "status", "width_px", "height_px", "left_margin_px", "top_margin_px",
    "right_margin_px", "bottom_margin_px", "occupancy", "tonal_range", "issues",
)


def inspect(path: Path, expected: tuple[int, int] | None, edge_fraction: float) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    with Image.open(path) as source:
        image = source.convert("RGB")
    width, height = image.size
    if expected and (width, height) != expected:
        errors.append(f"dimension mismatch; expected {expected[0]}x{expected[1]}")
    white = Image.new("RGB", image.size, "white")
    difference = ImageChops.difference(image, white).convert("L")
    threshold = difference.point(lambda value: 255 if value > 8 else 0)
    bbox = threshold.getbbox()
    margins = (None, None, None, None)
    occupancy = 0.0
    if bbox is None:
        errors.append("blank render")
    else:
        left, top, right, bottom = bbox
        margins = (left, top, width - right, height - bottom)
        minimum_x = math.ceil(width * edge_fraction)
        minimum_y = math.ceil(height * edge_fraction)
        if left < minimum_x or width - right < minimum_x:
            warnings.append("content near left/right edge")
        if top < minimum_y or height - bottom < minimum_y:
            warnings.append("content near top/bottom edge")
        pixels = threshold.get_flattened_data() if hasattr(threshold, "get_flattened_data") else threshold.getdata()
        occupancy = sum(bool(value) for value in pixels) / (width * height)
        if occupancy < 0.006:
            warnings.append("canvas occupancy below 0.6%")
        if occupancy > 0.90:
            warnings.append("canvas occupancy above 90%")
    extrema = ImageStat.Stat(image.convert("L")).extrema[0]
    tonal_range = extrema[1] - extrema[0]
    if tonal_range < 30:
        errors.append("insufficient tonal range")
    status = "FAIL" if errors else "WARN" if warnings else "PASS"
    return {
        "id": path.stem,
        "status": status,
        "width_px": width,
        "height_px": height,
        "left_margin_px": margins[0],
        "top_margin_px": margins[1],
        "right_margin_px": margins[2],
        "bottom_margin_px": margins[3],
        "occupancy": round(occupancy, 6),
        "tonal_range": tonal_range,
        "issues": " | ".join(errors + warnings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--edge-fraction", type=float, default=0.004)
    args = parser.parse_args()
    paths = sorted(path for path in args.input.glob("*.png") if not path.name.startswith("._"))
    if not paths:
        raise SystemExit("No PNG files found")
    with Image.open(paths[0]) as first:
        expected = first.size
    rows = [inspect(path, expected, args.edge_fraction) for path in paths]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter(str(row["status"]) for row in rows)
    summary = {
        "total": len(rows),
        "pass": counts["PASS"],
        "warn": counts["WARN"],
        "fail": counts["FAIL"],
        "expected_dimensions_px": list(expected),
        "occupancy_min": min(float(row["occupancy"]) for row in rows),
        "occupancy_max": max(float(row["occupancy"]) for row in rows),
        "scope": "structural raster QA; contact-sheet visual review is additionally required",
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

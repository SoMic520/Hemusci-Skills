#!/usr/bin/env python3
"""Validate raster dimensions, content bounds, density and basic export health."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--edge-fraction", type=float, default=0.004)
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    if not args.image.is_file():
        errors.append(f"missing image: {args.image}")
        payload = {"status": "FAIL", "errors": errors, "warnings": warnings}
    else:
        opened = Image.open(args.image)
        has_alpha = "A" in opened.getbands()
        alpha_extrema = None
        transparent_fraction = 0.0
        if has_alpha:
            rgba = opened.convert("RGBA")
            alpha = rgba.getchannel("A")
            alpha_extrema = alpha.getextrema()
            histogram = alpha.histogram()
            transparent_fraction = sum(histogram[:255]) / (rgba.width * rgba.height)
            white_rgba = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            image = Image.alpha_composite(white_rgba, rgba).convert("RGB")
        else:
            image = opened.convert("RGB")
        width, height = image.size
        white = Image.new("RGB", image.size, "white")
        difference = ImageChops.difference(image, white).convert("L")
        threshold = difference.point(lambda value: 255 if value > 8 else 0)
        bbox = threshold.getbbox()
        if bbox is None:
            errors.append("render is blank or visually indistinguishable from white")
            margins = None
        else:
            left, top, right, bottom = bbox
            margins = {
                "left_px": left,
                "top_px": top,
                "right_px": width - right,
                "bottom_px": height - bottom,
            }
            minimum_x = math.ceil(width * args.edge_fraction)
            minimum_y = math.ceil(height * args.edge_fraction)
            if left < minimum_x or width - right < minimum_x:
                warnings.append("non-white content is close to a left/right edge; inspect for clipping")
            if top < minimum_y or height - bottom < minimum_y:
                warnings.append("non-white content is close to a top/bottom edge; inspect for clipping")

        grey = image.convert("L")
        stats = ImageStat.Stat(grey)
        extrema = grey.getextrema()
        if extrema[1] - extrema[0] < 30:
            errors.append("render has insufficient tonal range")
        nonwhite_pixels = sum(1 for value in threshold.getdata() if value)
        occupancy = nonwhite_pixels / (width * height)
        if occupancy < 0.01:
            warnings.append("less than 1% of the canvas contains marks or text")
        if occupancy > 0.90:
            warnings.append("more than 90% of the canvas is non-white; check crowding/background")

        expected = None
        if args.config and args.config.is_file():
            config = json.loads(args.config.read_text(encoding="utf-8"))
            expected = {
                "width_px": round(config["width_mm"] / 25.4 * config["raster_dpi"]),
                "height_px": round(config["height_mm"] / 25.4 * config["raster_dpi"]),
            }
            if abs(width - expected["width_px"]) > 2 or abs(height - expected["height_px"]) > 2:
                errors.append(f"pixel dimensions differ from config: actual={width}x{height}, expected={expected}")

        payload = {
            "status": "FAIL" if errors else ("WARN" if warnings else "PASS"),
            "image": str(args.image.resolve()),
            "width_px": width,
            "height_px": height,
            "expected": expected,
            "content_margins": margins,
            "occupancy": round(occupancy, 6),
            "mean_luminance": round(stats.mean[0], 3),
            "tonal_extrema": extrema,
            "alpha": {
                "present": has_alpha,
                "extrema": alpha_extrema,
                "non_opaque_fraction": round(transparent_fraction, 6),
            },
            "errors": errors,
            "warnings": warnings,
            "scope": "structural raster QA; manual visual inspection is still required",
        }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

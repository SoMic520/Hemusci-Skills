#!/usr/bin/env python3
"""Prepare formula crops and a fingerprinted review manifest.

The output stays under the build work directory. A formula is only admitted
to runtime after a matching explicitly verified record is copied into the
source corpus formula-review.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


FORCED_FORMULA_IDS = {
    "lu-rukkun": {"P633-F3", "P643-F3"},
    "technical-spec": set(),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--book", choices=("lu-rukkun", "technical-spec"), required=True)
    return parser.parse_args()


def image_path(directory: Path, page: int) -> Path:
    for suffix in ("jpg", "png"):
        for width in (4, 3, 2, 0):
            number = f"{page:0{width}d}" if width else str(page)
            path = directory / f"page-{number}.{suffix}"
            if path.is_file():
                return path
    raise FileNotFoundError(f"{directory}:{page}")


def meaningful(latex: str) -> bool:
    return len(latex) >= 9 and any(
        marker in latex for marker in ("=", r"\approx", r"\geq", r"\leq")
    )


def normalize(latex: str) -> str:
    latex = latex.strip().replace(r"\bullet", r"\cdot")
    latex = latex.replace(r"\mathrm{m o l}", r"\mathrm{mol}")
    latex = latex.replace(r"\mathrm{m L}", r"\mathrm{mL}")
    latex = latex.replace(r"\mathrm{mL^{-1}}", r"\mathrm{mL}^{-1}")
    return re.sub(r"\\mu\s+g", r"\\mu\\mathrm{g}", latex)


def fingerprint(latex: str, region: list[Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            {"latex": latex, "region": region},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    )
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def crop_formula(source: Image.Image, region: list[Any], label: str, latex: str) -> Image.Image:
    boxes = []
    for polygon in region:
        if isinstance(polygon, list) and len(polygon) == 4 and all(isinstance(value, (int, float)) for value in polygon):
            boxes.append(polygon)
        elif isinstance(polygon, list):
            points = [point for point in polygon if isinstance(point, list) and len(point) >= 2]
            if points:
                xs = [float(point[0]) for point in points]
                ys = [float(point[1]) for point in points]
                boxes.append([min(xs), min(ys), max(xs), max(ys)])
    if not boxes:
        return Image.new("RGB", (900, 180), "white")
    left = max(0, int(min(box[0] for box in boxes)) - 24)
    top = max(0, int(min(box[1] for box in boxes)) - 24)
    right = min(source.width, int(max(box[2] for box in boxes)) + 24)
    bottom = min(source.height, int(max(box[3] for box in boxes)) + 24)
    raw = source.crop((left, top, right, bottom)).convert("RGB")
    scale = min(1.0, 1300 / max(raw.width, 1))
    if scale < 1:
        raw = raw.resize((int(raw.width * scale), int(raw.height * scale)), Image.Resampling.LANCZOS)
    header_lines = textwrap.wrap(latex, width=105)[:3]
    header_height = 38 + len(header_lines) * 22
    canvas = Image.new("RGB", (max(raw.width, 900), raw.height + header_height), "white")
    canvas.paste(raw, (0, header_height))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 4), label, fill="black", font=font(24))
    draw.multiline_text((8, 34), "\n".join(header_lines), fill="#183a68", font=font(16), spacing=2)
    return canvas


def main() -> None:
    config = parse_args()
    work = config.work_root / config.book
    review_root = work / "formula-review"
    crop_root = review_root / "crops"
    sheet_root = review_root / "sheets"
    crop_root.mkdir(parents=True, exist_ok=True)
    sheet_root.mkdir(parents=True, exist_ok=True)
    for stale in crop_root.glob("P*-F*.png"):
        stale.unlink()
    for stale in sheet_root.glob("sheet-*.jpg"):
        stale.unlink()
    records = []
    for path in sorted((work / "formula").glob("page-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        page = int(payload["page"])
        source = Image.open(image_path(work / "images", page))
        for index, item in enumerate(payload.get("formulas") or [], 1):
            latex = normalize(str(item.get("rec_formula") or ""))
            formula_id = f"P{page}-F{index}"
            if not meaningful(latex) and formula_id not in FORCED_FORMULA_IDS[config.book]:
                continue
            region = item.get("dt_polys") or []
            crop = crop_formula(source, region, formula_id, latex)
            crop_path = crop_root / f"{formula_id}.png"
            crop.save(crop_path, optimize=True)
            records.append({
                "id": formula_id,
                "page": page,
                "sourceFingerprint": fingerprint(latex, region),
                "sourceLatex": latex,
                "crop": str(crop_path.relative_to(config.work_root)),
                "status": "candidate",
            })
        source.close()

    sheet_size = 12
    for start in range(0, len(records), sheet_size):
        batch = records[start:start + sheet_size]
        crops = [Image.open(config.work_root / item["crop"]).convert("RGB") for item in batch]
        width = max(image.width for image in crops)
        heights = [image.height for image in crops]
        canvas = Image.new("RGB", (width, sum(heights) + 10 * (len(crops) - 1)), "#d8d8d8")
        y = 0
        for crop in crops:
            canvas.paste(crop, (0, y))
            y += crop.height + 10
        canvas.save(sheet_root / f"sheet-{start // sheet_size + 1:03d}.jpg", quality=94, subsampling=0)
        for crop in crops:
            crop.close()
    (review_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "soil-methods-consultant.formula-review.v1",
                "book": config.book,
                "formulaCount": len(records),
                "formulas": records,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    print(f"{config.book}: formulas={len(records)} sheets={(len(records)+sheet_size-1)//sheet_size}")


if __name__ == "__main__":
    main()

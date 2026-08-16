#!/usr/bin/env python3
"""Create paginated contact sheets for manual QA of all recipe renders."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--recursive", action="store_true", help="Include PNG files below subdirectories")
    args = parser.parse_args()

    candidates = args.input.rglob("*.png") if args.recursive else args.input.glob("*.png")
    paths = sorted(path for path in candidates if not path.name.startswith("._"))
    if not paths:
        raise SystemExit("No PNG files found")
    args.output.mkdir(parents=True, exist_ok=True)
    cell_w, cell_h = 360, 300
    thumb_w, thumb_h = 342, 258
    per_page = args.columns * args.rows
    font = ImageFont.load_default(size=12)
    pages = math.ceil(len(paths) / per_page)
    for page in range(pages):
        canvas = Image.new("RGB", (args.columns * cell_w, args.rows * cell_h), "white")
        draw = ImageDraw.Draw(canvas)
        subset = paths[page * per_page : (page + 1) * per_page]
        for index, path in enumerate(subset):
            row, column = divmod(index, args.columns)
            x0, y0 = column * cell_w, row * cell_h
            image = Image.open(path).convert("RGB")
            thumb = ImageOps.contain(image, (thumb_w, thumb_h), method=Image.Resampling.LANCZOS)
            x = x0 + (cell_w - thumb.width) // 2
            y = y0 + 4
            canvas.paste(thumb, (x, y))
            draw.rectangle((x0, y0, x0 + cell_w - 1, y0 + cell_h - 1), outline="#D9D9D9", width=1)
            label = str(path.relative_to(args.input).with_suffix("")) if args.recursive else path.stem
            if len(label) > 48:
                label = label[:45] + "..."
            draw.text((x0 + 8, y0 + cell_h - 28), label, fill="#222222", font=font)
        out = args.output / f"contact-sheet-{page + 1:03d}.png"
        canvas.save(out, format="PNG", optimize=True)
    print(f"created {pages} contact sheets for {len(paths)} renders")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

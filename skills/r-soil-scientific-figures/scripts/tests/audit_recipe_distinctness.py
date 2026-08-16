#!/usr/bin/env python3
"""Reject recipe libraries that merely rename identical rendered figures.

This is a structural quality gate, not a claim that every visually distinct
figure is scientifically correct. Exact duplicates fail by default. Near-match
pairs are reported for human review because trivial cosmetic changes must not be
used to evade the gate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageOps


def dhash(path: Path, size: int = 16) -> int:
    with Image.open(path) as source:
        image = ImageOps.grayscale(source).resize((size + 1, size), Image.Resampling.LANCZOS)
    pixel_source = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    pixels = list(pixel_source)
    value = 0
    for y in range(size):
        row = y * (size + 1)
        for x in range(size):
            value = (value << 1) | int(pixels[row + x] > pixels[row + x + 1])
    return value


def file_md5(path: Path) -> str:
    digest = hashlib.md5()  # noqa: S324 - content identity, not security
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Directory containing recipe PNG files")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--near-distance", type=int, default=3)
    parser.add_argument("--allow-exact-duplicates", action="store_true")
    args = parser.parse_args()

    paths = sorted(path for path in args.input.glob("*.png") if not path.name.startswith("._"))
    if not paths:
        raise SystemExit("No PNG files found")

    exact: dict[str, list[str]] = defaultdict(list)
    hashes: dict[str, int] = {}
    for path in paths:
        exact[file_md5(path)].append(path.stem)
        hashes[path.stem] = dhash(path)
    exact_groups = [sorted(ids) for ids in exact.values() if len(ids) > 1]
    exact_groups.sort(key=lambda ids: (-len(ids), ids))

    near_pairs: list[dict[str, object]] = []
    names = sorted(hashes)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            distance = (hashes[left] ^ hashes[right]).bit_count()
            if distance <= args.near_distance:
                near_pairs.append({"left": left, "right": right, "dhash_distance": distance})

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("kind", "group_size", "left", "right", "members", "distance"),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        for group in exact_groups:
            writer.writerow(
                {
                    "kind": "exact-duplicate-group",
                    "group_size": len(group),
                    "left": "",
                    "right": "",
                    "members": ";".join(group),
                    "distance": 0,
                }
            )
        for pair in near_pairs:
            writer.writerow(
                {
                    "kind": "near-match-pair",
                    "group_size": 2,
                    "left": pair["left"],
                    "right": pair["right"],
                    "members": "",
                    "distance": pair["dhash_distance"],
                }
            )

    exact_recipe_count = sum(len(group) for group in exact_groups)
    summary = {
        "total_recipes": len(paths),
        "exact_duplicate_groups": len(exact_groups),
        "recipes_in_exact_duplicate_groups": exact_recipe_count,
        "near_match_pairs_at_or_below_threshold": len(near_pairs),
        "near_distance_threshold": args.near_distance,
        "status": "FAIL" if exact_groups and not args.allow_exact_duplicates else "PASS",
        "interpretation": (
            "Exact duplicate renders indicate renamed or unresolved recipe implementations. "
            "Near matches require semantic and visual review; uniqueness alone is not quality."
        ),
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

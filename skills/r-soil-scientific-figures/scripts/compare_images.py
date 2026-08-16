#!/usr/bin/env python3
"""Compare reference and reconstructed figures without claiming semantic equivalence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, ImageStat


def average_hash(image: Image.Image, size: int = 16) -> str:
    small = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    values = list(small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata())
    mean = sum(values) / len(values)
    bits = "".join("1" if value >= mean else "0" for value in values)
    return f"{int(bits, 2):0{size * size // 4}x}"


def hamming(left: str, right: str) -> int:
    return sum(a != b for a, b in zip(bin(int(left, 16))[2:].zfill(len(left) * 4), bin(int(right, 16))[2:].zfill(len(right) * 4)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--diff", type=Path)
    args = parser.parse_args()

    with Image.open(args.reference) as reference_image, Image.open(args.candidate) as candidate_image:
        reference = reference_image.convert("RGB")
        candidate_original = candidate_image.convert("RGB")
        candidate = candidate_original.resize(reference.size, Image.Resampling.LANCZOS)
        diff = ImageChops.difference(reference, candidate)
        stats = ImageStat.Stat(diff)
        rms = math.sqrt(sum(value * value for value in stats.rms) / 3)
        ref_hash = average_hash(reference)
        candidate_hash = average_hash(candidate)
        report = {
            "status": "PASS",
            "reference": str(args.reference.resolve()),
            "candidate": str(args.candidate.resolve()),
            "reference_size_px": list(reference.size),
            "candidate_size_px": list(candidate_original.size),
            "candidate_resized_for_comparison": reference.size != candidate_original.size,
            "rgb_rms_difference_0_255": round(rms, 4),
            "average_hash_hamming_0_256": hamming(ref_hash, candidate_hash),
            "interpretation": "Pixel similarity supports layout QA only; it does not prove identical data, statistics or scientific meaning.",
        }
        if args.diff:
            args.diff.parent.mkdir(parents=True, exist_ok=True)
            ImageOps.autocontrast(diff).save(args.diff)
            report["difference_image"] = str(args.diff.resolve())
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

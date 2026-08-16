#!/usr/bin/env python3
"""Count Chinese scientific prose with explicit, reproducible counting units."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


COUNT_UNITS = {
    "han_characters",
    "han_characters_plus_alnum_tokens",
    "non_whitespace_characters",
}


def is_han(character: str) -> bool:
    point = ord(character)
    return any(
        lower <= point <= upper
        for lower, upper in (
            (0x3400, 0x4DBF),
            (0x4E00, 0x9FFF),
            (0xF900, 0xFAFF),
            (0x20000, 0x2EBEF),
            (0x30000, 0x323AF),
        )
    )


def count_text(text: str) -> dict[str, int]:
    han = sum(is_han(character) for character in text)
    without_han = "".join(" " if is_han(character) else character for character in text)
    alnum_tokens = re.findall(
        r"[A-Za-z0-9]+(?:[._/·%‰−–-][A-Za-z0-9⁰¹²³⁴⁵⁶⁷⁸⁹]+)*",
        without_han,
    )
    non_whitespace = sum(not character.isspace() for character in text)
    punctuation_or_symbols = sum(
        not character.isspace() and not is_han(character) and not character.isalnum()
        for character in text
    )
    return {
        "han_characters": han,
        "alnum_tokens": len(alnum_tokens),
        "han_characters_plus_alnum_tokens": han + len(alnum_tokens),
        "non_whitespace_characters": non_whitespace,
        "punctuation_or_symbols": punctuation_or_symbols,
        "total_unicode_characters": len(text),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--unit", choices=sorted(COUNT_UNITS), default="han_characters_plus_alnum_tokens")
    parser.add_argument("--minimum", type=int)
    parser.add_argument("--maximum", type=int)
    args = parser.parse_args()
    try:
        text = args.path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 1
    if args.minimum is not None and args.minimum < 0:
        print("ERROR: minimum must be non-negative")
        return 1
    if args.maximum is not None and args.maximum < 0:
        print("ERROR: maximum must be non-negative")
        return 1
    if args.minimum is not None and args.maximum is not None and args.maximum < args.minimum:
        print("ERROR: maximum must not be smaller than minimum")
        return 1
    counts = count_text(text)
    selected = counts[args.unit]
    within_range = (
        (args.minimum is None or selected >= args.minimum)
        and (args.maximum is None or selected <= args.maximum)
    )
    print(json.dumps({
        "status": "PASS" if within_range else "OUT_OF_RANGE",
        "selected_unit": args.unit,
        "selected_count": selected,
        "minimum": args.minimum,
        "maximum": args.maximum,
        "counts": counts,
    }, ensure_ascii=False, indent=2))
    return 0 if within_range else 1


if __name__ == "__main__":
    sys.exit(main())

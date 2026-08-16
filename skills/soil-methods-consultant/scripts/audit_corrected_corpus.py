#!/usr/bin/env python3
"""Reject a corrected corpus unless every source page passes all review gates."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = SKILL_ROOT / "references" / "corrected-pages"
PAGE_COUNTS = {1: 557, 2: 358}
REQUIRED_GATES = ("textPass", "precisionPass", "secondVisualPass")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验 915 页零容错语料的完整性与复核状态。")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def canonical_hash(record: dict[str, Any]) -> str:
    content = {
        "blocks": record.get("blocks"),
        "formulas": record.get("formulas"),
        "tables": record.get("tables"),
    }
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_record(path: Path) -> dict[str, Any]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    failures: list[str] = []
    verified = 0
    for volume, page_count in PAGE_COUNTS.items():
        for page in range(1, page_count + 1):
            base = args.corpus / f"volume-{volume}" / f"page-{page:04d}.json"
            path = base if base.is_file() else base.with_suffix(".json.gz")
            if not path.is_file():
                failures.append(f"volume-{volume}:{page}: missing")
                continue
            try:
                record = load_record(path)
            except Exception as error:
                failures.append(f"volume-{volume}:{page}: unreadable {error}")
                continue
            if record.get("schema") != "soil-methods-consultant.corrected-page.v1":
                failures.append(f"volume-{volume}:{page}: invalid schema")
            if record.get("bookId") != f"volume-{volume}" or int(record.get("page", 0)) != page:
                failures.append(f"volume-{volume}:{page}: identity mismatch")
            if not record.get("sourceImageSha256"):
                failures.append(f"volume-{volume}:{page}: missing source image hash")
            review = record.get("review") or {}
            for gate in REQUIRED_GATES:
                if (review.get(gate) or {}).get("status") != "verified":
                    failures.append(f"volume-{volume}:{page}: {gate} not verified")
            if not isinstance(record.get("blocks"), list):
                failures.append(f"volume-{volume}:{page}: blocks missing")
            if not isinstance(record.get("formulas"), list):
                failures.append(f"volume-{volume}:{page}: formulas missing")
            if not isinstance(record.get("tables"), list):
                failures.append(f"volume-{volume}:{page}: tables missing")
            expected = record.get("contentSha256")
            if not expected or expected != canonical_hash(record):
                failures.append(f"volume-{volume}:{page}: content hash mismatch")
            if not any(item.startswith(f"volume-{volume}:{page}:") for item in failures):
                verified += 1

    payload = {
        "requiredPages": sum(PAGE_COUNTS.values()),
        "verifiedPages": verified,
        "failureCount": len(failures),
        "complete": not failures and verified == sum(PAGE_COUNTS.values()),
        "failures": failures,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"verified={verified}/{payload['requiredPages']} failures={len(failures)}")
        for item in failures[:50]:
            print(item)
        if len(failures) > 50:
            print(f"... 另有 {len(failures) - 50} 项")
    if not payload["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

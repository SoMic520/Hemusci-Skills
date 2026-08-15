#!/usr/bin/env python3
"""Verify render artifacts and record an explicit all-page visual review decision."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ooxml_safety import sha256_file


def record(receipt_path: Path, status: str, reviewer: str, notes: str) -> dict:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") not in {"RENDERED_NOT_REVIEWED", "VISUAL_REVIEW_PASS", "VISUAL_REVIEW_FAIL"}:
        raise ValueError("Input is not a render receipt")
    docx = Path(str(receipt.get("docx", "")))
    if not docx.exists() or sha256_file(docx) != receipt.get("docx_sha256"):
        raise ValueError("Rendered DOCX is missing or its hash changed")
    pages = receipt.get("pages")
    if not isinstance(pages, list) or len(pages) != receipt.get("page_count"):
        raise ValueError("Render receipt page list is incomplete")
    expected_numbers = list(range(1, len(pages) + 1))
    if [row.get("page") for row in pages] != expected_numbers:
        raise ValueError("Render receipt page numbers are not contiguous")
    for row in pages:
        path = Path(str(row.get("path", "")))
        if not path.exists() or sha256_file(path) != row.get("sha256"):
            raise ValueError(f"Rendered page is missing or changed: {path}")
    receipt["status"] = f"VISUAL_REVIEW_{status}"
    receipt["visual_review"] = {
        "status": status,
        "reviewer": reviewer,
        "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "notes": notes,
        "pages_reviewed": expected_numbers,
    }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--status", choices=["PASS", "FAIL"], required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--notes", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = record(args.receipt, args.status, args.reviewer, args.notes)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"status": "ERROR", "error": str(exc)}
    if result.get("status") != "ERROR":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        for row in result.get("pages", []):
            page = Path(str(row.get("path", ""))).resolve()
            try:
                row["path"] = str(page.relative_to(args.out.parent.resolve()))
            except ValueError:
                row["path"] = str(page)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if result.get("status") != "ERROR":
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result.get("status") in {"VISUAL_REVIEW_PASS", "VISUAL_REVIEW_FAIL"} else 2


if __name__ == "__main__":
    sys.exit(main())

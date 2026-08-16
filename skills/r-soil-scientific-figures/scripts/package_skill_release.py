#!/usr/bin/env python3
"""Create a deterministic clean ZIP of this Codex skill."""

from __future__ import annotations

import argparse
import hashlib
import os
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def include(path: Path) -> bool:
    return (
        path.is_file()
        and not path.name.startswith("._")
        and path.suffix not in {".pyc", ".pyo"}
        and "__pycache__" not in path.parts
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not (root / "SKILL.md").is_file():
        raise SystemExit("SKILL.md is missing")
    catalog_rows = sum(1 for _ in (root / "references" / "figure-catalog.tsv").open(encoding="utf-8")) - 1
    if catalog_rows != 314:
        raise SystemExit(f"Expected 314 catalog rows, found {catalog_rows}")
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if not include(path):
                continue
            relative = Path(root.name) / path.relative_to(root)
            info = zipfile.ZipInfo.from_file(path, arcname=str(relative).replace(os.sep, "/"))
            info.date_time = (2026, 1, 1, 0, 0, 0)
            with path.open("rb") as handle:
                archive.writestr(info, handle.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            count += 1
    print(f"status=PASS files={count} bytes={output.stat().st_size} sha256={sha256(output)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

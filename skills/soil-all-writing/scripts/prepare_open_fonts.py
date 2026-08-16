#!/usr/bin/env python3
"""Download pinned open Chinese fonts for deterministic document/visual rendering."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request


FILES = {
    "NotoSerifCJKsc-Regular.otf": {
        "url": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Regular.otf",
        "sha256": "2a2eae2628df83556c54018c41e20fa532c1b862c5256ae8b3f23feb918d12ca",
        "role": "body",
    },
    "NotoSansCJKsc-Bold.otf": {
        "url": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf",
        "sha256": "b5f0d1a190a7f9b43c310a8850630af12553df32c4c050543f9059732d9b4c0a",
        "role": "heading",
    },
    "NotoSansCJKsc-Regular.otf": {
        "url": "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
        "sha256": "2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b",
        "role": "visual_body",
    },
}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for name, metadata in FILES.items():
        target = output / name
        if target.exists() and digest(target) != metadata["sha256"]:
            raise SystemExit(f"ERROR: existing font hash mismatch: {target}")
        if not target.exists():
            temporary = target.with_suffix(target.suffix + ".download")
            request = urllib.request.Request(metadata["url"], headers={"User-Agent": "soil-all-writing/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as handle:
                while chunk := response.read(1024 * 1024):
                    handle.write(chunk)
            if digest(temporary) != metadata["sha256"]:
                temporary.unlink(missing_ok=True)
                raise SystemExit(f"ERROR: downloaded font hash mismatch: {name}")
            temporary.replace(target)
        records.append({"file": str(target), "sha256": digest(target), **metadata})
    receipt = {
        "status": "PASS",
        "source_repository": "https://github.com/notofonts/noto-cjk",
        "license": "SIL Open Font License 1.1",
        "files": records,
    }
    if args.receipt:
        args.receipt.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.receipt.resolve().write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

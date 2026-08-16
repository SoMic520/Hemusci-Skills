#!/usr/bin/env python3
"""Execute every standalone recipe bundle and verify the delivery contract."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def test_one(root: Path, result_root: Path, row: dict[str, str]) -> dict[str, object]:
    recipe_id = row["id"]
    bundle = root / "recipes" / recipe_id
    target = result_root / recipe_id
    output = target / "outputs"
    derived = target / "derived"
    output.mkdir(parents=True, exist_ok=True)
    derived.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "Rscript",
            str(bundle / "figure.R"),
            "--out",
            str(output),
            "--derived",
            str(derived),
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    expected = [
        output / f"{recipe_id}.pdf",
        output / f"{recipe_id}.png",
        output / f"{recipe_id}.tiff",
        output / "figure-manifest.json",
        output / "session-info.txt",
        output / "caption-draft.txt",
        derived / "validated-input.csv",
        derived / "descriptive-summary.csv",
    ]
    missing = [path.name for path in expected if not path.is_file() or path.stat().st_size == 0]
    manifest_ok = False
    if (output / "figure-manifest.json").is_file():
        try:
            manifest = json.loads((output / "figure-manifest.json").read_text(encoding="utf-8"))
            manifest_ok = manifest.get("figure_id") == recipe_id
        except (OSError, json.JSONDecodeError):
            manifest_ok = False
    status = "PASS" if proc.returncode == 0 and not missing and manifest_ok else "FAIL"
    (target / "run.log").write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
    return {
        "id": recipe_id,
        "status": status,
        "exit_code": proc.returncode,
        "manifest_ok": manifest_ok,
        "missing": ";".join(missing),
        "stderr_tail": proc.stderr[-500:].replace("\n", " "),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("result_root", type=Path)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    root = args.library.expanduser().resolve()
    result_root = args.result_root.expanduser().resolve()
    result_root.mkdir(parents=True, exist_ok=True)
    with (root / "recipe-index.tsv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    results: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [pool.submit(test_one, root, result_root, row) for row in rows]
        for index, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if index % 25 == 0 or index == len(futures):
                failures = sum(item["status"] == "FAIL" for item in results)
                print(f"Tested {index}/{len(futures)} standalone bundles; failures: {failures}", flush=True)

    results.sort(key=lambda item: item["id"])
    fields = ["id", "status", "exit_code", "manifest_ok", "missing", "stderr_tail"]
    with (result_root / "standalone-bundle-qa.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
    failures = [item for item in results if item["status"] == "FAIL"]
    summary = {
        "status": "PASS" if not failures and len(results) == 314 else "FAIL",
        "expected": 314,
        "tested": len(results),
        "passed": sum(item["status"] == "PASS" for item in results),
        "failed": len(failures),
        "failures": failures,
        "scope": "standalone recipe entrypoint, PDF, PNG, LZW TIFF, manifest, session, caption and derived tables",
    }
    (result_root / "standalone-bundle-qa.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

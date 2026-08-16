#!/usr/bin/env python3
"""Build the complete independently runnable 314-recipe R figure library.

The individual bundles intentionally include their own renderer copy.  This is
larger than a shared-code distribution, but it makes every recipe folder
portable, auditable and runnable after extraction on macOS or Windows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "references" / "generated" / "recipe-registry.tsv"
BUILDER = ROOT / "scripts" / "build_figure_bundle.py"
MARKER = ".r-soil-complete-library"


def load_registry() -> list[dict[str, str]]:
    with REGISTRY.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def safe_prepare(path: Path, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not overwrite:
            raise SystemExit(f"Output exists and is not empty: {path}; use --overwrite")
        if not (path / MARKER).is_file():
            raise SystemExit(f"Refusing to overwrite unmarked output: {path}")
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    path.mkdir(parents=True, exist_ok=True)
    (path / MARKER).write_text("generated complete recipe library\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_zip(root: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name.startswith("._"):
                continue
            relative = Path(root.name) / path.relative_to(root)
            info = zipfile.ZipInfo.from_file(path, arcname=str(relative).replace(os.sep, "/"))
            info.date_time = (2026, 1, 1, 0, 0, 0)
            with path.open("rb") as handle:
                output.writestr(info, handle.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tested-render-dir", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--zip", action="store_true", dest="make_zip")
    args = parser.parse_args()

    output = args.output.expanduser().resolve()
    tested = args.tested_render_dir.expanduser().resolve() if args.tested_render_dir else None
    safe_prepare(output, args.overwrite)
    recipes_root = output / "recipes"
    gallery_root = output / "tested-gallery"
    environment_root = output / "environment"
    recipes_root.mkdir()
    gallery_root.mkdir()
    environment_root.mkdir()
    shutil.copy2(ROOT / "assets" / "library-README.md", output / "README.md")
    shutil.copy2(ROOT / "scripts" / "check_r_environment.py", environment_root / "check_r_environment.py")
    shutil.copy2(ROOT / "assets" / "install" / "install_macos.command", environment_root / "install_macos.command")
    shutil.copy2(ROOT / "assets" / "install" / "install_windows.ps1", environment_root / "install_windows.ps1")
    shutil.copy2(ROOT / "assets" / "install" / "README.md", environment_root / "README.md")

    rows = load_registry()
    index_rows: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    for position, row in enumerate(rows, start=1):
        recipe_id = row["id"]
        bundle = recipes_root / recipe_id
        command = [
            sys.executable,
            str(BUILDER),
            "--recipe",
            recipe_id,
            "--output",
            str(bundle),
            "--width-mm",
            "105",
            "--height-mm",
            "78",
            "--dpi",
            "600",
            "--layout",
            "auto",
        ]
        built = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
        if built.returncode:
            failures.append({"id": recipe_id, "error": (built.stderr or built.stdout)[-2000:]})
            continue

        tested_status = "NOT_SUPPLIED"
        tested_sha = ""
        if tested:
            source_png = tested / f"{recipe_id}.png"
            if source_png.is_file():
                target_png = gallery_root / source_png.name
                shutil.copy2(source_png, target_png)
                tested_status = "PASS"
                tested_sha = sha256(target_png)
                (bundle / "qa" / "full-library-render.json").write_text(
                    json.dumps(
                        {
                            "status": "PASS",
                            "scope": "full-library recipe render",
                            "recipe_id": recipe_id,
                            "tested_png": f"../../tested-gallery/{source_png.name}",
                            "sha256": tested_sha,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            else:
                tested_status = "MISSING"

        index_rows.append(
            {
                "sequence": str(position),
                "id": recipe_id,
                "name_en": row["name_en"],
                "name_zh": row["name_zh"],
                "primary_family": row["primary_family"],
                "schema_id": row["schema_id"],
                "renderer": row["renderer"],
                "tested_status": tested_status,
                "tested_png_sha256": tested_sha,
                "bundle_path": f"recipes/{recipe_id}",
            }
        )
        if position % 25 == 0 or position == len(rows):
            print(f"Built {position}/{len(rows)} recipe bundles; failures: {len(failures)}", flush=True)

    fields = list(index_rows[0]) if index_rows else ["id"]
    with (output / "recipe-index.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(index_rows)

    checksums = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name not in {"checksums.sha256", MARKER} and not path.name.startswith("._"):
            checksums.append(f"{sha256(path)}  {path.relative_to(output).as_posix()}")
    (output / "checksums.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")

    summary = {
        "status": "PASS" if not failures and len(index_rows) == len(rows) else "FAIL",
        "expected_recipes": len(rows),
        "built_recipes": len(index_rows),
        "tested_pass": sum(row["tested_status"] == "PASS" for row in index_rows),
        "failures": failures,
        "portable_platforms": ["macOS", "Windows"],
        "font_policy": "Chinese Songti-compatible; English Times New Roman-compatible; runtime fallback recorded in manifest",
        "typography_policy": "physical-size and panel-aware automatic typography; manual override remains available",
    }
    (output / "library-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    archive = output.with_suffix(".zip")
    if args.make_zip and summary["status"] == "PASS":
        write_zip(output, archive)
    print(json.dumps({**summary, "output": str(output), "archive": str(archive) if args.make_zip else None}, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

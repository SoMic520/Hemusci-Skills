#!/usr/bin/env python3
"""Generate, optionally execute, audit and zip a reproducible R figure bundle."""

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
SCHEMAS = ROOT / "references" / "input-schemas.tsv"
STANDARD_INPUTS = ROOT / "assets" / "standard-inputs"
R_ENGINE = ROOT / "assets" / "r-engine"


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_output(path: Path, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not overwrite:
            raise SystemExit(f"Output exists and is not empty: {path}; use --overwrite")
        # Only remove known generated bundle children, never an arbitrary directory tree.
        marker = path / ".r-soil-figure-bundle"
        if not marker.is_file():
            raise SystemExit(f"Refusing to overwrite unmarked directory: {path}")
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    path.mkdir(parents=True, exist_ok=True)
    (path / ".r-soil-figure-bundle").write_text("generated bundle\n", encoding="utf-8")


def run(command: list[str], cwd: Path, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def write_schema_row(path: Path, schema_id: str) -> None:
    rows = load_tsv(SCHEMAS)
    row = next(item for item in rows if item["schema_id"] == schema_id)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=row.keys(), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def zip_bundle(bundle: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(bundle.rglob("*")):
            if path.is_file() and not path.name.startswith("._"):
                arcname = Path(bundle.name) / path.relative_to(bundle)
                info = zipfile.ZipInfo.from_file(path, arcname=str(arcname).replace(os.sep, "/"))
                info.date_time = (2026, 1, 1, 0, 0, 0)
                with path.open("rb") as handle:
                    zf.writestr(info, handle.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--input", type=Path, help="Use a real CSV instead of the synthetic standard template")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--install-missing", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--zip", dest="make_zip", action="store_true")
    parser.add_argument("--width-mm", type=float, default=89)
    parser.add_argument("--height-mm", type=float, default=72)
    parser.add_argument("--dpi", type=int, default=600)
    parser.add_argument("--base-size-pt", type=float, default=None, help="Manual base size override in points")
    parser.add_argument(
        "--journal-profile",
        choices=("generic", "nature", "elsevier", "custom"),
        default="generic",
        help="Finished-size typography bounds; journal-specific guides still require live verification",
    )
    parser.add_argument("--min-size-pt", type=float, default=None, help="Override profile minimum finished text size")
    parser.add_argument("--max-size-pt", type=float, default=None, help="Override profile maximum finished text size")
    parser.add_argument(
        "--layout",
        choices=("auto", "single-column", "intermediate", "double-column", "full-page"),
        default="auto",
    )
    parser.add_argument("--panel-count", type=int, default=1)
    parser.add_argument("--facet-columns", type=int, default=None)
    parser.add_argument(
        "--show-title",
        action="store_true",
        help="Opt in to an internal Chinese title and English subtitle; journal figures omit these by default",
    )
    parser.add_argument(
        "--show-caption",
        action="store_true",
        help="Opt in to a short caption inside the graphics canvas; manuscript captions are separate by default",
    )
    args = parser.parse_args()

    if not REGISTRY.is_file():
        proc = run([sys.executable, str(ROOT / "scripts" / "build_recipe_registry.py")], ROOT)
        if proc.returncode:
            print(proc.stdout, end="")
            print(proc.stderr, file=sys.stderr, end="")
            return proc.returncode
    row = next((item for item in load_tsv(REGISTRY) if item["id"] == args.recipe), None)
    if not row:
        raise SystemExit(f"Unknown recipe: {args.recipe}")

    bundle = args.output.expanduser().resolve()
    safe_output(bundle, args.overwrite)
    for folder in ("config", "data", "derived", "lib", "outputs", "qa"):
        (bundle / folder).mkdir(exist_ok=True)

    shutil.copy2(R_ENGINE / "figure.R", bundle / "figure.R")
    shutil.copy2(R_ENGINE / "figure_engine.R", bundle / "lib" / "figure_engine.R")
    if (R_ENGINE / "renderers").is_dir():
        shutil.copytree(R_ENGINE / "renderers", bundle / "lib" / "renderers", dirs_exist_ok=True)
    shutil.copy2(R_ENGINE / "setup_packages.R", bundle / "setup_packages.R")
    shutil.copy2(ROOT / "scripts" / "audit_figure_bundle.py", bundle / "audit_figure_bundle.py")
    shutil.copy2(ROOT / "scripts" / "validate_render.py", bundle / "validate_render.py")
    template = STANDARD_INPUTS / f"{row['schema_id']}.csv"
    source_input = args.input.expanduser().resolve() if args.input else template
    if not source_input.is_file():
        raise SystemExit(f"Input not found: {source_input}")
    shutil.copy2(source_input, bundle / "data" / "input.csv")
    write_schema_row(bundle / "data" / "input-schema.tsv", row["schema_id"])

    config = {
        "schema_version": "2.0",
        "recipe_id": row["id"],
        "name_en": row["name_en"],
        "name_zh": row["name_zh"],
        "primary_family": row["primary_family"],
        "schema_id": row["schema_id"],
        "renderer": row["renderer"],
        "coverage_tier": row["coverage_tier"],
        "required_packages": row["required_packages"].split(";"),
        "source_keys": row["source_keys"].split(";"),
        "width_mm": args.width_mm,
        "height_mm": args.height_mm,
        "raster_dpi": args.dpi,
        "pdf_background": "white",
        "png_background": "white",
        "tiff_background": "white",
        "base_size_pt": args.base_size_pt,
        "typography_mode": "manual" if args.base_size_pt is not None else "auto",
        "journal_profile": args.journal_profile,
        "min_size_pt": args.min_size_pt,
        "max_size_pt": args.max_size_pt,
        "layout": args.layout,
        "panel_count": args.panel_count,
        "facet_columns": args.facet_columns,
        "show_title": args.show_title,
        "show_caption": args.show_caption,
        "experimental_unit": "Replace with the real experimental unit before publication",
        "replication": "Replace with independent n and technical-replicate handling",
        "pairing_blocking_nesting": "Replace with the real design structure",
    }
    config_path = bundle / "config" / "figure-config.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    provenance = {
        "bundle_schema": "1.0",
        "recipe_registry": str(REGISTRY),
        "input_source": str(source_input),
        "input_sha256": file_sha256(bundle / "data" / "input.csv"),
        "synthetic_standard_input": args.input is None,
        "reference_code_policy": "independently reimplemented after structural review; user scripts, data and images are not redistributed",
        "reference_review": "references/reference-archive-review.md and generated/reference-archive-audit.json in the source skill",
    }
    (bundle / "config" / "bundle-provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    execution: dict[str, object] = {"executed": False}
    if args.execute:
        if args.install_missing:
            setup = run([shutil.which("Rscript") or "Rscript", "--vanilla", "setup_packages.R"], bundle)
            execution["setup"] = {
                "exit_code": setup.returncode,
                "stdout": setup.stdout[-4000:],
                "stderr": setup.stderr[-4000:],
            }
            if setup.returncode:
                (bundle / "qa" / "execution.json").write_text(
                    json.dumps(execution, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                return setup.returncode
        rscript = shutil.which("Rscript")
        if not rscript:
            raise SystemExit("Rscript not found; run check_r_environment.py --install-r")
        rendered = run([rscript, "--vanilla", "figure.R"], bundle)
        execution["executed"] = True
        execution["render"] = {
            "exit_code": rendered.returncode,
            "stdout": rendered.stdout[-8000:],
            "stderr": rendered.stderr[-8000:],
        }
        if rendered.returncode == 0:
            pdf = bundle / "outputs" / f"{args.recipe}.pdf"
            png = bundle / "outputs" / f"{args.recipe}.png"
            tiff = bundle / "outputs" / f"{args.recipe}.tiff"
            tiff_ok = tiff.is_file() and tiff.stat().st_size > 0
            if not tiff_ok:
                execution["tiff_error"] = "600 dpi white-background LZW TIFF was not generated"
            audit = run(
                [sys.executable, "audit_figure_bundle.py", "--script", "lib/figure_engine.R", "--figure", str(pdf),
                 "--manifest", "outputs/figure-manifest.json"], bundle
            )
            layout = run(
                [sys.executable, "validate_render.py", "--image", str(png), "--config", str(config_path)], bundle
            )
            (bundle / "qa" / "structural-audit.json").write_text(audit.stdout, encoding="utf-8")
            (bundle / "qa" / "render-audit.json").write_text(layout.stdout, encoding="utf-8")
            execution["audit_exit_code"] = audit.returncode
            execution["render_audit_exit_code"] = layout.returncode
            execution["status"] = "PASS" if tiff_ok and audit.returncode == 0 and layout.returncode == 0 else "FAIL"
        else:
            execution["status"] = "FAIL"
        (bundle / "qa" / "execution.json").write_text(
            json.dumps(execution, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if execution["status"] != "PASS":
            print(json.dumps(execution, ensure_ascii=False, indent=2))
            return 1

    archive = bundle.with_suffix(".zip")
    if args.make_zip:
        zip_bundle(bundle, archive)
    print(
        json.dumps(
            {
                "status": "PASS",
                "bundle": str(bundle),
                "archive": str(archive) if args.make_zip else None,
                "recipe": args.recipe,
                "coverage_tier": row["coverage_tier"],
                "executed": args.execute,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build, validate, and render one QA artifact for every fallback format profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], env: dict[str, str] | None = None) -> str:
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(value: str) -> str:
    return value.lower().replace(".", "-").replace("_", "-")


def build_spec(route: dict, profile: dict, role_labels: dict[str, str], genre_label: str) -> dict:
    content: list[dict[str, object]] = []
    for index, role in enumerate(route["required_roles"], 1):
        content.extend([
            {"type": "heading", "level": 1 if index == 1 else 2, "role": role, "text": f"{index} {role_labels[role]}"},
            {
                "type": "paragraph",
                "role": role,
                "text": "本段验证中文字体、字号、行距、缩进和分页，不构成科学结论。",
            },
        ])
    include_toc = profile["toc_mode"] in {"optional", "required_for_long_form"}
    return {
        "schema_version": 1,
        "document_id": f"QA-{route['id']}",
        "genre_profile_id": route["id"],
        "lifecycle_stage": "draft",
        "controlled_template": {"state": "not_required_or_not_received", "registry_id": "UNRESOLVED", "snapshot_sha256": ""},
        "title": f"{genre_label}格式配置验证",
        "subtitle": "soil-all-writing 内部工程测试",
        "metadata": [
            {"label": "编制单位", "value": "soil-all-writing"},
            {"label": "版本", "value": "内部测试"},
            {"label": "日期", "value": "2026-08-16"},
        ],
        "running_header": f"{genre_label}格式配置验证",
        "include_toc": include_toc,
        "content": content,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--font-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=96)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    profiles_path = ROOT / "assets/genre-artifact-profiles.json"
    try:
        registry = json.loads(profiles_path.read_text(encoding="utf-8"))
        language_profiles = json.loads((ROOT / "assets/genre-language-profiles.json").read_text(encoding="utf-8"))
        genre_labels = {item["id"]: item["genre"] for item in language_profiles["profiles"]}
        role_labels = registry["role_labels_zh"]
        by_profile = {item["id"]: item for item in registry["format_profiles"]}
        routes = registry["genre_routes"]
        representative: dict[str, dict] = {}
        for route in routes:
            representative.setdefault(route["format_profile_id"], route)
        env = os.environ.copy()
        env["SOIL_BODY_FONT_ZH"] = "Noto Serif CJK SC"
        env["SOIL_HEADING_FONT_ZH"] = "Noto Sans CJK SC"
        env["SOIL_VISUAL_FONT_ZH"] = "Noto Sans CJK SC"
        node = shutil.which("node")
        if not node:
            raise RuntimeError("node is required")
        records: list[dict[str, object]] = []

        for profile_id, route in representative.items():
            profile = by_profile[profile_id]
            if profile["artifact_kind"] != "docx":
                continue
            item_dir = output / slug(profile_id)
            item_dir.mkdir(parents=True, exist_ok=True)
            spec = build_spec(route, profile, role_labels, genre_labels[route["id"]])
            spec_path = item_dir / "spec.json"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            final_docx = item_dir / "artifact.docx"
            render_dir = item_dir / "render"
            if spec["include_toc"]:
                first_docx = item_dir / "artifact-pass1.docx"
                first_render = item_dir / "render-pass1"
                run([
                    node, "scripts/build_chinese_professional_document.js", "--spec", str(spec_path),
                    "--profiles", str(profiles_path), "--output", str(first_docx),
                ], env=env)
                run([
                    sys.executable, "scripts/render_artifact.py", str(first_docx), "--output-dir", str(first_render),
                    "--emit-pdf", "--dpi", str(args.dpi), "--font-dir", str(args.font_dir.resolve()),
                ])
                toc_map = item_dir / "toc-page-map.json"
                cover_pages = "0" if profile["cover_mode"] == "none" else "1"
                run([
                    sys.executable, "scripts/derive_toc_page_map.py", "--spec", str(spec_path),
                    "--pdf", str(first_render / "artifact-pass1.pdf"), "--output", str(toc_map),
                    "--cover-pages", cover_pages,
                ])
                run([
                    node, "scripts/build_chinese_professional_document.js", "--spec", str(spec_path),
                    "--profiles", str(profiles_path), "--toc-page-map", str(toc_map), "--output", str(final_docx),
                ], env=env)
            else:
                run([
                    node, "scripts/build_chinese_professional_document.js", "--spec", str(spec_path),
                    "--profiles", str(profiles_path), "--output", str(final_docx),
                ], env=env)
            run([
                sys.executable, "scripts/validate_chinese_professional_document.py", str(final_docx),
                "--spec", str(spec_path), "--profiles", str(profiles_path),
            ])
            run([sys.executable, "scripts/audit_chinese_professional_style.py", str(final_docx), "--genre", route["id"]])
            receipt_path = item_dir / "render-receipt.json"
            receipt_raw = run([
                sys.executable, "scripts/render_artifact.py", str(final_docx), "--output-dir", str(render_dir),
                "--emit-pdf", "--dpi", str(args.dpi), "--font-dir", str(args.font_dir.resolve()),
                "--receipt", str(receipt_path),
            ])
            receipt = json.loads(receipt_raw)
            pdf_path = Path(receipt["pdf"])
            records.append({
                "profile_id": profile_id,
                "representative_genre": route["id"],
                "artifact_kind": "docx",
                "editable_path": str(final_docx),
                "editable_sha256": sha256(final_docx),
                "pdf_path": str(pdf_path),
                "pdf_sha256": sha256(pdf_path),
                "page_count": receipt["page_count"],
                "render_receipt": str(receipt_path),
                "visual_review": "pending",
            })

        for spec_name in ("professional-visual-spec-template.json", "oral-presentation-spec-template.json"):
            spec_path = ROOT / "assets" / spec_name
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            route = next(item for item in routes if item["id"] == spec["genre_profile_id"])
            profile = by_profile[route["format_profile_id"]]
            item_dir = output / slug(profile["id"])
            item_dir.mkdir(parents=True, exist_ok=True)
            pptx_path = item_dir / "artifact.pptx"
            render_dir = item_dir / "render"
            run([
                node, "scripts/build_chinese_scientific_visual.js", "--spec", str(spec_path),
                "--profiles", str(profiles_path), "--output", str(pptx_path),
            ], env=env)
            run([
                sys.executable, "scripts/validate_chinese_scientific_visual.py", str(pptx_path),
                "--spec", str(spec_path), "--profiles", str(profiles_path), "--allow-placeholders",
            ])
            receipt_path = item_dir / "render-receipt.json"
            receipt_raw = run([
                sys.executable, "scripts/render_artifact.py", str(pptx_path), "--output-dir", str(render_dir),
                "--emit-pdf", "--dpi", str(args.dpi), "--font-dir", str(args.font_dir.resolve()),
                "--font-profile", "visual", "--receipt", str(receipt_path),
            ])
            receipt = json.loads(receipt_raw)
            pdf_path = Path(receipt["pdf"])
            records.append({
                "profile_id": profile["id"],
                "representative_genre": route["id"],
                "artifact_kind": profile["artifact_kind"],
                "editable_path": str(pptx_path),
                "editable_sha256": sha256(pptx_path),
                "pdf_path": str(pdf_path),
                "pdf_sha256": sha256(pdf_path),
                "page_count": receipt["page_count"],
                "render_receipt": str(receipt_path),
                "visual_review": "pending",
            })

        manifest = {
            "schema_version": 1,
            "status": "structural_render_pass_visual_review_pending",
            "profile_count": len(records),
            "genre_route_count": len(routes),
            "font_dir": str(args.font_dir.resolve()),
            "records": records,
        }
        manifest_path = output / "qa-manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "PASS", "manifest": str(manifest_path), "profiles": len(records), "genre_routes": len(routes)}, ensure_ascii=False))
        return 0
    except (OSError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

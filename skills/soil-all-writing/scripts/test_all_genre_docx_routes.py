#!/usr/bin/env python3
"""Build and validate a DOCX smoke artifact for every DOCX-routed genre."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], env: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, default=ROOT / "assets/genre-artifact-profiles.json")
    args = parser.parse_args()
    node = shutil.which("node")
    if not node:
        print("ERROR: node is required")
        return 1
    try:
        registry = json.loads(args.profiles.read_text(encoding="utf-8"))
        by_profile = {item["id"]: item for item in registry["format_profiles"]}
        routes = registry["genre_routes"]
        docx_routes = [route for route in routes if by_profile[route["format_profile_id"]]["artifact_kind"] == "docx"]
        visual_routes = {route["id"] for route in routes if by_profile[route["format_profile_id"]]["artifact_kind"] != "docx"}
        if visual_routes != {"academic_poster", "oral_presentation"}:
            raise RuntimeError(f"unexpected non-DOCX routes: {sorted(visual_routes)}")
        env = os.environ.copy()
        env["SOIL_BODY_FONT_ZH"] = "Noto Serif CJK SC"
        env["SOIL_HEADING_FONT_ZH"] = "Noto Sans CJK SC"
        with tempfile.TemporaryDirectory(prefix="soil-all-writing-docx-routes-") as temp_name:
            temp = Path(temp_name)
            for route in docx_routes:
                genre = route["id"]
                content: list[dict[str, object]] = []
                for index, role in enumerate(route["required_roles"], 1):
                    content.extend([
                        {"type": "heading", "level": 1 if index == 1 else 2, "role": role, "text": f"{index} {role}"},
                        {
                            "type": "paragraph",
                            "role": role,
                            "text": "本段用于验证题材路由、中文字号、段落样式和受控结构；不代表正式科学结论。",
                        },
                    ])
                spec = {
                    "schema_version": 1,
                    "document_id": f"SMOKE-{genre}",
                    "genre_profile_id": genre,
                    "lifecycle_stage": "draft",
                    "controlled_template": {"state": "not_required_or_not_received", "registry_id": "UNRESOLVED", "snapshot_sha256": ""},
                    "title": f"{genre} 格式路由测试",
                    "subtitle": "",
                    "metadata": [
                        {"label": "编制单位", "value": "测试单位"},
                        {"label": "版本", "value": "内部测试"},
                        {"label": "日期", "value": "2026-08-16"},
                    ],
                    "running_header": "",
                    "include_toc": False,
                    "content": content,
                }
                spec_path = temp / f"{genre}.json"
                docx_path = temp / f"{genre}.docx"
                spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
                run([
                    node, "scripts/build_chinese_professional_document.js",
                    "--spec", str(spec_path), "--profiles", str(args.profiles.resolve()),
                    "--output", str(docx_path),
                ], env=env)
                run([
                    shutil.which("python3") or "python3", "scripts/validate_chinese_professional_document.py",
                    str(docx_path), "--spec", str(spec_path), "--profiles", str(args.profiles.resolve()),
                ])
        print(f"PASS: built and validated {len(docx_routes)} DOCX genre routes; visual routes are tested separately")
        return 0
    except (OSError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

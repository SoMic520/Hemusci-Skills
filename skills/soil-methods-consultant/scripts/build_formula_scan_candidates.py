#!/usr/bin/env python3
"""Build resumable formula/layout candidates for scanned source pages."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any


BOOKS = {"lu-rukkun": 665, "technical-spec": 267}
TRIGGER = re.compile(r"=|计算|公式|式中|方程|反应式|mol|kg|L[⁻\-~一]", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--book", choices=tuple(BOOKS), required=True)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def json_path(directory: Path, page: int) -> Path:
    for width in (4, 3, 2, 0):
        name = f"page-{page:0{width}d}.json" if width else f"page-{page}.json"
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return directory / f"page-{page:03d}.json"


def page_text(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    return "\n".join(str(line.get("text") or "") for line in data.get("lines", []))


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def payload(result: Any) -> dict[str, Any]:
    value = result.json
    if not isinstance(value, dict) or not isinstance(value.get("res"), dict):
        raise ValueError("公式识别返回格式异常")
    return value["res"]


def main() -> None:
    config = parse_args()
    work = config.work_root / config.book
    selected = []
    end = config.end or BOOKS[config.book]
    if config.start < 1 or end > BOOKS[config.book] or config.start > end:
        raise SystemExit("invalid --start/--end range")
    for page in range(config.start, end + 1):
        vision = json_path(work / "vision", page)
        if TRIGGER.search(page_text(vision)):
            selected.append(page)

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import FormulaRecognitionPipeline

    engine = FormulaRecognitionPipeline(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_layout_detection=True,
        layout_detection_model_name="PP-DocLayout_plus-L",
        formula_recognition_model_name="PP-FormulaNet_plus-M",
    )
    output = work / "formula"
    output.mkdir(parents=True, exist_ok=True)
    completed = failures = 0
    print(f"engine_ready pages {len(selected)}", flush=True)
    for index, page in enumerate(selected, 1):
        destination = output / f"page-{page:03d}.json"
        if destination.is_file() and not config.force:
            continue
        image = work / "images" / f"page-{page:03d}.jpg"
        try:
            results = engine.predict(str(image))
            if len(results) != 1:
                raise ValueError(f"预期1个页面结果，实际{len(results)}")
            raw = payload(results[0])
            formulas = raw.get("formula_res_list") or []
            atomic_json(destination, {
                "page": page,
                "engine": "PP-DocLayout_plus-L + PP-FormulaNet_plus-M",
                "formulas": formulas,
            })
            completed += 1
            if index % 10 == 0:
                print(f"{index}/{len(selected)} page={page} formulas={len(formulas)}", flush=True)
        except Exception as error:
            failures += 1
            print(f"ERROR {config.book}:{page}: {error!r}", flush=True)
    print(f"completed={completed} failures={failures}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

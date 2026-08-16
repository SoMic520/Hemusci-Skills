#!/usr/bin/env python3
"""Build resumable machine drafts for page-by-page human correction.

This is a build-time tool.  Its output is never accepted as verified content.
The final corpus builder must consume separately reviewed correction records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path("/Users/jia-haozhou/Desktop/书籍电子化/site/public/books")
DEFAULT_OUTPUT = Path("/Users/jia-haozhou/Desktop/书籍电子化/output/qa/ppstructure-v3")
PAGE_COUNTS = {1: 557, 2: 358}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成全书逐页校正底稿；输出始终标记为 machine_draft。")
    parser.add_argument("--volume", choices=("all", "1", "2"), default="all")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--without-tables", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def selected_pages(args: argparse.Namespace) -> list[tuple[int, int]]:
    volumes = (1, 2) if args.volume == "all" else (int(args.volume),)
    pages: list[tuple[int, int]] = []
    for volume in volumes:
        end = min(args.end or PAGE_COUNTS[volume], PAGE_COUNTS[volume])
        if args.start < 1 or end < args.start:
            raise ValueError(f"无效页码范围: {args.start}-{end}")
        pages.extend((volume, page) for page in range(args.start, end + 1))
    return pages[: args.limit] if args.limit else pages


def json_result(result: Any) -> dict[str, Any]:
    payload = result.json
    if not isinstance(payload, dict) or not isinstance(payload.get("res"), dict):
        raise ValueError("PP-StructureV3 返回格式异常")
    return payload["res"]


def main() -> None:
    args = parse_args()
    pages = selected_pages(args)
    if not pages:
        raise SystemExit("没有待处理页面")

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
    from paddleocr import PPStructureV3

    engine = PPStructureV3(
        layout_detection_model_name="PP-DocLayout-S",
        formula_recognition_model_name="PP-FormulaNet_plus-S",
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        use_seal_recognition=False,
        use_table_recognition=not args.without_tables,
        use_formula_recognition=True,
        use_chart_recognition=False,
        use_region_detection=False,
    )

    completed = 0
    failures = 0
    for index, (volume, page) in enumerate(pages, 1):
        book_id = f"volume-{volume}"
        source = args.source_root / book_id / "pages" / f"page-{page:04d}.jpg"
        destination = args.output_root / book_id / f"page-{page:04d}.json"
        if destination.exists() and not args.force:
            print(f"[{index}/{len(pages)}] skip {book_id}:{page}", flush=True)
            continue
        started = time.monotonic()
        try:
            if not source.is_file():
                raise FileNotFoundError(source)
            results = list(engine.predict(str(source)))
            if len(results) != 1:
                raise ValueError(f"预期 1 个页面结果，实际 {len(results)}")
            result = results[0]
            raw = json_result(result)
            markdown = result.markdown.get("markdown_texts", "")
            record = {
                "schema": "soil-methods-consultant.correction-draft.v1",
                "status": "machine_draft",
                "warning": "不得作为最终内容；必须逐页目视校正并完成第二遍复核。",
                "bookId": book_id,
                "page": page,
                "sourceImageSha256": sha256(source),
                "engine": {
                    "pipeline": "PP-StructureV3",
                    "layout": "PP-DocLayout-S",
                    "textDetection": "PP-OCRv5_mobile_det",
                    "textRecognition": "PP-OCRv5_mobile_rec",
                    "formula": "PP-FormulaNet_plus-S",
                    "tableRecognition": not args.without_tables,
                },
                "processingSeconds": round(time.monotonic() - started, 3),
                "markdownText": markdown,
                "structuredResult": raw,
            }
            atomic_json(destination, record)
            formula_count = len(raw.get("formula_res_list") or [])
            table_count = len(raw.get("table_res_list") or [])
            completed += 1
            print(
                f"[{index}/{len(pages)}] {book_id}:{page} "
                f"formulas={formula_count} tables={table_count} "
                f"seconds={record['processingSeconds']}",
                flush=True,
            )
        except Exception as error:
            failures += 1
            print(f"[{index}/{len(pages)}] ERROR {book_id}:{page}: {error!r}", flush=True)
    print(f"completed={completed} failures={failures}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

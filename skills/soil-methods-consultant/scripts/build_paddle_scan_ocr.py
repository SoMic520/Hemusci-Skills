#!/usr/bin/env python3
"""Run a third, high-accuracy OCR pass over the two scanned soil monographs.

This build-time helper writes resumable JSON candidates.  The candidates are
never runtime data by themselves; ``build_external_corpora.py`` reconciles
them with Apple Vision, Tesseract, formula recognition, and review overrides.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any


BOOKS = {
    "lu-rukkun": list(range(1, 666)),
    "technical-spec": list(range(1, 268)),
    "microbiome": [
        *range(84, 91), *range(112, 122), *range(215, 226), *range(248, 256),
        *range(277, 283), *range(298, 303), *range(312, 324), *range(360, 366),
    ],
    "gbz170": list(range(1, 25)),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--book", choices=("all", *BOOKS), default="all")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--model", choices=("mobile", "server"), default="mobile")
    return parser.parse_args()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def result_payload(result: Any) -> dict[str, Any]:
    payload = result.json
    if not isinstance(payload, dict) or not isinstance(payload.get("res"), dict):
        raise ValueError("PaddleOCR返回格式异常")
    return payload["res"]


def image_path(directory: Path, page: int) -> Path:
    for suffix in ("jpg", "png"):
        for width in (4, 3, 2, 0):
            number = f"{page:0{width}d}" if width else str(page)
            candidate = directory / f"page-{number}.{suffix}"
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(f"page image {directory}:{page}")


def main() -> None:
    config = parse_args()
    selected = BOOKS if config.book == "all" else {config.book: BOOKS[config.book]}
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    from paddleocr import PaddleOCR

    engine = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_detection_model_name=f"PP-OCRv5_{config.model}_det",
        text_recognition_model_name=f"PP-OCRv5_{config.model}_rec",
        text_recognition_batch_size=16,
    )
    completed = failures = 0
    for book, source_pages in selected.items():
        pages = [page for page in source_pages if page >= config.start and (config.end is None or page <= config.end)]
        output = config.work_root / book / "paddle"
        output.mkdir(parents=True, exist_ok=True)
        for index, page in enumerate(pages, 1):
            destination = output / f"page-{page:03d}.json"
            if destination.is_file() and not config.force:
                continue
            source = image_path(config.work_root / book / "images", page)
            started = time.monotonic()
            try:
                results = list(engine.predict(str(source)))
                if len(results) != 1:
                    raise ValueError(f"预期1个页面结果，实际{len(results)}")
                raw = result_payload(results[0])
                texts = raw.get("rec_texts") or []
                scores = raw.get("rec_scores") or []
                boxes = raw.get("rec_boxes") or []
                lines = []
                for text, score, box in zip(texts, scores, boxes):
                    lines.append({
                        "text": str(text),
                        "confidence": round(float(score), 6),
                        "box": [int(value) for value in box],
                    })
                lines.sort(key=lambda item: (item["box"][1], item["box"][0]))
                atomic_json(destination, {
                    "page": page,
                    "engine": f"PP-OCRv5_{config.model}_det + PP-OCRv5_{config.model}_rec",
                    "processingSeconds": round(time.monotonic() - started, 3),
                    "lines": lines,
                })
                completed += 1
                print(f"{book} {index}/{len(pages)} page={page} lines={len(lines)} seconds={time.monotonic()-started:.2f}", flush=True)
            except Exception as error:
                failures += 1
                print(f"ERROR {book}:{page}: {error!r}", flush=True)
    print(f"completed={completed} failures={failures}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

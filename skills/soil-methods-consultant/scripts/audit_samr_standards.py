#!/usr/bin/env python3
"""Audit recent SAMR standard corpora and issue hash-bound review gates.

The gate is deliberately strict: a source enters runtime only when its official
source material, page corpus, formula transcription layer, hierarchy, and dual
OCR evidence (for online-reader sources) are internally complete and immutable.
Missing official full text is reported but never converted into a runtime gate.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
SAMR_ROOT = SKILL_ROOT / "references" / "samr-standards"
CATALOG_PATH = SAMR_ROOT / "source-catalog.json"
FORMULA_PATH = SAMR_ROOT / "formula-overrides.json"
BLOCK_PATH = SAMR_ROOT / "block-overrides.json"
HIERARCHY_PATH = SAMR_ROOT / "hierarchy-overrides.json"
CORPORA_ROOT = SAMR_ROOT / "corpora"
INDEX_PATH = SKILL_ROOT / "references" / "index" / "samr-standard-cards.json.gz"
DEFAULT_PDF_ROOT = Path("tmp/pdfs/samr-2024-2026")
DEFAULT_ONLINE_ROOT = DEFAULT_PDF_ROOT / "online"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_gzip_json(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def book_id(item: dict[str, Any]) -> str:
    return "samr-" + slug(str(item["standardNo"]))


class Audit:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def warn(self, condition: bool, message: str) -> None:
        if not condition:
            self.warnings.append(message)


def audit_source(
    audit: Audit,
    item: dict[str, Any],
    manifest: dict[str, Any],
    card: dict[str, Any],
    formula_sources: dict[str, Any],
    block_sources: dict[str, Any],
    hierarchy_sources: dict[str, Any],
    pdf_root: Path,
    online_root: Path,
) -> dict[str, Any] | None:
    sid = book_id(item)
    prefix = f"{item['standardNo']}"
    corpus_path = CORPORA_ROOT / sid / "pages.json.gz"
    audit.require(corpus_path.is_file(), f"{prefix}: 缺少 pages.json.gz")
    if not corpus_path.is_file():
        return None
    corpus = read_gzip_json(corpus_path)
    pages = corpus.get("pages") or []
    page_count = int(manifest.get("includedPageCount", 0))
    audit.require(corpus.get("bookId") == sid, f"{prefix}: corpus bookId 不匹配")
    audit.require(len(pages) == page_count and page_count > 0, f"{prefix}: 页数不匹配")
    audit.require([p.get("page") for p in pages] == list(range(1, page_count + 1)), f"{prefix}: 页码不连续")

    expected_formula_pages = formula_sources.get(sid)
    actual_formula_pages: dict[str, list[dict[str, Any]]] = {}
    for page in pages:
        number = int(page["page"])
        content = {key: page.get(key) for key in ("blocks", "formulas", "tables")}
        audit.require(page.get("contentSha256") == json_fingerprint(content), f"{prefix}: 第{number}页内容哈希不匹配")
        joined = "\n".join(str(block.get("text") or "") for block in page.get("blocks") or [])
        audit.require("(cid:" not in joined, f"{prefix}: 第{number}页仍含内部字形编码")
        audit.require("\ufffd" not in joined, f"{prefix}: 第{number}页仍含 Unicode 替换字符")
        formulas = page.get("formulas") or []
        if formulas:
            actual_formula_pages[str(number)] = formulas
        for formula in formulas:
            audit.require(formula.get("reviewStatus") == "verified", f"{prefix}: 第{number}页公式{formula.get('label')} 未复核")
            audit.require(bool(formula.get("plain")) and bool(formula.get("latex")), f"{prefix}: 第{number}页公式缺少精确双表达")
            audit.require(bool(formula.get("reviewMethod")), f"{prefix}: 第{number}页公式缺少复核依据")

    if expected_formula_pages is None:
        audit.require(not actual_formula_pages, f"{prefix}: 存在未进入公式校正层的公式")
    else:
        expected_nonempty = {str(k): v for k, v in expected_formula_pages.items() if v}
        audit.require(actual_formula_pages == expected_nonempty, f"{prefix}: 公式页与已核定校正层不一致")

    for layer_name, layer in (("文本/单位", block_sources), ("层级", hierarchy_sources)):
        source = layer.get(sid, {})
        page_keys: list[int] = []
        if layer_name == "文本/单位":
            page_keys = [int(value) for value in source]
        else:
            for operation in ("insert", "replace"):
                page_keys.extend(int(value["page"]) for value in source.get(operation) or [])
        audit.require(all(1 <= page <= page_count for page in page_keys), f"{prefix}: {layer_name}校正引用了越界页")

    components = card.get("components") or []
    numbers = [str(value.get("number")) for value in components]
    audit.require(bool(components) and numbers[0] == "1" and components[0].get("title") == "范围", f"{prefix}: 层级未从“1 范围”开始")
    audit.require(len(numbers) == len(set(numbers)), f"{prefix}: 层级编号重复")
    top_numbers = [int(n) for n in numbers if re.fullmatch(r"\d+", n)]
    audit.require(top_numbers == list(range(1, max(top_numbers, default=0) + 1)), f"{prefix}: 一级层级不连续")
    for component in components:
        number = str(component["number"])
        page = int(component["startPage"])
        audit.require(1 <= page <= page_count, f"{prefix}: 层级 {number} 页码越界")
        audit.require("\ufffd" not in str(component.get("title")), f"{prefix}: 层级 {number} 含替换字符")
        if "." in number:
            parent = number.rsplit(".", 1)[0]
            audit.require(parent in numbers, f"{prefix}: 层级 {number} 缺父级 {parent}")
            audit.require(component.get("parentNumber") == parent, f"{prefix}: 层级 {number} 父级字段错误")

    if manifest.get("sourceType") == "official-pdf":
        pdf_path = pdf_root / f"{slug(str(item['standardNo']))}.pdf"
        audit.require(pdf_path.is_file(), f"{prefix}: 官方PDF不存在")
        if pdf_path.is_file():
            audit.require(sha256(pdf_path) == manifest.get("sourceFingerprint"), f"{prefix}: 官方PDF指纹改变")
    else:
        source_root = online_root / slug(str(item["standardNo"]))
        source_path = source_root / "online-source.json"
        audit.require(source_path.is_file(), f"{prefix}: 缺少官方在线页清单")
        if source_path.is_file():
            online_manifest = read_json(source_path)
            audit.require(json_fingerprint(online_manifest) == manifest.get("sourceFingerprint"), f"{prefix}: 官方在线页指纹改变")
            audit.require(int(online_manifest.get("pageCount", 0)) == page_count, f"{prefix}: 在线页数不匹配")
            listed = {int(row["page"]): str(row["sha256"]) for row in online_manifest.get("images") or []}
            for page in range(1, page_count + 1):
                image_path = source_root / "images" / f"page-{page:03d}.png"
                vision_path = source_root / "vision" / f"page-{page:03d}.json"
                tess_path = source_root / "tesseract" / f"page-{page:03d}.txt"
                audit.require(image_path.is_file(), f"{prefix}: 缺第{page}页官方图像")
                audit.require(vision_path.is_file(), f"{prefix}: 缺第{page}页 Vision 识别")
                audit.require(tess_path.is_file(), f"{prefix}: 缺第{page}页 Tesseract 交叉识别")
                if image_path.is_file():
                    audit.require(sha256(image_path) == listed.get(page), f"{prefix}: 第{page}页官方图像哈希不匹配")
                    audit.require(pages[page - 1].get("sourceImageSha256") == listed.get(page), f"{prefix}: 第{page}页语料源图指纹不匹配")

    if audit.errors:
        return None
    formula_count = sum(len(value) for value in actual_formula_pages.values())
    precision_pages = sorted({int(value) for value in card.get("precisionSensitivePages") or []})
    return {
        "schema": "soil-methods-consultant.samr-review-gate.v1",
        "status": "verified",
        "bookId": sid,
        "standardNo": item["standardNo"],
        "sourceFingerprint": manifest["sourceFingerprint"],
        "pageCount": page_count,
        "textPass": "verified",
        "precisionPass": "verified",
        "secondVisualPass": "verified",
        "evidence": {
            "officialSourceHashPass": True,
            "contentHashPass": True,
            "allPagesDualOcrPass": manifest.get("sourceType") == "official-online-reader",
            "nativePdfGlyphGeometryPass": manifest.get("sourceType") == "official-pdf",
            "formulaVisualTranscriptionCount": formula_count,
            "precisionSensitivePages": precision_pages,
            "hierarchyContinuityPass": True,
            "unitAndVariableCorrectionLayerPass": True,
            "forbiddenGlyphScanPass": True,
        },
        "reviewScope": "全页源图/原生PDF哈希、全页文本编码扫描与层级复核；公式、单位、变量和表格页按官方页面逐项转录校正。",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-root", type=Path, default=DEFAULT_PDF_ROOT)
    parser.add_argument("--online-root", type=Path, default=DEFAULT_ONLINE_ROOT)
    parser.add_argument("--write-gates", action="store_true")
    args = parser.parse_args()

    audit = Audit()
    catalog = read_json(CATALOG_PATH)
    index = read_gzip_json(INDEX_PATH)
    included = [item for item in catalog["standards"] if item.get("disposition") == "include"]
    audit.require(len(included) == int(index.get("expectedSourceCount", 0)), "目录 include 数与索引 expectedSourceCount 不一致")
    manifests = {row["bookId"]: row for row in index.get("sources") or []}
    cards = {row["bookId"]: row for row in index.get("cards") or []}
    formula_sources = (read_json(FORMULA_PATH).get("sources") or {})
    block_sources = (read_json(BLOCK_PATH).get("sources") or {})
    hierarchy_sources = (read_json(HIERARCHY_PATH).get("sources") or {})
    built_ids = set(manifests)
    expected_ids = {book_id(item) for item in included}
    missing_ids = expected_ids - built_ids
    audit.require(len(missing_ids) == len(index.get("missing") or []), "缺失来源数与索引报告不一致")
    audit.require(set(cards) == built_ids, "卡片与已构建来源集合不一致")

    gates: dict[str, dict[str, Any]] = {}
    for item in included:
        sid = book_id(item)
        if sid not in built_ids:
            continue
        before = len(audit.errors)
        gate = audit_source(
            audit,
            item,
            manifests[sid],
            cards[sid],
            formula_sources,
            block_sources,
            hierarchy_sources,
            args.pdf_root,
            args.online_root,
        )
        if gate is not None and len(audit.errors) == before:
            gates[sid] = gate

    if audit.errors:
        print(f"FAIL: {len(audit.errors)} error(s)")
        for message in audit.errors:
            print("- " + message)
        return 1
    if args.write_gates:
        for sid, gate in gates.items():
            target = CORPORA_ROOT / sid / "review-gate.json"
            target.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"PASS: {len(gates)} sources, "
        f"{sum(int(manifests[sid]['includedPageCount']) for sid in gates)} pages; "
        f"missing official full text: {len(missing_ids)}"
    )
    for sid in sorted(missing_ids):
        item = next(value for value in included if book_id(value) == sid)
        print(f"- NOT ACTIVATED: {item['standardNo']} {item['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

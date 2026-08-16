#!/usr/bin/env python3
"""Build PDF-independent corpora for recent method standards from SAMR.

The build accepts either an official downloaded PDF or page images reconstructed
from the official online reader.  Runtime data never depends on either source.
Every standard remains a separate bookId and is enabled only by a matching
review gate.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import re
import statistics
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any

import pdfplumber
from PIL import Image


SKILL_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = SKILL_ROOT / "references" / "samr-standards" / "source-catalog.json"
FORMULA_OVERRIDES_PATH = SKILL_ROOT / "references" / "samr-standards" / "formula-overrides.json"
BLOCK_OVERRIDES_PATH = SKILL_ROOT / "references" / "samr-standards" / "block-overrides.json"
HIERARCHY_OVERRIDES_PATH = SKILL_ROOT / "references" / "samr-standards" / "hierarchy-overrides.json"
STANDARD_ROOT = SKILL_ROOT / "references" / "samr-standards" / "corpora"
INDEX_PATH = SKILL_ROOT / "references" / "index" / "samr-standard-cards.json.gz"
OFFICIAL_ROOT = "https://openstd.samr.gov.cn"

SUBSCRIPT = str.maketrans("0123456789+-−", "₀₁₂₃₄₅₆₇₈₉₊₋₋")
SUPERSCRIPT = str.maketrans("0123456789+-−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁻")
HEADING = re.compile(r"^(?P<number>(?:[1-9]\d*(?:\.\d+)*|附录\s*[A-Z]))\s+(?P<title>\S.*)$")
JOINED_HEADING = re.compile(
    r"^(?P<number>[1-9]\d*(?:\.\d+)*)"
    r"(?P<title>范围|规范性引用文件|术语和定义|原理|方法原理|试验条件|"
    r"试剂和材料|试剂或材料|仪器设备|仪器和设备|被试物|样品|试验步骤|"
    r"试验数据处理|质量控制|试验报告)$"
)
FORMULA_LABEL = re.compile(r"[（(]([A-Z]?\.?\d+(?:\.\d+)?)[）)]\s*$")
PRECISION = re.compile(
    r"(?:\d|[=≈≤≥±∑√×·^%‰℃°μµρ₀-₉⁰-⁹]|"
    r"\b(?:mg|kg|g|mL|L|mol|mmol|μg|ng|cm|mm|nm|MPa|kPa|Pa|min|r/min|pH)\b|"
    r"公式|方程|计算|检出限|定量限)",
    re.IGNORECASE,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_fingerprint(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def slug(standard_no: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", standard_no.casefold()).strip("-")


def book_id(item: dict[str, Any]) -> str:
    return "samr-" + slug(str(item["standardNo"]))


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def formula_overrides(item: dict[str, Any], page: int) -> list[dict[str, Any]] | None:
    payload = json.loads(FORMULA_OVERRIDES_PATH.read_text(encoding="utf-8"))
    sources = payload.get("sources") or {}
    source_pages = sources.get(book_id(item))
    if not isinstance(source_pages, dict):
        return None
    # A source listed in the correction layer has had every numbered formula
    # page enumerated against the official rendering.  An absent page therefore
    # means "no formula on this page", not "fall back to OCR candidates".
    value = source_pages.get(str(page), [])
    return value if isinstance(value, list) else []


def apply_block_overrides(
    item: dict[str, Any], page: int, blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Apply page-specific corrections transcribed from a rendered official page.

    PDF font encodings and OCR can split a subscript variable across several
    blocks or expose an internal glyph id such as ``(cid:26)``.  Those strings
    must never reach the runtime corpus.  Every correction is kept in a
    separate, auditable data file instead of being hidden in extractor code.
    """
    if not BLOCK_OVERRIDES_PATH.is_file():
        return blocks
    payload = json.loads(BLOCK_OVERRIDES_PATH.read_text(encoding="utf-8"))
    override = (payload.get("sources") or {}).get(book_id(item), {}).get(str(page))
    if not isinstance(override, dict):
        return blocks
    drop_exact = set(str(value) for value in override.get("dropExact") or [])
    drop_contains = [str(value) for value in override.get("dropContains") or []]
    corrected = [
        block
        for block in blocks
        if str(block.get("text") or "") not in drop_exact
        and not any(value in str(block.get("text") or "") for value in drop_contains)
    ]
    for text in override.get("append") or []:
        corrected.append({"type": "verified-page-transcription", "text": str(text)})
    return corrected


def clean_space(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = re.sub(r"\s+([，。；：、！？）》】])", r"\1", text)
    text = re.sub(r"([《【（])\s+", r"\1", text)
    return text


def line_geometry(line: dict[str, Any]) -> tuple[float, float, float, float]:
    chars = line.get("chars") or []
    if not chars:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        min(float(char["x0"]) for char in chars),
        min(float(char["top"]) for char in chars),
        max(float(char["x1"]) for char in chars),
        max(float(char["bottom"]) for char in chars),
    )


def render_char_line(chars: list[dict[str, Any]]) -> str:
    if not chars:
        return ""
    chars = sorted(chars, key=lambda char: (float(char["x0"]), float(char["top"])))
    large_sizes = sorted(float(char.get("size") or 0.0) for char in chars if str(char["text"]).strip())
    if not large_sizes:
        return ""
    base_size = statistics.median(large_sizes[len(large_sizes) // 2 :])
    base_chars = [
        char
        for char in chars
        if str(char["text"]).strip() and float(char.get("size") or 0.0) >= base_size * 0.86
    ]
    base_top = statistics.median(float(char["top"]) for char in base_chars) if base_chars else 0.0
    base_bottom = statistics.median(float(char["bottom"]) for char in base_chars) if base_chars else 0.0
    out: list[str] = []
    for char in chars:
        text = str(char["text"])
        size = float(char.get("size") or base_size)
        if text.strip() and size < base_size * 0.86 and all(ch in "0123456789+-−" for ch in text):
            if float(char["top"]) > base_top + max(1.0, base_size * 0.13):
                text = text.translate(SUBSCRIPT)
            elif float(char["bottom"]) < base_bottom - max(1.0, base_size * 0.13):
                text = text.translate(SUPERSCRIPT)
        out.append(text)
    return clean_space("".join(out))


def extract_native_lines(page: pdfplumber.page.Page) -> list[dict[str, Any]]:
    extracted = page.extract_text_lines(layout=True, return_chars=True) or []
    raw_lines = [line for line in extracted if (line.get("chars") or [])]
    script_lines: set[int] = set()
    for index, line in enumerate(raw_lines):
        chars = line.get("chars") or []
        text = "".join(str(char["text"]) for char in chars).strip()
        if not text or not all(ch in "0123456789+-−" for ch in text):
            continue
        size = statistics.median(float(char.get("size") or 0.0) for char in chars)
        x0, top, x1, bottom = line_geometry(line)
        center = (top + bottom) / 2
        for candidate_index, candidate in enumerate(raw_lines):
            if candidate_index == index:
                continue
            candidate_chars = candidate.get("chars") or []
            candidate_size = statistics.median(
                float(char.get("size") or 0.0) for char in candidate_chars
            )
            cx0, ctop, cx1, cbottom = line_geometry(candidate)
            candidate_center = (ctop + cbottom) / 2
            horizontally_near = x0 <= cx1 + candidate_size and x1 >= cx0 - candidate_size
            if (
                size < candidate_size * 0.86
                and abs(center - candidate_center) <= max(7.0, candidate_size * 0.8)
                and horizontally_near
            ):
                script_lines.add(index)
                break
    base_lines = [line for index, line in enumerate(raw_lines) if index not in script_lines]
    assignments: list[list[dict[str, Any]]] = [[] for _ in base_lines]
    for char in page.chars:
        cy = (float(char["top"]) + float(char["bottom"])) / 2
        best = None
        for index, line in enumerate(base_lines):
            _, top, _, bottom = line_geometry(line)
            center = (top + bottom) / 2
            distance = abs(cy - center)
            if best is None or distance < best[0]:
                best = (distance, index, max(bottom - top, 1.0))
        if best is not None and best[0] <= max(8.0, best[2] * 0.9):
            assignments[best[1]].append(char)

    records: list[dict[str, Any]] = []
    for line, chars in zip(base_lines, assignments):
        text = render_char_line(chars)
        if not text:
            continue
        x0, top, x1, bottom = line_geometry(line)
        records.append(
            {
                "text": text,
                "x0": round(x0, 2),
                "top": round(top, 2),
                "x1": round(x1, 2),
                "bottom": round(bottom, 2),
            }
        )
    records.sort(key=lambda line: (line["top"], line["x0"]))
    return records


def clean_table(table: list[list[str | None]]) -> dict[str, Any] | None:
    rows = []
    for row in table:
        cleaned = [clean_space(str(cell or "").replace("\n", " ")) for cell in row]
        if any(cleaned):
            rows.append(cleaned)
    if len(rows) < 2:
        return None
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    return {"columns": rows[0], "rows": rows[1:]}


def formula_records(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    formulas: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        match = FORMULA_LABEL.search(str(line["text"]))
        if not match:
            continue
        near = []
        for candidate in lines[max(0, index - 2) : min(len(lines), index + 3)]:
            if abs(float(candidate["top"]) - float(line["top"])) <= 26:
                near.append(candidate)
        display = "\n".join(str(candidate["text"]) for candidate in near)
        formulas.append(
            {
                "label": f"（{match.group(1)}）",
                "displayAsPrinted": display,
                "reviewStatus": "candidate",
            }
        )
    return formulas


def page_record_native(
    item: dict[str, Any], page: pdfplumber.page.Page, page_number: int, pdf_hash: str
) -> dict[str, Any]:
    lines = extract_native_lines(page)
    tables = []
    for raw in page.extract_tables() or []:
        cleaned = clean_table(raw)
        if cleaned:
            tables.append(cleaned)
    corrected_formulas = formula_overrides(item, page_number)
    formulas = formula_records(lines) if corrected_formulas is None else corrected_formulas
    blocks = [{"type": "native-pdf-line", "text": line["text"]} for line in lines]
    blocks = apply_block_overrides(item, page_number, blocks)
    content = {"blocks": blocks, "formulas": formulas, "tables": tables}
    return {
        "schema": "soil-methods-consultant.samr-page.v1",
        "bookId": book_id(item),
        "page": page_number,
        "sourceType": "official-pdf",
        "sourcePdfSha256": pdf_hash,
        **content,
        "review": {
            "textPass": {"status": "candidate", "method": "原生文本层与字形坐标重建"},
            "precisionPass": {"status": "candidate", "method": "上下标、公式、单位和表格候选提取"},
            "secondVisualPass": {"status": "pending", "method": "待页面渲染复核"},
        },
        "contentSha256": json_fingerprint(content),
    }


def parse_online_pages(html: str) -> list[dict[str, Any]]:
    pages = []
    pattern = re.compile(
        r'<div id="(?P<index>\d+)" class="page" bg="(?P<bg>[^"]+)" '
        r'style="width:(?P<width>\d+)px;height:(?P<height>\d+)px;[^"]*">(?P<body>.*?)</div>',
        re.DOTALL,
    )
    tile_pattern = re.compile(
        r'class="pdfImg-(?P<x>\d+)-(?P<y>\d+)" '
        r'style="background-position: -(?P<sx>\d+)px -(?P<sy>\d+)px;"'
    )
    for match in pattern.finditer(html):
        tiles = [
            {key: int(tile.group(key)) for key in ("x", "y", "sx", "sy")}
            for tile in tile_pattern.finditer(match.group("body"))
        ]
        pages.append(
            {
                "index": int(match.group("index")),
                "bg": match.group("bg"),
                "width": int(match.group("width")),
                "height": int(match.group("height")),
                "tiles": tiles,
            }
        )
    return pages


def official_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def get_url(opener: urllib.request.OpenerDirector, url: str, referer: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Referer": referer,
            "User-Agent": "Mozilla/5.0",
            "Cache-Alive": "chunked",
        },
    )
    return opener.open(request, timeout=90).read()


def reconstruct_online_pages(item: dict[str, Any], work_root: Path) -> int:
    target = work_root / slug(str(item["standardNo"]))
    image_root = target / "images"
    image_root.mkdir(parents=True, exist_ok=True)
    detail = f"{OFFICIAL_ROOT}/bzgk/std/newGbInfo?hcno={item['hcno']}"
    viewer = (
        f"{OFFICIAL_ROOT}/bzgk/std/showGb?type=online&hcno={item['hcno']}"
        "&request_locale=zh"
    )
    opener = official_opener()
    cached_viewer = target / "viewer.html"
    if cached_viewer.is_file() and cached_viewer.stat().st_size > 20_000:
        html = cached_viewer.read_text(encoding="utf-8", errors="replace")
    else:
        html = get_url(opener, viewer, detail).decode("utf-8", "replace")
    pages = parse_online_pages(html)
    if not pages:
        raise RuntimeError(f"{item['standardNo']}: 官方在线全文暂时被验证码/限流阻断")
    cached_viewer.write_text(html, encoding="utf-8")
    for page in pages:
        output = image_root / f"page-{page['index'] + 1:03d}.png"
        if output.is_file() and output.stat().st_size > 10_000:
            continue
        image_url = f"{OFFICIAL_ROOT}/bzgk/std/viewGbImg?fileName={page['bg']}"
        sprite_bytes = get_url(opener, image_url, viewer)
        sprite_path = target / "sprite.webp"
        sprite_path.write_bytes(sprite_bytes)
        with Image.open(sprite_path) as sprite:
            tile_width = sprite.width // 10
            tile_height = int(round(page["height"] / 10))
            canvas = Image.new("RGB", (tile_width * 10, tile_height * 10), "white")
            for tile in page["tiles"]:
                crop = sprite.crop(
                    (
                        tile["sx"],
                        tile["sy"],
                        tile["sx"] + tile_width,
                        tile["sy"] + tile_height,
                    )
                )
                canvas.paste(crop, (tile["x"] * tile_width, tile["y"] * tile_height))
            if canvas.size != (page["width"], page["height"]):
                canvas = canvas.resize((page["width"], page["height"]), Image.Resampling.LANCZOS)
            canvas.save(output, format="PNG", optimize=True)
        sprite_path.unlink(missing_ok=True)
    manifest = {
        "standardNo": item["standardNo"],
        "hcno": item["hcno"],
        "detailUrl": detail,
        "viewerUrl": viewer,
        "pageCount": len(pages),
        "images": [
            {
                "page": index,
                "sha256": sha256(image_root / f"page-{index:03d}.png"),
            }
            for index in range(1, len(pages) + 1)
        ],
    }
    (target / "online-source.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return len(pages)


def ocr_page_record(item: dict[str, Any], page: int, work_root: Path) -> dict[str, Any]:
    target = work_root / slug(str(item["standardNo"]))
    image_path = target / "images" / f"page-{page:03d}.png"
    vision_path = target / "vision" / f"page-{page:03d}.json"
    if not vision_path.is_file():
        raise FileNotFoundError(f"缺少 Apple Vision 结果: {vision_path}")
    vision = json.loads(vision_path.read_text(encoding="utf-8"))
    observations = vision.get("observations") or []
    ordered = sorted(
        observations,
        key=lambda row: (
            -float((row.get("box") or [0, 0, 0, 0])[1]),
            float((row.get("box") or [0, 0, 0, 0])[0]),
        ),
    )
    blocks = [
        {"type": "official-reader-ocr-line", "text": clean_space(str(row.get("text") or ""))}
        for row in ordered
        if clean_space(str(row.get("text") or ""))
    ]
    blocks = apply_block_overrides(item, page, blocks)
    text_lines = [block["text"] for block in blocks]
    corrected_formulas = formula_overrides(item, page)
    formulas = (
        [
            {
                "label": f"（{match.group(1)}）",
                "displayAsPrinted": text,
                "reviewStatus": "candidate",
            }
            for text in text_lines
            if (match := FORMULA_LABEL.search(text))
        ]
        if corrected_formulas is None
        else corrected_formulas
    )
    content = {"blocks": blocks, "formulas": formulas, "tables": []}
    return {
        "schema": "soil-methods-consultant.samr-page.v1",
        "bookId": book_id(item),
        "page": page,
        "sourceType": "official-online-reader",
        "sourceImageSha256": sha256(image_path),
        **content,
        "review": {
            "textPass": {"status": "candidate", "method": "官方原分辨率阅读页+Apple Vision"},
            "precisionPass": {"status": "candidate", "method": "单位、上下标、公式和表格待视觉校正"},
            "secondVisualPass": {"status": "pending", "method": "待第二遍页面复核"},
        },
        "contentSha256": json_fingerprint(content),
    }


def section_role(title: str) -> str:
    rules = (
        ("范围", "scope"),
        ("原理", "principle"),
        ("试剂", "reagents"),
        ("材料", "materials"),
        ("仪器", "apparatus"),
        ("设备", "apparatus"),
        ("样品", "preparation"),
        ("步骤", "procedure"),
        ("测定", "measurement"),
        ("计算", "calculation"),
        ("表达", "calculation"),
        ("质量", "quality_control"),
        ("干扰", "interference"),
        ("报告", "reporting"),
        ("安全", "safety"),
    )
    for needle, role in rules:
        if needle in title:
            return role
    return "section"


def _heading_from_text(text: str) -> re.Match[str] | None:
    return HEADING.match(text) or JOINED_HEADING.match(text)


def _heading_lines(lines: list[str]) -> list[str]:
    """Recover headings split by OCR without joining arbitrary body lines."""
    recovered: list[str] = []
    canonical_titles = {
        "范围",
        "规范性引用文件",
        "术语和定义",
        "原理",
        "方法原理",
        "试验条件",
        "试剂和材料",
        "试剂或材料",
        "仪器设备",
        "仪器和设备",
        "被试物",
        "样品",
        "试验步骤",
        "试验数据处理",
        "质量控制",
        "试验报告",
    }
    for index, line in enumerate(lines):
        text = clean_space(line)
        if re.fullmatch(r"[1-9]\d*(?:\.\d+)*", text) and index + 1 < len(lines):
            next_text = clean_space(lines[index + 1])
            if next_text in canonical_titles:
                recovered.append(f"{text} {next_text}")
                continue
        recovered.append(text)
    return recovered


def _valid_heading_title(title: str) -> bool:
    if not title or len(title) > 48:
        return False
    if not re.search(r"[\u4e00-\u9fff]", title):
        return False
    if re.search(r"[，,:：。；=\[\]]", title):
        return False
    # These are clause openers in the standards, not heading nouns.  This also
    # removes OCR-truncated numbered prose that happens to be shorter than one
    # printed line.
    return not re.match(
        r"^(?:除非|在|将|称取|按公式|按GB|应|宜|从|对于|当|使用|可使用|仅测定|每次|根据|计算)",
        title,
    )


def _apply_hierarchy_overrides(
    item: dict[str, Any], components: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not HIERARCHY_OVERRIDES_PATH.is_file():
        return components
    payload = json.loads(HIERARCHY_OVERRIDES_PATH.read_text(encoding="utf-8"))
    source = (payload.get("sources") or {}).get(book_id(item), {})
    drop_numbers = {str(value) for value in source.get("dropNumbers") or []}
    corrected = [value for value in components if str(value["number"]) not in drop_numbers]
    for value in source.get("replace") or []:
        number = str(value["number"])
        corrected = [item for item in corrected if str(item["number"]) != number]
        corrected.append(
            {
                "number": number,
                "title": str(value["title"]),
                "role": section_role(str(value["title"])),
                "level": number.count(".") + 1,
                "parentNumber": number.rsplit(".", 1)[0] if "." in number else None,
                "startPage": int(value["page"]),
                "endPage": int(value["page"]),
                "correctionSource": "official-page-visual-transcription",
            }
        )
    for value in source.get("insert") or []:
        number = str(value["number"])
        if any(str(item["number"]) == number for item in corrected):
            continue
        corrected.append(
            {
                "number": number,
                "title": str(value["title"]),
                "role": section_role(str(value["title"])),
                "level": number.count(".") + 1,
                "parentNumber": number.rsplit(".", 1)[0] if "." in number else None,
                "startPage": int(value["page"]),
                "endPage": int(value["page"]),
                "correctionSource": "official-page-visual-transcription",
            }
        )
    return corrected


def method_card(
    item: dict[str, Any],
    pages: list[dict[str, Any]],
    secondary_heading_lines: dict[int, list[str]] | None = None,
) -> dict[str, Any]:
    raw_components: list[dict[str, Any]] = []
    body_started = False
    for page in pages:
        primary = [str(block.get("text") or "") for block in page.get("blocks") or []]
        secondary = (secondary_heading_lines or {}).get(int(page["page"]), [])
        # Primary (Apple Vision or the native PDF text layer) wins on duplicate
        # numbers. Tesseract contributes headings that the first engine missed.
        lines = [*_heading_lines(primary), *_heading_lines(secondary)]
        for text in lines:
            match = _heading_from_text(text)
            if not match:
                continue
            number = match.group("number")
            raw_title = match.group("title").strip()
            # Discard contents-page leaders and ordinary numbered sentences.
            # The remaining records are section headings, not every clause line.
            if re.search(r"[…⋯·]{2,}", raw_title):
                continue
            title = raw_title.strip(" \t.:：;；•·…⋯")
            title = title.lstrip("\"'“”‘’ ")
            title = title.replace("仅器", "仪器")
            split_number = re.match(r"^(\d+(?:\.\d+)*)\s+(.+)$", title)
            if split_number and "." not in number:
                number = f"{number}.{split_number.group(1)}"
                title = split_number.group(2).strip()
            if number == "1.0" and "质量" in title:
                number = "10"
            elif number == "1.1" and "质量" in title:
                number = "11"
            if (
                not body_started
                and number == "1"
                and title == "范围"
                and not re.search(r"[…⋯·•]", raw_title)
            ):
                body_started = True
                raw_components.clear()
            if not body_started:
                continue
            if not _valid_heading_title(title):
                continue
            level = 1 if number.startswith("附录") else number.count(".") + 1
            parent_number = None
            if "." in number:
                parent_number = number.rsplit(".", 1)[0]
            raw_components.append(
                {
                    "number": number,
                    "title": title,
                    "role": section_role(title),
                    "level": level,
                    "parentNumber": parent_number,
                    "startPage": int(page["page"]),
                    "endPage": int(page["page"]),
                }
            )

    raw_components = _apply_hierarchy_overrides(item, raw_components)

    # A second OCR engine is appended page-by-page, so put candidates back into
    # printed hierarchy order and keep one authoritative title per clause.
    def number_key(component: dict[str, Any]) -> tuple[int, ...]:
        number = str(component["number"])
        if number.startswith("附录"):
            return (10_000, ord(number[-1]))
        return tuple(int(part) for part in number.split("."))

    raw_components.sort(key=lambda value: (int(value["startPage"]), number_key(value)))
    components: list[dict[str, Any]] = []
    seen_numbers: set[str] = set()
    current_top = 0
    for component in raw_components:
        number = str(component["number"])
        if number in seen_numbers:
            continue
        top = int(number.split(".", 1)[0]) if not number.startswith("附录") else current_top
        if "." not in number and not number.startswith("附录"):
            if top < current_top or top > current_top + 1:
                continue
            if top > current_top:
                current_top = top
        elif top != current_top:
            continue
        seen_numbers.add(number)
        components.append(component)
    for index, component in enumerate(components):
        next_page = components[index + 1]["startPage"] if index + 1 < len(components) else len(pages)
        component["endPage"] = max(
            component["startPage"],
            next_page if next_page == component["startPage"] else next_page - 1,
        )
    start = next((c["startPage"] for c in components if c.get("number") == "1"), 1)
    sensitive = [
        int(page["page"])
        for page in pages
        if page.get("formulas")
        or page.get("tables")
        or any(PRECISION.search(str(block.get("text") or "")) for block in page.get("blocks") or [])
    ]
    return {
        "id": f"{book_id(item)}-method",
        "bookId": book_id(item),
        "sourceLabel": f"{item['standardNo']}《{item['title']}》",
        "kind": "method",
        "title": item["title"],
        "standardNo": item["standardNo"],
        "path": [item["standardNo"], item["title"]],
        "startPage": start,
        "endPage": len(pages),
        "components": components,
        "precisionSensitivePages": sensitive,
        "reviewPriorityCounts": {"verified": len(pages)},
        "officialDetailUrl": f"{OFFICIAL_ROOT}/bzgk/std/newGbInfo?hcno={item['hcno']}",
    }


def gate_matches(gate_path: Path, source_fingerprint: str, page_count: int) -> bool:
    if not gate_path.is_file():
        return False
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    return bool(
        gate.get("status") == "verified"
        and gate.get("sourceFingerprint") == source_fingerprint
        and int(gate.get("pageCount", 0)) == page_count
        and gate.get("textPass") == "verified"
        and gate.get("precisionPass") == "verified"
        and gate.get("secondVisualPass") == "verified"
    )


def write_gzip_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=9) as stream:
        json.dump(value, stream, ensure_ascii=False, separators=(",", ":"))
    os.replace(temporary, path)


def build_source(item: dict[str, Any], pdf_root: Path, online_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    sid = book_id(item)
    source_root = STANDARD_ROOT / sid
    source_root.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_root / f"{slug(str(item['standardNo']))}.pdf"
    pages = []
    source_type = "official-pdf" if pdf_path.is_file() and pdf_path.stat().st_size > 1000 else "official-online-reader"
    secondary_heading_lines: dict[int, list[str]] = {}
    if source_type == "official-pdf":
        fingerprint = sha256(pdf_path)
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, 1):
                pages.append(page_record_native(item, page, page_number, fingerprint))
    else:
        manifest_path = online_root / slug(str(item["standardNo"])) / "online-source.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"缺少官方在线页清单: {manifest_path}")
        online_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        fingerprint = json_fingerprint(online_manifest)
        for page_number in range(1, int(online_manifest["pageCount"]) + 1):
            pages.append(ocr_page_record(item, page_number, online_root))
            tesseract_path = (
                online_root
                / slug(str(item["standardNo"]))
                / "tesseract"
                / f"page-{page_number:03d}.txt"
            )
            if tesseract_path.is_file():
                secondary_heading_lines[page_number] = tesseract_path.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
    gate_path = source_root / "review-gate.json"
    ready = gate_matches(gate_path, fingerprint, len(pages))
    if ready:
        for page in pages:
            for key in ("textPass", "precisionPass", "secondVisualPass"):
                page["review"][key]["status"] = "verified"
            for formula in page.get("formulas") or []:
                formula["reviewStatus"] = "verified"
            content = {key: page[key] for key in ("blocks", "formulas", "tables")}
            page["contentSha256"] = json_fingerprint(content)
    pages_payload = {
        "schema": "soil-methods-consultant.samr-corpus.v1",
        "bookId": sid,
        "standardNo": item["standardNo"],
        "title": item["title"],
        "pages": pages,
    }
    write_gzip_json(source_root / "pages.json.gz", pages_payload)
    manifest = {
        "schema": "soil-methods-consultant.samr-manifest.v1",
        "bookId": sid,
        "label": f"{item['standardNo']}《{item['title']}》",
        "standardNo": item["standardNo"],
        "title": item["title"],
        "published": item["published"],
        "implemented": item.get("implemented"),
        "domain": item["domain"],
        "sourceType": source_type,
        "sourceFingerprint": fingerprint,
        "includedPageCount": len(pages),
        "runtimeReady": ready,
        "officialDetailUrl": f"{OFFICIAL_ROOT}/bzgk/std/newGbInfo?hcno={item['hcno']}",
    }
    (source_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest, method_card(item, pages, secondary_heading_lines)


def build_all(pdf_root: Path, online_root: Path) -> None:
    catalog = load_catalog()
    manifests = []
    cards = []
    missing = []
    missing_sources = []
    for item in catalog["standards"]:
        if item.get("disposition") != "include":
            continue
        try:
            manifest, card = build_source(item, pdf_root, online_root)
        except FileNotFoundError as error:
            missing.append(str(error))
            missing_sources.append(
                {
                    "bookId": book_id(item),
                    "label": f"{item['standardNo']}《{item['title']}》",
                    "standardNo": item["standardNo"],
                    "title": item["title"],
                    "published": item["published"],
                    "domain": item["domain"],
                    "runtimeReady": False,
                    "includedPageCount": 0,
                    "status": "official-full-text-unavailable",
                    "reason": str(error),
                    "officialDetailUrl": f"{OFFICIAL_ROOT}/bzgk/std/newGbInfo?hcno={item['hcno']}",
                }
            )
            continue
        manifests.append(manifest)
        cards.append(card)
    payload = {
        "schema": "soil-methods-consultant.samr-method-cards.v1",
        "catalogQueriedAt": catalog["queriedAt"],
        "queryWindow": catalog["queryWindow"],
        "expectedSourceCount": sum(1 for item in catalog["standards"] if item.get("disposition") == "include"),
        "sources": manifests,
        "cardCount": len(cards),
        "cards": cards,
        "missing": missing,
        "missingSources": missing_sources,
    }
    write_gzip_json(INDEX_PATH, payload)
    print(f"standards built: {len(manifests)}; ready: {sum(bool(x['runtimeReady']) for x in manifests)}")
    if missing:
        print("missing:")
        for message in missing:
            print("- " + message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf-root", type=Path, default=Path("tmp/pdfs/samr-2024-2026"))
    parser.add_argument("--online-root", type=Path, default=Path("tmp/pdfs/samr-2024-2026/online"))
    parser.add_argument("--fetch-online", action="store_true")
    parser.add_argument("--standard", action="append", default=[])
    args = parser.parse_args()
    if args.fetch_online:
        selected = set(args.standard)
        for item in load_catalog()["standards"]:
            if item.get("disposition") != "include":
                continue
            if selected and item["standardNo"] not in selected:
                continue
            pdf_path = args.pdf_root / f"{slug(str(item['standardNo']))}.pdf"
            if pdf_path.is_file() and pdf_path.stat().st_size > 1000:
                continue
            count = reconstruct_online_pages(item, args.online_root)
            print(f"{item['standardNo']}: {count} pages")
        return 0
    build_all(args.pdf_root, args.online_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

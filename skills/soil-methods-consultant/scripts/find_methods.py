#!/usr/bin/env python3
"""离线检索《土壤采样与分析方法》上下册的最终校正语料。"""

from __future__ import annotations

import argparse
import csv
import functools
import gzip
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from corrected_corpus import load_corrected_page, render_corrected_page


SKILL_ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = SKILL_ROOT / "references" / "index"
PADDLE_REVIEW = INDEX_DIR / "paddle-review-pages.json.gz"
PAGE_REVIEW_STATUS = INDEX_DIR / "page-review-status.csv.gz"
METHOD_CARDS = INDEX_DIR / "method-cards.json.gz"
CORPUS_STATUS = INDEX_DIR / "corpus-status.json"
EXTERNAL_CARDS = INDEX_DIR / "external-method-cards.json.gz"
EXTERNAL_ROOT = SKILL_ROOT / "references" / "external-corpora"
SAMR_CARDS = INDEX_DIR / "samr-standard-cards.json.gz"
SAMR_ROOT = SKILL_ROOT / "references" / "samr-standards" / "corpora"

VOLUMES = {
    1: {
        "label": "上册",
        "book": INDEX_DIR / "volume-1-book.json.gz",
        "search": INDEX_DIR / "volume-1-search.json.gz",
        "tesseract": INDEX_DIR / "volume-1-tesseract.txt.gz",
    },
    2: {
        "label": "下册",
        "book": INDEX_DIR / "volume-2-book.json.gz",
        "search": INDEX_DIR / "volume-2-search.json.gz",
        "tesseract": INDEX_DIR / "volume-2-tesseract.txt.gz",
    },
}

# 只扩展常见同义名；原查询始终保留。
ALIASES: dict[str, tuple[str, ...]] = {
    "ph": ("土壤反应", "酸碱度", "交换性酸"),
    "soc": ("土壤有机碳", "有机碳"),
    "toc": ("总有机碳", "有机碳"),
    "cec": ("阳离子交换量", "离子交换"),
    "容重": ("干容重", "bulk density"),
    "土壤质地": ("颗粒大小分布", "粒径分布", "机械组成"),
    "有效磷": ("可提取态磷", "碳酸氢钠可提取态磷", "mehlich 3"),
    "速效磷": ("有效磷", "可提取态磷"),
    "铵态氮": ("可交换性铵态氮", "nh4"),
    "硝态氮": ("no3", "硝酸盐氮"),
    "土壤水势": ("矩阵势", "吸力", "张力"),
    "持水曲线": ("土壤水分特征曲线", "脱水曲线", "吸水曲线"),
    "导水率": ("水力学特性", "渗透系数"),
    "饱和导水率": ("饱和水力学特性", "饱和渗透系数"),
    "圆环入渗法": ("圆环入渗", "双环入渗"),
    "圆环法": ("圆环入渗法", "单圆环入渗法", "双圆环入渗法"),
    "井渗法": ("定水头井渗法", "降水头井渗法", "井渗"),
    "微生物量碳": ("熏蒸提取", "微生物生物量"),
    "熏蒸提取法": ("微生物量碳", "微生物量氮", "氯仿熏蒸"),
    "碳矿化": ("有机碳矿化", "土壤呼吸"),
    "土壤团聚体": ("团聚体", "水稳性团聚体", "湿团聚体", "干团聚体"),
    "团聚体": ("团聚体水稳性", "水稳性团聚体", "湿筛", "干筛"),
    "土壤酶活性": ("荧光底物微孔板", "MUF", "AMC", "水解酶"),
}

PROMPT_WORDS = (
    "请帮我",
    "帮我",
    "请查找",
    "查找",
    "寻找",
    "怎么样",
    "怎么",
    "如何",
    "用什么",
    "试验方法",
    "实验方法",
    "测定方法",
    "分析方法",
    "怎么测",
    "如何测",
    "测定",
    "测量",
    "检测",
    "方法",
)

PRECISION_LINE = re.compile(
    r"(?:\d|[=≈≤≥±∑√×·^%‰℃°μµ₀-₉⁰-⁹]|"
    r"\b(?:mg|kg|g|ml|mL|L|mol|mmol|cm|mm|nm|ha|MPa|kPa|Pa|min|rpm|pH)\b|"
    r"公式|方程|式中|计算)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class VolumeData:
    volume: int
    label: str
    title: str
    page_count: int
    outline: list[dict[str, Any]]
    pages: list[dict[str, Any]]


def load_gzip_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"缺少内置索引: {path}")
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def load_volume(volume: int) -> VolumeData:
    spec = VOLUMES[volume]
    book = load_gzip_json(spec["book"])
    page_count = int(book["pageCount"])
    pages = [
        {"page": page, "text": render_corrected_page(load_corrected_page(volume, page))}
        for page in range(1, page_count + 1)
    ]
    return VolumeData(
        volume=volume,
        label=spec["label"],
        title=book["title"],
        page_count=page_count,
        outline=book.get("outline") or [],
        pages=pages,
    )


def load_tesseract_pages(volume: int) -> list[str]:
    path = VOLUMES[volume]["tesseract"]
    if not path.is_file():
        raise FileNotFoundError(f"缺少内置 Tesseract 文本: {path}")
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        return handle.read().split("\f")


def load_paddle_page(volume: int, page: int) -> dict[str, Any] | None:
    if not PADDLE_REVIEW.is_file():
        return None
    payload = load_gzip_json(PADDLE_REVIEW)
    volume_data = payload.get("volumes", {}).get(str(volume), {})
    for record in volume_data.get("pages", []):
        if int(record.get("page", 0)) == page:
            return record
    return None


def load_review_status() -> dict[tuple[int, int], str]:
    statuses: dict[tuple[int, int], str] = {}
    if not PAGE_REVIEW_STATUS.is_file():
        return statuses
    with gzip.open(PAGE_REVIEW_STATUS, "rt", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            book_id = str(row.get("book_id", ""))
            if not book_id.startswith("volume-"):
                continue
            statuses[(int(book_id.removeprefix("volume-")), int(row["pdf_page"]))] = str(
                row.get("review_priority", "")
            )
    return statuses


def load_method_cards() -> list[dict[str, Any]]:
    """读取由两册识别文本和完整目录层级生成的方法卡。"""
    payload = load_gzip_json(METHOD_CARDS)
    cards = payload.get("cards") or []
    if not isinstance(cards, list):
        raise ValueError("内置方法卡格式无效")
    return cards


@functools.lru_cache(maxsize=None)
def load_external_page_map(book_id: str) -> dict[int, dict[str, Any]]:
    root = SAMR_ROOT if book_id.startswith("samr-") else EXTERNAL_ROOT
    path = root / book_id / "pages.json.gz"
    payload = load_gzip_json(path)
    return {int(page["page"]): page for page in payload.get("pages") or []}


def load_external_payload() -> dict[str, Any]:
    if not EXTERNAL_CARDS.is_file():
        return {"sources": [], "cards": []}
    return load_gzip_json(EXTERNAL_CARDS)


def load_samr_payload() -> dict[str, Any]:
    if not SAMR_CARDS.is_file():
        return {"sources": [], "cards": [], "missingSources": [], "expectedSourceCount": 0}
    return load_gzip_json(SAMR_CARDS)


def runtime_external_sources() -> list[dict[str, Any]]:
    return [source for source in load_external_payload().get("sources", []) if source.get("runtimeReady")]


def runtime_samr_sources() -> list[dict[str, Any]]:
    return [source for source in load_samr_payload().get("sources", []) if source.get("runtimeReady")]


def runtime_auxiliary_sources() -> list[dict[str, Any]]:
    return [*runtime_external_sources(), *runtime_samr_sources()]


def runtime_method_cards() -> list[dict[str, Any]]:
    ready = {source["bookId"] for source in runtime_auxiliary_sources()}
    external = [
        card
        for card in [
            *(load_external_payload().get("cards") or []),
            *(load_samr_payload().get("cards") or []),
        ]
        if card.get("bookId") in ready
    ]
    return [*load_method_cards(), *external]


def external_card_text(card: dict[str, Any]) -> str:
    pages = load_external_page_map(str(card["bookId"]))
    return "\n".join(
        render_corrected_page(pages[page])
        for page in range(int(card["startPage"]), int(card["endPage"]) + 1)
        if page in pages
    )


def load_corpus_status() -> dict[str, Any]:
    if not CORPUS_STATUS.is_file():
        raise FileNotFoundError(f"缺少语料状态文件: {CORPUS_STATUS}")
    return json.loads(CORPUS_STATUS.read_text(encoding="utf-8"))


def require_verified_corpus() -> None:
    status = load_corpus_status()
    if not status.get("runtimeReady"):
        verified = int(status.get("verifiedPages", 0))
        required = int(status.get("requiredPages", 915))
        raise ValueError(
            f"校正语料尚未完成（{verified}/{required} 页）。"
            "零容错模式禁止使用机器 OCR 回答，也禁止回查原 PDF。"
        )


def corpus_status(args: argparse.Namespace) -> int:
    status = load_corpus_status()
    external = load_external_payload().get("sources", [])
    core_sources_ready = bool(status.get("runtimeReady")) and len(external) == 4 and all(
        source.get("runtimeReady") for source in external
    )
    samr = load_samr_payload()
    samr_sources = samr.get("sources") or []
    samr_missing = samr.get("missingSources") or []
    samr_expected = int(samr.get("expectedSourceCount", 0))
    samr_ready = sum(bool(source.get("runtimeReady")) for source in samr_sources)
    recent_standards_complete = samr_expected > 0 and samr_ready == samr_expected
    all_sources_ready = core_sources_ready and recent_standards_complete
    combined = {
        **status,
        "allSourcesReady": all_sources_ready,
        "coreSourcesReady": core_sources_ready,
        "recentStandardsComplete": recent_standards_complete,
        "samrExpectedSourceCount": samr_expected,
        "samrBuiltSourceCount": len(samr_sources),
        "samrReadySourceCount": samr_ready,
        "samrMissingSourceCount": len(samr_missing),
        "samrQueryWindow": samr.get("queryWindow"),
        "includedPageCount": int(status.get("requiredPages", 915))
        + sum(int(source.get("includedPageCount", 0)) for source in external)
        + sum(
            int(source.get("includedPageCount", 0))
            for source in samr_sources
            if source.get("runtimeReady")
        ),
        "sources": [
            {"bookId": "volume-1", "runtimeReady": bool(status.get("runtimeReady")), "includedPageCount": 557},
            {"bookId": "volume-2", "runtimeReady": bool(status.get("runtimeReady")), "includedPageCount": 358},
            *external,
            *samr_sources,
            *samr_missing,
        ],
    }
    if args.json:
        print(json.dumps(combined, ensure_ascii=False, indent=2))
        return 0
    print(f"status: {status.get('status', 'unknown')}")
    print(f"verified: {status.get('verifiedPages', 0)}/{status.get('requiredPages', 915)}")
    print(f"runtimeReady: {str(bool(status.get('runtimeReady'))).lower()}")
    print(f"coreSourcesReady: {str(core_sources_ready).lower()}")
    print(
        f"recentStandards: {samr_ready}/{samr_expected} ready; "
        f"missing={len(samr_missing)}; complete={str(recent_standards_complete).lower()}"
    )
    print(f"allSourcesReady: {str(all_sources_ready).lower()}")
    print(f"includedPages: {combined['includedPageCount']}")
    print(status.get("message", ""))
    return 0


def selected_volumes(value: str) -> list[int]:
    return [1, 2] if value == "all" else [int(value)]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in text if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def clean_query(query: str) -> str:
    cleaned = unicodedata.normalize("NFKC", query).casefold()
    for word in PROMPT_WORDS:
        cleaned = cleaned.replace(word, " ")
    cleaned = re.sub(r"[\s\W_]+", " ", cleaned, flags=re.UNICODE).strip()
    return cleaned or query


def query_concepts(query: str) -> list[str]:
    raw = unicodedata.normalize("NFKC", query).casefold()
    concepts = [query, clean_query(query)]
    for key, values in ALIASES.items():
        key_norm = normalize(key)
        if key_norm and (key_norm in normalize(raw) or any(normalize(v) in normalize(raw) for v in values)):
            concepts.extend((key, *values))
    for token in re.split(r"[\s,，;；/]+", clean_query(query)):
        if len(normalize(token)) >= 2:
            concepts.append(token)
    for method_name in re.findall(r"[一-鿿A-Za-z0-9]{2,}?法", raw):
        concepts.append(method_name)
    unique: list[str] = []
    seen: set[str] = set()
    for concept in concepts:
        n = normalize(concept)
        if len(n) >= 2 and n not in seen:
            unique.append(concept)
            seen.add(n)
    return unique


def ngrams(text: str, sizes: Iterable[int] = (2, 3, 4)) -> set[str]:
    ntext = normalize(text)
    grams: set[str] = set()
    for size in sizes:
        if len(ntext) < size:
            continue
        grams.update(ntext[index : index + size] for index in range(len(ntext) - size + 1))
    return grams


def outline_context(data: VolumeData, page: int) -> tuple[list[str], list[str]]:
    chapter = ""
    active_by_depth: dict[int, str] = {}
    on_page: list[str] = []
    for entry in data.outline:
        entry_page = int(entry["page"])
        if entry_page > page:
            break
        depth = int(entry.get("depth", 0))
        title = str(entry["title"])
        if depth == 1 and title.startswith("第"):
            chapter = title
        active_by_depth[depth] = title
        for old_depth in [d for d in active_by_depth if d > depth]:
            del active_by_depth[old_depth]
        if entry_page == page:
            on_page.append(title)
    active = [active_by_depth[d] for d in sorted(active_by_depth)]
    if chapter and chapter not in active:
        active.insert(0, chapter)
    return active, on_page


def section_role(title: str) -> str:
    rules = (
        ("原理", "principle"),
        ("适用", "scope"),
        ("材料", "materials"),
        ("试剂", "reagents"),
        ("仪器", "apparatus"),
        ("设备", "apparatus"),
        ("步骤", "procedure"),
        ("操作", "procedure"),
        ("计算", "calculation"),
        ("质量控制", "quality_control"),
        ("注意", "caution"),
        ("干扰", "interference"),
        ("安全", "safety"),
        ("参考文献", "references"),
    )
    for needle, role in rules:
        if needle in title:
            return role
    if re.match(r"^第\s*\d+\s*章", title):
        return "chapter"
    if re.match(r"^第[一二三四五六七八九十]+篇", title):
        return "part"
    return "section"


def outline_records(data: VolumeData) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    stack: dict[int, dict[str, Any]] = {}
    for index, entry in enumerate(data.outline):
        depth = int(entry.get("depth", 0))
        page = int(entry["page"])
        title = str(entry["title"])
        for old_depth in [value for value in stack if value >= depth]:
            del stack[old_depth]
        path = [str(stack[value]["title"]) for value in sorted(stack) if value < depth] + [title]
        parent = stack.get(depth - 1)
        end_page = page
        for later in data.outline[index + 1 :]:
            if int(later.get("depth", 0)) <= depth:
                end_page = max(end_page, int(later["page"]) - 1)
                break
            end_page = max(end_page, int(later["page"]))
        record = {
            "id": f"v{data.volume}-s{index + 1:04d}",
            "parentId": parent["id"] if parent else None,
            "volume": data.volume,
            "volumeLabel": data.label,
            "depth": depth,
            "title": title,
            "role": section_role(title),
            "startPage": page,
            "endPage": end_page,
            "path": path,
        }
        records.append(record)
        stack[depth] = record
    return records


def best_excerpt(text: str, concepts: list[str], width: int = 300) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    if not flat:
        return ""
    lower = unicodedata.normalize("NFKC", flat).casefold()
    positions = []
    for concept in concepts:
        candidate = unicodedata.normalize("NFKC", concept).casefold().strip()
        if candidate:
            pos = lower.find(candidate)
            if pos >= 0:
                positions.append(pos)
    center = min(positions) if positions else 0
    start = max(0, center - width // 3)
    end = min(len(flat), start + width)
    excerpt = flat[start:end]
    if start:
        excerpt = "…" + excerpt
    if end < len(flat):
        excerpt += "…"
    return excerpt


def best_structured_excerpt(
    record: dict[str, Any],
    query: str,
    concepts: list[str],
    width: int = 300,
) -> str:
    """Prefer corrected formula/table fields when the query is precision-sensitive."""
    rendered = render_corrected_page(record)
    precision_intent = bool(
        re.search(
            r"公式|计算|单位|浓度|配方|波长|温度|体积|质量|稀释|下标|[A-Za-z]{2,}|\d",
            query,
            re.IGNORECASE,
        )
    )
    if not precision_intent:
        return best_excerpt(rendered, concepts, width)
    sections = re.split(r"(?=\[(?:公式|表格)\])", rendered)
    precision_sections = [
        section for section in sections if section.startswith("[公式]") or section.startswith("[表格]")
    ]
    scored = []
    for section in precision_sections:
        normalized = normalize(section)
        score = sum(
            1
            for concept in concepts
            if len(normalize(concept)) >= 2 and normalize(concept) in normalized
        )
        if score:
            scored.append((score, section))
    if scored:
        return best_excerpt(max(scored, key=lambda item: item[0])[1], concepts, width)
    return best_excerpt(rendered, concepts, width)


def score_page(query: str, concepts: list[str], text: str, headings: list[str]) -> float:
    page_norm = normalize(text)
    title_norm = normalize(" ".join(headings))
    if not page_norm and not title_norm:
        return 0.0

    score = 0.0
    full = normalize(query)
    cleaned = normalize(clean_query(query))
    if full:
        score += 80.0 if full in title_norm else 0.0
        score += min(page_norm.count(full), 5) * 16.0
    if cleaned and cleaned != full:
        score += 70.0 if cleaned in title_norm else 0.0
        score += min(page_norm.count(cleaned), 5) * 14.0

    for concept in concepts:
        c = normalize(concept)
        if not c:
            continue
        if c in title_norm:
            score += 40.0 + min(len(c), 12) * 2.0
        if c in page_norm:
            score += 8.0 + min(page_norm.count(c), 5) * 2.0 + min(len(c), 12) * 0.5

    qgrams = ngrams(clean_query(query))
    if qgrams:
        title_overlap = len(qgrams & ngrams(title_norm)) / len(qgrams)
        page_overlap = len(qgrams & ngrams(page_norm)) / len(qgrams)
        score += title_overlap * 30.0 + page_overlap * 12.0
    return round(score, 3)


def search(args: argparse.Namespace) -> int:
    concepts = query_concepts(args.query)
    review_statuses = load_review_status()
    results: list[dict[str, Any]] = []
    for volume in selected_volumes(args.volume):
        data = load_volume(volume)
        for record in data.pages:
            page = int(record["page"])
            text = str(record.get("text") or "")
            active, on_page = outline_context(data, page)
            headings = list(dict.fromkeys([*on_page, *active]))
            score = score_page(args.query, concepts, text, headings)
            if score <= 0:
                continue
            results.append(
                {
                    "volume": volume,
                    "volumeLabel": data.label,
                    "page": page,
                    "score": score,
                    "reviewPriority": review_statuses.get((volume, page), "unknown"),
                    "chapter": next((h for h in active if h.startswith("第") and "章" in h), ""),
                    "headingsOnPage": on_page,
                    "activeOutline": active,
                    "excerpt": best_excerpt(text, concepts, args.excerpt),
                }
            )

    if args.volume == "all":
        for source in runtime_auxiliary_sources():
            book_id = str(source["bookId"])
            label = str(source["label"])
            for page, record in load_external_page_map(book_id).items():
                text = render_corrected_page(record)
                score = score_page(args.query, concepts, text, [])
                if score <= 0:
                    continue
                results.append(
                    {
                        "bookId": book_id,
                        "sourceLabel": label,
                        "page": page,
                        "score": score,
                        "reviewPriority": "verified",
                        "chapter": "",
                        "headingsOnPage": [],
                        "activeOutline": [],
                        "excerpt": best_structured_excerpt(record, args.query, concepts, args.excerpt),
                    }
                )

    results.sort(key=lambda item: (-item["score"], str(item.get("bookId", item.get("volume"))), item["page"]))
    results = results[: args.top]
    payload = {
        "query": args.query,
        "expandedConcepts": concepts,
        "resultCount": len(results),
        "results": results,
        "pageNumbering": "PDF 页码",
        "corpus": "最终逐页校正语料",
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if not results:
        print("未找到候选页。请换用更具体的指标、试剂、仪器或原理。")
        return 1
    print(f"查询: {args.query}")
    print(f"扩展概念: {', '.join(concepts)}")
    for index, item in enumerate(results, 1):
        source_label = item.get("sourceLabel") or item.get("volumeLabel")
        print(f"\n[{index}] {source_label} PDF 第 {item['page']} 页  score={item['score']}")
        if item["chapter"]:
            print(f"章: {item['chapter']}")
        print(f"校正版页级标签: {item['reviewPriority']}")
        if item["headingsOnPage"]:
            print("本页标题: " + " | ".join(item["headingsOnPage"]))
        print("摘录: " + item["excerpt"])
    print("\n注: 页码均为 PDF 页码；内容来自最终逐页校正语料。")
    return 0


def consult(args: argparse.Namespace) -> int:
    """按自然语言问题返回可用于咨询判断的结构化方法候选。"""
    concepts = query_concepts(args.query)
    allowed_volumes = set(selected_volumes(args.volume))
    results: list[dict[str, Any]] = []
    for card in runtime_method_cards():
        is_external = "bookId" in card
        if not is_external and int(card["volume"]) not in allowed_volumes:
            continue
        if is_external and args.volume != "all":
            continue
        page_texts = (
            [external_card_text(card)]
            if is_external
            else [str(page.get("text") or "") for page in card.get("pages", [])]
        )
        component_titles = [str(item.get("title") or "") for item in card.get("components", [])]
        path = [str(item) for item in card.get("path", [])]
        headings = [*path, *component_titles]
        combined_text = "\n".join(page_texts)
        score = score_page(args.query, concepts, combined_text, headings)
        title_norm = normalize(str(card.get("title") or ""))
        path_norm = normalize(" ".join(path))
        for concept in concepts:
            concept_norm = normalize(concept)
            if concept_norm and concept_norm in title_norm:
                score += 90.0
            elif concept_norm and concept_norm in path_norm:
                score += 30.0
        if card.get("kind") == "method":
            score += 45.0
        if score <= 45.0:
            continue
        roles = list(dict.fromkeys(str(item.get("role") or "section") for item in card.get("components", [])))
        results.append(
            {
                "id": card["id"],
                "kind": card.get("kind", "method"),
                "volume": card.get("volume"),
                "volumeLabel": card.get("volumeLabel"),
                "bookId": card.get("bookId"),
                "sourceLabel": card.get("sourceLabel") or card.get("volumeLabel"),
                "title": card["title"],
                "path": path,
                "startPage": card["startPage"],
                "endPage": card["endPage"],
                "componentRoles": roles,
                "components": card.get("components", []),
                "precisionSensitivePages": card.get("precisionSensitivePages", []),
                "reviewPriorityCounts": card.get("reviewPriorityCounts", {}),
                "score": round(score, 3),
                "excerpt": best_excerpt(combined_text, concepts, args.excerpt),
            }
        )

    results.sort(
        key=lambda item: (
            -item["score"],
            0 if item["kind"] == "method" else 1,
            str(item.get("bookId") or item.get("volume")),
            item["startPage"],
        )
    )
    results = results[: args.top]
    payload = {
        "query": args.query,
        "expandedConcepts": concepts,
        "resultCount": len(results),
        "results": results,
        "pageNumbering": "PDF 页码",
        "usage": "先据候选的适用范围和限制选法，再用 method <id> 展开最终校正内容。",
        "precisionRule": "数字、公式、上下标、化学式、单位和表格均以最终校正页的结构化值为准。",
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if not results:
        print("未找到方法候选。请补充待测指标、土壤类型、仪器或方法原理。")
        return 1
    print(f"咨询问题: {args.query}")
    print(f"检索概念: {', '.join(concepts)}")
    for index, item in enumerate(results, 1):
        page_range = (
            str(item["startPage"])
            if item["startPage"] == item["endPage"]
            else f"{item['startPage']}-{item['endPage']}"
        )
        print(
            f"\n[{index}] {item['id']}  {item['sourceLabel']} PDF 第 {page_range} 页 "
            f"score={item['score']}"
        )
        print("层级: " + " > ".join(item["path"]))
        if item["components"]:
            print(
                "组成: "
                + " | ".join(
                    f"{component.get('number', '')} {component['title']}".strip()
                    for component in item["components"]
                )
            )
        if item["precisionSensitivePages"]:
            pages = ", ".join(str(page) for page in item["precisionSensitivePages"])
            print(f"数值/公式/单位敏感页: {pages}")
        print(f"校正版页级标签分布: {item['reviewPriorityCounts']}")
        print("内容摘录: " + item["excerpt"])
    print("\n展开方法: method <方法卡ID>。")
    return 0


def method(args: argparse.Namespace) -> int:
    """按方法卡 ID 展开完整层级和最终校正页文。"""
    card = next((item for item in runtime_method_cards() if item.get("id") == args.card_id), None)
    if card is None:
        raise ValueError(f"未找到方法卡: {args.card_id}")
    if "bookId" in card:
        page_map = load_external_page_map(str(card["bookId"]))
        structured_pages = [
            page_map[page]
            for page in range(int(card["startPage"]), int(card["endPage"]) + 1)
            if page in page_map
        ]
        printable_pages = [
            {"page": page["page"], "text": render_corrected_page(page)}
            for page in structured_pages
        ]
        source_label = str(card["sourceLabel"])
    else:
        structured_pages = [
            load_corrected_page(int(card["volume"]), int(page["page"]))
            for page in card.get("pages", [])
        ]
        printable_pages = card.get("pages", [])
        source_label = str(card["volumeLabel"])
    payload = {
        **card,
        "structuredPages": structured_pages,
        "pageNumbering": "PDF 页码",
        "precisionRule": "所有文字、公式、上下标、化学式、单位和表格均取自最终校正页。",
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    page_range = (
        str(card["startPage"])
        if card["startPage"] == card["endPage"]
        else f"{card['startPage']}-{card['endPage']}"
    )
    print(f"{card['id']}  {source_label} PDF 第 {page_range} 页")
    print("层级: " + " > ".join(card["path"]))
    if card.get("components"):
        print("\n方法层级:")
        for component in card["components"]:
            component_range = (
                str(component["startPage"])
                if component["startPage"] == component["endPage"]
                else f"{component['startPage']}-{component['endPage']}"
            )
            number = f"{component.get('number')} " if component.get("number") else ""
            print(
                f"- [{component['role']}] {number}{component['title']}"
                f"（PDF {component_range} 页）"
            )
    for page in printable_pages:
        marker = " [公式/单位敏感]" if page["page"] in card.get("precisionSensitivePages", []) else ""
        print(f"\n===== {source_label} PDF 第 {page['page']} 页{marker} =====")
        print(page.get("text") or "")
    print("\n[精确性规则] " + payload["precisionRule"])
    return 0


def outline_search(args: argparse.Namespace) -> int:
    concepts = query_concepts(args.query)
    results: list[dict[str, Any]] = []
    for volume in selected_volumes(args.volume):
        data = load_volume(volume)
        for record in outline_records(data):
            title = str(record["title"])
            path_text = " > ".join(record["path"])
            score = score_page(args.query, concepts, title, [path_text])
            if score <= 0:
                continue
            results.append({**record, "score": score})
    results.sort(
        key=lambda item: (
            -item["score"],
            item["volume"],
            item["startPage"],
            item["depth"],
        )
    )
    results = results[: args.top]
    if args.json:
        print(
            json.dumps(
                {
                    "query": args.query,
                    "expandedConcepts": concepts,
                    "resultCount": len(results),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not results:
        print("未找到匹配的目录节点。")
        return 1
    print(f"层级查询: {args.query}")
    for index, item in enumerate(results, 1):
        path = " > ".join(item["path"])
        print(
            f"\n[{index}] {item['volumeLabel']} PDF {item['startPage']}-{item['endPage']} 页 "
            f"role={item['role']} score={item['score']}"
        )
        print(f"层级: {path}")
    return 0


def page_text(data: VolumeData, page: int) -> str:
    if page < 1 or page > data.page_count:
        raise ValueError(f"{data.label}页码必须在 1-{data.page_count} 之间")
    # 索引按页码顺序建立，但仍显式校验。
    candidate = data.pages[page - 1]
    if int(candidate["page"]) == page:
        return str(candidate.get("text") or "")
    for candidate in data.pages:
        if int(candidate["page"]) == page:
            return str(candidate.get("text") or "")
    raise ValueError(f"索引中缺少 {data.label} PDF 第 {page} 页")


def show(args: argparse.Namespace) -> int:
    data = load_volume(args.volume)
    if args.end is not None and args.around:
        raise ValueError("--end 与 --around 不能同时使用")
    if args.end is not None:
        start, end = args.page, args.end
    else:
        start = max(1, args.page - args.around)
        end = min(data.page_count, args.page + args.around)
    if end < start:
        raise ValueError("结束页不能小于起始页")
    if end - start + 1 > 20 and not args.force:
        raise ValueError("一次最多展开 20 页；确需更多时加 --force")

    pages: list[dict[str, Any]] = []
    for page in range(start, end + 1):
        active, on_page = outline_context(data, page)
        pages.append(
            {
                "volume": args.volume,
                "volumeLabel": data.label,
                "page": page,
                "headingsOnPage": on_page,
                "activeOutline": active,
                "text": page_text(data, page),
                "structuredContent": load_corrected_page(args.volume, page),
            }
        )
    if args.json:
        print(
            json.dumps(
                {
                    "title": data.title,
                    "pageNumbering": "PDF 页码",
                    "pages": pages,
                    "corpus": "最终逐页校正语料",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    for item in pages:
        print(f"\n===== {item['volumeLabel']} PDF 第 {item['page']} 页 =====")
        if item["headingsOnPage"]:
            print("目录节点: " + " | ".join(item["headingsOnPage"]))
        print(item["text"])
    print("\n[提示] 以上为最终逐页校正语料；JSON 模式同时返回公式、表格和层级的结构化值。")
    return 0


def show_book(args: argparse.Namespace) -> int:
    source = next(
        (item for item in runtime_auxiliary_sources() if item.get("bookId") == args.book_id),
        None,
    )
    if source is None:
        raise ValueError(f"未找到已启用的外部来源: {args.book_id}")
    pages = load_external_page_map(args.book_id)
    end = args.end if args.end is not None else args.page
    if end < args.page:
        raise ValueError("结束页不能小于起始页")
    if end - args.page + 1 > 20 and not args.force:
        raise ValueError("一次最多展开20页；确需更多时加--force")
    selected = [pages[page] for page in range(args.page, end + 1) if page in pages]
    if not selected:
        raise ValueError("所选页不在该来源的内置范围内")
    if args.json:
        print(
            json.dumps(
                {
                    "bookId": args.book_id,
                    "sourceLabel": source["label"],
                    "pages": selected,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    for record in selected:
        print(f"\n===== {source['label']} PDF 第 {record['page']} 页 =====")
        print(render_corrected_page(record))
    return 0


def sources(args: argparse.Namespace) -> int:
    initial = [
        {"bookId": "volume-1", "label": "《土壤采样与分析方法》上册", "runtimeReady": True, "includedPageCount": 557},
        {"bookId": "volume-2", "label": "《土壤采样与分析方法》下册", "runtimeReady": True, "includedPageCount": 358},
    ]
    samr = load_samr_payload()
    rows = [
        *initial,
        *(load_external_payload().get("sources") or []),
        *(samr.get("sources") or []),
        *(samr.get("missingSources") or []),
    ]
    if args.json:
        print(json.dumps({"sources": rows}, ensure_ascii=False, indent=2))
        return 0
    for row in rows:
        print(
            f"{row['bookId']}\tready={str(bool(row.get('runtimeReady'))).lower()}\t"
            f"pages={row.get('includedPageCount')}\t{row['label']}"
        )
    return 0


def precision_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and PRECISION_LINE.search(line)]


def compare(args: argparse.Namespace) -> int:
    data = load_volume(args.volume)
    vision = page_text(data, args.page)
    tesseract_pages = load_tesseract_pages(args.volume)
    if args.page > len(tesseract_pages):
        raise ValueError(f"Tesseract 索引中缺少 {data.label} PDF 第 {args.page} 页")
    tesseract = tesseract_pages[args.page - 1].strip()
    paddle_record = load_paddle_page(args.volume, args.page)
    paddle = "\n".join(paddle_record.get("lines", [])) if paddle_record else ""
    review_priority = load_review_status().get((args.volume, args.page), "unknown")
    similarity = SequenceMatcher(
        None,
        normalize(vision),
        normalize(tesseract),
        autojunk=False,
    ).ratio()
    active, on_page = outline_context(data, args.page)
    payload = {
        "volume": args.volume,
        "volumeLabel": data.label,
        "page": args.page,
        "pageNumbering": "PDF 页码",
        "activeOutline": active,
        "headingsOnPage": on_page,
        "normalizedSimilarity": round(similarity, 6),
        "reviewPriority": review_priority,
        "visionPrecisionLines": precision_lines(vision),
        "tesseractPrecisionLines": precision_lines(tesseract),
        "paddleAvailable": paddle_record is not None,
        "paddleEngine": paddle_record.get("engine", "") if paddle_record else "",
        "paddlePrecisionLines": precision_lines(paddle) if paddle_record else [],
        "visionText": vision,
        "tesseractText": tesseract,
        "paddleText": paddle,
        "decisionRule": (
            "两引擎字符一致时才可直接采用公式、单位、上下标或数值；"
            "Paddle 可用时必须一并比较；任何分歧都保留识别版本并标记待核对。"
        ),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"{data.label} PDF 第 {args.page} 页")
    if active:
        print("层级: " + " > ".join(active))
    print(f"规范化全页相似度: {similarity:.4f}")
    print(f"OCR 复核优先级: {review_priority}")
    print("\n--- Apple Vision 高风险行 ---")
    print("\n".join(payload["visionPrecisionLines"]) or "(无)")
    print("\n--- Tesseract 高风险行 ---")
    print("\n".join(payload["tesseractPrecisionLines"]) or "(无)")
    if paddle_record:
        print("\n--- PaddleOCR 高风险行 ---")
        print("\n".join(payload["paddlePrecisionLines"]) or "(无)")
    else:
        print("\n--- PaddleOCR ---")
        print("本页无第三引擎复核记录。")
    if args.full:
        print("\n--- Apple Vision 全页 ---")
        print(vision)
        print("\n--- Tesseract 全页 ---")
        print(tesseract)
        if paddle_record:
            print("\n--- PaddleOCR 全页 ---")
            print(paddle)
    print("\n判定规则: " + payload["decisionRule"])
    return 0


def chapters(args: argparse.Namespace) -> int:
    rows: list[dict[str, Any]] = []
    for volume in selected_volumes(args.volume):
        data = load_volume(volume)
        chapters_in_volume = [
            entry
            for entry in data.outline
            if int(entry.get("depth", 0)) == 1
            and re.match(r"^第\s*\d+\s*章", str(entry.get("title", "")))
        ]
        for index, entry in enumerate(chapters_in_volume):
            next_page = (
                int(chapters_in_volume[index + 1]["page"]) - 1
                if index + 1 < len(chapters_in_volume)
                else data.page_count
            )
            rows.append(
                {
                    "volume": volume,
                    "volumeLabel": data.label,
                    "title": entry["title"],
                    "startPage": int(entry["page"]),
                    "endPage": next_page,
                }
            )
    if args.json:
        print(json.dumps({"chapterCount": len(rows), "chapters": rows}, ensure_ascii=False, indent=2))
        return 0
    for item in rows:
        print(
            f"{item['volumeLabel']} PDF {item['startPage']}-{item['endPage']} 页\t{item['title']}"
        )
    print(f"\n共 {len(rows)} 章。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="离线检索《土壤采样与分析方法》的试验方法。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="显示全书逐页校正和运行时可用状态")
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(func=corpus_status)

    consult_parser = subparsers.add_parser("consult", help="按问题检索并比较结构化方法候选")
    consult_parser.add_argument("query", help="咨询问题、待测指标、土壤类型、仪器或方法要求")
    consult_parser.add_argument("--volume", choices=("all", "1", "2"), default="all")
    consult_parser.add_argument("--top", type=int, default=5)
    consult_parser.add_argument("--excerpt", type=int, default=360, help="候选内容摘录最大字符数")
    consult_parser.add_argument("--json", action="store_true")
    consult_parser.set_defaults(func=consult)

    method_parser = subparsers.add_parser("method", help="按方法卡 ID 展开完整识别内容")
    method_parser.add_argument("card_id", help="consult 输出的方法卡 ID，例如 v2-s0014")
    method_parser.add_argument("--json", action="store_true")
    method_parser.set_defaults(func=method)

    search_parser = subparsers.add_parser("search", help="检索章节和全文")
    search_parser.add_argument("query", help="指标、样品、试剂、仪器或自然语言问题")
    search_parser.add_argument("--volume", choices=("all", "1", "2"), default="all")
    search_parser.add_argument("--top", type=int, default=8)
    search_parser.add_argument("--excerpt", type=int, default=300, help="摘录最大字符数")
    search_parser.add_argument("--json", action="store_true")
    search_parser.set_defaults(func=search)

    outline_parser = subparsers.add_parser("outline", help="按完整章节层级检索方法")
    outline_parser.add_argument("query", help="方法、指标或小节名称")
    outline_parser.add_argument("--volume", choices=("all", "1", "2"), default="all")
    outline_parser.add_argument("--top", type=int, default=12)
    outline_parser.add_argument("--json", action="store_true")
    outline_parser.set_defaults(func=outline_search)

    show_parser = subparsers.add_parser("show", help="展开一页或连续页最终校正内容")
    show_parser.add_argument("volume", type=int, choices=(1, 2))
    show_parser.add_argument("page", type=int, help="起始 PDF 页码")
    show_parser.add_argument("--end", type=int, help="结束 PDF 页码（含）")
    show_parser.add_argument("--around", type=int, default=0, help="同时显示前后 N 页")
    show_parser.add_argument("--force", action="store_true", help="允许一次展开超过 20 页")
    show_parser.add_argument("--json", action="store_true")
    show_parser.set_defaults(func=show)

    show_book_parser = subparsers.add_parser("show-book", help="展开附加来源的一页或连续页校正内容")
    show_book_parser.add_argument("book_id", help="sources命令列出的bookId")
    show_book_parser.add_argument("page", type=int, help="起始PDF页码")
    show_book_parser.add_argument("--end", type=int, help="结束PDF页码（含）")
    show_book_parser.add_argument("--force", action="store_true", help="允许一次展开超过20页")
    show_book_parser.add_argument("--json", action="store_true")
    show_book_parser.set_defaults(func=show_book)

    compare_parser = subparsers.add_parser("compare", help="逐页对照两套 OCR，核查公式和单位")
    compare_parser.add_argument("volume", type=int, choices=(1, 2))
    compare_parser.add_argument("page", type=int, help="PDF 页码")
    compare_parser.add_argument("--full", action="store_true", help="同时输出两套全页文本")
    compare_parser.add_argument("--json", action="store_true")
    compare_parser.set_defaults(func=compare)

    chapter_parser = subparsers.add_parser("chapters", help="列出章节及页码范围")
    chapter_parser.add_argument("--volume", choices=("all", "1", "2"), default="all")
    chapter_parser.add_argument("--json", action="store_true")
    chapter_parser.set_defaults(func=chapters)

    sources_parser = subparsers.add_parser("sources", help="列出全部独立来源及运行时状态")
    sources_parser.add_argument("--json", action="store_true")
    sources_parser.set_defaults(func=sources)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if hasattr(args, "top") and args.top < 1:
        parser.error("--top 必须大于 0")
    if hasattr(args, "excerpt") and args.excerpt < 80:
        parser.error("--excerpt 不能小于 80")
    if hasattr(args, "around") and args.around < 0:
        parser.error("--around 不能为负数")
    try:
        if args.command != "status":
            require_verified_corpus()
        return int(args.func(args))
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(f"错误: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Scan accepted report text, rich units, revisions, links, and structure."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator
from xml.etree import ElementTree as ET


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

EXCLUDED_ACCEPTED_TAGS = {W + "del", W + "moveFrom"}
TEXT_PART_PATTERNS = (
    re.compile(r"^word/document\.xml$"),
    re.compile(r"^word/header\d*\.xml$"),
    re.compile(r"^word/footer\d*\.xml$"),
    re.compile(r"^word/footnotes\.xml$"),
    re.compile(r"^word/endnotes\.xml$"),
    re.compile(r"^word/comments\.xml$"),
)


@dataclass
class Paragraph:
    index: int
    text: str
    style_id: str = ""
    style_name: str = ""
    raw_text: str = ""
    part: str = ""
    location: str = "body"
    vertical_align: list[str] = field(default_factory=list, repr=False)


@dataclass
class Finding:
    category: str
    severity: str
    paragraph: int | None
    style: str
    location: str
    part: str
    match: str
    context: str


RULES: dict[str, tuple[str, list[str]]] = {
    "editorial_instruction": (
        "error",
        [
            r"按(?:表|图)\s*\d+(?:\.\d+)?[^。；]{0,30}(?:重算|计算|修改)",
            r"以(?:表|图)\s*\d+(?:\.\d+)?为准",
            r"(?:面积|数据|指标|结果)[^。；]{0,30}不可混用",
            r"二者[^。；]{0,30}(?:功能|作用)[^。；]{0,20}(?:分开|分别)说明",
            r"(?:作者|编写人员)(?:应|需|需要|建议)",
            r"此处(?:应|需|需要|建议)[^。；]{0,30}(?:修改|补充|说明|删除)",
            r"(?:请|建议)(?:重新)?(?:核实|补充|修改|重算)",
        ],
    ),
    "validation_caveat": (
        "error",
        [
            r"(?:待|需|需要|还需|仍需)(?:进一步)?验证",
            r"交叉验证",
            r"多重验证",
            r"建议(?:进一步)?核实",
            r"数据(?:仍)?需核实",
        ],
    ),
    "model_conversation_trace": (
        "error",
        [
            r"希望(?:这|以上内容)对您有帮助",
            r"如需(?:进一步|继续)?(?:修改|补充|调整)",
            r"请告诉我",
            r"下面(?:将)?为您",
            r"您说得(?:完全)?正确",
        ],
    ),
    "management_or_promotional": (
        "warning",
        [
            r"口径",
            r"闭环",
            r"赋能",
            r"抓手",
            r"底色",
            r"赛道",
            r"精准施策",
            r"久久为功",
            r"多措并举",
            r"协同发力",
            r"全面发力",
            r"形成合力",
            r"提质增效",
            r"打造[^，。；]{0,20}(?:高地|名片|样板)",
            r"(?:擦亮|塑造)[^，。；]{0,20}名片",
            r"谱写[^，。；]{0,20}篇章",
            r"注入[^，。；]{0,20}动力",
        ],
    ),
    "model_like_abstraction": (
        "warning",
        [
            r"用于刻画",
            r"刻画了",
            r"对应关系",
            r"具有(?:十分)?重要(?:的)?意义",
            r"提供(?:了)?坚实(?:的)?支撑",
            r"奠定(?:了)?坚实(?:的)?基础",
            r"充分彰显",
            r"深刻揭示",
            r"不难发现",
            r"从某种意义上说",
            r"值得注意的是",
            r"需要指出的是",
        ],
    ),
    "table_figure_shell": (
        "warning",
        [
            r"由(?:表|图)\s*\d+(?:\.\d+)?可知",
            r"从(?:表|图)\s*\d+(?:\.\d+)?中可以(?:直观)?看出",
            r"(?:表|图)\s*\d+(?:\.\d+)?列出了[^。；]{0,30}(?:情况|数据|结果)",
            r"具体数据见(?:下表|表\s*\d+(?:\.\d+)?)",
            r"如下图所示",
            r"以上数据充分说明",
            r"^\s*[（(]?(?:参见|详见|见)?(?:表|图)\s*\d+(?:[.．-]\d+)+[）)]?[。.]?\s*$",
        ],
    ),
    "evidence_strength_candidate": (
        "review",
        [
            r"(?:显著|明显|普遍|广泛|严重|突出|主导|集中连片)",
            r"(?:证明|证实|决定|揭示了?[^，。；]{0,12}机制)",
            r"(?:导致|造成|驱动)[^，。；]{0,30}",
        ],
    ),
    "time_trend_candidate": (
        "review",
        [r"近年来", r"长期以来", r"(?:持续|不断|逐步|日益)(?:上升|下降|增加|减少|改善|加重|提高|降低|扩大)"],
    ),
    "quantitative_expression_candidate": (
        "review",
        [
            r"(?:增加|减少|提高|降低)了?\d+(?:\.\d+)?倍",
            r"(?:占比|比例)(?:达到|为)?\d+(?:\.\d+)?%",
            r"(?:大部分|绝大多数|少数|居首|排名第[一二三四五六七八九十\d]+)",
        ],
    ),
    "grammar_candidate": (
        "warning",
        [
            r"通过[^。；]{0,40}[，,]使",
            r"随着[^。；]{0,40}[，,]使",
            r"基于[^，。；]{0,30}下",
            r"围绕[^，。；]{0,30}为目标",
            r"对于[^，。；]{0,20}方面",
            r"原因是由于",
            r"(?:现状情况|主要原因因素|基本上大致|相对比较|分别各自|进行分析研究)",
        ],
    ),
    "soil_term_candidate": (
        "warning",
        [
            r"(?:土壤)?pH(?:值)?(?:含量|浓度)",
            r"(?:有机质|全氮|全磷|全钾|有效磷|速效钾)储量",
            r"容重越低越好",
            r"(?:中量|微量|中微量)?元素[^。；]{0,12}越高越好",
            r"(?:单项|仅凭)[^。；]{0,20}(?:耕地质量提升|土壤肥力提高)",
        ],
    ),
    "academic_register_candidate": ("review", [r"研究"]),
}

COMMENT_RULES = {"validation_caveat", "model_conversation_trace", "management_or_promotional"}

RAW_RULES: dict[str, tuple[str, list[str]]] = {
    "circled_number_spacing": (
        "warning",
        [r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳](?=\S)"],
    ),
    "chinese_unit_candidate": (
        "review",
        [r"\d+(?:\.\d+)?\s*(?:平方千米|平方米|公顷|立方米|立方厘米|千米|公里|厘米|毫米|千克|公斤|毫克|毫升|摄氏度)"],
    ),
    "mu_requires_integer": ("error", [r"(?<![\d.])\d+\.\d+\s*亩"]),
    "decimal_precision_candidate": (
        "warning",
        [r"(?<![\d.])\d+\.(?:\d(?!\d)|\d{3,})(?=\s*(?:%|万亩|km²|m²|hm²|m³|km|m|cm|mm|kg|g|mg|L|mL|℃))"],
    ),
}


def _text_part(name: str) -> bool:
    return any(pattern.match(name) for pattern in TEXT_PART_PATTERNS)


def _base_location(part: str) -> str:
    if part == "word/document.xml":
        return "body"
    for prefix, label in (
        ("word/header", "header"),
        ("word/footer", "footer"),
        ("word/footnotes", "footnote"),
        ("word/endnotes", "endnote"),
        ("word/comments", "comment"),
    ):
        if part.startswith(prefix):
            return label
    return "other"


def _location_with(location: str, suffix: str) -> str:
    pieces = location.split("_")
    return location if suffix in pieces else location + "_" + suffix


def iter_paragraph_elements(element: ET.Element, location: str) -> Iterator[tuple[ET.Element, str]]:
    """Yield all paragraphs, including tables and text boxes, in XML order."""
    current = location
    if element.tag == W + "tbl":
        current = _location_with(current, "table")
    elif element.tag == W + "txbxContent":
        current = _location_with(current, "textbox")
    if element.tag == W + "p":
        yield element, current
    for child in list(element):
        yield from iter_paragraph_elements(child, current)


def rich_accepted_text(paragraph: ET.Element) -> tuple[str, list[str]]:
    chars: list[str] = []
    aligns: list[str] = []

    def append(value: str, align: str) -> None:
        chars.extend(value)
        aligns.extend([align] * len(value))

    def walk(node: ET.Element, align: str = "", root: bool = False) -> None:
        if not root and node.tag == W + "p":
            return
        if node.tag in EXCLUDED_ACCEPTED_TAGS:
            return
        current_align = align
        if node.tag == W + "r":
            rpr = node.find(W + "rPr")
            if rpr is not None:
                vert = rpr.find(W + "vertAlign")
                if vert is not None:
                    current_align = vert.get(W + "val", "")
        if node.tag == W + "t":
            append(node.text or "", current_align)
            return
        if node.tag == W + "tab":
            append("\t", current_align)
            return
        if node.tag in {W + "br", W + "cr"}:
            append("\n", current_align)
            return
        for child in list(node):
            walk(child, current_align, False)

    walk(paragraph, root=True)
    raw = "".join(chars).translate(str.maketrans({"\t": " ", "\r": " ", "\n": " "}))
    start = 0
    end = len(raw)
    while start < end and raw[start].isspace():
        start += 1
    while end > start and raw[end - 1].isspace():
        end -= 1
    return raw[start:end], aligns[start:end]


def load_style_names(zf: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = ET.fromstring(zf.read("word/styles.xml"))
    except KeyError:
        return {}
    names: dict[str, str] = {}
    for style in root.findall(W + "style"):
        style_id = style.get(W + "styleId", "")
        name = style.find(W + "name")
        names[style_id] = name.get(W + "val", style_id) if name is not None else style_id
    return names


def paragraph_style(paragraph: ET.Element, styles: dict[str, str]) -> tuple[str, str]:
    ppr = paragraph.find(W + "pPr")
    if ppr is None:
        return "", ""
    node = ppr.find(W + "pStyle")
    if node is None:
        return "", ""
    style_id = node.get(W + "val", "")
    return style_id, styles.get(style_id, style_id)


def _source_part_from_rels(rels_part: str) -> str | None:
    if rels_part == "_rels/.rels":
        return None
    directory, filename = posixpath.split(rels_part)
    if posixpath.basename(directory) != "_rels" or not filename.endswith(".rels"):
        return None
    source_dir = posixpath.dirname(directory)
    return posixpath.join(source_dir, filename[:-5])


def _paragraph_anchor(root: ET.Element, element: ET.Element) -> str:
    parents = {child: parent for parent in root.iter() for child in parent}
    current: ET.Element | None = element
    while current is not None and current.tag != W + "p":
        current = parents.get(current)
    if current is None:
        return ""
    return rich_accepted_text(current)[0][:160]


def relationship_findings(zf: zipfile.ZipFile) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    names = set(zf.namelist())
    for rels_part in sorted(name for name in names if name.endswith(".rels")):
        try:
            rel_root = ET.fromstring(zf.read(rels_part))
        except (ET.ParseError, KeyError):
            continue
        source_part = _source_part_from_rels(rels_part)
        source_root = None
        if source_part and source_part in names:
            try:
                source_root = ET.fromstring(zf.read(source_part))
            except ET.ParseError:
                source_root = None
        for rel in rel_root.findall(PKG_REL + "Relationship"):
            if rel.get("TargetMode") != "External":
                continue
            rel_id = rel.get("Id", "")
            anchors: list[str] = []
            if source_root is not None and rel_id:
                for element in source_root.iter():
                    if rel_id in element.attrib.values():
                        anchor = _paragraph_anchor(source_root, element)
                        label = anchor or f"<{element.tag.rsplit('}', 1)[-1]}>"
                        if label not in anchors:
                            anchors.append(label)
            results.append(
                {
                    "relationships_part": rels_part,
                    "source_part": source_part or "package",
                    "id": rel_id,
                    "type": rel.get("Type", "").rsplit("/", 1)[-1],
                    "target": rel.get("Target", ""),
                    "anchors": anchors,
                }
            )
    return results


def _revision_stats(zf: zipfile.ZipFile) -> dict[str, int]:
    tags = {
        "insertions": W + "ins",
        "deletions": W + "del",
        "move_from": W + "moveFrom",
        "move_to": W + "moveTo",
        "paragraph_property_changes": W + "pPrChange",
        "run_property_changes": W + "rPrChange",
        "table_property_changes": W + "tblPrChange",
        "row_property_changes": W + "trPrChange",
        "cell_property_changes": W + "tcPrChange",
    }
    counts = Counter({key: 0 for key in tags})
    for name in zf.namelist():
        if not name.startswith("word/") or not name.endswith(".xml"):
            continue
        try:
            root = ET.fromstring(zf.read(name))
        except ET.ParseError:
            continue
        for key, tag in tags.items():
            counts[key] += len(root.findall(".//" + tag))
    return dict(counts)


def read_docx(path: Path) -> tuple[list[Paragraph], dict[str, object]]:
    with zipfile.ZipFile(path) as zf:
        styles = load_style_names(zf)
        paragraphs: list[Paragraph] = []
        table_count = 0
        drawing_count = 0
        field_count = 0
        scanned_parts: list[str] = []
        for part in sorted(name for name in zf.namelist() if _text_part(name)):
            try:
                root = ET.fromstring(zf.read(part))
            except ET.ParseError:
                continue
            scanned_parts.append(part)
            table_count += len(root.findall(".//" + W + "tbl"))
            drawing_count += len(root.findall(".//" + W + "drawing"))
            field_count += len(root.findall(".//" + W + "fldSimple"))
            field_count += len(root.findall(".//" + W + "instrText"))
            container = root.find(W + "body") if part == "word/document.xml" else root
            if container is None:
                continue
            for element, location in iter_paragraph_elements(container, _base_location(part)):
                raw_text, vertical_align = rich_accepted_text(element)
                text = re.sub(r"\s+", "", raw_text)
                style_id, style_name = paragraph_style(element, styles)
                paragraphs.append(
                    Paragraph(
                        index=len(paragraphs) + 1,
                        text=text,
                        style_id=style_id,
                        style_name=style_name,
                        raw_text=raw_text,
                        part=part,
                        location=location,
                        vertical_align=vertical_align,
                    )
                )

        locations = Counter(p.location for p in paragraphs if p.text)
        comments = 0
        if "word/comments.xml" in zf.namelist():
            try:
                comment_root = ET.fromstring(zf.read("word/comments.xml"))
                comments = len(comment_root.findall(W + "comment"))
            except ET.ParseError:
                pass
        stats: dict[str, object] = {
            "tables": table_count,
            "drawings": drawing_count,
            "fields": field_count,
            "comments": comments,
            "paragraphs_by_location": dict(locations),
            "scanned_parts": scanned_parts,
            "tracked_revisions": _revision_stats(zf),
            "external_relationships": relationship_findings(zf),
        }
        return paragraphs, stats


def read_txt(path: Path) -> tuple[list[Paragraph], dict[str, object]]:
    raw = path.read_text(encoding="utf-8-sig")
    blocks = [item.strip() for item in re.split(r"\n\s*\n", raw) if item.strip()]
    if len(blocks) == 1 and "\n" in blocks[0]:
        blocks = [line.strip() for line in blocks[0].splitlines() if line.strip()]
    paragraphs = [
        Paragraph(i, re.sub(r"\s+", "", value), raw_text=value, part=str(path), location="body")
        for i, value in enumerate(blocks, 1)
    ]
    return paragraphs, {
        "tables": None,
        "drawings": None,
        "fields": None,
        "comments": None,
        "paragraphs_by_location": {"body": len(paragraphs)},
        "scanned_parts": [str(path)],
        "tracked_revisions": None,
        "external_relationships": [],
    }


def heading_level(paragraph: Paragraph) -> int | None:
    marker = (paragraph.style_id + " " + paragraph.style_name).lower()
    match = re.search(r"(?:heading|标题)\s*([1-9])", marker)
    if match:
        return int(match.group(1))
    text = paragraph.text
    if re.match(r"^第[一二三四五六七八九十百\d]+章", text):
        return 1
    if re.match(r"^[一二三四五六七八九十]+、", text):
        return 2
    if re.match(r"^（[一二三四五六七八九十]+）", text):
        return 3
    if re.match(r"^\d+[.．、]\s*", paragraph.raw_text):
        return 4
    if re.match(r"^（\d+）", text):
        return 5
    return None


def is_caption(paragraph: Paragraph) -> bool:
    marker = (paragraph.style_id + " " + paragraph.style_name).lower()
    if any(token in marker for token in ("caption", "题注", "图题", "表题")):
        return True
    return bool(re.match(r"^(?:图|表)\s*\d+(?:[.．-]\d+)?", paragraph.raw_text) and len(paragraph.text) <= 100)


def is_heading_or_caption(paragraph: Paragraph) -> bool:
    marker = (paragraph.style_id + " " + paragraph.style_name).lower()
    if heading_level(paragraph) is not None or is_caption(paragraph):
        return True
    return any(token in marker for token in ("toc", "目录"))


def context(text: str, start: int, end: int, radius: int = 42) -> str:
    return text[max(0, start - radius):min(len(text), end + radius)]


def _finding(
    paragraph: Paragraph,
    category: str,
    severity: str,
    match: re.Match[str],
    source_text: str | None = None,
) -> Finding:
    source = source_text if source_text is not None else (paragraph.raw_text or paragraph.text)
    return Finding(
        category,
        severity,
        paragraph.index,
        paragraph.style_name,
        paragraph.location,
        paragraph.part,
        match.group(0),
        context(source, match.start(), match.end()),
    )


def _alignment_ok(paragraph: Paragraph, position: int, expected: str) -> bool:
    return 0 <= position < len(paragraph.vertical_align) and paragraph.vertical_align[position] == expected


def rich_unit_findings(paragraph: Paragraph) -> list[Finding]:
    results: list[Finding] = []
    text = paragraph.raw_text
    for match in re.finditer(r"(?i)(?<![A-Za-z])(?:km|hm|cm|mm|m)[23](?![A-Za-z0-9])", text):
        position = match.end() - 1
        if not _alignment_ok(paragraph, position, "superscript"):
            results.append(_finding(paragraph, "plain_unit_exponent", "error", match))
    for match in re.finditer(r"(?i)(?:g|mg)\s*[·/]\s*(?:kg|L|cm)-?[13](?!\d)", text):
        digit = max(text.rfind("1", match.start(), match.end()), text.rfind("3", match.start(), match.end()))
        if digit >= 0 and not _alignment_ok(paragraph, digit, "superscript"):
            results.append(_finding(paragraph, "plain_unit_exponent", "error", match))

    chemical = re.compile(r"(?<![A-Za-z0-9])(?:NH4\+?-N|NO3(?:-)?-N|P2O5|K2O|Ca2\+|Mg2\+)(?![A-Za-z0-9])")
    for match in chemical.finditer(text):
        token = match.group(0)
        failures = False
        for offset, char in enumerate(token):
            absolute = match.start() + offset
            if char.isdigit():
                expected = "superscript" if token.startswith(("Ca", "Mg")) else "subscript"
                failures = failures or not _alignment_ok(paragraph, absolute, expected)
            if char == "+":
                failures = failures or not _alignment_ok(paragraph, absolute, "superscript")
        if token.startswith("NO3"):
            charge_index = token.find("-", 3)
            if charge_index < 0 or token.count("-") < 2:
                failures = True
            else:
                failures = failures or not _alignment_ok(paragraph, match.start() + charge_index, "superscript")
        if failures:
            results.append(_finding(paragraph, "plain_chemical_subscript", "error", match))
    return results


def _repetitive_opening_findings(paragraphs: Iterable[Paragraph]) -> list[Finding]:
    openings = ("总体来看", "综合来看", "综上所述", "值得注意的是", "此外", "同时")
    groups: dict[str, list[Paragraph]] = {key: [] for key in openings}
    for paragraph in paragraphs:
        if paragraph.location != "body":
            continue
        for opening in openings:
            if paragraph.text.startswith(opening):
                groups[opening].append(paragraph)
    results: list[Finding] = []
    for opening, members in groups.items():
        if len(members) < 3:
            continue
        for paragraph in members:
            fake = re.match(re.escape(opening), paragraph.raw_text or paragraph.text)
            if fake:
                results.append(_finding(paragraph, "repetitive_paragraph_opening", "warning", fake))
    return results


def scan(
    paragraphs: list[Paragraph],
    min_chars: int,
    max_chars: int,
    salinization_status: str,
    length_scope: set[int] | None = None,
) -> tuple[list[Finding], list[dict[str, object]]]:
    findings: list[Finding] = []
    lengths: list[dict[str, object]] = []
    active_rules = dict(RULES)
    if salinization_status == "absent":
        active_rules["unexpected_salinization"] = ("error", [r"盐渍化", r"盐碱地"])

    for paragraph in paragraphs:
        if not paragraph.text:
            continue
        for category, (severity, regexes) in active_rules.items():
            if paragraph.location.startswith("comment") and category not in COMMENT_RULES:
                continue
            for regex in regexes:
                for match in re.finditer(regex, paragraph.text):
                    findings.append(_finding(paragraph, category, severity, match, paragraph.text))
        if not paragraph.location.startswith("comment"):
            for category, (severity, regexes) in RAW_RULES.items():
                for regex in regexes:
                    for match in re.finditer(regex, paragraph.raw_text):
                        findings.append(_finding(paragraph, category, severity, match, paragraph.raw_text))
            findings.extend(rich_unit_findings(paragraph))

        in_length_scope = length_scope is None or paragraph.index in length_scope
        if in_length_scope and paragraph.location == "body" and not is_heading_or_caption(paragraph) and len(paragraph.text) >= 80:
            if len(paragraph.text) < min_chars or len(paragraph.text) > max_chars:
                lengths.append(
                    {
                        "paragraph": paragraph.index,
                        "style": paragraph.style_name,
                        "characters": len(paragraph.text),
                        "kind": "short_candidate" if len(paragraph.text) < min_chars else "long_candidate",
                        "context": paragraph.raw_text[:100],
                    }
                )
    findings.extend(_repetitive_opening_findings(paragraphs))
    return findings, lengths


def select_body_paragraphs(
    paragraphs: list[Paragraph], start_regex: str | None = None, end_regex: str | None = None
) -> tuple[list[Paragraph], dict[str, object]]:
    candidates = [
        p for p in paragraphs
        if p.part == "word/document.xml" and p.location == "body" and p.text
    ]
    if not candidates and paragraphs and paragraphs[0].part.lower().endswith((".txt", ".md")):
        candidates = [p for p in paragraphs if p.location == "body" and p.text]
    start_at = 0
    start_found = False
    method = "fallback_all_body_paragraphs"
    if start_regex:
        compiled = re.compile(start_regex)
        for pos, paragraph in enumerate(candidates):
            if compiled.search(paragraph.raw_text):
                start_at = pos
                start_found = True
                method = "explicit_start_regex"
                break
    else:
        for pos, paragraph in enumerate(candidates):
            if heading_level(paragraph) == 1:
                start_at = pos
                start_found = True
                method = "first_heading_1"
                break
        if not start_found:
            directory_positions = [pos for pos, p in enumerate(candidates) if p.text == "目录"]
            after = directory_positions[-1] + 1 if directory_positions else 0
            for pos in range(after, len(candidates)):
                if heading_level(candidates[pos]) == 2:
                    start_at = pos
                    start_found = True
                    method = "first_top_heading_after_directory"
                    break

    end_at = len(candidates)
    if end_regex:
        compiled = re.compile(end_regex)
        for pos in range(start_at + 1, len(candidates)):
            if compiled.search(candidates[pos].raw_text):
                end_at = pos
                break
    else:
        for pos in range(start_at + 1, len(candidates)):
            paragraph = candidates[pos]
            if heading_level(paragraph) is not None and re.match(r"^(?:附件|附录)(?:\s|$|[一二三四五六七八九十\d])", paragraph.raw_text):
                end_at = pos
                break

    selected = [p for p in candidates[start_at:end_at] if not is_heading_or_caption(p)]
    info = {
        "method": method,
        "reliable": start_found or bool(start_regex),
        "start_paragraph": candidates[start_at].index if candidates else None,
        "end_before_paragraph": candidates[end_at].index if end_at < len(candidates) else None,
        "excluded_table_text": True,
        "excluded_front_matter": start_found,
        "excluded_attachments": end_at < len(candidates),
    }
    return selected, info


def _length_warning(
    count: int, level: str, report_type: str | None, reliable: bool
) -> tuple[dict[str, int | None] | None, dict[str, object] | None]:
    ranges: dict[tuple[str, str], tuple[int | None, int | None]] = {
        ("county", "overall"): (3000, 5000),
        ("county", "work"): (None, 15000),
        ("city", "overall"): (7000, 8000),
        ("city", "work"): (15000, 20000),
        ("province", "resource"): (30000, 50000),
    }
    if not report_type or (level, report_type) not in ranges:
        return None, None
    minimum, maximum = ranges[(level, report_type)]
    expected = {"min": minimum, "max": maximum}
    outside = (minimum is not None and count < minimum) or (maximum is not None and count > maximum)
    if not reliable:
        return expected, {
            "kind": "body_boundary_unreliable",
            "accepted_body_characters": count,
            "message": "Body boundary was not identified reliably; set --body-start-regex before enforcing length.",
        }
    if outside:
        return expected, {
            "kind": "outside_expected_range",
            "accepted_body_characters": count,
            "expected_min": minimum,
            "expected_max": maximum,
        }
    return expected, None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help=".docx or UTF-8 .txt/.md report")
    parser.add_argument("--min-body-chars", type=int, default=300)
    parser.add_argument("--max-body-chars", type=int, default=1000)
    parser.add_argument(
        "--salinization-status",
        choices=("unknown", "present", "absent"),
        default="unknown",
        help="default unknown; use absent only when the area is confirmed to have no salinization section",
    )
    parser.add_argument("--body-start-regex", help="regex matching the first main-body heading")
    parser.add_argument("--body-end-regex", help="regex matching the first heading after the main body")
    parser.add_argument("--level", choices=("province", "city", "county"), default="city")
    parser.add_argument("--report-type", choices=("overall", "work", "resource"))
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true", help="exit 1 when review leads exist")
    args = parser.parse_args()

    if args.input.suffix.lower() == ".docx":
        paragraphs, stats = read_docx(args.input)
    elif args.input.suffix.lower() in {".txt", ".md"}:
        paragraphs, stats = read_txt(args.input)
    else:
        parser.error("input must be .docx, .txt, or .md")

    body_paragraphs, body_scope = select_body_paragraphs(
        paragraphs, args.body_start_regex, args.body_end_regex
    )
    length_scope = {p.index for p in body_paragraphs}
    findings, length_warnings = scan(
        paragraphs,
        args.min_body_chars,
        args.max_body_chars,
        args.salinization_status,
        length_scope,
    )
    body_characters = sum(len(p.text) for p in body_paragraphs)
    expected_range, report_length_warning = _length_warning(
        body_characters, args.level, args.report_type, bool(body_scope["reliable"])
    )
    nonempty = [p for p in paragraphs if p.text]
    severity_counts = Counter(item.severity for item in findings)

    report = {
        "input": str(args.input.resolve()),
        "accepted_paragraphs": len(nonempty),
        "accepted_characters_all_scanned_parts": sum(len(p.text) for p in nonempty),
        "accepted_body_characters": body_characters,
        "body_scope": body_scope,
        "report_length_expected_range": expected_range,
        "level": args.level,
        "report_type": args.report_type,
        "report_length_warning": report_length_warning,
        "salinization_status": args.salinization_status,
        "stats": stats,
        "finding_counts_by_severity": dict(severity_counts),
        "findings": [asdict(item) for item in findings],
        "paragraph_length_warnings": length_warnings,
        "coverage": {
            "scans": [
                "accepted text in body, tables, headers, footers, footnotes, endnotes, comments and text boxes",
                "external relationship targets with source part and available anchor text",
                "insert/delete/move and property-revision counts",
                "ASCII unit and chemical tokens with run-level superscript/subscript properties",
            ],
            "does_not_certify": [
                "text embedded in raster images",
                "page layout, pagination or rendering quality",
                "explanatory-paragraph, table/figure and blank-line ordering",
                "all inherited fonts, colors and paragraph/table style effects",
            ],
        },
        "note": "Findings are review leads. Read the full sentence, table and figure context before editing; never batch-replace blindly.",
    }

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Input: {report['input']}")
        print(f"Accepted paragraphs in scanned parts: {report['accepted_paragraphs']}")
        print(f"Accepted characters in scanned parts: {report['accepted_characters_all_scanned_parts']}")
        print(f"Accepted main-body characters: {body_characters}")
        print("Body scope: " + json.dumps(body_scope, ensure_ascii=False))
        if expected_range:
            print("Expected body range: " + json.dumps(expected_range, ensure_ascii=False))
        if report_length_warning:
            print("Report length warning: " + json.dumps(report_length_warning, ensure_ascii=False))
        print("Stats: " + json.dumps(stats, ensure_ascii=False))
        print(f"Risk findings: {len(findings)} " + json.dumps(dict(severity_counts), ensure_ascii=False))
        for item in findings:
            print(
                f"  [{item.severity}/{item.category}] p{item.paragraph} "
                f"{item.location} {item.match!r} | {item.context}"
            )
        print(f"Paragraph length warnings: {len(length_warnings)}")
        for item in length_warnings:
            print(f"  [{item['kind']}] p{item['paragraph']} {item['characters']} chars | {item['context']}")
        print(report["note"])

    has_issues = bool(
        findings
        or length_warnings
        or report_length_warning
        or stats.get("external_relationships")
    )
    return 1 if args.strict and has_issues else 0


if __name__ == "__main__":
    sys.exit(main())


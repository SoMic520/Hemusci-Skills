#!/usr/bin/env python3
"""Generate a polished, source-faithful HTML/PDF soil-method report."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import find_methods as methods
from corrected_corpus import load_corrected_page, render_corrected_page

REPORTLAB_IMPORT_ERROR: ModuleNotFoundError | None = None
try:
    from reportlab.graphics.shapes import Circle, Drawing, Line, Path as ShapePath, Rect
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ModuleNotFoundError as error:
    REPORTLAB_IMPORT_ERROR = error


SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = Path("output")
FONT_REGULAR = "SoilHeiti"
FONT_BOLD = "SoilHeitiBold"
FONT_SERIF = "SoilSongti"
FONT_SERIF_BOLD = "SoilSongtiBold"
FONT_FORMULA = "SoilFormula"

ROLE_LABELS = {
    "scope": "适用范围",
    "principle": "方法原理",
    "materials": "材料",
    "reagents": "试剂",
    "apparatus": "仪器设备",
    "preparation": "样品制备",
    "calibration": "校准",
    "procedure": "操作步骤",
    "measurement": "测定",
    "calculation": "结果计算",
    "quality_control": "质量控制",
    "interference": "干扰与限制",
    "notes": "注释",
    "caution": "注意事项",
    "safety": "安全",
    "reporting": "结果报告",
    "section": "方法条款",
}


def reexec_with_bundled_runtime() -> None:
    """Restart a direct report command in Codex's document runtime when needed."""
    python = (
        Path.home()
        / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
    )
    if not python.is_file() or Path(sys.executable).resolve() == python.resolve():
        missing = REPORTLAB_IMPORT_ERROR.name if REPORTLAB_IMPORT_ERROR else "PDF dependencies"
        raise RuntimeError(f"缺少 {missing}，无法生成 PDF")
    os.execv(str(python), [str(python), *sys.argv])


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def stable_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-.")
    return cleaned[:120] or "soil-method-report"


def page_range(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"


def unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def resolved_source_label(card: dict[str, Any], pages: list[dict[str, Any]]) -> str:
    explicit = str(card.get("sourceLabel") or "").strip()
    if explicit:
        return explicit
    for page in pages:
        for block in page.get("blocks") or []:
            if block.get("type") == "running-header" and str(block.get("text") or "").strip():
                return str(block["text"]).strip()
    return str(card.get("volumeLabel") or "本地已校正资料")


def full_source_citation(card: dict[str, Any], pages: list[dict[str, Any]]) -> str:
    label = resolved_source_label(card, pages)
    path = [str(value).strip() for value in card.get("path") or [] if str(value).strip()]
    return f"{label}；方法层级：{' > '.join(path)}" if path else label


def method_overview(card: dict[str, Any], pages: list[dict[str, Any]]) -> str:
    """Return the first exact method-level rationale paragraph when structured."""
    component_numbers = {
        heading_number(value, index)
        for index, value in enumerate(card.get("components") or [], 1)
    }
    started = False
    for page in pages:
        for block in page.get("blocks") or []:
            if block.get("type") == "section-heading":
                number = str(block.get("number") or "")
                if number in component_numbers:
                    return ""
                started = True
                continue
            if started and block.get("type") == "paragraph":
                text = str(block.get("text") or "").strip()
                if text:
                    return text
    return ""


def icon(name: str) -> str:
    paths = {
        "why": '<path d="M12 3a7 7 0 0 0-4 12.74V19h8v-3.26A7 7 0 0 0 12 3Z"/><path d="M9 22h6M9 16h6"/>',
        "steps": '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
        "calc": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 12h2M14 12h2M8 16h2M14 16h2"/>',
        "shield": '<path d="M12 3 5 6v5c0 4.5 2.8 8.1 7 10 4.2-1.9 7-5.5 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-5"/>',
        "source": '<path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 12h6M9 16h6M9 8h2"/>',
        "flask": '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3"/><path d="M8 15h8"/>',
        "target": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 2v3M22 12h-3"/>',
    }
    return (
        '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" '
        'fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>'
    )


def load_card(card_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    methods.require_verified_corpus()
    card = next((item for item in methods.runtime_method_cards() if item.get("id") == card_id), None)
    if card is None:
        raise ValueError(f"未找到可用的方法记录: {card_id}")
    if card.get("bookId"):
        page_map = methods.load_external_page_map(str(card["bookId"]))
        pages = [
            page_map[page]
            for page in range(int(card["startPage"]), int(card["endPage"]) + 1)
            if page in page_map
        ]
    else:
        pages = [
            load_corrected_page(int(card["volume"]), int(page["page"]))
            for page in card.get("pages") or []
        ]
    if not pages:
        raise ValueError("方法记录没有可用的校正页")
    return card, pages


def find_card_for_query(query: str) -> str:
    concepts = methods.query_concepts(query)
    ranked: list[tuple[float, str]] = []
    for card in methods.runtime_method_cards():
        if card.get("bookId"):
            text = methods.external_card_text(card)
        else:
            text = "\n".join(str(page.get("text") or "") for page in card.get("pages") or [])
        headings = [
            *(str(value) for value in card.get("path") or []),
            *(str(value.get("title") or "") for value in card.get("components") or []),
        ]
        score = methods.score_page(query, concepts, text, headings)
        title_norm = methods.normalize(str(card.get("title") or ""))
        for concept in concepts:
            normalized = methods.normalize(concept)
            if normalized and normalized in title_norm:
                score += 90
        if card.get("kind") == "method":
            score += 45
        if score > 45:
            ranked.append((score, str(card["id"])))
    if not ranked:
        raise ValueError("未找到可用的方法记录；请先用 consult 补充指标或仪器条件")
    ranked.sort(key=lambda value: (-value[0], value[1]))
    return ranked[0][1]


def extract_formulas(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for page in pages:
        for formula in page.get("formulas") or []:
            plain = str(
                formula.get("plain")
                or formula.get("displayAsPrinted")
                or formula.get("display")
                or ""
            ).strip()
            label = str(formula.get("label") or formula.get("number") or "")
            key = (label, plain)
            if not plain or key in seen:
                continue
            seen.add(key)
            values.append({**formula, "page": int(page["page"]), "plain": plain, "label": label})
    return values


def extract_verified_definitions(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in pages:
        for block in page.get("blocks") or []:
            text = str(block.get("text") or "").strip()
            if block.get("type") not in {
                "verified-page-transcription",
                "formula-explanation",
                "conversion-item",
            } or not text:
                continue
            if text in seen:
                continue
            if "─" in text or "单位" in text or re.search(r"[=]​?|10[⁻⁺⁰-⁹]", text):
                seen.add(text)
                rows.append({"page": int(page["page"]), "text": text})
    return rows


def extract_tables(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for page in pages:
        for index, table in enumerate(page.get("tables") or [], 1):
            tables.append({**table, "page": int(page["page"]), "index": index})
    return tables


def source_digest(card: dict[str, Any], pages: list[dict[str, Any]]) -> str:
    payload = {
        "card": card.get("id"),
        "pages": [(page.get("page"), page.get("contentSha256")) for page in pages],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def heading_number(value: dict[str, Any], fallback: int) -> str:
    explicit = str(value.get("number") or "").strip()
    if explicit:
        return explicit
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)*)", str(value.get("title") or ""))
    return match.group(1) if match else str(fallback)


def component_details(card: dict[str, Any], pages: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Extract exact structured blocks bounded by component headings."""
    components = list(card.get("components") or [])
    if not components:
        return {}
    flattened: list[tuple[int, dict[str, Any]]] = []
    for page in pages:
        flattened.extend((int(page["page"]), block) for block in page.get("blocks") or [])
    component_numbers = [heading_number(value, index) for index, value in enumerate(components, 1)]
    start_indices: dict[str, int] = {}
    structured_mode = False
    for index, (_, block) in enumerate(flattened):
        if block.get("type") != "section-heading":
            continue
        number = str(block.get("number") or "").strip()
        if number in component_numbers and number not in start_indices:
            start_indices[number] = index
            structured_mode = True
    if not start_indices:
        for index, (_, block) in enumerate(flattened):
            if block.get("type") != "official-reader-ocr-line":
                continue
            text = str(block.get("text") or "").strip()
            for number in component_numbers:
                if number not in start_indices and re.match(rf"^{re.escape(number)}(?=\s|$)", text):
                    start_indices[number] = index
                    break
    if not start_indices:
        return {}
    root_match = re.match(r"\s*([0-9]+(?:\.[0-9]+)*)", str(card.get("title") or ""))
    root_number = root_match.group(1) if root_match else ""
    result: dict[str, list[dict[str, Any]]] = {}
    ignored = {"running-header", "printed-page-number", "section-heading"}
    for position, number in enumerate(component_numbers):
        start = start_indices.get(number)
        if start is None:
            continue
        later = [start_indices[value] for value in component_numbers[position + 1 :] if value in start_indices]
        end = min(later) if later else len(flattened)
        if not later and root_number:
            for index in range(start + 1, len(flattened)):
                block = flattened[index][1]
                next_number = str(block.get("number") or "")
                if block.get("type") == "section-heading" and next_number and not next_number.startswith(root_number + "."):
                    end = index
                    break
        rows: list[dict[str, Any]] = []
        if structured_mode:
            for page, block in flattened[start + 1 : end]:
                if str(block.get("type") or "") in ignored:
                    continue
                text = str(block.get("text") or block.get("title") or "").strip()
                name = str(block.get("name") or "").strip()
                if name and name not in text:
                    text = f"{name}：{text}" if text else name
                if not text:
                    continue
                rows.append({"page": page, "number": str(block.get("number") or ""), "text": text})
        else:
            grouped: dict[int, list[str]] = {}
            component = components[position]
            component_title = methods.normalize(re.sub(r"^\s*[0-9.]+\s*", "", str(component.get("title") or "")))
            for page, block in flattened[start + 1 : end]:
                if block.get("type") != "official-reader-ocr-line":
                    continue
                text = str(block.get("text") or "").strip()
                if not text or text.startswith("GB/T "):
                    continue
                if component_title and methods.normalize(text) == component_title:
                    continue
                grouped.setdefault(page, []).append(text)
            rows = [
                {"page": page, "number": "", "text": " ".join(values)}
                for page, values in grouped.items()
                if values
            ]
        if rows:
            result[number] = rows
    return result


def render_components(card: dict[str, Any], pages: list[dict[str, Any]]) -> str:
    components = list(card.get("components") or [])
    if not components:
        return ""
    details = component_details(card, pages)
    if len(components) > 18 and details:
        components = [
            value
            for index, value in enumerate(components, 1)
            if details.get(heading_number(value, index))
        ]
    rows = []
    for index, component in enumerate(components, 1):
        number = heading_number(component, index)
        title = str(component.get("title") or "")
        role = ROLE_LABELS.get(str(component.get("role") or "section"), "方法条款")
        start = int(component.get("startPage", card["startPage"]))
        end = int(component.get("endPage", start))
        level = int(component.get("level", 1))
        detail_rows = details.get(number) or []
        detail_html = ""
        if detail_rows:
            detail_html = '<div class="step-detail">' + "".join(
                '<p>'
                + (f'<b>{esc(item["number"])}</b>' if item["number"] else "")
                + f'<span>{esc(item["text"])}</span><small>P.{item["page"]}</small></p>'
                for item in detail_rows
            ) + "</div>"
        rows.append(
            f'<div class="step level-{min(level, 4)}">'
            f'<div class="step-no">{esc(number)}</div>'
            '<div class="step-body"><div class="step-heading">'
            f'<div class="step-title">{esc(title)}</div>'
            f'<div class="step-meta">{esc(role)} · PDF {esc(page_range(start, end))} 页</div></div>{detail_html}</div>'
            '</div>'
        )
    return "".join(rows)


def render_formulas(formulas: list[dict[str, Any]], definitions: list[dict[str, Any]]) -> str:
    if not formulas:
        formula_html = ""
    else:
        cards = []
        for formula in formulas:
            label = str(formula.get("label") or "计算式")
            cards.append(
                '<article class="formula-card">'
                f'<div class="formula-head"><span>{esc(label)}</span><span>PDF {formula["page"]} 页</span></div>'
                f'<div class="formula">{esc(formula["plain"])}</div>'
                '<div class="verified-line">'
                f'{icon("shield")}<span>公式及上下标已按来源核对</span></div>'
                '</article>'
            )
        formula_html = "".join(cards)
    definition_html = ""
    if definitions:
        definition_html = '<h3>变量、系数与单位</h3><div class="definition-list">' + "".join(
            f'<div class="definition"><span class="page-chip">P.{row["page"]}</span><span>{esc(row["text"])}</span></div>'
            for row in definitions
        ) + '</div>'
    return formula_html + definition_html


def render_tables(tables: list[dict[str, Any]]) -> str:
    if not tables:
        return ""
    rendered = [
        '<section class="section page-break-before" id="tables">'
        '<aside class="section-rail"><span>04</span><b>DATA</b></aside><div class="section-content">'
        '<div class="section-kicker">DATA &amp; ACCEPTANCE</div><h2>' + icon("calc") + '数据表与结果判定</h2>'
    ]
    for table in tables:
        columns = table.get("columns") or []
        rows = table.get("rows") or []
        rendered.append(f'<div class="table-wrap"><div class="table-caption">PDF {table["page"]} 页 · 表 {table["index"]}</div><table><thead><tr>')
        rendered.extend(f"<th>{esc(value)}</th>" for value in columns)
        rendered.append("</tr></thead><tbody>")
        for row in rows:
            rendered.append("<tr>" + "".join(f"<td>{esc(value)}</td>" for value in row) + "</tr>")
        rendered.append("</tbody></table></div>")
    rendered.append("</div></section>")
    return "".join(rendered)


def render_source_pages(card: dict[str, Any], pages: list[dict[str, Any]]) -> str:
    values = [
        '<section class="section page-break-before appendix" id="appendix">'
        '<aside class="section-rail"><span>A</span><b>SOURCE</b></aside><div class="section-content">'
        '<div class="section-kicker">VERIFIED SOURCE</div>'
        f'<h2>{icon("source")}校正原文与页码对照</h2>'
        '<p class="lead">以下按 PDF 页码保留所选方法范围内的原文内容。公式、表格和已校正单位均按来源呈现。</p>'
    ]
    label = str(card.get("sourceLabel") or card.get("volumeLabel") or "本地校正来源")
    for page in pages:
        text = render_corrected_page(page).strip()
        values.append(
            '<article class="source-page">'
            f'<div class="source-page-head"><span>{esc(label)}</span><strong>PDF 第 {int(page["page"])} 页</strong></div>'
            f'<pre>{esc(text)}</pre></article>'
        )
    values.append("</div></section>")
    return "".join(values)


def build_html(card: dict[str, Any], pages: list[dict[str, Any]], query: str, include_source: bool) -> str:
    title = str(card.get("title") or "土壤试验方法")
    source_label = resolved_source_label(card, pages)
    full_source = full_source_citation(card, pages)
    start, end = int(card["startPage"]), int(card["endPage"])
    formulas = extract_formulas(pages)
    definitions = extract_verified_definitions(pages)
    tables = extract_tables(pages)
    components = card.get("components") or []
    roles = unique(ROLE_LABELS.get(str(value.get("role") or "section"), "方法条款") for value in components)
    official_url = str(card.get("officialDetailUrl") or "")
    digest = source_digest(card, pages)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    direct_match = methods.normalize(query) in methods.normalize(title) or methods.normalize(title) in methods.normalize(query)
    overview = method_overview(card, pages)
    reason = overview or (
        '查询对象与方法名称直接对应，因此优先展开此独立来源。'
        if direct_match
        else '此方法与查询条件最匹配；实施前仍应核对适用范围、样品状态和仪器条件。'
    )
    official_link = (
        f'<a class="source-link" href="{esc(official_url)}">查看官方条目 ↗</a>'
        if official_url
        else ""
    )
    tables_html = render_tables(tables)
    appendix_html = render_source_pages(card, pages) if include_source else ""
    appendix_nav = '<a href="#appendix">校正原文</a>' if include_source else ""
    css = r"""
      :root{--forest:#102f29;--deep:#0a211d;--paper:#f4f0e7;--white:#fffdf8;--ink:#152923;--muted:#6b756f;--sage:#9db6a8;--acid:#d9ec8b;--gold:#d7a753;--line:rgba(21,41,35,.18);--sans:"PingFang SC","Noto Sans CJK SC","Source Han Sans SC","Microsoft YaHei",sans-serif;--serif:"Songti SC","Noto Serif CJK SC","Source Han Serif SC","STSong",serif;--math:"STIX Two Math","Cambria Math","Times New Roman","PingFang SC",sans-serif}
      *{box-sizing:border-box}html{background:#d9ddd8;scroll-behavior:smooth}body{margin:0;color:var(--ink);font-family:var(--sans);font-size:15px;line-height:1.75;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;font-kerning:normal;font-variant-numeric:tabular-nums}.sheet{width:min(1180px,100%);margin:0 auto;background:var(--paper);overflow:hidden}.icon{width:20px;height:20px;flex:0 0 auto}
      .reader-nav{height:48px;padding:0 4vw;background:rgba(10,33,29,.96);display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.14);color:#fff;position:sticky;top:0;z-index:10;backdrop-filter:blur(12px)}.reader-nav strong{display:flex;align-items:center;gap:8px;font-size:11px;letter-spacing:.16em}.reader-nav strong .icon{width:15px;height:15px;color:var(--acid)}.reader-nav div{display:flex;gap:22px}.reader-nav a{font-size:10px;letter-spacing:.08em;color:#c8d5cf;text-decoration:none}.reader-nav a:hover{color:var(--acid)}
      .report-header{padding:54px 74px 50px;background:var(--white);border-bottom:1px solid var(--line)}.report-super{display:flex;justify-content:space-between;gap:24px;padding-bottom:14px;border-bottom:2px solid var(--ink);font-size:9px;letter-spacing:.18em;color:#477066}.report-super strong{display:flex;align-items:center;gap:8px}.report-super .icon{width:16px;height:16px}.title-lockup{display:grid;grid-template-columns:54px minmax(0,1fr);gap:22px;align-items:start;margin-top:32px}.title-icon{width:54px;height:54px;color:#477066;border-top:2px solid #477066;padding-top:10px}.title-icon .icon{width:34px;height:34px}.report-header h1{font-family:var(--serif);font-size:clamp(38px,5vw,58px);line-height:1.14;letter-spacing:-.04em;margin:0;max-width:900px}.report-question{display:grid;grid-template-columns:140px minmax(0,1fr);gap:20px;margin-top:30px;padding:15px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.report-question span,.report-source span{font-size:9px;letter-spacing:.12em;color:var(--muted)}.report-question strong{font-size:15px}.report-source{display:grid;grid-template-columns:140px minmax(0,1fr);gap:20px;padding:15px 0;border-bottom:1px solid var(--line)}.report-source strong{font-size:12px;overflow-wrap:anywhere}
      .page{padding:42px 56px}.cover{min-height:calc(100vh - 48px);position:relative;background:var(--forest);color:#f8f4e9;display:grid;grid-template-rows:auto 1fr auto;overflow:hidden}.cover:before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent 49.88%,rgba(255,255,255,.07) 50%,transparent 50.12%),linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px);background-size:100% 100%,100% 72px;pointer-events:none}.cover:after{content:"";position:absolute;right:-150px;top:40px;width:520px;height:520px;border:1px solid rgba(217,236,139,.42);border-radius:50%;box-shadow:0 0 0 56px rgba(217,236,139,.025),0 0 0 112px rgba(217,236,139,.018)}.cover-head,.cover-grid,.cover-foot{position:relative;z-index:1}.cover-head{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(255,255,255,.24);padding-bottom:20px}.brand{display:flex;align-items:center;gap:12px;font-size:11px;font-weight:750;letter-spacing:.18em}.brand-mark{width:32px;height:32px;border:1px solid var(--acid);color:var(--acid);display:grid;place-items:center}.brand-mark .icon{width:17px}.edition{font-size:10px;color:#b7c8c1;letter-spacing:.18em}.cover-grid{display:grid;grid-template-columns:105px minmax(0,1fr) 225px;gap:36px;align-items:center;padding:50px 0}.cover-index{font-family:var(--serif);font-size:92px;line-height:1;color:rgba(217,236,139,.28);align-self:start}.eyebrow{color:var(--acid);font-size:10px;font-weight:800;letter-spacing:.25em;margin-bottom:22px}.cover h1{font-family:var(--serif);font-size:clamp(46px,6.1vw,76px);font-weight:700;line-height:1.08;letter-spacing:-.045em;margin:0 0 24px;max-width:720px}.cover-subtitle{font-family:var(--serif);font-size:18px;line-height:1.7;color:#cbd7d1;max-width:650px}.query{margin-top:36px;padding-top:18px;border-top:1px solid rgba(217,236,139,.55);max-width:650px}.query-label{font-size:9px;letter-spacing:.2em;color:var(--acid);font-weight:800}.query-value{font-size:16px;font-weight:650;margin-top:5px}.cover-aside{align-self:stretch;border-left:1px solid rgba(255,255,255,.2);padding-left:24px;display:flex;flex-direction:column;justify-content:center;gap:25px}.aside-item span{display:block;color:#9fb2aa;font-size:9px;letter-spacing:.14em;margin-bottom:5px}.aside-item strong{display:block;font-size:13px;line-height:1.55}.cover-foot{display:grid;grid-template-columns:repeat(3,100px) 1fr;gap:24px;align-items:end;border-top:1px solid rgba(255,255,255,.24);padding-top:20px}.trust strong{display:block;color:var(--acid);font-size:25px;line-height:1}.trust span{display:block;color:#a8bbb3;font-size:9px;margin-top:7px}.source-strip{padding-left:24px;border-left:1px solid rgba(255,255,255,.2);display:flex;justify-content:space-between;gap:24px}.source-strip small{display:block;color:#9fb2aa;font-size:9px;letter-spacing:.12em}.source-strip strong{display:block;font-size:12px;margin-top:4px}.meta{font-size:9px;color:#9fb2aa;text-align:right;white-space:nowrap}
      .section{display:grid;grid-template-columns:100px minmax(0,1fr);grid-template-areas:"rail content";gap:40px;padding:96px 74px;background:var(--paper);page-break-inside:auto}.section+.section{border-top:1px solid var(--line)}.section-rail{grid-area:rail;padding-top:3px;display:flex;flex-direction:column;align-items:flex-start}.section-rail span{font-family:var(--serif);font-size:47px;line-height:1;color:var(--gold)}.section-rail b{font-size:8px;letter-spacing:.22em;color:var(--muted);writing-mode:vertical-rl;margin:15px 0 0 16px}.section-content{grid-area:content;width:100%;min-width:0;max-width:100%}.section-kicker{font-size:9px;font-weight:800;letter-spacing:.24em;color:#477066;margin-bottom:12px}.section h2{display:flex;align-items:center;gap:13px;font-family:var(--serif);font-size:36px;font-weight:700;line-height:1.22;margin:0 0 18px;letter-spacing:-.025em}.section h2 .icon{width:27px;height:27px;color:#477066}.section h3{font-family:var(--serif);font-size:20px;font-weight:700;margin:30px 0 12px}.lead{font-family:var(--sans);font-weight:400;color:#465b54;font-size:16px;line-height:1.85;max-width:760px;margin:0 0 34px}.decision-grid{display:grid;grid-template-columns:1.25fr .75fr;border-top:2px solid var(--ink);border-bottom:1px solid var(--line)}.decision-card{padding:26px 30px 28px 0}.decision-card+.decision-card{border-left:1px solid var(--line);padding-left:30px}.decision-label{display:flex;align-items:center;gap:8px;font-size:9px;font-weight:800;letter-spacing:.16em;color:#477066}.decision-label .icon{width:16px;height:16px}.decision-card h3{margin:14px 0 10px}.decision-card p{margin:0;color:#364b44}.role-chips{display:flex;flex-wrap:wrap;margin-top:20px}.chip{font-size:10px;color:#477066;font-weight:700}.chip:not(:last-child):after{content:" / ";color:#a1aaa5;margin:0 7px}.notice{margin-top:28px;border-top:1px solid var(--gold);border-bottom:1px solid var(--gold);padding:18px 0;display:grid;grid-template-columns:25px 1fr;gap:12px;color:#6e531e}.notice .icon{color:var(--gold)}
      .steps{border-top:2px solid var(--ink);margin-top:8px}.step{display:grid;grid-template-columns:92px minmax(0,1fr);border-bottom:1px solid var(--line);padding:18px 0;position:relative}.step-no{font-family:"SF Mono","Menlo",monospace;color:#477066;font-size:12px;font-weight:800;letter-spacing:.04em}.step-heading{display:grid;grid-template-columns:minmax(0,1fr) 110px;gap:20px;align-items:baseline}.step-title{font-family:var(--serif);font-weight:700;font-size:17px}.step-meta{font-size:9px;color:var(--muted);text-align:right}.step-detail{margin-top:16px;border-top:1px solid rgba(21,41,35,.1)}.step-detail p{display:grid;grid-template-columns:42px minmax(0,1fr) 36px;gap:10px;margin:0;padding:11px 0;border-bottom:1px solid rgba(21,41,35,.08);font-family:var(--sans);font-size:12px;font-weight:400;line-height:1.75}.step-detail p:last-child{border-bottom:0}.step-detail p>b{grid-column:1;color:#477066;font-weight:600}.step-detail p>span{grid-column:2;display:block;min-width:0;word-break:normal;overflow-wrap:break-word}.step-detail p>small{grid-column:3;font-family:var(--sans);font-size:8px;color:var(--muted);text-align:right}.level-2{padding-left:28px}.level-3,.level-4{padding-left:58px}.level-2 .step-title{font-size:15px}.level-3 .step-title,.level-4 .step-title{font-family:var(--sans);font-size:13px;font-weight:600}
      #calculation{background:var(--deep);color:#f7f3e8}#calculation .section-rail span{color:var(--acid)}#calculation .section-rail b,#calculation .lead{color:#9fb2aa}#calculation .section-kicker,#calculation h2 .icon{color:var(--acid)}.formula-card{width:100%;min-width:0;padding:26px 0 30px;border-top:1px solid rgba(255,255,255,.22);page-break-inside:avoid}.formula-head{display:flex;justify-content:space-between;color:var(--acid);font-size:9px;font-weight:800;letter-spacing:.13em}.formula{font-family:var(--math);font-size:clamp(21px,3vw,34px);font-weight:400;line-height:1.55;color:#fff;margin:24px 0;overflow-wrap:anywhere}.verified-line{display:flex;align-items:center;gap:8px;color:#9fb2aa;font-size:9px}.verified-line .icon{width:15px;height:15px;color:var(--acid)}#calculation h3{color:#fff}.definition-list{width:100%;min-width:0;border-top:1px solid rgba(255,255,255,.2)}.definition{display:grid;grid-template-columns:66px minmax(0,1fr);gap:18px;width:100%;min-width:0;padding:14px 0;border-bottom:1px solid rgba(255,255,255,.13);font-family:var(--math);font-size:12px;color:#d8e0dc;page-break-inside:avoid}.definition>span:last-child{display:block;min-width:0;word-break:normal;overflow-wrap:break-word}.page-chip{color:var(--acid);font-family:"SF Mono","Menlo",monospace}.empty{padding:24px 0;border-top:1px solid rgba(255,255,255,.25);color:#9fb2aa}
      .table-wrap{margin:18px 0 38px;overflow:auto;border-top:2px solid var(--ink);page-break-inside:auto}.table-caption{padding:10px 0;color:#477066;font-weight:800;font-size:9px;letter-spacing:.1em}table{border-collapse:collapse;width:100%;font-size:10px}thead{display:table-header-group}th{font-weight:800;text-align:left;border-top:1px solid var(--ink)}th,td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}tr{page-break-inside:avoid}
      .source-link{display:inline-flex;margin-top:18px;color:#315f53;font-weight:800;text-decoration:none;border-bottom:1px solid #315f53}.appendix{background:var(--white)}.appendix .section-rail{display:none}.appendix .section-content{grid-column:1/-1;grid-area:auto;width:100%;min-width:0;max-width:none}.appendix .lead{max-width:800px}.source-page{display:block;width:100%;min-width:0;max-width:100%;margin:32px 0 54px;page-break-before:auto}.source-page-head{display:flex;justify-content:space-between;gap:20px;padding:0 0 10px;border-bottom:2px solid var(--ink);font-size:9px;letter-spacing:.08em;color:#477066}pre{display:block;width:100%;min-width:0;max-width:100%;white-space:pre-wrap;word-break:normal;overflow-wrap:break-word;margin:0;padding:22px 0;font-family:var(--serif);font-size:11px;line-height:1.85;color:#263d35;background:transparent}.muted{color:var(--muted)}.page-break-before{page-break-before:always}
      @page{size:A4;margin:0}@media print{html,body{background:#fff}.reader-nav{display:none}.sheet{width:210mm;margin:0}.report-header{padding:16mm}.report-header h1{font-size:32px}.section{grid-template-columns:22mm 1fr;gap:9mm;padding:18mm 16mm}.section h2{font-size:26px}.page-break-before{break-before:page}.source-page{break-inside:auto}.formula-card,.prov-card,.trust{break-inside:avoid}}
      @media(max-width:900px){.reader-nav div{display:none}.report-header{padding:42px 24px}.report-header h1{font-size:36px}.report-question,.report-source{grid-template-columns:1fr;gap:4px}.section{grid-template-columns:minmax(0,1fr);grid-template-areas:"content";padding:62px 24px;gap:24px}.section-rail{display:none}.section-content{grid-column:1;grid-area:content}.section h2{font-size:30px}.decision-grid{grid-template-columns:1fr}.decision-card+.decision-card{border-left:0;border-top:1px solid var(--line);padding-left:0}.step{grid-template-columns:60px minmax(0,1fr)}.step-heading{grid-template-columns:minmax(0,1fr)}.step-meta{text-align:left}.step-detail p{grid-template-columns:34px minmax(0,1fr)}.step-detail small{display:none}.level-2{padding-left:14px}.level-3,.level-4{padding-left:28px}.formula{font-size:22px}.definition{grid-template-columns:56px minmax(0,1fr);gap:12px}.appendix .section-content{grid-column:1;grid-area:content}}
    """
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} - 试验方法报告</title><style>{css}</style></head>
<body><main class="sheet">
  <nav class="reader-nav"><strong>{icon("flask")} HEMUSCI / METHOD DOSSIER</strong><div><a href="#decision">适用性</a><a href="#workflow">操作规程</a><a href="#calculation">结果计算</a>{appendix_nav}</div></nav>
  <header class="report-header"><div class="report-super"><strong>{icon("shield")} VERIFIED SOIL METHOD</strong><span>{esc(generated)}</span></div><div class="title-lockup"><span class="title-icon">{icon("flask")}</span><div><h1>{esc(title)}</h1></div></div><div class="report-question"><span>CONSULTATION</span><strong>{esc(query)}</strong></div><div class="report-source"><span>完整出处</span><strong>{esc(full_source)}</strong></div>{official_link}</header>
  <section class="section page-break-before" id="decision"><aside class="section-rail"><span>01</span><b>DECISION</b></aside><div class="section-content"><div class="section-kicker">METHOD SELECTION</div><h2>{icon("target")}方法适用性与选择依据</h2>
    <p class="lead">方法选择以测量对象、样品状态、仪器条件和结果口径为依据。确认适用条件后，再进入实验操作。</p>
    <div class="decision-grid"><article class="decision-card primary"><div class="decision-label">{icon("why")}METHOD SELECTION</div><h3>{esc(title)}</h3><p>{esc(reason)}</p><div class="role-chips">{''.join(f'<span class="chip">{esc(role)}</span>' for role in roles[:10])}</div></article><article class="decision-card"><div class="decision-label">{icon("shield")}PARAMETER SOURCE</div><h3>参数来自同一方法</h3><p>本方案的试剂、操作条件、公式和质控限均来自同一方法，不混用其他书籍或标准的参数。</p></article></div>
    <div class="notice">{icon("why")}<div><strong>实施前必查：</strong>样品是鲜样还是风干样；待测组分是总量、有效态还是可提取态；实验室仪器是否与来源条款一致。</div></div></div>
  </section>
  <section class="section page-break-before" id="workflow"><aside class="section-rail"><span>02</span><b>PROTOCOL</b></aside><div class="section-content"><div class="section-kicker">STANDARD OPERATING PROCEDURE</div><h2>{icon("steps")}标准操作规程</h2><div class="steps">{render_components(card, pages)}</div></div></section>
  <section class="section page-break-before" id="calculation"><aside class="section-rail"><span>03</span><b>CALCULATION</b></aside><div class="section-content"><div class="section-kicker">EQUATIONS &amp; UNITS</div><h2>{icon("calc")}结果计算、单位与判定</h2><p class="lead">公式保留核对后的原始字符；变量、系数和单位只在来源明确说明时列出。</p>{render_formulas(formulas,definitions)}</div></section>
  {tables_html}
  {appendix_html}
</main></body></html>"""


def register_pdf_fonts() -> None:
    songti = "/System/Library/Fonts/Supplemental/Songti.ttc"
    stheiti = "/System/Library/AssetsV2/com_apple_MobileAsset_Font8/53fe5be564086fefc7523ccd0a31200acf92e0e5.asset/AssetData/STHEITI.ttf"
    candidates = {
        FONT_REGULAR: [
            (stheiti, 0),
            ("/System/Library/Fonts/STHeiti Light.ttc", 1),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),
        ],
        FONT_BOLD: [
            ("/System/Library/Fonts/STHeiti Medium.ttc", 1),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2),
        ],
        FONT_SERIF: [
            (songti, 6),
            ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 2),
        ],
        FONT_SERIF_BOLD: [
            (songti, 1),
            ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc", 2),
        ],
        FONT_FORMULA: [
            ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 2),
        ],
    }
    for name, specs in candidates.items():
        if name in pdfmetrics.getRegisteredFontNames():
            continue
        spec = next(((Path(value), index) for value, index in specs if Path(value).is_file()), None)
        if spec is None:
            raise FileNotFoundError(f"缺少用于精确显示中文和上下标的字体: {name}")
        path, index = spec
        pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=index))


def pdf_icon(kind: str, size: float = 22, color: colors.Color | None = None) -> Drawing:
    color = color or colors.HexColor("#0e684f")
    drawing = Drawing(size, size)
    scale = size / 24

    def line(x1: float, y1: float, x2: float, y2: float, width: float = 1.6) -> None:
        drawing.add(Line(x1 * scale, y1 * scale, x2 * scale, y2 * scale, strokeColor=color, strokeWidth=width * scale))

    if kind == "steps":
        for y in (6, 12, 18):
            drawing.add(Circle(4 * scale, y * scale, 1.25 * scale, fillColor=color, strokeColor=None))
            line(8, y, 20, y)
    elif kind == "calc":
        drawing.add(Rect(4 * scale, 3 * scale, 16 * scale, 18 * scale, rx=2 * scale, ry=2 * scale, fillColor=None, strokeColor=color, strokeWidth=1.6 * scale))
        line(8, 8, 16, 8)
        for y in (13, 17):
            line(8, y, 10, y)
            line(14, y, 16, y)
    elif kind == "source":
        drawing.add(Rect(5 * scale, 3 * scale, 14 * scale, 18 * scale, fillColor=None, strokeColor=color, strokeWidth=1.6 * scale))
        line(9, 9, 16, 9)
        line(9, 13, 16, 13)
        line(9, 17, 15, 17)
    elif kind == "shield":
        path = ShapePath()
        path.moveTo(12 * scale, 2 * scale)
        path.lineTo(19 * scale, 6 * scale)
        path.lineTo(18 * scale, 14 * scale)
        path.curveTo(17 * scale, 18 * scale, 14 * scale, 20 * scale, 12 * scale, 22 * scale)
        path.curveTo(10 * scale, 20 * scale, 7 * scale, 18 * scale, 6 * scale, 14 * scale)
        path.lineTo(5 * scale, 6 * scale)
        path.closePath()
        path.fillColor = None
        path.strokeColor = color
        path.strokeWidth = 1.6 * scale
        drawing.add(path)
        line(9, 12, 11, 14)
        line(11, 14, 15.5, 9)
    elif kind == "flask":
        path = ShapePath()
        path.moveTo(9 * scale, 3 * scale)
        path.lineTo(15 * scale, 3 * scale)
        path.moveTo(10 * scale, 3 * scale)
        path.lineTo(10 * scale, 9 * scale)
        path.lineTo(5 * scale, 18 * scale)
        path.curveTo(4 * scale, 20 * scale, 6 * scale, 22 * scale, 8 * scale, 22 * scale)
        path.lineTo(16 * scale, 22 * scale)
        path.curveTo(18 * scale, 22 * scale, 20 * scale, 20 * scale, 19 * scale, 18 * scale)
        path.lineTo(14 * scale, 9 * scale)
        path.lineTo(14 * scale, 3 * scale)
        path.fillColor = None
        path.strokeColor = color
        path.strokeWidth = 1.6 * scale
        drawing.add(path)
        line(7.5, 16, 16.5, 16)
    else:
        drawing.add(Circle(12 * scale, 12 * scale, 8 * scale, fillColor=None, strokeColor=color, strokeWidth=1.6 * scale))
        drawing.add(Circle(12 * scale, 12 * scale, 3 * scale, fillColor=None, strokeColor=color, strokeWidth=1.6 * scale))
    return drawing


def pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_eyebrow": ParagraphStyle("cover_eyebrow", parent=base["Normal"], fontName=FONT_BOLD, fontSize=8, leading=11, textColor=colors.HexColor("#d9ec8b"), spaceAfter=8),
        "cover_title": ParagraphStyle("cover_title", parent=base["Title"], fontName=FONT_SERIF_BOLD, fontSize=31, leading=38, textColor=colors.HexColor("#fffdf8"), spaceAfter=13),
        "cover_subtitle": ParagraphStyle("cover_subtitle", parent=base["Normal"], fontName=FONT_SERIF, fontSize=11.5, leading=19, textColor=colors.HexColor("#cbd7d1")),
        "question_label": ParagraphStyle("question_label", parent=base["Normal"], fontName=FONT_BOLD, fontSize=7, leading=10, textColor=colors.HexColor("#d9ec8b")),
        "question": ParagraphStyle("question", parent=base["Normal"], fontName=FONT_BOLD, fontSize=12, leading=18, textColor=colors.HexColor("#fffdf8")),
        "cover_stat": ParagraphStyle("cover_stat", parent=base["Normal"], fontName=FONT_BOLD, fontSize=18, leading=21, textColor=colors.HexColor("#d9ec8b")),
        "cover_stat_label": ParagraphStyle("cover_stat_label", parent=base["Normal"], fontName=FONT_REGULAR, fontSize=6.8, leading=10, textColor=colors.HexColor("#a8bbb3")),
        "report_title": ParagraphStyle("report_title", parent=base["Title"], fontName=FONT_SERIF_BOLD, fontSize=25, leading=32, textColor=colors.HexColor("#17332c"), spaceAfter=9),
        "report_deck": ParagraphStyle("report_deck", parent=base["Normal"], fontName=FONT_SERIF, fontSize=10, leading=16, textColor=colors.HexColor("#51635d")),
        "source_white": ParagraphStyle("source_white", parent=base["Normal"], fontName=FONT_BOLD, fontSize=9, leading=14, textColor=colors.white),
        "source_meta": ParagraphStyle("source_meta", parent=base["Normal"], fontName=FONT_REGULAR, fontSize=7, leading=10, textColor=colors.HexColor("#d5e2dd"), alignment=TA_LEFT),
        "kicker": ParagraphStyle("kicker", parent=base["Normal"], fontName=FONT_BOLD, fontSize=7, leading=9, textColor=colors.HexColor("#0e684f"), spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=FONT_BOLD, fontSize=18, leading=23, textColor=colors.HexColor("#17332c"), spaceAfter=7),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName=FONT_BOLD, fontSize=12, leading=17, textColor=colors.HexColor("#17332c"), spaceBefore=10, spaceAfter=5),
        "lead": ParagraphStyle("lead", parent=base["Normal"], fontName=FONT_REGULAR, fontSize=10, leading=16, textColor=colors.HexColor("#425a52"), spaceAfter=12),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName=FONT_REGULAR, fontSize=9, leading=14, textColor=colors.HexColor("#17332c")),
        "body_exact": ParagraphStyle("body_exact", parent=base["Normal"], fontName=FONT_FORMULA, fontSize=8.5, leading=14, textColor=colors.HexColor("#17332c"), wordWrap="CJK"),
        "body_white": ParagraphStyle("body_white", parent=base["Normal"], fontName=FONT_REGULAR, fontSize=9, leading=14, textColor=colors.white),
        "small": ParagraphStyle("small", parent=base["Normal"], fontName=FONT_REGULAR, fontSize=7.5, leading=11, textColor=colors.HexColor("#62726c")),
        "small_green": ParagraphStyle("small_green", parent=base["Normal"], fontName=FONT_BOLD, fontSize=7.5, leading=11, textColor=colors.HexColor("#0e684f")),
        "formula": ParagraphStyle("formula", parent=base["Normal"], fontName=FONT_FORMULA, fontSize=15, leading=22, textColor=colors.HexColor("#17332c"), alignment=TA_CENTER, wordWrap="CJK"),
        "formula_small": ParagraphStyle("formula_small", parent=base["Normal"], fontName=FONT_FORMULA, fontSize=7.5, leading=11.5, textColor=colors.HexColor("#53665f"), wordWrap="CJK"),
        "source": ParagraphStyle("source", parent=base["Normal"], fontName=FONT_FORMULA, fontSize=7.2, leading=11.2, textColor=colors.HexColor("#263d35"), wordWrap="CJK"),
        "table_head": ParagraphStyle("table_head", parent=base["Normal"], fontName=FONT_BOLD, fontSize=6.8, leading=9, textColor=colors.HexColor("#17332c")),
        "table_cell": ParagraphStyle("table_cell", parent=base["Normal"], fontName=FONT_REGULAR, fontSize=6.5, leading=9, textColor=colors.HexColor("#263d35"), wordWrap="CJK"),
    }


def pdf_section_heading(kind: str, kicker: str, title: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    return [
        Paragraph(esc(kicker), styles["kicker"]),
        Table(
            [[pdf_icon(kind, 21), Paragraph(esc(title), styles["h2"])]],
            colWidths=[9 * mm, 165 * mm],
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]),
        ),
    ]


def pdf_footer(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d8ded8"))
    canvas.setLineWidth(0.35)
    canvas.line(18 * mm, 12 * mm, 192 * mm, 12 * mm)
    canvas.setFont(FONT_REGULAR, 7)
    canvas.setFillColor(colors.HexColor("#66736e"))
    canvas.drawString(18 * mm, 7.5 * mm, "土壤试验方法顾问")
    canvas.drawRightString(192 * mm, 7.5 * mm, f"{doc.page}")
    canvas.restoreState()


def pdf_cover(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#102f29"))
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setStrokeColor(colors.Color(0.85, 0.93, 0.55, alpha=.42))
    canvas.setLineWidth(.6)
    for radius in (37 * mm, 52 * mm, 67 * mm):
        canvas.circle(A4[0] - 12 * mm, A4[1] - 24 * mm, radius, fill=0, stroke=1)
    canvas.setStrokeColor(colors.Color(1, 1, 1, alpha=.07))
    for y in range(30, 820, 51):
        canvas.line(0, y, A4[0], y)
    canvas.restoreState()


def render_pdf_report(card: dict[str, Any], pages: list[dict[str, Any]], query: str, pdf_path: Path, include_source: bool) -> None:
    if REPORTLAB_IMPORT_ERROR is not None:
        raise RuntimeError(f"缺少 {REPORTLAB_IMPORT_ERROR.name}，无法生成 PDF")
    register_pdf_fonts()
    styles = pdf_styles()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    title = str(card.get("title") or "土壤试验方法")
    source_label = resolved_source_label(card, pages)
    full_source = full_source_citation(card, pages)
    start, end = int(card["startPage"]), int(card["endPage"])
    formulas = extract_formulas(pages)
    definitions = extract_verified_definitions(pages)
    tables = extract_tables(pages)
    components = card.get("components") or []
    direct_match = methods.normalize(query) in methods.normalize(title) or methods.normalize(title) in methods.normalize(query)
    overview = method_overview(card, pages)
    reason = overview or (
        "查询对象与方法名称直接对应，因此优先展开此独立来源。"
        if direct_match
        else "此方法与查询条件最匹配；实施前仍应核对适用范围、样品状态和仪器条件。"
    )
    digest = source_digest(card, pages)
    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=17 * mm,
        title=f"{title} - 试验方法报告", author="soil-methods-consultant",
    )
    story: list[Any] = []
    masthead = Table(
        [[pdf_icon("flask", 18, colors.HexColor("#0e684f")), Paragraph("HEMUSCI / VERIFIED SOIL METHOD", styles["small_green"]), Paragraph(datetime.now().strftime("%Y-%m-%d %H:%M"), styles["small"])]],
        colWidths=[9 * mm, 125 * mm, 40 * mm],
        style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1.0, colors.HexColor("#17332c")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]),
    )
    story.extend([masthead, Spacer(1, 9 * mm), Paragraph(esc(title), styles["report_title"]), Spacer(1, 6 * mm)])
    header_ledger = Table(
        [
            [Paragraph("咨询问题", styles["small"]), Paragraph(esc(query), styles["body"])],
            [Paragraph("完整出处", styles["small"]), Paragraph(esc(full_source), styles["body_exact"])],
        ],
        colWidths=[38 * mm, 136 * mm],
        style=TableStyle([("LINEABOVE", (0, 0), (-1, 0), .5, colors.HexColor("#d8ded8")), ("LINEBELOW", (0, 0), (-1, -1), .35, colors.HexColor("#d8ded8")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]),
    )
    story.extend([header_ledger, Spacer(1, 11 * mm)])

    story.extend(pdf_section_heading("target", "METHOD SELECTION", "方法适用性与选择依据", styles))
    story.append(Paragraph("先确认测定对象与方法适用范围，再根据样品状态、仪器和结果口径决定是否实施。", styles["lead"]))
    decision = Table(
        [[Paragraph(f"<b>方法选择依据</b><br/>{esc(reason)}", styles["body_exact"]), Paragraph("<b>参数来源</b><br/>本方案的试剂、条件、公式和质控限均来自同一方法，不混用其他来源的参数。", styles["body"])]],
        colWidths=[105 * mm, 69 * mm],
        style=TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.2, colors.HexColor("#17332c")), ("LINEBELOW", (0, 0), (-1, 0), .5, colors.HexColor("#d8ded8")), ("LINEBEFORE", (1, 0), (1, 0), .5, colors.HexColor("#d8ded8")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, 0), 0), ("LEFTPADDING", (1, 0), (1, 0), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]),
    )
    story.extend([decision, Spacer(1, 5 * mm), Table([[pdf_icon("shield", 18, colors.HexColor("#8a5b0a")), Paragraph("<b>实施前必查：</b>样品是鲜样还是风干样、待测组分是总量还是有效/可提取态、仪器是否与来源条款一致。", styles["body"])]], colWidths=[9 * mm, 165 * mm], style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff0cf")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)])), Spacer(1, 10 * mm)])

    story.extend(pdf_section_heading("steps", "STANDARD OPERATING PROCEDURE", "标准操作规程", styles))
    detail_map = component_details(card, pages)
    if detail_map:
        detail_components = list(components)
        if len(detail_components) > 18:
            detail_components = [
                value
                for index, value in enumerate(detail_components, 1)
                if detail_map.get(heading_number(value, index))
            ]
        for index, component in enumerate(detail_components, 1):
            number = heading_number(component, index)
            rows = detail_map.get(number) or []
            if not rows:
                continue
            role = ROLE_LABELS.get(str(component.get("role") or "section"), "方法条款")
            story.append(Paragraph(f"{esc(str(component.get('title') or number))} <font color='#62726c'>· {esc(role)}</font>", styles["h3"]))
            detail_data = [
                [
                    Paragraph(esc(row["number"]), styles["small_green"]),
                    Paragraph(esc(row["text"]), styles["body_exact"]),
                    Paragraph(f"P.{row['page']}", styles["small"]),
                ]
                for row in rows
            ]
            detail_table = Table(detail_data, colWidths=[16 * mm, 142 * mm, 16 * mm], splitByRow=True)
            detail_table.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), .45, colors.HexColor("#d8ded8")), ("LINEBELOW", (0, 0), (-1, -1), .3, colors.HexColor("#e2e6e2")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
            story.extend([detail_table, Spacer(1, 4 * mm)])
    story.append(Spacer(1, 6 * mm))

    story.extend(pdf_section_heading("calc", "RESULT CALCULATION", "结果计算、单位与判定", styles))
    story.append(Paragraph("公式保留核对后的原始字符，并就近列出已校正的变量、系数和单位。", styles["lead"]))
    if formulas:
        for formula in formulas:
            formula_box = Table(
                [[Paragraph(f"<b>{esc(formula.get('label') or '计算式')}</b> · PDF {formula['page']} 页", styles["small_green"])], [Paragraph(esc(formula["plain"]), styles["formula"])], [Paragraph("公式及上下标已按来源核对", styles["small"])]],
                colWidths=[174 * mm],
                style=TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.0, colors.HexColor("#17332c")), ("LINEBELOW", (0, 2), (-1, 2), .5, colors.HexColor("#d8ded8")), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]),
            )
            story.extend([KeepTogether([formula_box]), Spacer(1, 3 * mm)])
    if definitions:
        story.append(Paragraph("变量、系数与单位", styles["h3"]))
        def_rows = [[Paragraph(f"P.{row['page']}", styles["small_green"]), Paragraph(esc(row["text"]), styles["formula_small"])] for row in definitions]
        definition_table = Table(def_rows, colWidths=[17 * mm, 157 * mm], splitByRow=True)
        definition_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6f7f4")), ("BOX", (0, 0), (-1, -1), .4, colors.HexColor("#e4e8e3")), ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#e4e8e3")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        story.append(definition_table)

    if tables:
        story.append(PageBreak())
        story.extend(pdf_section_heading("calc", "DATA & ACCEPTANCE", "数据表与结果判定", styles))
        for table in tables:
            story.append(Paragraph(f"PDF {table['page']} 页 · 表 {table['index']}", styles["small_green"]))
            columns = list(table.get("columns") or [])
            rows = list(table.get("rows") or [])
            data = [[Paragraph(esc(value), styles["table_head"]) for value in columns]] + [[Paragraph(esc(value), styles["table_cell"]) for value in row] for row in rows]
            width = 174 * mm / max(1, len(columns))
            table_flow = Table(data, colWidths=[width] * max(1, len(columns)), repeatRows=1, splitByRow=True)
            table_flow.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf3ee")), ("BOX", (0, 0), (-1, -1), .45, colors.HexColor("#d8ded8")), ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#e2e6e2")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
            story.extend([table_flow, Spacer(1, 5 * mm)])

    if include_source:
        story.append(PageBreak())
        story.extend(pdf_section_heading("source", "VERIFIED SOURCE", "校正原文与页码对照", styles))
        story.append(Paragraph("以下按 PDF 页码保留所选方法范围内的原文内容。公式、表格和已校正单位均按来源呈现。", styles["lead"]))
        for index, page in enumerate(pages):
            if index:
                story.append(PageBreak())
            story.append(Paragraph(f"{esc(source_label)} · PDF 第 {int(page['page'])} 页", styles["h3"]))
            raw = render_corrected_page(page).strip()
            if raw:
                story.append(Paragraph(esc(raw).replace("\n", "<br/>"), styles["source"]))
            else:
                story.append(
                    Table(
                        [[pdf_icon("source", 18), Paragraph("本页没有可用正文；仍保留页码，以便与来源文件对应。", styles["body"])]],
                        colWidths=[9 * mm, 165 * mm],
                        style=TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef5f1")), ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#d8ded8")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]),
                    )
                )

    doc.build(story, onFirstPage=pdf_footer, onLaterPages=pdf_footer)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成精美的土壤试验方法 HTML/PDF 报告")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--card-id", help="consult 返回的方法记录 ID")
    selection.add_argument("--query", help="自动选择本地检索排名第一的方法记录")
    parser.add_argument("--question", help="封面显示的原始问题；默认与 --query 相同")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--name", help="输出文件的稳定名称（不含扩展名）")
    parser.add_argument("--no-pdf", action="store_true", help="只生成 HTML")
    parser.add_argument("--include-source-pages", action="store_true", help="在报告末尾附校正原文和页码（仅在明确要求时使用）")
    args = parser.parse_args()

    card_id = args.card_id or find_card_for_query(str(args.query))
    card, pages = load_card(card_id)
    question = str(args.question or args.query or card.get("title") or card_id)
    name = stable_slug(str(args.name or f"soil-method-{card_id}"))
    html_path = args.output_root / "html" / f"{name}.html"
    pdf_path = args.output_root / "pdf" / f"{name}.pdf"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_text = build_html(card, pages, question, args.include_source_pages)
    html_path.write_text(html_text, encoding="utf-8")
    result: dict[str, Any] = {
        "cardId": card_id,
        "html": str(html_path.resolve()),
        "pdf": None,
        "sourcePageCount": len(pages),
        "formulaCount": len(extract_formulas(pages)),
    }
    if not args.no_pdf:
        render_pdf_report(card, pages, question, pdf_path.resolve(), args.include_source_pages)
        result["pdf"] = str(pdf_path.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if REPORTLAB_IMPORT_ERROR is not None:
        reexec_with_bundled_runtime()
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"错误: {error}", file=sys.stderr)
        raise SystemExit(2)

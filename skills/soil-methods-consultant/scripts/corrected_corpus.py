#!/usr/bin/env python3
"""Load and render the verified, corrected page corpus used at runtime."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Iterator


SKILL_ROOT = Path(__file__).resolve().parents[1]
CORRECTED_DIR = SKILL_ROOT / "references" / "corrected-pages"

_NON_CONTENT_KEYS = {
    "type",
    "level",
    "continuation",
    "continued",
    "continuedFromPreviousPage",
    "inlineNotation",
    "confidence",
    "alternatives",
}


def corrected_page_path(volume: int, page: int) -> Path:
    base = CORRECTED_DIR / f"volume-{volume}" / f"page-{page:04d}.json"
    if base.is_file():
        return base
    compressed = base.with_suffix(".json.gz")
    if compressed.is_file():
        return compressed
    raise FileNotFoundError(f"缺少最终校正页: volume-{volume} PDF 第 {page} 页")


def load_corrected_page(volume: int, page: int) -> dict[str, Any]:
    path = corrected_page_path(volume, page)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def _content_scalars(value: Any, key: str = "") -> Iterator[str]:
    """Yield searchable/displayable values without losing Unicode notation."""
    if value is None or key in _NON_CONTENT_KEYS:
        return
    if isinstance(value, bool):
        return
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        if text:
            yield text
        return
    if isinstance(value, list):
        for item in value:
            yield from _content_scalars(item)
        return
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            yield from _content_scalars(child_value, child_key)


def _render_block(block: dict[str, Any]) -> str:
    parts: list[str] = []
    number = str(block.get("number") or "").strip()
    title = str(block.get("title") or "").strip()
    text = str(block.get("text") or "").strip()
    if number or title:
        parts.append(" ".join(item for item in (number, title) if item))
    if text and text not in parts:
        parts.append(text)

    excluded = {
        "type",
        "level",
        "number",
        "title",
        "text",
        "continuation",
        "continued",
        "continuedFromPreviousPage",
        "inlineNotation",
        "confidence",
        "alternatives",
        "box",
        "engine",
    }
    for key, value in block.items():
        if key in excluded:
            continue
        values = list(_content_scalars(value, key))
        if values:
            parts.append(" | ".join(values))
    return "\n".join(dict.fromkeys(part for part in parts if part))


def _render_formula(formula: dict[str, Any]) -> str:
    label = str(formula.get("label") or formula.get("number") or formula.get("id") or "").strip()
    plain = str(
        formula.get("plain")
        or formula.get("display")
        or formula.get("expression")
        or formula.get("displayAsPrinted")
        or ""
    ).strip()
    latex = str(formula.get("latex") or formula.get("latexAsPrinted") or "").strip()
    lines = [f"公式 {label}".strip()]
    if plain:
        lines.append(plain)
    if latex:
        lines.append(f"LaTeX: {latex}")
    excluded = {
        "label",
        "number",
        "id",
        "plain",
        "display",
        "expression",
        "displayAsPrinted",
        "latex",
        "latexAsPrinted",
        "region",
        "engine",
        "sourceFingerprint",
        "reviewStatus",
        "reviewMethod",
    }
    for key, value in formula.items():
        if key in excluded:
            continue
        values = list(_content_scalars(value, key))
        if values:
            lines.append(f"{key}: " + " | ".join(values))
    return "\n".join(dict.fromkeys(line for line in lines if line))


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _render_table(table: dict[str, Any]) -> str:
    number = str(table.get("number") or table.get("label") or table.get("id") or "").strip()
    title = str(table.get("title") or "").strip()
    lines = [" ".join(item for item in ("表", number, title) if item).strip()]
    columns = table.get("columns") or table.get("headers") or []
    if isinstance(columns, list) and columns:
        lines.append("\t".join(_cell_text(item) for item in columns))
    rows = table.get("rows") or []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, list):
                lines.append("\t".join(_cell_text(item) for item in row))
            else:
                lines.append(_cell_text(row))
    excluded = {"number", "label", "id", "title", "columns", "headers", "rows"}
    for key, value in table.items():
        if key in excluded:
            continue
        values = list(_content_scalars(value, key))
        if values:
            lines.append(f"{key}: " + " | ".join(values))
    return "\n".join(line for line in lines if line)


def render_corrected_page(record: dict[str, Any]) -> str:
    """Render every corrected content field into lossless searchable plain text.

    The structured record remains authoritative. This rendering is only the
    human-readable/search representation; formulas and tables retain their
    structured forms in JSON output.
    """
    sections: list[str] = []
    blocks = [
        rendered
        for block in record.get("blocks") or []
        if isinstance(block, dict) and (rendered := _render_block(block))
    ]
    formulas = [
        _render_formula(item) for item in record.get("formulas") or [] if isinstance(item, dict)
    ]
    tables = [_render_table(item) for item in record.get("tables") or [] if isinstance(item, dict)]
    if blocks:
        sections.append("[正文]\n" + "\n".join(blocks))
    if formulas:
        sections.append("[公式]\n" + "\n\n".join(formulas))
    if tables:
        sections.append("[表格]\n" + "\n\n".join(tables))
    return "\n\n".join(sections)

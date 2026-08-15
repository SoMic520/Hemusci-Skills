#!/usr/bin/env python3
"""Shared scope policy for format-only review records and comments."""

from __future__ import annotations

import re
from typing import Any

ALLOWED_CATEGORIES = {
    "PAGE_LAYOUT",
    "TITLE_BLOCK",
    "AUTHOR_AFFILIATION_LAYOUT",
    "ABSTRACT_LAYOUT",
    "HEADING_STYLE",
    "BODY_TYPOGRAPHY",
    "PARAGRAPH_SPACING",
    "FIGURE_LAYOUT",
    "TABLE_LAYOUT",
    "CAPTION_STYLE",
    "EQUATION_LAYOUT",
    "FOOTNOTE_ENDNOTE_LAYOUT",
    "REFERENCE_LAYOUT",
    "HEADER_FOOTER",
    "ANONYMIZATION_LAYOUT",
    "FILE_NAMING_DELIVERY",
}

_FORBIDDEN_KEY_PATTERNS = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"quality",
        r"novelty",
        r"significance",
        r"method(?:ology)?",
        r"statistics?",
        r"scientific",
        r"logic",
        r"conclusion",
        r"data[_-]?quality",
        r"article[_-]?grade",
        r"journal[_-]?rank",
        r"impact[_-]?factor",
        r"文章质量",
        r"创新(?:性)?",
        r"科学(?:性)?",
        r"方法(?:学)?",
        r"统计(?:学)?",
        r"逻辑",
        r"结论",
        r"数据质量",
        r"学术水平",
        r"期刊等级",
        r"影响因子",
    )
)

_FORBIDDEN_TEXT_PATTERNS = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"(?:研究|文章|论文).{0,8}(?:质量|水平|创新|价值|意义|科学性|可信度)",
        r"(?:方法|试验设计|实验设计).{0,8}(?:不当|错误|合理|科学|严谨|缺陷)",
        r"(?:统计|显著性|样本量).{0,8}(?:错误|不足|不合理|有问题)",
        r"(?:结论|结果|数据).{0,8}(?:不支持|错误|可疑|不可信|矛盾)",
        r"(?:应拒稿|建议拒稿|不宜发表|可以发表|录用价值)",
        r"\b(?:poor|weak|strong|high)[ -](?:quality|novelty|significance)\b",
        r"\b(?:scientifically|methodologically|statistically) (?:sound|flawed|invalid)\b",
        r"\b(?:reject|accept) (?:the )?(?:paper|manuscript|article)\b",
        r"\b(?:methods?|statistics?|results?|conclusions?|data) (?:are|is|seem) (?:wrong|invalid|weak|unreliable|unsupported)\b",
    )
)


def _walk(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield "key", child_path, str(key)
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield "text", path, value


def validate_format_only_payload(value: Any) -> list[str]:
    errors: list[str] = []
    for kind, path, text in _walk(value):
        patterns = _FORBIDDEN_KEY_PATTERNS if kind == "key" else _FORBIDDEN_TEXT_PATTERNS
        for pattern in patterns:
            match = pattern.search(text)
            if match and kind == "text":
                prefix = text[max(0, match.start() - 24) : match.start()].casefold()
                if any(
                    marker in prefix
                    for marker in (
                        "不审查",
                        "不评价",
                        "未审查",
                        "未评价",
                        "不涉及",
                        "does not review",
                        "not reviewed",
                        "no review of",
                    )
                ):
                    continue
            if match:
                errors.append(f"{path}: out-of-scope {kind} matches {pattern.pattern!r}")
                break
    return errors


def require_format_category(value: Any, label: str) -> str:
    category = str(value or "").strip().upper()
    if category not in ALLOWED_CATEGORIES:
        raise ValueError(
            f"{label}: category must be one of {', '.join(sorted(ALLOWED_CATEGORIES))}"
        )
    return category

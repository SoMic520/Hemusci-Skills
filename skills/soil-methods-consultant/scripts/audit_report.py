#!/usr/bin/env python3
"""Audit a generated HTML/PDF method report against its verified method card."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import generate_report

try:
    from pypdf import PdfReader
except ModuleNotFoundError:
    generate_report.reexec_with_bundled_runtime()


def normalized(value: str) -> str:
    return re.sub(r"\s+", "", value)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def find_pdftotext() -> Path | None:
    candidates = [
        Path.home()
        / ".cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/poppler/bin/pdftotext",
        Path(shutil.which("pdftotext") or ""),
    ]
    return next((value for value in candidates if value and value.is_file()), None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--card-id", required=True)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--include-source-pages", action="store_true")
    parser.add_argument("--curated", action="store_true", help="审计由 AI 依据已核验来源整理的简要实验方案")
    args = parser.parse_args()

    errors: list[str] = []
    card, pages = generate_report.load_card(args.card_id)
    formulas = generate_report.extract_formulas(pages)
    definitions = generate_report.extract_verified_definitions(pages)
    details = generate_report.component_details(card, pages)
    require(args.html.is_file() and args.html.stat().st_size > 10_000, "HTML 不存在或体积异常", errors)
    require(args.pdf.is_file() and args.pdf.stat().st_size > 20_000, "PDF 不存在或体积异常", errors)
    if errors:
        print("FAIL")
        for value in errors:
            print("- " + value)
        return 1

    html_text = args.html.read_text(encoding="utf-8")
    visible_html = html.unescape(re.sub(r"<[^>]+>", " ", html_text))
    require("\ufffd" not in html_text and "(cid:" not in html_text, "HTML 含乱码或内部字形编码", errors)
    required_labels = (
        ("测定组合", "试剂与仪器", "实验步骤", "计算与结果表达", "质量控制")
        if args.curated
        else ("方法适用性与选择依据", "标准操作规程", "结果计算、单位与判定")
    )
    for label in required_labels:
        require(label in visible_html, f"HTML 缺少模块: {label}", errors)
    require("来源、版本与复核信息" not in visible_html, "HTML 仍包含已取消的来源信息专节", errors)
    require("<section class=\"page cover\"" not in html_text, "HTML 不应包含独立封面", errors)
    require("校正语料直接生成" not in visible_html, "HTML 仍显示内部生成说明", errors)
    require("页码 / 方法卡 / 指纹" not in visible_html, "HTML 仍显示内部追踪汇总行", errors)
    require("校正语料生成" not in visible_html, "HTML 仍显示内部生成标记", errors)
    if args.curated:
        require(generate_report.resolved_source_label(card, pages) in visible_html, "HTML 未列出主来源", errors)
    else:
        require("完整出处" in visible_html and generate_report.full_source_citation(card, pages) in visible_html, "HTML 未完整列出出处和方法层级", errors)
    require(html_text.count("<svg") >= (5 if args.curated else 8), "HTML 图标数不足", errors)
    require("@media print" in html_text and re.search(r"@media\(max-width:\d+px\)", html_text) is not None, "HTML 缺少打印或响应式样式", errors)
    require('--sans:"PingFang SC","Noto Sans CJK SC","Source Han Sans SC"' in html_text, "HTML 正文未使用标准化中文无衬线字体栈", errors)
    require('--serif:"Songti SC","Noto Serif CJK SC","Source Han Serif SC"' in html_text, "HTML 标题未使用标准化中文衬线字体栈", errors)
    require('--math:"STIX Two Math","Cambria Math"' in html_text, "HTML 公式未使用数学字体栈", errors)
    require("font-family:var(--sans)" in html_text, "HTML 步骤正文字体未标准化", errors)
    if not args.curated:
        require(".step-detail p{display:grid" in html_text, "HTML 步骤正文字体未标准化", errors)
        require('grid-template-areas:"rail content"' in html_text, "HTML 未锁定编号栏与正文栏位置", errors)
    if args.include_source_pages:
        require('id="appendix"' in html_text and "校正原文与页码对照" in visible_html, "HTML 缺少已要求的校正页文", errors)
        require(".appendix .section-content{grid-column:1/-1" in html_text, "HTML 校正原文未使用通栏布局", errors)
    else:
        require('id="appendix"' not in html_text and "校正原文与页码对照" not in visible_html, "HTML 不应默认附带校正原文", errors)
    require("书中未明确说明" not in visible_html and "不根据常识自行补写" not in visible_html and "本方法卡未提供" not in visible_html, "HTML 含内部占位说明", errors)
    normalized_html = normalized(visible_html)
    if args.curated:
        for token in ("csa", "cb", "Vsa", "Vsu", "Vb", "msa", "Wsd", "1000"):
            require(token in normalized_html, f"HTML 公式缺少关键字符: {token}", errors)
        for token in ("22.10g", "0.10mol/L", "300μL", "500μmol/L", "30±2", "700次/min", "355nm", "460nm"):
            require(token in normalized_html, f"HTML 缺少关键执行参数: {token}", errors)
    else:
        require("grid-template-columns:66px minmax(0,1fr)" in html_text, "HTML 公式释义列缺少宽度保护", errors)
        require(".step-detail p>span{grid-column:2" in html_text, "HTML 无编号操作行未锁定到正文列", errors)
        require(".step-detail p>small{grid-column:3" in html_text, "HTML 步骤页码未锁定到页码列", errors)
        for formula in formulas:
            require(normalized(formula["plain"]) in normalized_html, f"HTML 公式不一致: {formula['label']}", errors)
        for row in definitions:
            require(normalized(row["text"]) in normalized_html, f"HTML 变量或单位不一致: P.{row['page']}", errors)
        for rows in details.values():
            for row in rows:
                require(normalized(row["text"]) in normalized_html, f"HTML 条款正文不一致: P.{row['page']}", errors)

    reader = PdfReader(str(args.pdf))
    require(len(reader.pages) >= 2, "PDF 页数异常", errors)
    if args.curated:
        require(bool(str((reader.metadata or {}).get("/Title") or "").strip()), "PDF 缺少标题元数据", errors)
    else:
        require(str((reader.metadata or {}).get("/Title") or "").startswith(str(card.get("title") or "")), "PDF 标题元数据不匹配", errors)
    base_fonts: set[str] = set()
    for page_number, page in enumerate(reader.pages, 1):
        box = page.mediabox
        width, height = float(box.width), float(box.height)
        require(abs(width - 595.276) < 1 and abs(height - 841.89) < 1, f"PDF 第{page_number}页不是 A4", errors)
        resources = page.get("/Resources") or {}
        fonts = resources.get("/Font") or {}
        if hasattr(fonts, "get_object"):
            fonts = fonts.get_object()
        for font_ref in fonts.values():
            font = font_ref.get_object() if hasattr(font_ref, "get_object") else font_ref
            base_fonts.add(str(font.get("/BaseFont") or ""))
    require(any("STHeiti" in name or "NotoSansCJK" in name for name in base_fonts), "PDF 未嵌入标准化中文正文字体", errors)
    require(any("STSongti-SC-Bold" in name or "NotoSerifCJK" in name for name in base_fonts), "PDF 未嵌入标准化中文标题字体", errors)
    require(any("ArialUnicode" in name or "NotoSansCJK" in name for name in base_fonts), "PDF 未嵌入完整公式字形字体", errors)

    pdftotext = find_pdftotext()
    require(pdftotext is not None, "缺少 pdftotext，无法校验 PDF 公式字符", errors)
    if pdftotext is not None:
        with tempfile.TemporaryDirectory(prefix="soil-report-audit-") as temp:
            text_path = Path(temp) / "report.txt"
            subprocess.run([str(pdftotext), "-layout", str(args.pdf), str(text_path)], check=True)
            pdf_text = text_path.read_text(encoding="utf-8", errors="replace")
        pdf_content_text = re.sub(r"P\.\d+", "", pdf_text)
        require("\ufffd" not in pdf_text and "(cid:" not in pdf_text, "PDF 文本含乱码或内部字形编码", errors)
        require("校正语料生成" not in pdf_text, "PDF 页脚仍显示内部生成标记", errors)
        require("书中未明确说明" not in pdf_text and "不根据常识自行补写" not in pdf_text and "本方法卡未提供" not in pdf_text, "PDF 含内部占位说明", errors)
        if args.include_source_pages:
            require("校正原文与页码对照" in pdf_text, "PDF 缺少已要求的校正页文", errors)
        else:
            require("校正原文与页码对照" not in pdf_text, "PDF 不应默认附带校正原文", errors)
        if args.curated:
            normalized_pdf = normalized(pdf_text)
            for token in ("csa", "cb", "Vsa", "Vsu", "Vb", "msa", "Wsd", "1000"):
                require(token in normalized_pdf, f"PDF 公式缺少关键字符: {token}", errors)
            for token in ("22.10g", "0.10mol/L", "300μL", "500μmol/L", "30±2", "700次/min", "355nm", "460nm"):
                require(token in normalized_pdf, f"PDF 缺少关键执行参数: {token}", errors)
        else:
            for formula in formulas:
                require(normalized(formula["plain"]) in normalized(pdf_text), f"PDF 公式不一致: {formula['label']}", errors)
            for row in definitions:
                require(normalized(row["text"]) in normalized(pdf_content_text), f"PDF 变量或单位不一致: P.{row['page']}", errors)
            for rows in details.values():
                for row in rows:
                    require(normalized(row["text"]) in normalized(pdf_content_text), f"PDF 条款正文不一致: P.{row['page']}", errors)

    if errors:
        print(f"FAIL: {len(errors)}")
        for value in errors:
            print("- " + value)
        return 1
    print(f"PASS: {args.card_id}; formulas={len(formulas)}; pdfPages={len(reader.pages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

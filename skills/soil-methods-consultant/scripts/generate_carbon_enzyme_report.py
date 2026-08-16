#!/usr/bin/env python3
"""Generate the concise GB/Z 170—2026 carbon-enzyme protocol report."""

from __future__ import annotations

import html
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import generate_report as base
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = SCRIPT_DIR.parents[2]
HTML_PATH = ROOT / "output/html/soil-carbon-enzyme-activity-microplate.html"
PDF_PATH = ROOT / "output/pdf/soil-carbon-enzyme-activity-microplate.pdf"
SOURCE = (
    "GB/Z 170—2026/ISO/TS 22939:2019《土壤质量 土壤酶活性测定 "
    "荧光底物微孔板法》，正文第5—10章及附录A、NB"
)


def e(value: str) -> str:
    return html.escape(value, quote=True)


def svg_icon(kind: str) -> str:
    paths = {
        "target": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v4M22 12h-4"/>',
        "reagent": '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3"/><path d="M8 15h8"/>',
        "steps": '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
        "calc": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 13h2M14 13h2M8 17h2M14 17h2"/>',
        "check": '<path d="M12 3 5 6v5c0 4.5 2.8 8.1 7 10 4.2-1.9 7-5.5 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-5"/>',
    }
    return (
        '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round">{paths[kind]}</svg>'
    )


def build_html() -> str:
    enzyme_rows = [
        ("AG", "α-葡萄糖苷酶", "4-MUF-α-D-吡喃葡萄糖苷", "淀粉和糖原"),
        ("BG", "β-葡萄糖苷酶", "4-MUF-β-D-吡喃葡萄糖苷", "纤维素"),
        ("CBH", "纤维二糖酶", "4-MUF-β-纤维素二糖苷", "纤维素"),
        ("BX", "β-木糖苷酶", "4-MUF-β-D-吡喃木糖苷", "木聚糖、木二糖"),
    ]
    enzyme_html = "".join(
        f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{d}</td></tr>"
        for a, b, c, d in enzyme_rows
    )
    steps = [
        ("01", "配制 MES 缓冲液", "将 22.10 g MES 溶于 1 L 去离子水，得到 0.10 mol/L、pH 6.1 的 MES 缓冲液；（121±3）℃灭菌 20 min。碳循环 MUF 底物均使用该缓冲液。"),
        ("02", "现配底物与 MUF 标准", "各底物配成 10 mmol/L 储备液：先溶于 300 μL DMSO，再用灭菌去离子水定容至 10 mL；以 MES 稀释成 1 mmol/L 工作液。MUF 标准以 DMSO 配成 5 mmol/L，再以 MES 稀释至 10 μmol/L。全部临用现配并避光。"),
        ("03", "制备土壤悬浊液", "称取 1.00 g 新鲜、过筛并混匀的土壤，加入 100 mL 无菌去离子水；50 J/s 超声 120 s，得到 1∶100 悬浊液。高活性样品可预试 1∶1 000，但不同稀释水平的数据不能直接比较。"),
        ("04", "孔板加样", "每个反应孔加入 50 μL 土壤悬浊液、50 μL MES 缓冲液和 100 μL 底物工作液，总体积 200 μL，底物终浓度 500 μmol/L；每样每酶做 4 个平行。设置不加底物的土壤对照。"),
        ("05", "建立样品基质标准曲线", "每个土壤样品单独建立 MUF 标准曲线：孔内含 50 μL 同一土壤悬浊液，加 MUF 标准液和 MES 至 200 μL，使终浓度为 0、0.50、1.00、2.50、4.00、6.00 μmol/L。另设试剂空白：100 μL MES + 100 μL 底物。"),
        ("06", "培养与读数", "加样后立即读荧光；随后在（30±2）℃、700 次/min 条件下振荡培养 3 h，并在严格一致的时间间隔再次读数。荧光计设置：激发 355 nm、发射 460 nm。"),
    ]
    step_html = "".join(
        f'<article class="step"><span class="step-no">{n}</span><div><h3>{t}</h3><p>{x}</p></div></article>'
        for n, t, x in steps
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>土壤碳循环水解酶活性测定</title>
<style>
:root{{--ink:#17332c;--green:#0e684f;--mint:#eaf3ee;--line:#ccd8d2;--paper:#fbfaf6;--gold:#b97b18;--sans:"PingFang SC","Noto Sans CJK SC","Source Han Sans SC","Microsoft YaHei",sans-serif;--serif:"Songti SC","Noto Serif CJK SC","Source Han Serif SC","STSong",serif;--math:"STIX Two Math","Cambria Math","Times New Roman",serif}}
*{{box-sizing:border-box}}html{{background:#e6e8e4}}body{{margin:0;color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.72;-webkit-font-smoothing:antialiased}}main{{width:min(1040px,100%);margin:0 auto;background:var(--paper);padding:54px 72px 64px}}header{{border-top:4px solid var(--ink);padding:28px 0 30px;border-bottom:1px solid var(--line)}}.eyebrow{{font-size:11px;letter-spacing:.2em;color:var(--green);font-weight:700}}h1{{font-family:var(--serif);font-size:48px;line-height:1.16;letter-spacing:-.035em;margin:10px 0 10px}}.deck{{font-family:var(--serif);font-size:19px;color:#4e625a;margin:0 0 18px}}.source{{font-size:12px;color:#68766f;margin:0}}section{{padding:42px 0;border-bottom:1px solid var(--line)}}.section-title{{display:flex;align-items:center;gap:12px;margin-bottom:20px}}.ico{{width:25px;height:25px;color:var(--green);flex:0 0 auto}}h2{{font-family:var(--serif);font-size:29px;line-height:1.25;margin:0}}.intro{{margin:-7px 0 24px;color:#50635b}}table{{width:100%;border-collapse:collapse;font-size:14px}}th{{text-align:left;font-size:12px;letter-spacing:.08em;color:#53685f;background:var(--mint)}}th,td{{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}}td:first-child{{white-space:nowrap;color:var(--green)}}.note{{margin-top:18px;padding:13px 0 13px 18px;border-left:3px solid var(--gold);color:#4a5b54}}.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:40px}}h3{{font-size:16px;margin:0 0 7px}}ul{{margin:0;padding-left:20px}}li+li{{margin-top:7px}}.steps{{border-top:1px solid var(--ink)}}.step{{display:grid;grid-template-columns:54px 1fr;gap:20px;padding:21px 0;border-bottom:1px solid var(--line)}}.step-no{{font-family:var(--math);font-size:20px;color:var(--green);font-weight:700}}.step p{{margin:0;color:#344a42}}.formula-wrap{{padding:26px 20px;text-align:center;background:var(--mint);border-top:1px solid var(--green);border-bottom:1px solid var(--green);overflow-x:auto}}.formula{{font-family:var(--math);font-size:25px;white-space:nowrap}}.frac{{display:inline-flex;vertical-align:middle;flex-direction:column;align-items:stretch;margin-left:6px}}.frac .num{{padding:0 10px 5px;border-bottom:1.5px solid currentColor}}.frac .den{{padding-top:5px}}.defs{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 28px;margin-top:22px;font-size:13px}}.defs p{{margin:0;padding-bottom:7px;border-bottom:1px dotted var(--line)}}.defs b{{font-family:var(--math);color:var(--green)}}.qc{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 34px;counter-reset:item}}.qc p{{position:relative;margin:0;padding:13px 0 13px 32px;border-bottom:1px solid var(--line)}}.qc p:before{{counter-increment:item;content:counter(item,decimal-leading-zero);position:absolute;left:0;color:var(--green);font-family:var(--math);font-size:12px;font-weight:700}}footer{{padding-top:26px;font-size:12px;color:#68766f}}footer strong{{color:var(--ink)}}
@media(max-width:760px){{main{{padding:32px 22px 44px}}h1{{font-size:37px}}.two-col,.defs,.qc{{grid-template-columns:1fr}}.formula{{font-size:19px}}th:nth-child(3),td:nth-child(3){{display:none}}}}
@media print{{html{{background:#fff}}body{{font-size:11px}}main{{width:210mm;margin:0;padding:15mm 17mm 14mm}}header{{padding:8mm 0}}h1{{font-size:28px}}.deck{{font-size:13px}}section{{padding:9mm 0}}h2{{font-size:19px}}.step{{break-inside:avoid;padding:4mm 0}}.formula-wrap,.note{{break-inside:avoid}}}}
</style></head><body><main>
<header><div class="eyebrow">SOIL CARBON ENZYME ASSAY</div><h1>土壤碳循环水解酶活性测定</h1><p class="deck">采用现测现配 MUF 荧光底物的 96 孔板方案；同一块板可并行测定碳水化合物降解酶谱。</p><p class="source">依据：{e(SOURCE)}</p></header>
<section><div class="section-title">{svg_icon('target')}<h2>测定组合</h2></div><p class="intro">基础碳水化合物降解酶谱建议同时测定下列 4 项；若研究几丁质或微生物残体，可在同一标准体系中另加 NAG。</p><table><thead><tr><th>缩写</th><th>酶</th><th>荧光底物</th><th>主要表征对象</th></tr></thead><tbody>{enzyme_html}</tbody></table><p class="note"><b>结果含义：</b>测得的是规定底物、pH、温度和培养时间下的潜在酶活性，适合处理间或场地间比较，不宜仅凭单个绝对值判定土壤质量。</p></section>
<section><div class="section-title">{svg_icon('reagent')}<h2>试剂与仪器</h2></div><div class="two-col"><div><h3>关键试剂</h3><ul><li>0.10 mol/L MES 缓冲液，pH 6.1</li><li>AG、BG、CBH、BX 的 4-MUF 底物</li><li>4-甲基伞形酮（MUF）标准品</li><li>DMSO、无菌去离子水</li></ul></div><div><h3>关键仪器</h3><ul><li>黑色 96 孔微孔板（带盖）</li><li>多道移液器与避光容器</li><li>可振荡培养箱：700 次/min</li><li>荧光酶标仪：Ex 355 nm / Em 460 nm</li></ul></div></div></section>
<section><div class="section-title">{svg_icon('steps')}<h2>实验步骤</h2></div><div class="steps">{step_html}</div></section>
<section><div class="section-title">{svg_icon('calc')}<h2>计算与结果表达</h2></div><p class="intro">由每个样品自己的 MUF 标准曲线换算培养 3 h 后的浓度，再按标准公式计算：</p><div class="formula-wrap"><span class="formula"><i>x</i> = <span class="frac"><span class="num">(<i>c</i><sub>sa</sub> − <i>c</i><sub>b</sub>)(<i>V</i><sub>sa</sub> + <i>V</i><sub>su</sub> + <i>V</i><sub>b</sub>)<i>V</i> × 1000</span><span class="den"><i>V</i><sub>sa</sub><i>m</i><sub>sa</sub><i>W</i><sub>sd</sub></span></span></span></div><div class="defs"><p><b>c<sub>sa</sub></b>：培养 3 h 后反应体系 MUF 浓度，μmol/L</p><p><b>c<sub>b</sub></b>：空白体系 MUF 浓度，μmol/L</p><p><b>V<sub>sa</sub></b>：土壤悬浊液加入量，μL</p><p><b>V<sub>su</sub></b>：底物溶液加入量，μL</p><p><b>V<sub>b</sub></b>：缓冲液加入量，μL</p><p><b>V</b>：土壤悬浊液总体积，L</p><p><b>m<sub>sa</sub></b>：新鲜土壤质量，g</p><p><b>W<sub>sd</sub></b>：干土质量/鲜土质量</p></div><p class="note"><b>推荐报告口径：</b>每克干重土壤在 3 h 内释放的 MUF（μmol 或 nmol）。鲜重、干重或单位土壤有机质只能选定一种口径并在全部样品中保持一致。</p></section>
<section><div class="section-title">{svg_icon('check')}<h2>质量控制</h2></div><div class="qc"><p>同一样品、同一酶做 4 个平行，报告平均值并检查异常孔。</p><p>每种土壤/每个稀释水平单独建立 MUF 标准曲线，以校正土壤荧光淬灭。</p><p>底物、MUF 标准和 DMSO 溶液临用现配，全程避光。</p><p>所有组保持相同缓冲液 pH、稀释倍数、培养温度和精确培养时间。</p><p>正式测定前预检底物浓度和稀释倍数，确保信号落在标准曲线范围内。</p><p>同步测定土壤含水量并计算 W<sub>sd</sub>；解释结果时至少记录土壤 pH。</p></div></section>
<footer><strong>方法边界：</strong>本方案仅对应 MUF 荧光底物微孔板法中的碳循环水解酶；木质素相关氧化酶（如酚氧化酶、过氧化物酶）需采用另一套方法，不能直接套用本方案参数。</footer>
</main></body></html>"""


def pdf_styles() -> dict[str, ParagraphStyle]:
    base_styles = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle("eyebrow", parent=base_styles["Normal"], fontName=base.FONT_BOLD, fontSize=7.5, leading=10, textColor=colors.HexColor("#0e684f"), spaceAfter=5),
        "title": ParagraphStyle("title", parent=base_styles["Title"], fontName=base.FONT_SERIF_BOLD, fontSize=26, leading=32, textColor=colors.HexColor("#17332c"), spaceAfter=6),
        "deck": ParagraphStyle("deck", parent=base_styles["Normal"], fontName=base.FONT_SERIF, fontSize=10.5, leading=16, textColor=colors.HexColor("#4e625a"), spaceAfter=7),
        "source": ParagraphStyle("source", parent=base_styles["Normal"], fontName=base.FONT_REGULAR, fontSize=7.2, leading=11, textColor=colors.HexColor("#66766f")),
        "h2": ParagraphStyle("h2", parent=base_styles["Heading2"], fontName=base.FONT_SERIF_BOLD, fontSize=17, leading=22, textColor=colors.HexColor("#17332c"), spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=base_styles["Heading3"], fontName=base.FONT_BOLD, fontSize=9.4, leading=13, textColor=colors.HexColor("#17332c"), spaceAfter=3),
        "body": ParagraphStyle("body", parent=base_styles["Normal"], fontName=base.FONT_REGULAR, fontSize=8.4, leading=13.2, textColor=colors.HexColor("#2f463e")),
        "body_small": ParagraphStyle("body_small", parent=base_styles["Normal"], fontName=base.FONT_REGULAR, fontSize=7.4, leading=11.3, textColor=colors.HexColor("#42584f")),
        "small": ParagraphStyle("small", parent=base_styles["Normal"], fontName=base.FONT_REGULAR, fontSize=6.7, leading=9.8, textColor=colors.HexColor("#64756e")),
        "table_head": ParagraphStyle("table_head", parent=base_styles["Normal"], fontName=base.FONT_BOLD, fontSize=7.2, leading=10, textColor=colors.HexColor("#17332c")),
        "table_cell": ParagraphStyle("table_cell", parent=base_styles["Normal"], fontName=base.FONT_REGULAR, fontSize=7.2, leading=10.5, textColor=colors.HexColor("#263d35")),
        "step_no": ParagraphStyle("step_no", parent=base_styles["Normal"], fontName=base.FONT_FORMULA, fontSize=11, leading=14, textColor=colors.HexColor("#0e684f"), alignment=TA_CENTER),
        "formula": ParagraphStyle("formula", parent=base_styles["Normal"], fontName=base.FONT_FORMULA, fontSize=12.5, leading=17, textColor=colors.HexColor("#17332c"), alignment=TA_CENTER),
        "formula_def": ParagraphStyle("formula_def", parent=base_styles["Normal"], fontName=base.FONT_FORMULA, fontSize=6.7, leading=10.5, textColor=colors.HexColor("#384f47")),
    }


def heading(kind: str, number: str, title: str, styles: dict[str, ParagraphStyle]) -> Table:
    return Table(
        [[base.pdf_icon(kind, 19), Paragraph(f"<font color='#0e684f'>{number}</font>  {e(title)}", styles["h2"])]],
        colWidths=[8 * mm, 166 * mm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]),
    )


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#ccd8d2"))
    canvas.setLineWidth(0.35)
    canvas.line(18 * mm, 12 * mm, 192 * mm, 12 * mm)
    canvas.setFont(base.FONT_REGULAR, 6.4)
    canvas.setFillColor(colors.HexColor("#66766f"))
    canvas.drawString(18 * mm, 7.4 * mm, "GB/Z 170—2026 · 土壤碳循环水解酶活性测定")
    canvas.drawRightString(192 * mm, 7.4 * mm, str(doc.page))
    canvas.restoreState()


def build_pdf() -> None:
    base.register_pdf_fonts()
    styles = pdf_styles()
    PDF_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(PDF_PATH), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=15 * mm, bottomMargin=17 * mm,
        title="土壤碳循环水解酶活性测定", author="soil-methods-consultant",
    )
    story = []
    mast = Table(
        [[base.pdf_icon("flask", 17), Paragraph("SOIL CARBON ENZYME ASSAY", styles["eyebrow"])]],
        colWidths=[8 * mm, 166 * mm],
        style=TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 1.1, colors.HexColor("#17332c")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]),
    )
    story.extend([
        mast, Spacer(1, 6 * mm),
        Paragraph("土壤碳循环水解酶活性测定", styles["title"]),
        Paragraph("采用现测现配 MUF 荧光底物的 96 孔板方案；同一块板可并行测定碳水化合物降解酶谱。", styles["deck"]),
        Paragraph(f"依据：{e(SOURCE)}", styles["source"]),
        Spacer(1, 8 * mm),
    ])

    story.append(heading("target", "01", "测定组合", styles))
    enzyme_data = [
        ["缩写", "酶", "荧光底物", "主要表征对象"],
        ["AG", "α-葡萄糖苷酶", "4-MUF-α-D-吡喃葡萄糖苷", "淀粉和糖原"],
        ["BG", "β-葡萄糖苷酶", "4-MUF-β-D-吡喃葡萄糖苷", "纤维素"],
        ["CBH", "纤维二糖酶", "4-MUF-β-纤维素二糖苷", "纤维素"],
        ["BX", "β-木糖苷酶", "4-MUF-β-D-吡喃木糖苷", "木聚糖、木二糖"],
    ]
    enzyme_table = Table(
        [[Paragraph(e(cell), styles["table_head"] if r == 0 else styles["table_cell"]) for cell in row] for r, row in enumerate(enzyme_data)],
        colWidths=[18 * mm, 34 * mm, 81 * mm, 41 * mm], repeatRows=1,
    )
    enzyme_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf3ee")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#ccd8d2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([enzyme_table, Spacer(1, 3 * mm), Paragraph("基础酶谱测 AG、BG、CBH、BX；若研究几丁质或微生物残体，可在同一标准体系中另加 NAG。测得的是规定条件下的潜在酶活性，主要用于样品间比较。", styles["body_small"]), Spacer(1, 7 * mm)])

    story.append(heading("flask", "02", "试剂与仪器", styles))
    reagent_table = Table(
        [[Paragraph("<b>关键试剂</b><br/>0.10 mol/L MES（pH 6.1）；4 种 4-MUF 底物；MUF 标准品；DMSO；无菌去离子水。", styles["body"]), Paragraph("<b>关键仪器</b><br/>黑色 96 孔板；多道移液器；可振荡培养箱；荧光酶标仪（Ex 355 nm / Em 460 nm）。", styles["body"])]],
        colWidths=[87 * mm, 87 * mm],
        style=TableStyle([
            ("LINEABOVE", (0, 0), (-1, 0), 0.7, colors.HexColor("#17332c")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.35, colors.HexColor("#ccd8d2")),
            ("LINEBEFORE", (1, 0), (1, 0), 0.35, colors.HexColor("#ccd8d2")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("LEFTPADDING", (1, 0), (1, 0), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]),
    )
    story.extend([reagent_table, Spacer(1, 7 * mm)])

    story.append(heading("steps", "03", "实验步骤", styles))
    steps = [
        ("01", "配制 MES 缓冲液", "22.10 g MES 溶于 1 L 去离子水，得到 0.10 mol/L、pH 6.1 缓冲液；（121±3）℃灭菌 20 min。"),
        ("02", "现配底物与标准", "各底物先溶于 300 μL DMSO，再以灭菌去离子水定容至 10 mL，配成 10 mmol/L 储备液；以 MES 稀释成 1 mmol/L 工作液。MUF 标准先以 DMSO 配成 5 mmol/L，再以 MES 稀释至 10 μmol/L。全程避光。"),
        ("03", "制备土壤悬浊液", "1.00 g 新鲜、过筛并混匀的土壤 + 100 mL 无菌去离子水；50 J/s 超声 120 s，得到 1∶100 悬浊液。高活性样品可预试 1∶1 000，但不同稀释水平不可直接比较。"),
        ("04", "反应孔", "每孔加入 50 μL 土壤悬浊液 + 50 μL MES + 100 μL 底物工作液，总体积 200 μL，底物终浓度 500 μmol/L；每样每酶 4 个平行，并设置不加底物的土壤对照。"),
        ("05", "样品基质标准曲线", "每个土壤样品单独建 MUF 标准曲线：50 μL 同一土壤悬浊液，加 MUF 标准液和 MES 至 200 μL，使终浓度为 0、0.50、1.00、2.50、4.00、6.00 μmol/L。试剂空白为 100 μL MES + 100 μL 底物。"),
        ("06", "培养与读数", "加样后立即读荧光；（30±2）℃、700 次/min 振荡培养 3 h，在严格一致的时间间隔再次读数。荧光计：激发 355 nm，发射 460 nm。"),
    ]
    for number, title, text in steps:
        row = Table(
            [[Paragraph(number, styles["step_no"]), Paragraph(f"<b>{e(title)}</b><br/>{e(text)}", styles["body"])]],
            colWidths=[14 * mm, 160 * mm],
            style=TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 0.35, colors.HexColor("#ccd8d2")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
            ]),
        )
        story.append(KeepTogether([row]))
    story.append(Spacer(1, 7 * mm))

    story.append(heading("calc", "04", "计算与结果表达", styles))
    numerator = "(<i>c</i><sub>sa</sub> − <i>c</i><sub>b</sub>)(<i>V</i><sub>sa</sub> + <i>V</i><sub>su</sub> + <i>V</i><sub>b</sub>)<i>V</i> × 1000"
    denominator = "<i>V</i><sub>sa</sub><i>m</i><sub>sa</sub><i>W</i><sub>sd</sub>"
    fraction = Table(
        [[Paragraph(numerator, styles["formula"])], [Paragraph(denominator, styles["formula"])]],
        colWidths=[130 * mm],
        style=TableStyle([
            ("LINEBELOW", (0, 0), (0, 0), 0.8, colors.HexColor("#17332c")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]),
    )
    formula = Table(
        [[Paragraph("<i>x</i> =", styles["formula"]), fraction]],
        colWidths=[20 * mm, 138 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eaf3ee")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#0e684f")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]),
    )
    story.extend([Paragraph("由每个样品自己的 MUF 标准曲线换算培养 3 h 后的浓度，再按标准公式计算：", styles["body"]), Spacer(1, 3 * mm), formula, Spacer(1, 4 * mm)])
    definitions = [
        ("c<sub>sa</sub>", "培养 3 h 后反应体系 MUF 浓度，μmol/L"),
        ("c<sub>b</sub>", "空白体系 MUF 浓度，μmol/L"),
        ("V<sub>sa</sub>", "土壤悬浊液加入量，μL"),
        ("V<sub>su</sub>", "底物溶液加入量，μL"),
        ("V<sub>b</sub>", "缓冲液加入量，μL"),
        ("V", "土壤悬浊液总体积，L"),
        ("m<sub>sa</sub>", "新鲜土壤质量，g"),
        ("W<sub>sd</sub>", "干土质量/鲜土质量"),
    ]
    def_data = []
    for index in range(0, len(definitions), 2):
        pair = definitions[index:index + 2]
        row = []
        for symbol, text in pair:
            row.extend([Paragraph(f"<b>{symbol}</b>", styles["formula_def"]), Paragraph(e(text), styles["body_small"])])
        def_data.append(row)
    def_table = Table(def_data, colWidths=[15 * mm, 72 * mm, 15 * mm, 72 * mm])
    def_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#dce3df")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.extend([def_table, Spacer(1, 3 * mm), Paragraph("结果按每克干重土壤在 3 h 内释放的 MUF（μmol 或 nmol）表达；鲜重、干重或单位土壤有机质只能选定一种口径，并在全部样品中保持一致。", styles["body"]), Spacer(1, 7 * mm)])

    story.append(heading("shield", "05", "质量控制", styles))
    qc = [
        "每样每酶 4 个平行，检查异常孔后报告平均值。",
        "每种土壤、每个稀释水平单独建立 MUF 标准曲线，校正荧光淬灭。",
        "底物和 MUF 标准临用现配、全程避光；各组培养时间必须严格一致。",
        "同一比较中保持缓冲液 pH、稀释倍数、培养温度和读板设置一致。",
        "正式测定前预检稀释倍数和底物浓度，确保信号落入标准曲线范围。",
        "同步测含水量并计算 W<sub>sd</sub>；解释结果时至少记录土壤 pH。",
    ]
    qc_data = []
    for index in range(0, len(qc), 2):
        qc_data.append([
            Paragraph(f"<font color='#0e684f'><b>{index + 1:02d}</b></font>　{qc[index]}", styles["body_small"]),
            Paragraph(f"<font color='#0e684f'><b>{index + 2:02d}</b></font>　{qc[index + 1]}", styles["body_small"]),
        ])
    qc_table = Table(qc_data, colWidths=[87 * mm, 87 * mm])
    qc_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, -1), 0.3, colors.HexColor("#ccd8d2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([qc_table, Spacer(1, 5 * mm), Paragraph("<b>方法边界：</b>本方案仅对应 MUF 荧光底物微孔板法中的碳循环水解酶；木质素相关氧化酶（如酚氧化酶、过氧化物酶）需采用另一套方法，不能直接套用本方案参数。", styles["body_small"])])
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def main() -> None:
    HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    HTML_PATH.write_text(build_html(), encoding="utf-8")
    build_pdf()
    print(HTML_PATH)
    print(PDF_PATH)


if __name__ == "__main__":
    main()

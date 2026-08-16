#!/usr/bin/env python3
"""Build the four additional, PDF-independent source corpora.

This is a build-time tool. The generated runtime data contains no paths to the
source PDFs and keeps every source under a distinct bookId.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader


SKILL_ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_ROOT = SKILL_ROOT / "references" / "external-corpora"
INDEX_ROOT = SKILL_ROOT / "references" / "index"

BOOKS = (
    {
        "bookId": "lu-rukkun-2000",
        "title": "土壤农业化学分析方法",
        "label": "鲁如坤《土壤农业化学分析方法》",
        "filename": "200004[M]-鲁如坤-土壤农业化学分析方法.pdf",
        "sha256": "af4d96488633e34e3f103aa3669b83257e13081c7aa56944aacf8eba118f9266",
        "pageCount": 665,
        "mode": "vision",
        "workKey": "lu-rukkun",
        "includedPages": list(range(1, 666)),
        "reviewStatus": "candidate",
    },
    {
        "bookId": "soil-analysis-spec-2e-2006",
        "title": "土壤分析技术规范（第二版）",
        "label": "《土壤分析技术规范》第2版",
        "filename": "200606[M]-土壤分析技术规范 第2版 (全国农业技术推广服务中心).pdf",
        "sha256": "eb41c75c0b04304b53b9f4e5823ddfa185bf34a8dcc49bbfc126bc2782b48d74",
        "pageCount": 267,
        "mode": "vision",
        "workKey": "technical-spec",
        "includedPages": list(range(1, 268)),
        "reviewStatus": "candidate",
    },
    {
        "bookId": "microbiome-protocol-1e-soil",
        "title": "微生物组学实验手册（第一版）—土壤相关方法选编",
        "label": "《微生物组学实验手册》第一版（土壤相关）",
        "filename": "liu yong xin微生物组学实验手册 （第一版）:Bio-protocol.pdf",
        "sha256": "2f1e675367dfdf738665b7ed6cea846e37e84f6417e9c021f8519a2a37ca58cf",
        "pageCount": 433,
        "mode": "native",
        "workKey": "microbiome",
        "includedPages": [
            *range(84, 91), *range(112, 122), *range(215, 226), *range(248, 256),
            *range(277, 283), *range(298, 303), *range(312, 324), *range(360, 366),
        ],
        "reviewStatus": "verified",
        "selectionRule": "仅纳入标题或完整方法对象直接涉及土壤、根际土、土壤线虫、土壤微生物或堆肥样品的8组方法。",
    },
    {
        "bookId": "gbz-170-2026",
        "title": "GB/Z 170—2026 土壤质量 土壤酶活性测定 荧光底物微孔板法",
        "label": "GB/Z 170—2026",
        "filename": "GBZ 170-2026 土壤质量 土壤酶活性测定 荧光底物微孔板法(1).pdf",
        "sha256": "c5275867b62cbf5f63f998c1088719869e118f135372c232806ddf3212154a78",
        "pageCount": 24,
        "mode": "native-gbz",
        "workKey": "gbz170",
        "includedPages": list(range(1, 25)),
        "reviewStatus": "verified",
    },
)

MICRO_METHODS = (
    ("11", "野外树木根系取样及根际土收集操作规程", 84, 90),
    ("14", "根系分泌物调控土壤微生物群落结构和功能的研究方法", 112, 121),
    ("22", "土壤宏转录组学样本前处理与数据分析", 215, 225),
    ("25", "土壤和水体环境T4型细菌病毒g23基因多样性研究", 248, 255),
    ("27", "土壤线虫群落DNA提取、扩增及高通量测序", 277, 282),
    ("30", "尾菜堆肥微生物组样品取样方法", 298, 302),
    ("32", "结构方程模型在土壤微生物生态学中的应用", 312, 323),
    ("35", "基于BIOLOG的微生物群落碳代谢功能分析", 360, 365),
)

MICRO_FORMULAS = {
    361: [
        {
            "label": "AWCD",
            "plain": "AWCD=Σ(A_i−A_A1)/95",
            "latex": r"\mathrm{AWCD}=\frac{\sum(A_i-A_{A1})}{95}",
            "definitions": {
                "A_i": "第i孔的相对吸光度",
                "A_A1": "A1孔的相对吸光度",
            },
        },
    ],
    362: [
        {
            "label": "Shannon指数",
            "plain": "H′=−ΣP_i·ln(P_i)",
            "latex": r"H'=-\sum P_i\ln(P_i)",
            "definitions": {"P_i": "第i孔相对吸光值占整个平板相对吸光值总和的比率"},
        },
        {
            "label": "Simpson指数（无穷大群落）",
            "plain": "D=1−Σ(P_i)²",
            "latex": r"D=1-\sum(P_i)^2",
            "definitions": {"P_i": "第i孔相对吸光值占整个平板相对吸光值总和的比率"},
        },
        {
            "label": "Simpson指数（有限群落）",
            "plain": "D=1−Σ[A_i(A_i−1)]/[N(N−1)]",
            "latex": r"D=1-\frac{\sum A_i(A_i-1)}{N(N-1)}",
            "definitions": {"A_i": "第i孔的相对吸光度", "N": "相对吸光值总和"},
        },
        {
            "label": "McIntosh多样性指数",
            "plain": "D=(N−U)/(N−√N)",
            "latex": r"D=\frac{N-U}{N-\sqrt{N}}",
            "definitions": {"N": "相对吸光值总和", "U": "McIntosh指数U"},
        },
        {
            "label": "McIntosh指数U",
            "plain": "U=√(Σn_i²)",
            "latex": r"U=\sqrt{\sum n_i^2}",
            "definitions": {"n_i": "第i孔的相对吸光值"},
        },
        {
            "label": "McIntosh均匀度",
            "plain": "E=(N−U)/(N−N/√S)",
            "latex": r"E=\frac{N-U}{N-N/\sqrt{S}}",
            "definitions": {"N": "相对吸光值总和", "S": "发生颜色变化的孔数", "U": "McIntosh指数U"},
        },
    ],
}

MICRO_PRECISION_TABLES = {
    361: {
        "number": "BIOLOG-关键参数",
        "title": "BIOLOG ECO微孔板培养与读数参数（原页逐项复核）",
        "columns": ["项目", "校正值"],
        "rows": [
            ["接种液", "10⁻³稀释液；每孔150 μL；每个土壤样品3次重复"],
            ["培养", "25 ℃；24、36、48、60、72、84、96、108、120、132、144 h"],
            ["读数波长", "750 nm和590 nm"],
        ],
    },
    365: {
        "number": "BIOLOG-磷酸缓冲液",
        "title": "磷酸缓冲液（pH 7.0）配方（原页逐项复核）",
        "columns": ["组分或条件", "校正值"],
        "rows": [
            ["KH₂PO₄", "2.65 g"],
            ["K₂HPO₄", "6.96 g"],
            ["定容", "蒸馏水定容至1 000 mL"],
            ["灭菌与保存", "121 ℃高压灭菌20 min；4 ℃保存"],
        ],
    },
}

GBZ_OUTLINE = (
    ("GB/Z 170—2026", "土壤质量 土壤酶活性测定 荧光底物微孔板法", 7),
    ("1", "范围", 7), ("2", "规范性引用文件", 7), ("3", "术语和定义", 7),
    ("4", "缩略语", 7), ("5", "原理", 8), ("6", "试剂", 8),
    ("6.1", "缓冲液", 8), ("6.2", "底物和标准溶液", 9),
    ("7", "仪器和材料", 10), ("8", "测定程序", 11), ("8.1", "采样", 11),
    ("8.2", "样品制备", 11), ("8.3", "培养", 12), ("8.4", "荧光测定", 12),
    ("9", "计算", 12), ("10", "结果的表达方式", 12), ("11", "测试报告", 13),
    ("A", "关于现测现配底物的使用指南", 14), ("B", "标准曲线示例", 16),
    ("NA", "常见酶的缩写", 18), ("NB", "计算与结果的表达", 19),
)

GBZ_FORMULA = {
    "label": "NB.1",
    "plain": "x=[(c_sa−c_b)×(V_sa+V_su+V_b)×V×1000]/(V_sa×m_sa×W_sd)",
    "latex": r"x=\frac{(c_{sa}-c_b)(V_{sa}+V_{su}+V_b)V\times1000}{V_{sa}m_{sa}W_{sd}}",
    "definitions": {
        "x": "土壤酶活性",
        "c_sa": "样品培养3 h后反应体系中MUF或AMC浓度，μmol/L",
        "c_b": "空白体系中MUF或AMC浓度，μmol/L",
        "V_sa": "加入反应体系的土壤悬浊液体积，μL",
        "V_su": "加入反应体系的底物溶液体积，μL",
        "V_b": "加入反应体系的缓冲液体积，μL",
        "V": "土壤悬浊液体积，L",
        "m_sa": "新鲜土壤质量，g",
        "W_sd": "土壤干重占湿土的比率",
        "1000": "换算系数",
    },
}

GBZ_TABLE_B1 = {
    "number": "B.1",
    "title": "MUF和AMC标准品的荧光强度测定结果",
    "columns": ["MUF浓度 (μmol/g)", "MUF荧光值", "AMC浓度 (μmol/g)", "AMC荧光值"],
    "rows": [
        [0, 9652, 0, 2807], [0, 9837, 0, 2771], [0, 9629, 0, 2918],
        [1, 12309, 0.10, 3185], [1, 13054, 0.10, 3188], [1, 12532, 0.10, 3223],
        [5, 29430, 0.50, 4224], [5, 27881, 0.50, 4496], [5, 29940, 0.50, 4375],
        [10, 50703, 1, 7091], [10, 53686, 1, 6671], [10, 54361, 1, 6892],
        [25, 112601, 5, 44442], [25, 128289, 5, 45015], [25, 128303, 5, 42234],
        [50, 240218, 10, 94225], [50, 241312, 10, 92720], [50, 239976, 10, 95688],
        [100, 342290, 25, 223674], [100, 421423, 25, 218396], [100, 416506, 25, 237820],
        [200, 676064, 50, 306714], [200, 692148, 50, 329967], [200, 665945, 50, 335326],
    ],
}

GBZ_TABLE_1 = {
    "number": "1",
    "title": "市售的用于酶活性测定的合成荧光底物",
    "columns": ["酶", "NC-IUBMB", "底物", "元素", "降解的大分子"],
    "rows": [
        ["芳基硫酸酯酶", "E.C. 3.1.6.1", "4-MUF-硫酸酯", "硫", "矿化有机硫"],
        ["α-葡萄糖苷酶", "E.C. 3.2.1.20", "4-MUF-α-D-吡喃葡萄糖苷", "碳", "淀粉和糖原"],
        ["纤维二糖酶", "E.C. 3.2.1.91", "4-MUF-β-纤维素二糖苷", "碳", "纤维素"],
        ["β-木糖苷酶", "E.C. 3.2.1.37", "4-MUF-β-D-吡喃木糖苷", "碳", "木聚糖、木二糖"],
        ["β-葡萄糖苷酶", "E.C. 3.2.1.21", "4-MUF-β-D-吡喃葡萄糖苷", "碳", "纤维素"],
        ["磷酸二酯酶（PDE）", "E.C. 3.1.4.1", "bis-(4-MUF)-phosphate", "磷", "水解磷酸二酯"],
        ["几丁质酶", "E.C. 3.2.1.52", "4-MUF-N-乙酰-β-D-氨基葡萄糖苷", "碳", "断裂聚N-乙酰-氨基葡萄糖苷（几丁质）和几丁二糖的β-1-4-糖苷键"],
        ["磷酸单酯酶（PME）", "E.C. 3.1.3.2", "4-MUF-磷酸酯", "磷", "磷酸盐单酯的水解"],
        ["亮氨酸氨基肽酶", "E.C. 3.4.11.1", "L-AMC-亮氨酸", "氮", "水解寡肽生成氨基酸"],
        ["丙氨酸氨基肽酶", "E.C. 3.4.11.2", "L-AMC-丙氨酸", "氮", "水解寡肽生成氨基酸"],
    ],
    "notes": ["MUF=4-甲基伞形酮", "AMC=7-氨基-4-甲基香豆素"],
}

GBZ_TABLE_NA1 = {
    "number": "NA.1",
    "title": "常见土壤水解酶名称、编码及缩写",
    "columns": ["酶的中文名称", "酶的英文名称", "IUBMB编码", "缩写"],
    "rows": [
        ["α-葡萄糖苷酶", "α-glucosidase", "E.C. 3.2.1.20", "AG"],
        ["β-葡萄糖苷酶", "β-glucosidase", "E.C. 3.2.1.21", "BG"],
        ["纤维二糖酶", "cellulose 1,4-β-cellobiosidase, cellobiohydrolase", "E.C. 3.2.1.91", "CBH"],
        ["β-木糖苷酶", "β-xylosidase", "E.C. 3.2.1.37", "BX"],
        ["几丁质酶，N-乙酰-β-氨基葡萄糖苷酶", "β-N-acetylglucosaminidase, chitinase", "E.C. 3.2.1.52", "NAG"],
        ["亮氨酸氨基肽酶", "leucyl aminopeptidase, leucine amino peptidase", "E.C. 3.4.11.1", "LAP"],
        ["丙氨酸氨基肽酶", "alanine amino peptidase", "E.C. 3.4.11.2", "AAP"],
        ["磷酸单酯酶（PME）", "phosphoric monoester hydrolase", "E.C. 3.1.3.2", "PME"],
        ["磷酸二酯酶（PDE）", "phosphodiesterase", "E.C. 3.1.4.1", "PDE"],
        ["芳基硫酸酯酶", "arylsulfatase", "E.C. 3.1.6.1", "AS"],
    ],
}

GBZ_PRECISION_PARAMETERS = {
    8: [
        ["乙酸钠缓冲液", "0.50 mol/L，pH 5.5；68.04 g乙酸钠三水化合物溶于800 mL去离子水，以冰乙酸（>99.8%）调pH，定容至1 000 mL；（121±3）℃灭菌20 min；冷藏最长2周"],
        ["MUB储备液", "1 mol/L NaOH：40.00 g定容至1 000 mL；另取12.10 g Tris、11.60 g马来酸、14.00 g柠檬酸、6.30 g硼酸，加488 mL上述NaOH并定容至1 000 mL"],
        ["MUB最终缓冲液", "取200 mL储备液，调至所需pH并定容至1 000 mL；（121±3）℃灭菌20 min"],
    ],
    9: [
        ["MUF标准液", "0.022 g 4-甲基伞形酮溶于DMSO，棕色容量瓶定容至25 mL；临用前配制"],
        ["AMC标准液", "0.022 g 7-氨基-4-甲基香豆素溶于DMSO，棕色容量瓶定容至25 mL；临用前配制"],
        ["底物储液", "可设为1 000 μmol/L、2 500 μmol/L或2 750 μmol/L；50 mL棕色容量瓶定容；临用前配制"],
    ],
    11: [
        ["微孔板荧光计", "激发波长355 nm；发射波长460 nm"],
        ["采样与保存", "野外20个样点混合过筛形成一个土壤样品；过筛样不宜冷藏，可在（−20±2）℃至少保存4个月"],
        ["均质化", "4 g供试样+120 mL缓冲液；9 600 r/min冰浴匀质3 min，调至200 mL（1∶50）；或50 J/s超声120 s"],
        ["常用稀释", "1∶100和1∶1 000；不同稀释水平不可直接比较"],
    ],
    12: [
        ["加样", "每孔200 μL土壤样品稀释液，每样4次重复；β-葡萄糖苷酶和磷酸单酯酶底物孔另加20 μL DMSO"],
        ["培养", "（30±2）℃振荡培养3 h，700次/min"],
        ["荧光测定", "加样后立即测定，培养3 h后再次测定；激发355 nm，发射460 nm"],
    ],
    15: [
        ["现配底物板", "1 g土壤+100 mL无菌去离子水；50 J/s超声120 s；每孔50 μL土壤悬浊液+50 μL缓冲液+100 μL底物；3～4次重复"],
        ["标准曲线孔终浓度", "0 μmol/L、0.50 μmol/L、1 μmol/L、2.50 μmol/L、4 μmol/L和6 μmol/L；总体积200 μL"],
    ],
}

# Page-scoped repairs are used only where the rendered source and dimensional
# check make the OCR (or a source misprint) unambiguous.  Keeping these fixes
# page-scoped prevents a legitimate formula elsewhere from being changed.
SCAN_PAGE_REPLACEMENTS: dict[tuple[str, int], dict[str, str]] = {
    ("lu-rukkun-2000", 567): {
        "S-—在10-{mol·L-4与10-4mol·L⁻¹NH₄Cl标准溶液中实测的氨电极斜率。":
            "S——在10⁻³ mol·L⁻¹与10⁻⁴ mol·L⁻¹ NH₄Cl标准溶液中实测的氨电极斜率。",
    },
    ("lu-rukkun-2000", 625): {
        "[ρ(N)=100mg·L⁻¹：": "[ρ(N)=100 mg·L⁻¹]：",
        "ρ（N）=100mg·L⁻¹NO₃-N": "ρ(NO₃⁻-N)=100 mg·L⁻¹",
        "2mg·": "2 mg·",
        "1.1、4mg·L⁻¹": "L⁻¹、4 mg·L⁻¹",
        "10-6—由mg转换为g及将mL换算成I.的因数。": "10⁻⁶——由mg转换为g及将mL换算成L的因数。",
    },
    ("lu-rukkun-2000", 626): {
        "H₃CH5O·H₂O": "H₃C₆H₅O₇·H₂O",
        "H₂SO4": "H₂SO₄",
        "ρ(Mo）=25g·L⁻¹": "ρ(Mo)=25 g·L⁻¹",
        "(NH4)6MoO24·4HO": "(NH₄)₆Mo₇O₂₄·4H₂O",
        "[ρ（P₂O5）=10mg·L⁻¹：": "[ρ(P₂O₅)=10 mg·L⁻¹]：",
        "45C烘": "45 ℃烘",
        "含P2O10μg～50μg": "含P₂O₅ 10 μg～50 μg",
        "ρ(P₂O）=10mg·L⁻¹": "ρ(P₂O₅)=10 mg·L⁻¹",
        "ω(P₂Os)=ρ×V×ts×10⁻⁸": "ω(P₂O₅)=ρ×V×ts×10⁻⁶",
        "ω（P₂O）—试样含P₂5质量分数": "ω(P₂O₅)——试样中P₂O₅质量分数",
        "mg·mL⁻¹": "mg·L⁻¹",
    },
    ("lu-rukkun-2000", 627): {
        "c(NaOH）=2mol·L⁻¹": "c(NaOH)=2 mol·L⁻¹",
        "{ρNaB（CHs)4]=30g·L⁻¹}": "[ρ(NaB(C₆H₅)₄)=30 g·L⁻¹]",
        "氧化钾（K2O）": "氧化钾（K₂O）",
        "10-6——将mg换算成g及将mL换算成I的系数": "10⁻⁶——将mg换算成g及将mL换算成L的系数",
    },
}

SCAN_PAGE_DROP_LINES: dict[tuple[str, int], set[str]] = {
    ("lu-rukkun-2000", 625): {"72"},
    ("lu-rukkun-2000", 626): {"2m"},
    ("lu-rukkun-2000", 627): {"−"},
}


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_hash(record: dict[str, Any]) -> str:
    content = {key: record.get(key) for key in ("blocks", "formulas", "tables")}
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def vision_path(directory: Path, page: int) -> Path:
    candidates = [
        directory / f"page-{page:04d}.json",
        directory / f"page-{page:03d}.json",
        directory / f"page-{page:02d}.json",
        directory / f"page-{page}.json",
    ]
    return next((path for path in candidates if path.is_file()), candidates[0])


def image_path(directory: Path, page: int) -> Path | None:
    for suffix in ("jpg", "png"):
        for width in (4, 3, 2, 0):
            number = f"{page:0{width}d}" if width else str(page)
            path = directory / f"page-{number}.{suffix}"
            if path.is_file():
                return path
    return None


def clean_vision_line(text: str, gbz: bool = False) -> str:
    text = text.strip()
    # Conservative corrections shared by the two scanned monographs and the
    # scanned standard.  These are restricted to stable OCR confusions seen in
    # the rendered pages; analytical values are never inferred here.
    shared_replacements = {
        "士壤": "土壤", "土壞": "土壤", "土壊": "土壤",
        "土壞": "土壤", "士样": "土样", "取士": "取土",
        "砂士": "砂土", "黏士": "黏土", "壤士": "壤土",
        "湿士": "湿土", "风干士": "风干土", "士粒": "土粒",
        "加人": "加入", "放人": "放入", "移人": "移入",
        "插人": "插入", "并人": "并入", "倒人": "倒入", "转人": "转入",
        "范團": "范围", "范圃": "范围", "冷帮": "冷却",
        "镂态氮": "铵态氮", "镂态": "铵态", "重铭酸": "重铬酸",
        "测土配方施肥": "测土配方施肥", "溯定": "测定",
        "HCI": "HCl", "KCI": "KCl", "HCIO₄": "HClO₄", "HCIO4": "HClO₄",
        "HC1": "HCl", "KC1": "KCl", "NaC1": "NaCl",
        "NaCI": "NaCl", "NH₄CI": "NH₄Cl", "CaCI₂": "CaCl₂",
        "BaCL₂": "BaCl₂", "BaCL2": "BaCl₂", "CaCL₂": "CaCl₂",
        "C1₂HgN₂": "C₁₂H₈N₂", "C12HgN2": "C₁₂H₈N₂",
        "（NH4）₂（SO4）₂·6H₂O": "（NH₄）₂（SO₄）₂·6H₂O",
        "(NH4)₂(SO4)₂·6H₂O": "(NH₄)₂(SO₄)₂·6H₂O",
        "K2Cr2O，": "K₂Cr₂O₇，", "K2Cr2O7": "K₂Cr₂O₇",
        "重铬酸钾一硫酸": "重铬酸钾-硫酸",
    }
    for old, new in shared_replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\bPH\b", "pH", text)
    text = re.sub(r"(?<![A-Za-z])mmo1(?=\s*[·（(])", "mmol", text)
    text = re.sub(r"(?<![A-Za-z])cmo1(?=\s*·)", "cmol", text)
    text = re.sub(r"(?<![A-Za-z])mo[Il1](?=\s*·)", "mol", text)
    text = re.sub(r"(?<==)[Il](?=\s*mol\b)", "1", text)
    text = re.sub(r"(?<=mL)[lI](?=mol)", " 1", text)
    text = re.sub(r"(?<=\d\.)[Il](?=mol)", "1", text)
    text = text.replace("•", "·")
    text = text.replace("g·cm³", "g·cm⁻³")
    text = re.sub(
        r"C(?:₁?[o0₀]|1[o0]|10|0)H(?:₁?4|14|₁₄)O?[g8₈]N₂Na(?:₂|2|z)?·2H₂O",
        "C₁₀H₁₄O₈N₂Na₂·2H₂O",
        text,
    )
    text = text.replace("NH4C1", "NH₄Cl").replace("NH₄C1", "NH₄Cl")
    text = text.replace("HONH₃C1", "HONH₃Cl").replace("AgC1", "AgCl")
    text = text.replace("C1-", "Cl⁻").replace("C1⁻", "Cl⁻")
    text = text.replace("无C1", "无Cl⁻").replace("有C1存在", "有Cl⁻存在")
    text = text.replace("mmo1(C1-)", "mmol(Cl⁻)").replace("mmo1（C1-）", "mmol（Cl⁻）")
    text = text.replace("H₂SO）=0.02", "H₂SO₄）=0.02")
    text = text.replace("CO₂2，mmo1($CO₃-)", "CO₃²⁻，mmol(1/2CO₃²⁻)")
    text = text.replace("AI-P", "Al-P").replace("P、AI、Si", "P、Al、Si")
    text = text.replace("对A1的", "对Al的").replace("Superflocl27", "Superfloc127")
    text = text.replace("H₂SO4o", "H₂SO₄。").replace("H₂SO₄o", "H₂SO₄。")
    text = re.sub(r"(?<=\d)O(?=(?:min|mL)\b)", "0", text)
    text = re.sub(r"(?<=\d)\s*(?:ml|mI)\.?(?=[^A-Za-z]|$)", " mL", text)
    text = re.sub(r"^mI(?=[，,.;；])", "mL", text)
    text = re.sub(r"(?<=\d)\s*(?:ul|uL|pL|yL)(?=[^A-Za-z]|$)", " μL", text)
    text = re.sub(r"(?<=\d)\s*μ[lL](?=[^A-Za-z]|$)", " μL", text)
    text = re.sub(r"(?<=\d)\s*(?:ug|pg|yg|wg)(?=(?:\s|·|/|mL|L|kg|g|$))", " μg", text)
    text = re.sub(r"(?<=\d)\s*(?:umol|pmol|ymol|wmol)(?=(?:\s|·|/|L|$))", " μmol", text)
    text = re.sub(
        r"(?<![A-Za-z])(mol|mmol|μmol|nmol|g|mg|μg|ng)(L|mL|kg)\s*[-−—一~～]\s*1(?=[^0-9A-Za-z]|$)",
        r"\1·\2⁻¹",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])(mol|mmol|μmol|nmol)·[LI]\s*[-−]\s*1(?=\d)",
        r"\1·L⁻¹ ",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])(mol|mmol|μmol|nmol)·[LI]\s*[-−]\s*1(?=c\s*[\(（\[])",
        r"\1·L⁻¹ ",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])(mol|mmol|μmol|nmol)·[LI]\s*[-−]\s*\](?=[^0-9A-Za-z]|$)",
        r"\1·L⁻¹]",
        text,
    )
    # Enzyme-activity units on Lu Rukun p.277 and p.280 lose both the
    # reciprocal kg exponent and the middle dot before h.  The printed unit
    # is mg·kg⁻¹·h⁻¹ in both places.
    text = re.sub(
        r"(?<![A-Za-z])(g|mg|μg|ng)·kg(?:[-−—一~～]?h[-−—一~～]1|h−1)(?=[^0-9A-Za-z]|$)",
        r"\1·kg⁻¹·h⁻¹",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])(g|mg|μg|ng)·kg-d(?=[^0-9A-Za-z]|$)",
        r"\1·kg⁻¹·d⁻¹",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])(g|mg|μg|ng)·kgh(?=[^0-9A-Za-z]|$)",
        r"\1·kg⁻¹·h⁻¹",
        text,
    )
    # On Lu Rukun p.233–234 the range separator is repeatedly fused to the
    # reciprocal exponent (for example, ``mg·kg一1000`` and
    # ``mg·I-1一20``).  A following multi-digit value makes these cases
    # unambiguous: restore both the exponent and the printed range separator.
    text = re.sub(
        r"(?<![A-Za-z])(g|mg|μg|ng)·kg一(?=\d{3,})",
        r"\1·kg⁻¹～",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])(g|mg|μg|ng)·[LI]\s*[-−]\s*1[一—](?=\d)",
        r"\1·L⁻¹～",
        text,
    )
    # The 0.6 mol·L⁻¹ HCl sentence on p.234 is split by OCR exactly
    # after ``mol·``; the next line therefore starts with the tail ``I-1中``.
    text = re.sub(r"^I-1中", "L⁻¹]中", text)
    # Concentration and content units have a fixed reciprocal denominator.
    # Normalize only complete mass/amount-per-volume or mass-per-mass tokens;
    # this also repairs I/l for L and the frequent OCR readings −2, −], or a
    # dropped exponent.  Existing Unicode superscripts are explicitly left
    # untouched.
    text = re.sub(
        r"(?<![A-Za-z])(g|mg|μg|ng)·kg\s*[−-]1(?=[^0-9A-Za-z]|$)",
        lambda match: f"{match.group(1)}·kg⁻¹",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])(mol|mmol|μmol|nmol|g|mg|μg|ng)·[LI](?:\s*[-−—一~～]\s*(?:[12Il\]²])?|[1Il²])?(?![⁻⁰¹²³⁴⁵⁶⁷⁸⁹−—一-])(?=[A-Zmα-ω（(]|[^0-9A-Za-z]|$)",
        lambda match: f"{match.group(1)}·L⁻¹",
        text,
    )
    text = re.sub(
        r"(?<![A-Za-z])(g|mg|μg|ng)·kg(?:\s*[-−—一~～]\s*(?:[12Il\]²])?|[1Il²T™])?(?:['’])?(?![⁻⁰¹²³⁴⁵⁶⁷⁸⁹−—一-])(?=[A-Zmα-ω（(]|[^0-9A-Za-z]|$)",
        lambda match: f"{match.group(1)}·kg⁻¹",
        text,
    )
    # Normalize the negative-one exponent only when it follows a denominator
    # unit.  OCR variants include L-', L~', L一1, and L.-’.
    text = re.sub(
        r"\b(L|kg|min|cm|mL)\s*[.·]?\s*[-—一~～]?\s*[1lI'’\"]{1,2}(?=[A-Zα-ω（(]|[^0-9A-Za-z]|$)",
        r"\1⁻¹",
        text,
    )
    text = re.sub(r"\b(cm)\s*[.·]?\s*[-—一~～]?\s*[3'’](?=[^0-9A-Za-z]|$)", r"\1⁻³", text)
    text = re.sub(
        r"(?<![A-Za-z])(mol|mmol|μmol|nmol|g|mg|μg)·(L|mL|kg)\s*[.·]?\s*[-—一~～](?=[A-Zp]|[^0-9A-Za-z]|$)",
        r"\1·\2⁻¹",
        text,
    )
    # In molar-concentration units the scan OCR sometimes reads L as I and
    # the superscript −1 as -2, -], or drops the final 1.  These variants are
    # unambiguous after mol· and are normalized only in that exact context.
    text = re.sub(
        r"(?<![A-Za-z])(mol|mmol|μmol|nmol)·[LI]\s*(?:[-—一~～]\s*[12Il\]]?|[12Il])(?=[^0-9A-Za-z]|$)",
        r"\1·L⁻¹",
        text,
    )
    text = re.sub(r"(?<![A-Za-z])r·min\s*[.·]?\s*[-—一~～](?=[^0-9A-Za-z]|$)", "r·min⁻¹", text)
    text = re.sub(r"(?<![A-Za-z])g·cm\s*[.·]?\s*[-—一~～](?=[^0-9A-Za-z]|$)", "g·cm⁻³", text)
    text = re.sub(r"(?<=g·mL)[-−—一~～][²2](?=[^0-9A-Za-z]|$)", "⁻¹", text)
    text = re.sub(r"(?<=\d)I(?=[，。；;、）)\]】］]|$)", " L", text)
    text = re.sub(r"(?<![A-Za-z])(mol|mmol|μmol|nmol|g|mg|μg)·(L|mL|kg)(?=[\s,.;；，。:：）)\]】］]|$)", r"\1·\2⁻¹", text)
    text = re.sub(r"(?<![A-Za-z])r·min(?=[\s,.;；，。:：）)\]】］]|$)", "r·min⁻¹", text)
    text = re.sub(r"(?<![A-Za-z])g·cm(?=[\s,.;；，。:：）)\]】］]|$)", "g·cm⁻³", text)
    text = re.sub(r"(?<=\d)士(?=\d)", "±", text)
    text = re.sub(r"(?<=\d)土(?=\d)", "±", text)
    text = re.sub(r"(?<=h)士(?=\d)", "±", text)
    text = re.sub(r"(?<=°C)士(?=\d)", "±", text)
    text = re.sub(r"(?<=℃)士(?=\d)", "±", text)
    text = re.sub(r"(?<=⁻¹)士(?=\d)", "±", text)
    text = re.sub(r"(?<![A-Za-z])(min|h|℃|°C)[土士](?=\d)", r"\1±", text)
    text = re.sub(r"(?<![A-Za-z])(mol|mmol|μmol|nmol)·L-(?=\d+\s*mL)", r"\1·L⁻¹ ", text)
    text = re.sub(r"(?<=⁻¹)[\"'’]", "", text)
    text = re.sub(r"(?<=\d)~(?=\d)", "～", text)
    superscript = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    text = re.sub(
        r"10[-−](\d)(?=(?:\s|的|稀释|倍|～|~|至|$))",
        lambda match: "10⁻" + match.group(1).translate(superscript),
        text,
    )
    text = re.sub(
        r"(?<=\d)\s*[×x]\s*10(\d)(?=(?:\s|CFU|cfu|个|$))",
        lambda match: "×10" + match.group(1).translate(superscript),
        text,
    )
    text = re.sub(r"(?<=/)ml\b", "mL", text, flags=re.IGNORECASE)
    text = text.replace("°C", "℃")
    if not gbz:
        return text
    if any(marker in text for marker in ("订单号：", "防伪编号：", "购买单位：", "禾木科技工作室", "禾木科技T作室", "2026-0630-0224-3945-5574")):
        return ""
    if any(marker in text for marker in ("TYwtY", "1-La-0XU", "VaXns XWa")):
        return ""
    if text in {"室", "工作", "科技", "禾木", "专用", "5574"}:
        return ""
    replacements = {
        "悬独液": "悬浊液",
        "PH": "pH", "ml.": "mL", "∞-葡萄糖": "α-葡萄糖", "a-葡萄糖": "α-葡萄糖",
        "B-葡萄糖": "β-葡萄糖", "B-木糖": "β-木糖", "土壤醯活性": "土壤酶活性",
        "（B-glucosidase）": "（β-glucosidase）",
        "(B-glucosidase)": "(β-glucosidase)",
        "（a-glucosidase）": "（α-glucosidase）",
        "(a-glucosidase)": "(α-glucosidase)",
        "（B-xylosidase）": "（β-xylosidase）",
        "(B-xylosidase)": "(β-xylosidase)",
        "cel- lubisidase": "cellobiosidase",
        "cel-lubisidase": "cellobiosidase",
        "GB/7.": "GB/Z ", "GB/7": "GB/Z", "底物浓度力": "底物浓度为",
        "B-葡糖苷酶": "β-葡萄糖苷酶", "μuL": "μL", "umol/L": "μmol/L",
        "酶活性z按公式": "酶活性x按公式",
        "激发波长设定沩855 nm": "激发波长设定为355 nm",
        "形成二个土壤样品": "形成一个土壤样品",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"(?<=\d)\s*[ypw]mol(?=/|[^A-Za-z]|$)", " μmol", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\d)\s*[ypw]L(?=[^A-Za-z]|$)", " μL", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\d)\s*ml\.?(?=[^A-Za-z]|$)", " mL", text, flags=re.IGNORECASE)
    text = text.replace("4-MUF-B-", "4-MUF-β-").replace("4-MUF-B\n", "4-MUF-β\n")
    return text


def vision_page(work: Path, page: int, gbz: bool = False) -> tuple[list[dict[str, Any]], str]:
    path = vision_path(work / "vision", page)
    payload = json.loads(path.read_text(encoding="utf-8"))
    blocks: list[dict[str, Any]] = []
    for line in payload.get("lines", []):
        text = clean_vision_line(str(line.get("text") or ""), gbz=gbz)
        if not text:
            continue
        blocks.append(
            {
                "type": "line",
                "text": text,
                "confidence": round(float(line.get("confidence", 0.0)), 6),
                "alternatives": line.get("alternatives") or [],
            }
        )
    return blocks, "\n".join(block["text"] for block in blocks)


def paddle_page(work: Path, page: int, gbz: bool = False) -> tuple[list[dict[str, Any]], str] | None:
    path = vision_path(work / "paddle", page)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    engine = str(payload.get("engine") or "PaddleOCR")
    blocks: list[dict[str, Any]] = []
    for line in payload.get("lines", []):
        text = clean_vision_line(str(line.get("text") or ""), gbz=gbz)
        if not text:
            continue
        blocks.append({
            "type": "line",
            "text": text,
            "confidence": round(float(line.get("confidence", 0.0)), 6),
            "box": line.get("box") or [],
            "engine": engine,
        })
    return blocks, "\n".join(block["text"] for block in blocks)


def native_page(reader: PdfReader, page: int, gbz: bool = False) -> tuple[list[dict[str, Any]], str]:
    """Read an exact embedded text layer; OCR engines remain comparison evidence."""
    extracted = reader.pages[page - 1].extract_text() or ""
    blocks: list[dict[str, Any]] = []
    footer_patterns = (
        "订单号：", "防伪编号：", "购买单位:", "购买单位：", "禾木科技工作室 专用",
    )
    for raw in extracted.splitlines():
        text = raw.strip()
        if not text:
            continue
        if gbz and any(token in text for token in footer_patterns):
            continue
        # The GB/Z text layer contains artificial tracking spaces inserted
        # between Chinese glyphs. They are layout artifacts, not source words.
        text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
        text = re.sub(r"\s+([，。；：、！？）】])", r"\1", text)
        text = re.sub(r"([（【])\s+", r"\1", text)
        blocks.append({"type": "native-pdf-line", "text": text})
    return blocks, "\n".join(block["text"] for block in blocks)


def scan_formula_candidates(
    work: Path,
    page: int,
    review: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    path = vision_path(work / "formula", page)
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    formulas: list[dict[str, Any]] = []
    seen_verified_latex: set[str] = set()
    for index, item in enumerate(payload.get("formulas") or [], 1):
        latex = str(item.get("rec_formula") or "").strip()
        if len(latex) < 9:
            continue
        label = f"P{page}-F{index}"
        forced = work.name == "lu-rukkun" and label in {"P633-F3", "P643-F3"}
        if not forced and not any(marker in latex for marker in ("=", r"\approx", r"\geq", r"\leq")):
            continue
        latex = latex.replace(r"\bullet", r"\cdot").replace(r"\mathrm{m o l}", r"\mathrm{mol}")
        latex = latex.replace(r"\mathrm{m L}", r"\mathrm{mL}").replace(r"\mathrm{mL^{-1}}", r"\mathrm{mL}^{-1}")
        latex = re.sub(r"\\mu\s+g", r"\\mu\\mathrm{g}", latex)
        source_fingerprint = hashlib.sha256(
            json.dumps(
                {"latex": latex, "region": item.get("dt_polys") or []},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        verified = (review or {}).get(label) or {}
        rejected = (
            verified.get("status") == "rejected"
            and verified.get("sourceFingerprint") == source_fingerprint
        )
        if rejected:
            continue
        accepted = (
            verified.get("status") == "verified"
            and verified.get("sourceFingerprint") == source_fingerprint
        )
        final_latex = str(verified.get("latex") or latex) if accepted else latex
        if final_latex in seen_verified_latex:
            continue
        seen_verified_latex.add(final_latex)
        formula = {
            "label": label,
            "latex": final_latex,
            "region": item.get("dt_polys") or [],
            "engine": payload.get("engine"),
            "sourceFingerprint": source_fingerprint,
            "reviewStatus": "verified" if accepted else "candidate",
        }
        if accepted:
            if verified.get("plain"):
                formula["plain"] = str(verified["plain"])
            if verified.get("label"):
                formula["label"] = str(verified["label"])
            formula["reviewMethod"] = str(verified.get("reviewMethod") or "公式裁剪图逐项目视复核")
        formulas.append(formula)
    return formulas


def formula_review(book_id: str) -> dict[str, dict[str, Any]]:
    path = EXTERNAL_ROOT / book_id / "formula-review.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = [*(payload.get("formulas") or []), *(payload.get("rejected") or [])]
    return {
        str(item["id"]): item
        for item in rows
        if isinstance(item, dict) and item.get("id")
    }


def effective_review_status(book: dict[str, Any]) -> str:
    if book["reviewStatus"] == "verified":
        return "verified"
    path = EXTERNAL_ROOT / book["bookId"] / "scan-review.json"
    if not path.is_file():
        return str(book["reviewStatus"])
    gate = json.loads(path.read_text(encoding="utf-8"))
    if (
        gate.get("status") == "verified"
        and gate.get("bookId") == book["bookId"]
        and gate.get("sourcePdfSha256") == book["sha256"]
        and int(gate.get("pageCount", 0)) == int(book["pageCount"])
        and gate.get("textPass") == "verified"
        and gate.get("precisionPass") == "verified"
        and gate.get("secondVisualPass") == "verified"
    ):
        return "verified"
    return str(book["reviewStatus"])


def apply_scan_page_repairs(
    book_id: str,
    page: int,
    blocks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    replacements = SCAN_PAGE_REPLACEMENTS.get((book_id, page)) or {}
    drop_lines = SCAN_PAGE_DROP_LINES.get((book_id, page)) or set()
    if not replacements:
        return blocks, "\n".join(str(block.get("text") or "") for block in blocks)
    repaired: list[dict[str, Any]] = []
    for block in blocks:
        item = dict(block)
        text = str(item.get("text") or "")
        if text.strip() in drop_lines:
            continue
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = re.sub(r"(?<![A-Za-z])mI(?=[^A-Za-z]|$)", "mL", text)
        item["text"] = text.strip()
        if item["text"]:
            repaired.append(item)
    return repaired, "\n".join(str(block["text"]) for block in repaired)


def outline_from_pdf(reader: PdfReader) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    def walk(items: list[Any], depth: int = 0) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item, depth + 1)
                continue
            try:
                page = reader.get_destination_page_number(item) + 1
            except Exception:
                page = None
            if page:
                rows.append({"title": str(getattr(item, "title", item)), "page": page, "depth": depth})
    walk(reader.outline)
    return rows


def manual_outline(book_id: str) -> list[dict[str, Any]]:
    if book_id == "microbiome-protocol-1e-soil":
        return [
            {"title": f"{number}. {title}", "page": start, "endPage": end, "depth": 1}
            for number, title, start, end in MICRO_METHODS
        ]
    if book_id == "gbz-170-2026":
        rows = []
        for number, title, page in GBZ_OUTLINE:
            depth = 0 if number.startswith("GB/Z") else 2 if "." in number else 1
            rows.append({"title": f"{number} {title}", "page": page, "depth": depth})
        return rows
    return []


def normalize_outline(book_id: str, outline: list[dict[str, Any]]) -> None:
    """Keep chapter hierarchy separate from Lu Rukun bookmark authors.

    The PDF bookmarks encode a chapter title and its credited author(s) as
    ``第…章  标题&作者``.  The ampersand is a bookmark field separator,
    not part of the printed chapter title.  Preserve the names as metadata but
    do not let them leak into the method hierarchy or search title.
    """
    if book_id != "lu-rukkun-2000":
        return
    for row in outline:
        raw = str(row.get("title") or "")
        is_chapter = raw.startswith("第") and "章" in raw
        is_appendix = raw.startswith("附录")
        if not ((is_chapter or is_appendix) and "&" in raw):
            continue
        title, authors = raw.rsplit("&", 1)
        names = [item.strip() for item in re.split(r"\s{2,}", authors.strip()) if item.strip()]
        if not title.strip() or not names:
            continue
        row["title"] = title.rstrip()
        row["authors"] = names


def add_end_pages(outline: list[dict[str, Any]], last_page: int) -> None:
    for index, row in enumerate(outline):
        if row.get("endPage"):
            continue
        end = last_page
        for later in outline[index + 1:]:
            if int(later["depth"]) <= int(row["depth"]):
                end = max(int(row["page"]), int(later["page"]) - 1)
                break
        row["endPage"] = end


def method_cards(book: dict[str, Any], outline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    active: dict[int, str] = {}
    for index, row in enumerate(outline):
        depth = int(row["depth"])
        active[depth] = str(row["title"])
        for old in [item for item in active if item > depth]:
            del active[old]
        title = str(row["title"])
        is_numbered = bool(re.match(r"^(?:\d+(?:\.\d+)*|[A-Z]{1,2}|GB/Z\s+\d+)", title))
        is_chapter = "章" in title and title.startswith("第")
        if not (is_numbered or is_chapter):
            continue
        cards.append(
            {
                "id": f"ext-{book['bookId']}-{index + 1:04d}",
                "bookId": book["bookId"],
                "sourceLabel": book["label"],
                "kind": "chapter" if is_chapter else "method",
                "title": title,
                "path": [active[item] for item in sorted(active)],
                "startPage": int(row["page"]),
                "endPage": int(row["endPage"]),
                **({"authors": row["authors"]} if row.get("authors") else {}),
            }
        )
    return cards


def build_book(book: dict[str, Any], source_root: Path, work_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = source_root / book["filename"]
    if sha256(source) != book["sha256"]:
        raise ValueError(f"SHA-256不匹配: {source}")
    reader = PdfReader(source)
    if len(reader.pages) != book["pageCount"]:
        raise ValueError(f"页数不匹配: {source}")
    work = work_root / book["workKey"]
    outline = manual_outline(book["bookId"]) or outline_from_pdf(reader)
    normalize_outline(book["bookId"], outline)
    add_end_pages(outline, book["pageCount"])
    reviewed_formulas = formula_review(book["bookId"])
    review_status = effective_review_status(book)

    records: list[dict[str, Any]] = []
    for page in book["includedPages"]:
        if str(book["mode"]).startswith("native"):
            blocks, text = native_page(reader, page, gbz=book["mode"] == "native-gbz")
        else:
            paddle = paddle_page(work, page)
            if paddle is not None:
                blocks, text = paddle
            else:
                blocks, text = vision_page(work, page)
            blocks, text = apply_scan_page_repairs(book["bookId"], page, blocks)
        formulas: list[dict[str, Any]] = []
        tables: list[dict[str, Any]] = []
        if book["bookId"] in {"lu-rukkun-2000", "soil-analysis-spec-2e-2006"}:
            formulas.extend(scan_formula_candidates(work, page, reviewed_formulas))
        if book["bookId"] == "microbiome-protocol-1e-soil":
            formulas.extend(MICRO_FORMULAS.get(page, []))
            if page in MICRO_PRECISION_TABLES:
                tables.append(MICRO_PRECISION_TABLES[page])
        if book["bookId"] == "gbz-170-2026" and page == 19:
            formulas.append(GBZ_FORMULA)
        if book["bookId"] == "gbz-170-2026" and page == 16:
            tables.append(GBZ_TABLE_B1)
        if book["bookId"] == "gbz-170-2026" and page == 10:
            tables.append(GBZ_TABLE_1)
        if book["bookId"] == "gbz-170-2026" and page == 18:
            tables.append(GBZ_TABLE_NA1)
        if book["bookId"] == "gbz-170-2026" and page in GBZ_PRECISION_PARAMETERS:
            tables.append(
                {
                    "number": f"精度复核-P{page}",
                    "title": "关键试剂与操作参数（逐项对照原页）",
                    "columns": ["项目", "原页校正值"],
                    "rows": GBZ_PRECISION_PARAMETERS[page],
                }
            )
        image = image_path(work / "images", page)
        status = review_status
        record: dict[str, Any] = {
            "schema": "soil-methods-consultant.external-page.v1",
            "bookId": book["bookId"],
            "page": page,
            "sourcePdfSha256": book["sha256"],
            "sourceImageSha256": sha256(image) if image else None,
            "blocks": blocks,
            "formulas": formulas,
            "tables": tables,
            "review": {
                "textPass": {"status": status, "method": "数字文本层+页面渲染复核" if str(book["mode"]).startswith("native") else "Apple Vision+PaddleOCR+Tesseract逐页对照候选"},
                "precisionPass": {"status": status, "method": "公式、单位和表格结构化核对" if status == "verified" else "待多引擎差异复核"},
                "secondVisualPass": {"status": status, "method": "页面渲染复核" if status == "verified" else "待第二遍视觉复核"},
            },
        }
        record["contentSha256"] = content_hash(record)
        records.append(record)

    output = EXTERNAL_ROOT / book["bookId"]
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "soil-methods-consultant.external-corpus.v1",
        "bookId": book["bookId"],
        "title": book["title"],
        "label": book["label"],
        "sourcePdfSha256": book["sha256"],
        "sourcePageCount": book["pageCount"],
        "includedPages": book["includedPages"],
        "includedPageCount": len(book["includedPages"]),
        "runtimeReady": review_status == "verified",
        "selectionRule": book.get("selectionRule", "整本纳入"),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "outline.json").write_text(json.dumps(outline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary = output / "pages.json.gz.tmp"
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=9) as stream:
        json.dump({"bookId": book["bookId"], "pages": records}, stream, ensure_ascii=False, separators=(",", ":"))
    os.replace(temporary, output / "pages.json.gz")
    return manifest, method_cards(book, outline)


def main() -> None:
    config = args()
    EXTERNAL_ROOT.mkdir(parents=True, exist_ok=True)
    manifests: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    for book in BOOKS:
        manifest, book_cards = build_book(book, config.source_root, config.work_root)
        manifests.append(manifest)
        cards.extend(book_cards)
        print(f"{book['bookId']}: pages={manifest['includedPageCount']} cards={len(book_cards)} ready={manifest['runtimeReady']}")
    payload = {
        "schema": "soil-methods-consultant.external-method-cards.v1",
        "sources": manifests,
        "cardCount": len(cards),
        "cards": cards,
    }
    temporary = INDEX_ROOT / "external-method-cards.json.gz.tmp"
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=9) as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
    os.replace(temporary, INDEX_ROOT / "external-method-cards.json.gz")
    print(f"external cards: {len(cards)}")


if __name__ == "__main__":
    main()

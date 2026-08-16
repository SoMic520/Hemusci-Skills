#!/usr/bin/env python3
"""Deterministic runtime regressions for the corrected soil-method corpus."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import find_methods as search
import generate_report
from corrected_corpus import CORRECTED_DIR, load_corrected_page, render_corrected_page


REQUIRED_PAGES = {1: 557, 2: 358}
REQUIRED_GATES = ("textPass", "precisionPass", "secondVisualPass")
REQUIRED_EXTERNAL_PAGES = {
    "lu-rukkun-2000": 665,
    "soil-analysis-spec-2e-2006": 267,
    "microbiome-protocol-1e-soil": 65,
    "gbz-170-2026": 24,
}
REQUIRED_SAMR_PAGES = {
    "samr-gb-t-44343-2024": 15,
    "samr-gb-t-44615-2024": 19,
    "samr-gb-t-34765-2024": 15,
    "samr-gb-t-44741-2024": 11,
    "samr-gb-t-31270-16-2025": 15,
    "samr-gb-t-31270-22-2025": 15,
    "samr-gb-t-31270-4-2025": 27,
    "samr-gb-t-31270-5-2025": 19,
    "samr-gb-t-31270-1-2025": 23,
    "samr-gb-t-47215-2026": 15,
    "samr-gb-t-47305-2026": 19,
    "samr-gb-t-47310-2026": 15,
    "samr-gb-t-47293-2026": 11,
    "samr-gb-t-47297-2026": 19,
    "samr-gb-t-47361-2026": 11,
    "samr-gb-t-47437-2026": 15,
    "samr-gb-t-22105-1-2026": 15,
    "samr-gb-t-22105-2-2026": 15,
    "samr-gb-t-22105-3-2026": 15,
}


def canonical_hash(record: dict[str, Any]) -> str:
    content = {key: record.get(key) for key in ("blocks", "formulas", "tables")}
    encoded = json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def rank(query: str, top: int = 5) -> list[dict[str, Any]]:
    concepts = search.query_concepts(query)
    results: list[dict[str, Any]] = []
    for card in search.load_method_cards():
        page_text = "\n".join(str(page.get("text") or "") for page in card.get("pages", []))
        headings = [
            *card.get("path", []),
            *(component.get("title", "") for component in card.get("components", [])),
        ]
        score = search.score_page(query, concepts, page_text, headings)
        title = search.normalize(str(card.get("title") or ""))
        path = search.normalize(" ".join(card.get("path", [])))
        for concept in concepts:
            normalized = search.normalize(concept)
            if normalized and normalized in title:
                score += 90
            elif normalized and normalized in path:
                score += 30
        if card.get("kind") == "method":
            score += 45
        results.append({"score": score, **card})
    return sorted(
        results,
        key=lambda item: (-item["score"], item["volume"], item["startPage"]),
    )[:top]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def external_pages(book_id: str) -> list[dict[str, Any]]:
    path = search.EXTERNAL_ROOT / book_id / "pages.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return list(json.load(stream).get("pages") or [])


def samr_pages(book_id: str) -> list[dict[str, Any]]:
    return list(search.load_external_page_map(book_id).values())


def main() -> None:
    status = search.load_corpus_status()
    check(status.get("runtimeReady") is True, "runtimeReady 尚未开启")
    check(status.get("verifiedPages") == 915, "状态文件页数不是 915")

    verified = 0
    for volume, page_count in REQUIRED_PAGES.items():
        for page in range(1, page_count + 1):
            record = load_corrected_page(volume, page)
            check(record.get("bookId") == f"volume-{volume}", f"册次错误: {volume}:{page}")
            check(record.get("page") == page, f"页码错误: {volume}:{page}")
            check(record.get("contentSha256") == canonical_hash(record), f"哈希错误: {volume}:{page}")
            for gate in REQUIRED_GATES:
                check(
                    (record.get("review") or {}).get(gate, {}).get("status") == "verified",
                    f"复核门未通过: {volume}:{page}:{gate}",
                )
            verified += 1
    check(verified == 915, "最终校正页数量不完整")

    external = search.load_external_payload()
    sources = {source["bookId"]: source for source in external.get("sources") or []}
    check(set(sources) == set(REQUIRED_EXTERNAL_PAGES), "四份新增来源不完整或发生串源")
    check(all(source.get("runtimeReady") is True for source in sources.values()), "四份新增来源尚未全部就绪")
    check(
        sum(int(source.get("includedPageCount", 0)) for source in sources.values()) == 1021,
        "四份新增来源纳入页数不是1021",
    )
    check(verified + 1021 == 1936, "六套语料总纳入页数不是1936")

    for book_id, required_count in REQUIRED_EXTERNAL_PAGES.items():
        pages = external_pages(book_id)
        check(len(pages) == required_count, f"新增来源页数错误: {book_id}")
        for record in pages:
            check(record.get("bookId") == book_id, f"新增来源串源: {book_id}:{record.get('page')}")
            check(record.get("contentSha256") == canonical_hash(record), f"新增来源哈希错误: {book_id}:{record.get('page')}")
            for gate in REQUIRED_GATES:
                check(
                    (record.get("review") or {}).get(gate, {}).get("status") == "verified",
                    f"新增来源复核门未通过: {book_id}:{record.get('page')}:{gate}",
                )

    external_cards = list(external.get("cards") or [])
    check(int(external.get("cardCount", -1)) == len(external_cards), "新增方法卡计数错误")
    check(
        all(card.get("bookId") in REQUIRED_EXTERNAL_PAGES for card in external_cards),
        "新增方法卡出现未知或混合来源",
    )

    samr = search.load_samr_payload()
    samr_sources = {source["bookId"]: source for source in samr.get("sources") or []}
    check(set(samr_sources) == set(REQUIRED_SAMR_PAGES), "SAMR已构建来源不是预期19份")
    check(int(samr.get("expectedSourceCount", 0)) == 25, "SAMR应纳入标准数不是25")
    check(len(samr.get("missingSources") or []) == 6, "SAMR未取得官方全文数不是6")
    check(all(source.get("runtimeReady") is True for source in samr_sources.values()), "SAMR 19份语料未全部启用")
    check(
        sum(int(source.get("includedPageCount", 0)) for source in samr_sources.values()) == 309,
        "SAMR已启用页数不是309",
    )
    check(
        {source["standardNo"] for source in samr.get("missingSources") or []}
        == {
            "GB/T 8574-2024",
            "GB/T 22924-2024",
            "GB/T 46293-2025",
            "GB/T 46742-2025",
            "GB/T 19203-2026",
            "GB/T 47386-2026",
        },
        "SAMR未激活标准集合变化",
    )
    check(verified + 1021 + 309 == 2245, "当前运行时总纳入页数不是2245")
    for book_id, required_count in REQUIRED_SAMR_PAGES.items():
        pages = samr_pages(book_id)
        check(len(pages) == required_count, f"SAMR页数错误: {book_id}")
        gate_path = search.SAMR_ROOT / book_id / "review-gate.json"
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        check(gate.get("status") == "verified", f"SAMR审计门未通过: {book_id}")
        check(
            gate.get("sourceFingerprint") == samr_sources[book_id].get("sourceFingerprint"),
            f"SAMR审计门源指纹不匹配: {book_id}",
        )
        for record in pages:
            check(record.get("bookId") == book_id, f"SAMR串源: {book_id}:{record.get('page')}")
            check(record.get("contentSha256") == canonical_hash(record), f"SAMR哈希错误: {book_id}:{record.get('page')}")
            for gate_name in REQUIRED_GATES:
                check(
                    (record.get("review") or {}).get(gate_name, {}).get("status") == "verified",
                    f"SAMR页级复核门未通过: {book_id}:{record.get('page')}:{gate_name}",
                )

    samr_cards = list(samr.get("cards") or [])
    check(len(samr_cards) == 19 and int(samr.get("cardCount", -1)) == 19, "SAMR方法卡数不是19")
    for card in samr_cards:
        components = card.get("components") or []
        top = [int(value["number"]) for value in components if "." not in value["number"]]
        check(top == list(range(1, max(top) + 1)), f"SAMR一级层级不连续: {card['bookId']}")
        numbers = {value["number"] for value in components}
        check(
            all("." not in value["number"] or value["number"].rsplit(".", 1)[0] in numbers for value in components),
            f"SAMR方法层级缺父级: {card['bookId']}",
        )

    samr_47215 = {int(page["page"]): page for page in samr_pages("samr-gb-t-47215-2026")}
    check(
        samr_47215[11]["formulas"][0]["plain"]
        == "F = ρ₁ × 10⁻⁶ × 60 × [10⁴ / (π × r²)] × 6",
        "GB/T 47215氨挥发公式的上下标或指数回归失败",
    )
    check(
        any("kg/(hm²·d)" in block["text"] for block in samr_47215[11]["blocks"]),
        "GB/T 47215氨挥发量单位回归失败",
    )
    samr_47361 = {int(page["page"]): page for page in samr_pages("samr-gb-t-47361-2026")}
    check(
        samr_47361[9]["formulas"][0]["plain"]
        == "w_{OM} = {[(c × 5.00) / V₀] × (V₀ − V) × 0.003 × 1.724 × 1.1 / m} × 1 000",
        "GB/T 47361土壤有机质公式回归失败",
    )
    samr_47437 = {int(page["page"]): page for page in samr_pages("samr-gb-t-47437-2026")}
    check(
        samr_47437[10]["formulas"][0]["plain"].startswith("δ¹⁸O_{SA−ST}"),
        "GB/T 47437氧同位素上标回归失败",
    )
    lu_cards = [card for card in external_cards if card.get("bookId") == "lu-rukkun-2000"]
    check(
        all(
            "&" not in str(card.get("title") or "")
            and all("&" not in str(item) for item in card.get("path", []))
            for card in lu_cards
        ),
        "鲁如坤书签中的作者分隔符混入方法层级",
    )
    check(
        any(card.get("authors") == ["鲁如坤"] for card in lu_cards if card.get("kind") == "chapter"),
        "鲁如坤章节作者元数据未保留",
    )

    with gzip.open(search.METHOD_CARDS, "rt", encoding="utf-8") as stream:
        cards = json.load(stream)
    check(cards.get("source", "").startswith("verified corrected"), "方法卡不是由校正版生成")
    check(cards.get("stats", {}).get("methodCardCount") == 389, "方法卡数量变化")
    sample_card = next(item for item in cards["cards"] if item["id"] == "v2-s0116")
    for page in sample_card["pages"]:
        expected = render_corrected_page(load_corrected_page(2, int(page["page"])))
        check(page["text"] == expected, "方法卡正文与校正版不一致")

    p100 = load_corrected_page(1, 100)
    check(
        p100["formulas"][0]["plain"]
        == "mg P/kg土壤=μg P（样品中）×[50 mL（提取体积）/mL（实际测定体积）]×[1/g（土壤）]",
        "第100页公式或单位回归失败",
    )
    p338 = load_corrected_page(2, 338)
    check(p338["tables"][0]["columns"] == ["X (m)", "K_s (cm·h⁻¹)", "Sa (wt%)"], "表85.2单位回归失败")
    check(len(p338["tables"][0]["rows"]) == 128, "表85.2不是128行")

    micro = {int(page["page"]): page for page in external_pages("microbiome-protocol-1e-soil")}
    check(micro[361]["formulas"][0]["plain"] == "AWCD=Σ(A_i−A_A1)/95", "微生物手册AWCD公式回归失败")
    check(
        micro[365]["tables"][0]["rows"][0:2] == [["KH₂PO₄", "2.65 g"], ["K₂HPO₄", "6.96 g"]],
        "微生物手册磷酸缓冲液配方回归失败",
    )
    gbz = {int(page["page"]): page for page in external_pages("gbz-170-2026")}
    check("定容至25 mL" in gbz[9]["tables"][0]["rows"][0][1], "GB/Z 170 MUF标准液体积回归失败")
    check(
        gbz[19]["formulas"][0]["plain"]
        == "x=[(c_sa−c_b)×(V_sa+V_su+V_b)×V×1000]/(V_sa×m_sa×W_sd)",
        "GB/Z 170 NB.1公式回归失败",
    )
    lu = {int(page["page"]): page for page in external_pages("lu-rukkun-2000")}
    check(
        any(formula.get("plain") == "ρ(SO₄²⁻)=1000 mg·L⁻¹" for formula in lu[168].get("formulas", [])),
        "鲁如坤第168页硫酸根标准液原书量纲误印未校正",
    )
    check(
        any(formula.get("plain") == "ω(NaOCl)=5.25%" for formula in lu[186].get("formulas", [])),
        "鲁如坤第186页次氯酸钠下标回归失败",
    )
    check(
        any(formula.get("plain") == "F⁻(mg·g⁻¹)=G(V₁/V₂)/m" for formula in lu[570].get("formulas", [])),
        "鲁如坤第570页氟含量公式回归失败",
    )
    check(
        any(formula.get("plain") == "m/e=R²H²/(2V)" for formula in lu[577].get("formulas", [])),
        "鲁如坤第577页质谱基本方程回归失败",
    )
    check(
        any(
            formula.get("plain")
            == "石灰性土：Mehlich 3-P=−0.431+2.72(Olsen-P)；非石灰性土：Mehlich 3-P=0.591+1.42(Olsen-P)"
            for formula in lu[603].get("formulas", [])
        ),
        "鲁如坤第603页Mehlich 3-P转换方程回归失败",
    )
    check(
        any(formula.get("plain") == "ρ(K)=4000 mg·L⁻¹" for formula in lu[620].get("formulas", [])),
        "鲁如坤第620页钾标准液单位回归失败",
    )
    check(
        any(
            formula.get("plain") == "ρ(KNaC₄H₄O₆·4H₂O)=400 g·L⁻¹"
            for formula in lu[622].get("formulas", [])
        ),
        "鲁如坤第622页酒石酸钾钠化学式回归失败",
    )
    check(
        any(formula.get("plain") == "ω(P₂O₅)=ρV·ts×10⁻⁶/m×100" for formula in lu[626].get("formulas", [])),
        "鲁如坤第626页有效磷公式指数回归失败",
    )
    lu626_text = "\n".join(str(block.get("text") or "") for block in lu[626].get("blocks", []))
    check("(NH₄)₆Mo₇O₂₄·4H₂O" in lu626_text, "鲁如坤第626页钼酸铵化学式回归失败")
    check("mg·mL⁻¹" not in lu626_text and "mg·L⁻¹" in lu626_text, "鲁如坤第626页显色液浓度单位未校正")
    check(
        any(formula.get("plain", "").startswith("S=√{[0.48²+0.37²") for formula in lu[633].get("formulas", [])),
        "鲁如坤第633页样本标准差公式层级回归失败",
    )
    technical = {int(page["page"]): page for page in external_pages("soil-analysis-spec-2e-2006")}
    check(
        any(formula.get("plain") == "ρ(K)=100 mg·L⁻¹" for formula in technical[221].get("formulas", [])),
        "土壤分析技术规范第221页钾标准液公式回归失败",
    )

    aggregate_ids = {item["id"] for item in rank("土壤团聚体怎么测定", 5)}
    check(
        bool(aggregate_ids & {"v2-s0112", "v2-s0116", "v2-s0121", "v2-s0129"}),
        "团聚体咨询未返回湿筛或干筛方法",
    )
    check(rank("阳离子交换量", 1)[0]["id"] == "v1-s0292", "CEC首条方法回归失败")
    check(rank("微生物量碳熏蒸提取法", 1)[0]["id"] == "v1-s0874", "微生物量碳首条方法回归失败")

    report_card, report_pages = generate_report.load_card("samr-gb-t-47305-2026-method")
    report_html = generate_report.build_html(
        report_card,
        report_pages,
        "土壤有效硼怎么测定",
        False,
    )
    for label in (
        "方法适用性与选择依据",
        "标准操作规程",
        "结果计算、单位与判定",
    ):
        check(label in report_html, f"报告缺少必需模块: {label}")
    check("来源、版本与复核信息" not in report_html, "报告仍包含已取消的来源信息专节")
    check('<section class="page cover"' not in report_html, "报告不应包含独立封面")
    check("校正语料直接生成" not in report_html, "报告仍显示内部生成说明")
    check("页码 / 方法卡 / 指纹" not in report_html, "报告仍显示内部追踪汇总行")
    check("校正语料生成" not in report_html, "报告仍显示内部生成标记")
    check(report_html.count("<svg") >= 8, "报告图标数不足")
    check("@media print" in report_html and "@media(max-width:900px)" in report_html, "报告缺少打印或响应式样式")
    check('--sans:"PingFang SC","Noto Sans CJK SC","Source Han Sans SC"' in report_html, "正文未使用标准化中文无衬线字体栈")
    check('--serif:"Songti SC","Noto Serif CJK SC","Source Han Serif SC"' in report_html, "标题未使用标准化中文衬线字体栈")
    check('--math:"STIX Two Math","Cambria Math"' in report_html, "公式未使用数学字体栈")
    check(".step-detail p{display:grid" in report_html and "font-family:var(--sans)" in report_html, "步骤正文字体未标准化")
    check('grid-template-areas:"rail content"' in report_html, "报告未锁定编号栏与正文栏位置")
    check('id="appendix"' not in report_html, "简要实验方案不应默认附带校正原文")
    check("校正原文与页码对照" not in report_html, "简要实验方案仍显示校正原文标题")
    source_report_html = generate_report.build_html(report_card, report_pages, "土壤有效硼怎么测定", True)
    check('id="appendix"' in source_report_html, "明确要求校正页文时未生成附录")
    check(".appendix .section-content{grid-column:1/-1" in source_report_html, "可选校正原文未使用通栏布局")
    check("grid-template-columns:66px minmax(0,1fr)" in report_html, "公式释义列缺少宽度保护")
    check(".step-detail p>span{grid-column:2" in report_html, "无编号操作行未锁定到正文列")
    check(".step-detail p>small{grid-column:3" in report_html, "步骤页码未锁定到页码列")
    check("\ufffd" not in report_html and "(cid:" not in report_html, "报告含乱码或内部字形编码")
    for formula in generate_report.extract_formulas(report_pages):
        check(formula["plain"] in report_html, f"报告公式字符回归失败: {formula['label']}")

    print("regressions: PASS")
    print("verified pages: 915")
    print("method cards: 389")
    print("external included pages: 1021")
    print("SAMR ready standards: 19/25 (309 pages)")
    print("combined included pages: 2245")


if __name__ == "__main__":
    main()

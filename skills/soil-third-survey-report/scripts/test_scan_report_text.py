#!/usr/bin/env python3
"""Regression tests for scan_report_text.py."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).with_name("scan_report_text.py")
SPEC = importlib.util.spec_from_file_location("scan_report_text", SCRIPT)
assert SPEC and SPEC.loader
SCAN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SCAN
SPEC.loader.exec_module(SCAN)


DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <w:body>
  <w:p><w:r><w:t>封面普通文字</w:t></w:r></w:p>
  <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>第一章 正文</w:t></w:r></w:p>
  <w:p><w:r><w:t>正文分析段落包含明确数据10.00%。</w:t></w:r></w:p>
  <w:p><w:r><w:t>（表5.32）</w:t></w:r></w:p>
  <w:tbl><w:tr><w:tc><w:p><w:r><w:t>统计口径</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
  <w:p>
   <w:r><w:t>P</w:t></w:r>
   <w:r><w:rPr><w:vertAlign w:val="subscript"/></w:rPr><w:t>2</w:t></w:r>
   <w:r><w:t>O</w:t></w:r>
   <w:r><w:rPr><w:vertAlign w:val="subscript"/></w:rPr><w:t>5</w:t></w:r>
   <w:r><w:t>。</w:t></w:r>
  </w:p>
  <w:p><w:r><w:t>P2O5。</w:t></w:r></w:p>
  <w:p>
   <w:r><w:t>Ca</w:t></w:r>
   <w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>2+</w:t></w:r>
   <w:r><w:t>。</w:t></w:r>
  </w:p>
  <w:p><w:r><w:t>Ca2+。</w:t></w:r></w:p>
  <w:p><w:r><w:t>体积为m</w:t></w:r><w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>3</w:t></w:r><w:r><w:t>。</w:t></w:r></w:p>
  <w:p><w:r><w:t>体积为m3。</w:t></w:r></w:p>
  <w:p><w:r><w:t>面积为12.00亩，另一区域为12.00万亩。</w:t></w:r></w:p>
  <w:p><w:r><w:t>盐渍化面积为10亩。</w:t></w:r></w:p>
  <w:p><w:hyperlink r:id="rId9"><w:r><w:t>DeepSeek隐藏链接</w:t></w:r></w:hyperlink></w:p>
  <w:p><w:moveFrom><w:r><w:t>旧句</w:t></w:r></w:moveFrom><w:moveTo><w:r><w:t>新句</w:t></w:r></w:moveTo></w:p>
  <w:p><w:r><w:drawing><w:txbxContent><w:p><w:r><w:t>文本框口径</w:t></w:r></w:p></w:txbxContent></w:drawing></w:r></w:p>
  <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>附件</w:t></w:r></w:p>
  <w:p><w:r><w:t>附件文字不计入正文。</w:t></w:r></w:p>
  <w:sectPr/>
 </w:body>
</w:document>
"""

STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>
</w:styles>
"""

RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
  Target="https://chat.deepseek.com/hidden" TargetMode="External"/>
</Relationships>
"""

COMMENTS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:comment w:id="0"><w:p><w:r><w:t>建议修改该句，但不要写需要验证。</w:t></w:r></w:p></w:comment>
</w:comments>
"""

HEADER_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
 <w:p><w:r><w:t>页眉口径</w:t></w:r></w:p>
</w:hdr>
"""


def build_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", DOCUMENT_XML)
        archive.writestr("word/styles.xml", STYLES_XML)
        archive.writestr("word/_rels/document.xml.rels", RELS_XML)
        archive.writestr("word/comments.xml", COMMENTS_XML)
        archive.writestr("word/header1.xml", HEADER_XML)


class ScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="soil-report-scan-test-")
        self.docx = Path(self.temp.name) / "fixture.docx"
        build_docx(self.docx)
        self.paragraphs, self.stats = SCAN.read_docx(self.docx)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_table_text_is_scanned(self) -> None:
        findings, _ = SCAN.scan(self.paragraphs, 300, 1000, "unknown")
        table_hits = [item for item in findings if item.match == "口径" and "table" in item.location]
        self.assertEqual(len(table_hits), 1)
        self.assertIn("table", table_hits[0].location)

    def test_header_and_textbox_are_scanned_with_locations(self) -> None:
        findings, _ = SCAN.scan(self.paragraphs, 300, 1000, "unknown")
        locations = {item.match: item.location for item in findings if item.match == "口径"}
        self.assertEqual(locations["口径"], "header")
        textbox_hits = [p for p in self.paragraphs if p.raw_text == "文本框口径"]
        self.assertEqual(len(textbox_hits), 1)
        self.assertIn("textbox", textbox_hits[0].location)

    def test_comment_editorial_language_is_not_misclassified_as_body_text(self) -> None:
        findings, _ = SCAN.scan(self.paragraphs, 300, 1000, "unknown")
        comment_editorial = [
            item for item in findings
            if item.location.startswith("comment") and item.category == "editorial_instruction"
        ]
        self.assertFalse(comment_editorial)
        self.assertTrue(any(
            item.location.startswith("comment") and item.category == "validation_caveat"
            for item in findings
        ))

    def test_run_level_subscript_avoids_false_positive(self) -> None:
        chemical_paragraphs = [p for p in self.paragraphs if p.raw_text == "P2O5。"]
        self.assertEqual(len(chemical_paragraphs), 2)
        proper, plain = chemical_paragraphs
        proper_hits = SCAN.rich_unit_findings(proper)
        plain_hits = SCAN.rich_unit_findings(plain)
        self.assertFalse(any(item.category == "plain_chemical_subscript" for item in proper_hits))
        self.assertTrue(any(item.category == "plain_chemical_subscript" for item in plain_hits))

    def test_superscript_ions_and_units_use_run_properties(self) -> None:
        calcium = [p for p in self.paragraphs if p.raw_text == "Ca2+。"]
        volume = [p for p in self.paragraphs if p.raw_text == "体积为m3。"]
        self.assertEqual(len(calcium), 2)
        self.assertEqual(len(volume), 2)
        self.assertFalse(SCAN.rich_unit_findings(calcium[0]))
        self.assertTrue(any(item.category == "plain_chemical_subscript" for item in SCAN.rich_unit_findings(calcium[1])))
        self.assertFalse(SCAN.rich_unit_findings(volume[0]))
        self.assertTrue(any(item.category == "plain_unit_exponent" for item in SCAN.rich_unit_findings(volume[1])))

    def test_mu_and_wanmu_precision_are_distinguished(self) -> None:
        findings, _ = SCAN.scan(self.paragraphs, 300, 1000, "unknown")
        hits = [item.match for item in findings if item.category == "mu_requires_integer"]
        self.assertEqual(hits, ["12.00亩"])

    def test_salinization_defaults_to_unknown(self) -> None:
        unknown, _ = SCAN.scan(self.paragraphs, 300, 1000, "unknown")
        absent, _ = SCAN.scan(self.paragraphs, 300, 1000, "absent")
        self.assertFalse(any(item.category == "unexpected_salinization" for item in unknown))
        self.assertTrue(any(item.category == "unexpected_salinization" for item in absent))

    def test_standalone_figure_table_reference_is_flagged(self) -> None:
        findings, _ = SCAN.scan(self.paragraphs, 300, 1000, "unknown")
        hits = [item for item in findings if item.category == "table_figure_shell"]
        self.assertTrue(any(item.match == "（表5.32）" for item in hits))

    def test_move_from_is_excluded_and_move_to_is_included(self) -> None:
        moved = [p for p in self.paragraphs if p.raw_text == "新句"]
        self.assertEqual(len(moved), 1)
        self.assertNotIn("旧句", "".join(p.raw_text for p in self.paragraphs))

    def test_external_relationship_maps_anchor(self) -> None:
        relationships = self.stats["external_relationships"]
        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0]["target"], "https://chat.deepseek.com/hidden")
        self.assertIn("DeepSeek隐藏链接", relationships[0]["anchors"])

    def test_body_count_excludes_cover_table_and_attachment(self) -> None:
        body, info = SCAN.select_body_paragraphs(self.paragraphs)
        joined = "".join(p.raw_text for p in body)
        self.assertTrue(info["reliable"])
        self.assertNotIn("封面", joined)
        self.assertNotIn("统计口径", joined)
        self.assertNotIn("附件文字", joined)
        self.assertIn("正文分析段落", joined)


if __name__ == "__main__":
    unittest.main()

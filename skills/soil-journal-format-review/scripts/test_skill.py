#!/usr/bin/env python3
"""Adversarial regression tests for the format-only DOCX toolchain."""

from __future__ import annotations

import hashlib
import csv
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from add_format_comments import add_comments, verify_comments  # noqa: E402
from audit_docx_fonts import audit as audit_fonts  # noqa: E402
from apply_docx_format import _section_hash, _table_structure_hash, apply_format, qn  # noqa: E402
from audit_docx_notes import audit_notes  # noqa: E402
from compare_docx_content import GuardError, compare_documents  # noqa: E402
from check_toolchain import inspect_toolchain  # noqa: E402
from install_open_fonts import git_blob_sha1  # noqa: E402
from ooxml_safety import PackageSafetyError, read_docx_package, sha256_file  # noqa: E402
from inspect_docx import inspect as inspect_docx  # noqa: E402
from render_docx import _prepare_output  # noqa: E402
from scope_policy import validate_format_only_payload  # noqa: E402
from validate_findings import validate_findings_payload  # noqa: E402
from validate_format_review_bundle import validate_bundle  # noqa: E402
from validate_journal_profile import validate_profile  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def document_xml(body: str, namespaces: str = "") -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}" xmlns:r="{R}" {namespaces}><w:body>{body}'
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
        '</w:body></w:document>'
    ).encode()


def make_docx(
    path: Path,
    document: bytes,
    *,
    extras: dict[str, bytes] | None = None,
    document_rels: bytes | None = None,
    compression: int = zipfile.ZIP_STORED,
) -> None:
    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''.encode()
    root_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{PR}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>'''.encode()
    document_rels = document_rels or f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{PR}"/>'''.encode()
    with zipfile.ZipFile(path, "w", compression=compression) as package:
        package.writestr("[Content_Types].xml", content_types)
        package.writestr("_rels/.rels", root_rels)
        package.writestr("word/document.xml", document)
        package.writestr("word/_rels/document.xml.rels", document_rels)
        for name, data in (extras or {}).items():
            package.writestr(name, data)


def rewrite_parts(source: Path, target: Path, replacements: dict[str, bytes]) -> None:
    with zipfile.ZipFile(source) as source_package, zipfile.ZipFile(target, "w") as output:
        written = set()
        for info in source_package.infolist():
            output.writestr(info, replacements.get(info.filename, source_package.read(info.filename)))
            written.add(info.filename)
        for name, data in replacements.items():
            if name not in written:
                output.writestr(name, data)


def valid_profile() -> dict:
    rule_specs = (
        ("PAGE-001", "PAGE_LAYOUT"),
        ("TITLE-001", "TITLE_BLOCK"),
        ("TABLE-001", "TABLE_LAYOUT"),
        ("NOTE-001", "FOOTNOTE_ENDNOTE_LAYOUT"),
    )
    return {
        "schema_version": "2.0",
        "journal": {
            "name": "Example Soil Journal",
            "article_type": "Article",
            "submission_stage": "initial",
            "language": "zh-CN",
            "accessed_at": "2026-08-15",
            "official_domain": "example.org",
            "publisher": "Example Publisher",
        },
        "scope_statement": "FORMAT_ONLY，只审查排版与投稿形式，不审查论文质量或科学内容。",
        "rules": [
            {
                "rule_id": rule_id,
                "category": category,
                "requirement": f"Exact format rule {rule_id}",
                "applies_to": "main_manuscript",
                "article_type": "Article",
                "source_title": "Official author guide",
                "source_url": "https://example.org/guide",
                "source_locator": f"Section {index}",
                "source_kind": "official_journal_guide",
                "source_sha256": "0" * 64,
                "source_snapshot": "source.html",
                "accessed_at": "2026-08-15",
                "verification_status": "VERIFIED",
                "automation": "AUTO_FIX",
                "notes": "",
            }
            for index, (rule_id, category) in enumerate(rule_specs, start=1)
        ],
    }


class SkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = tempfile.TemporaryDirectory(prefix="soil-format-skill-test-")
        self.temp = Path(self.context.name)
        footnotes = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="{W}">
<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
<w:footnote w:id="1"><w:p><w:r><w:t>Footnote format text</w:t></w:r></w:p></w:footnote>
</w:footnotes>'''.encode()
        body = (
            '<w:p><w:r><w:t>Soil title</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Content 1.25 mg kg-1.</w:t></w:r><w:r><w:footnoteReference w:id="1"/></w:r></w:p>'
            '<w:tbl><w:tblPr/><w:tr><w:tc><w:p><w:r><w:t>Table value 7</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
        )
        self.source = self.temp / "source.docx"
        make_docx(self.source, document_xml(body), extras={"word/footnotes.xml": footnotes})
        self.profile_path = self.temp / "profile.json"
        self.profile_path.write_text(json.dumps(valid_profile(), ensure_ascii=False), encoding="utf-8")

    def tearDown(self) -> None:
        self.context.cleanup()

    def _valid_plan(self) -> dict:
        parts, _, _ = read_docx_package(self.source)
        root = ET.fromstring(parts["word/document.xml"])
        paragraphs = list(root.iter(qn("p")))
        table = next(root.iter(qn("tbl")))
        section = next(root.iter(qn("sectPr")))
        return {
            "schema_version": "2.0",
            "scope": "FORMAT_ONLY",
            "source_document_sha256": sha256_file(self.source),
            "journal_profile_sha256": sha256_file(self.profile_path),
            "operations": [
                {
                    "operation_id": "OP-SECTION",
                    "rule_id": "PAGE-001",
                    "op": "section",
                    "story": "document",
                    "section_index": 0,
                    "expected_structure_sha256": _section_hash(section),
                    "risk_class": "SAFE_TYPOGRAPHY",
                    "properties": {"margin_left_twips": 1800},
                },
                {
                    "operation_id": "OP-TITLE",
                    "rule_id": "TITLE-001",
                    "op": "paragraph",
                    "story": "document",
                    "paragraph_index": 0,
                    "expected_text_sha256": text_hash("Soil title"),
                    "risk_class": "SAFE_TYPOGRAPHY",
                    "properties": {"alignment": "center", "keep_with_next": True},
                },
                {
                    "operation_id": "OP-RUN",
                    "rule_id": "TITLE-001",
                    "op": "run",
                    "story": "document",
                    "paragraph_index": 0,
                    "run_index": "all",
                    "expected_text_sha256": text_hash("Soil title"),
                    "risk_class": "SAFE_TYPOGRAPHY",
                    "properties": {"font_ascii": "Times New Roman", "font_size_half_points": 28},
                },
                {
                    "operation_id": "OP-TABLE",
                    "rule_id": "TABLE-001",
                    "op": "table",
                    "story": "document",
                    "table_index": 0,
                    "expected_structure_sha256": _table_structure_hash(table),
                    "risk_class": "SAFE_TYPOGRAPHY",
                    "properties": {"alignment": "center", "repeat_first_row": True},
                },
                {
                    "operation_id": "OP-NOTE",
                    "rule_id": "NOTE-001",
                    "op": "paragraph",
                    "story": "footnotes",
                    "note_id": "1",
                    "paragraph_index": 0,
                    "expected_text_sha256": text_hash("Footnote format text"),
                    "risk_class": "SAFE_TYPOGRAPHY",
                    "properties": {"spacing_after_twips": 120},
                },
            ],
        }

    def test_end_to_end_format_and_document_and_note_comments(self) -> None:
        plan_path = self.temp / "plan.json"
        plan_path.write_text(json.dumps(self._valid_plan()), encoding="utf-8")
        clean = self.temp / "clean.docx"
        receipt = apply_format(self.source, plan_path, self.profile_path, clean)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(compare_documents(self.source, clean)["status"], "PASS")
        note_audit = audit_notes(clean)
        self.assertEqual(note_audit["status"], "PASS")

        findings = {
            "schema_version": "2.0",
            "document": clean.name,
            "scope": "FORMAT_ONLY",
            "profile_sha256": sha256_file(self.profile_path),
            "source_document_sha256": sha256_file(clean),
            "findings": [
                {
                    "issue_id": "CMT-TITLE",
                    "story": "document",
                    "note_id": None,
                    "paragraph_index": 0,
                    "location": "Title",
                    "category": "TITLE_BLOCK",
                    "rule_id": "TITLE-001",
                    "current_format": "Title spacing differs from the rule",
                    "required_format": "Use the cited title spacing",
                    "action": "COMMENT",
                    "status": "COMMENTED",
                    "scope": "FORMAT_ONLY",
                    "expected_text_sha256": text_hash("Soil title"),
                },
                {
                    "issue_id": "CMT-NOTE",
                    "story": "footnotes",
                    "note_id": "1",
                    "paragraph_index": 0,
                    "location": "Footnote 1",
                    "category": "FOOTNOTE_ENDNOTE_LAYOUT",
                    "rule_id": "NOTE-001",
                    "current_format": "Footnote spacing differs from the rule",
                    "required_format": "Use the cited footnote spacing",
                    "action": "COMMENT",
                    "status": "COMMENTED",
                    "scope": "FORMAT_ONLY",
                    "expected_text_sha256": text_hash("Footnote format text"),
                },
            ],
        }
        findings_path = self.temp / "findings.json"
        findings_path.write_text(json.dumps(findings, ensure_ascii=False), encoding="utf-8")
        annotated = self.temp / "annotated.docx"
        result = add_comments(clean, findings_path, self.profile_path, annotated, "排版审查", "FR")
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["native_word_review_required"])
        self.assertTrue(verify_comments(annotated)["valid"])
        self.assertEqual(compare_documents(clean, annotated, allow_comment_additions=True)["status"], "PASS")

    def test_guard_rejects_semantic_and_package_tampering(self) -> None:
        cases = {}
        parts, _, _ = read_docx_package(self.source)

        footnote_remap = parts["word/document.xml"].replace(b'w:id="1"', b'w:id="2"')
        cases["footnote remap"] = {"word/document.xml": footnote_remap}

        field_source = self.temp / "field-source.docx"
        field_changed = self.temp / "field-changed.docx"
        prefix = '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText>'
        suffix = '</w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
        make_docx(field_source, document_xml(prefix + " REF A " + suffix))
        make_docx(field_changed, document_xml(prefix + " REF B " + suffix))
        self.assertEqual(compare_documents(field_source, field_changed)["status"], "FAIL")

        revision_source = self.temp / "revision-source.docx"
        revision_changed = self.temp / "revision-changed.docx"
        make_docx(revision_source, document_xml('<w:p><w:ins w:id="7" w:author="A"><w:r><w:t>Visible</w:t></w:r></w:ins></w:p>'))
        make_docx(revision_changed, document_xml('<w:p><w:r><w:t>Visible</w:t></w:r></w:p>'))
        self.assertEqual(compare_documents(revision_source, revision_changed)["status"], "FAIL")

        math_source = self.temp / "math-source.docx"
        math_changed = self.temp / "math-changed.docx"
        ns = f'xmlns:m="{M}"'
        fraction = '<w:p><m:oMath><m:f><m:num><m:r><m:t>x</m:t></m:r></m:num><m:den><m:r><m:t>y</m:t></m:r></m:den></m:f></m:oMath></w:p>'
        subscript = '<w:p><m:oMath><m:sSub><m:e><m:r><m:t>x</m:t></m:r></m:e><m:sub><m:r><m:t>y</m:t></m:r></m:sub></m:sSub></m:oMath></w:p>'
        make_docx(math_source, document_xml(fraction, ns))
        make_docx(math_changed, document_xml(subscript, ns))
        self.assertEqual(compare_documents(math_source, math_changed)["status"], "FAIL")

        drawing_source = self.temp / "drawing-source.docx"
        drawing_changed = self.temp / "drawing-changed.docx"
        rels = f'''<Relationships xmlns="{PR}"><Relationship Id="rId5" Type="{R}/image" Target="media/a.png"/><Relationship Id="rId6" Type="{R}/image" Target="media/b.png"/></Relationships>'''.encode()
        extra = {"word/media/a.png": b"a", "word/media/b.png": b"b"}
        drawing_ns = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
        make_docx(drawing_source, document_xml('<w:p><w:r><w:drawing><a:blip r:embed="rId5"/></w:drawing></w:r></w:p>', drawing_ns), extras=extra, document_rels=rels)
        make_docx(drawing_changed, document_xml('<w:p><w:r><w:drawing><a:blip r:embed="rId6"/></w:drawing></w:r></w:p>', drawing_ns), extras=extra, document_rels=rels)
        self.assertEqual(compare_documents(drawing_source, drawing_changed)["status"], "FAIL")

        for label, replacements in cases.items():
            changed = self.temp / f"{label.replace(' ', '-')}.docx"
            rewrite_parts(self.source, changed, replacements)
            with self.subTest(label=label):
                self.assertEqual(compare_documents(self.source, changed)["status"], "FAIL")

        binary = self.temp / "binary.docx"
        rewrite_parts(self.source, binary, {"custom/payload.bin": b"opaque"})
        self.assertEqual(compare_documents(self.source, binary)["status"], "FAIL")
        macro = self.temp / "macro.docx"
        rewrite_parts(self.source, macro, {"word/vbaProject.bin": b"macro"})
        with self.assertRaises(GuardError):
            compare_documents(self.source, macro)

    def test_scope_provenance_fingerprints_and_semantic_style_block(self) -> None:
        profile = valid_profile()
        self.assertEqual(validate_profile(profile)["status"], "PASS")
        profile["期刊评价"] = {"影响因子": 99, "推荐等级": "五星"}
        self.assertEqual(validate_profile(profile)["status"], "FAIL")
        bad_findings = {
            "schema_version": "2.0",
            "document": "x.docx",
            "scope": "FORMAT_ONLY",
            "profile_sha256": "0" * 64,
            "source_document_sha256": "0" * 64,
            "findings": [
                {
                    "issue_id": "FMT-BAD",
                    "story": "document",
                    "paragraph_index": 0,
                    "location": "正文",
                    "category": "BODY_TYPOGRAPHY",
                    "rule_id": "TITLE-001",
                    "current_format": "研究方法不合理，创新性不足",
                    "required_format": "重做试验",
                    "action": "COMMENT",
                    "status": "COMMENTED",
                    "scope": "FORMAT_ONLY",
                    "expected_text_sha256": "0" * 64,
                }
            ],
        }
        self.assertEqual(validate_findings_payload(bad_findings, profile=valid_profile())["status"], "FAIL")

        plan = self._valid_plan()
        plan["operations"][2]["properties"] = {"vertical_alignment": "superscript"}
        plan_path = self.temp / "bad-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        with self.assertRaises(ValueError):
            apply_format(self.source, plan_path, self.profile_path, self.temp / "bad.docx")

        stale_plan = self._valid_plan()
        stale_plan["operations"][1]["expected_text_sha256"] = "0" * 64
        stale_path = self.temp / "stale-plan.json"
        stale_path.write_text(json.dumps(stale_plan), encoding="utf-8")
        with self.assertRaises(ValueError):
            apply_format(self.source, stale_path, self.profile_path, self.temp / "stale.docx")

    def test_comment_verifier_rejects_unanchored_comment(self) -> None:
        fake = f'''<w:comments xmlns:w="{W}"><w:comment w:id="9" w:author="x"><w:p><w:r><w:t>fake</w:t></w:r></w:p></w:comment></w:comments>'''.encode()
        malformed = self.temp / "malformed.docx"
        rewrite_parts(self.source, malformed, {"word/comments.xml": fake})
        verification = verify_comments(malformed)
        self.assertFalse(verification["valid"])
        self.assertTrue(any("start" in error for error in verification["errors"]))

    def test_zip_security_and_stale_render_guard(self) -> None:
        traversal = self.temp / "traversal.docx"
        rewrite_parts(self.source, traversal, {"../escape.bin": b"x"})
        with self.assertRaises(PackageSafetyError):
            read_docx_package(traversal)

        bomb = self.temp / "bomb.docx"
        parts, _, _ = read_docx_package(self.source)
        with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as package:
            for name, data in parts.items():
                package.writestr(name, data)
            package.writestr("custom/repeated.bin", b"0" * (2 * 1024 * 1024))
        with self.assertRaises(PackageSafetyError):
            read_docx_package(bomb)

        render_dir = self.temp / "render"
        render_dir.mkdir()
        (render_dir / "page-999.png").write_bytes(b"stale")
        with self.assertRaises(ValueError):
            _prepare_output(render_dir, "source.pdf", False)
        _prepare_output(render_dir, "source.pdf", True)
        self.assertFalse((render_dir / "page-999.png").exists())

    def test_note_audit_detects_missing_definition(self) -> None:
        broken = self.temp / "broken-note.docx"
        parts, _, _ = read_docx_package(self.source)
        bad_notes = parts["word/footnotes.xml"].replace(b'w:id="1"', b'w:id="2"')
        rewrite_parts(self.source, broken, {"word/footnotes.xml": bad_notes})
        result = audit_notes(broken)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["stories"]["footnotes"]["missing_definition_ids"], ["1"])

    def test_format_only_exclusion_is_allowed_but_scientific_comment_is_not(self) -> None:
        exclusion = {"statement": "不审查论文质量、科学内容、方法、统计或结论。"}
        self.assertEqual(validate_format_only_payload(exclusion), [])
        criticism = {"comment": "研究方法错误，结论不可信。"}
        self.assertTrue(validate_format_only_payload(criticism))

    def test_complete_v2_bundle_passes_and_cross_checks_receipts(self) -> None:
        bundle = self.temp / "bundle"
        records = bundle / "03_审查记录"
        (records / "规则原文").mkdir(parents=True)
        (bundle / "00_原稿只读副本").mkdir()
        (bundle / "01_格式修订清洁版").mkdir()
        (bundle / "02_格式审查批注版").mkdir()
        clean_render_dir = bundle / "04_逐页渲染/clean"
        annotated_render_dir = bundle / "04_逐页渲染/annotated"
        clean_render_dir.mkdir(parents=True)
        annotated_render_dir.mkdir(parents=True)
        bundle_source = bundle / "00_原稿只读副本/manuscript.docx"
        shutil.copy2(self.source, bundle_source)

        snapshot = records / "规则原文/source.html"
        snapshot.write_text("Official format source snapshot", encoding="utf-8")
        profile = valid_profile()
        profile["rules"] = [rule for rule in profile["rules"] if rule["rule_id"] == "TITLE-001"]
        profile["rules"][0]["source_sha256"] = sha256_file(snapshot)
        profile["rules"][0]["source_snapshot"] = "03_审查记录/规则原文/source.html"
        profile_path = records / "journal-profile.json"
        profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")

        source_parts, _, _ = read_docx_package(bundle_source)
        source_root = ET.fromstring(source_parts["word/document.xml"])
        plan = {
            "schema_version": "2.0",
            "scope": "FORMAT_ONLY",
            "source_document_sha256": sha256_file(bundle_source),
            "journal_profile_sha256": sha256_file(profile_path),
            "operations": [
                {
                    "operation_id": "OP-TITLE",
                    "rule_id": "TITLE-001",
                    "op": "paragraph",
                    "story": "document",
                    "paragraph_index": 0,
                    "expected_text_sha256": text_hash("Soil title"),
                    "risk_class": "SAFE_TYPOGRAPHY",
                    "properties": {"alignment": "center"},
                }
            ],
        }
        plan_path = records / "format-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        clean = bundle / "01_格式修订清洁版/manuscript-格式修订清洁版.docx"
        format_receipt = apply_format(bundle_source, plan_path, profile_path, clean)
        (records / "format-application-receipt.json").write_text(
            json.dumps(format_receipt, ensure_ascii=False), encoding="utf-8"
        )

        findings = {
            "schema_version": "2.0",
            "document": clean.name,
            "scope": "FORMAT_ONLY",
            "profile_sha256": sha256_file(profile_path),
            "source_document_sha256": sha256_file(clean),
            "findings": [
                {
                    "issue_id": "CMT-TITLE",
                    "story": "document",
                    "note_id": None,
                    "paragraph_index": 0,
                    "location": "Title paragraph",
                    "category": "TITLE_BLOCK",
                    "rule_id": "TITLE-001",
                    "current_format": "Title alignment was checked",
                    "required_format": "Use the cited title alignment",
                    "action": "COMMENT",
                    "status": "COMMENTED",
                    "scope": "FORMAT_ONLY",
                    "expected_text_sha256": text_hash("Soil title"),
                }
            ],
        }
        findings_path = records / "format-findings.json"
        findings_path.write_text(json.dumps(findings), encoding="utf-8")
        annotated = bundle / "02_格式审查批注版/manuscript-格式审查批注版.docx"
        comment_receipt = add_comments(clean, findings_path, profile_path, annotated, "Review", "R")
        (records / "comment-application-receipt.json").write_text(
            json.dumps(comment_receipt, ensure_ascii=False), encoding="utf-8"
        )

        clean_integrity = compare_documents(bundle_source, clean)
        annotated_integrity = compare_documents(clean, annotated, allow_comment_additions=True)
        (records / "clean-integrity.json").write_text(json.dumps(clean_integrity), encoding="utf-8")
        (records / "annotated-integrity.json").write_text(json.dumps(annotated_integrity), encoding="utf-8")
        (records / "source-inspection.json").write_text(json.dumps(inspect_docx(bundle_source)), encoding="utf-8")
        (records / "note-audit.json").write_text(json.dumps(audit_notes(bundle_source)), encoding="utf-8")
        (records / "toolchain-report.json").write_text(json.dumps(inspect_toolchain()), encoding="utf-8")
        mapping = SCRIPT_DIR.parent / "assets/font-compatibility.json"
        (records / "clean-font-audit.json").write_text(json.dumps(audit_fonts(clean, mapping, [])), encoding="utf-8")
        (records / "annotated-font-audit.json").write_text(
            json.dumps(audit_fonts(annotated, mapping, [])), encoding="utf-8"
        )

        png = b"\x89PNG\r\n\x1a\n" + b"test-render-page" * 10
        for render_dir, document, receipt_name in (
            (clean_render_dir, clean, "clean"),
            (annotated_render_dir, annotated, "annotated"),
        ):
            page = render_dir / "page-1.png"
            page.write_bytes(png)
            render_receipt = {
                "status": "VISUAL_REVIEW_PASS",
                "docx_sha256": sha256_file(document),
                "pages": [{"page": 1, "path": "page-1.png", "sha256": sha256_file(page), "bytes": len(png)}],
                "page_count": 1,
                "visual_review": {
                    "status": "PASS",
                    "reviewer": "Test",
                    "reviewed_at": "2026-08-15T00:00:00Z",
                    "notes": f"Reviewed every {receipt_name} page",
                    "pages_reviewed": [1],
                },
            }
            (render_dir / "reviewed-render-receipt.json").write_text(json.dumps(render_receipt), encoding="utf-8")

        with (records / "期刊规则来源.csv").open("w", encoding="utf-8", newline="") as handle:
            columns = [
                "rule_id", "category", "requirement", "source_url", "source_title", "source_locator", "source_kind",
                "source_sha256", "source_snapshot", "accessed_at", "article_type", "verification_status", "automation",
            ]
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerow({key: profile["rules"][0][key] for key in columns})
        with (records / "格式修改台账.csv").open("w", encoding="utf-8", newline="") as handle:
            columns = [
                "issue_id", "operation_id", "story", "note_id", "location", "category", "rule_id", "before_format",
                "after_format", "action", "comment_id", "target_text_sha256", "status",
            ]
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerow(
                {
                    "issue_id": "CMT-TITLE",
                    "operation_id": "OP-TITLE",
                    "story": "document",
                    "note_id": "",
                    "location": "Title paragraph",
                    "category": "TITLE_BLOCK",
                    "rule_id": "TITLE-001",
                    "before_format": "left",
                    "after_format": "center",
                    "action": "COMMENT",
                    "comment_id": str(comment_receipt["added"][0]["comment_id"]),
                    "target_text_sha256": text_hash("Soil title"),
                    "status": "COMMENTED",
                }
            )
        headings = [
            "## 目标与范围", "## 官方规则", "## 已修订格式问题", "## 仅批注或需作者处理", "## 未验证规则与冲突",
            "## 内容保真校验", "## 脚注与尾注校验", "## 字体与跨平台校验", "## 逐页视觉核验", "## 未开展的内容审查",
        ]
        report = (
            "# 格式审查报告\n\n本次只审查形式和投稿格式，未评价论文质量、科学内容、方法、统计、论证、语言表达或引文真实性。\n\n"
            + "\n\n".join(f"{heading}\n\n本节记录可复核的格式事实、文件哈希、规则来源和验证结果。" for heading in headings)
        )
        (records / "格式审查报告.md").write_text(report, encoding="utf-8")

        manifest = {
            "schema_version": "2.0",
            "scope": "FORMAT_ONLY",
            "source_document": "00_原稿只读副本/manuscript.docx",
            "clean_document": "01_格式修订清洁版/manuscript-格式修订清洁版.docx",
            "annotated_document": "02_格式审查批注版/manuscript-格式审查批注版.docx",
            "audit_report": "03_审查记录/格式审查报告.md",
            "change_ledger": "03_审查记录/格式修改台账.csv",
            "rule_manifest": "03_审查记录/期刊规则来源.csv",
            "journal_profile": "03_审查记录/journal-profile.json",
            "findings": "03_审查记录/format-findings.json",
            "format_plan": "03_审查记录/format-plan.json",
            "format_application_receipt": "03_审查记录/format-application-receipt.json",
            "comment_application_receipt": "03_审查记录/comment-application-receipt.json",
            "source_inspection": "03_审查记录/source-inspection.json",
            "note_audit": "03_审查记录/note-audit.json",
            "toolchain_report": "03_审查记录/toolchain-report.json",
            "clean_font_audit": "03_审查记录/clean-font-audit.json",
            "annotated_font_audit": "03_审查记录/annotated-font-audit.json",
            "clean_integrity": "03_审查记录/clean-integrity.json",
            "annotated_integrity": "03_审查记录/annotated-integrity.json",
            "clean_render_receipt": "04_逐页渲染/clean/reviewed-render-receipt.json",
            "annotated_render_receipt": "04_逐页渲染/annotated/reviewed-render-receipt.json",
            "expect_format_comments": True,
            "approved_header_footer_parts": [],
            "platform_claims": [inspect_toolchain()["platform"]["system"]],
        }
        manifest_path = bundle / "delivery-manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        result = validate_bundle(manifest_path)
        self.assertEqual(result["status"], "PASS", result["errors"])

        ledger_path = records / "格式修改台账.csv"
        ledger_text = ledger_path.read_text(encoding="utf-8")
        ledger_path.write_text(ledger_text.replace(",0,", ",999,"), encoding="utf-8")
        tampered = validate_bundle(manifest_path)
        self.assertEqual(tampered["status"], "FAIL")
        self.assertTrue(any("comment_id" in error for error in tampered["errors"]))

    def test_applicable_journal_index_matches_registry(self) -> None:
        skill_root = SCRIPT_DIR.parent
        registry_path = skill_root / "references/journal-registry.csv"
        index_path = skill_root / "references/applicable-journals.md"
        with registry_path.open(encoding="utf-8-sig", newline="") as handle:
            registry_names = [row["journal_name"] for row in csv.DictReader(handle)]
        index_names = [
            line[3:-1]
            for line in index_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("- `") and line.endswith("`")
        ]
        self.assertEqual(len(registry_names), 228)
        self.assertEqual(len(index_names), len(registry_names))
        self.assertEqual(len(index_names), len(set(index_names)))
        self.assertEqual(set(index_names), set(registry_names))

    def test_git_blob_hash_implementation(self) -> None:
        self.assertEqual(git_blob_sha1(b"test\n"), "9daeafb9864cf43055ae93beb0afd6c7d144bfa4")


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Add structurally verified Word comments from format-only findings."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

from compare_docx_content import GuardError, compare_documents
from ooxml_safety import PackageSafetyError, read_docx_package, sha256_file
from validate_findings import rendered_comment, validate_findings_payload
from validate_journal_profile import validate_profile

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
XML = "http://www.w3.org/XML/1998/namespace"

ET.register_namespace("w", W)
ET.register_namespace("r", R)

STORY_PARTS = {
    "document": "word/document.xml",
    "footnotes": "word/footnotes.xml",
    "endnotes": "word/endnotes.xml",
}


def qn(local: str) -> str:
    return f"{{{W}}}{local}"


def _parse_xml(data: bytes) -> tuple[ET.Element, dict[str, str]]:
    namespaces: dict[str, str] = {}
    for _, (prefix, uri) in ET.iterparse(BytesIO(data), events=("start-ns",)):
        namespaces.setdefault(prefix, uri)
    return ET.fromstring(data), namespaces


def _used_namespace_uris(root: ET.Element) -> set[str]:
    used: set[str] = set()
    for element in root.iter():
        if element.tag.startswith("{"):
            used.add(element.tag[1:].split("}", 1)[0])
        for name in element.attrib:
            if name.startswith("{"):
                used.add(name[1:].split("}", 1)[0])
    return used


def _serialize(root: ET.Element, namespaces: dict[str, str] | None = None) -> bytes:
    namespaces = dict(namespaces or {})
    for prefix, uri in namespaces.items():
        if prefix in {"xml", "xmlns"} or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*|", prefix):
            continue
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            continue
    ignorable_name = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable"
    used_uris = _used_namespace_uris(root)
    for prefix in root.get(ignorable_name, "").split():
        uri = namespaces.get(prefix)
        if uri and uri not in used_uris:
            root.set(f"xmlns:{prefix}", uri)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _paragraph_visible_text(paragraph: ET.Element) -> str:
    chunks = []
    for element in paragraph.iter():
        if element.tag == qn("t"):
            chunks.append(element.text or "")
        elif element.tag == qn("tab"):
            chunks.append("\t")
        elif element.tag in {qn("br"), qn("cr")}:
            chunks.append("\n")
    return "".join(chunks)


def _story_paragraphs(root: ET.Element, story: str, note_id: str | None) -> list[ET.Element]:
    if story == "document":
        return list(root.iter(qn("p")))
    singular = "footnote" if story == "footnotes" else "endnote"
    for note in root.findall(qn(singular)):
        if note.get(qn("id")) == note_id:
            if note.get(qn("type"), "normal") != "normal":
                raise ValueError(f"{story} note_id {note_id} is a separator, not a manuscript note")
            return list(note.iter(qn("p")))
    raise ValueError(f"{story} note_id {note_id} was not found")


def _existing_ids(stories: dict[str, ET.Element], comments: ET.Element | None) -> set[int]:
    ids: set[int] = set()
    for root in stories.values():
        for element in root.iter():
            if element.tag not in {qn("commentRangeStart"), qn("commentRangeEnd"), qn("commentReference")}:
                continue
            value = element.get(qn("id"))
            if value is not None and value.lstrip("-").isdigit():
                ids.add(int(value))
    if comments is not None:
        for element in comments.findall(qn("comment")):
            value = element.get(qn("id"))
            if value is not None and value.lstrip("-").isdigit():
                ids.add(int(value))
    return ids


def _next_id(used: set[int]) -> int:
    candidate = max(used, default=-1) + 1
    while candidate in used:
        candidate += 1
    used.add(candidate)
    return candidate


def _comment_body(comment_id: int, author: str, initials: str, text: str, date: str) -> ET.Element:
    comment = ET.Element(
        qn("comment"),
        {qn("id"): str(comment_id), qn("author"): author, qn("initials"): initials, qn("date"): date},
    )
    paragraph = ET.SubElement(comment, qn("p"))
    p_pr = ET.SubElement(paragraph, qn("pPr"))
    ET.SubElement(p_pr, qn("pStyle"), {qn("val"): "CommentText"})
    reference_run = ET.SubElement(paragraph, qn("r"))
    r_pr = ET.SubElement(reference_run, qn("rPr"))
    ET.SubElement(r_pr, qn("rStyle"), {qn("val"): "CommentReference"})
    ET.SubElement(reference_run, qn("annotationRef"))
    text_run = ET.SubElement(paragraph, qn("r"))
    text_element = ET.SubElement(text_run, qn("t"), {f"{{{XML}}}space": "preserve"})
    text_element.text = text
    return comment


def _ensure_comments_relationship(rels: ET.Element) -> None:
    comment_type = f"{R}/comments"
    if any(rel.get("Type") == comment_type for rel in rels.findall(f"{{{PR}}}Relationship")):
        return
    used = {
        int(rel.get("Id", "")[3:])
        for rel in rels.findall(f"{{{PR}}}Relationship")
        if rel.get("Id", "").startswith("rId") and rel.get("Id", "")[3:].isdigit()
    }
    candidate = 1
    while candidate in used:
        candidate += 1
    ET.SubElement(
        rels,
        f"{{{PR}}}Relationship",
        {"Id": f"rId{candidate}", "Type": comment_type, "Target": "comments.xml"},
    )


def _ensure_content_type(content_types: ET.Element) -> None:
    if any(
        item.get("PartName") == "/word/comments.xml"
        for item in content_types.findall(f"{{{CT}}}Override")
    ):
        return
    ET.SubElement(
        content_types,
        f"{{{CT}}}Override",
        {
            "PartName": "/word/comments.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
        },
    )


def _load_inputs(findings_path: Path, profile_path: Path, source: Path) -> tuple[dict, dict]:
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile_validation = validate_profile(profile)
    if profile_validation["status"] != "PASS":
        raise ValueError(f"Journal profile is invalid: {profile_validation['errors']}")
    findings_validation = validate_findings_payload(findings, profile=profile)
    if findings_validation["status"] != "PASS":
        raise ValueError(f"Findings are invalid: {findings_validation['errors']}")
    if findings["profile_sha256"].lower() != sha256_file(profile_path):
        raise ValueError("findings.profile_sha256 does not match the journal profile")
    if findings["source_document_sha256"].lower() != sha256_file(source):
        raise ValueError("findings.source_document_sha256 does not match the source DOCX")
    return findings, profile


def add_comments(
    source: Path,
    findings_path: Path,
    profile_path: Path,
    output: Path,
    author: str,
    initials: str,
) -> dict:
    if source.resolve() == output.resolve():
        raise ValueError("Output must not overwrite the source DOCX")
    findings_payload, _ = _load_inputs(findings_path, profile_path, source)
    parts, infos, security = read_docx_package(source)

    story_roots: dict[str, ET.Element] = {}
    story_namespaces: dict[str, dict[str, str]] = {}
    for story, part_name in STORY_PARTS.items():
        if part_name in parts:
            story_roots[story], story_namespaces[story] = _parse_xml(parts[part_name])
    if "word/comments.xml" in parts:
        comments, comments_namespaces = _parse_xml(parts["word/comments.xml"])
    else:
        comments = ET.Element(qn("comments"))
        comments_namespaces = {"w": W}
    if "word/_rels/document.xml.rels" in parts:
        rels, rels_namespaces = _parse_xml(parts["word/_rels/document.xml.rels"])
    else:
        rels = ET.Element(f"{{{PR}}}Relationships")
        rels_namespaces = {"": PR}
    content_types, content_type_namespaces = _parse_xml(parts["[Content_Types].xml"])
    used_ids = _existing_ids(story_roots, comments)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    added = []
    note_story_used = False

    for finding in findings_payload["findings"]:
        story = finding["story"]
        if story not in story_roots:
            raise ValueError(f"DOCX does not contain the {story} story")
        note_id = str(finding["note_id"]) if finding.get("note_id") is not None else None
        paragraphs = _story_paragraphs(story_roots[story], story, note_id)
        index = finding["paragraph_index"]
        if index >= len(paragraphs):
            raise ValueError(
                f"{finding['issue_id']}: paragraph_index {index} is out of range for {story}"
            )
        paragraph = paragraphs[index]
        visible_text = _paragraph_visible_text(paragraph)
        if not visible_text:
            raise ValueError(f"{finding['issue_id']}: target paragraph has no visible text")
        import hashlib

        actual_hash = hashlib.sha256(visible_text.encode("utf-8")).hexdigest()
        if actual_hash != finding["expected_text_sha256"].lower():
            raise ValueError(f"{finding['issue_id']}: target fingerprint does not match the DOCX")
        comment_id = _next_id(used_ids)
        children = list(paragraph)
        insert_at = 1 if children and children[0].tag == qn("pPr") else 0
        paragraph.insert(insert_at, ET.Element(qn("commentRangeStart"), {qn("id"): str(comment_id)}))
        paragraph.append(ET.Element(qn("commentRangeEnd"), {qn("id"): str(comment_id)}))
        reference_run = ET.SubElement(paragraph, qn("r"))
        r_pr = ET.SubElement(reference_run, qn("rPr"))
        ET.SubElement(r_pr, qn("rStyle"), {qn("val"): "CommentReference"})
        ET.SubElement(reference_run, qn("commentReference"), {qn("id"): str(comment_id)})
        comments.append(_comment_body(comment_id, author, initials, rendered_comment(finding), now))
        note_story_used = note_story_used or story in {"footnotes", "endnotes"}
        added.append(
            {
                "issue_id": finding["issue_id"],
                "rule_id": finding["rule_id"],
                "story": story,
                "note_id": note_id,
                "paragraph_index": index,
                "comment_id": comment_id,
                "target_text_sha256": actual_hash,
            }
        )

    _ensure_comments_relationship(rels)
    _ensure_content_type(content_types)
    for story, root in story_roots.items():
        parts[STORY_PARTS[story]] = _serialize(root, story_namespaces[story])
    parts["word/comments.xml"] = _serialize(comments, comments_namespaces)
    parts["word/_rels/document.xml.rels"] = _serialize(rels, rels_namespaces)
    parts["[Content_Types].xml"] = _serialize(content_types, content_type_namespaces)

    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix="format-comments-", suffix=".docx", dir=output.parent)
    os.close(handle)
    try:
        with zipfile.ZipFile(temporary_name, "w") as target:
            written = set()
            for info in infos:
                target.writestr(info, b"" if info.is_dir() else parts[info.filename])
                written.add(info.filename)
            if "word/comments.xml" not in written:
                target.writestr("word/comments.xml", parts["word/comments.xml"])
            if "word/_rels/document.xml.rels" not in written:
                target.writestr("word/_rels/document.xml.rels", parts["word/_rels/document.xml.rels"])
        verification = verify_comments(Path(temporary_name))
        if not verification["valid"]:
            raise ValueError(f"Comment structural verification failed: {verification['errors']}")
        guard = compare_documents(source, Path(temporary_name), allow_comment_additions=True)
        if guard["status"] != "PASS":
            raise ValueError(f"Content guard rejected the annotated DOCX: {guard['failures']}")
        os.replace(temporary_name, output)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)

    return {
        "status": "PASS",
        "scope": "FORMAT_ONLY_COMMENTS",
        "source": str(source.resolve()),
        "output": str(output.resolve()),
        "source_sha256": sha256_file(source),
        "output_sha256": sha256_file(output),
        "profile_sha256": sha256_file(profile_path),
        "findings_sha256": sha256_file(findings_path),
        "package_security": security,
        "added": added,
        "verification": verify_comments(output),
        "native_word_review_required": note_story_used,
        "native_word_review_reason": (
            "At least one comment is anchored in a footnote/endnote story; verify comment UI placement in desktop Word."
            if note_story_used
            else None
        ),
    }


def verify_comments(path: Path) -> dict:
    try:
        parts, _, security = read_docx_package(path)
    except PackageSafetyError as exc:
        return {"valid": False, "errors": [str(exc)]}
    errors = []
    if "word/comments.xml" not in parts:
        return {"valid": False, "errors": ["word/comments.xml missing"]}
    comments = ET.fromstring(parts["word/comments.xml"])
    rels = ET.fromstring(parts["word/_rels/document.xml.rels"])
    content_types = ET.fromstring(parts["[Content_Types].xml"])
    comment_elements = comments.findall(qn("comment"))
    comment_ids = [element.get(qn("id")) for element in comment_elements]
    if None in comment_ids or len(comment_ids) != len(set(comment_ids)):
        errors.append("comment IDs are missing or duplicated")

    counts = {"start": {}, "end": {}, "reference": {}}
    anchor_locations: dict[str, list[str]] = {}
    story_names = ["word/document.xml", "word/footnotes.xml", "word/endnotes.xml"] + sorted(
        name
        for name in parts
        if re.fullmatch(r"word/(?:header|footer)\d+\.xml", name)
    )
    for name in story_names:
        if name not in parts:
            continue
        root = ET.fromstring(parts[name])
        for key, tag in (
            ("start", "commentRangeStart"),
            ("end", "commentRangeEnd"),
            ("reference", "commentReference"),
        ):
            for element in root.iter(qn(tag)):
                comment_id = element.get(qn("id"))
                counts[key][comment_id] = counts[key].get(comment_id, 0) + 1
                anchor_locations.setdefault(str(comment_id), []).append(name)

    all_anchor_ids = set().union(*(set(value) for value in counts.values()))
    for comment_id in sorted(set(comment_ids) | all_anchor_ids, key=lambda value: str(value)):
        if comment_id not in set(comment_ids):
            errors.append(f"orphan comment anchor {comment_id}")
            continue
        for key in ("start", "end", "reference"):
            if counts[key].get(comment_id, 0) != 1:
                errors.append(f"comment {comment_id}: expected one {key}, found {counts[key].get(comment_id, 0)}")
        locations = set(anchor_locations.get(str(comment_id), []))
        if len(locations) > 1:
            errors.append(f"comment {comment_id}: anchors span multiple story parts")

    relationships = [
        rel
        for rel in rels.findall(f"{{{PR}}}Relationship")
        if rel.get("Type") == f"{R}/comments"
    ]
    if len(relationships) != 1 or relationships[0].get("Target") != "comments.xml":
        errors.append("exact comments relationship is missing or duplicated")
    overrides = [
        item
        for item in content_types.findall(f"{{{CT}}}Override")
        if item.get("PartName") == "/word/comments.xml"
    ]
    if len(overrides) != 1:
        errors.append("comments content type override is missing or duplicated")
    return {
        "valid": not errors,
        "errors": errors,
        "comment_count": len(comment_ids),
        "comment_ids": sorted(str(value) for value in comment_ids),
        "anchor_locations": anchor_locations,
        "package_security": security,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("findings", type=Path)
    parser.add_argument("--journal-profile", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--author", default="排版审查")
    parser.add_argument("--initials", default="FR")
    args = parser.parse_args()
    try:
        result = add_comments(
            args.source,
            args.findings,
            args.journal_profile,
            args.out,
            args.author,
            args.initials,
        )
    except (
        FileNotFoundError,
        KeyError,
        ValueError,
        GuardError,
        PackageSafetyError,
        zipfile.BadZipFile,
        ET.ParseError,
        json.JSONDecodeError,
    ) as exc:
        result = {"status": "ERROR", "error": str(exc)}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Shared fail-closed DOCX package reader and security preflight.

The helpers in this module deliberately use only the Python standard library so
every bundled command can perform the same checks on macOS and Windows before
parsing or rewriting OOXML.
"""

from __future__ import annotations

import hashlib
import argparse
import json
import posixpath
import re
import zipfile
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

PR = "http://schemas.openxmlformats.org/package/2006/relationships"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

DEFAULT_MAX_MEMBERS = 5_000
DEFAULT_MAX_MEMBER_BYTES = 128 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_COMPRESSION_RATIO = 200.0

_ACTIVE_PART_PATTERNS = (
    re.compile(r"(^|/)vbaproject\.bin$", re.I),
    re.compile(r"(^|/)activex/", re.I),
    re.compile(r"(^|/)ctrlprops/", re.I),
    re.compile(r"(^|/)customui/", re.I),
    re.compile(r"(^|/)webextensions/", re.I),
)

_UNSAFE_EXTERNAL_REL_SUFFIXES = {
    "/attachedTemplate",
    "/oleObject",
    "/externalLink",
    "/image",
    "/aFChunk",
    "/package",
}

_DDE_RE = re.compile(r"(?:^|\s)(?:DDE|DDEAUTO)(?:\s|$)", re.I)


class PackageSafetyError(RuntimeError):
    """Raised when a DOCX is malformed, unsafe, or exceeds resource limits."""


@dataclass(frozen=True)
class PackageLimits:
    max_members: int = DEFAULT_MAX_MEMBERS
    max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_member_name(name: str) -> None:
    if not name or "\x00" in name:
        raise PackageSafetyError("DOCX contains an empty or NUL-containing ZIP member name")
    if "\\" in name:
        raise PackageSafetyError(f"DOCX member uses a backslash path: {name!r}")
    pure = PurePosixPath(name)
    if pure.is_absolute() or name.startswith("/"):
        raise PackageSafetyError(f"DOCX member has an absolute path: {name!r}")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise PackageSafetyError(f"DOCX member has an unsafe path component: {name!r}")
    normalized = posixpath.normpath(name)
    if normalized != name.rstrip("/"):
        raise PackageSafetyError(f"DOCX member path is not canonical: {name!r}")


def _xml_root(data: bytes, label: str) -> ET.Element:
    prefix = data[:4096].upper()
    if b"<!DOCTYPE" in prefix or b"<!ENTITY" in prefix:
        raise PackageSafetyError(f"DTD/entity declarations are not allowed in {label}")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise PackageSafetyError(f"Invalid XML in {label}: {exc}") from exc


def relationship_source_part(rels_name: str) -> str | None:
    """Return the OOXML source part for a relationship part."""
    if rels_name == "_rels/.rels":
        return ""
    marker = "/_rels/"
    if marker not in rels_name or not rels_name.endswith(".rels"):
        return None
    prefix, basename = rels_name.rsplit(marker, 1)
    return f"{prefix}/{basename[:-5]}"


def resolve_relationship_target(rels_name: str, target: str) -> str:
    source = relationship_source_part(rels_name)
    if source is None:
        raise PackageSafetyError(f"Unrecognized relationship part path: {rels_name}")
    if target.startswith("/"):
        return target.lstrip("/")
    base = posixpath.dirname(source)
    resolved = posixpath.normpath(posixpath.join(base, target))
    if resolved == ".." or resolved.startswith("../"):
        raise PackageSafetyError(
            f"Relationship target escapes the package: {rels_name} -> {target}"
        )
    return resolved


def _scan_security(parts: dict[str, bytes]) -> dict:
    active_parts = sorted(
        name
        for name in parts
        if any(pattern.search(name) for pattern in _ACTIVE_PART_PATTERNS)
        or name.lower().endswith((".exe", ".dll", ".js", ".vbs", ".ps1", ".bat", ".cmd"))
    )
    altchunk_parts = sorted(name for name in parts if name.lower().startswith("word/afchunk"))
    content_type_root = _xml_root(parts["[Content_Types].xml"], "[Content_Types].xml")
    unsafe_content_types = sorted(
        value
        for element in content_type_root
        for value in (element.get("ContentType", ""),)
        if any(marker in value.lower() for marker in ("macroenabled", "activex", "vba"))
    )
    external_relationships: list[dict[str, str]] = []
    unsafe_external_relationships: list[dict[str, str]] = []
    missing_internal_targets: list[dict[str, str]] = []
    invalid_relationships: list[str] = []

    for rels_name, data in sorted(parts.items()):
        if not rels_name.endswith(".rels"):
            continue
        root = _xml_root(data, rels_name)
        seen_ids: set[str] = set()
        for rel in root.findall(f"{{{PR}}}Relationship"):
            rel_id = rel.get("Id", "")
            rel_type = rel.get("Type", "")
            target = rel.get("Target", "")
            target_mode = rel.get("TargetMode", "Internal")
            if not rel_id or rel_id in seen_ids:
                invalid_relationships.append(f"{rels_name}: missing/duplicate relationship Id {rel_id!r}")
            seen_ids.add(rel_id)
            if not target or not rel_type:
                invalid_relationships.append(f"{rels_name}:{rel_id}: empty Type or Target")
                continue
            if target_mode == "External":
                row = {"part": rels_name, "id": rel_id, "type": rel_type, "target": target}
                external_relationships.append(row)
                parsed = urlparse(target)
                unsafe_scheme = parsed.scheme.lower() not in {"http", "https", "mailto"}
                unsafe_type = any(rel_type.endswith(suffix) for suffix in _UNSAFE_EXTERNAL_REL_SUFFIXES)
                if unsafe_scheme or unsafe_type:
                    unsafe_external_relationships.append(row)
            elif target_mode == "Internal":
                try:
                    resolved = resolve_relationship_target(rels_name, target)
                except PackageSafetyError as exc:
                    invalid_relationships.append(str(exc))
                    continue
                if resolved not in parts:
                    missing_internal_targets.append(
                        {"part": rels_name, "id": rel_id, "type": rel_type, "target": resolved}
                    )
            else:
                invalid_relationships.append(
                    f"{rels_name}:{rel_id}: unsupported TargetMode {target_mode!r}"
                )

    field_instructions: list[dict[str, str]] = []
    dde_fields: list[dict[str, str]] = []
    for name, data in sorted(parts.items()):
        if not name.startswith("word/") or not name.endswith(".xml"):
            continue
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            continue
        for element in root.iter():
            local = element.tag.rsplit("}", 1)[-1]
            if local == "instrText":
                instruction = (element.text or "").strip()
            elif local == "fldSimple":
                instruction = (element.get(f"{{{W}}}instr") or "").strip()
            else:
                continue
            if not instruction:
                continue
            row = {"part": name, "instruction": instruction}
            field_instructions.append(row)
            if _DDE_RE.search(instruction):
                dde_fields.append(row)
        joined_instructions = " ".join(
            (element.text or "").strip()
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1] == "instrText"
        )
        if joined_instructions and _DDE_RE.search(joined_instructions):
            row = {"part": name, "instruction": joined_instructions}
            if row not in dde_fields:
                dde_fields.append(row)

    errors: list[str] = []
    if active_parts:
        errors.append("active or executable package parts are not allowed")
    if altchunk_parts:
        errors.append("altChunk parts are not allowed in a format-only workflow")
    if unsafe_content_types:
        errors.append("macro-enabled or ActiveX content types are not allowed")
    if unsafe_external_relationships:
        errors.append("unsafe external relationships are not allowed")
    if missing_internal_targets:
        errors.append("internal relationship targets are missing")
    if invalid_relationships:
        errors.append("relationship parts are malformed")
    if dde_fields:
        errors.append("DDE/DDEAUTO field instructions are not allowed")

    return {
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "active_parts": active_parts,
        "altchunk_parts": altchunk_parts,
        "unsafe_content_types": unsafe_content_types,
        "external_relationships": external_relationships,
        "unsafe_external_relationships": unsafe_external_relationships,
        "missing_internal_targets": missing_internal_targets,
        "invalid_relationships": invalid_relationships,
        "dde_fields": dde_fields,
        "field_instruction_count": len(field_instructions),
    }


def read_docx_package(
    path: Path,
    *,
    limits: PackageLimits | None = None,
    reject_unsafe: bool = True,
) -> tuple[dict[str, bytes], list[zipfile.ZipInfo], dict]:
    """Read a DOCX after ZIP resource, path, relationship, and active-content checks."""
    limits = limits or PackageLimits()
    if not path.exists():
        raise PackageSafetyError(f"File not found: {path}")
    if path.suffix.lower() != ".docx":
        raise PackageSafetyError(f"Expected .docx: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > limits.max_members:
                raise PackageSafetyError(
                    f"DOCX has {len(infos)} ZIP members; limit is {limits.max_members}"
                )
            seen: set[str] = set()
            total = 0
            for info in infos:
                _validate_member_name(info.filename)
                if info.filename in seen:
                    raise PackageSafetyError(f"DOCX contains duplicate ZIP member: {info.filename}")
                seen.add(info.filename)
                if info.is_dir():
                    continue
                if info.file_size > limits.max_member_bytes:
                    raise PackageSafetyError(
                        f"DOCX member exceeds size limit: {info.filename} ({info.file_size} bytes)"
                    )
                total += info.file_size
                if total > limits.max_total_bytes:
                    raise PackageSafetyError(
                        f"DOCX uncompressed size exceeds {limits.max_total_bytes} bytes"
                    )
                if info.file_size and info.compress_size == 0:
                    raise PackageSafetyError(f"DOCX member has an invalid compression size: {info.filename}")
                if info.compress_size:
                    ratio = info.file_size / info.compress_size
                    if ratio > limits.max_compression_ratio and info.file_size > 1024 * 1024:
                        raise PackageSafetyError(
                            f"DOCX member compression ratio is suspicious: {info.filename} ({ratio:.1f}:1)"
                        )
            required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
            missing = sorted(required - seen)
            if missing:
                raise PackageSafetyError(f"Not a complete Word DOCX package; missing: {', '.join(missing)}")
            parts = {
                info.filename: archive.read(info.filename)
                for info in infos
                if not info.is_dir()
            }
    except zipfile.BadZipFile as exc:
        raise PackageSafetyError(f"Invalid DOCX ZIP package: {path}") from exc

    for name, data in parts.items():
        if name.endswith((".xml", ".rels")):
            _xml_root(data, name)
    security = _scan_security(parts)
    security.update(
        {
            "file": str(path.resolve()),
            "file_sha256": sha256_file(path),
            "member_count": len(parts),
            "uncompressed_bytes": sum(len(value) for value in parts.values()),
        }
    )
    if reject_unsafe and security["status"] != "PASS":
        raise PackageSafetyError("; ".join(security["errors"]))
    return parts, infos, security


def audit_docx_security(path: Path, *, limits: PackageLimits | None = None) -> dict:
    try:
        _, _, report = read_docx_package(path, limits=limits, reject_unsafe=False)
        return report
    except PackageSafetyError as exc:
        return {"status": "ERROR", "file": str(path.resolve()), "error": str(exc)}


def stable_part_hashes(parts: dict[str, bytes], names: Iterable[str]) -> dict[str, str]:
    return {name: sha256_bytes(parts[name]) for name in sorted(set(names)) if name in parts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit_docx_security(args.docx)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())

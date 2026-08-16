#!/usr/bin/env python3
"""Validate the official/user template registry and its activation boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


REQUIRED_FIELDS = {
    "id", "genre", "authority_type", "resource_kind", "title", "url",
    "download_url", "status", "scope", "template_required",
    "snapshot_required", "use_condition", "recheck",
}
REQUIRED_GENRES = {
    "academic_paper", "journal_manuscript", "grant_application",
    "patent_application", "standard", "thesis_dissertation",
    "scientific_report", "conference_abstract_or_presentation",
    "academic_poster", "technical_bid", "all_other_supported_genres",
}
URL_OPTIONAL_AUTHORITIES = {
    "controlled_procurement_document", "user_or_current_authority",
}
DOWNLOAD_KINDS = ("docx", "word", "pdf", "zip", "download", "attachment")


def is_https(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors: list[str] = []

    try:
        data = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    if data.get("schema_version") != 2:
        errors.append("schema_version must be 2")

    activation = data.get("activation")
    if not isinstance(activation, str) or not activation.strip():
        errors.append("activation must be a non-empty string")
        activation_text = ""
    else:
        activation_text = activation.casefold()
        if "full_artifact_generation" not in activation_text:
            errors.append("activation must include full_artifact_generation")
        if "template-aware repair" not in activation_text:
            errors.append("activation must include explicitly requested template-aware repair")
        if "ordinary language repair" not in activation_text or not any(
            marker in activation_text for marker in ("do not", "never", "must not")
        ):
            errors.append("activation must explicitly exclude ordinary language repair")

    priority = data.get("user_template_priority")
    if not isinstance(priority, str) or not priority.strip():
        errors.append("user_template_priority must be a non-empty string")
    else:
        priority_text = priority.casefold()
        if "user-supplied template" not in priority_text or "primary" not in priority_text:
            errors.append("user_template_priority must make the user-supplied template primary")
        if "conflict" not in priority_text:
            errors.append("user_template_priority must define conflict handling")

    entries = data.get("entries")
    if not isinstance(entries, list):
        errors.append("entries must be an array")
        entries = []
    if len(entries) < 20:
        errors.append("registry must contain at least 20 controlled entries")

    seen: set[str] = set()
    genres: set[str] = set()
    for index, entry in enumerate(entries):
        locator = f"entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{locator} must be an object")
            continue

        missing = REQUIRED_FIELDS - set(entry)
        extra = set(entry) - REQUIRED_FIELDS
        if missing:
            errors.append(f"{locator} missing fields: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"{locator} has unknown fields: {', '.join(sorted(extra))}")

        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id.strip():
            errors.append(f"{locator}.id must be a non-empty string")
            entry_id = locator
        elif entry_id in seen:
            errors.append(f"duplicate entry id: {entry_id}")
        seen.add(entry_id)

        for key in (
            "genre", "authority_type", "resource_kind", "title", "status",
            "scope", "use_condition", "recheck",
        ):
            value = entry.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{entry_id}.{key} must be a non-empty string")
        for key in ("url", "download_url"):
            value = entry.get(key)
            if not isinstance(value, str):
                errors.append(f"{entry_id}.{key} must be a string")
            elif value and not is_https(value):
                errors.append(f"{entry_id}.{key} must use a valid https URL")
        for key in ("template_required", "snapshot_required"):
            if not isinstance(entry.get(key), bool):
                errors.append(f"{entry_id}.{key} must be boolean")

        genre = entry.get("genre", "")
        authority = entry.get("authority_type", "")
        resource_kind = entry.get("resource_kind", "")
        status = entry.get("status", "")
        use_condition = entry.get("use_condition", "")
        recheck = entry.get("recheck", "")
        url = entry.get("url", "")
        download_url = entry.get("download_url", "")
        scope = entry.get("scope", "")
        if isinstance(genre, str) and genre:
            genres.add(genre)

        combined = " ".join(
            str(value).casefold()
            for value in (resource_kind, status, use_condition, scope, entry.get("title", ""))
        )
        if authority not in URL_OPTIONAL_AUTHORITIES and not url:
            errors.append(f"{entry_id}.url is required for an official/current registry entry")
        if download_url and entry.get("snapshot_required") is not True:
            errors.append(f"{entry_id}: downloadable resources require snapshot_required=true")
        if any(token in resource_kind.casefold() for token in DOWNLOAD_KINDS):
            if not any(token in combined for token in ("unresolved", "discovery")):
                if entry.get("snapshot_required") is not True:
                    errors.append(f"{entry_id}: downloadable template kind requires a controlled snapshot")

        if genre == "journal_manuscript" or authority.startswith("venue_"):
            if recheck != "before_each_submission":
                errors.append(f"{entry_id}: venue rules must be rechecked before_each_submission")
            if "full_artifact_generation" not in use_condition:
                errors.append(f"{entry_id}: venue templates are only activated for full-artifact work")

        if "historical" in status.casefold() or "historical" in resource_kind.casefold():
            if "reference_only" not in use_condition or "never_reuse" not in use_condition:
                errors.append(f"{entry_id}: historical/event-specific material must be reference-only and non-reusable")
        if authority == "event_instruction" and "historical" not in combined:
            if "this_event_only" not in use_condition:
                errors.append(f"{entry_id}: current event template must be limited to that event")

        if genre == "technical_bid":
            if authority != "controlled_procurement_document":
                errors.append(f"{entry_id}: a technical bid must use the controlled procurement document")
            if "tender" not in resource_kind.casefold() and "tender" not in combined:
                errors.append(f"{entry_id}: technical-bid entry must identify the tender template")
            if status != "must_be_supplied_per_project":
                errors.append(f"{entry_id}: tender template must be supplied per project")
            if url or download_url:
                errors.append(f"{entry_id}: project tender source must not be replaced by a generic URL")

        if "ordinary_language_repair" in use_condition.casefold():
            errors.append(f"{entry_id}: template registry cannot activate ordinary language repair")

    missing_genres = REQUIRED_GENRES - genres
    if missing_genres:
        errors.append(f"registry missing required genre coverage: {', '.join(sorted(missing_genres))}")

    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} template-registry error(s)")
        return 1
    print(f"PASS: {len(entries)} template-registry entries preserve authority and activation boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a non-copying implementation index for extracted R reference archives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


SCRIPT_SUFFIXES = {".r", ".rmd", ".qmd"}
PACKAGE_CALL = re.compile(r"(?:library|require)\s*\(\s*[\"']?([A-Za-z][A-Za-z0-9.]*)", re.I)
NAMESPACE_CALL = re.compile(r"\b([A-Za-z][A-Za-z0-9.]*)\s*:::{0,1}\s*([A-Za-z][A-Za-z0-9._]*)")
PLOT_CALL = re.compile(
    r"\b((?:geom|stat|scale|coord|facet|theme)_[A-Za-z0-9._]+|"
    r"ggplot|ggsave|Heatmap|ComplexHeatmap|ggraph|ggtree|gheatmap|"
    r"chordDiagram|circos\.[A-Za-z0-9._]+|mantel_test|qcorrplot|"
    r"plot_grid|wrap_plots|inset_element|geom_fruit|geom_couple|"
    r"pie_donut|PieDonut|network_plot|plotweb)\s*\(",
    re.I,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def decode(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="Directory containing one folder per extracted archive")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-tsv", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    scripts = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SCRIPT_SUFFIXES and not path.name.startswith("._")
    )
    rows: list[dict[str, object]] = []
    archive_packages: dict[str, Counter[str]] = defaultdict(Counter)
    archive_calls: dict[str, Counter[str]] = defaultdict(Counter)
    archive_patterns: dict[str, Counter[str]] = defaultdict(Counter)

    for path in scripts:
        relative = path.relative_to(root)
        archive = relative.parts[0]
        text = decode(path)
        packages = Counter(match.group(1) for match in PACKAGE_CALL.finditer(text))
        namespaces = Counter(match.group(1) for match in NAMESPACE_CALL.finditer(text))
        calls = Counter(match.group(1).lower() for match in PLOT_CALL.finditer(text))
        packages.update(namespaces)
        patterns = {
            "setwd": len(re.findall(r"\bsetwd\s*\(", text, re.I)),
            "runtime_install": len(re.findall(r"\b(?:install\.packages|BiocManager::install|remotes::install_)\s*\(", text, re.I)),
            "absolute_windows_path": len(re.findall(r"[A-Za-z]:[/\\\\]", text)),
            "absolute_macos_path": len(re.findall(r"/(?:Users|Volumes)/", text)),
            "set_seed": len(re.findall(r"\bset\.seed\s*\(", text, re.I)),
            "ggsave": len(re.findall(r"\bggsave\s*\(", text, re.I)),
            "explicit_device": len(re.findall(r"\b(?:pdf|png|tiff|jpeg|svg)\s*\(", text, re.I)),
            "secondary_axis": len(re.findall(r"\bsec_axis\s*\(", text, re.I)),
            "significance_annotation": len(re.findall(r"stat_(?:compare_means|pvalue_manual)|geom_signif|multcompLetters", text, re.I)),
        }
        archive_packages[archive].update(packages)
        archive_calls[archive].update(calls)
        archive_patterns[archive].update({key: value for key, value in patterns.items() if value})
        rows.append({
            "archive": archive,
            "path": str(relative),
            "bytes": path.stat().st_size,
            "lines": text.count("\n") + 1,
            "sha256": sha256(path),
            "packages": ";".join(sorted(packages)),
            "plot_calls": ";".join(sorted(calls)),
            **patterns,
        })

    fieldnames = list(rows[0]) if rows else ["archive", "path"]
    args.output_tsv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "scope": "Read-only structural audit; no source code is copied into the skill.",
        "root": str(root),
        "script_count": len(rows),
        "archive_summary": {},
    }
    archives = sorted({str(row["archive"]) for row in rows})
    for archive in archives:
        archive_rows = [row for row in rows if row["archive"] == archive]
        payload["archive_summary"][archive] = {
            "scripts": len(archive_rows),
            "lines": sum(int(row["lines"]) for row in archive_rows),
            "top_packages": archive_packages[archive].most_common(40),
            "top_plot_calls": archive_calls[archive].most_common(60),
            "portability_and_method_patterns": dict(archive_patterns[archive]),
        }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scripts": len(rows), "archives": archives}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

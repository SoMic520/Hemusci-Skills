#!/usr/bin/env python3
"""Audit identity, page coverage, hashes, gates and precision fixtures for four PDF corpora."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
ROOT = SKILL_ROOT / "references" / "external-corpora"
EXPECTED = {
    "lu-rukkun-2000": (665, 665),
    "soil-analysis-spec-2e-2006": (267, 267),
    "microbiome-protocol-1e-soil": (433, 65),
    "gbz-170-2026": (24, 24),
}
GATES = ("textPass", "precisionPass", "secondVisualPass")


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def canonical_hash(record: dict[str, Any]) -> str:
    content = {key: record.get(key) for key in ("blocks", "formulas", "tables")}
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> None:
    config = args()
    failures: list[str] = []
    summary: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    records_by_book: dict[str, dict[int, dict[str, Any]]] = {}
    for book_id, (source_pages, included_pages) in EXPECTED.items():
        directory = ROOT / book_id
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        outline = json.loads((directory / "outline.json").read_text(encoding="utf-8"))
        with gzip.open(directory / "pages.json.gz", "rt", encoding="utf-8") as stream:
            payload = json.load(stream)
        records = {int(record["page"]): record for record in payload.get("pages") or []}
        records_by_book[book_id] = records
        check(manifest.get("bookId") == book_id, f"{book_id}: manifest identity", failures)
        check(manifest.get("sourcePageCount") == source_pages, f"{book_id}: source page count", failures)
        check(manifest.get("includedPageCount") == included_pages, f"{book_id}: included count", failures)
        check(len(records) == included_pages, f"{book_id}: stored page count", failures)
        sha = str(manifest.get("sourcePdfSha256") or "")
        check(len(sha) == 64, f"{book_id}: source SHA-256", failures)
        check(sha not in hashes, f"{book_id}: duplicate content of {hashes.get(sha)}", failures)
        hashes[sha] = book_id
        if config.require_ready:
            check(manifest.get("runtimeReady") is True, f"{book_id}: runtimeReady false", failures)
        if book_id == "lu-rukkun-2000":
            check(
                all("&" not in str(item.get("title") or "") for item in outline),
                "lu-rukkun-2000: bookmark author separator leaked into hierarchy",
                failures,
            )
            check(
                any(
                    item.get("title") == "第一章  土壤样品采集与处理"
                    and item.get("authors") == ["鲁如坤"]
                    for item in outline
                ),
                "lu-rukkun-2000: chapter author metadata missing",
                failures,
            )
        for page, record in records.items():
            check(record.get("bookId") == book_id, f"{book_id}:{page}: identity", failures)
            check(record.get("sourcePdfSha256") == sha, f"{book_id}:{page}: PDF hash", failures)
            check(record.get("contentSha256") == canonical_hash(record), f"{book_id}:{page}: content hash", failures)
            check(isinstance(record.get("blocks"), list), f"{book_id}:{page}: blocks", failures)
            check(isinstance(record.get("formulas"), list), f"{book_id}:{page}: formulas", failures)
            check(isinstance(record.get("tables"), list), f"{book_id}:{page}: tables", failures)
            if manifest.get("runtimeReady"):
                for gate in GATES:
                    check(
                        (record.get("review") or {}).get(gate, {}).get("status") == "verified",
                        f"{book_id}:{page}: {gate}",
                        failures,
                    )
                for formula_index, formula in enumerate(record.get("formulas") or [], 1):
                    if formula.get("engine"):
                        check(
                            formula.get("reviewStatus") == "verified",
                            f"{book_id}:{page}: formula {formula_index} not verified",
                            failures,
                        )
        summary.append(
            {
                "bookId": book_id,
                "sourcePageCount": source_pages,
                "includedPageCount": included_pages,
                "runtimeReady": bool(manifest.get("runtimeReady")),
            }
        )

    gbz = records_by_book["gbz-170-2026"]
    formula = gbz[19]["formulas"][0]
    check(formula.get("label") == "NB.1", "gbz: NB.1 label", failures)
    check("V_sa+V_su+V_b" in formula.get("plain", ""), "gbz: NB.1 numerator", failures)
    check(len(gbz[16]["tables"][0]["rows"]) == 24, "gbz: table B.1 rows", failures)
    gbz_p9_rows = gbz[9]["tables"][0]["rows"]
    check(
        any(row == ["MUF标准液", "0.022 g 4-甲基伞形酮溶于DMSO，棕色容量瓶定容至25 mL；临用前配制"] for row in gbz_p9_rows),
        "gbz: MUF standard volume 25 mL",
        failures,
    )
    micro_pages = set(records_by_book["microbiome-protocol-1e-soil"])
    for excluded_transition in (256, 283, 303, 324, 366):
        check(excluded_transition not in micro_pages, f"microbiome: transition page {excluded_transition}", failures)
    micro = records_by_book["microbiome-protocol-1e-soil"]
    check(micro[361]["formulas"][0].get("plain") == "AWCD=Σ(A_i−A_A1)/95", "microbiome: AWCD formula", failures)
    check(len(micro[362]["formulas"]) == 6, "microbiome: diversity formula count", failures)
    check(
        micro[362]["formulas"][-1].get("latex") == r"E=\frac{N-U}{N-N/\sqrt{S}}",
        "microbiome: McIntosh evenness formula",
        failures,
    )
    check(
        any(row == ["KH₂PO₄", "2.65 g"] for row in micro[365]["tables"][0]["rows"]),
        "microbiome: phosphate buffer subscripts",
        failures,
    )
    technical = records_by_book["soil-analysis-spec-2e-2006"]
    check(
        any(formula.get("plain") == "c(C₁₀H₁₄O₈N₂Na₂·2H₂O)=0.02 mol·L⁻¹" for formula in technical[116]["formulas"]),
        "technical-spec: EDTA disodium dihydrate subscripts",
        failures,
    )
    check(
        any(formula.get("plain") == "砷(As)，mg·kg⁻¹=m₁/m" for formula in technical[192]["formulas"]),
        "technical-spec: arsenic symbol correction",
        failures,
    )
    check(
        any(formula.get("plain") == "水溶态氟，mg·kg⁻¹=ρV/m" for formula in technical[207]["formulas"]),
        "technical-spec: water-soluble fluoride denominator",
        failures,
    )
    check(
        any(formula.get("plain") == "ρ((NH₄)₆Mo₇O₂₄·4H₂O)=10 g·L⁻¹" for formula in technical[218]["formulas"]),
        "technical-spec: ammonium molybdate formula",
        failures,
    )
    check(
        any(formula.get("plain") == "t=(X̄₁−X̄₂)/S_d" for formula in technical[244]["formulas"]),
        "technical-spec: paired t-test denominator",
        failures,
    )
    check(
        any(formula.get("plain") == "S_wb=√{[ΣXᵢ²−(ΣXᵢ)²/n]/[m(n−1)]}" for formula in technical[241]["formulas"]),
        "technical-spec: whole-process blank standard deviation",
        failures,
    )
    check(
        any(formula.get("plain") == "ρ_B=m_B·V⁻¹" for formula in technical[248]["formulas"]),
        "technical-spec: mass concentration symbol rho",
        failures,
    )

    result = {"sources": summary, "failureCount": len(failures), "failures": failures}
    if config.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for row in summary:
            print(
                f"{row['bookId']}: {row['includedPageCount']} pages "
                f"ready={str(row['runtimeReady']).lower()}"
            )
        print(f"failures={len(failures)}")
        for failure in failures[:50]:
            print(failure)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

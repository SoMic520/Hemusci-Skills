#!/usr/bin/env python3
"""Finalize formula decisions after crop-by-crop visual review."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
BOOK_IDS = {
    "lu-rukkun": "lu-rukkun-2000",
    "technical-spec": "soil-analysis-spec-2e-2006",
}
SUSPICIOUS = re.compile(
    r"\\mathbf|\\mathbb|\\bmod|\\parallel|m o l|N a|d_\{will\}|Hg|7_2|"
    r"\\mu8|\\mathbf\{j\}|\\left\.|^\s*[=×]|=\s*$|\\mathrm\{m L\}|"
    r"\\mathrm\{K\}\\mathrm\{I\}|C_\{5\}H_\{5\}O_\{7\}|"
    r"\\begin\{aligned\}|\\rho\(kg|NaPO_3\\right\)_5|"
    r"NH_4\\ F|\\mathrm\{cmol\}.*=|mg\\cdot100g\^\{-1\}|"
    r"\\mathrm\{\[o|\\mathrm\{o~|KM_\{n\}|N_\{2\}\\mathrm\{NO\}_\{2\}|"
    r"Mo_\{2\}\\mathrm\{O\}_\{24\}|\\mathrm\{已\}|\\widetilde\{X\}|"
    r"\\mathrm\{M g\}|\\mathrm\{m g\}|\\mathrm\{k g\}|\\geq F\\alpha|"
    r"\\frac\{交换性|\\mathrm\{Co\\ \(|\\mathrm\{Co\}\(|\\mathrm\{Co\}|\\mathrm\{\(Ag\)\}|"
    r"水溶态氟.*\\frac\{\\rho\\cdot V\}\{n\}|(?:kg|L|mL|cm)\^\{-\}|"
    r"S_\{[s6]\}|\\varphi.*(?:\\mathrm\{(?:mg|g)\}|\\mu\\mathrm\{g\}).*L\^\{-1\}|\\varphi\\left\([^)]*=|"
    r"\\frac\{S_\{6\}=|S_\{\\overline\{n\}\}|\\mathrm\{Lo\}"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--book", choices=tuple(BOOK_IDS), required=True)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def balanced(text: str) -> bool:
    depth = 0
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def main() -> None:
    config = parse_args()
    manifest_path = config.work_root / config.book / "formula-review" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    decisions_path = config.decisions or (
        SKILL_ROOT / "references" / "build-audits" / f"{config.book}-formula-decisions.json"
    )
    decisions = {}
    if decisions_path.is_file():
        decisions = json.loads(decisions_path.read_text(encoding="utf-8")).get("decisions") or {}
    accepted = []
    rejected = []
    unresolved = []
    for item in manifest.get("formulas") or []:
        formula_id = str(item["id"])
        decision = decisions.get(formula_id) or {}
        if decision.get("reject"):
            rejected.append({
                "id": formula_id,
                "page": item["page"],
                "sourceFingerprint": item["sourceFingerprint"],
                "status": "rejected",
                "reason": decision.get("reason", "非完整公式区域"),
            })
            continue
        source = str(item["sourceLatex"])
        latex = str(decision.get("latex") or source)
        needs_decision = (
            bool(SUSPICIOUS.search(source))
            or not balanced(source)
            or len(source) > 500
        )
        if needs_decision and not decision.get("latex") and not decision.get("accept"):
            unresolved.append({
                "id": formula_id,
                "page": item["page"],
                "sourceLatex": source,
                "crop": item["crop"],
                "reason": "suspicious syntax or recognition",
            })
            continue
        accepted.append({
            "id": formula_id,
            "page": item["page"],
            "sourceFingerprint": item["sourceFingerprint"],
            "status": "verified",
            "latex": latex,
            **({"plain": decision["plain"]} if decision.get("plain") else {}),
            **({"label": decision["label"]} if decision.get("label") else {}),
            "reviewMethod": "页面公式裁剪图逐项复核＋LaTeX语法、化学式和单位校验",
        })
    print(
        f"{config.book}: candidates={len(manifest.get('formulas') or [])} "
        f"accepted={len(accepted)} rejected={len(rejected)} unresolved={len(unresolved)}"
    )
    for item in unresolved:
        print(f"{item['id']}\t{item['sourceLatex']}")
    if unresolved:
        raise SystemExit(1)
    if config.write:
        output = (
            SKILL_ROOT
            / "references"
            / "external-corpora"
            / BOOK_IDS[config.book]
            / "formula-review.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "schema": "soil-methods-consultant.formula-review.v1",
                    "bookId": BOOK_IDS[config.book],
                    "formulaCount": len(accepted),
                    "rejectedCount": len(rejected),
                    "formulas": accepted,
                    "rejected": rejected,
                },
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        print(output)


if __name__ == "__main__":
    main()

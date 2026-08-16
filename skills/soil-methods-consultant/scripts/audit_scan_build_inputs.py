#!/usr/bin/env python3
"""Audit multi-engine build inputs for the two scanned monographs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from build_external_corpora import apply_scan_page_repairs, clean_vision_line, vision_path
from prepare_formula_reviews import FORCED_FORMULA_IDS, fingerprint, normalize


BOOKS = {
    "lu-rukkun": 665,
    "technical-spec": 267,
}
KNOWN_OCR_ERRORS = re.compile(
    r"士壤|土壞|土壊|士样|取士|砂士|黏士|壤士|加人|放人|移人|转人|插人|并人|"
    r"范團|范圃|溯定|镂态|重铭酸|HC1|KC1|NaC1|BaCL|CaCL|NH[₄4]C1|HONH₃C1|AgC1|C1-|AI-P|Superfloc[lI]27|H₂SO[4₄]o|(?:mo[I1]|mmo1|cmo1)(?=[·（(])|g·cm³|(?:无|有)C1|(?<=\d)(?:pg|yg|wg|ug)(?=·|/|mL|L)|"
    r"(?<=\d)(?:ml|mI)(?=[^A-Za-z]|$)|mol·L[.·]?[—一~～\-']|℃[土士]\d|min[土士]\d"
    r"|(?<=\d)μl\b|/ml\b|(?:mol|mmol|μmol|nmol|g|mg|μg|ng)·I|(?:g|mg|μg|ng)·kg(?:[-−—一~～]?[12Il\]²T™])?(?=[^⁻])|g·mL[-−—一~～][²2]|=[Il]\s*mol|10[-−]\d(?=(?:\s|的|稀释|倍|～|~|至|$))"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--require-paddle", action="store_true")
    parser.add_argument("--require-formula-review", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def load_lines(path: Path) -> list[dict]:
    return list(json.loads(path.read_text(encoding="utf-8")).get("lines") or [])


def chinese_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def meaningful_formula(latex: str) -> bool:
    return len(latex) >= 9 and any(
        marker in latex for marker in ("=", r"\approx", r"\geq", r"\leq")
    )


def main() -> None:
    config = parse_args()
    failures: list[str] = []
    summaries = []
    for book, page_count in BOOKS.items():
        work = config.work_root / book
        missing_paddle = 0
        anomalies = 0
        ratio_flags = 0
        formula_candidates = 0
        formula_verified = 0
        review_path = (
            Path(__file__).resolve().parents[1]
            / "references"
            / "external-corpora"
            / ("lu-rukkun-2000" if book == "lu-rukkun" else "soil-analysis-spec-2e-2006")
            / "formula-review.json"
        )
        reviewed = {}
        if review_path.is_file():
            review_payload = json.loads(review_path.read_text(encoding="utf-8"))
            reviewed = {
                str(item.get("id")): item
                for item in [
                    *(review_payload.get("formulas") or []),
                    *(review_payload.get("rejected") or []),
                ]
            }
        for page in range(1, page_count + 1):
            vision_file = vision_path(work / "vision", page)
            if not vision_file.is_file():
                failures.append(f"{book}:{page}: missing Vision")
                continue
            tesseract_file = work / "tesseract" / f"page-{page:03d}.txt"
            if not tesseract_file.is_file():
                failures.append(f"{book}:{page}: missing Tesseract")
            vision_lines = load_lines(vision_file)
            paddle_file = vision_path(work / "paddle", page)
            if not paddle_file.is_file():
                missing_paddle += 1
                if config.require_paddle:
                    failures.append(f"{book}:{page}: missing PaddleOCR")
                selected = vision_lines
            else:
                paddle_lines = load_lines(paddle_file)
                vision_chars = chinese_count("\n".join(str(item.get("text") or "") for item in vision_lines))
                paddle_chars = chinese_count("\n".join(str(item.get("text") or "") for item in paddle_lines))
                if vision_chars >= 80 and paddle_chars < int(vision_chars * 0.65):
                    ratio_flags += 1
                    failures.append(
                        f"{book}:{page}: Paddle/Vision Chinese coverage {paddle_chars}/{vision_chars}"
                    )
                selected = paddle_lines
            corrected_blocks = [
                {"text": clean_vision_line(str(item.get("text") or ""))}
                for item in selected
                if str(item.get("text") or "").strip()
            ]
            _, corrected = apply_scan_page_repairs(
                "lu-rukkun-2000" if book == "lu-rukkun" else "soil-analysis-spec-2e-2006",
                page,
                corrected_blocks,
            )
            if chinese_count(corrected) == 0 and len(re.findall(r"[A-Za-z0-9]", corrected)) < 50 and page > 15:
                failures.append(f"{book}:{page}: empty text body")
            found = sorted(set(KNOWN_OCR_ERRORS.findall(corrected)))
            if found:
                anomalies += len(found)
                failures.append(f"{book}:{page}: residual OCR tokens {found[:8]}")
            formula_file = vision_path(work / "formula", page)
            if formula_file.is_file():
                payload = json.loads(formula_file.read_text(encoding="utf-8"))
                for index, item in enumerate(payload.get("formulas") or [], 1):
                    latex = normalize(str(item.get("rec_formula") or ""))
                    formula_id = f"P{page}-F{index}"
                    if not meaningful_formula(latex) and formula_id not in FORCED_FORMULA_IDS[book]:
                        continue
                    formula_candidates += 1
                    review = reviewed.get(formula_id) or {}
                    expected_fingerprint = fingerprint(latex, item.get("dt_polys") or [])
                    if (
                        review.get("status") in {"verified", "rejected"}
                        and review.get("sourceFingerprint") == expected_fingerprint
                    ):
                        formula_verified += 1
                    elif config.require_formula_review:
                        failures.append(f"{book}:{formula_id}: formula not verified or stale fingerprint")
        summaries.append({
            "book": book,
            "pages": page_count,
            "missingPaddle": missing_paddle,
            "coverageFlags": ratio_flags,
            "residualOcrTokens": anomalies,
            "formulaCandidates": formula_candidates,
            "formulaVerified": formula_verified,
        })
    result = {"sources": summaries, "failureCount": len(failures), "failures": failures}
    if config.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for row in summaries:
            print(
                f"{row['book']}: pages={row['pages']} paddle-missing={row['missingPaddle']} "
                f"coverage-flags={row['coverageFlags']} OCR-flags={row['residualOcrTokens']} "
                f"formulas={row['formulaVerified']}/{row['formulaCandidates']}"
            )
        print(f"failures={len(failures)}")
        for failure in failures[:100]:
            print(failure)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

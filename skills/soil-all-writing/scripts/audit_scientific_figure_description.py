#!/usr/bin/env python3
"""Audit Chinese scientific-figure prose against a task-local evidence manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
TASK_MODES = {"results_paragraph", "figure_legend", "figure_title", "reading_explanation", "discussion"}
SOURCE_KINDS = {"image_only", "image_plus_legend", "image_plus_statistics", "raw_data"}
QUANTITY_KINDS = {
    "concentration_or_content", "stock", "flux", "rate", "ratio", "count",
    "index", "probability", "other",
}
REFERENCE_ROLES = {"visual_aid", "validated_threshold", "target", "other"}
LOCATOR_STYLES = {"free", "content_first_locator_later", "lead_locator_allowed", "venue_controlled"}
BLANK_CELL_POLICIES = {"free", "omit_unless_material", "report_material", "report_all"}
VISUALIZATION_TYPES = {
    "other", "scientific_table", "bar", "box_or_violin", "line_or_time_series",
    "interaction_plot", "scatter_or_regression", "ordination", "heatmap", "map",
    "soil_profile", "forest_plot", "sem_path",
}
COMPARISON_STRUCTURES = {
    "descriptive", "direct_group", "within_stratum", "interaction", "association",
    "reference_contrast", "prediction",
}


def validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if manifest.get("task_mode") not in TASK_MODES:
        errors.append("task_mode is not controlled")
    if manifest.get("source_kind") not in SOURCE_KINDS:
        errors.append("source_kind is not controlled")
    for field in (
        "image_has_alpha", "raw_data_available", "statistical_output_available",
        "experimental_design_verified", "allow_visual_numeric_estimates", "legend_available",
    ):
        if not isinstance(manifest.get(field), bool):
            errors.append(f"{field} must be boolean")
    backgrounds = manifest.get("contrast_backgrounds_checked")
    if not isinstance(backgrounds, list) or not all(item in {"white", "black"} for item in backgrounds):
        errors.append("contrast_backgrounds_checked must contain only white/black")
    elif len(set(backgrounds)) != len(backgrounds):
        errors.append("contrast_backgrounds_checked contains duplicates")
    symbols = manifest.get("figure_symbols")
    if not isinstance(symbols, list) or not all(isinstance(item, str) and item for item in symbols):
        errors.append("figure_symbols must be a string array")
    symbol_map = manifest.get("significance_symbol_map")
    if not isinstance(symbol_map, dict) or not all(
        isinstance(key, str) and key and isinstance(value, str) and value
        for key, value in symbol_map.items()
    ):
        errors.append("significance_symbol_map must be a string-to-string object")
    elif isinstance(symbols, list) and not set(symbol_map).issubset(set(symbols)):
        errors.append("significance_symbol_map contains a symbol absent from figure_symbols")
    for field in ("reported_conditions", "group_labels"):
        value = manifest.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            errors.append(f"{field} must be a string array")
    for field in ("comparison_strata", "mechanism_evidence"):
        value = manifest.get(field, [])
        if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
            errors.append(f"{field} must be a string array when supplied")
    if not isinstance(manifest.get("missingness_analysis_requested", False), bool):
        errors.append("missingness_analysis_requested must be boolean when supplied")
    if manifest.get("locator_style", "free") not in LOCATOR_STYLES:
        errors.append("locator_style is not controlled")
    if manifest.get("blank_cell_policy", "free") not in BLANK_CELL_POLICIES:
        errors.append("blank_cell_policy is not controlled")
    if not isinstance(manifest.get("blank_cells_material", False), bool):
        errors.append("blank_cells_material must be boolean when supplied")
    if manifest.get("visualization_type", "other") not in VISUALIZATION_TYPES:
        errors.append("visualization_type is not controlled")
    if manifest.get("comparison_structure", "descriptive") not in COMPARISON_STRUCTURES:
        errors.append("comparison_structure is not controlled")
    for field in (
        "within_stratum_contrasts_available", "equivalence_test_available",
        "prediction_uncertainty_available",
    ):
        if not isinstance(manifest.get(field, False), bool):
            errors.append(f"{field} must be boolean when supplied")
    reference_markers = manifest.get("reference_markers", [])
    if not isinstance(reference_markers, list):
        errors.append("reference_markers must be an array when supplied")
    else:
        for index, marker in enumerate(reference_markers):
            if not isinstance(marker, dict):
                errors.append(f"reference_markers[{index}] must be an object")
                continue
            if not isinstance(marker.get("value"), (int, float, str)):
                errors.append(f"reference_markers[{index}].value must be numeric or string")
            if not isinstance(marker.get("unit"), str):
                errors.append(f"reference_markers[{index}].unit must be a string")
            if marker.get("role") not in REFERENCE_ROLES:
                errors.append(f"reference_markers[{index}].role is not controlled")
            if not isinstance(marker.get("contrast_tested"), bool):
                errors.append(f"reference_markers[{index}].contrast_tested must be boolean")
    quantity = manifest.get("measured_quantity")
    if not isinstance(quantity, dict):
        errors.append("measured_quantity must be an object")
    else:
        if not isinstance(quantity.get("name"), str):
            errors.append("measured_quantity.name must be a string")
        if quantity.get("quantity_kind") not in QUANTITY_KINDS:
            errors.append("measured_quantity.quantity_kind is not controlled")
        if not isinstance(quantity.get("unit"), str):
            errors.append("measured_quantity.unit must be a string")
    char_range = manifest.get("requested_char_range")
    if char_range is not None:
        if not isinstance(char_range, dict):
            errors.append("requested_char_range must be null or an object")
        else:
            minimum = char_range.get("min")
            maximum = char_range.get("max")
            if not isinstance(minimum, int) or minimum < 0:
                errors.append("requested_char_range.min must be a non-negative integer")
            if not isinstance(maximum, int) or not isinstance(minimum, int) or maximum < minimum:
                errors.append("requested_char_range.max must be an integer not smaller than min")
    return errors


def add(findings: list[dict], code: str, message: str, match: str = "") -> None:
    finding = {"code": code, "severity": "error", "message": message}
    if match:
        finding["match"] = match
    findings.append(finding)


def first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(0) if match else ""


def first_non_negated_match(pattern: str, text: str, window: int = 16) -> str:
    """Return the first match that is not part of an explicit scope denial."""
    denial = re.compile(
        r"(?:不|未|无|非|不能|不得|无法|不足以|不应)"
        r"(?:据此)?(?:说明|证明|表明|推断|代表|等同于|换算为|写为)?"
        r"[^，。；！？]{0,8}$"
    )
    for match in re.finditer(pattern, text, re.IGNORECASE):
        prefix = text[max(0, match.start() - window):match.start()]
        if denial.search(prefix):
            continue
        return match.group(0)
    return ""


def normalize_p_notation(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("＜", "<").replace("＞", ">").upper()


def has_authorized_p_value(manifest: dict, observed: str) -> bool:
    if manifest.get("statistical_output_available"):
        return True
    mapping = manifest.get("significance_symbol_map", {})
    normalized_observed = normalize_p_notation(observed)
    return any(
        normalize_p_notation(value) == normalized_observed
        for value in mapping.values()
        if re.search(r"[Pp]\s*[<=>≤≥＜＞]", value)
    )


def normalized_range(value: str) -> tuple[float, float] | None:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*[-–—～~]\s*(\d+(?:\.\d+)?)\s*", value)
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def audit(text: str, manifest: dict) -> list[dict]:
    findings: list[dict] = []
    task_mode = manifest.get("task_mode")
    if manifest.get("image_has_alpha"):
        checked = set(manifest.get("contrast_backgrounds_checked", []))
        if checked != {"white", "black"}:
            add(
                findings, "SFD001",
                "Transparent figures must be inspected on both white and black backgrounds before interpretation.",
            )
    if task_mode == "results_paragraph":
        match = first_match(
            r"^\s*(?:由\s*)?(?:图|表)\s*[0-9A-Za-z一二三四五六七八九十.\-—–]*\s*"
            r"(?:中|可知|显示|表明)",
            text,
        )
        if match and manifest.get("locator_style", "free") == "content_first_locator_later":
            add(
                findings, "SFD015",
                "Lead with the scientific object or comparison and place the figure/table locator later.",
                match,
            )
        match = first_match(
            r"(?:清晰|清楚)(?:的)?(?:梯度|差异|趋势|分离|排序)|"
            r"(?:梯度|差异|趋势|分离|排序).{0,4}(?:清晰|清楚)|"
            r"明显(?:的)?(?:增加|升高|降低|减少|差异|趋势)",
            text,
        )
        if match:
            add(findings, "SFD002", "Replace subjective visual appraisal with the direct group relation.", match)
        match = first_match(r"(?:两两|组间)比较结果(?:表明|显示|可见)", text)
        if match:
            add(findings, "SFD003", "Report the contrasts and statistical evidence directly.", match)
        match = first_match(r"在本(?:试验|实验|研究)条件下", text)
        if match:
            conditions = manifest.get("reported_conditions", [])
            missing_conditions = [condition for condition in conditions if condition not in text]
            if not conditions or missing_conditions:
                add(
                    findings, "SFD004",
                    "A condition hedge is valid only when the actual limiting conditions are stated in the sentence.",
                    match,
                )
        match = first_match(
            r"箱体表示(?:四分位距|第?25.{0,4}75百分位数)|"
            r"中线表示中位数|散点(?:为|表示)独立观测值",
            text,
        )
        if match:
            add(findings, "SFD005", "Figure-encoding instructions belong in the legend, not the results paragraph.", match)
    if (
        not manifest.get("raw_data_available")
        and not manifest.get("statistical_output_available")
        and not manifest.get("allow_visual_numeric_estimates")
    ):
        match = first_match(
            r"(?:中位数|均值|四分位数|平均值)(?:分别)?(?:约为|为|=).{0,40}\d|"
            r"(?:较|比).{0,12}(?:高|低|增加|减少)约?\s*\d",
            text,
        )
        if match:
            add(
                findings, "SFD006",
                "Exact or approximate manuscript statistics may not be reconstructed from image pixels without authorization.",
                match,
            )
    p_match = first_match(r"[Pp]\s*[＜＞<>≤≥=]\s*0?\.\d+", text)
    if p_match and not has_authorized_p_value(manifest, p_match):
        add(
            findings, "SFD007",
            "The P-value threshold is not defined by the supplied legend or verified statistical output.",
            p_match,
        )
    for marker in manifest.get("reference_markers", []):
        if marker.get("role") != "visual_aid" or marker.get("contrast_tested"):
            continue
        value = re.escape(str(marker.get("value")))
        unit = re.escape(marker.get("unit", ""))
        marker_present = re.search(rf"{value}\s*{unit}", text, re.IGNORECASE)
        threshold_claim = first_match(
            r"(?:高于|低于|超过|未达到|越过|位于).{0,18}(?:参考值|参考线|阈值)(?:之上|之下)?|"
            r"(?:参考值|参考线|阈值).{0,12}(?:以上|以下|之上|之下|高于|低于|超过)",
            text,
        )
        if marker_present and threshold_claim:
            add(
                findings, "SFD016",
                "A visual reference line is not a tested threshold; do not turn it into an inferential result.",
                threshold_claim,
            )
            break
    strata = [normalized_range(item) for item in manifest.get("comparison_strata", [])]
    strata = [item for item in strata if item is not None]
    if len(strata) >= 2:
        exact = set(strata)
        for match in re.finditer(
            r"(\d+(?:\.\d+)?)\s*[-–—～~]\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)?\s*土层",
            text,
            re.IGNORECASE,
        ):
            span = (float(match.group(1)), float(match.group(2)))
            contained = [item for item in strata if item[0] >= span[0] and item[1] <= span[1]]
            if span not in exact and len(contained) >= 2:
                add(
                    findings, "SFD017",
                    "Do not collapse separately analysed depth intervals into one continuous soil layer.",
                    match.group(0),
                )
                break
    quantity_kind = manifest.get("measured_quantity", {}).get("quantity_kind")
    if quantity_kind == "concentration_or_content":
        match = first_non_negated_match(r"(?:碳积累|碳储量|碳库|碳固存|固碳量)", text)
        if match:
            add(
                findings, "SFD008",
                "A concentration/content figure does not by itself establish accumulation, stock, pool size, or sequestration.",
                match,
            )
    if not manifest.get("experimental_design_verified"):
        match = first_match(
            r"(?:施用|添加|应用).{0,18}(?:提高|增加|降低|减少|促进|导致|造成)|"
            r"(?:堆肥|生物炭|处理)(?:显著)?(?:提高|增加|降低|减少|促进|导致)|"
            r"(?:堆肥|生物炭|处理).{0,12}有利于",
            text,
        )
        if match:
            add(
                findings, "SFD009",
                "Use a group contrast until the experimental unit, allocation, and causal design are verified.",
                match,
            )
    if task_mode == "results_paragraph":
        match = first_match(
            r"提升幅度|数据主体|总体排序|组间排序|"
            r"处理效应强于|提高作用强于|效果(?:更好|更强)",
            text,
        )
        if match:
            add(
                findings, "SFD010",
                "Name the statistic or direct group relation instead of using a generic summary label.",
                match,
            )
        match = first_match(r"(?:结果表明|这说明|由此可见).{0,30}(?:机制|通过|由于|归因于)", text)
        if match:
            add(findings, "SFD011", "A figure-results paragraph may not invent a mechanism.", match)
        match = first_match(r"(?:呈|表现为).{0,6}(?:递增|递减|梯度)(?:趋势|变化|差异)?", text)
        if match:
            add(
                findings, "SFD014",
                "Do not describe unordered treatment categories as a trend or gradient; state the group contrasts.",
                match,
            )
        labels = [label for label in manifest.get("group_labels", []) if label in text]
        comparison = re.search(r"高于|低于|不高于|不低于|无显著差异|差异未达到统计学显著水平", text)
        if len(manifest.get("group_labels", [])) >= 2 and (len(labels) < 2 or not comparison):
            add(
                findings, "SFD012",
                "A results paragraph must state at least one direct contrast between named groups.",
            )
        if (
            manifest.get("blank_cell_policy", "free") == "omit_unless_material"
            and not manifest.get("blank_cells_material", False)
            and not manifest.get("missingness_analysis_requested", False)
        ):
            match = first_match(
                r"(?:缺少|未列示|未提供).{0,24}(?:数据|数值|指标|效率|回收率)|"
                r"(?:缺少|未列示|未提供).{0,30}(?:不能|无法).{0,10}(?:完整)?比较",
                text,
            )
            if match:
                add(
                    findings, "SFD020",
                    "Do not narrate blank table cells unless missingness itself is requested or affects the claim.",
                    match,
                )
    visualization_type = manifest.get("visualization_type", "other")
    if visualization_type == "ordination" and not manifest.get("statistical_output_available"):
        match = first_match(r"显著(?:分离|分开|区分|差异)|分离(?:达到)?显著", text)
        if match:
            add(
                findings, "SFD021",
                "Ordination geometry alone does not establish statistical separation; require a named test and output.",
                match,
            )
    if (
        manifest.get("comparison_structure") == "interaction"
        and not manifest.get("within_stratum_contrasts_available", False)
    ):
        match = first_match(
            r"(?:所有|全部|各个|各).{0,8}(?:时间|时期|深度|水平|土层).{0,18}"
            r"(?:均|始终|一致).{0,8}(?:高于|低于|增加|降低)",
            text,
        )
        if match:
            add(
                findings, "SFD022",
                "A significant interaction does not authorize uniform within-stratum contrasts without simple-effect results.",
                match,
            )
    if not manifest.get("equivalence_test_available", False):
        match = first_match(
            r"(?:差异不显著|未达到统计学显著水平).{0,24}"
            r"(?<!不能)(?<!无法)(?:说明|表明|证明).{0,12}"
            r"(?:无效|没有作用|完全相同|等效)|(?:无效|没有作用|完全相同|等效).{0,20}"
            r"(?:P|p)\s*[＞>]",
            text,
        )
        if match:
            add(
                findings, "SFD023",
                "Non-significance is not equivalence or evidence of no effect without an equivalence/non-inferiority design.",
                match,
            )
    if visualization_type == "map" and not manifest.get("prediction_uncertainty_available", False):
        match = first_match(
            r"(?:未采样|无采样|样点之外|插值区域).{0,24}(?:为|达到|等于)\s*\d+(?:\.\d+)?",
            text,
        )
        if match:
            add(
                findings, "SFD024",
                "Do not present an interpolated unsampled location as an exact observation without prediction uncertainty.",
                match,
            )
    if task_mode == "discussion":
        if not manifest.get("mechanism_evidence", []):
            match = first_match(
                r"(?:这|该结果|上述差异).{0,6}(?:说明|证实).{0,30}(?:通过|由于|机制)|"
                r"(?:主要|完全|直接)(?:归因于|由于)|(?:原因|机制)(?:是|在于)",
                text,
            )
            if match:
                add(
                    findings, "SFD018",
                    "Without direct process evidence, present a mechanism as a bounded hypothesis, not a conclusion.",
                    match,
                )
        match = first_match(
            r"(?:校正|控制|纳入).{0,20}(?:排除|消除).{0,14}(?:含水量|协变量|混杂)|"
            r"(?:排除|消除).{0,14}(?:含水量|协变量|混杂).{0,10}(?:影响|作用)",
            text,
        )
        if match:
            add(
                findings, "SFD019",
                "Covariate adjustment supports a common-level comparison; it does not eliminate the variable or all confounding.",
                match,
            )
    char_range = manifest.get("requested_char_range")
    if isinstance(char_range, dict):
        count = len(text.strip())
        if count < char_range["min"] or count > char_range["max"]:
            add(
                findings, "SFD013",
                f"Character count {count} is outside {char_range['min']}–{char_range['max']}.",
            )
    return findings


def read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"line {line_number} must be an object")
        records.append(record)
    return records


def validate_cases(path: Path) -> int:
    errors: list[str] = []
    try:
        cases = read_jsonl(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    seen: set[str] = set()
    pass_count = 0
    fail_count = 0
    covered_codes: set[str] = set()
    for index, case in enumerate(cases, 1):
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(f"case {index}: case_id must be non-empty")
            continue
        if case_id in seen:
            errors.append(f"{case_id}: duplicate case id")
        seen.add(case_id)
        manifest = case.get("manifest")
        text = case.get("text")
        expected = case.get("expected")
        required_codes = case.get("required_codes")
        if not isinstance(manifest, dict):
            errors.append(f"{case_id}: manifest must be an object")
            continue
        manifest_errors = validate_manifest(manifest)
        if manifest_errors:
            errors.extend(f"{case_id}: manifest {error}" for error in manifest_errors)
            continue
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{case_id}: text must be non-empty")
            continue
        if expected not in {"pass", "fail"}:
            errors.append(f"{case_id}: expected must be pass or fail")
            continue
        if not isinstance(required_codes, list) or not all(
            isinstance(code, str) and re.fullmatch(r"SFD\d{3}", code) for code in required_codes
        ):
            errors.append(f"{case_id}: required_codes must be an SFD code array")
            continue
        findings = audit(text, manifest)
        codes = {finding["code"] for finding in findings}
        missing = set(required_codes) - codes
        if missing:
            errors.append(f"{case_id}: missing required findings {', '.join(sorted(missing))}")
        if expected == "pass":
            pass_count += 1
            if findings:
                errors.append(f"{case_id}: expected pass but found {', '.join(sorted(codes))}")
        else:
            fail_count += 1
            if not findings:
                errors.append(f"{case_id}: expected failure but no finding was emitted")
            covered_codes.update(codes)
    required_failure_codes = {f"SFD{index:03d}" for index in range(1, 25)}
    missing_coverage = required_failure_codes - covered_codes
    if missing_coverage:
        errors.append(f"case corpus does not cover {', '.join(sorted(missing_coverage))}")
    if pass_count < 18 or fail_count < 26:
        errors.append("case corpus requires at least 18 pass and 26 fail cases")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} scientific-figure case validation error(s)")
        return 1
    print(
        f"PASS: scientific-figure description cases are valid; pass={pass_count}; fail={fail_count}"
    )
    return 0


def audit_command(text_path: Path, manifest_path: Path, report_path: Path | None) -> int:
    try:
        text = text_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    manifest_errors = validate_manifest(manifest)
    findings = [
        {"code": "SFD000", "severity": "error", "message": message}
        for message in manifest_errors
    ]
    if not manifest_errors:
        findings = audit(text, manifest)
    report = {
        "schema_version": 1,
        "character_count": len(text.strip()),
        "error_count": len(findings),
        "release_status": "blocked" if findings else "clear",
        "findings": findings,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if report_path:
        report_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if findings else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser("audit", help="audit one text against one evidence manifest")
    audit_parser.add_argument("text", type=Path)
    audit_parser.add_argument("--manifest", required=True, type=Path)
    audit_parser.add_argument("--report", type=Path)
    cases_parser = subparsers.add_parser("validate-cases", help="run the frozen case corpus")
    cases_parser.add_argument(
        "cases", nargs="?", type=Path,
        default=ROOT / "assets/scientific-figure-description-cases.jsonl",
    )
    args = parser.parse_args()
    if args.command == "validate-cases":
        return validate_cases(args.cases)
    if args.command == "audit":
        return audit_command(args.text, args.manifest, args.report)
    return 2


if __name__ == "__main__":
    sys.exit(main())

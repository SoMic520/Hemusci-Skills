#!/usr/bin/env python3
"""Profile a tabular dataset and recommend defensible figure recipes.

The script is deliberately conservative: it never performs an inferential test,
never overwrites the source table and never treats technical rows as independent n.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "references" / "input-schemas.tsv"
REGISTRY = ROOT / "references" / "generated" / "recipe-registry.tsv"

ALIASES: dict[str, tuple[str, ...]] = {
    "sample_id": ("sample", "sampleid", "sample_id", "id", "observation_id"),
    "observation_id": ("observation_id", "observation", "row_id", "sample_id", "id"),
    "profile_id": ("profile_id", "profile", "core_id", "pedon_id", "sample_id"),
    "group": ("group", "treatment", "condition", "site", "class"),
    "value": ("value", "measurement", "response", "concentration", "abundance"),
    "block": ("block", "block_id", "plot", "replicate"),
    "subject_id": ("subject", "subject_id", "individual", "core_id", "profile_id"),
    "time": ("time", "timepoint", "date", "day", "month", "year"),
    "x": ("x", "predictor", "longitude", "lon", "easting"),
    "y": ("y", "outcome", "latitude", "lat", "northing"),
    "estimate": ("estimate", "effect", "coefficient", "mean_difference"),
    "lower": ("lower", "lcl", "ci_lower", "lower_ci"),
    "upper": ("upper", "ucl", "ci_upper", "upper_ci"),
    "label": ("label", "term", "name"),
    "component": ("component", "taxon", "fraction", "part", "species"),
    "row_id": ("row_id", "row", "feature", "feature_id"),
    "column_id": ("column_id", "column", "variable"),
    "observed": ("observed", "measured", "actual", "truth"),
    "predicted": ("predicted", "prediction", "fitted", "estimate_model"),
    "feature_id": ("feature_id", "feature", "gene", "taxon", "otu", "asv"),
    "log2_fold_change": ("log2_fold_change", "log2fc", "logfc"),
    "p_value": ("p_value", "pvalue", "pval", "p"),
    "top_cm": ("top_cm", "depth_top", "top", "upper_depth"),
    "bottom_cm": ("bottom_cm", "depth_bottom", "bottom", "lower_depth"),
    "property": ("property", "soil_property", "variable"),
    "part_a": ("part_a", "sand", "clay"),
    "part_b": ("part_b", "silt"),
    "part_c": ("part_c", "clay", "sand"),
}

SOURCE_URLS = {
    "P-JAMBOR-2025": "https://www.nature.com/articles/s41556-025-01684-z",
    "P-REVEAL-2019": "https://pubmed.ncbi.nlm.nih.gov/31657957/",
    "P-RAINCLOUD": "https://pmc.ncbi.nlm.nih.gov/articles/PMC6480976/",
    "P-ESTIMATION": "https://pubmed.ncbi.nlm.nih.gov/31217592/",
    "P-SOIL-R-2025": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12202774/",
    "R-CTVS": "https://cran.r-project.org/web/views/",
    "R-CTV-SPATIAL": "https://cran.r-project.org/web/views/Spatial.html",
    "R-CTV-COMP": "https://cran.r-project.org/web/views/CompositionalData.html",
    "R-AQP": "https://ncss-tech.github.io/aqp/",
}


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]], str]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel_tab if path.suffix.lower() == ".tsv" else csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("The table has no header row")
    headers = [str(item).strip() for item in reader.fieldnames]
    rows = [{str(k).strip(): ("" if v is None else str(v).strip()) for k, v in row.items()} for row in reader]
    if not rows:
        raise ValueError("The table contains no data rows")
    return headers, rows, dialect.delimiter


def is_number(value: str) -> bool:
    try:
        number = float(value)
        return math.isfinite(number)
    except (TypeError, ValueError):
        return False


def is_date(value: str) -> bool:
    value = value.strip()
    if not re.search(r"[-/]", value):
        return False
    for candidate in (value, value.replace("/", "-")):
        try:
            dt.datetime.fromisoformat(candidate)
            return True
        except ValueError:
            pass
    return False


def profile_columns(headers: list[str], rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for header in headers:
        values = [row.get(header, "") for row in rows]
        present = [value for value in values if value not in ("", "NA", "NaN", "null", ".")]
        numeric_fraction = sum(is_number(value) for value in present) / len(present) if present else 0
        date_fraction = sum(is_date(value) for value in present) / len(present) if present else 0
        inferred = "numeric" if numeric_fraction >= 0.95 else "date/time" if date_fraction >= 0.8 else "categorical/text"
        result.append(
            {
                "column": header,
                "normalized": norm(header),
                "type": inferred,
                "rows": len(rows),
                "missing": len(values) - len(present),
                "missing_fraction": round((len(values) - len(present)) / len(values), 4),
                "unique_non_missing": len(set(present)),
                "numeric_fraction": round(numeric_fraction, 4),
            }
        )
    return result


def canonical_mapping(headers: list[str]) -> tuple[dict[str, str], list[str]]:
    normalized = {norm(header): header for header in headers}
    schema_fields = {
        field
        for schema in load_tsv(SCHEMAS)
        for column_group in (schema["required_columns"], schema["optional_columns"])
        for field in column_group.split(";")
        if field
    }
    mapping: dict[str, str] = {
        canonical: normalized[canonical] for canonical in schema_fields if canonical in normalized
    }
    used = set(mapping.values())
    warnings: list[str] = []
    for canonical, aliases in ALIASES.items():
        if canonical in mapping:
            continue
        hits = [normalized[item] for item in aliases if item in normalized and normalized[item] not in used]
        hits = list(dict.fromkeys(hits))
        if len(hits) == 1:
            mapping[canonical] = hits[0]
            used.add(hits[0])
        elif len(hits) > 1:
            warnings.append(f"Ambiguous mapping for {canonical}: {', '.join(hits)}")
    names = set(normalized)
    if {"sand", "silt", "clay"}.issubset(names):
        mapping.update(part_a=normalized["sand"], part_b=normalized["silt"], part_c=normalized["clay"])
    return mapping, warnings


def match_schemas(mapping: dict[str, str]) -> list[dict[str, Any]]:
    matches = []
    for schema in load_tsv(SCHEMAS):
        required = schema["required_columns"].split(";")
        optional = [column for column in schema["optional_columns"].split(";") if column]
        found = [column for column in required if column in mapping]
        optional_found = [column for column in optional if column in mapping]
        required_fraction = len(found) / len(required)
        optional_fraction = len(optional_found) / len(optional) if optional else 0
        matches.append(
            {
                "schema_id": schema["schema_id"],
                "score": round(required_fraction + 0.03 * optional_fraction, 3),
                "required_score": round(required_fraction, 3),
                "matched": found,
                "missing": [column for column in required if column not in mapping],
                "optional_matched": optional_found,
                "validation_notes": schema["validation_notes"],
            }
        )
    return sorted(
        matches,
        key=lambda item: (-item["score"], len(item["missing"]), -len(item["matched"]), item["schema_id"]),
    )


def row_values(rows: list[dict[str, str]], header: str | None) -> list[str]:
    if not header:
        return []
    return [row.get(header, "") for row in rows if row.get(header, "") not in ("", "NA", "NaN")]


def recommend(
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    schema_matches: list[dict[str, Any]],
    design: str,
    question: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    primary_schema = schema_matches[0]["schema_id"]
    flags: list[str] = []
    choices: list[tuple[str, str, str, list[str]]] = []
    design_lower = design.lower()
    question_lower = question.lower()

    if {"observed", "predicted"}.issubset(mapping):
        choices.append(("observed-predicted", "primary", "Validate agreement on a common scale with a 1:1 reference.", ["Held-out or cross-validated predictions must be identified."]))
    elif {"log2_fold_change", "p_value"}.issubset(mapping):
        choices.append(("volcano-plot", "primary", "Show effect magnitude against model-derived evidence for many features.", ["State multiplicity correction and thresholds; do not infer significance in the renderer."]))
    elif {"part_a", "part_b", "part_c"}.issubset(mapping):
        choices.append(("soil-texture-triangle", "primary", "The three soil fractions form a closed composition.", ["Confirm particle-size system and closure to 100 before classification."]))
    elif {"top_cm", "bottom_cm", "property", "value"}.issubset(mapping):
        choices.append(("soil-depth-profile", "primary", "Preserve horizon support and make depth increase downward.", ["Layers within a profile are dependent observations."]))
    elif {"estimate", "lower", "upper"}.issubset(mapping):
        choices.append(("forest-plot", "primary", "Put estimates and named intervals on a common comparison axis.", ["Declare interval type, level, model and reference value."]))
    elif primary_schema == "time-series":
        recipe = "spaghetti-plot" if "subject_id" in mapping or "repeated" in design_lower else "line-chart"
        choices.append((recipe, "primary", "Respect observed time spacing and show trajectories.", ["Do not connect across structural missing periods."]))
    elif primary_schema == "composition":
        choices.append(("percent-stacked-bar", "primary", "Compare the composition of samples on a common 0–100% scale.", ["Relative abundance cannot establish absolute abundance; record closure and rare-part handling."]))
        choices.append(("stacked-bar", "alternative", "Retain total magnitude when values are not normalized.", ["Middle segments lack a common baseline."]))
    elif primary_schema == "ordination":
        choices.append(("pca-biplot", "primary", "Show plot-ready sample and variable scores in a two-axis ordination.", ["The method, distance/transform and score scaling must come from the analysis, not the renderer."]))
    elif primary_schema == "matrix":
        choices.append(("heatmap", "primary", "Expose structured high-dimensional patterns in a long-form matrix.", ["Record ordering, scaling, clustering and missing-value handling."]))
    elif primary_schema == "matrix-links":
        choices.append(("mantel-correlogram", "primary", "Combine the variable-association matrix with externally supplied, plot-ready Mantel links.", ["Document distance definitions, constrained permutations, multiplicity correction and link cut-points; the renderer does not calculate tests."]))
    elif primary_schema == "network":
        choices.append(("weighted-network", "primary", "Encode supplied edge direction, sign and magnitude without inferring a network.", ["State how edges were estimated, filtered and corrected for multiplicity."]))
        choices.append(("adjacency-matrix", "alternative", "Use a matrix when dense links would create an unreadable node-link hairball.", ["Keep node ordering and zero/absent-edge semantics explicit."]))
    elif primary_schema == "hierarchy":
        recipe = "tree-heatmap" if any(name.startswith("track_") for name in mapping) else "phylogram"
        choices.append((recipe, "primary", "Preserve parent-child structure and align supplied tip annotations when available.", ["Values and tracks must share a documented aggregation and tip order."]))
    elif primary_schema == "hydrochemistry":
        choices.append(("piper-diagram", "primary", "Compare major-ion equivalent composition using a hydrochemical standard diagram.", ["Convert to a documented equivalent basis and verify charge balance before plotting."]))
    elif primary_schema == "ecology-community":
        choices.append(("species-accumulation", "primary", "Show how observed richness changes with explicit sampling effort.", ["Choose permutation or analytical uncertainty at the independent sampling-unit level."]))
    elif primary_schema == "variogram":
        choices.append(("fitted-variogram", "primary", "Compare empirical semivariance with a supplied fitted model.", ["Record lag units, binning, anisotropy, estimator and fitted parameters."]))
    elif primary_schema == "classification":
        choices.append(("roc-curve", "primary", "Evaluate supplied scores across thresholds.", ["Identify the positive class, evaluation split, prevalence and uncertainty; include precision-recall for imbalanced outcomes."]))
        choices.append(("precision-recall", "required-companion", "Expose precision-recall trade-offs when class prevalence is low.", ["Report the baseline prevalence and do not tune and evaluate on the same data."]))
    elif primary_schema == "spectral":
        choices.append(("spectral-signature", "primary", "Compare spectra on their physical wavelength support.", ["State instrument, preprocessing, unit and whether curves are reflectance, absorbance or derivatives."]))
    elif primary_schema == "mcmc":
        choices.append(("trace-plot", "primary", "Inspect chain mixing and stationarity for supplied posterior draws.", ["Report R-hat, ESS, divergences and sampler settings in addition to graphics."]))
    elif primary_schema == "events":
        choices.append(("event-timeline", "primary", "Preserve subject-level event timing and duration.", ["Define the time origin, interval closure and censoring."]))
    elif primary_schema == "survival":
        choices.append(("survival-km", "primary", "Display supplied time-to-event experience by group.", ["Provide risk tables and document status coding, censoring and confidence interval method."]))
    elif primary_schema == "meta-analysis":
        choices.append(("forest-plot", "primary", "Compare study-level effects and uncertainty on a common scale.", ["Declare effect measure, dependence, heterogeneity model and interval type."]))
    elif primary_schema == "multivariate-long":
        choices.append(("parallel-coordinates", "primary", "Compare many variables across samples after explicit scaling.", ["Record scaling, variable order and missing-data handling; avoid unreadable overplotting."]))
    elif primary_schema == "climate":
        choices.append(("walter-lieth", "primary", "Pair monthly temperature and precipitation under an explicit climate-diagram convention.", ["Declare station, reference period, units and missing-month handling."]))
    elif primary_schema == "wind":
        choices.append(("wind-rose", "primary", "Show directional frequency by supplied speed class or magnitude.", ["Declare direction convention, calm handling, bin edges and normalization."]))
    elif primary_schema == "sequence-logo":
        choices.append(("sequence-logo", "primary", "Encode symbol frequency or information content at each sequence position.", ["Verify per-position closure and state background frequencies and weighting."]))
    elif primary_schema == "genomic":
        choices.append(("genome-track", "primary", "Align supplied genomic intervals and values on a named genome build.", ["State coordinate convention, build, strand handling and source analysis."]))
    elif primary_schema == "state-series":
        choices.append(("state-sequence", "primary", "Preserve categorical state trajectories over observed time.", ["Define state semantics, spacing, censoring and structural missing intervals."]))
    elif primary_schema == "hydrology":
        choices.append(("hydrograph", "primary", "Show discharge over its actual temporal support.", ["State catchment support and discharge aggregation; use a separate aligned precipitation panel when needed."]))
    elif primary_schema == "image":
        choices.append(("multichannel-overlay", "primary", "Render supplied calibrated channel intensities without modifying the source image.", ["Retain the original image and record bit depth, channel mapping and all processing."]))
    elif primary_schema == "interpretation":
        choices.append(("shap-beeswarm", "primary", "Display supplied model-attribution values across features.", ["State model, background population and whether values are local or aggregated; attribution is not causation."]))
    elif primary_schema == "spatial-grid" or any(name in mapping for name in ("crs",)) or {norm(v) for v in mapping.values()} & {"longitude", "latitude", "lon", "lat", "easting", "northing"}:
        choices.append(("prediction-map", "primary", "Preserve spatial support for a measured or predicted surface.", ["Record CRS, resolution, support domain and whether values are observations or predictions."]))
        choices.append(("uncertainty-map", "required-companion", "Show model uncertainty or applicability beside predictions.", ["Uncertainty is not an accuracy certificate."]))
    elif primary_schema == "xy":
        choices.append(("scatterplot", "primary", "Show the observation-level relationship without implying causation.", ["Use density/binning rather than opaque overplotting for large n."]))
    elif primary_schema == "categorical":
        paired = any(token in design_lower for token in ("paired", "配对", "block", "区组")) and "block" in mapping
        if paired:
            choices.append(("paired-dotplot", "primary", "Connect the same experimental unit across conditions.", ["Pairing IDs must be complete and unique at the experimental-unit level."]))
        else:
            choices.append(("raincloud-plot", "primary", "Show distribution, robust summary and every observation together.", ["A density shape is unstable at very small group n; retain raw points."]))
            choices.append(("strip-plot", "alternative", "Use a compact raw-data view when density estimation is not justified.", ["Show an explicit summary separately if the question requires one, and identify independent n."]))
    elif primary_schema == "set-membership":
        choices.append(("upset-plot", "primary", "Scale set intersections beyond a small Venn diagram.", ["Define the set universe and empty intersections."]))
    elif primary_schema == "flow":
        choices.append(("alluvial-plot", "primary", "Track categorical paths across explicitly ordered stages.", ["Retain path identity and state whether flows are counts or mass."]))
    else:
        choices.append(("scatterplot", "provisional", "No complete standard schema was detected; use only after mapping x and y.", ["Resolve missing and ambiguous fields before rendering."]))

    group_values = row_values(rows, mapping.get("group"))
    if group_values:
        counts = Counter(group_values)
        if min(counts.values()) < 5:
            flags.append("At least one group has fewer than 5 rows; emphasize raw observations and avoid a smooth density as the sole display.")
    if re.search(r"\bp(?:[ -]?value)?s?\b", question_lower) and "effect" not in question_lower:
        flags.append("The question mentions P values without effect size; add an estimate and interval display where possible.")
    if not design.strip():
        flags.append("Experimental design was not supplied; independent n, pairing, blocking, nesting and repeated measures remain unresolved.")

    registry = {row["id"]: row for row in load_tsv(REGISTRY)}
    recommendations: list[dict[str, Any]] = []
    for recipe_id, rank, reason, cautions in choices:
        row = registry.get(recipe_id)
        if not row:
            flags.append(f"Catalog recipe {recipe_id} was not found; registry must be rebuilt.")
            continue
        recommendations.append(
            {
                "recipe_id": recipe_id,
                "rank": rank,
                "name_en": row["name_en"],
                "name_zh": row["name_zh"],
                "schema_id": row["schema_id"],
                "renderer": row["renderer"],
                "coverage_tier": row["coverage_tier"],
                "reason": reason,
                "cautions": cautions,
                "source_keys": row["source_keys"].split(";"),
            }
        )
    return recommendations, flags


def standardize(
    output: Path,
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    schema_id: str,
) -> None:
    schema = next(item for item in load_tsv(SCHEMAS) if item["schema_id"] == schema_id)
    fields = schema["required_columns"].split(";") + schema["optional_columns"].split(";")
    fields = [field for field in fields if field]
    missing = [field for field in schema["required_columns"].split(";") if field not in mapping]
    if missing:
        raise ValueError(f"Cannot standardize {schema_id}; unresolved required fields: {', '.join(missing)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(mapping[field], "") if field in mapping else "" for field in fields})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--design", default="", help="independent, paired, blocked, nested, repeated, spatial, etc.")
    parser.add_argument("--question", default="", help="Scientific question or intended comparison")
    parser.add_argument("--domain", default="soil")
    parser.add_argument("--output", type=Path, help="Write full JSON report")
    parser.add_argument("--standardized", type=Path, help="Write a non-destructive standardized CSV when mapping is complete")
    parser.add_argument("--schema", help="Schema to use for --standardized; defaults to the best match")
    args = parser.parse_args()

    headers, rows, delimiter = read_table(args.input)
    columns = profile_columns(headers, rows)
    mapping, mapping_warnings = canonical_mapping(headers)
    schema_matches = match_schemas(mapping)
    recommendations, flags = recommend(rows, mapping, schema_matches, args.design, args.question)
    best_schema = args.schema or schema_matches[0]["schema_id"]
    if args.standardized:
        standardize(args.standardized, rows, mapping, best_schema)

    used_sources = sorted({key for item in recommendations for key in item["source_keys"]} | {"P-JAMBOR-2025", "P-REVEAL-2019"})
    report = {
        "status": "PASS" if recommendations else "NEEDS_INPUT",
        "input": str(args.input.resolve()),
        "rows": len(rows),
        "columns": len(headers),
        "delimiter": "TAB" if delimiter == "\t" else delimiter,
        "domain": args.domain,
        "design": args.design or None,
        "question": args.question or None,
        "column_profile": columns,
        "canonical_mapping": mapping,
        "mapping_warnings": mapping_warnings,
        "schema_matches": schema_matches[:5],
        "recommendations": recommendations,
        "scientific_flags": flags,
        "standardized_output": str(args.standardized.resolve()) if args.standardized else None,
        "sources": [{"key": key, "url": SOURCE_URLS.get(key)} for key in used_sources],
        "accessed": "2026-08-16",
        "limitations": [
            "Recommendations are structural, not a substitute for the experimental design or fitted model.",
            "No inferential test is run and no missing value is imputed.",
            "Aliases are suggestions; inspect the mapping before publication use.",
        ],
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

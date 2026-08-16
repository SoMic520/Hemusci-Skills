#!/usr/bin/env python3
"""Build the complete figure-ID to tested-renderer registry from the catalog."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "references" / "figure-catalog.tsv"
FAMILIES = ROOT / "references" / "recipe-families.tsv"
DEFAULT_OUTPUT = ROOT / "references" / "generated" / "recipe-registry.tsv"

FIELDS = (
    "id",
    "name_en",
    "name_zh",
    "primary_family",
    "schema_id",
    "renderer",
    "coverage_tier",
    "required_packages",
    "source_keys",
)


def ids(value: str) -> set[str]:
    return set(value.split())


VARIANT_GROUPS: list[tuple[str, str, set[str]]] = [
    ("distribution", "categorical", ids("strip-plot beeswarm-plot quasirandom-plot sina-plot dotplot-stacked histogram frequency-polygon density-plot ecdf-plot ccdf-plot boxplot notched-boxplot variable-width-boxplot letter-value-plot violin-plot half-violin beanplot raincloud-plot ridgeline-plot rug-plot qq-plot pp-plot quantile-dotplot half-eye-plot spike-plot hdr-boxplot violin-box-points pirate-plot pore-size-distribution")),
    ("bagplot", "xy", ids("bagplot")),
    ("genomic-rainfall", "omics", ids("rainfall-plot-genomics")),
    ("comparison", "categorical", ids("bar-count bar-value grouped-bar diverging-stacked-bar cleveland-dotplot lollipop-chart dumbbell-plot slopegraph bump-chart pareto-chart paired-dotplot superplot small-multiples")),
    ("bullet", "interval", ids("bullet-chart")),
    ("waterfall", "categorical", ids("waterfall-chart")),
    ("composition", "composition", ids("stacked-bar percent-stacked-bar pie-chart donut-chart waffle-chart pictogram-chart marimekko aggregate-size-composition microbiome-composition")),
    ("ternary", "ternary", ids("ternary-plot soil-texture-triangle")),
    ("hydrochemistry", "hydrochemistry", ids("piper-diagram schoeller-diagram stiff-diagram durov-diagram")),
    ("temporal", "time-series", ids("spaghetti-plot line-chart step-chart area-chart stacked-area streamgraph horizon-chart lasagna-plot calendar-heatmap phenology-wheel seasonal-subseries autocorrelation-plot partial-autocorrelation lag-plot change-point-plot control-chart run-chart soil-gas-flux-series cumulative-emissions")),
    ("events", "events", ids("event-timeline gantt-chart swimmer-plot lexis-diagram")),
    ("survival", "survival", ids("survival-km cumulative-incidence")),
    ("state-series", "state-series", ids("state-sequence")),
    ("climate", "climate", ids("walter-lieth")),
    ("estimation", "categorical", ids("gardner-altman cumming-estimation bootstrap-distribution hypothetical-outcome-plot")),
    ("temporal-uncertainty", "time-series", ids("fan-chart")),
    ("meta-analysis", "meta-analysis", ids("funnel-plot contour-enhanced-funnel galbraith-plot l-abbe-plot baujat-plot drapery-plot")),
    ("interval", "interval", ids("forest-plot caterpillar-plot interval-dotplot specification-curve multiverse-plot vibration-of-effects permanova-effect-plot differential-abundance-effect")),
    ("relationship", "xy", ids("scatterplot bubble-chart hexbin-plot rect-bin2d density-2d density-raster scatter-density connected-scatter regression-line loess-plot gam-smooth response-surface incubation-kinetics adsorption-isotherm dose-response-curve cate-nelson-plot prevalence-abundance rating-curve hysteresis-loop")),
    ("response-surface", "spatial-grid", ids("response-surface")),
    ("ternary-response", "ternary", ids("ternary-response")),
    ("matrix", "matrix", ids("correlation-matrix")),
    ("mantel-composite", "matrix-links", ids("mantel-correlogram")),
    ("multivariate-pairs", "multivariate-long", ids("scatterplot-matrix")),
    ("hydrochemistry", "hydrochemistry", ids("gibbs-diagram")),
    ("multivariate", "multivariate-long", ids("parallel-coordinates andrews-curves radar-chart star-glyph")),
    ("ordination", "ordination", ids("pca-biplot pcoa-plot nmds-plot rda-triplot cca-triplot dbrda-plot ordination-hull ordination-ellipse ordination-spider envfit-ordination co-inertia-plot procrustes-plot beta-dispersion-plot")),
    ("set-membership", "set-membership", ids("variation-partition upset-plot venn-diagram euler-diagram")),
    ("flow", "flow", ids("alluvial-plot sankey-diagram parallel-sets riverplot fishplot muller-plot")),
    ("network", "network", ids("chord-diagram node-link-network directed-network weighted-network bipartite-network arc-diagram hive-plot adjacency-matrix network-small-multiples enrichment-map cnetplot sem-path causal-dag workflow-diagram experimental-design-diagram conceptual-model consort-flow")),
    ("hierarchy", "hierarchy", ids("treemap sunburst icicle-plot dendrogram phylogram fan-tree unrooted-tree tree-heatmap tanglegram cophylogeny-plot heat-tree taxonomic-tree-bar")),
    ("matrix", "matrix", ids("mosaic-plot association-plot fluctuation-diagram heatmap clustered-heatmap annotated-heatmap dot-heatmap distance-matrix confusion-matrix hinton-diagram oncoprint fourth-corner-heatmap enrichment-dotplot")),
    ("spatial", "spatial-grid", ids("sample-location-map choropleth-map proportional-symbol-map dot-density-map raster-map categorical-raster-map contour-map filled-contour-map hillshade-map terrain-map slope-aspect-map vector-field-map flow-map kernel-density-map hotspot-map cartogram hex-tile-map bivariate-map geofacet-map")),
    ("spatial-prediction", "spatial-grid", ids("uncertainty-map prediction-map residual-map applicability-domain-map spatial-cv-map")),
    ("variogram", "variogram", ids("variogram fitted-variogram directional-variogram variogram-cloud cross-variogram")),
    ("spatial-profile", "spatial-grid", ids("depth-slice-maps soil-cross-section")),
    ("spatial-temporal", "spatial-grid", ids("space-time-cube hovmoller-diagram soil-moisture-depth-time")),
    ("spatial-composition", "spatial-grid", ids("scatterpie-map scatterbar-map")),
    ("profile", "profile", ids("soil-profile-sketch grouped-soil-profiles soil-depth-profile mass-preserving-spline-profile depth-property-heatmap soil-color-profile catena-diagram stratigraphic-log penetration-resistance-profile")),
    ("soil-physics", "xy", ids("particle-size-cumulative water-retention-curve hydraulic-conductivity-curve infiltration-curve breakthrough-curve")),
    ("ecology", "ecology-community", ids("rank-abundance species-abundance-distribution species-accumulation rarefaction-curve coverage-rarefaction alpha-diversity-plot")),
    ("omics", "omics", ids("ma-plot volcano-plot manhattan-plot miami-plot gsea-running-score")),
    ("genomic", "genomic", ids("regional-association karyogram circos-plot genome-track sashimi-plot mutation-lollipop copy-number-segment")),
    ("sequence-logo", "sequence-logo", ids("sequence-logo")),
    ("hydrology", "hydrology", ids("hydrograph hyetograph hydrograph-hyetograph flow-duration-curve double-mass-curve")),
    ("wind", "wind", ids("wind-rose pollution-rose polar-annulus")),
    ("diagnostic", "diagnostic", ids("taylor-diagram target-diagram observed-predicted residual-fitted scale-location leverage-plot cooks-distance calibration-plot bland-altman")),
    ("classification", "classification", ids("roc-curve precision-recall calibration-plot decision-curve lift-gain")),
    ("interval", "interval", ids("spectral-coefficient-plot")),
    ("mcmc-diagnostic", "mcmc", ids("posterior-predictive-check trace-plot rank-histogram")),
    ("spectral", "spectral", ids("spectral-signature derivative-spectrum")),
    ("image-volume", "image", ids("hyperspectral-cube kymograph orthogonal-slices maximum-intensity-projection isosurface surface-3d point-cloud-3d")),
    ("interpretation", "interpretation", ids("pdp-plot ice-plot ale-plot variable-importance shap-beeswarm shap-dependence shap-waterfall nomogram")),
    ("image", "image", ids("image-montage multichannel-overlay segmentation-overlay")),
]

VARIANT_LOOKUP = {
    figure_id: (renderer, schema)
    for renderer, schema, figure_ids in VARIANT_GROUPS
    for figure_id in figure_ids
}


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def classify(row: dict[str, str], defaults: dict[str, dict[str, str]]) -> tuple[str, str, str]:
    figure_id = row["id"]
    family = row["primary_family"]
    default = defaults[family]
    schema = default["schema_id"]
    renderer = default["renderer"]
    tier = "family-validated"

    if figure_id in VARIANT_LOOKUP:
        renderer, schema = VARIANT_LOOKUP[figure_id]
        return schema, renderer, "named-variant-validated"

    rules: list[tuple[str, str, str | None]] = [
        (r"rank-histogram", "rank-histogram", "mcmc"),
        (r"ternary|soil-texture", "ternary", "ternary"),
        (r"histogram", "histogram", None),
        (r"frequency-polygon", "frequency-polygon", None),
        (r"ecdf", "ecdf", None),
        (r"qq-plot", "qq", None),
        (r"raincloud|half-eye|eye-plot", "raincloud", None),
        (r"violin", "violin", None),
        (r"box|letter-value", "boxplot", None),
        (r"ridge", "ridgeline", None),
        (r"dumbbell|paired-dotplot|paired-slope", "paired", "categorical"),
        (r"lollipop", "lollipop", "categorical"),
        (r"bump-chart|slopegraph", "temporal", "time-series"),
        (r"waterfall", "waterfall", "categorical"),
        (r"forest|interval-dotplot|caterpillar", "interval", "interval"),
        (r"bubble", "bubble", "xy"),
        (r"hexbin|binned-scatter", "hexbin", "xy"),
        (r"scatter|regression|smooth|response-surface", "relationship", "xy"),
        (r"heatmap|matrix|corr|onco|dot-matrix", "matrix", "matrix"),
        (r"pca|pcoa|nmds|rda|cca|ordination|biplot", "ordination", "ordination"),
        (r"alluvial|sankey|parallel-sets", "flow", "flow"),
        (r"venn|euler|upset", "set-membership", "set-membership"),
        (r"network|graph|co-occurrence|coexpression|chord", "network", "network"),
        (r"soil-profile|depth-profile|pedon|horizon", "profile", "profile"),
        (r"water-retention|infiltration|sorption|adsorption|breakthrough", "soil-physics", "xy"),
        (r"radar|star-glyph|rose|polar", "polar", "categorical"),
        (r"pie|donut", "composition", "composition"),
        (r"volcano|ma-plot|manhattan", "omics", "omics"),
        (r"calibration|roc|residual|bland-altman|observed-predicted", "diagnostic", "diagnostic"),
        (r"spectral|spectra", "spectral", "spectral"),
    ]
    for pattern, candidate_renderer, candidate_schema in rules:
        if re.search(pattern, figure_id):
            renderer = candidate_renderer
            if candidate_schema:
                schema = candidate_schema
            tier = "named-variant-validated"
            break
    return schema, renderer, tier


def build(output: Path) -> tuple[int, int]:
    rows = load_tsv(CATALOG)
    family_rows = load_tsv(FAMILIES)
    defaults = {row["primary_family"]: row for row in family_rows}
    missing_families = sorted({row["primary_family"] for row in rows} - defaults.keys())
    if missing_families:
        raise SystemExit(f"Missing family registry rows: {', '.join(missing_families)}")
    missing_variants = sorted({row["id"] for row in rows} - VARIANT_LOOKUP.keys())
    unknown_variants = sorted(VARIANT_LOOKUP.keys() - {row["id"] for row in rows})
    if missing_variants:
        raise SystemExit(f"Missing named renderer mappings: {', '.join(missing_variants)}")
    if unknown_variants:
        raise SystemExit(f"Unknown named renderer mappings: {', '.join(unknown_variants)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            schema, renderer, tier = classify(row, defaults)
            writer.writerow(
                {
                    "id": row["id"],
                    "name_en": row["name_en"],
                    "name_zh": row["name_zh"],
                    "primary_family": row["primary_family"],
                    "schema_id": schema,
                    "renderer": renderer,
                    "coverage_tier": tier,
                    "required_packages": "ggplot2;jsonlite;ragg",
                    "source_keys": row["source_keys"],
                }
            )
    return len(rows), sum(1 for row in load_tsv(output) if row["coverage_tier"] == "named-variant-validated")


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    catalog_ids = [row["id"] for row in load_tsv(CATALOG)]
    rows = load_tsv(path)
    ids = [row["id"] for row in rows]
    if ids != catalog_ids:
        errors.append("registry IDs/order differ from figure catalog")
    if len(ids) != len(set(ids)):
        errors.append("registry contains duplicate IDs")
    schema_ids = {row["schema_id"] for row in load_tsv(ROOT / "references" / "input-schemas.tsv")}
    for line_no, row in enumerate(rows, start=2):
        if row["schema_id"] not in schema_ids:
            errors.append(f"line {line_no}: unknown schema {row['schema_id']}")
        template = ROOT / "assets" / "standard-inputs" / f"{row['schema_id']}.csv"
        if not template.is_file():
            errors.append(f"line {line_no}: missing template {template.name}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Validate an existing registry only")
    args = parser.parse_args()
    output = args.output.resolve()
    if not args.check:
        total, named = build(output)
        print(f"built {total} registry rows ({named} named-variant mappings): {output}")
    errors = validate(output)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"registry validation PASS: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env Rscript

# Replace the demo data and labels with the real, immutable source data.
# This template demonstrates a blocked/paired design; it is not a universal analysis.

params <- list(
  figure_id = "figure-1",
  width_mm = 89,
  height_mm = 70,
  raster_dpi = 600,
  png_background = "white",
  pdf_background = "white",
  tiff_background = "white",
  base_size_pt = NULL,
  point_size_mm = 1.6,
  line_width_mm = 0.45,
  output_dir = "outputs",
  data_dir = "data",
  palette = c(Control = "#0072B2", Compost = "#D55E00"),
  shapes = c(Control = 16, Compost = 17),
  seed = 20260816
)

required <- c("ggplot2", "jsonlite", "ragg")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) {
  options(repos = c(CRAN = "https://cloud.r-project.org"))
  message("Installing missing packages: ", paste(missing, collapse = ", "))
  utils::install.packages(missing, dependencies = NA)
}
remaining <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(remaining)) stop("Packages still missing: ", paste(remaining, collapse = ", "))

dir.create(params$output_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(params$data_dir, recursive = TRUE, showWarnings = FALSE)

data_path <- Sys.getenv("FIGURE_DATA", file.path(params$data_dir, "figure-data.csv"))
demo <- identical(Sys.getenv("FIGURE_DEMO", "0"), "1")

if (demo) {
  set.seed(params$seed)
  dat <- expand.grid(
    block = factor(seq_len(8)),
    treatment = factor(c("Control", "Compost"), levels = c("Control", "Compost"))
  )
  block_effect <- rnorm(8, mean = 0, sd = 0.8)
  dat$response <- 10 + block_effect[as.integer(dat$block)] +
    ifelse(dat$treatment == "Compost", 1.5, 0) + rnorm(nrow(dat), 0, 0.45)
  dat$unit <- "mg kg^-1"
} else {
  if (!file.exists(data_path)) {
    stop("Missing source data: ", data_path,
         ". Set FIGURE_DATA or run the self-contained smoke test with FIGURE_DEMO=1.")
  }
  dat <- utils::read.csv(data_path, check.names = FALSE)
}

required_columns <- c("block", "treatment", "response", "unit")
missing_columns <- setdiff(required_columns, names(dat))
if (length(missing_columns)) {
  stop("Missing columns: ", paste(missing_columns, collapse = ", "))
}
if (anyNA(dat[c("block", "treatment", "response")])) {
  stop("Missing block, treatment or response values require an explicit handling rule.")
}
if (anyDuplicated(dat[c("block", "treatment")])) {
  stop("Expected one independent block-level value per treatment in this template.")
}

dat$block <- factor(dat$block)
dat$treatment <- factor(dat$treatment, levels = names(params$palette))
if (anyNA(dat$treatment)) {
  stop("Treatment values do not match the declared stable factor levels.")
}

summary_by_treatment <- do.call(
  rbind,
  lapply(split(dat$response, dat$treatment), function(x) {
    n <- length(x)
    se <- stats::sd(x) / sqrt(n)
    critical <- stats::qt(0.975, df = n - 1)
    data.frame(mean = mean(x), lower = mean(x) - critical * se,
               upper = mean(x) + critical * se, n = n)
  })
)
summary_by_treatment$treatment <- factor(
  rownames(summary_by_treatment), levels = levels(dat$treatment)
)
rownames(summary_by_treatment) <- NULL

resolved_base_size_pt <- if (!is.null(params$base_size_pt)) {
  as.numeric(params$base_size_pt)
} else {
  category_penalty <- 0.16 * log1p(nlevels(dat$treatment))
  max(7.0, min(9.5, 8.6 + 0.006 * (min(params$width_mm, params$height_mm) - 70) - category_penalty))
}

figure <- ggplot2::ggplot(
  dat,
  ggplot2::aes(x = treatment, y = response, group = block)
) +
  ggplot2::geom_line(
    color = "#8A8A8A", linewidth = params$line_width_mm * 0.65, alpha = 0.65
  ) +
  ggplot2::geom_point(
    ggplot2::aes(color = treatment, shape = treatment),
    size = params$point_size_mm
  ) +
  ggplot2::geom_errorbar(
    data = summary_by_treatment,
    ggplot2::aes(x = treatment, ymin = lower, ymax = upper, group = NULL),
    inherit.aes = FALSE,
    width = 0.08,
    linewidth = params$line_width_mm,
    color = "black"
  ) +
  ggplot2::geom_point(
    data = summary_by_treatment,
    ggplot2::aes(x = treatment, y = mean, group = NULL),
    inherit.aes = FALSE,
    shape = 21,
    size = params$point_size_mm + 0.5,
    fill = "white",
    color = "black",
    stroke = params$line_width_mm
  ) +
  ggplot2::scale_color_manual(values = params$palette, drop = FALSE) +
  ggplot2::scale_shape_manual(values = params$shapes, drop = FALSE) +
  ggplot2::labs(
    x = NULL,
    y = expression("Soil response"~"/"~"(mg kg"^{-1}*")"),
    color = "Treatment",
    shape = "Treatment"
  ) +
  ggplot2::theme_bw(base_size = resolved_base_size_pt) +
  ggplot2::theme(
    legend.position = "top",
    legend.title = ggplot2::element_text(face = "bold"),
    axis.text.x = ggplot2::element_text(color = "black"),
    axis.text.y = ggplot2::element_text(color = "black"),
    axis.line = ggplot2::element_blank(),
    panel.border = ggplot2::element_rect(fill = NA, color = "#202020", linewidth = 0.42),
    panel.grid = ggplot2::element_blank(),
    panel.background = ggplot2::element_rect(fill = "white", color = NA),
    plot.background = ggplot2::element_rect(fill = "white", color = NA)
  )

pdf_path <- file.path(params$output_dir, paste0(params$figure_id, ".pdf"))
png_path <- file.path(params$output_dir, paste0(params$figure_id, ".png"))
tiff_path <- file.path(params$output_dir, paste0(params$figure_id, ".tiff"))
derived_path <- file.path(params$data_dir, paste0(params$figure_id, "-data.csv"))

ggplot2::ggsave(
  pdf_path, figure, device = grDevices::pdf,
  width = params$width_mm, height = params$height_mm, units = "mm",
  useDingbats = FALSE, bg = params$pdf_background
)

png_device <- if (requireNamespace("ragg", quietly = TRUE)) ragg::agg_png else "png"
ggplot2::ggsave(
  png_path, figure, device = png_device,
  width = params$width_mm, height = params$height_mm, units = "mm",
  dpi = params$raster_dpi, bg = params$png_background
)
ggplot2::ggsave(
  tiff_path, figure, device = ragg::agg_tiff,
  width = params$width_mm, height = params$height_mm, units = "mm",
  dpi = params$raster_dpi, compression = "lzw", bg = params$tiff_background
)
utils::write.csv(dat, derived_path, row.names = FALSE, na = "NA")

manifest <- list(
  schema_version = "1.0",
  figure_id = params$figure_id,
  created = format(Sys.Date(), "%Y-%m-%d"),
  source_data = if (demo) list("self-contained simulated smoke-test data") else list(data_path),
  transformations = list(
    "Stable treatment factor order declared in the parameter block.",
    "Means and two-sided 95% t intervals calculated across independent blocks."
  ),
  design = list(
    experimental_unit = "block-level value within treatment (demo only)",
    replication = paste0(nlevels(dat$block), " independent blocks; no technical replicates"),
    pairing_blocking_nesting = "Treatments are paired within block and connected by gray lines."
  ),
  statistics = list(
    estimand = "Treatment mean; paired raw block values are shown.",
    uncertainty = "Two-sided 95% t confidence interval for each treatment mean across blocks.",
    model = "Descriptive demo; replace with a verified design-appropriate model for real data.",
    multiplicity = "Not applicable in the two-treatment demo."
  ),
  software = list(
    R = R.version.string,
    packages = list(
      ggplot2 = as.character(utils::packageVersion("ggplot2")),
      jsonlite = as.character(utils::packageVersion("jsonlite")),
      ragg = if (requireNamespace("ragg", quietly = TRUE))
        as.character(utils::packageVersion("ragg")) else "not installed"
    )
  ),
  dimensions = list(
    width_mm = params$width_mm, height_mm = params$height_mm,
    raster_dpi = params$raster_dpi,
    background = list(pdf = params$pdf_background, png = params$png_background,
                      tiff = params$tiff_background),
    resolved_base_size_pt = resolved_base_size_pt
  ),
  color = list(
    semantics = "qualitative treatment",
    mapping = as.list(params$palette),
    redundant_encoding = "shape and direct x-axis category"
  ),
  outputs = list(pdf_path, png_path, tiff_path, derived_path),
  notes = list(
    "This is a runnable template and smoke test, not a scientific analysis of user data.",
    "Manual visual review and live journal-rule verification remain required."
  )
)
jsonlite::write_json(
  manifest,
  file.path(params$output_dir, "figure-manifest.json"),
  auto_unbox = TRUE,
  pretty = TRUE
)
utils::capture.output(sessionInfo(), file = file.path(params$output_dir, "session-info.txt"))

message("Created: ", pdf_path)
message("Created: ", png_path)
message("Created: ", tiff_path)

#!/usr/bin/env Rscript

# Standalone bundle entrypoint. Paths are resolved relative to this file on macOS and Windows.

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0L) return(y)
  if (length(x) == 1L && (is.na(x) || (is.character(x) && !nzchar(x)))) return(y)
  x
}

parse_cli <- function(args) {
  out <- list()
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (!startsWith(key, "--")) stop("Unexpected argument: ", key)
    if (i == length(args)) stop("Missing value for ", key)
    out[[substring(key, 3L)]] <- args[[i + 1L]]
    i <- i + 2L
  }
  out
}

script_path <- function() {
  arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (!length(arg)) return(normalizePath(".", winslash = "/", mustWork = TRUE))
  normalizePath(sub("^--file=", "", arg[[1]]), winslash = "/", mustWork = TRUE)
}

root <- dirname(script_path())
cli <- parse_cli(commandArgs(trailingOnly = TRUE))
config_path <- cli$config %||% file.path(root, "config", "figure-config.json")
input_path <- cli$input %||% file.path(root, "data", "input.csv")
output_dir <- cli$out %||% file.path(root, "outputs")
derived_dir <- cli$derived %||% file.path(root, "derived")

required_packages <- c("ggplot2", "jsonlite", "ragg", "scales", "systemfonts", "sysfonts", "showtext")
missing_packages <- required_packages[
  !vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)
]
if (length(missing_packages)) {
  options(repos = c(CRAN = "https://cloud.r-project.org"))
  message("Installing missing packages: ", paste(missing_packages, collapse = ", "))
  utils::install.packages(missing_packages, dependencies = NA)
}
remaining_packages <- required_packages[
  !vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)
]
if (length(remaining_packages)) stop("Packages still missing: ", paste(remaining_packages, collapse = ", "))

source(file.path(root, "lib", "figure_engine.R"), encoding = "UTF-8")
if (!file.exists(config_path)) stop("Configuration file not found: ", config_path)
config <- jsonlite::fromJSON(config_path, simplifyVector = TRUE)
dat <- read_figure_data(input_path, config$schema_id)
validation <- validate_figure_data(dat, config$schema_id)
if (length(validation$errors)) stop(paste(validation$errors, collapse = "; "))
if (length(validation$warnings)) warning(paste(validation$warnings, collapse = "; "))

figure <- render_figure(dat, config)
derived <- write_clean_and_summary(dat, config, derived_dir)
outputs <- save_figure(figure, config, output_dir)
fonts <- attr(figure, "resolved_fonts") %||% configure_figure_fonts(config$raster_dpi %||% 600)
typography <- attr(figure, "resolved_typography") %||% resolve_figure_typography(config, dat)
if (isTRUE(typography$needs_layout_revision)) {
  warning("Final-size layout risk: ", paste(typography$layout_messages, collapse = "; "))
}

manifest <- list(
  schema_version = "2.0",
  figure_id = config$recipe_id,
  created = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
  source_data = list(normalizePath(input_path, winslash = "/", mustWork = TRUE)),
  transformations = list(
    "Required-column, numeric-coercion and schema-specific validation.",
    "Only descriptive transformations implemented by the named renderer; no inferential results invented."
  ),
  design = list(
    schema_id = config$schema_id,
    primary_family = config$primary_family,
    coverage_tier = config$coverage_tier,
    experimental_unit = config$experimental_unit %||% "Must be supplied for real data",
    replication = config$replication %||% "Must be supplied for real data",
    pairing_blocking_nesting = config$pairing_blocking_nesting %||% "Must be supplied for real data"
  ),
  statistics = list(
    estimand = config$estimand %||% "Renderer-specific descriptive display",
    uncertainty = config$uncertainty %||% "No uncertainty unless present in the standard input or explicitly computed",
    model = config$model %||% "No inferential model fitted by default",
    multiplicity = config$multiplicity %||% "Not applicable unless supplied by a validated analysis"
  ),
  software = list(
    R = R.version.string,
    platform = R.version$platform,
    packages = lapply(required_packages, function(pkg) as.character(utils::packageVersion(pkg)))
  ),
  dimensions = list(
    width_mm = config$width_mm,
    height_mm = config$height_mm,
    raster_dpi = config$raster_dpi,
    background = "white"
  ),
  typography = list(
    chinese = fonts$chinese_resolved,
    english = fonts$english_resolved,
    chinese_path = fonts$chinese_path,
    english_path = fonts$english_path,
    showtext = fonts$showtext,
    platform = fonts$platform,
    sizing = typography,
    note = "Chinese plot titles use Songti/SimSun and English analytical labels use Times New Roman when an internal title is explicitly enabled; journal figures omit internal titles by default."
  ),
  color = list(
    semantics = "Renderer-specific explicit scientific palette",
    mapping = as.list(palette_discrete),
    redundant_encoding = "Shape, line, position, label or facet is used when group distinction is essential."
  ),
  outputs = list(outputs$pdf, outputs$png, outputs$tiff, derived$validated, derived$summary),
  warnings = as.list(validation$warnings),
  notes = list(
    "The standard input is synthetic and for smoke testing only unless replaced by user data.",
    "Live journal instructions and scientific analysis must be verified before submission."
  )
)
names(manifest$software$packages) <- required_packages
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
jsonlite::write_json(manifest, file.path(output_dir, "figure-manifest.json"),
                     auto_unbox = TRUE, pretty = TRUE, null = "null")
utils::capture.output(sessionInfo(), file = file.path(output_dir, "session-info.txt"))

caption <- paste0(
  config$name_zh, "（", config$name_en, "）。",
  "本文件使用标准输入模式 ", config$schema_id, " 和渲染器 ", config$renderer,
  " 生成；替换真实数据后必须补充实验单位、样本量、统计模型和不确定性定义。"
)
writeLines(enc2utf8(caption), file.path(output_dir, "caption-draft.txt"), useBytes = TRUE)

message("Created: ", outputs$pdf)
message("Created: ", outputs$png)
message("Created: ", outputs$tiff)
message("Manifest: ", file.path(output_dir, "figure-manifest.json"))

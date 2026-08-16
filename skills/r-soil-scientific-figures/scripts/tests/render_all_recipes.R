#!/usr/bin/env Rscript

# Render every catalog entry in one R session and write an auditable result matrix.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) stop("Usage: Rscript render_all_recipes.R SKILL_ROOT OUTPUT_DIR")
skill_root <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)
output_root <- normalizePath(args[[2]], winslash = "/", mustWork = FALSE)
dir.create(output_root, recursive = TRUE, showWarnings = FALSE)
png_dir <- file.path(output_root, "png")
pdf_dir <- file.path(output_root, "pdf")
dir.create(png_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(pdf_dir, recursive = TRUE, showWarnings = FALSE)

required <- c("ggplot2", "jsonlite", "ragg", "scales", "systemfonts", "sysfonts", "showtext")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) stop("Missing test packages: ", paste(missing, collapse = ", "))

source(file.path(skill_root, "assets", "r-engine", "figure_engine.R"), encoding = "UTF-8")
registry <- utils::read.delim(
  file.path(skill_root, "references", "generated", "recipe-registry.tsv"),
  check.names = FALSE, stringsAsFactors = FALSE, fileEncoding = "UTF-8"
)

results <- vector("list", nrow(registry))
for (i in seq_len(nrow(registry))) {
  row <- registry[i, , drop = FALSE]
  warnings <- character()
  started <- proc.time()[["elapsed"]]
  result <- tryCatch(
    withCallingHandlers({
      config <- list(
        recipe_id = row$id,
        name_en = row$name_en,
        name_zh = row$name_zh,
        primary_family = row$primary_family,
        schema_id = row$schema_id,
        renderer = row$renderer,
        coverage_tier = row$coverage_tier,
        width_mm = 105,
        height_mm = 78,
        raster_dpi = 160,
        base_size_pt = NULL,
        typography_mode = "auto",
        layout = "auto",
        panel_count = 1,
        show_title = FALSE
      )
      input <- file.path(skill_root, "assets", "standard-inputs", paste0(row$schema_id, ".csv"))
      dat <- read_figure_data(input, row$schema_id)
      validation <- validate_figure_data(dat, row$schema_id)
      if (length(validation$errors)) stop(paste(validation$errors, collapse = "; "))
      warnings <- c(warnings, validation$warnings)
      figure <- render_figure(dat, config)
      pdf_path <- file.path(pdf_dir, paste0(row$id, ".pdf"))
      png_path <- file.path(png_dir, paste0(row$id, ".png"))
      ggplot2::ggsave(
        pdf_path, figure, device = grDevices::pdf, width = config$width_mm,
        height = config$height_mm, units = "mm", bg = "white", useDingbats = FALSE
      )
      ggplot2::ggsave(
        png_path, figure, device = ragg::agg_png, width = config$width_mm,
        height = config$height_mm, units = "mm", dpi = config$raster_dpi, bg = "white"
      )
      png_info <- file.info(png_path)
      pdf_info <- file.info(pdf_path)
      if (!isTRUE(png_info$size > 1000)) stop("PNG is missing or unexpectedly small")
      if (!isTRUE(pdf_info$size > 1000)) stop("PDF is missing or unexpectedly small")
      data.frame(
        id = row$id,
        primary_family = row$primary_family,
        schema_id = row$schema_id,
        renderer = row$renderer,
        coverage_tier = row$coverage_tier,
        status = if (length(warnings)) "WARN" else "PASS",
        warnings = paste(unique(warnings), collapse = " | "),
        error = "",
        png_bytes = png_info$size,
        pdf_bytes = pdf_info$size,
        png_md5 = unname(tools::md5sum(png_path)),
        elapsed_seconds = round(proc.time()[["elapsed"]] - started, 3),
        stringsAsFactors = FALSE
      )
    }, warning = function(w) {
      warnings <<- c(warnings, conditionMessage(w))
      invokeRestart("muffleWarning")
    }),
    error = function(e) data.frame(
      id = row$id,
      primary_family = row$primary_family,
      schema_id = row$schema_id,
      renderer = row$renderer,
      coverage_tier = row$coverage_tier,
      status = "FAIL",
      warnings = paste(unique(warnings), collapse = " | "),
      error = conditionMessage(e),
      png_bytes = NA_real_,
      pdf_bytes = NA_real_,
      png_md5 = "",
      elapsed_seconds = round(proc.time()[["elapsed"]] - started, 3),
      stringsAsFactors = FALSE
    )
  )
  results[[i]] <- result
  if (i %% 25 == 0 || i == nrow(registry)) {
    interim <- do.call(rbind, results[seq_len(i)])
    utils::write.table(
      interim, file.path(output_root, "recipe-test-results.tsv"), sep = "\t",
      row.names = FALSE, quote = TRUE, fileEncoding = "UTF-8", na = "NA"
    )
    message("Rendered ", i, "/", nrow(registry), "; failures: ", sum(interim$status == "FAIL"))
  }
}

final <- do.call(rbind, results)
summary <- list(
  tested_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
  R = R.version.string,
  platform = R.version$platform,
  total = nrow(final),
  pass = sum(final$status == "PASS"),
  warn = sum(final$status == "WARN"),
  fail = sum(final$status == "FAIL"),
  named_variant = sum(final$coverage_tier == "named-variant-validated"),
  family_validated = sum(final$coverage_tier == "family-validated")
)
jsonlite::write_json(summary, file.path(output_root, "recipe-test-summary.json"),
                     auto_unbox = TRUE, pretty = TRUE)
utils::capture.output(sessionInfo(), file = file.path(output_root, "session-info.txt"))
if (summary$fail) quit(status = 1)

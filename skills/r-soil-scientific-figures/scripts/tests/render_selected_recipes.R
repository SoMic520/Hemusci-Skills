#!/usr/bin/env Rscript

# Fast regression renderer for a selected set of catalog IDs.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3L) {
  stop("Usage: Rscript render_selected_recipes.R SKILL_ROOT OUTPUT_DIR RECIPE_ID [RECIPE_ID ...]")
}
skill_root <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)
output_root <- normalizePath(args[[2]], winslash = "/", mustWork = FALSE)
recipe_ids <- args[-c(1, 2)]
dir.create(output_root, recursive = TRUE, showWarnings = FALSE)

source(file.path(skill_root, "assets", "r-engine", "figure_engine.R"), encoding = "UTF-8")
registry <- utils::read.delim(
  file.path(skill_root, "references", "generated", "recipe-registry.tsv"),
  check.names = FALSE, stringsAsFactors = FALSE, fileEncoding = "UTF-8"
)
unknown <- setdiff(recipe_ids, registry$id)
if (length(unknown)) stop("Unknown recipe IDs: ", paste(unknown, collapse = ", "))

results <- vector("list", length(recipe_ids))
for (index in seq_along(recipe_ids)) {
  recipe_id <- recipe_ids[[index]]
  row <- registry[registry$id == recipe_id, , drop = FALSE]
  warnings <- character()
  error <- ""
  status <- tryCatch(
    withCallingHandlers({
      config <- list(
        recipe_id = row$id, name_en = row$name_en, name_zh = row$name_zh,
        primary_family = row$primary_family, schema_id = row$schema_id,
        renderer = row$renderer, coverage_tier = row$coverage_tier,
        width_mm = 105, height_mm = 78, raster_dpi = 160,
        typography_mode = "auto", layout = "auto", panel_count = 1,
        show_title = FALSE
      )
      input <- file.path(skill_root, "assets", "standard-inputs", paste0(row$schema_id, ".csv"))
      dat <- read_figure_data(input, row$schema_id)
      validation <- validate_figure_data(dat, row$schema_id)
      if (length(validation$errors)) stop(paste(validation$errors, collapse = "; "))
      figure <- render_figure(dat, config)
      ggplot2::ggsave(
        file.path(output_root, paste0(recipe_id, ".png")), figure,
        device = ragg::agg_png, width = config$width_mm, height = config$height_mm,
        units = "mm", dpi = config$raster_dpi, bg = "white"
      )
      if (length(warnings)) "WARN" else "PASS"
    }, warning = function(w) {
      warnings <<- c(warnings, conditionMessage(w))
      invokeRestart("muffleWarning")
    }),
    error = function(e) {
      error <<- conditionMessage(e)
      "FAIL"
    }
  )
  results[[index]] <- data.frame(
    id = recipe_id, status = status,
    warnings = paste(unique(warnings), collapse = " | "), error = error,
    stringsAsFactors = FALSE
  )
}
results <- do.call(rbind, results)
utils::write.table(results, file.path(output_root, "selected-results.tsv"), sep = "\t",
                   row.names = FALSE, quote = TRUE, fileEncoding = "UTF-8")
print(results)
if (any(results$status == "FAIL")) quit(status = 1)

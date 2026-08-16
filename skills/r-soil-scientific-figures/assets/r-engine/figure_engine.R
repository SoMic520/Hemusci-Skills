# Cross-platform, dependency-light rendering engine for validated figure recipes.
# The engine renders plot-ready inputs. It never invents inferential test results.

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0L) return(y)
  if (length(x) == 1L && (is.na(x) || (is.character(x) && !nzchar(x)))) return(y)
  x
}

required_columns <- list(
  categorical = c("sample_id", "group", "value"),
  interval = c("label", "estimate", "lower", "upper"),
  xy = c("sample_id", "x", "y"),
  `time-series` = c("sample_id", "time", "value"),
  composition = c("sample_id", "component", "value"),
  matrix = c("row_id", "column_id", "value"),
  ordination = c("element_type", "label", "axis1", "axis2"),
  flow = c("path_id", "stage", "state", "value"),
  hierarchy = c("node_id", "label", "value"),
  `set-membership` = c("item_id", "set_id", "present"),
  network = c("from", "to"),
  `spatial-grid` = c("x", "y", "value"),
  profile = c("profile_id", "top_cm", "bottom_cm", "property", "value"),
  spectral = c("sample_id", "wavelength_nm", "value"),
  diagnostic = c("observation_id", "observed", "predicted"),
  image = c("x", "y", "intensity"),
  ternary = c("sample_id", "part_a", "part_b", "part_c"),
  omics = c("feature_id", "log2_fold_change", "p_value"),
  mcmc = c("draw_id", "parameter", "chain", "value"),
  events = c("event_id", "subject_id", "start", "end", "label"),
  survival = c("subject_id", "time", "status"),
  `meta-analysis` = c("study_id", "effect", "se"),
  `multivariate-long` = c("sample_id", "variable", "value"),
  hydrochemistry = c("sample_id", "analyte", "value"),
  `ecology-community` = c("sample_id", "species", "abundance"),
  variogram = c("lag", "semivariance"),
  classification = c("observation_id", "truth", "score"),
  interpretation = c("observation_id", "feature", "feature_value", "effect"),
  climate = c("time", "temperature", "precipitation"),
  wind = c("direction_deg", "speed", "frequency"),
  `sequence-logo` = c("position", "symbol", "frequency"),
  genomic = c("feature_id", "chromosome", "start", "end", "value"),
  `state-series` = c("subject_id", "time", "state"),
  hydrology = c("time", "discharge", "precipitation"),
  `matrix-links` = c("element_type")
)

numeric_columns <- list(
  categorical = c("value"),
  interval = c("estimate", "lower", "upper", "reference"),
  xy = c("x", "y", "size"),
  `time-series` = c("time", "value", "lower", "upper"),
  composition = c("value", "denominator"),
  matrix = c("value"),
  ordination = c("axis1", "axis2"),
  flow = c("stage", "value"),
  hierarchy = c("value", "level", "track_control", "track_compost", "track_biochar"),
  `set-membership` = c("present"),
  network = c("weight"),
  `spatial-grid` = c("x", "y", "value", "uncertainty", "u", "v"),
  profile = c("top_cm", "bottom_cm", "depth_cm", "value"),
  spectral = c("wavelength_nm", "value"),
  diagnostic = c("observed", "predicted", "fitted", "residual", "lower", "upper"),
  image = c("x", "y", "intensity", "slice"),
  ternary = c("part_a", "part_b", "part_c", "total"),
  omics = c("log2_fold_change", "p_value", "adjusted_p_value", "mean_abundance", "position"),
  mcmc = c("value", "iteration", "warmup", "weight"),
  events = c("start", "end", "value"),
  survival = c("time", "status"),
  `meta-analysis` = c("effect", "se", "variance", "event_treatment", "total_treatment", "event_control", "total_control"),
  `multivariate-long` = c("value"),
  hydrochemistry = c("value"),
  `ecology-community` = c("abundance", "effort"),
  variogram = c("lag", "semivariance", "pairs", "model_semivariance"),
  classification = c("truth", "score", "predicted_class", "weight"),
  interpretation = c("feature_value", "effect", "importance", "lower", "upper"),
  climate = c("time", "temperature", "precipitation", "year"),
  wind = c("direction_deg", "speed", "frequency", "pollutant"),
  `sequence-logo` = c("position", "frequency", "information_bits"),
  genomic = c("start", "end", "value", "p_value"),
  `state-series` = c("time", "duration"),
  hydrology = c("time", "discharge", "precipitation", "cumulative_reference"),
  `matrix-links` = c("value", "p_value", "link_value", "link_p")
)

read_figure_data <- function(path, schema_id) {
  if (!file.exists(path)) stop("Input file not found: ", path)
  dat <- tryCatch(
    utils::read.csv(path, check.names = FALSE, stringsAsFactors = FALSE,
                    fileEncoding = "UTF-8-BOM", na.strings = c("", "NA", "NaN")),
    error = function(e) utils::read.csv(
      path, check.names = FALSE, stringsAsFactors = FALSE,
      fileEncoding = "UTF-8", na.strings = c("", "NA", "NaN")
    )
  )
  need <- required_columns[[schema_id]]
  if (is.null(need)) stop("Unknown schema: ", schema_id)
  absent <- setdiff(need, names(dat))
  if (length(absent)) stop("Missing required columns: ", paste(absent, collapse = ", "))
  for (column in intersect(numeric_columns[[schema_id]], names(dat))) {
    original_non_missing <- !is.na(dat[[column]])
    dat[[column]] <- suppressWarnings(as.numeric(dat[[column]]))
    if (any(original_non_missing & is.na(dat[[column]]))) {
      stop("Column must be numeric: ", column)
    }
  }
  if (!nrow(dat)) stop("Input contains no rows")
  dat
}

validate_figure_data <- function(dat, schema_id) {
  errors <- character()
  warnings <- character()
  key <- required_columns[[schema_id]]
  for (column in key) {
    if (anyNA(dat[[column]])) errors <- c(errors, paste("missing required values in", column))
  }
  if (schema_id == "interval" && any(dat$lower > dat$estimate | dat$estimate > dat$upper, na.rm = TRUE)) {
    errors <- c(errors, "interval rows must satisfy lower <= estimate <= upper")
  }
  if (schema_id == "profile" && any(dat$top_cm > dat$bottom_cm, na.rm = TRUE)) {
    errors <- c(errors, "profile rows must satisfy top_cm <= bottom_cm")
  }
  if (schema_id == "ternary") {
    totals <- dat$part_a + dat$part_b + dat$part_c
    declared <- if ("total" %in% names(dat)) dat$total else rep(100, nrow(dat))
    if (any(abs(totals - declared) > pmax(1e-8, declared * 0.01), na.rm = TRUE)) {
      errors <- c(errors, "ternary parts do not close to declared total within 1%")
    }
  }
  if (schema_id == "composition" && any(dat$value < 0, na.rm = TRUE)) {
    errors <- c(errors, "composition values must be non-negative")
  }
  if (schema_id == "omics" && any(dat$p_value <= 0 | dat$p_value > 1, na.rm = TRUE)) {
    errors <- c(errors, "omics p_value must be in (0, 1]")
  }
  if (schema_id == "set-membership" && any(!dat$present %in% c(0, 1))) {
    errors <- c(errors, "set membership present must be 0/1")
  }
  if (schema_id == "events" && any(dat$start > dat$end, na.rm = TRUE)) {
    errors <- c(errors, "event rows must satisfy start <= end")
  }
  if (schema_id == "survival" && any(!dat$status %in% c(0, 1))) {
    errors <- c(errors, "survival status must be 0/1")
  }
  if (schema_id == "classification" &&
      (any(!dat$truth %in% c(0, 1)) || any(dat$score < 0 | dat$score > 1, na.rm = TRUE))) {
    errors <- c(errors, "classification truth must be 0/1 and score must be within [0, 1]")
  }
  if (schema_id == "sequence-logo") {
    totals <- stats::aggregate(frequency ~ position, dat, sum)$frequency
    if (any(abs(totals - 1) > 0.01)) errors <- c(errors, "sequence frequencies must close to 1 at each position")
  }
  if (schema_id == "wind" && any(dat$direction_deg < 0 | dat$direction_deg >= 360, na.rm = TRUE)) {
    errors <- c(errors, "wind direction must be in [0, 360)")
  }
  if (schema_id == "genomic" && any(dat$start > dat$end, na.rm = TRUE)) {
    errors <- c(errors, "genomic intervals must satisfy start <= end")
  }
  if (schema_id == "matrix-links") {
    cells <- dat$element_type == "cell"
    links <- dat$element_type == "link"
    if (any(!dat$element_type %in% c("cell", "link"))) {
      errors <- c(errors, "matrix-links element_type must be cell or link")
    }
    cell_columns <- c("row_id", "column_id", "value", "p_value")
    link_columns <- c("from", "to", "link_value", "link_p")
    if (any(cells) && length(setdiff(cell_columns, names(dat)))) {
      errors <- c(errors, "matrix-links input is missing one or more cell columns")
    } else if (any(cells & (is.na(dat$row_id) | is.na(dat$column_id) | is.na(dat$value) | is.na(dat$p_value)))) {
      errors <- c(errors, "matrix-links cell rows require row_id, column_id, value and p_value")
    }
    if (any(links) && length(setdiff(link_columns, names(dat)))) {
      errors <- c(errors, "matrix-links input is missing one or more link columns")
    } else if (any(links & (is.na(dat$from) | is.na(dat$to) | is.na(dat$link_value) | is.na(dat$link_p)))) {
      errors <- c(errors, "matrix-links link rows require from, to, link_value and link_p")
    }
  }
  if (schema_id == "matrix-links") {
    cell_rows <- dat[dat$element_type == "cell", , drop = FALSE]
    link_rows <- dat[dat$element_type == "link", , drop = FALSE]
    if (nrow(cell_rows) && anyDuplicated(cell_rows[c("row_id", "column_id")])) {
      warnings <- c(warnings, "duplicate matrix cell rows detected")
    }
    link_key <- intersect(c("from", "to", "group"), names(link_rows))
    if (nrow(link_rows) && length(link_key) >= 2 && anyDuplicated(link_rows[link_key])) {
      warnings <- c(warnings, "duplicate matrix-link edge rows detected")
    }
  } else if (anyDuplicated(dat[key])) {
    warnings <- c(warnings, "duplicate required-key rows detected; verify observation grain")
  }
  list(errors = unique(errors), warnings = unique(warnings))
}

palette_discrete <- c(
  "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
  "#56B4E9", "#6A3D9A", "#7F7F7F"
)

first_available_font <- function(candidates, fallback = "serif") {
  if (!requireNamespace("systemfonts", quietly = TRUE)) {
    return(list(family = fallback, path = NA_character_))
  }
  fonts <- systemfonts::system_fonts()
  for (candidate in candidates) {
    row <- fonts[fonts$family == candidate & grepl("Regular|Book|Roman|Normal", fonts$style, ignore.case = TRUE), , drop = FALSE]
    if (!nrow(row)) row <- fonts[fonts$family == candidate, , drop = FALSE]
    if (nrow(row)) return(list(family = candidate, path = row$path[[1]]))
  }
  list(family = fallback, path = NA_character_)
}

configure_figure_fonts <- function(raster_dpi = NULL) {
  platform <- Sys.info()[["sysname"]]
  chinese_candidates <- if (identical(platform, "Windows")) {
    c("SimSun", "宋体", "NSimSun", "Microsoft YaHei")
  } else {
    c("Songti SC", "STSong", "SimSong", "Noto Serif CJK SC", "Source Han Serif SC")
  }
  english <- first_available_font(c("Times New Roman", "Times", "Liberation Serif"), "serif")
  chinese <- first_available_font(chinese_candidates, "serif")
  use_showtext <- requireNamespace("sysfonts", quietly = TRUE) &&
    requireNamespace("showtext", quietly = TRUE) &&
    !is.na(english$path) && !is.na(chinese$path)
  if (use_showtext) {
    registered <- sysfonts::font_families()
    if (!"figure_en" %in% registered) sysfonts::font_add("figure_en", regular = english$path)
    if (!"figure_zh" %in% registered) sysfonts::font_add("figure_zh", regular = chinese$path)
    if (!is.null(raster_dpi)) showtext::showtext_opts(dpi = as.numeric(raster_dpi))
    showtext::showtext_auto(enable = TRUE)
  }
  list(
    english = if (use_showtext) "figure_en" else english$family,
    chinese = if (use_showtext) "figure_zh" else chinese$family,
    english_resolved = english$family,
    chinese_resolved = chinese$family,
    english_path = english$path,
    chinese_path = chinese$path,
    showtext = use_showtext,
    platform = platform
  )
}

resolve_figure_typography <- function(config, dat = NULL) {
  width <- as.numeric(config$width_mm %||% 89)
  height <- as.numeric(config$height_mm %||% 72)
  panels <- as.integer(config$panel_count %||% 1)
  facet_columns <- as.integer(config$facet_columns %||% ceiling(sqrt(panels)))
  facet_columns <- max(1L, min(panels, facet_columns))
  effective_panel_width <- width / facet_columns
  layout <- config$layout %||% "auto"
  if (identical(layout, "auto")) {
    layout <- if (width <= 100) "single-column" else if (width <= 150) "intermediate" else "double-column"
  }
  journal_profile <- tolower(as.character(config$journal_profile %||% "generic"))
  if (!journal_profile %in% c("generic", "nature", "elsevier", "custom")) {
    stop("Unknown journal_profile: ", journal_profile)
  }
  profile_defaults <- switch(
    journal_profile,
    nature = c(min = 5, max = 7, preferred = 6.75),
    elsevier = c(min = 6, max = 10, preferred = 7.25),
    custom = c(min = 7.5, max = 9.5, preferred = 8.5),
    generic = c(min = 7.5, max = 9.5, preferred = 8.5)
  )
  min_pt <- as.numeric(config$min_size_pt %||% profile_defaults[["min"]])
  max_pt <- as.numeric(config$max_size_pt %||% profile_defaults[["max"]])
  if (!is.finite(min_pt) || !is.finite(max_pt) || min_pt <= 0 || max_pt < min_pt) {
    stop("Typography limits require 0 < min_size_pt <= max_size_pt")
  }
  base <- switch(layout,
                 `single-column` = 8.5,
                 intermediate = 8.75,
                 `double-column` = 9,
                 `full-page` = 9,
                 8.5)
  if (!identical(journal_profile, "generic")) base <- profile_defaults[["preferred"]]
  axis_candidates <- switch(
    config$schema_id %||% "",
    categorical = c("group"),
    interval = c("label"),
    composition = c("component", "sample_id"),
    matrix = c("row_id", "column_id"),
    flow = c("state"),
    hierarchy = c("label"),
    profile = c("property", "profile_id"),
    events = c("subject_id", "label", "state"),
    survival = c("group", "event_type"),
    `meta-analysis` = c("study_id", "moderator"),
    `multivariate-long` = c("variable", "group"),
    hydrochemistry = c("analyte", "sample_id"),
    `ecology-community` = c("species", "sample_id", "group"),
    classification = c("group", "predicted_class"),
    interpretation = c("feature", "group"),
    genomic = c("chromosome", "type"),
    `sequence-logo` = c("symbol"),
    `state-series` = c("subject_id", "state"),
    `matrix-links` = c("row_id", "column_id", "from", "to"),
    c("group", "label", "component", "state", "property", "variable")
  )
  label_columns <- if (is.null(dat)) character() else intersect(axis_candidates, names(dat))
  label_values <- if (length(label_columns)) {
    unlist(lapply(label_columns, function(column) as.character(dat[[column]])), use.names = FALSE)
  } else character()
  label_values <- label_values[!is.na(label_values)]
  longest_label <- if (length(label_values)) max(nchar(label_values, type = "width")) else 0L
  category_count <- if (length(label_columns)) {
    max(vapply(label_columns, function(column) length(unique(dat[[column]][!is.na(dat[[column]])])), integer(1)))
  } else 0L
  density_penalty <- 0
  if (effective_panel_width < 58) density_penalty <- density_penalty + 0.25
  if (effective_panel_width < 46) density_penalty <- density_penalty + 0.25
  if (height < 58) density_penalty <- density_penalty + 0.25
  if (category_count > 8) density_penalty <- density_penalty + 0.25
  if (longest_label > 16) density_penalty <- density_penalty + 0.25
  base <- base - density_penalty
  if (identical(config$typography_mode %||% "auto", "manual") &&
      !is.null(config$base_size_pt) && is.finite(as.numeric(config$base_size_pt))) {
    base <- as.numeric(config$base_size_pt)
  }
  base <- max(min_pt, min(max_pt, base))
  x_axis_angle <- if (category_count > 10 || longest_label > 20) 45 else if (category_count > 6 || longest_label > 13) 30 else 0
  needs_layout_revision <- effective_panel_width < 40 || category_count > 14 || longest_label > 28
  layout_messages <- character()
  if (effective_panel_width < 40) layout_messages <- c(layout_messages, "panel width is below 40 mm; increase figure width or reduce facet columns")
  if (category_count > 14) layout_messages <- c(layout_messages, "more than 14 categories; use horizontal layout, grouping, or multiple panels")
  if (longest_label > 28) layout_messages <- c(layout_messages, "long labels require wrapping or a horizontal layout")
  list(
    mode = config$typography_mode %||% "auto",
    journal_profile = journal_profile,
    minimum_pt = min_pt,
    maximum_pt = max_pt,
    layout = layout,
    panel_count = panels,
    facet_columns = facet_columns,
    effective_panel_width_mm = round(effective_panel_width, 2),
    longest_label_characters = longest_label,
    category_count = category_count,
    density_penalty_pt = density_penalty,
    base_pt = base,
    axis_title_pt = if (journal_profile == "generic") min(10, base + 0.75) else min(max_pt, base + 0.75),
    axis_text_pt = base,
    legend_pt = base,
    strip_pt = if (journal_profile == "generic") min(9.5, base + 0.25) else min(max_pt, base + 0.25),
    caption_pt = max(min_pt, base - 0.75),
    panel_tag_pt = if (journal_profile == "nature") 8 else min(max_pt + 1.5, base + 2),
    internal_title_pt = min(max_pt + 2, base + 2),
    x_axis_angle = x_axis_angle,
    needs_layout_revision = needs_layout_revision,
    layout_messages = layout_messages
  )
}

theme_publication <- function(typography, fonts = configure_figure_fonts()) {
  ggplot2::theme_classic(base_size = typography$base_pt) +
    ggplot2::theme(
      text = ggplot2::element_text(family = fonts$english, color = "#222222"),
      plot.title = ggplot2::element_text(family = fonts$chinese, face = "bold",
                                         size = typography$internal_title_pt, hjust = 0, lineheight = 1.08,
                                         margin = ggplot2::margin(b = 2.5)),
      plot.subtitle = ggplot2::element_text(family = fonts$english, color = "#4D4D4D",
                                            size = typography$base_pt, lineheight = 1.05,
                                            margin = ggplot2::margin(b = 4)),
      axis.title = ggplot2::element_text(size = typography$axis_title_pt),
      axis.text = ggplot2::element_text(size = typography$axis_text_pt, color = "#222222"),
      axis.text.x = ggplot2::element_text(
        angle = typography$x_axis_angle,
        hjust = if (typography$x_axis_angle == 0) 0.5 else 1,
        vjust = if (typography$x_axis_angle == 0) 1 else 1
      ),
      axis.line = ggplot2::element_blank(),
      axis.ticks = ggplot2::element_line(linewidth = 0.25, color = "#222222"),
      axis.ticks.length = grid::unit(1.5, "mm"),
      legend.position = "top",
      legend.title = ggplot2::element_text(family = fonts$english, face = "bold", size = typography$legend_pt),
      legend.text = ggplot2::element_text(size = typography$legend_pt),
      legend.key.height = grid::unit(3.8, "mm"),
      strip.background = ggplot2::element_rect(fill = "#F2F2F2", color = NA),
      strip.text = ggplot2::element_text(face = "bold", size = typography$strip_pt),
      plot.caption = ggplot2::element_text(size = typography$caption_pt, color = "#555555", hjust = 0),
      plot.tag = ggplot2::element_text(face = "bold", size = typography$panel_tag_pt),
      panel.border = ggplot2::element_rect(fill = NA, color = "#222222", linewidth = 0.38),
      panel.background = ggplot2::element_rect(fill = "white", color = NA),
      plot.background = ggplot2::element_rect(fill = "white", color = NA),
      # Leave a physical safety zone around the final-size panel.  This is in
      # points (not pixels), so it remains stable for PDF and 300/600 dpi PNG.
      plot.margin = ggplot2::margin(8, 10, 7, 8)
    )
}

theme_borderless_scientific <- function() {
  ggplot2::theme(
    axis.line = ggplot2::element_blank(),
    axis.text = ggplot2::element_blank(),
    axis.text.x = ggplot2::element_blank(),
    axis.text.y = ggplot2::element_blank(),
    axis.ticks = ggplot2::element_blank(),
    axis.title = ggplot2::element_blank(),
    axis.title.x = ggplot2::element_blank(),
    axis.title.y = ggplot2::element_blank(),
    panel.grid = ggplot2::element_blank(),
    panel.border = ggplot2::element_blank()
  )
}

infer_panel_layout <- function(p, dat, config) {
  configured <- max(1L, as.integer(config$panel_count %||% 1L))
  facets <- character()
  if (!is.null(p$facet$params$facets)) facets <- names(p$facet$params$facets)
  if (!length(facets)) {
    facets <- unique(c(names(p$facet$params$rows), names(p$facet$params$cols)))
  }
  facets <- intersect(facets, names(dat))
  inferred <- if (length(facets)) nrow(unique(dat[facets])) else 1L
  panels <- max(configured, inferred, 1L)
  explicit_columns <- config$facet_columns %||% p$facet$params$ncol
  columns <- if (!is.null(explicit_columns) && is.finite(as.numeric(explicit_columns))) {
    max(1L, as.integer(explicit_columns))
  } else if (panels > 1L) {
    ceiling(sqrt(panels))
  } else 1L
  config$panel_count <- panels
  config$facet_columns <- columns
  config
}

adapt_annotation_typography <- function(p, typography, fonts) {
  # geom_text() sizes are millimetres whereas theme text is in points.  Clamp
  # data annotations to a final-size readable floor instead of allowing each
  # renderer's convenient preview constant to become microscopic after layout.
  minimum_mm <- max(7.5, typography$base_pt - 0.5) / ggplot2::.pt
  for (index in seq_along(p$layers)) {
    layer <- p$layers[[index]]
    if (inherits(layer$geom, "GeomText") || inherits(layer$geom, "GeomLabel")) {
      existing <- layer$aes_params$size
      if (is.null(existing) || !is.finite(existing) || existing < minimum_mm) {
        p$layers[[index]]$aes_params$size <- minimum_mm
      }
      if (is.null(layer$aes_params$family) || !nzchar(layer$aes_params$family)) {
        p$layers[[index]]$aes_params$family <- fonts$english
      }
    }
  }
  p
}

apply_discrete_scales <- function(p) {
  p +
    ggplot2::scale_color_manual(values = palette_discrete) +
    ggplot2::scale_fill_manual(values = palette_discrete)
}

compact_continuous_legend_breaks <- function(p, target = 3L) {
  # Automatic continuous legends often request five or more labels.  That is
  # readable on a screen preview but collides after a figure is reduced to a
  # journal column.  Only colour/fill guides with default breaks are compacted;
  # explicit scientific thresholds and all positional axes are preserved.
  for (index in seq_along(p$scales$scales)) {
    scale <- p$scales$scales[[index]]
    aesthetics <- scale$aesthetics
    if (is.null(aesthetics)) aesthetics <- character(0)
    is_colour_scale <- any(aesthetics %in% c("colour", "color", "fill"))
    uses_default_breaks <- inherits(scale$breaks, "waiver")
    if (inherits(scale, "ScaleContinuous") && is_colour_scale && uses_default_breaks) {
      p$scales$scales[[index]]$breaks <- local({
        n <- target
        function(limits) pretty(limits, n = n)
      })
    }
  }
  p
}

plot_title <- function(config) {
  config$name_zh %||% config$name_en %||% gsub("-", " ", config$recipe_id %||% "Scientific figure")
}

plot_subtitle <- function(config) {
  config$name_en %||% NULL
}

half_violin_geometry <- function(dat, width = 0.34) {
  groups <- levels(dat$group)
  pieces <- lapply(seq_along(groups), function(index) {
    values <- dat$value[dat$group == groups[[index]]]
    values <- values[is.finite(values)]
    if (length(unique(values)) < 2L) return(NULL)
    dens <- stats::density(values, n = 192, na.rm = TRUE)
    scaled <- dens$y / max(dens$y) * width
    n <- length(dens$x)
    data.frame(
      group = groups[[index]],
      polygon_id = index,
      plot_x = c(rep(index, n), rev(index - scaled)),
      plot_y = c(dens$x, rev(dens$x))
    )
  })
  do.call(rbind, pieces)
}

summary_mean_ci <- function(dat) {
  groups <- split(dat$value, dat$group)
  out <- do.call(rbind, lapply(names(groups), function(group_name) {
    x <- groups[[group_name]]
    n <- sum(!is.na(x))
    mean_value <- mean(x, na.rm = TRUE)
    if (n > 1) {
      se <- stats::sd(x, na.rm = TRUE) / sqrt(n)
      critical <- stats::qt(0.975, df = n - 1)
      lower <- mean_value - critical * se
      upper <- mean_value + critical * se
    } else {
      lower <- upper <- NA_real_
    }
    data.frame(group = group_name, mean = mean_value, lower = lower, upper = upper, n = n)
  }))
  rownames(out) <- NULL
  out
}

value_axis_label <- function(
    dat,
    fallback = "Value",
    style = getOption("r_soil.axis_unit_style", "slash-parentheses")) {
  allowed_styles <- c("slash-parentheses", "parentheses")
  if (!style %in% allowed_styles) {
    stop("Unknown axis-unit style: ", style,
         ". Use one of: ", paste(allowed_styles, collapse = ", "))
  }
  label <- fallback
  if ("variable" %in% names(dat)) {
    variables <- unique(trimws(as.character(dat$variable[!is.na(dat$variable)])))
    variables <- variables[nzchar(variables)]
    if (length(variables) == 1L) {
      label <- gsub("_", " ", variables[[1]], fixed = TRUE)
      label <- paste0(toupper(substr(label, 1, 1)), substr(label, 2, nchar(label)))
    }
  }
  if ("unit" %in% names(dat)) {
    units <- unique(trimws(as.character(dat$unit[!is.na(dat$unit)])))
    units <- units[nzchar(units)]
    if (length(units) == 1L) {
      unit_tokens <- strsplit(units[[1]], "[[:space:]]+")[[1]]
      unit_tokens <- gsub("^([[:alpha:]]+)\\^-([0-9]+)$", "\\1^{-\\2}", unit_tokens)
      unit_math <- paste(unit_tokens, collapse = "~")
      escaped_label <- gsub("'", "\\\\'", label, fixed = TRUE)
      has_cjk <- grepl("[\u3400-\u9FFF]", label, perl = TRUE)
      math_text <- if (identical(style, "slash-parentheses") && has_cjk) {
        paste0("plain('", escaped_label, "')*'/'~'('~", unit_math, "~')'")
      } else if (identical(style, "slash-parentheses")) {
        paste0("plain('", escaped_label, "')~'/'~'('~", unit_math, "~')'")
      } else {
        paste0("plain('", escaped_label, "')~'('~", unit_math, "~')'")
      }
      text_fallback <- if (identical(style, "slash-parentheses")) {
        paste0(label, if (has_cjk) "/ (" else " / (", units[[1]], ")")
      } else {
        paste0(label, " (", units[[1]], ")")
      }
      label <- tryCatch(parse(text = math_text)[[1]], error = function(e) text_fallback)
    }
  }
  label
}

render_distribution <- function(dat, recipe_id) {
  dat$group <- factor(dat$group, levels = unique(dat$group))
  value_label <- value_axis_label(dat)
  if (recipe_id == "histogram") {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = value, fill = group, color = group)) +
        ggplot2::geom_histogram(bins = 9, alpha = 0.35, position = "identity", linewidth = 0.3)
    ) + ggplot2::labs(x = value_label, y = "Count", fill = "Group", color = "Group"))
  }
  if (recipe_id == "frequency-polygon") {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = value, color = group)) +
        ggplot2::geom_freqpoly(bins = 9, linewidth = 0.65)
    ) + ggplot2::labs(x = value_label, y = "Count", color = "Group"))
  }
  if (recipe_id %in% c("density-plot", "pore-size-distribution")) {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = value, fill = group, color = group)) +
        ggplot2::geom_density(alpha = 0.22, linewidth = 0.55, adjust = 1)
    ) + ggplot2::labs(x = value_label, y = "Density", fill = "Group", color = "Group"))
  }
  if (recipe_id == "ecdf-plot") {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = value, color = group)) +
        ggplot2::stat_ecdf(linewidth = 0.65)
    ) + ggplot2::labs(x = value_label, y = "Cumulative probability", color = "Group"))
  }
  if (recipe_id == "ccdf-plot") {
    pieces <- do.call(rbind, lapply(split(dat, dat$group), function(part) {
      part <- part[order(part$value), , drop = FALSE]
      part$ccdf <- rev(seq_len(nrow(part))) / nrow(part)
      part
    }))
    return(apply_discrete_scales(
      ggplot2::ggplot(pieces, ggplot2::aes(x = value, y = ccdf, color = group)) +
        ggplot2::geom_step(linewidth = 0.65)
    ) + ggplot2::labs(x = value_label, y = "Complementary cumulative probability", color = "Group"))
  }
  if (recipe_id == "qq-plot") {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(sample = value, color = group)) +
        ggplot2::stat_qq(size = 1.4) + ggplot2::stat_qq_line(linewidth = 0.45) +
        ggplot2::facet_wrap(~group, scales = "free")
    ) + ggplot2::labs(x = "Theoretical quantile", y = "Sample quantile", color = "Group"))
  }
  if (recipe_id == "pp-plot") {
    pieces <- do.call(rbind, lapply(split(dat, dat$group), function(part) {
      z <- sort((part$value - mean(part$value)) / stats::sd(part$value))
      data.frame(group = part$group[1], theoretical = stats::pnorm(z), empirical = stats::ppoints(length(z)))
    }))
    return(apply_discrete_scales(
      ggplot2::ggplot(pieces, ggplot2::aes(x = theoretical, y = empirical, color = group)) +
        ggplot2::geom_abline(slope = 1, intercept = 0, linetype = 2, color = "#666666") +
        ggplot2::geom_point(size = 1.5) + ggplot2::coord_equal()
    ) + ggplot2::labs(x = "Theoretical probability", y = "Empirical probability", color = "Group"))
  }
  if (recipe_id == "ridgeline-plot") {
    pieces <- lapply(seq_along(levels(dat$group)), function(index) {
      group_name <- levels(dat$group)[index]
      x <- dat$value[dat$group == group_name]
      dens <- stats::density(x, n = 128, na.rm = TRUE)
      data.frame(group = group_name, x = dens$x, density = dens$y / max(dens$y), offset = index)
    })
    ridge <- do.call(rbind, pieces)
    return(apply_discrete_scales(
      ggplot2::ggplot(ridge, ggplot2::aes(x = x, y = offset, color = group)) +
        ggplot2::geom_ribbon(ggplot2::aes(ymin = offset, ymax = offset + density * 0.75, fill = group),
                             alpha = 0.35, color = NA) +
        ggplot2::geom_line(ggplot2::aes(y = offset + density * 0.75), linewidth = 0.45) +
        ggplot2::scale_y_continuous(breaks = seq_along(levels(dat$group)), labels = levels(dat$group))
    ) + ggplot2::labs(x = value_label, y = NULL, color = "Group", fill = "Group"))
  }
  if (recipe_id == "quantile-dotplot") {
    probs <- seq(0.05, 0.95, by = 0.05)
    pieces <- split(dat$value, dat$group)
    dots <- do.call(rbind, lapply(names(pieces), function(group_name) {
      data.frame(group = group_name, value = stats::quantile(pieces[[group_name]], probs = probs, names = FALSE), probability = probs)
    }))
    return(apply_discrete_scales(
      ggplot2::ggplot(dots, ggplot2::aes(x = group, y = value, color = group)) +
        ggplot2::geom_point(size = 1.25)
    ) + ggplot2::guides(color = "none") + ggplot2::labs(x = NULL, y = value_label))
  }
  if (recipe_id %in% c("rug-plot", "spike-plot")) {
    p <- ggplot2::ggplot(dat, ggplot2::aes(x = value, color = group)) +
      ggplot2::geom_rug(sides = "b", linewidth = 0.55)
    if (recipe_id == "rug-plot") p <- p + ggplot2::geom_density(linewidth = 0.55)
    if (recipe_id == "spike-plot") {
      p <- p + ggplot2::geom_segment(ggplot2::aes(xend = value, y = 0, yend = 1), position = ggplot2::position_nudge(x = 0)) +
        ggplot2::facet_wrap(~group)
    }
    return(apply_discrete_scales(p) + ggplot2::labs(x = value_label, y = if (recipe_id == "rug-plot") "Density" else NULL, color = "Group"))
  }
  base <- ggplot2::ggplot(dat, ggplot2::aes(x = group, y = value, fill = group, color = group))
  if (recipe_id %in% c("strip-plot", "beeswarm-plot", "quasirandom-plot", "sina-plot", "dotplot-stacked")) {
    point_dat <- dat
    point_dat$plot_x <- as.numeric(point_dat$group) + ave(
      point_dat$value, point_dat$group,
      FUN = function(z) seq(-0.16, 0.16, length.out = length(z))[rank(z, ties.method = "first")]
    )
    p <- ggplot2::ggplot(point_dat, ggplot2::aes(x = plot_x, y = value, color = group)) +
      ggplot2::geom_point(size = 1.55, alpha = 0.85) +
      ggplot2::scale_x_continuous(breaks = seq_along(levels(dat$group)), labels = levels(dat$group))
  } else if (recipe_id %in% c("boxplot", "notched-boxplot", "variable-width-boxplot", "letter-value-plot")) {
    p <- base + ggplot2::geom_boxplot(
      width = 0.48, outlier.shape = NA, alpha = 0.25, linewidth = 0.45,
      notch = recipe_id == "notched-boxplot", varwidth = recipe_id == "variable-width-boxplot"
    ) +
      ggplot2::geom_jitter(width = 0.08, height = 0, size = 1.4, alpha = 0.8)
  } else if (recipe_id %in% c("violin-plot", "beanplot")) {
    p <- base + ggplot2::geom_violin(trim = FALSE, alpha = 0.25, linewidth = 0.4) +
      ggplot2::geom_boxplot(width = 0.12, outlier.shape = NA, fill = "white", color = "#222222", linewidth = 0.4)
  } else if (recipe_id %in% c("half-violin", "raincloud-plot", "half-eye-plot")) {
    density_dat <- half_violin_geometry(dat)
    point_dat <- dat
    point_dat$plot_x <- as.numeric(point_dat$group) +
      0.13 + ave(seq_len(nrow(point_dat)), point_dat$group,
                 FUN = function(z) seq(-0.045, 0.045, length.out = length(z)))
    p <- ggplot2::ggplot() +
      ggplot2::geom_polygon(
        data = density_dat,
        ggplot2::aes(x = plot_x, y = plot_y, group = polygon_id, fill = group, color = group),
        alpha = 0.24, linewidth = 0.38
      ) +
      ggplot2::geom_boxplot(
        data = dat,
        ggplot2::aes(x = as.numeric(group), y = value, group = group),
        width = 0.105, outlier.shape = NA, fill = "white", color = "#222222",
        linewidth = 0.38
      ) +
      ggplot2::geom_point(
        data = point_dat,
        ggplot2::aes(x = plot_x, y = value, fill = group, color = group),
        shape = 21, size = 1.55, stroke = 0.35, alpha = 0.82
      ) +
      ggplot2::scale_x_continuous(
        breaks = seq_along(levels(dat$group)), labels = levels(dat$group),
        expand = ggplot2::expansion(mult = c(0.16, 0.18))
      )
    if (recipe_id == "half-violin") p <- p + ggplot2::guides(fill = "none", color = "none")
  } else if (recipe_id == "hdr-boxplot") {
    p <- base +
      ggplot2::geom_boxplot(width = 0.52, outlier.shape = NA, alpha = 0.18) +
      ggplot2::stat_summary(fun.min = function(x) stats::quantile(x, 0.05),
                            fun.max = function(x) stats::quantile(x, 0.95),
                            geom = "errorbar", width = 0.18, linewidth = 0.55, color = "#222222") +
      ggplot2::geom_jitter(width = 0.07, size = 1.2, alpha = 0.7)
  } else {
    p <- base + ggplot2::geom_violin(trim = FALSE, alpha = 0.18, linewidth = 0.35) +
      ggplot2::geom_boxplot(width = 0.12, outlier.shape = NA, fill = "white", color = "#222222", linewidth = 0.4) +
      ggplot2::geom_jitter(width = 0.08, height = 0, size = 1.25, alpha = 0.75)
  }
  apply_discrete_scales(p) + ggplot2::guides(fill = "none", color = "none") +
    ggplot2::labs(x = NULL, y = value_label)
}

render_comparison <- function(dat, recipe_id) {
  dat$group <- factor(dat$group, levels = unique(dat$group))
  value_label <- value_axis_label(dat)
  sums <- summary_mean_ci(dat)
  sums$group <- factor(sums$group, levels = levels(dat$group))
  if (recipe_id == "bar-count") {
    counts <- as.data.frame(table(dat$group), stringsAsFactors = FALSE)
    names(counts) <- c("group", "count")
    return(apply_discrete_scales(
      ggplot2::ggplot(counts, ggplot2::aes(x = group, y = count, fill = group)) +
        ggplot2::geom_col(width = 0.66, color = "#222222", linewidth = 0.25) +
        ggplot2::geom_text(ggplot2::aes(label = count), vjust = -0.4, size = 2.5)
    ) + ggplot2::guides(fill = "none") + ggplot2::expand_limits(y = max(counts$count) * 1.12) +
      ggplot2::labs(x = NULL, y = "Independent observations (n)"))
  }
  if (recipe_id %in% c("bar-value", "grouped-bar")) {
    return(apply_discrete_scales(
      ggplot2::ggplot(sums, ggplot2::aes(x = group, y = mean, fill = group)) +
        ggplot2::geom_col(width = 0.58, color = "#222222", linewidth = 0.25, alpha = 0.78) +
        ggplot2::geom_errorbar(ggplot2::aes(ymin = lower, ymax = upper), width = 0.12, linewidth = 0.45) +
        ggplot2::geom_point(data = dat, ggplot2::aes(x = group, y = value), inherit.aes = FALSE,
                            position = ggplot2::position_jitter(width = 0.07), size = 1.0, alpha = 0.65)
    ) + ggplot2::guides(fill = "none") + ggplot2::labs(x = NULL, y = value_label))
  }
  if (recipe_id == "diverging-stacked-bar") {
    sums$centered <- sums$mean - mean(sums$mean)
    return(apply_discrete_scales(
      ggplot2::ggplot(sums, ggplot2::aes(x = reorder(group, centered), y = centered, fill = group)) +
        ggplot2::geom_col(width = 0.62, color = "#222222", linewidth = 0.25) +
        ggplot2::geom_hline(yintercept = 0, color = "#333333", linewidth = 0.35) +
        ggplot2::coord_flip()
    ) + ggplot2::guides(fill = "none") + ggplot2::labs(x = NULL, y = "Mean deviation from grand mean"))
  }
  if (recipe_id %in% c("cleveland-dotplot", "lollipop-chart")) {
    lollipop_baseline <- min(sums$mean) * 0.95
    return(apply_discrete_scales(
      ggplot2::ggplot(sums, ggplot2::aes(x = group, y = mean, color = group)) +
        {if (recipe_id == "lollipop-chart") ggplot2::geom_segment(
          ggplot2::aes(xend = group, y = lollipop_baseline, yend = mean),
          color = "#B3B3B3", linewidth = 0.65
        ) else ggplot2::geom_blank()} +
        ggplot2::geom_point(size = 2.4) + ggplot2::coord_flip()
    ) + ggplot2::guides(color = "none") + ggplot2::labs(x = NULL, y = value_label))
  }
  if (recipe_id %in% c("dumbbell-plot", "paired-dotplot", "slopegraph", "bump-chart") && "block" %in% names(dat)) {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = group, y = value, group = block)) +
        ggplot2::geom_line(color = "#A6A6A6", linewidth = 0.4) +
        ggplot2::geom_point(ggplot2::aes(color = group, shape = group), size = 1.7)
    ) + ggplot2::scale_shape_manual(values = c(16, 17, 15, 18, 3, 7)) +
      ggplot2::guides(color = "none", shape = "none") + ggplot2::labs(x = NULL, y = value_label))
  }
  if (recipe_id == "pareto-chart") {
    values <- stats::aggregate(value ~ group, dat, sum)
    values <- values[order(values$value, decreasing = TRUE), , drop = FALSE]
    values$group <- factor(values$group, levels = values$group)
    values$cumulative_percent <- cumsum(values$value) / sum(values$value) * 100
    return(apply_discrete_scales(
      ggplot2::ggplot(values, ggplot2::aes(x = group, y = value, fill = group)) +
        ggplot2::geom_col(width = 0.66, color = "#222222", linewidth = 0.25) +
        ggplot2::geom_text(ggplot2::aes(label = paste0(round(cumulative_percent), "%")), vjust = -0.35, size = 2.4)
    ) + ggplot2::guides(fill = "none") + ggplot2::labs(x = NULL, y = "Total; labels show cumulative percent"))
  }
  if (recipe_id == "superplot" && "block" %in% names(dat)) {
    block_means <- stats::aggregate(value ~ block + group, dat, mean)
    return(apply_discrete_scales(
      ggplot2::ggplot(block_means, ggplot2::aes(x = group, y = value, color = group)) +
        ggplot2::geom_line(ggplot2::aes(group = block), color = "#B3B3B3", linewidth = 0.35) +
        ggplot2::geom_point(size = 1.7, alpha = 0.78) +
        ggplot2::geom_errorbar(data = sums, ggplot2::aes(x = group, ymin = lower, ymax = upper),
                               inherit.aes = FALSE, width = 0.12, linewidth = 0.55, color = "#222222") +
        ggplot2::geom_point(data = sums, ggplot2::aes(y = mean), shape = 21, size = 2.6,
                            fill = "white", stroke = 0.55)
    ) + ggplot2::guides(color = "none") +
      ggplot2::labs(x = NULL, y = value_label, caption = "Grey lines identify independent blocks; large symbols show group estimates."))
  }
  if (recipe_id == "small-multiples") {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = value, y = 0, color = group)) +
        ggplot2::geom_point(position = ggplot2::position_jitter(height = 0.08), size = 1.4) +
        ggplot2::facet_wrap(~group, ncol = 1) + ggplot2::guides(color = "none")
    ) + ggplot2::labs(x = value_label, y = NULL))
  }
  apply_discrete_scales(
    ggplot2::ggplot(dat, ggplot2::aes(x = group, y = value, color = group)) +
      ggplot2::geom_jitter(width = 0.07, height = 0, size = 1.35, alpha = 0.75) +
      ggplot2::geom_errorbar(data = sums, ggplot2::aes(x = group, ymin = lower, ymax = upper),
                             inherit.aes = FALSE, width = 0.09, linewidth = 0.5, color = "#222222") +
      ggplot2::geom_point(data = sums, ggplot2::aes(x = group, y = mean), inherit.aes = FALSE,
                          shape = 21, size = 2.2, fill = "white", color = "#222222", stroke = 0.5)
  ) + ggplot2::guides(color = "none") + ggplot2::labs(x = NULL, y = value_label)
}

render_waterfall <- function(dat) {
  values <- stats::aggregate(value ~ group, dat, mean)
  values$group <- factor(values$group, levels = values$group)
  values$delta <- values$value - mean(values$value)
  values$end <- cumsum(values$delta)
  values$start <- c(0, head(values$end, -1))
  values$ymin <- pmin(values$start, values$end)
  values$ymax <- pmax(values$start, values$end)
  values$direction <- ifelse(values$delta >= 0, "Increase", "Decrease")
  ggplot2::ggplot(values, ggplot2::aes(x = group, ymin = ymin, ymax = ymax, fill = direction)) +
    ggplot2::geom_rect(ggplot2::aes(xmin = as.numeric(group) - 0.34, xmax = as.numeric(group) + 0.34),
                       color = "#333333", linewidth = 0.3) +
    ggplot2::scale_fill_manual(values = c(Increase = "#0072B2", Decrease = "#D55E00")) +
    ggplot2::geom_hline(yintercept = 0, color = "#555555", linewidth = 0.35) +
    ggplot2::labs(x = NULL, y = "Cumulative centered change", fill = NULL)
}

render_interval <- function(dat) {
  dat$label <- factor(dat$label, levels = rev(dat$label))
  reference <- if ("reference" %in% names(dat) && any(!is.na(dat$reference))) dat$reference[which(!is.na(dat$reference))[1]] else 0
  p <- ggplot2::ggplot(dat, ggplot2::aes(x = estimate, y = label)) +
    ggplot2::geom_vline(xintercept = reference, linetype = 2, color = "#666666", linewidth = 0.4) +
    ggplot2::geom_errorbarh(ggplot2::aes(xmin = lower, xmax = upper, color = group),
                            height = 0.15, linewidth = 0.5) +
    ggplot2::geom_point(ggplot2::aes(color = group), size = 1.8) +
    ggplot2::labs(x = "Estimate and interval", y = NULL, color = NULL) +
    ggplot2::guides(color = ggplot2::guide_legend(ncol = 2, byrow = TRUE))
  apply_discrete_scales(p)
}

render_bullet <- function(dat) {
  dat$label <- factor(dat$label, levels = rev(dat$label))
  dat$reference_value <- if ("reference" %in% names(dat)) dat$reference else 0
  ggplot2::ggplot(dat, ggplot2::aes(y = label)) +
    ggplot2::geom_segment(ggplot2::aes(x = lower, xend = upper, yend = label), linewidth = 5,
                          color = "#D9D9D9", lineend = "butt") +
    ggplot2::geom_segment(ggplot2::aes(x = lower, xend = estimate, yend = label), linewidth = 2.3,
                          color = "#0072B2", lineend = "butt") +
    ggplot2::geom_point(ggplot2::aes(x = reference_value), shape = 21, fill = "white", size = 2.0) +
    ggplot2::labs(x = "Observed value, target and reference range", y = NULL)
}

render_relationship <- function(dat, recipe_id) {
  if (!"group" %in% names(dat)) dat$group <- "All"
  if (recipe_id %in% c("hexbin-plot", "rect-bin2d")) {
    bx <- cut(dat$x, breaks = 7, include.lowest = TRUE, labels = FALSE)
    by <- cut(dat$y, breaks = 7, include.lowest = TRUE, labels = FALSE)
    binned <- stats::aggregate(rep(1, nrow(dat)), list(bx = bx, by = by), sum)
    names(binned)[3] <- "count"
    return(ggplot2::ggplot(binned, ggplot2::aes(x = bx, y = by, fill = count)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.25) +
      ggplot2::scale_fill_viridis_c(option = "C") +
      ggplot2::labs(x = "Binned x", y = "Binned y", fill = "Count",
                    caption = if (recipe_id == "hexbin-plot") "Square-bin dependency-light approximation; install hexbin for true hexagons." else NULL))
  }
  if (recipe_id %in% c("density-2d", "density-raster", "scatter-density")) {
    p <- ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = group)) +
      ggplot2::geom_density_2d(linewidth = 0.5) +
      ggplot2::geom_point(size = 1.2, alpha = 0.7)
    return(apply_discrete_scales(p) + ggplot2::labs(x = "X", y = "Y", color = "Group"))
  }
  if (recipe_id %in% c("connected-scatter", "hysteresis-loop")) {
    dat <- dat[order(dat$group, dat$x), , drop = FALSE]
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = group, group = group)) +
        ggplot2::geom_path(linewidth = 0.6, arrow = if (recipe_id == "hysteresis-loop") grid::arrow(length = grid::unit(1.3, "mm")) else NULL) +
        ggplot2::geom_point(size = 1.4)
    ) + ggplot2::labs(x = "X", y = "Y", color = "Group"))
  }
  if (recipe_id == "cate-nelson-plot") {
    x_cut <- stats::median(dat$x)
    y_cut <- stats::median(dat$y)
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = group)) +
        ggplot2::geom_vline(xintercept = x_cut, linetype = 2, linewidth = 0.4) +
        ggplot2::geom_hline(yintercept = y_cut, linetype = 2, linewidth = 0.4) +
        ggplot2::geom_point(size = 1.7)
    ) + ggplot2::labs(x = "Soil-test value", y = "Response", color = "Group"))
  }
  if (recipe_id == "rating-curve") {
    dat <- dat[order(dat$x), , drop = FALSE]
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = group)) +
        ggplot2::geom_point(size = 1.5) +
        ggplot2::geom_smooth(method = "lm", formula = y ~ poly(x, 2), se = TRUE, linewidth = 0.55)
    ) + ggplot2::labs(x = "Stage", y = "Discharge", color = "Group"))
  }
  p <- ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = group))
  if (recipe_id == "bubble-chart" && "size" %in% names(dat)) {
    p <- p + ggplot2::geom_point(ggplot2::aes(size = size), alpha = 0.72) +
      ggplot2::scale_size_area(max_size = 5)
  } else if (recipe_id %in% c("loess-plot", "gam-smooth", "dose-response-curve", "incubation-kinetics", "adsorption-isotherm")) {
    p <- p + ggplot2::geom_point(size = 1.5, alpha = 0.78) +
      ggplot2::geom_smooth(method = "loess", formula = y ~ x, se = TRUE, linewidth = 0.55, alpha = 0.13,
                           span = 1)
  } else if (recipe_id == "response-surface") {
    p <- ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y)) +
      ggplot2::stat_summary_2d(ggplot2::aes(z = y, fill = ggplot2::after_stat(value)), bins = 5, fun = mean) +
      ggplot2::scale_fill_viridis_c(option = "C")
    return(p + ggplot2::labs(x = "Predictor 1", y = "Predictor 2", fill = "Response"))
  } else {
    p <- p + ggplot2::geom_point(size = 1.6, alpha = 0.78) +
      {if (recipe_id %in% c("regression-line")) ggplot2::geom_smooth(
        method = "lm", formula = y ~ x, se = TRUE, linewidth = 0.55, alpha = 0.13
      ) else ggplot2::geom_blank()}
  }
  apply_discrete_scales(p) + ggplot2::labs(x = "X", y = "Y", color = "Group", size = "Size")
}

render_bagplot <- function(dat) {
  hull <- dat[grDevices::chull(dat$x, dat$y), , drop = FALSE]
  center <- data.frame(x = stats::median(dat$x), y = stats::median(dat$y))
  apply_discrete_scales(
    ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = group)) +
      ggplot2::geom_polygon(data = hull, ggplot2::aes(fill = group), alpha = 0.12, show.legend = FALSE) +
      ggplot2::geom_point(size = 1.5) +
      ggplot2::geom_point(data = center, inherit.aes = FALSE, ggplot2::aes(x = x, y = y),
                          shape = 4, size = 3, stroke = 0.8, color = "#222222")
  ) + ggplot2::labs(x = "X", y = "Y", color = "Group")
}

render_ordination <- function(dat, recipe_id) {
  samples <- dat[dat$element_type != "arrow", , drop = FALSE]
  arrows <- dat[dat$element_type == "arrow", , drop = FALSE]
  p <- ggplot2::ggplot(samples, ggplot2::aes(x = axis1, y = axis2, color = group)) +
    ggplot2::geom_hline(yintercept = 0, color = "#DDDDDD", linewidth = 0.3) +
    ggplot2::geom_vline(xintercept = 0, color = "#DDDDDD", linewidth = 0.3) +
    ggplot2::geom_point(size = 1.8, alpha = 0.85)
  if (recipe_id == "ordination-hull") {
    hulls <- do.call(rbind, lapply(split(samples, samples$group), function(part) part[grDevices::chull(part$axis1, part$axis2), , drop = FALSE]))
    p <- p + ggplot2::geom_polygon(data = hulls, ggplot2::aes(fill = group), alpha = 0.12, show.legend = FALSE)
  }
  if (recipe_id == "ordination-ellipse") {
    ellipse_data <- do.call(rbind, lapply(split(samples, samples$group), function(part) {
      theta <- seq(0, 2 * pi, length.out = 101)
      covariance <- stats::cov(cbind(part$axis1, part$axis2)) + diag(1e-8, 2)
      transformed <- t(chol(covariance)) %*% rbind(cos(theta), sin(theta)) * sqrt(stats::qchisq(0.68, 2))
      data.frame(group = part$group[1], axis1 = mean(part$axis1) + transformed[1, ],
                 axis2 = mean(part$axis2) + transformed[2, ])
    }))
    p <- p + ggplot2::geom_polygon(data = ellipse_data, ggplot2::aes(fill = group), alpha = 0.10,
                                    show.legend = FALSE)
  }
  if (recipe_id %in% c("ordination-spider", "beta-dispersion-plot")) {
    centers <- stats::aggregate(cbind(axis1, axis2) ~ group, samples, mean)
    names(centers)[2:3] <- c("center1", "center2")
    spiders <- merge(samples, centers, by = "group")
    p <- p + ggplot2::geom_segment(
      data = spiders, ggplot2::aes(x = center1, y = center2, xend = axis1, yend = axis2, color = group),
      inherit.aes = FALSE, linewidth = 0.35, alpha = 0.65
    )
  }
  if (recipe_id == "procrustes-plot" && nrow(samples) >= 6) {
    first <- samples[seq_len(floor(nrow(samples) / 2)), , drop = FALSE]
    second <- samples[seq_len(nrow(first)) + nrow(first), , drop = FALSE]
    links <- data.frame(x = first$axis1, y = first$axis2, xend = second$axis1, yend = second$axis2)
    p <- p + ggplot2::geom_segment(data = links, ggplot2::aes(x = x, y = y, xend = xend, yend = yend),
                                   inherit.aes = FALSE, arrow = grid::arrow(length = grid::unit(1.2, "mm")),
                                   linewidth = 0.4, color = "#555555")
  }
  if (nrow(arrows) && grepl("biplot|triplot|envfit", recipe_id)) {
    p <- p +
      ggplot2::geom_segment(data = arrows, ggplot2::aes(x = 0, y = 0, xend = axis1, yend = axis2),
                            inherit.aes = FALSE, color = "#333333", linewidth = 0.4,
                            arrow = grid::arrow(length = grid::unit(1.6, "mm"))) +
      ggplot2::geom_text(data = arrows, ggplot2::aes(x = axis1, y = axis2, label = label),
                         inherit.aes = FALSE, size = 2.2, nudge_y = 0.04)
  }
  xlab <- if ("axis1_label" %in% names(dat)) dat$axis1_label[1] else "Axis 1"
  ylab <- if ("axis2_label" %in% names(dat)) dat$axis2_label[1] else "Axis 2"
  apply_discrete_scales(p) + ggplot2::coord_equal() + ggplot2::labs(x = xlab, y = ylab, color = "Group")
}

render_temporal <- function(dat, recipe_id = "line-chart") {
  if (!"group" %in% names(dat)) dat$group <- "All"
  dat <- dat[order(dat$group, dat$time), , drop = FALSE]
  value_label <- value_axis_label(dat)
  if (recipe_id == "spaghetti-plot" && "subject_id" %in% names(dat)) {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = time, y = value, color = group, group = subject_id)) +
        ggplot2::geom_line(linewidth = 0.55, alpha = 0.72) + ggplot2::geom_point(size = 1.15)
    ) + ggplot2::labs(x = "Time", y = value_label, color = "Group"))
  }
  if (recipe_id == "step-chart") {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = time, y = value, color = group, group = group)) +
        ggplot2::geom_step(linewidth = 0.65) + ggplot2::geom_point(size = 1.2)
    ) + ggplot2::labs(x = "Time", y = value_label, color = "Group"))
  }
  if (recipe_id %in% c("area-chart", "stacked-area", "streamgraph")) {
    position <- if (recipe_id == "area-chart") "identity" else "stack"
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = time, y = value, fill = group, group = group)) +
        ggplot2::geom_area(position = position, alpha = if (position == "identity") 0.30 else 0.75,
                           color = "white", linewidth = 0.25)
    ) + ggplot2::labs(x = "Time", y = value_label, fill = "Group"))
  }
  if (recipe_id == "horizon-chart") {
    dat$centered <- ave(dat$value, dat$group, FUN = function(x) x - mean(x))
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = time, y = centered, fill = group)) +
        ggplot2::geom_area(alpha = 0.65) + ggplot2::geom_hline(yintercept = 0, linewidth = 0.3) +
        ggplot2::facet_wrap(~group, ncol = 1, scales = "free_y") + ggplot2::guides(fill = "none")
    ) + ggplot2::labs(x = "Time", y = "Centered value"))
  }
  if (recipe_id == "lasagna-plot") {
    subject <- if ("subject_id" %in% names(dat)) dat$subject_id else dat$group
    dat$subject <- subject
    return(ggplot2::ggplot(dat, ggplot2::aes(x = time, y = subject, fill = value)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.25) +
      ggplot2::scale_fill_viridis_c(option = "C") + ggplot2::labs(x = "Time", y = "Subject", fill = "Value"))
  }
  if (recipe_id == "calendar-heatmap") {
    dat$week <- floor(dat$time / 7)
    dat$day <- dat$time %% 7
    return(ggplot2::ggplot(dat, ggplot2::aes(x = week, y = day, fill = value)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.25) + ggplot2::facet_wrap(~group) +
      ggplot2::scale_fill_viridis_c(option = "C") + ggplot2::labs(x = "Week", y = "Day of week", fill = "Value"))
  }
  if (recipe_id == "phenology-wheel") {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = time, y = value, fill = group)) +
        ggplot2::geom_col(position = "dodge", width = 0.8) + ggplot2::coord_polar()
    ) + ggplot2::labs(x = "Time", y = value_label, fill = "Group"))
  }
  if (recipe_id %in% c("autocorrelation-plot", "partial-autocorrelation")) {
    series <- stats::aggregate(value ~ time, dat, mean)$value
    values <- if (recipe_id == "autocorrelation-plot") {
      as.numeric(stats::acf(series, plot = FALSE, lag.max = min(8, length(series) - 1))$acf)
    } else {
      c(1, as.numeric(stats::pacf(series, plot = FALSE, lag.max = min(7, length(series) - 2))$acf))
    }
    ac <- data.frame(lag = seq_along(values) - 1, correlation = values)
    return(ggplot2::ggplot(ac, ggplot2::aes(x = lag, y = correlation)) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.3) +
      ggplot2::geom_segment(ggplot2::aes(xend = lag, y = 0, yend = correlation), linewidth = 0.65, color = "#0072B2") +
      ggplot2::geom_point(size = 1.6, color = "#0072B2") + ggplot2::labs(x = "Lag", y = "Correlation"))
  }
  if (recipe_id == "lag-plot") {
    parts <- do.call(rbind, lapply(split(dat, dat$group), function(part) {
      part <- part[order(part$time), , drop = FALSE]
      data.frame(group = part$group[-1], current = part$value[-1], previous = head(part$value, -1))
    }))
    return(apply_discrete_scales(
      ggplot2::ggplot(parts, ggplot2::aes(x = previous, y = current, color = group)) + ggplot2::geom_point(size = 1.7)
    ) + ggplot2::labs(x = "Value at t - 1", y = "Value at t", color = "Group"))
  }
  if (recipe_id %in% c("control-chart", "run-chart", "change-point-plot")) {
    center <- mean(dat$value)
    spread <- stats::sd(dat$value)
    p <- apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = time, y = value, color = group, group = group)) +
        ggplot2::geom_line(linewidth = 0.6) + ggplot2::geom_point(size = 1.3) +
        ggplot2::geom_hline(yintercept = center, color = "#333333", linewidth = 0.35)
    )
    if (recipe_id == "control-chart") p <- p + ggplot2::geom_hline(yintercept = center + c(-3, 3) * spread, linetype = 2, linewidth = 0.35)
    if (recipe_id == "change-point-plot") {
      aggregated <- stats::aggregate(value ~ time, dat, mean)
      change_time <- aggregated$time[which.max(abs(diff(aggregated$value))) + 1]
      p <- p + ggplot2::geom_vline(xintercept = change_time, linetype = 2, linewidth = 0.4)
    }
    return(p + ggplot2::labs(x = "Time", y = value_label, color = "Group"))
  }
  if (recipe_id == "cumulative-emissions") {
    dat$cumulative <- ave(dat$value, dat$group, FUN = cumsum)
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = time, y = cumulative, color = group, group = group)) +
        ggplot2::geom_line(linewidth = 0.65) + ggplot2::geom_point(size = 1.2)
    ) + ggplot2::labs(x = "Time", y = "Cumulative value", color = "Group"))
  }
  p <- ggplot2::ggplot(dat, ggplot2::aes(x = time, y = value, color = group, group = group)) +
    ggplot2::geom_line(linewidth = 0.65) + ggplot2::geom_point(size = 1.4)
  apply_discrete_scales(p) + ggplot2::labs(x = "Time", y = value_label, color = "Group")
}

render_composition <- function(dat, recipe_id) {
  totals <- stats::aggregate(value ~ sample_id, dat, sum)
  names(totals)[2] <- "total_value"
  dat <- merge(dat, totals, by = "sample_id")
  dat$proportion <- dat$value / dat$total_value
  if (recipe_id == "stacked-bar") {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = sample_id, y = value, fill = component)) +
        ggplot2::geom_col(width = 0.78, color = "white", linewidth = 0.25)
    ) + ggplot2::labs(x = NULL, y = "Total value", fill = "Component"))
  }
  if (recipe_id %in% c("waffle-chart", "pictogram-chart")) {
    one <- dat[dat$sample_id == dat$sample_id[1], , drop = FALSE]
    counts <- floor(one$proportion * 100)
    counts[which.max(one$proportion)] <- counts[which.max(one$proportion)] + 100 - sum(counts)
    waffle <- data.frame(
      cell = seq_len(100),
      component = rep(one$component, counts),
      x = (seq_len(100) - 1) %% 10,
      y = 9 - floor((seq_len(100) - 1) / 10)
    )
    geom <- if (recipe_id == "waffle-chart") ggplot2::geom_tile(color = "white", linewidth = 0.25) else
      ggplot2::geom_point(shape = 21, size = 2.1, color = "white")
    return(apply_discrete_scales(
      ggplot2::ggplot(waffle, ggplot2::aes(x = x, y = y, fill = component)) + geom +
        ggplot2::coord_equal() + ggplot2::theme_void()
    ) + ggplot2::labs(fill = "Component"))
  }
  if (recipe_id == "marimekko") {
    sample_totals <- unique(dat[c("sample_id", "total_value")])
    sample_totals <- sample_totals[order(sample_totals$sample_id), , drop = FALSE]
    sample_totals$xmax <- cumsum(sample_totals$total_value) / sum(sample_totals$total_value)
    sample_totals$xmin <- c(0, head(sample_totals$xmax, -1))
    dat <- merge(dat, sample_totals, by = c("sample_id", "total_value"))
    dat <- dat[order(dat$sample_id, dat$component), , drop = FALSE]
    dat$ymax <- ave(dat$proportion, dat$sample_id, FUN = cumsum)
    dat$ymin <- dat$ymax - dat$proportion
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax, fill = component)) +
        ggplot2::geom_rect(color = "white", linewidth = 0.3)
    ) + ggplot2::labs(x = "Sample width proportional to total", y = "Composition", fill = "Component"))
  }
  base <- ggplot2::ggplot(dat, ggplot2::aes(x = sample_id, y = proportion, fill = component)) +
    ggplot2::geom_col(width = 0.78, color = "white", linewidth = 0.25) +
    ggplot2::scale_y_continuous(labels = scales::label_percent()) +
    ggplot2::labs(x = NULL, y = "Composition", fill = "Component")
  if (grepl("pie|donut", recipe_id)) {
    one <- dat[dat$sample_id == dat$sample_id[1], , drop = FALSE]
    base <- ggplot2::ggplot(one, ggplot2::aes(x = if (grepl("donut", recipe_id)) 2 else 1,
                                              y = proportion, fill = component)) +
      ggplot2::geom_col(width = 1, color = "white", linewidth = 0.35) +
      ggplot2::coord_polar(theta = "y") +
      ggplot2::xlim(if (grepl("donut", recipe_id)) c(0.5, 2.5) else c(0, 1.5)) +
      ggplot2::theme_void(base_size = 8) + ggplot2::labs(fill = "Component")
  }
  apply_discrete_scales(base)
}

render_ternary <- function(dat) {
  total <- dat$part_a + dat$part_b + dat$part_c
  dat$tx <- (dat$part_b + 0.5 * dat$part_c) / total
  dat$ty <- (sqrt(3) / 2 * dat$part_c) / total
  triangle <- data.frame(x = c(0, 1, 0.5, 0), y = c(0, 0, sqrt(3) / 2, 0))
  p <- ggplot2::ggplot(dat, ggplot2::aes(x = tx, y = ty, color = group)) +
    ggplot2::geom_path(data = triangle, ggplot2::aes(x = x, y = y), inherit.aes = FALSE,
                       color = "#333333", linewidth = 0.55) +
    ggplot2::geom_point(size = 2) +
    ggplot2::annotate("text", x = -0.03, y = -0.03, label = "A", size = 2.6) +
    ggplot2::annotate("text", x = 1.03, y = -0.03, label = "B", size = 2.6) +
    ggplot2::annotate("text", x = 0.5, y = sqrt(3) / 2 + 0.04, label = "C", size = 2.6) +
    ggplot2::coord_equal(xlim = c(-0.08, 1.08), ylim = c(-0.08, 0.96), clip = "off") +
    ggplot2::theme_void(base_size = 8) + ggplot2::labs(color = "Group")
  apply_discrete_scales(p)
}

render_events <- function(dat, recipe_id) {
  if (!"group" %in% names(dat)) dat$group <- "All"
  dat$subject_id <- factor(dat$subject_id, levels = rev(unique(dat$subject_id)))
  p <- ggplot2::ggplot(dat, ggplot2::aes(y = subject_id, color = group)) +
    ggplot2::geom_segment(ggplot2::aes(x = start, xend = end, yend = subject_id), linewidth = 3.0,
                          lineend = "round", alpha = 0.72) +
    ggplot2::geom_point(ggplot2::aes(x = end), size = 1.5) +
    ggplot2::geom_text(ggplot2::aes(x = (start + end) / 2, label = label), color = "#222222",
                       size = 2.1, vjust = -0.9, check_overlap = TRUE)
  if (recipe_id == "event-timeline") {
    p <- p + ggplot2::geom_point(ggplot2::aes(x = start), shape = 21, fill = "white", size = 1.7)
  }
  apply_discrete_scales(p) + ggplot2::labs(x = "Time", y = "Subject", color = "Group")
}

survival_steps <- function(dat) {
  pieces <- lapply(split(dat, dat$group), function(part) {
    part <- part[order(part$time, -part$status), , drop = FALSE]
    times <- sort(unique(part$time))
    survival <- 1
    out <- data.frame(time = 0, survival = 1, group = part$group[1], events = 0, at_risk = nrow(part))
    for (time in times) {
      at_risk <- sum(part$time >= time)
      events <- sum(part$time == time & part$status == 1)
      if (events > 0) survival <- survival * (1 - events / at_risk)
      out <- rbind(out, data.frame(time = time, survival = survival, group = part$group[1],
                                   events = events, at_risk = at_risk))
    }
    out
  })
  do.call(rbind, pieces)
}

render_survival <- function(dat, recipe_id) {
  if (!"group" %in% names(dat)) dat$group <- "All"
  curves <- survival_steps(dat)
  curves$value <- if (recipe_id == "cumulative-incidence") 1 - curves$survival else curves$survival
  apply_discrete_scales(
    ggplot2::ggplot(curves, ggplot2::aes(x = time, y = value, color = group, group = group)) +
      ggplot2::geom_step(linewidth = 0.7) +
      ggplot2::geom_point(data = curves[curves$events == 0 & curves$time > 0, , drop = FALSE],
                          shape = 3, size = 1.3)
  ) + ggplot2::scale_y_continuous(limits = c(0, 1)) +
    ggplot2::labs(x = "Time", y = if (recipe_id == "cumulative-incidence") "Cumulative incidence" else "Survival probability",
                  color = "Group")
}

render_state_series <- function(dat) {
  if (!"duration" %in% names(dat)) dat$duration <- 1
  if (!"group" %in% names(dat)) dat$group <- "All"
  dat$subject_id <- factor(dat$subject_id, levels = rev(unique(dat$subject_id)))
  ggplot2::ggplot(dat, ggplot2::aes(fill = state)) +
    ggplot2::geom_rect(ggplot2::aes(xmin = time, xmax = time + duration,
                                    ymin = as.numeric(subject_id) - 0.38, ymax = as.numeric(subject_id) + 0.38),
                       color = "white", linewidth = 0.25) +
    ggplot2::scale_y_continuous(breaks = seq_along(levels(dat$subject_id)), labels = levels(dat$subject_id)) +
    ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::labs(x = "Time", y = "Subject", fill = "State")
}

render_climate <- function(dat) {
  ratio <- 2
  ggplot2::ggplot(dat, ggplot2::aes(x = time)) +
    ggplot2::geom_col(ggplot2::aes(y = precipitation / ratio), fill = "#56B4E9", alpha = 0.55, width = 0.78) +
    ggplot2::geom_line(ggplot2::aes(y = temperature, group = station), color = "#D55E00", linewidth = 0.7) +
    ggplot2::geom_point(ggplot2::aes(y = temperature), color = "#D55E00", size = 1.2) +
    ggplot2::scale_y_continuous("Temperature (°C)", sec.axis = ggplot2::sec_axis(~ . * ratio, name = "Precipitation (mm)")) +
    ggplot2::scale_x_continuous(breaks = 1:12) +
    ggplot2::labs(x = "Month", caption = "Walter–Lieth convention shown with an explicit 1 °C : 2 mm scale.")
}

render_temporal_uncertainty <- function(dat) {
  if (!all(c("lower", "upper") %in% names(dat))) stop("Fan chart requires lower and upper columns")
  if (!"group" %in% names(dat)) dat$group <- "All"
  apply_discrete_scales(
    ggplot2::ggplot(dat, ggplot2::aes(x = time, y = value, color = group, fill = group, group = group)) +
      ggplot2::geom_ribbon(ggplot2::aes(ymin = lower, ymax = upper), color = NA, alpha = 0.18) +
      ggplot2::geom_line(linewidth = 0.65)
  ) + ggplot2::labs(x = "Time", y = value_axis_label(dat), color = "Group", fill = "Group")
}

render_estimation <- function(dat, recipe_id) {
  dat$group <- factor(dat$group, levels = unique(dat$group))
  if (nlevels(dat$group) < 2) stop("Estimation display requires at least two groups")
  groups <- levels(dat$group)[1:2]
  first <- dat$value[dat$group == groups[1]]
  second <- dat$value[dat$group == groups[2]]
  difference <- mean(second) - mean(first)
  se <- sqrt(stats::var(first) / length(first) + stats::var(second) / length(second))
  critical <- stats::qt(0.975, df = max(1, length(first) + length(second) - 2))
  estimate <- data.frame(x = 3, y = difference, lower = difference - critical * se, upper = difference + critical * se)
  dat$x <- as.numeric(dat$group)
  ggplot2::ggplot(dat, ggplot2::aes(x = x, y = value, color = group)) +
    ggplot2::geom_point(position = ggplot2::position_jitter(width = 0.08), size = 1.4, alpha = 0.8) +
    ggplot2::stat_summary(fun = mean, geom = "crossbar", width = 0.35, linewidth = 0.45) +
    ggplot2::geom_errorbar(data = estimate, ggplot2::aes(x = x, ymin = lower, ymax = upper),
                           inherit.aes = FALSE, width = 0.10, linewidth = 0.55, color = "#222222") +
    ggplot2::geom_point(data = estimate, ggplot2::aes(x = x, y = y), inherit.aes = FALSE,
                        shape = 21, fill = "white", size = 2.2, color = "#222222") +
    ggplot2::geom_hline(yintercept = 0, linetype = 3, linewidth = 0.3, color = "#777777") +
    ggplot2::scale_x_continuous(
      breaks = 1:3,
      labels = c(groups, paste0(groups[2], "\n\u2212 ", groups[1])),
      expand = ggplot2::expansion(mult = c(0.10, 0.16))
    ) +
    ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::guides(color = "none") +
    ggplot2::labs(x = NULL, y = paste0(value_axis_label(dat), " / mean difference"))
}

render_meta_analysis <- function(dat, recipe_id) {
  if (!"variance" %in% names(dat)) dat$variance <- dat$se^2
  pooled <- stats::weighted.mean(dat$effect, w = 1 / dat$variance)
  dat$z <- dat$effect / dat$se
  dat$precision <- 1 / dat$se
  if (grepl("funnel", recipe_id)) {
    p <- ggplot2::ggplot(dat, ggplot2::aes(x = effect, y = se)) +
      ggplot2::geom_point(ggplot2::aes(color = moderator), size = 1.8) +
      ggplot2::geom_vline(xintercept = pooled, linewidth = 0.4) +
      ggplot2::geom_line(data = data.frame(se = seq(0, max(dat$se) * 1.1, length.out = 100)),
                         ggplot2::aes(x = pooled - 1.96 * se, y = se), inherit.aes = FALSE, linetype = 2) +
      ggplot2::geom_line(data = data.frame(se = seq(0, max(dat$se) * 1.1, length.out = 100)),
                         ggplot2::aes(x = pooled + 1.96 * se, y = se), inherit.aes = FALSE, linetype = 2) +
      ggplot2::scale_y_reverse()
    return(apply_discrete_scales(p) + ggplot2::labs(x = "Study effect", y = "Standard error", color = "Moderator"))
  }
  if (recipe_id == "galbraith-plot") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = precision, y = z)) +
      ggplot2::geom_point(size = 1.8, color = "#0072B2") +
      ggplot2::geom_abline(intercept = 0, slope = pooled, linewidth = 0.45) +
      ggplot2::labs(x = "Precision (1/SE)", y = "Standardized effect"))
  }
  if (recipe_id == "l-abbe-plot") {
    dat$rate_t <- dat$event_treatment / dat$total_treatment
    dat$rate_c <- dat$event_control / dat$total_control
    return(ggplot2::ggplot(dat, ggplot2::aes(x = rate_c, y = rate_t, size = total_treatment + total_control)) +
      ggplot2::geom_abline(slope = 1, intercept = 0, linetype = 2) +
      ggplot2::geom_point(color = "#0072B2", alpha = 0.75) + ggplot2::coord_equal() +
      ggplot2::scale_size_area(max_size = 5) + ggplot2::labs(x = "Control event rate", y = "Treatment event rate", size = "Total n"))
  }
  if (recipe_id == "baujat-plot") {
    dat$heterogeneity <- (dat$effect - pooled)^2 / dat$variance
    dat$influence <- abs(dat$effect - pooled) / dat$se
    return(ggplot2::ggplot(dat, ggplot2::aes(x = heterogeneity, y = influence, label = study_id)) +
      ggplot2::geom_point(color = "#D55E00", size = 1.8) + ggplot2::geom_text(size = 2.0, nudge_y = 0.12, check_overlap = TRUE) +
      ggplot2::labs(x = "Contribution to heterogeneity", y = "Standardized influence"))
  }
  ggplot2::ggplot(dat, ggplot2::aes(x = effect, y = reorder(study_id, effect))) +
    ggplot2::geom_errorbarh(ggplot2::aes(xmin = effect - 1.96 * se, xmax = effect + 1.96 * se), height = 0.14) +
    ggplot2::geom_point(color = "#0072B2", size = 1.8) + ggplot2::geom_vline(xintercept = pooled, linetype = 2) +
    ggplot2::labs(x = "Study effect and 95% interval", y = NULL)
}

render_multivariate <- function(dat, recipe_id) {
  dat$scaled <- ave(dat$value, dat$variable, FUN = function(x) {
    spread <- stats::sd(x)
    if (is.na(spread) || spread == 0) x * 0 else (x - mean(x)) / spread
  })
  dat$variable <- factor(dat$variable, levels = unique(dat$variable))
  if (recipe_id %in% c("radar-chart", "star-glyph")) {
    summaries <- stats::aggregate(scaled ~ group + variable, dat, mean)
    return(apply_discrete_scales(
      ggplot2::ggplot(summaries, ggplot2::aes(x = variable, y = scaled - min(scaled) + 0.1,
                                              group = group, color = group, fill = group)) +
        ggplot2::geom_polygon(alpha = 0.12, linewidth = 0.55) + ggplot2::geom_point(size = 1.3) +
        ggplot2::coord_polar()
    ) + ggplot2::labs(x = NULL, y = "Standardized value", color = "Group", fill = "Group"))
  }
  if (recipe_id == "andrews-curves") {
    wide <- reshape(dat[c("sample_id", "variable", "scaled", "group")], idvar = c("sample_id", "group"),
                    timevar = "variable", direction = "wide")
    value_columns <- grep("^scaled\\.", names(wide), value = TRUE)
    theta <- seq(-pi, pi, length.out = 120)
    curves <- do.call(rbind, lapply(seq_len(nrow(wide)), function(i) {
      coefficients <- as.numeric(wide[i, value_columns, drop = TRUE])
      y <- rep(coefficients[1] / sqrt(2), length(theta))
      if (length(coefficients) >= 2) y <- y + coefficients[2] * sin(theta)
      if (length(coefficients) >= 3) y <- y + coefficients[3] * cos(theta)
      if (length(coefficients) >= 4) y <- y + coefficients[4] * sin(2 * theta)
      data.frame(sample_id = wide$sample_id[i], group = wide$group[i], theta = theta, curve = y)
    }))
    return(apply_discrete_scales(
      ggplot2::ggplot(curves, ggplot2::aes(x = theta, y = curve, group = sample_id, color = group)) +
        ggplot2::geom_line(linewidth = 0.55, alpha = 0.75)
    ) + ggplot2::labs(x = expression(theta), y = "Andrews function", color = "Group"))
  }
  apply_discrete_scales(
    ggplot2::ggplot(dat, ggplot2::aes(x = variable, y = scaled, group = sample_id, color = group)) +
      ggplot2::geom_line(linewidth = 0.55, alpha = 0.72) + ggplot2::geom_point(size = 1.2)
  ) + ggplot2::labs(x = NULL, y = "Within-variable z-score", color = "Group")
}

render_multivariate_pairs <- function(dat) {
  variables <- unique(dat$variable)
  pairs <- utils::combn(variables, 2, simplify = FALSE)
  pair_data <- do.call(rbind, lapply(pairs, function(pair) {
    left <- dat[dat$variable == pair[1], c("sample_id", "group", "value")]
    right <- dat[dat$variable == pair[2], c("sample_id", "value")]
    names(left)[3] <- "x"
    names(right)[2] <- "y"
    merged <- merge(left, right, by = "sample_id")
    merged$pair <- paste(pair, collapse = " × ")
    merged
  }))
  apply_discrete_scales(
    ggplot2::ggplot(pair_data, ggplot2::aes(x = x, y = y, color = group)) +
      ggplot2::geom_point(size = 1.5, alpha = 0.78) + ggplot2::facet_wrap(~pair, scales = "free")
  ) + ggplot2::labs(x = "First variable", y = "Second variable", color = "Group")
}

render_hydrochemistry <- function(dat, recipe_id) {
  if (!"group" %in% names(dat)) dat$group <- dat$sample_id
  if (recipe_id == "schoeller-diagram") {
    dat$analyte <- factor(dat$analyte, levels = c("Ca", "Mg", "NaK", "HCO3CO3", "SO4", "Cl"))
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = analyte, y = value, group = sample_id, color = group)) +
        ggplot2::geom_line(linewidth = 0.6) + ggplot2::geom_point(size = 1.4) + ggplot2::scale_y_log10()
    ) + ggplot2::labs(x = "Ion", y = "Equivalent concentration (log scale)", color = "Group"))
  }
  wide <- reshape(dat[c("sample_id", "analyte", "value", "group")], idvar = c("sample_id", "group"),
                  timevar = "analyte", direction = "wide")
  names(wide) <- sub("value\\.", "", names(wide))
  if (recipe_id == "gibbs-diagram") {
    wide$x <- wide$NaK / (wide$NaK + wide$Ca)
    wide$y <- wide$Cl / (wide$Cl + wide$HCO3CO3)
    return(apply_discrete_scales(
      ggplot2::ggplot(wide, ggplot2::aes(x = x, y = y, color = group, label = sample_id)) +
        ggplot2::geom_point(size = 2) + ggplot2::geom_text(size = 2, nudge_y = 0.035) + ggplot2::coord_equal()
    ) + ggplot2::labs(x = "Na+K / (Na+K+Ca)", y = "Cl / (Cl+HCO3+CO3)", color = "Group"))
  }
  if (recipe_id == "stiff-diagram") {
    stiff <- do.call(rbind, lapply(seq_len(nrow(wide)), function(i) data.frame(
      sample_id = wide$sample_id[i], group = wide$group[i],
      x = c(-wide$Ca[i], -wide$Mg[i], -wide$NaK[i], wide$Cl[i], wide$SO4[i], wide$HCO3CO3[i]),
      y = c(3, 2, 1, 1, 2, 3)
    )))
    return(apply_discrete_scales(
      ggplot2::ggplot(stiff, ggplot2::aes(x = x, y = y, group = sample_id, color = group, fill = group)) +
        ggplot2::geom_polygon(alpha = 0.12, linewidth = 0.55) + ggplot2::facet_wrap(~sample_id) +
        ggplot2::geom_vline(xintercept = 0, linewidth = 0.3)
    ) + ggplot2::labs(x = "Cations ← equivalent percent → anions", y = NULL, color = "Group", fill = "Group"))
  }
  # Standardize to equivalent fractions by analyte name.  The input contract
  # deliberately requires the analyst to perform and document the meq/L
  # conversion before plotting; this renderer never mixes mass concentrations.
  required_ions <- c("Ca", "Mg", "NaK", "HCO3CO3", "SO4", "Cl")
  missing_ions <- setdiff(required_ions, names(wide))
  if (length(missing_ions)) stop("Piper/Durov input is missing ions: ", paste(missing_ions, collapse = ", "))
  cation_total <- wide$Ca + wide$Mg + wide$NaK
  anion_total <- wide$HCO3CO3 + wide$SO4 + wide$Cl
  wide$ca <- wide$Ca / cation_total
  wide$mg <- wide$Mg / cation_total
  wide$nak <- wide$NaK / cation_total
  wide$hco3 <- wide$HCO3CO3 / anion_total
  wide$so4 <- wide$SO4 / anion_total
  wide$cl <- wide$Cl / anion_total
  h <- sqrt(3) / 2

  # Two conventional lower ternaries.  Coordinates use the ion labels rather
  # than row order, making the output reproducible after input sorting.
  wide$cat_x <- wide$nak + 0.5 * wide$mg
  wide$cat_y <- h * wide$mg
  wide$an_x <- 2.2 + wide$cl + 0.5 * wide$so4
  wide$an_y <- h * wide$so4
  triangle_left <- data.frame(x = c(0, 1, 0.5, 0), y = c(0, 0, h, 0))
  triangle_right <- transform(triangle_left, x = x + 2.2)
  frame <- rbind(triangle_left, triangle_right)
  frame$panel <- rep(c("Cations", "Anions"), each = nrow(triangle_left))

  lower_points <- rbind(
    data.frame(sample_id = wide$sample_id, group = wide$group, x = wide$cat_x, y = wide$cat_y),
    data.frame(sample_id = wide$sample_id, group = wide$group, x = wide$an_x, y = wide$an_y)
  )
  if (recipe_id == "durov-diagram") {
    # Durov central square: the two ternary horizontal fractions are projected
    # without claiming an inferred hydrochemical class.
    square <- data.frame(x = c(1.05, 2.15, 2.15, 1.05, 1.05), y = c(0, 0, 1.1, 1.1, 0))
    projected <- data.frame(sample_id = wide$sample_id, group = wide$group,
                            x = 1.05 + 1.1 * wide$cat_x,
                            y = 1.1 * (wide$an_x - 2.2))
    return(apply_discrete_scales(
      ggplot2::ggplot() +
        ggplot2::geom_path(data = frame, ggplot2::aes(x = x, y = y, group = panel), color = "#333333") +
        ggplot2::geom_path(data = square, ggplot2::aes(x = x, y = y), color = "#333333") +
        ggplot2::geom_point(data = lower_points, ggplot2::aes(x = x, y = y, color = group), size = 1.8) +
        ggplot2::geom_point(data = projected, ggplot2::aes(x = x, y = y, color = group), size = 2.0, shape = 17) +
        ggplot2::coord_equal(xlim = c(-0.05, 3.25), ylim = c(-0.05, 1.18), clip = "off")
    ) + ggplot2::labs(x = "Equivalent fraction projection", y = NULL, color = "Group",
                      caption = "Triangles and central Durov projection use normalized milliequivalent fractions."))
  }

  # Piper diamond.  The affine projection preserves the two lower-triangle
  # horizontal ion fractions and provides the familiar central diagnostic field.
  diamond <- data.frame(x = c(1.1, 1.6, 2.1, 1.6, 1.1),
                        y = c(1.02, 1.02 + h, 1.02, 1.02 - h, 1.02))
  projected <- data.frame(
    sample_id = wide$sample_id,
    group = wide$group,
    x = 1.1 + 0.5 * (wide$cat_x + (wide$an_x - 2.2)),
    y = 1.02 + h * ((wide$an_x - 2.2) - wide$cat_x)
  )
  apply_discrete_scales(
    ggplot2::ggplot() +
      ggplot2::geom_path(data = frame, ggplot2::aes(x = x, y = y, group = panel), color = "#333333") +
      ggplot2::geom_path(data = diamond, ggplot2::aes(x = x, y = y), color = "#333333") +
      ggplot2::geom_point(data = lower_points, ggplot2::aes(x = x, y = y, color = group), size = 1.8) +
      ggplot2::geom_point(data = projected, ggplot2::aes(x = x, y = y, color = group), size = 2.1, shape = 17) +
      ggplot2::coord_equal(xlim = c(-0.05, 3.25), ylim = c(-0.05, 1.95), clip = "off")
  ) + ggplot2::labs(x = "Equivalent fraction projection", y = NULL, color = "Group",
                    caption = "Piper coordinates use normalized milliequivalent fractions from the supplied six-ion table.")
}

render_matrix <- function(dat, recipe_id) {
  if (recipe_id == "clustered-heatmap") {
    row_order <- stats::aggregate(value ~ row_id, dat, mean)
    col_order <- stats::aggregate(value ~ column_id, dat, mean)
    dat$row_id <- factor(dat$row_id, levels = row_order$row_id[order(row_order$value)])
    dat$column_id <- factor(dat$column_id, levels = col_order$column_id[order(col_order$value)])
  }
  if (recipe_id %in% c("dot-heatmap", "enrichment-dotplot", "hinton-diagram", "fluctuation-diagram")) {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, size = abs(value), color = value)) +
      ggplot2::geom_point(shape = if (recipe_id == "hinton-diagram") 22 else 16,
                          fill = if (recipe_id == "hinton-diagram") "white" else NA) +
      ggplot2::scale_size_area(max_size = 7) +
      ggplot2::scale_color_gradient2(low = "#2166AC", mid = "#BDBDBD", high = "#B2182B", midpoint = 0) +
      ggplot2::guides(
        color = ggplot2::guide_colorbar(order = 1, barwidth = grid::unit(20, "mm")),
        size = ggplot2::guide_legend(order = 2, nrow = 1)
      ) +
      ggplot2::theme(legend.box = "vertical") +
      ggplot2::labs(x = NULL, y = NULL, size = "Magnitude", color = "Value"))
  }
  if (recipe_id == "oncoprint") {
    dat$state <- cut(dat$value, breaks = c(-Inf, -0.2, 0.2, Inf), labels = c("Decrease", "Neutral", "Increase"))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, fill = state)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.35) +
      ggplot2::scale_fill_manual(values = c(Decrease = "#2166AC", Neutral = "#F2F2F2", Increase = "#B2182B")) +
      ggplot2::labs(x = NULL, y = NULL, fill = "State"))
  }
  p <- ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, fill = value)) +
    ggplot2::geom_tile(color = "white", linewidth = 0.35) +
    ggplot2::scale_fill_gradient2(low = "#2166AC", mid = "white", high = "#B2182B", midpoint = 0) +
    ggplot2::labs(x = NULL, y = NULL, fill = "Value")
  if (recipe_id %in% c("annotated-heatmap", "confusion-matrix", "association-plot", "mosaic-plot")) {
    p <- p + ggplot2::geom_text(ggplot2::aes(label = format(round(value, 2), nsmall = 2)), size = 2.1)
  }
  p + ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1))
}

render_mantel_composite <- function(dat) {
  if (!"group" %in% names(dat)) dat$group <- "Source"
  dat$group[is.na(dat$group) | !nzchar(trimws(dat$group))] <- "Source"
  cells <- dat[dat$element_type == "cell", , drop = FALSE]
  links <- dat[dat$element_type == "link", , drop = FALSE]
  variables <- unique(c(cells$row_id, cells$column_id))
  variable_count <- length(variables)
  cells$row_index <- match(cells$row_id, variables)
  cells$column_index <- match(cells$column_id, variables)
  cells <- cells[cells$column_index >= cells$row_index, , drop = FALSE]
  cells$x <- cells$column_index
  cells$y <- variable_count - cells$row_index + 1
  cells$significance <- ifelse(
    cells$p_value < 0.001, "***",
    ifelse(cells$p_value < 0.01, "**", ifelse(cells$p_value < 0.05, "*", ""))
  )

  sources <- unique(links[c("from", "group")])
  sources$source_y <- seq(variable_count - 0.35, 1.35, length.out = nrow(sources))
  sources$source_x <- -1.05
  links <- merge(links, sources, by = c("from", "group"), all.x = TRUE)
  links$target_index <- match(links$to, variables)
  links$target_x <- links$target_index
  links$target_y <- variable_count - links$target_index + 1
  links$link_significance <- ifelse(links$link_p < 0.05, "P < 0.05", "P ≥ 0.05")

  ggplot2::ggplot() +
    ggplot2::geom_tile(
      data = cells, ggplot2::aes(x = x, y = y, fill = value),
      width = 0.92, height = 0.92, color = "white", linewidth = 0.35
    ) +
    ggplot2::geom_text(
      data = cells, ggplot2::aes(x = x, y = y, label = significance),
      size = 2.0, color = "#222222"
    ) +
    ggplot2::geom_curve(
      data = links,
      ggplot2::aes(
        x = source_x, y = source_y, xend = target_x - 0.42, yend = target_y,
        linewidth = abs(link_value), color = link_significance, linetype = link_significance
      ),
      curvature = 0.20, alpha = 0.78
    ) +
    ggplot2::geom_point(
      data = sources, ggplot2::aes(x = source_x, y = source_y),
      shape = 21, size = 2.8, color = "#222222", fill = "#E69F00"
    ) +
    ggplot2::geom_text(
      data = sources, ggplot2::aes(x = source_x, y = source_y, label = from),
      hjust = 1, nudge_x = -0.12, size = 2.0
    ) +
    ggplot2::scale_x_continuous(
      breaks = seq_len(variable_count), labels = variables,
      limits = c(-2.35, variable_count + 0.55), expand = c(0, 0)
    ) +
    ggplot2::scale_y_continuous(
      breaks = seq_len(variable_count), labels = rev(variables),
      limits = c(0.45, variable_count + 0.55), expand = c(0, 0)
    ) +
    ggplot2::scale_fill_gradient2(
      low = "#2166AC", mid = "white", high = "#B2182B", midpoint = 0,
      limits = c(-1, 1)
    ) +
    ggplot2::scale_color_manual(values = c(`P < 0.05` = "#0072B2", `P ≥ 0.05` = "#A6A6A6")) +
    ggplot2::scale_linetype_manual(values = c(`P < 0.05` = 1, `P ≥ 0.05` = 2)) +
    ggplot2::scale_linewidth(range = c(0.35, 1.35)) +
    ggplot2::guides(
      fill = ggplot2::guide_colorbar(order = 1, barwidth = grid::unit(20, "mm")),
      color = ggplot2::guide_legend(order = 2),
      linetype = "none",
      linewidth = ggplot2::guide_legend(order = 3)
    ) +
    ggplot2::coord_cartesian(clip = "off") +
    ggplot2::labs(x = NULL, y = NULL, fill = "Matrix r", color = "Mantel", linetype = "Mantel", linewidth = "|Mantel r|")
}

render_flow <- function(dat, recipe_id) {
  dat$stage_factor <- factor(dat$stage, levels = sort(unique(dat$stage)))
  if (recipe_id %in% c("fishplot", "muller-plot")) {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = stage, y = value, fill = group, group = path_id)) +
        ggplot2::geom_area(position = "stack", alpha = 0.76, color = "white", linewidth = 0.25)
    ) + ggplot2::labs(x = "Stage", y = "Clone / lineage abundance", fill = "Lineage"))
  }
  apply_discrete_scales(
    ggplot2::ggplot(dat, ggplot2::aes(x = stage_factor, y = value, group = path_id, color = group)) +
      ggplot2::geom_line(linewidth = 1.3, alpha = 0.55, lineend = "round") +
      ggplot2::geom_point(size = 2.5) +
      ggplot2::geom_text(ggplot2::aes(label = state), size = 2.0, vjust = -1, check_overlap = TRUE)
  ) + ggplot2::labs(x = "Stage", y = "Flow value", color = "Group")
}

hierarchy_layout <- function(dat) {
  dat$level <- as.integer(dat$level)
  dat$x <- dat$level
  dat$y <- ave(seq_len(nrow(dat)), dat$level, FUN = function(z) seq(0, 1, length.out = length(z) + 2)[-c(1, length(z) + 2)])
  dat
}

render_hierarchy <- function(dat, recipe_id) {
  if (!"level" %in% names(dat)) dat$level <- 0
  if (!"group" %in% names(dat)) dat$group <- "All"
  if (recipe_id == "treemap") {
    leaves <- dat[!dat$node_id %in% dat$parent_id, , drop = FALSE]
    leaves <- leaves[order(leaves$group, -leaves$value), , drop = FALSE]
    leaves$xmax <- cumsum(leaves$value) / sum(leaves$value)
    leaves$xmin <- c(0, head(leaves$xmax, -1))
    return(apply_discrete_scales(
      ggplot2::ggplot(leaves) +
        ggplot2::geom_rect(ggplot2::aes(xmin = xmin, xmax = xmax, ymin = 0, ymax = 1, fill = group),
                           color = "white", linewidth = 0.4) +
        ggplot2::geom_text(ggplot2::aes(x = (xmin + xmax) / 2, y = 0.5, label = label), size = 2.1, check_overlap = TRUE) +
        ggplot2::theme_void()
    ) + ggplot2::labs(fill = "Group"))
  }
  if (recipe_id == "sunburst") {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = factor(level), y = value, fill = group)) +
        ggplot2::geom_col(position = "fill", color = "white", linewidth = 0.25) +
        ggplot2::coord_polar(theta = "y") + ggplot2::theme_void()
    ) + ggplot2::labs(fill = "Group"))
  }
  if (recipe_id == "icicle-plot") {
    dat <- dat[order(dat$level, dat$node_id), , drop = FALSE]
    dat$xmax <- ave(dat$value, dat$level, FUN = function(x) cumsum(x) / sum(x))
    dat$xmin <- ave(dat$xmax, dat$level, FUN = function(x) c(0, head(x, -1)))
    return(apply_discrete_scales(
      ggplot2::ggplot(dat) +
        ggplot2::geom_rect(ggplot2::aes(xmin = xmin, xmax = xmax, ymin = level, ymax = level + 0.9, fill = group),
                           color = "white", linewidth = 0.25) +
        ggplot2::geom_text(ggplot2::aes(x = (xmin + xmax) / 2, y = level + 0.45, label = label), size = 2, check_overlap = TRUE)
    ) + ggplot2::labs(x = NULL, y = "Hierarchy level", fill = "Group"))
  }
  layout <- hierarchy_layout(dat)
  parents <- layout[c("node_id", "x", "y")]
  names(parents) <- c("parent_id", "parent_x", "parent_y")
  edges <- merge(layout, parents, by = "parent_id", all.x = TRUE)
  leaves <- layout[!layout$node_id %in% layout$parent_id, , drop = FALSE]

  if (recipe_id == "tree-heatmap") {
    track_columns <- grep("^track_", names(leaves), value = TRUE)
    if (!length(track_columns)) stop("tree-heatmap requires one or more optional track_* columns")
    track_data <- do.call(rbind, lapply(seq_along(track_columns), function(track_index) {
      data.frame(
        node_id = leaves$node_id,
        y = leaves$y,
        track = sub("^track_", "", track_columns[[track_index]]),
        track_index = track_index,
        track_value = leaves[[track_columns[[track_index]]]]
      )
    }))
    track_data$x <- max(layout$x) + 1.15 + (track_data$track_index - 1) * 0.38
    track_labels <- unique(track_data[c("track", "track_index", "x")])
    return(ggplot2::ggplot(layout, ggplot2::aes(x = x, y = y)) +
      ggplot2::geom_segment(
        data = edges[!is.na(edges$parent_x), ],
        ggplot2::aes(x = parent_x, y = parent_y, xend = x, yend = y),
        inherit.aes = FALSE, color = "#8C8C8C", linewidth = 0.35
      ) +
      ggplot2::geom_point(ggplot2::aes(color = group, size = value), alpha = 0.86) +
      ggplot2::geom_text(
        data = leaves, ggplot2::aes(label = label), hjust = 0, nudge_x = 0.10,
        size = 2.0, check_overlap = TRUE
      ) +
      ggplot2::geom_tile(
        data = track_data, ggplot2::aes(x = x, y = y, fill = track_value),
        inherit.aes = FALSE, width = 0.32, height = 0.105, color = "white", linewidth = 0.25
      ) +
      ggplot2::geom_text(
        data = track_labels, ggplot2::aes(x = x, y = 1.06, label = track),
        inherit.aes = FALSE, angle = 45, hjust = 0, size = 1.9
      ) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::scale_size_area(max_size = 4.5, guide = "none") +
      ggplot2::scale_fill_viridis_c(option = "C", limits = range(track_data$track_value, na.rm = TRUE)) +
      ggplot2::coord_cartesian(
        xlim = c(min(layout$x) - 0.10, max(track_data$x) + 0.22),
        ylim = c(-0.03, 1.15), clip = "off"
      ) +
      ggplot2::labs(x = NULL, y = NULL, color = "Group", fill = "Track value") +
      ggplot2::theme(axis.text = ggplot2::element_blank(), axis.ticks = ggplot2::element_blank()))
  }

  if (recipe_id == "taxonomic-tree-bar") {
    maximum <- max(leaves$value, na.rm = TRUE)
    start <- max(layout$x) + 0.85
    leaves$bar_start <- start
    leaves$bar_end <- start + 1.25 * leaves$value / maximum
    return(apply_discrete_scales(
      ggplot2::ggplot(layout, ggplot2::aes(x = x, y = y)) +
        ggplot2::geom_segment(
          data = edges[!is.na(edges$parent_x), ],
          ggplot2::aes(x = parent_x, y = parent_y, xend = x, yend = y),
          inherit.aes = FALSE, color = "#8C8C8C", linewidth = 0.35
        ) +
        ggplot2::geom_point(ggplot2::aes(fill = group, size = value), shape = 21, color = "#222222") +
        ggplot2::geom_text(
          data = leaves, ggplot2::aes(label = label), hjust = 0, nudge_x = 0.10,
          size = 2.0, check_overlap = TRUE
        ) +
        ggplot2::geom_segment(
          data = leaves,
          ggplot2::aes(x = bar_start, xend = bar_end, y = y, yend = y, color = group),
          inherit.aes = FALSE, linewidth = 3.2, lineend = "butt"
        ) +
        ggplot2::scale_size_area(max_size = 4.5, guide = "none") +
        ggplot2::coord_cartesian(xlim = c(-0.1, max(leaves$bar_end) + 0.12), clip = "off")
    ) + ggplot2::labs(x = NULL, y = NULL, fill = "Group", color = "Group") +
      ggplot2::theme(axis.text = ggplot2::element_blank(), axis.ticks = ggplot2::element_blank()))
  }

  if (recipe_id == "heat-tree") {
    return(ggplot2::ggplot(layout, ggplot2::aes(x = x, y = y)) +
      ggplot2::geom_segment(
        data = edges[!is.na(edges$parent_x), ],
        ggplot2::aes(x = parent_x, y = parent_y, xend = x, yend = y, color = value),
        inherit.aes = FALSE, linewidth = 0.7, alpha = 0.75
      ) +
      ggplot2::geom_point(ggplot2::aes(size = value, fill = value), shape = 21, color = "#222222") +
      ggplot2::geom_text(ggplot2::aes(label = label), hjust = 0, nudge_x = 0.08,
                         size = 2.0, check_overlap = TRUE) +
      ggplot2::scale_color_viridis_c(option = "C") + ggplot2::scale_fill_viridis_c(option = "C") +
      ggplot2::scale_size_area(max_size = 7, guide = "none") +
      ggplot2::guides(color = "none") +
      ggplot2::coord_cartesian(xlim = c(-0.1, max(layout$x) + 0.8), clip = "off") +
      ggplot2::labs(x = "Hierarchy level", y = NULL, color = "Value", fill = "Value"))
  }

  tree_plot <- apply_discrete_scales(
    ggplot2::ggplot(layout, ggplot2::aes(x = x, y = y)) +
      ggplot2::geom_segment(data = edges[!is.na(edges$parent_x), ],
                            ggplot2::aes(x = parent_x, y = parent_y, xend = x, yend = y),
                            inherit.aes = FALSE, color = "#888888", linewidth = 0.4) +
      ggplot2::geom_point(ggplot2::aes(size = value, fill = group), shape = 21, color = "#222222") +
      ggplot2::geom_text(ggplot2::aes(label = label), size = 2.0, nudge_y = 0.055, check_overlap = TRUE) +
      ggplot2::scale_size_area(max_size = 5, guide = "none")
  ) + ggplot2::labs(x = "Hierarchy level", y = NULL, fill = "Group")
  if (recipe_id == "fan-tree") {
    tree_plot <- tree_plot + ggplot2::coord_polar(theta = "y", clip = "off") +
      ggplot2::labs(x = NULL, y = NULL) +
      ggplot2::theme(axis.text = ggplot2::element_blank(), axis.ticks = ggplot2::element_blank())
  } else {
    tree_plot <- tree_plot +
      ggplot2::scale_x_continuous(expand = ggplot2::expansion(mult = c(0.03, 0.32))) +
      ggplot2::coord_cartesian(clip = "off")
  }
  tree_plot
}

render_set_membership <- function(dat, recipe_id) {
  if (recipe_id %in% c("venn-diagram", "euler-diagram", "variation-partition")) {
    sets <- unique(dat$set_id)[1:min(3, length(unique(dat$set_id)))]
    centers <- data.frame(set_id = sets, x = c(-0.32, 0.32, 0)[seq_along(sets)],
                          y = c(0, 0, 0.38)[seq_along(sets)])
    theta <- seq(0, 2 * pi, length.out = 181)
    circles <- do.call(rbind, lapply(seq_len(nrow(centers)), function(i) data.frame(
      set_id = centers$set_id[i], x = centers$x[i] + 0.62 * cos(theta), y = centers$y[i] + 0.62 * sin(theta)
    )))
    counts <- stats::aggregate(present ~ set_id, dat[dat$set_id %in% sets, ], sum)
    labels <- merge(centers, counts, by = "set_id")
    return(apply_discrete_scales(
      ggplot2::ggplot(circles, ggplot2::aes(x = x, y = y, group = set_id, fill = set_id, color = set_id)) +
        ggplot2::geom_polygon(alpha = 0.12, linewidth = 0.55) +
        ggplot2::geom_text(data = labels, ggplot2::aes(x = x, y = y, label = paste0(set_id, "\nn=", present)),
                           inherit.aes = FALSE, size = 2.2) + ggplot2::coord_equal() + ggplot2::theme_void()
    ) + ggplot2::guides(fill = "none", color = "none") +
      ggplot2::labs(caption = "Circle areas are schematic; counts come from the membership table."))
  }
  dat$present_factor <- factor(dat$present, levels = c(0, 1))
  ggplot2::ggplot(dat, ggplot2::aes(x = set_id, y = item_id)) +
    ggplot2::geom_tile(fill = "#F2F2F2", color = "white") +
    ggplot2::geom_point(data = dat[dat$present == 1, , drop = FALSE], size = 2, color = "#0072B2") +
    ggplot2::labs(x = "Set", y = "Item")
}

render_network <- function(dat, recipe_id) {
  if (!"weight" %in% names(dat)) dat$weight <- 1
  if (!"from_group" %in% names(dat)) dat$from_group <- "Source"
  if (!"to_group" %in% names(dat)) dat$to_group <- "Target"
  dat$weight[!is.finite(dat$weight)] <- 1
  nodes <- sort(unique(c(dat$from, dat$to)))
  if (recipe_id == "adjacency-matrix") {
    dat$presence <- 1
    return(ggplot2::ggplot(dat, ggplot2::aes(x = to, y = from, fill = weight)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.3) +
      ggplot2::scale_fill_gradient2(low = "#2166AC", mid = "white", high = "#B2182B", midpoint = 0) +
      ggplot2::labs(x = "To", y = "From", fill = "Weight") +
      ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1)))
  }
  if (recipe_id == "arc-diagram") {
    node_data <- data.frame(node = nodes, x = seq_along(nodes), y = 0)
    edges <- merge(dat, node_data, by.x = "from", by.y = "node")
    names(edges)[names(edges) == "x"] <- "x_from"
    edges <- merge(edges, node_data, by.x = "to", by.y = "node")
    names(edges)[names(edges) == "x"] <- "x_to"
    return(ggplot2::ggplot() +
      ggplot2::geom_curve(data = edges, ggplot2::aes(x = x_from, y = 0, xend = x_to, yend = 0,
                                                     linewidth = abs(weight), linetype = weight < 0),
                          curvature = 0.35, color = "#888888", alpha = 0.7) +
      ggplot2::geom_point(data = node_data, ggplot2::aes(x = x, y = y), size = 2.4, color = "#0072B2") +
      ggplot2::geom_text(data = node_data, ggplot2::aes(x = x, y = y, label = node), angle = 45,
                         hjust = 1, nudge_y = -0.12, size = 2.0, check_overlap = TRUE) +
      ggplot2::scale_linewidth(range = c(0.3, 1.2), guide = "none") +
      ggplot2::scale_linetype_manual(values = c(`FALSE` = 1, `TRUE` = 2), guide = "none") +
      ggplot2::theme_void() + ggplot2::coord_cartesian(ylim = c(-0.42, 1.15), clip = "off"))
  }

  join_network_layout <- function(layout) {
    edges <- merge(dat, layout, by.x = "from", by.y = "node", all.x = TRUE)
    names(edges)[names(edges) %in% c("x", "y")] <- c("x_from", "y_from")
    edges <- merge(edges, layout, by.x = "to", by.y = "node", all.x = TRUE)
    names(edges)[names(edges) %in% c("x", "y")] <- c("x_to", "y_to")
    edges$sign <- ifelse(edges$weight >= 0, "Positive", "Negative")
    edges
  }

  if (recipe_id == "bipartite-network") {
    left <- unique(dat$from)
    right <- unique(dat$to)
    left_data <- data.frame(node = left, x = 0, y = seq(0.10, 0.90, length.out = length(left)),
                            node_type = "Source")
    right_data <- data.frame(node = right, x = 1, y = seq(0.10, 0.90, length.out = length(right)),
                             node_type = "Target")
    node_data <- rbind(left_data, right_data)
    edges <- merge(dat, left_data[c("node", "x", "y")], by.x = "from", by.y = "node", all.x = TRUE)
    names(edges)[names(edges) %in% c("x", "y")] <- c("x_from", "y_from")
    edges <- merge(edges, right_data[c("node", "x", "y")], by.x = "to", by.y = "node", all.x = TRUE)
    names(edges)[names(edges) %in% c("x", "y")] <- c("x_to", "y_to")
    edges$sign <- ifelse(edges$weight >= 0, "Positive", "Negative")
    return(ggplot2::ggplot() +
      ggplot2::geom_curve(
        data = edges,
        ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to,
                     linewidth = abs(weight), color = sign),
        curvature = 0.08, alpha = 0.62, lineend = "round"
      ) +
      ggplot2::geom_point(data = node_data, ggplot2::aes(x = x, y = y, fill = node_type),
                          shape = 21, size = 3.2, color = "#222222") +
      ggplot2::geom_text(data = left_data, ggplot2::aes(x = x, y = y, label = node),
                         hjust = 1, nudge_x = -0.04, size = 2.0, check_overlap = TRUE) +
      ggplot2::geom_text(data = right_data, ggplot2::aes(x = x, y = y, label = node),
                         hjust = 0, nudge_x = 0.04, size = 2.0, check_overlap = TRUE) +
      ggplot2::scale_linewidth(range = c(0.35, 1.5), guide = "none") +
      ggplot2::scale_color_manual(values = c(Positive = "#0072B2", Negative = "#D55E00")) +
      ggplot2::scale_fill_manual(values = c(Source = "#56B4E9", Target = "#E69F00")) +
      ggplot2::coord_cartesian(xlim = c(-0.40, 1.40), ylim = c(0, 1), clip = "off") +
      ggplot2::theme_void() + ggplot2::labs(color = "Association", fill = "Node role"))
  }

  schematic_recipes <- c(
    "sem-path", "causal-dag", "workflow-diagram", "experimental-design-diagram",
    "conceptual-model", "consort-flow"
  )
  if (recipe_id %in% schematic_recipes) {
    group_order <- unique(c(dat$from_group, dat$to_group))
    node_group <- rbind(
      data.frame(node = dat$from, group = dat$from_group),
      data.frame(node = dat$to, group = dat$to_group)
    )
    node_group <- node_group[!duplicated(node_group$node), , drop = FALSE]
    node_group$stage <- match(node_group$group, group_order)
    node_group$x <- if (length(group_order) > 1) {
      (node_group$stage - 1) / (length(group_order) - 1)
    } else 0.5
    node_group$y <- ave(
      seq_len(nrow(node_group)), node_group$stage,
      FUN = function(index) seq(0.15, 0.85, length.out = length(index))
    )
    edges <- join_network_layout(node_group[c("node", "x", "y")])
    return(ggplot2::ggplot() +
      ggplot2::geom_curve(
        data = edges,
        ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to,
                     linewidth = abs(weight), linetype = sign),
        curvature = 0.08, color = "#667085", alpha = 0.82,
        arrow = grid::arrow(length = grid::unit(1.4, "mm"), type = "closed")
      ) +
      ggplot2::geom_label(
        data = node_group,
        ggplot2::aes(x = x, y = y, label = node, fill = group),
        label.size = 0.25, label.padding = grid::unit(1.8, "mm"),
        size = 2.05, color = "#17202A", show.legend = FALSE
      ) +
      ggplot2::geom_text(
        data = unique(node_group[c("group", "x")]),
        ggplot2::aes(x = x, y = 1.02, label = group),
        fontface = "bold", size = 2.2, inherit.aes = FALSE
      ) +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::scale_linewidth(range = c(0.35, 1.25), guide = "none") +
      ggplot2::scale_linetype_manual(values = c(Positive = 1, Negative = 2), guide = "none") +
      ggplot2::coord_cartesian(xlim = c(-0.15, 1.15), ylim = c(0.04, 1.08), clip = "off") +
      ggplot2::theme_void())
  }

  if (recipe_id == "chord-diagram") {
    angle <- seq(0, 2 * pi, length.out = length(nodes) + 1)[-1]
    node_data <- data.frame(node = nodes, x = cos(angle), y = sin(angle), angle = angle)
    edges <- join_network_layout(node_data[c("node", "x", "y")])
    node_data$label_x <- 1.15 * node_data$x
    node_data$label_y <- 1.15 * node_data$y
    return(ggplot2::ggplot() +
      ggplot2::geom_curve(
        data = edges,
        ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to,
                     linewidth = abs(weight), color = sign),
        curvature = -0.18, alpha = 0.58, lineend = "round"
      ) +
      ggplot2::geom_point(data = node_data, ggplot2::aes(x = x, y = y),
                          size = 3.5, shape = 21, fill = "white", color = "#2B2B2B") +
      ggplot2::geom_text(data = node_data,
                         ggplot2::aes(x = label_x, y = label_y, label = node),
                         size = 2.0, check_overlap = TRUE) +
      ggplot2::scale_linewidth(range = c(0.45, 2.1), guide = "none") +
      ggplot2::scale_color_manual(values = c(Positive = "#0072B2", Negative = "#D55E00")) +
      ggplot2::coord_equal(xlim = c(-1.35, 1.35), ylim = c(-1.35, 1.35), clip = "off") +
      ggplot2::theme_void() + ggplot2::labs(color = "Association"))
  }

  if (recipe_id == "hive-plot") {
    node_group <- rbind(
      data.frame(node = dat$from, group = dat$from_group),
      data.frame(node = dat$to, group = dat$to_group)
    )
    node_group <- node_group[!duplicated(node_group$node), , drop = FALSE]
    groups <- unique(node_group$group)
    group_angle <- setNames(seq(0, 2 * pi, length.out = length(groups) + 1)[-1], groups)
    node_group$radius <- ave(seq_len(nrow(node_group)), node_group$group,
                             FUN = function(index) seq(0.35, 1, length.out = length(index)))
    node_group$angle <- group_angle[node_group$group]
    node_group$x <- node_group$radius * cos(node_group$angle)
    node_group$y <- node_group$radius * sin(node_group$angle)
    edges <- join_network_layout(node_group[c("node", "x", "y")])
    axes <- data.frame(group = groups, x = cos(group_angle), y = sin(group_angle))
    return(ggplot2::ggplot() +
      ggplot2::geom_segment(data = axes, ggplot2::aes(x = 0, y = 0, xend = x, yend = y),
                            color = "#B0B0B0", linewidth = 0.45) +
      ggplot2::geom_curve(data = edges,
                          ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to,
                                       linewidth = abs(weight), color = sign),
                          curvature = 0.18, alpha = 0.56) +
      ggplot2::geom_point(data = node_group, ggplot2::aes(x = x, y = y, fill = group),
                          shape = 21, size = 2.8, color = "#222222") +
      ggplot2::geom_text(data = node_group, ggplot2::aes(x = 1.09 * x, y = 1.09 * y, label = node),
                         size = 1.9, check_overlap = TRUE) +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::scale_color_manual(values = c(Positive = "#0072B2", Negative = "#D55E00")) +
      ggplot2::scale_linewidth(range = c(0.35, 1.25), guide = "none") +
      ggplot2::coord_equal(xlim = c(-1.25, 1.25), ylim = c(-1.25, 1.25), clip = "off") +
      ggplot2::theme_void() +
      ggplot2::guides(
        color = ggplot2::guide_legend(order = 1, nrow = 1),
        fill = ggplot2::guide_legend(order = 2, nrow = 1)
      ) +
      ggplot2::labs(color = "Association", fill = "Axis"))
  }
  angle <- seq(0, 2 * pi, length.out = length(nodes) + 1)[-1]
  node_data <- data.frame(node = nodes, x = cos(angle), y = sin(angle))
  edges <- merge(dat, node_data, by.x = "from", by.y = "node", all.x = TRUE)
  names(edges)[names(edges) %in% c("x", "y")] <- c("x_from", "y_from")
  edges <- merge(edges, node_data, by.x = "to", by.y = "node", all.x = TRUE)
  names(edges)[names(edges) %in% c("x", "y")] <- c("x_to", "y_to")
  if (!"weight" %in% names(edges)) edges$weight <- 1
  edges$sign <- ifelse(edges$weight >= 0, "Positive", "Negative")
  ggplot2::ggplot() +
    ggplot2::geom_segment(data = edges,
                          ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to,
                                       linewidth = abs(weight), linetype = sign),
                          color = "#777777", alpha = 0.7,
                          arrow = grid::arrow(length = grid::unit(1.3, "mm"))) +
    ggplot2::geom_point(data = node_data, ggplot2::aes(x = x, y = y),
                        size = 3.2, shape = 21, fill = "#56B4E9", color = "#222222") +
    ggplot2::geom_text(data = node_data, ggplot2::aes(x = x, y = y, label = node),
                       size = 2.1, nudge_y = 0.10, check_overlap = TRUE) +
    ggplot2::scale_linewidth(range = c(0.3, 1.2), guide = "none") +
    ggplot2::scale_linetype_manual(values = c(Positive = 1, Negative = 2)) +
    ggplot2::coord_equal(clip = "off") + ggplot2::theme_void(base_size = 8) +
    ggplot2::labs(linetype = "Association")
}

render_spatial <- function(dat, renderer, recipe_id) {
  if (renderer == "spatial-profile") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = value)) +
      ggplot2::geom_tile() + ggplot2::scale_y_reverse() +
      ggplot2::scale_fill_viridis_c(option = "C") +
      ggplot2::labs(x = "Distance", y = "Depth", fill = "Value"))
  }
  if (renderer == "spatial-composition" && "component" %in% names(dat)) {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = value)) +
      ggplot2::geom_tile() + ggplot2::facet_wrap(~component) +
      ggplot2::scale_fill_viridis_c(option = "C") + ggplot2::coord_equal() +
      ggplot2::labs(x = "X", y = "Y", fill = "Value"))
  }
  if (renderer == "spatial-temporal" && "time" %in% names(dat)) {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = value)) +
      ggplot2::geom_tile() + ggplot2::facet_wrap(~time) +
      ggplot2::scale_fill_viridis_c(option = "C") + ggplot2::coord_equal() +
      ggplot2::labs(x = "X", y = "Y", fill = "Value"))
  }
  if (recipe_id == "sample-location-map") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = class)) +
      ggplot2::geom_point(size = 2.0) + ggplot2::coord_equal() +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::labs(x = "Easting", y = "Northing", color = "Class"))
  }
  if (recipe_id %in% c("proportional-symbol-map", "dot-density-map", "cartogram", "hex-tile-map")) {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, size = value, color = class)) +
      ggplot2::geom_point(shape = if (recipe_id == "hex-tile-map") 23 else 21,
                          fill = "white", alpha = 0.78) +
      ggplot2::scale_size_area(max_size = 6) + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::coord_equal() + ggplot2::labs(x = "Easting", y = "Northing", size = "Value", color = "Class"))
  }
  if (recipe_id == "categorical-raster-map") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = class)) +
      ggplot2::geom_tile() + ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::coord_equal() +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Class"))
  }
  if (recipe_id %in% c("contour-map", "filled-contour-map")) {
    p <- ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, z = value))
    if (recipe_id == "filled-contour-map") {
      p <- p + ggplot2::stat_contour_filled(bins = 7) + ggplot2::scale_fill_viridis_d(option = "C")
    } else {
      p <- p + ggplot2::geom_contour(ggplot2::aes(color = ggplot2::after_stat(level)), bins = 7, linewidth = 0.55) +
        ggplot2::scale_color_viridis_c(option = "C")
    }
    return(p + ggplot2::coord_equal() + ggplot2::labs(x = "Easting", y = "Northing", fill = "Value", color = "Value"))
  }
  if (recipe_id %in% c("vector-field-map", "flow-map")) {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y)) +
      ggplot2::geom_segment(ggplot2::aes(xend = x + u, yend = y + v, color = sqrt(u^2 + v^2)),
                            arrow = grid::arrow(length = grid::unit(1.4, "mm")), linewidth = 0.5) +
      ggplot2::scale_color_viridis_c(option = "C") + ggplot2::coord_equal() +
      ggplot2::labs(x = "Easting", y = "Northing", color = "Magnitude"))
  }
  if (recipe_id == "bivariate-map") {
    value_class <- cut(dat$value, breaks = stats::quantile(dat$value, c(0, 1/3, 2/3, 1)), include.lowest = TRUE, labels = FALSE)
    uncertainty_class <- cut(dat$uncertainty, breaks = stats::quantile(dat$uncertainty, c(0, 1/3, 2/3, 1)),
                             include.lowest = TRUE, labels = FALSE)
    dat$bivariate_class <- factor(paste(value_class, uncertainty_class, sep = "-"))
    colors <- c("#E8E8E8", "#ACE4E4", "#5AC8C8", "#DFB0D6", "#A5ADD3", "#5698B9", "#BE64AC", "#8C62AA", "#3B4994")
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = bivariate_class)) +
      ggplot2::geom_tile() + ggplot2::scale_fill_manual(values = colors) + ggplot2::coord_equal() +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Value–uncertainty class"))
  }
  if (recipe_id == "geofacet-map" && "time" %in% names(dat)) {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = value)) +
      ggplot2::geom_tile() + ggplot2::facet_wrap(~time) + ggplot2::scale_fill_viridis_c(option = "C") +
      ggplot2::coord_equal() + ggplot2::labs(x = "Easting", y = "Northing", fill = "Value"))
  }
  if (recipe_id == "response-surface") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = value)) +
      ggplot2::geom_tile() +
      ggplot2::geom_contour(data = dat, ggplot2::aes(x = x, y = y, z = value), inherit.aes = FALSE,
                            color = "white", linewidth = 0.35, bins = 6) +
      ggplot2::scale_fill_viridis_c(option = "C") + ggplot2::coord_equal() +
      ggplot2::labs(x = "Predictor 1", y = "Predictor 2", fill = "Response"))
  }
  p <- ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = value)) +
    ggplot2::geom_tile() + ggplot2::scale_fill_viridis_c(option = "C") +
    ggplot2::coord_equal() + ggplot2::labs(x = "X", y = "Y", fill = "Value")
  if (renderer == "spatial-prediction" && "uncertainty" %in% names(dat)) {
    p <- p + ggplot2::geom_contour(
      data = dat, ggplot2::aes(x = x, y = y, z = uncertainty), inherit.aes = FALSE,
      color = "white", linewidth = 0.35, bins = 4, alpha = 0.9
    )
  }
  p
}

render_variogram <- function(dat, recipe_id) {
  if (!"direction" %in% names(dat)) dat$direction <- "Omnidirectional"
  if (!"pairs" %in% names(dat)) dat$pairs <- 1
  p <- ggplot2::ggplot(dat, ggplot2::aes(x = lag, y = semivariance, color = factor(direction))) +
    ggplot2::geom_point(ggplot2::aes(size = pairs), alpha = 0.78)
  if (recipe_id == "fitted-variogram" && "model_semivariance" %in% names(dat)) {
    p <- p + ggplot2::geom_line(ggplot2::aes(y = model_semivariance, group = direction), linewidth = 0.65)
  } else if (recipe_id == "variogram-cloud") {
    p <- p + ggplot2::geom_jitter(width = 1.4, height = 0, alpha = 0.45)
  } else {
    p <- p + ggplot2::geom_line(ggplot2::aes(group = direction), linewidth = 0.5)
  }
  apply_discrete_scales(p) + ggplot2::scale_size_area(max_size = 4) +
    ggplot2::labs(x = "Lag distance", y = "Semivariance", color = "Direction", size = "Pairs")
}

render_ecology <- function(dat, recipe_id) {
  if (!"group" %in% names(dat)) dat$group <- "All"
  if (!"effort" %in% names(dat)) dat$effort <- as.numeric(factor(dat$sample_id))
  if (recipe_id == "rank-abundance") {
    sums <- stats::aggregate(abundance ~ group + species, dat, sum)
    sums <- sums[sums$abundance > 0, , drop = FALSE]
    sums <- do.call(rbind, lapply(split(sums, sums$group), function(part) {
      part <- part[order(part$abundance, decreasing = TRUE), , drop = FALSE]
      part$rank <- seq_len(nrow(part))
      part$relative <- part$abundance / sum(part$abundance)
      part
    }))
    return(apply_discrete_scales(
      ggplot2::ggplot(sums, ggplot2::aes(x = rank, y = relative, color = group)) +
        ggplot2::geom_line(linewidth = 0.6) + ggplot2::geom_point(size = 1.4) + ggplot2::scale_y_log10()
    ) + ggplot2::labs(x = "Species rank", y = "Relative abundance (log scale)", color = "Group"))
  }
  if (recipe_id == "species-abundance-distribution") {
    sums <- stats::aggregate(abundance ~ species, dat, sum)
    return(ggplot2::ggplot(sums, ggplot2::aes(x = abundance)) +
      ggplot2::geom_histogram(bins = 7, fill = "#56B4E9", color = "white") +
      ggplot2::scale_x_log10() + ggplot2::labs(x = "Species abundance (log scale)", y = "Species count"))
  }
  if (recipe_id %in% c("species-accumulation", "rarefaction-curve", "coverage-rarefaction")) {
    sample_order <- unique(dat[c("sample_id", "effort", "group")])
    curve <- do.call(rbind, lapply(split(sample_order, sample_order$group), function(group_samples) {
      group_samples <- group_samples[order(group_samples$effort), , drop = FALSE]
      observed <- character()
      do.call(rbind, lapply(seq_len(nrow(group_samples)), function(i) {
        current <- dat[
          dat$sample_id == group_samples$sample_id[i] & dat$abundance > 0,
          "species"
        ]
        observed <<- union(observed, current)
        data.frame(
          effort = group_samples$effort[i], richness = length(observed),
          group = group_samples$group[i]
        )
      }))
    }))
    return(apply_discrete_scales(
      ggplot2::ggplot(curve, ggplot2::aes(x = effort, y = richness, color = group)) +
        ggplot2::geom_step(linewidth = 0.65) + ggplot2::geom_point(size = 1.4)
    ) + ggplot2::labs(x = "Sampling effort", y = "Accumulated richness", color = "Group",
                      caption = "Deterministic accumulation from the supplied sample order; random permutations are not invented."))
  }
  diversity <- do.call(rbind, lapply(split(dat, dat$sample_id), function(part) {
    proportions <- part$abundance / sum(part$abundance)
    data.frame(sample_id = part$sample_id[1], group = part$group[1],
               shannon = -sum(proportions[proportions > 0] * log(proportions[proportions > 0])))
  }))
  apply_discrete_scales(
    ggplot2::ggplot(diversity, ggplot2::aes(x = group, y = shannon, color = group)) +
      ggplot2::geom_point(size = 1.8, position = ggplot2::position_jitter(width = 0.06))
  ) + ggplot2::guides(color = "none") + ggplot2::labs(x = NULL, y = "Shannon diversity")
}

render_genomic <- function(dat, recipe_id) {
  dat$chromosome <- factor(dat$chromosome, levels = unique(dat$chromosome))
  dat$chrom_index <- as.numeric(dat$chromosome)
  if (recipe_id == "regional-association") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = start, y = -log10(p_value), color = type)) +
      ggplot2::geom_point(size = 1.8) + ggplot2::facet_wrap(~chromosome, scales = "free_x") +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Genomic position", y = expression(-log[10](P)), color = "Feature type"))
  }
  if (recipe_id == "karyogram") {
    lengths <- stats::aggregate(end ~ chromosome, dat, max)
    lengths$y <- seq_len(nrow(lengths))
    return(ggplot2::ggplot(lengths, ggplot2::aes(y = y)) +
      ggplot2::geom_segment(ggplot2::aes(x = 0, xend = end, yend = y), linewidth = 3, color = "#D9D9D9") +
      ggplot2::geom_point(data = dat, ggplot2::aes(x = start, y = chrom_index, color = value > 0), size = 1.8) +
      ggplot2::scale_y_continuous(breaks = lengths$y, labels = lengths$chromosome) +
      ggplot2::scale_color_manual(values = c(`FALSE` = "#0072B2", `TRUE` = "#D55E00"), guide = "none") +
      ggplot2::labs(x = "Genomic position", y = "Chromosome"))
  }
  if (recipe_id == "circos-plot") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = start, y = abs(value), color = chromosome, size = abs(value))) +
      ggplot2::geom_point(alpha = 0.82) + ggplot2::coord_polar() +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_size_area(max_size = 4) +
      ggplot2::labs(x = "Position", y = "Magnitude", color = "Chromosome", size = "Magnitude"))
  }
  if (recipe_id == "sashimi-plot") {
    junctions <- dat[dat$type == "junction", , drop = FALSE]
    return(ggplot2::ggplot(dat, ggplot2::aes(x = start, y = chrom_index)) +
      ggplot2::geom_segment(ggplot2::aes(xend = end, yend = chrom_index, color = type), linewidth = 2.5, alpha = 0.65) +
      ggplot2::geom_curve(data = junctions, ggplot2::aes(x = start, xend = end, y = chrom_index, yend = chrom_index),
                          curvature = -0.45, linewidth = 0.6, inherit.aes = FALSE) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::scale_y_continuous(breaks = seq_along(levels(dat$chromosome)), labels = levels(dat$chromosome)) +
      ggplot2::labs(x = "Genomic position", y = "Chromosome", color = "Feature type"))
  }
  if (recipe_id == "mutation-lollipop") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = start, y = abs(value), color = type)) +
      ggplot2::geom_segment(ggplot2::aes(xend = start, y = 0, yend = abs(value)), linewidth = 0.45) +
      ggplot2::geom_point(size = 2.0) + ggplot2::facet_wrap(~chromosome, scales = "free_x") +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::labs(x = "Position", y = "Effect magnitude", color = "Type"))
  }
  ggplot2::ggplot(dat, ggplot2::aes(x = start, xend = end, y = value, yend = value, color = group)) +
    ggplot2::geom_segment(linewidth = 2.2, alpha = 0.75) + ggplot2::facet_wrap(~chromosome, scales = "free_x") +
    ggplot2::scale_color_manual(values = palette_discrete) +
    ggplot2::scale_x_continuous(
      breaks = scales::breaks_pretty(n = 3),
      labels = scales::label_number(scale_cut = scales::cut_short_scale())
    ) +
    ggplot2::labs(x = "Genomic position", y = "Track value", color = "Group")
}

render_sequence_logo <- function(dat) {
  dat$symbol <- factor(dat$symbol, levels = c("A", "C", "G", "T"))
  ggplot2::ggplot(dat, ggplot2::aes(x = factor(position), y = frequency, fill = symbol)) +
    ggplot2::geom_col(width = 0.82, color = "white", linewidth = 0.25) +
    ggplot2::geom_text(ggplot2::aes(label = symbol), position = ggplot2::position_stack(vjust = 0.5), size = 2.3) +
    ggplot2::scale_fill_manual(values = c(A = "#009E73", C = "#0072B2", G = "#E69F00", T = "#D55E00")) +
    ggplot2::labs(x = "Sequence position", y = "Symbol frequency", fill = "Symbol")
}

classification_curves <- function(dat) {
  thresholds <- sort(unique(c(Inf, dat$score, -Inf)), decreasing = TRUE)
  do.call(rbind, lapply(thresholds, function(threshold) {
    predicted <- dat$score >= threshold
    tp <- sum(predicted & dat$truth == 1)
    fp <- sum(predicted & dat$truth == 0)
    fn <- sum(!predicted & dat$truth == 1)
    tn <- sum(!predicted & dat$truth == 0)
    data.frame(threshold = threshold,
               sensitivity = if (tp + fn) tp / (tp + fn) else NA,
               specificity = if (tn + fp) tn / (tn + fp) else NA,
               precision = if (tp + fp) tp / (tp + fp) else 1,
               recall = if (tp + fn) tp / (tp + fn) else NA,
               selected = tp + fp, tp = tp, fp = fp)
  }))
}

render_classification <- function(dat, recipe_id) {
  curve <- classification_curves(dat)
  if (recipe_id == "roc-curve") {
    return(ggplot2::ggplot(curve, ggplot2::aes(x = 1 - specificity, y = sensitivity)) +
      ggplot2::geom_abline(slope = 1, intercept = 0, linetype = 2, color = "#777777") +
      ggplot2::geom_step(color = "#0072B2", linewidth = 0.7) + ggplot2::coord_equal() +
      ggplot2::labs(x = "1 - specificity", y = "Sensitivity"))
  }
  if (recipe_id == "precision-recall") {
    return(ggplot2::ggplot(curve, ggplot2::aes(x = recall, y = precision)) +
      ggplot2::geom_step(color = "#D55E00", linewidth = 0.7) + ggplot2::coord_equal() +
      ggplot2::labs(x = "Recall", y = "Precision"))
  }
  if (recipe_id == "calibration-plot") {
    dat$bin <- cut(dat$score, breaks = seq(0, 1, length.out = 5), include.lowest = TRUE)
    calibration <- stats::aggregate(cbind(score, truth) ~ bin, dat, mean)
    return(ggplot2::ggplot(calibration, ggplot2::aes(x = score, y = truth)) +
      ggplot2::geom_abline(slope = 1, intercept = 0, linetype = 2) +
      ggplot2::geom_line(color = "#0072B2", linewidth = 0.65) + ggplot2::geom_point(size = 1.8, color = "#0072B2") +
      ggplot2::coord_equal(xlim = c(0, 1), ylim = c(0, 1)) + ggplot2::labs(x = "Mean predicted probability", y = "Observed event fraction"))
  }
  if (recipe_id == "decision-curve") {
    prevalence <- mean(dat$truth)
    valid <- curve[is.finite(curve$threshold) & curve$threshold > 0 & curve$threshold < 1, ]
    valid$net_benefit <- valid$tp / nrow(dat) - valid$fp / nrow(dat) * valid$threshold / (1 - valid$threshold)
    return(ggplot2::ggplot(valid, ggplot2::aes(x = threshold, y = net_benefit)) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.3) + ggplot2::geom_line(color = "#0072B2", linewidth = 0.7) +
      ggplot2::labs(x = "Decision threshold", y = "Net benefit", caption = paste("Observed prevalence:", round(prevalence, 3))))
  }
  ordered <- dat[order(dat$score, decreasing = TRUE), , drop = FALSE]
  ordered$population_fraction <- seq_len(nrow(ordered)) / nrow(ordered)
  ordered$gain <- cumsum(ordered$truth) / sum(ordered$truth)
  ggplot2::ggplot(ordered, ggplot2::aes(x = population_fraction, y = gain)) +
    ggplot2::geom_abline(slope = 1, intercept = 0, linetype = 2) +
    ggplot2::geom_step(color = "#0072B2", linewidth = 0.7) +
    ggplot2::labs(x = "Population fraction ranked by score", y = "Cumulative event capture")
}

render_hydrology <- function(dat, recipe_id) {
  dat <- dat[order(dat$time), , drop = FALSE]
  if (recipe_id == "hyetograph") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = time, y = precipitation)) +
      ggplot2::geom_col(fill = "#56B4E9", width = 0.8) +
      ggplot2::scale_y_reverse() + ggplot2::labs(x = "Time", y = "Precipitation (reversed)") )
  }
  if (recipe_id == "hydrograph-hyetograph") {
    ratio <- max(dat$precipitation) / max(dat$discharge)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = time)) +
      ggplot2::geom_col(ggplot2::aes(y = -precipitation / ratio), fill = "#56B4E9", width = 0.8, alpha = 0.6) +
      ggplot2::geom_line(ggplot2::aes(y = discharge), color = "#0072B2", linewidth = 0.7) +
      ggplot2::geom_point(ggplot2::aes(y = discharge), color = "#0072B2", size = 1.2) +
      ggplot2::labs(x = "Time", y = "Discharge; precipitation shown downward",
                    caption = "Precipitation is scaled by an explicit constant for alignment; values remain in the input table."))
  }
  if (recipe_id == "flow-duration-curve") {
    sorted <- sort(dat$discharge, decreasing = TRUE)
    curve <- data.frame(exceedance = stats::ppoints(length(sorted)) * 100, discharge = sorted)
    return(ggplot2::ggplot(curve, ggplot2::aes(x = exceedance, y = discharge)) +
      ggplot2::geom_line(color = "#0072B2", linewidth = 0.7) + ggplot2::scale_y_log10() +
      ggplot2::labs(x = "Exceedance probability (%)", y = "Discharge (log scale)"))
  }
  if (recipe_id == "double-mass-curve") {
    dat$cumulative_discharge <- cumsum(dat$discharge)
    reference <- if ("cumulative_reference" %in% names(dat)) dat$cumulative_reference else cumsum(dat$precipitation)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = reference, y = cumulative_discharge)) +
      ggplot2::geom_line(color = "#0072B2", linewidth = 0.7) + ggplot2::geom_point(size = 1.2, color = "#0072B2") +
      ggplot2::labs(x = "Cumulative reference", y = "Cumulative discharge"))
  }
  ggplot2::ggplot(dat, ggplot2::aes(x = time, y = discharge)) +
    ggplot2::geom_area(fill = "#56B4E9", alpha = 0.25) + ggplot2::geom_line(color = "#0072B2", linewidth = 0.7) +
    ggplot2::labs(x = "Time", y = "Discharge")
}

render_wind <- function(dat, recipe_id) {
  dat$direction <- factor(dat$direction_deg, levels = sort(unique(dat$direction_deg)))
  dat$display_value <- if (recipe_id == "pollution-rose") dat$pollutant else dat$frequency
  ggplot2::ggplot(dat, ggplot2::aes(x = direction, y = display_value, fill = speed)) +
    ggplot2::geom_col(width = 0.92, color = "white", linewidth = 0.25) +
    ggplot2::coord_polar(start = -pi / 8) + ggplot2::scale_fill_viridis_c(option = "C") +
    ggplot2::labs(x = "Direction (degrees)", y = if (recipe_id == "pollution-rose") "Pollutant" else "Frequency",
                  fill = "Speed")
}

render_profile <- function(dat, recipe_id) {
  dat$depth_mid <- if ("depth_cm" %in% names(dat) && any(!is.na(dat$depth_cm))) dat$depth_cm else
    (dat$top_cm + dat$bottom_cm) / 2
  if (grepl("profile-sketch|pedon|horizon", recipe_id)) {
    dat$xmin <- as.numeric(factor(dat$profile_id)) - 0.32
    dat$xmax <- as.numeric(factor(dat$profile_id)) + 0.32
    return(ggplot2::ggplot(dat) +
      ggplot2::geom_rect(ggplot2::aes(xmin = xmin, xmax = xmax, ymin = top_cm, ymax = bottom_cm, fill = horizon),
                         color = "#333333", linewidth = 0.3) +
      ggplot2::scale_y_reverse() +
      ggplot2::scale_x_continuous(breaks = seq_along(unique(dat$profile_id)), labels = unique(dat$profile_id)) +
      ggplot2::scale_fill_brewer(palette = "YlOrBr") +
      ggplot2::labs(x = "Profile", y = "Depth (cm)", fill = "Horizon"))
  }
  if (recipe_id == "depth-property-heatmap") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = profile_id, y = depth_mid, fill = value)) +
      ggplot2::geom_tile(ggplot2::aes(height = pmax(bottom_cm - top_cm, 1)), color = "white", linewidth = 0.3) +
      ggplot2::scale_y_reverse() + ggplot2::scale_fill_viridis_c(option = "C") +
      ggplot2::labs(x = "Profile", y = "Depth (cm)", fill = "Value"))
  }
  apply_discrete_scales(
    ggplot2::ggplot(dat, ggplot2::aes(x = value, y = depth_mid, color = group, group = profile_id)) +
      ggplot2::geom_path(linewidth = 0.6) + ggplot2::geom_point(size = 1.6) +
      ggplot2::scale_y_reverse()
  ) + ggplot2::labs(x = "Property value", y = "Depth (cm)", color = "Group")
}

render_soil_physics <- function(dat) {
  if (!"group" %in% names(dat)) dat$group <- "All"
  dat <- dat[order(dat$group, dat$x), , drop = FALSE]
  apply_discrete_scales(
    ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = group)) +
      ggplot2::geom_point(size = 1.5) +
      ggplot2::geom_line(linewidth = 0.55)
  ) + ggplot2::labs(
    x = "Predictor / pressure / time", y = "Response", color = "Group",
    caption = "Lines connect ordered observations; no physical model is fitted by this template."
  )
}

render_polar <- function(dat, recipe_id) {
  sums <- stats::aggregate(value ~ group, dat, mean)
  sums$group <- factor(sums$group, levels = sums$group)
  ggplot2::ggplot(sums, ggplot2::aes(x = group, y = value, fill = group)) +
    ggplot2::geom_col(width = 0.82, color = "white", linewidth = 0.3) +
    ggplot2::coord_polar() + ggplot2::scale_fill_manual(values = palette_discrete) +
    ggplot2::labs(x = NULL, y = "Value", fill = "Group")
}

render_spectral <- function(dat) {
  if (!"group" %in% names(dat)) dat$group <- dat$sample_id
  apply_discrete_scales(
    ggplot2::ggplot(dat, ggplot2::aes(x = wavelength_nm, y = value, color = group, group = sample_id)) +
      ggplot2::geom_line(linewidth = 0.65) + ggplot2::geom_point(size = 1.2)
  ) + ggplot2::labs(x = "Wavelength (nm)", y = "Spectral value", color = "Group")
}

render_image <- function(dat, recipe_id, volume = FALSE) {
  if (recipe_id != "multichannel-overlay" && "channel" %in% names(dat) && length(unique(dat$channel)) > 1L) {
    grouping <- intersect(c("x", "y", "slice"), names(dat))
    dat <- stats::aggregate(dat$intensity, dat[grouping], mean)
    names(dat)[ncol(dat)] <- "intensity"
  }
  if (recipe_id == "segmentation-overlay") {
    dat$segment <- factor(ifelse(dat$intensity >= stats::median(dat$intensity), "Foreground", "Background"))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = segment, alpha = intensity)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.15) +
      ggplot2::scale_fill_manual(values = c(Background = "#333333", Foreground = "#D55E00")) +
      ggplot2::scale_alpha(range = c(0.35, 0.95)) + ggplot2::coord_equal() +
      ggplot2::labs(x = "X", y = "Y", fill = "Segment", alpha = "Intensity"))
  }
  if (recipe_id == "multichannel-overlay") {
    dat$channel <- factor(dat$channel, levels = c("R", "G", "B"))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = channel, alpha = intensity)) +
      ggplot2::geom_tile() +
      ggplot2::scale_fill_manual(values = c(R = "#D55E00", G = "#009E73", B = "#0072B2")) +
      ggplot2::scale_alpha(range = c(0.1, 0.9)) + ggplot2::coord_equal() +
      ggplot2::guides(alpha = "none") +
      ggplot2::labs(x = "X", y = "Y", fill = "Channel"))
  }
  if (recipe_id == "maximum-intensity-projection" && "slice" %in% names(dat)) {
    dat <- stats::aggregate(intensity ~ x + y, dat, max)
  }
  p <- ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = intensity)) +
    ggplot2::geom_raster() + ggplot2::scale_fill_viridis_c(option = "magma") +
    ggplot2::coord_equal() + ggplot2::labs(x = "X", y = "Y", fill = "Intensity")
  if ((volume || recipe_id == "image-montage") && "slice" %in% names(dat) &&
      recipe_id != "maximum-intensity-projection") p <- p + ggplot2::facet_wrap(~slice)
  p
}

render_omics <- function(dat, recipe_id) {
  dat$neg_log10_p <- -log10(pmax(dat$p_value, .Machine$double.xmin))
  dat$status <- ifelse(dat$p_value < 0.05 & dat$log2_fold_change >= 1, "Up",
                       ifelse(dat$p_value < 0.05 & dat$log2_fold_change <= -1, "Down", "Not selected"))
  if (grepl("manhattan", recipe_id) && all(c("chromosome", "position") %in% names(dat))) {
    dat$chromosome <- factor(dat$chromosome, levels = unique(dat$chromosome))
    dat$x_index <- as.numeric(dat$chromosome) + dat$position / max(dat$position, na.rm = TRUE) * 0.7
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x_index, y = neg_log10_p, color = chromosome)) +
      ggplot2::geom_point(size = 1.6) +
      ggplot2::geom_hline(yintercept = -log10(0.05), linetype = 2, linewidth = 0.4) +
      ggplot2::scale_color_manual(values = rep(c("#0072B2", "#D55E00"), length.out = nlevels(dat$chromosome))) +
      ggplot2::labs(x = "Chromosome and position", y = expression(-log[10](P)), color = "Chromosome"))
  }
  if (recipe_id == "genomic-rainfall" && all(c("chromosome", "position") %in% names(dat))) {
    dat <- dat[order(dat$chromosome, dat$position), , drop = FALSE]
    dat$distance <- ave(dat$position, dat$chromosome, FUN = function(x) c(NA, diff(x)))
    return(ggplot2::ggplot(dat[is.finite(dat$distance) & dat$distance > 0, ],
                           ggplot2::aes(x = position, y = distance, color = factor(chromosome))) +
      ggplot2::geom_point(size = 1.6) + ggplot2::scale_y_log10() +
      ggplot2::facet_wrap(~chromosome, scales = "free_x") +
      ggplot2::scale_x_continuous(
        breaks = function(limits) mean(range(limits)),
        labels = function(value) format(round(value / 1000, 1), trim = TRUE)
      ) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::guides(color = "none") +
      ggplot2::labs(x = "Genomic position (kb)", y = "Inter-feature distance (log scale)"))
  }
  if (recipe_id == "miami-plot" && all(c("chromosome", "position") %in% names(dat))) {
    dat$direction_y <- ifelse(as.numeric(factor(dat$chromosome)) %% 2 == 0, -dat$neg_log10_p, dat$neg_log10_p)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = position, y = direction_y, color = factor(chromosome))) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.3) + ggplot2::geom_point(size = 1.6) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Position", y = expression(paste("Signed ", -log[10](P))), color = "Chromosome"))
  }
  if (recipe_id == "gsea-running-score") {
    dat <- dat[order(dat$log2_fold_change, decreasing = TRUE), , drop = FALSE]
    hit <- dat$p_value < 0.05
    positive_total <- sum(abs(dat$log2_fold_change[hit]))
    increment <- ifelse(hit, abs(dat$log2_fold_change) / max(positive_total, .Machine$double.eps),
                        -1 / max(1, sum(!hit)))
    dat$running_score <- cumsum(increment)
    dat$rank <- seq_len(nrow(dat))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = rank, y = running_score)) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.3) +
      ggplot2::geom_line(color = "#0072B2", linewidth = 0.7) +
      ggplot2::geom_rug(data = dat[hit, ], sides = "b") +
      ggplot2::labs(x = "Ranked feature", y = "Running enrichment score"))
  }
  if (grepl("ma-plot", recipe_id) && "mean_abundance" %in% names(dat)) {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = log10(mean_abundance + 1), y = log2_fold_change, color = status)) +
      ggplot2::geom_hline(yintercept = 0, color = "#555555", linewidth = 0.4) +
      ggplot2::geom_point(size = 1.6, alpha = 0.8) +
      ggplot2::scale_color_manual(values = c(Down = "#0072B2", `Not selected` = "#B3B3B3", Up = "#D55E00")) +
      ggplot2::labs(x = "log10 mean abundance", y = "log2 fold change", color = NULL))
  }
  ggplot2::ggplot(dat, ggplot2::aes(x = log2_fold_change, y = neg_log10_p, color = status)) +
    ggplot2::geom_vline(xintercept = c(-1, 1), linetype = 2, color = "#777777", linewidth = 0.35) +
    ggplot2::geom_hline(yintercept = -log10(0.05), linetype = 2, color = "#777777", linewidth = 0.35) +
    ggplot2::geom_point(size = 1.7, alpha = 0.82) +
    ggplot2::scale_color_manual(values = c(Down = "#0072B2", `Not selected` = "#B3B3B3", Up = "#D55E00")) +
    ggplot2::labs(x = "log2 fold change", y = expression(-log[10](P)), color = NULL)
}

render_diagnostic <- function(dat, recipe_id) {
  if (!"group" %in% names(dat)) dat$group <- "All"
  if (recipe_id == "taylor-diagram") {
    summaries <- do.call(rbind, lapply(split(dat, dat$group), function(part) {
      correlation <- stats::cor(part$observed, part$predicted)
      ratio <- stats::sd(part$predicted) / stats::sd(part$observed)
      data.frame(group = part$group[1], x = ratio * correlation,
                 y = ratio * sqrt(max(0, 1 - correlation^2)), correlation = correlation, ratio = ratio)
    }))
    return(apply_discrete_scales(
      ggplot2::ggplot(summaries, ggplot2::aes(x = x, y = y, color = group)) +
        ggplot2::geom_point(size = 2.3) + ggplot2::annotate("point", x = 1, y = 0, shape = 8, size = 3) +
        ggplot2::coord_equal(xlim = c(0, max(1.25, summaries$x)), ylim = c(0, max(0.5, summaries$y)))
    ) + ggplot2::labs(x = "SD ratio × correlation", y = "Orthogonal SD component", color = "Group"))
  }
  if (recipe_id == "target-diagram") {
    summaries <- do.call(rbind, lapply(split(dat, dat$group), function(part) {
      difference <- part$predicted - part$observed
      data.frame(group = part$group[1], bias = mean(difference), centered_rmsd = stats::sd(difference))
    }))
    return(apply_discrete_scales(
      ggplot2::ggplot(summaries, ggplot2::aes(x = bias, y = centered_rmsd, color = group)) +
        ggplot2::geom_hline(yintercept = 0, linewidth = 0.3) + ggplot2::geom_vline(xintercept = 0, linewidth = 0.3) +
        ggplot2::geom_point(size = 2.3)
    ) + ggplot2::labs(x = "Bias", y = "Centered RMSD", color = "Group"))
  }
  if (grepl("residual", recipe_id) && all(c("fitted", "residual") %in% names(dat))) {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = fitted, y = residual, color = group)) +
        ggplot2::geom_hline(yintercept = 0, linetype = 2, color = "#555555", linewidth = 0.4) +
        ggplot2::geom_point(size = 1.6) +
        ggplot2::geom_smooth(
          data = dat, ggplot2::aes(x = fitted, y = residual), inherit.aes = FALSE,
          method = "loess", formula = y ~ x, se = FALSE, linewidth = 0.5, color = "#333333"
        )
    ) + ggplot2::labs(x = "Fitted", y = "Residual", color = "Group"))
  }
  if (grepl("bland-altman", recipe_id)) {
    dat$mean_pair <- (dat$observed + dat$predicted) / 2
    dat$difference <- dat$observed - dat$predicted
    md <- mean(dat$difference)
    limits <- md + c(-1, 1) * 1.96 * stats::sd(dat$difference)
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = mean_pair, y = difference, color = group)) +
        ggplot2::geom_hline(yintercept = c(md, limits), linetype = c(1, 2, 2), linewidth = 0.4) +
        ggplot2::geom_point(size = 1.6)
    ) + ggplot2::labs(x = "Mean of methods", y = "Observed - predicted", color = "Group"))
  }
  if (recipe_id == "scale-location" && all(c("fitted", "residual") %in% names(dat))) {
    scaled <- dat$residual / stats::sd(dat$residual)
    dat$sqrt_abs_residual <- sqrt(abs(scaled))
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = fitted, y = sqrt_abs_residual, color = group)) +
        ggplot2::geom_point(size = 1.6) +
        ggplot2::geom_smooth(data = dat, ggplot2::aes(x = fitted, y = sqrt_abs_residual), inherit.aes = FALSE,
                             method = "lm", formula = y ~ x, se = FALSE, linewidth = 0.5, color = "#333333")
    ) + ggplot2::labs(x = "Fitted", y = expression(sqrt("|standardized residual|")), color = "Group"))
  }
  if (recipe_id %in% c("leverage-plot", "cooks-distance")) {
    model <- stats::lm(predicted ~ observed, data = dat)
    diagnostic <- data.frame(index = seq_len(nrow(dat)), leverage = stats::hatvalues(model), cooks = stats::cooks.distance(model))
    y_name <- if (recipe_id == "leverage-plot") "leverage" else "cooks"
    diagnostic$value <- diagnostic[[y_name]]
    return(ggplot2::ggplot(diagnostic, ggplot2::aes(x = index, y = value)) +
      ggplot2::geom_segment(ggplot2::aes(xend = index, y = 0, yend = value), color = "#777777") +
      ggplot2::geom_point(color = "#D55E00", size = 1.5) +
      ggplot2::labs(x = "Observation index", y = if (recipe_id == "leverage-plot") "Leverage" else "Cook's distance"))
  }
  limits <- range(c(dat$observed, dat$predicted), na.rm = TRUE)
  apply_discrete_scales(
    ggplot2::ggplot(dat, ggplot2::aes(x = observed, y = predicted, color = group)) +
      ggplot2::geom_abline(intercept = 0, slope = 1, color = "#333333", linetype = 2, linewidth = 0.45) +
      ggplot2::geom_point(size = 1.7) +
      ggplot2::coord_equal(xlim = limits, ylim = limits)
  ) + ggplot2::labs(x = "Observed", y = "Predicted", color = "Group")
}

render_rank_histogram <- function(dat) {
  dat$chain <- factor(dat$chain, levels = unique(dat$chain))
  dat$rank <- rank(dat$value, ties.method = "average", na.last = "keep")
  bins <- max(5L, min(20L, floor(sqrt(nrow(dat)))))
  expected <- nrow(dat) / (nlevels(dat$chain) * bins)
  apply_discrete_scales(
    ggplot2::ggplot(dat, ggplot2::aes(x = rank, fill = chain, color = chain)) +
      ggplot2::geom_histogram(bins = bins, boundary = 0.5, linewidth = 0.25, alpha = 0.65) +
      ggplot2::geom_hline(yintercept = expected, linetype = 2, color = "#555555", linewidth = 0.35) +
      ggplot2::facet_wrap(~chain, ncol = 1) +
      ggplot2::guides(fill = "none", color = "none") +
      ggplot2::labs(x = "Pooled rank", y = "Draw count")
  )
}

render_mcmc_diagnostic <- function(dat, recipe_id) {
  if (recipe_id == "rank-histogram") return(render_rank_histogram(dat))
  dat$iteration_plot <- if ("iteration" %in% names(dat)) dat$iteration else ave(seq_len(nrow(dat)), dat$chain, FUN = seq_along)
  if (recipe_id == "trace-plot") {
    return(apply_discrete_scales(
      ggplot2::ggplot(dat, ggplot2::aes(x = iteration_plot, y = value, color = factor(chain), group = chain)) +
        ggplot2::geom_line(linewidth = 0.5, alpha = 0.8) + ggplot2::facet_wrap(~parameter, scales = "free_y")
    ) + ggplot2::labs(x = "Iteration", y = "Draw value", color = "Chain"))
  }
  apply_discrete_scales(
    ggplot2::ggplot(dat, ggplot2::aes(x = value, color = factor(chain), fill = factor(chain))) +
      ggplot2::geom_density(alpha = 0.18, linewidth = 0.55) + ggplot2::facet_wrap(~parameter, scales = "free")
  ) + ggplot2::labs(x = "Posterior draw", y = "Density", color = "Chain", fill = "Chain",
                    caption = "Posterior draws only; observed-data overlays require an explicit observed column.")
}

render_interpretation <- function(dat, recipe_id) {
  if (!"group" %in% names(dat)) dat$group <- "All"
  if (recipe_id %in% c("pdp-plot", "ice-plot", "ale-plot", "shap-dependence")) {
    dat$display_effect <- if (recipe_id == "ale-plot") ave(dat$effect, dat$feature, FUN = function(x) x - mean(x)) else dat$effect
    p <- ggplot2::ggplot(dat, ggplot2::aes(x = feature_value, y = display_effect, color = group)) +
      ggplot2::geom_hline(yintercept = 0, color = "#777777", linewidth = 0.3) +
      ggplot2::geom_point(size = 1.3, alpha = 0.75) +
      ggplot2::geom_line(ggplot2::aes(group = group), linewidth = 0.5, alpha = 0.72) +
      ggplot2::facet_wrap(~feature, scales = "free_x")
    return(apply_discrete_scales(p) + ggplot2::labs(x = "Feature value", y = "Model effect", color = "Group"))
  }
  if (recipe_id == "variable-importance") {
    values <- stats::aggregate(importance ~ feature, dat, max)
    return(ggplot2::ggplot(values, ggplot2::aes(x = importance, y = reorder(feature, importance))) +
      ggplot2::geom_col(fill = "#0072B2", width = 0.65) + ggplot2::labs(x = "Importance", y = NULL))
  }
  if (recipe_id == "shap-beeswarm") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = effect, y = reorder(feature, importance), color = feature_value)) +
      ggplot2::geom_vline(xintercept = 0, linewidth = 0.3) +
      ggplot2::geom_point(size = 1.5, alpha = 0.78, position = ggplot2::position_jitter(height = 0.08)) +
      ggplot2::scale_color_viridis_c(option = "C") + ggplot2::labs(x = "SHAP effect", y = NULL, color = "Feature value"))
  }
  if (recipe_id == "shap-waterfall") {
    values <- stats::aggregate(effect ~ feature, dat, mean)
    values <- values[order(abs(values$effect), decreasing = TRUE), , drop = FALSE]
    values$end <- cumsum(values$effect)
    values$start <- c(0, head(values$end, -1))
    values$direction <- ifelse(values$effect >= 0, "Increase", "Decrease")
    return(ggplot2::ggplot(values, ggplot2::aes(x = reorder(feature, seq_along(feature)), fill = direction)) +
      ggplot2::geom_rect(ggplot2::aes(xmin = seq_along(feature) - 0.35, xmax = seq_along(feature) + 0.35,
                                      ymin = pmin(start, end), ymax = pmax(start, end)), color = "#333333", linewidth = 0.25) +
      ggplot2::scale_fill_manual(values = c(Increase = "#D55E00", Decrease = "#0072B2")) +
      ggplot2::labs(x = NULL, y = "Cumulative mean SHAP effect", fill = NULL))
  }
  values <- stats::aggregate(cbind(effect, lower, upper) ~ feature, dat, mean)
  ggplot2::ggplot(values, ggplot2::aes(x = effect, y = reorder(feature, effect))) +
    ggplot2::geom_errorbarh(ggplot2::aes(xmin = lower, xmax = upper), height = 0.15, linewidth = 0.5) +
    ggplot2::geom_point(color = "#0072B2", size = 1.8) + ggplot2::geom_vline(xintercept = 0, linetype = 2) +
    ggplot2::labs(x = "Feature score / effect", y = NULL)
}

.figure_engine_path <- tryCatch(
  normalizePath(sys.frame(1)$ofile, winslash = "/", mustWork = TRUE),
  error = function(e) ""
)
.advanced_renderer_path <- if (nzchar(.figure_engine_path)) {
  file.path(dirname(.figure_engine_path), "renderers", "advanced_variants.R")
} else ""
if (nzchar(.advanced_renderer_path) && file.exists(.advanced_renderer_path)) {
  source(.advanced_renderer_path, encoding = "UTF-8")
}

render_figure <- function(dat, config) {
  renderer <- config$renderer
  recipe_id <- config$recipe_id
  p <- if (exists("render_recipe_override", mode = "function")) {
    render_recipe_override(dat, recipe_id, config)
  } else NULL
  if (!is.null(p)) {
    # Recipe-level renderer supplied by a tested module.
  } else if (renderer == "distribution") {
    p <- render_distribution(dat, recipe_id)
  } else if (renderer == "bagplot") {
    p <- render_bagplot(dat)
  } else if (renderer == "genomic-rainfall") {
    p <- render_omics(dat, renderer)
  } else if (renderer == "comparison") {
    p <- render_comparison(dat, recipe_id)
  } else if (renderer == "bullet") {
    p <- render_bullet(dat)
  } else if (renderer == "waterfall") {
    p <- render_waterfall(dat)
  } else if (renderer == "interval") {
    if (!"group" %in% names(dat)) dat$group <- "Estimate"
    p <- render_interval(dat)
  } else if (renderer == "estimation") {
    p <- render_estimation(dat, recipe_id)
  } else if (renderer == "meta-analysis") {
    p <- render_meta_analysis(dat, recipe_id)
  } else if (renderer == "relationship") {
    p <- render_relationship(dat, recipe_id)
  } else if (renderer == "response-surface") {
    p <- render_spatial(dat, "spatial", recipe_id)
  } else if (renderer == "ternary-response") {
    p <- render_ternary(dat)
  } else if (renderer == "multivariate-pairs") {
    p <- render_multivariate_pairs(dat)
  } else if (renderer == "multivariate") {
    p <- render_multivariate(dat, recipe_id)
  } else if (renderer == "hydrochemistry") {
    p <- render_hydrochemistry(dat, recipe_id)
  } else if (renderer == "ordination") {
    p <- render_ordination(dat, recipe_id)
  } else if (renderer == "temporal") {
    p <- render_temporal(dat, recipe_id)
  } else if (renderer == "events") {
    p <- render_events(dat, recipe_id)
  } else if (renderer == "survival") {
    p <- render_survival(dat, recipe_id)
  } else if (renderer == "state-series") {
    p <- render_state_series(dat)
  } else if (renderer == "climate") {
    p <- render_climate(dat)
  } else if (renderer == "temporal-uncertainty") {
    p <- render_temporal_uncertainty(dat)
  } else if (renderer == "hydrology") {
    p <- render_hydrology(dat, recipe_id)
  } else if (renderer == "composition") {
    p <- render_composition(dat, recipe_id)
  } else if (renderer == "ternary") {
    p <- render_ternary(dat)
  } else if (renderer == "matrix") {
    p <- render_matrix(dat, recipe_id)
  } else if (renderer == "mantel-composite") {
    p <- render_mantel_composite(dat)
  } else if (renderer == "flow") {
    p <- render_flow(dat, recipe_id)
  } else if (renderer == "hierarchy") {
    p <- render_hierarchy(dat, recipe_id)
  } else if (renderer == "set-membership") {
    p <- render_set_membership(dat, recipe_id)
  } else if (renderer == "network") {
    p <- render_network(dat, recipe_id)
  } else if (renderer %in% c("spatial", "spatial-prediction", "spatial-profile",
                             "spatial-composition", "spatial-temporal")) {
    p <- render_spatial(dat, renderer, recipe_id)
  } else if (renderer == "variogram") {
    p <- render_variogram(dat, recipe_id)
  } else if (renderer == "profile") {
    p <- render_profile(dat, recipe_id)
  } else if (renderer == "soil-physics") {
    p <- render_soil_physics(dat)
  } else if (renderer == "ecology") {
    p <- render_ecology(dat, recipe_id)
  } else if (renderer == "genomic") {
    p <- render_genomic(dat, recipe_id)
  } else if (renderer == "sequence-logo") {
    p <- render_sequence_logo(dat)
  } else if (renderer == "wind") {
    p <- render_wind(dat, recipe_id)
  } else if (renderer == "spectral") {
    p <- render_spectral(dat)
  } else if (renderer == "image") {
    p <- render_image(dat, recipe_id, volume = FALSE)
  } else if (renderer == "image-volume") {
    p <- render_image(dat, recipe_id, volume = TRUE)
  } else if (renderer == "omics") {
    p <- render_omics(dat, recipe_id)
  } else if (renderer == "diagnostic") {
    p <- render_diagnostic(dat, recipe_id)
  } else if (renderer == "classification") {
    p <- render_classification(dat, recipe_id)
  } else if (renderer == "mcmc-diagnostic") {
    p <- render_mcmc_diagnostic(dat, recipe_id)
  } else if (renderer == "interpretation") {
    p <- render_interpretation(dat, recipe_id)
  } else {
    stop("Renderer not implemented: ", renderer)
  }
  p <- compact_continuous_legend_breaks(p)
  config <- infer_panel_layout(p, dat, config)
  fonts <- configure_figure_fonts(config$raster_dpi %||% 600)
  typography <- resolve_figure_typography(config, dat)
  config$resolved_fonts <- fonts
  p <- adapt_annotation_typography(p, typography, fonts) + theme_publication(typography, fonts = fonts)
  if (isTRUE(config$show_title)) {
    p <- p + ggplot2::labs(title = plot_title(config), subtitle = plot_subtitle(config))
  } else {
    p <- p + ggplot2::labs(title = NULL, subtitle = NULL)
  }
  if (!isTRUE(config$show_caption)) p <- p + ggplot2::labs(caption = NULL)
  borderless_recipes <- c(
    "waffle-chart", "pictogram-chart", "pie-chart", "donut-chart", "treemap", "sunburst",
    "fan-tree", "dendrogram", "phylogram", "unrooted-tree", "tanglegram", "cophylogeny-plot",
    "tree-heatmap", "taxonomic-tree-bar", "venn-diagram", "euler-diagram",
    "variation-partition", "ternary-plot", "ternary-response", "soil-texture-triangle",
    "chord-diagram", "node-link-network", "directed-network", "weighted-network", "bipartite-network",
    "arc-diagram", "hive-plot", "network-small-multiples", "enrichment-map", "cnetplot",
    "sem-path", "causal-dag", "workflow-diagram", "experimental-design-diagram",
    "conceptual-model", "consort-flow"
  )
  if (recipe_id %in% borderless_recipes) p <- p + theme_borderless_scientific()
  if (recipe_id == "mantel-correlogram") {
    p <- p +
      ggplot2::guides(
        fill = ggplot2::guide_colorbar(order = 1, barwidth = grid::unit(18, "mm")),
        color = ggplot2::guide_legend(order = 2, nrow = 1),
        linewidth = ggplot2::guide_legend(order = 3, nrow = 1),
        linetype = "none"
      ) +
      ggplot2::theme(legend.position = "top", legend.box = "vertical")
  }
  if (recipe_id == "tree-heatmap") {
    p <- p + ggplot2::theme(
      legend.position = "bottom", legend.box = "vertical",
      plot.margin = ggplot2::margin(8, 10, 11, 8)
    ) + ggplot2::guides(
      fill = ggplot2::guide_colorbar(order = 1, barwidth = grid::unit(22, "mm")),
      color = ggplot2::guide_legend(order = 2, nrow = 1)
    )
  }
  if (recipe_id == "taxonomic-tree-bar") {
    p <- p + ggplot2::theme(
      legend.position = "bottom", legend.box = "horizontal",
      plot.margin = ggplot2::margin(8, 10, 11, 8)
    )
  }
  if (recipe_id == "taxonomic-tree-bar") p <- p + ggplot2::guides(color = "none")
  if (recipe_id == "hive-plot") {
    p <- p + ggplot2::theme(
      legend.position = "bottom", legend.box = "vertical",
      legend.margin = ggplot2::margin(0, 0, 0, 0),
      legend.box.margin = ggplot2::margin(0, 0, 0, 0)
    )
  }
  bottom_legend_recipes <- c(
    "microbiome-composition", "genome-track", "space-time-cube", "swimmer-plot",
    "pdp-plot", "ternary-response", "contour-enhanced-funnel",
    "association-plot", "dot-heatmap", "enrichment-dotplot", "fourth-corner-heatmap",
    "coverage-rarefaction", "cross-variogram", "directional-variogram",
    "bipartite-network", "directed-network", "weighted-network",
    "parallel-sets", "rda-triplot", "permanova-effect-plot", "multiverse-plot",
    "point-cloud-3d", "prevalence-abundance", "proportional-symbol-map",
    "segmentation-overlay", "soil-color-profile", "soil-gas-flux-series",
    "specification-curve", "spectral-coefficient-plot", "slope-aspect-map",
    "filled-contour-map", "kernel-density-map", "mantel-correlogram", "hinton-diagram"
  )
  if (recipe_id %in% bottom_legend_recipes) {
    p <- p + ggplot2::theme(
      legend.position = "bottom", legend.box = "vertical",
      legend.margin = ggplot2::margin(0, 0, 0, 0),
      legend.box.margin = ggplot2::margin(0, 0, 0, 0),
      plot.margin = ggplot2::margin(8, 9, 12, 9)
    )
  }
  if (recipe_id == "microbiome-composition") {
    p <- p + ggplot2::guides(fill = ggplot2::guide_legend(nrow = 2, byrow = TRUE))
  }
  if (recipe_id == "genome-track") {
    p <- p + ggplot2::guides(
      color = ggplot2::guide_legend(order = 1, nrow = 1),
      fill = ggplot2::guide_legend(order = 2, nrow = 1),
      size = ggplot2::guide_legend(order = 3, nrow = 1)
    )
  }
  if (recipe_id == "space-time-cube") {
    p <- p + ggplot2::guides(
      color = ggplot2::guide_legend(order = 1, nrow = 1),
      shape = ggplot2::guide_legend(order = 2, nrow = 1),
      size = ggplot2::guide_legend(order = 3, nrow = 1)
    )
  }
  if (recipe_id == "swimmer-plot") {
    p <- p + ggplot2::guides(
      color = ggplot2::guide_legend(order = 1, nrow = 1),
      shape = ggplot2::guide_legend(order = 2, nrow = 1)
    )
  }
  if (recipe_id == "pdp-plot") {
    p <- p + ggplot2::guides(
      color = ggplot2::guide_legend(order = 1, nrow = 1),
      fill = ggplot2::guide_legend(order = 2, nrow = 1)
    )
  }
  if (recipe_id == "ternary-response") {
    p <- p + ggplot2::guides(
      size = "none",
      color = ggplot2::guide_colorbar(order = 1, barwidth = grid::unit(23, "mm"),
                                      barheight = grid::unit(2.5, "mm"))
    )
  }
  if (recipe_id == "contour-enhanced-funnel") {
    p <- p + ggplot2::guides(fill = ggplot2::guide_legend(nrow = 2, byrow = TRUE))
  }
  if (recipe_id %in% c("multiverse-plot", "permanova-effect-plot", "specification-curve")) {
    p <- p + ggplot2::guides(
      color = ggplot2::guide_legend(nrow = 2, byrow = TRUE),
      shape = ggplot2::guide_legend(nrow = 1)
    )
  }
  if (recipe_id == "spectral-coefficient-plot") {
    p <- p + ggplot2::guides(
      color = ggplot2::guide_legend(nrow = 2, byrow = TRUE),
      fill = ggplot2::guide_legend(nrow = 2, byrow = TRUE)
    )
  }
  if (recipe_id == "soil-color-profile") {
    p <- p + ggplot2::guides(fill = ggplot2::guide_legend(nrow = 2, byrow = TRUE))
  }
  if (recipe_id == "hinton-diagram") {
    p <- p + ggplot2::guides(size = ggplot2::guide_legend(nrow = 2, byrow = TRUE))
  }
  attr(p, "resolved_typography") <- typography
  attr(p, "resolved_fonts") <- fonts
  p
}

write_clean_and_summary <- function(dat, config, derived_dir) {
  dir.create(derived_dir, recursive = TRUE, showWarnings = FALSE)
  utils::write.csv(dat, file.path(derived_dir, "validated-input.csv"), row.names = FALSE,
                   na = "NA", fileEncoding = "UTF-8")
  summary_path <- file.path(derived_dir, "descriptive-summary.csv")
  if (config$schema_id == "categorical") {
    out <- summary_mean_ci(dat)
  } else if (config$schema_id == "time-series") {
    out <- stats::aggregate(value ~ time + group, dat, function(x) c(n = length(x), mean = mean(x), sd = stats::sd(x)))
  } else {
    out <- data.frame(rows = nrow(dat), columns = ncol(dat), schema_id = config$schema_id)
  }
  utils::write.csv(out, summary_path, row.names = FALSE, na = "NA", fileEncoding = "UTF-8")
  invisible(list(validated = file.path(derived_dir, "validated-input.csv"), summary = summary_path))
}

save_figure <- function(figure, config, output_dir) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  width <- config$width_mm %||% 89
  height <- config$height_mm %||% 70
  dpi <- config$raster_dpi %||% 600
  stem <- config$recipe_id
  pdf_path <- file.path(output_dir, paste0(stem, ".pdf"))
  png_path <- file.path(output_dir, paste0(stem, ".png"))
  tiff_path <- file.path(output_dir, paste0(stem, ".tiff"))
  ggplot2::ggsave(pdf_path, figure, device = grDevices::pdf, width = width, height = height,
                  units = "mm", bg = config$pdf_background %||% "white", useDingbats = FALSE)
  png_device <- if (requireNamespace("ragg", quietly = TRUE)) ragg::agg_png else "png"
  ggplot2::ggsave(png_path, figure, device = png_device, width = width, height = height,
                  units = "mm", dpi = dpi, bg = config$png_background %||% "white")
  ggplot2::ggsave(tiff_path, figure, device = ragg::agg_tiff, width = width, height = height,
                  units = "mm", dpi = dpi, compression = "lzw",
                  bg = config$tiff_background %||% "white")
  list(pdf = pdf_path, png = png_path, tiff = tiff_path)
}

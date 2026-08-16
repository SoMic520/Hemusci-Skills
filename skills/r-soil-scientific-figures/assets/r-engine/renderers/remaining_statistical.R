# Remaining general statistical variants that require recipe-specific semantics.

render_advanced_flow <- function(dat, recipe_id, config) {
  dat$stage_factor <- factor(dat$stage, levels = sort(unique(dat$stage)))
  if (recipe_id == "alluvial-plot") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = stage, y = value, fill = group, group = path_id)) +
      ggplot2::geom_area(position = "stack", alpha = 0.80, color = "white", linewidth = 0.30) +
      ggplot2::geom_text(ggplot2::aes(label = state), position = ggplot2::position_stack(vjust = 0.5), size = 1.8, check_overlap = TRUE) +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::labs(x = "Ordered stage", y = "Flow abundance", fill = "Path group"))
  }
  if (recipe_id == "sankey-diagram") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = stage, y = value, color = group, group = path_id)) +
      ggplot2::geom_line(ggplot2::aes(linewidth = value), alpha = 0.55, lineend = "round") +
      ggplot2::geom_point(ggplot2::aes(size = value), shape = 21, fill = "white", stroke = 0.7) +
      ggplot2::geom_text(ggplot2::aes(label = state), vjust = -1, size = 1.85, check_overlap = TRUE) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_linewidth(range = c(1.2, 5), guide = "none") +
      ggplot2::scale_size_area(max_size = 5, guide = "none") +
      ggplot2::labs(x = "Stage", y = "Node / flow magnitude", color = "Path"))
  }
  if (recipe_id == "parallel-sets") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = stage_factor, y = state, group = path_id, color = group)) +
      ggplot2::geom_line(linewidth = 1.8, alpha = 0.48) + ggplot2::geom_point(ggplot2::aes(size = value), alpha = 0.85) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_size_area(max_size = 5) +
      ggplot2::labs(x = "Parallel set axis", y = "Categorical state", color = "Path", size = "Flow"))
  }
  if (recipe_id == "riverplot") {
    dat$centered <- ave(dat$value, dat$stage, FUN = function(z) z - mean(z))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = stage, y = centered, group = path_id, color = group)) +
      ggplot2::geom_line(ggplot2::aes(linewidth = value), alpha = 0.72,
                         lineend = "round", linejoin = "round") +
      ggplot2::geom_point(ggplot2::aes(size = value), alpha = 0.86) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::scale_linewidth(range = c(1, 4), guide = "none") + ggplot2::scale_size_area(max_size = 4, guide = "none") +
      ggplot2::labs(x = "River stage", y = "Centered flow", color = "River branch"))
  }
  NULL
}
register_recipe_override(c("alluvial-plot", "sankey-diagram", "parallel-sets", "riverplot"), render_advanced_flow)

render_advanced_matrix <- function(dat, recipe_id, config) {
  dat$row_id <- factor(dat$row_id, levels = unique(dat$row_id))
  dat$column_id <- factor(dat$column_id, levels = unique(dat$column_id))
  diverging <- ggplot2::scale_fill_gradient2(low = "#2166AC", mid = "white", high = "#B2182B", midpoint = 0)
  if (recipe_id == "heatmap") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, fill = value)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.30) + diverging +
      ggplot2::labs(x = NULL, y = NULL, fill = "Value"))
  }
  if (recipe_id == "correlation-matrix") {
    dat$row_index <- as.numeric(dat$row_id)
    dat$column_index <- as.numeric(dat$column_id)
    dat <- dat[dat$column_index >= dat$row_index, ]
    return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, fill = value)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.35) +
      ggplot2::geom_text(ggplot2::aes(label = sprintf("%.2f", value)), size = 1.9) + diverging +
      ggplot2::labs(x = NULL, y = NULL, fill = "Correlation"))
  }
  if (recipe_id == "distance-matrix") {
    dat$distance <- abs(dat$value)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, fill = distance)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.25) +
      ggplot2::scale_fill_viridis_c(option = "C", direction = -1) +
      ggplot2::labs(x = "Object", y = "Object", fill = "Distance"))
  }
  if (recipe_id == "fourth-corner-heatmap") {
    dat$direction <- factor(sign(dat$value), levels = c(-1, 1), labels = c("Negative", "Positive"))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id)) +
      ggplot2::geom_tile(ggplot2::aes(fill = direction), color = "white", linewidth = 0.35, alpha = 0.25) +
      ggplot2::geom_point(ggplot2::aes(size = abs(value), color = value), alpha = 0.88) +
      ggplot2::scale_fill_manual(values = c(Negative = "#2166AC", Positive = "#B2182B"), guide = "none") +
      ggplot2::scale_color_gradient2(low = "#2166AC", mid = "white", high = "#B2182B", midpoint = 0) +
      ggplot2::scale_size_area(max_size = 7) + ggplot2::theme(legend.box = "vertical") +
      ggplot2::labs(x = "Environmental variable", y = "Trait / taxon", color = "Association", size = "|Value|"))
  }
  if (recipe_id == "annotated-heatmap") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, fill = value)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.35) +
      ggplot2::geom_text(ggplot2::aes(label = sprintf("%.2f", value)), size = 2.0) + diverging +
      ggplot2::labs(x = NULL, y = NULL, fill = "Value"))
  }
  if (recipe_id == "association-plot") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, color = value, size = abs(value))) +
      ggplot2::geom_hline(yintercept = seq(1.5, length(levels(dat$row_id)) - 0.5), color = "#EFEFEF") +
      ggplot2::geom_point(shape = 21, fill = "white", stroke = 0.8) +
      ggplot2::scale_color_gradient2(low = "#2166AC", mid = "#BDBDBD", high = "#B2182B", midpoint = 0) +
      ggplot2::scale_size_area(max_size = 8) + ggplot2::theme(legend.box = "vertical") +
      ggplot2::labs(x = NULL, y = NULL, color = "Association", size = "Magnitude"))
  }
  if (recipe_id == "confusion-matrix") {
    dat$correct <- as.character(dat$row_id) == as.character(dat$column_id)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, fill = value)) +
      ggplot2::geom_tile(ggplot2::aes(linewidth = correct), color = "white") +
      ggplot2::geom_text(data = dat[!dat$correct, , drop = FALSE],
                         ggplot2::aes(label = sprintf("%.2f", value)), size = 2.0) +
      ggplot2::geom_text(data = dat[dat$correct, , drop = FALSE],
                         ggplot2::aes(label = sprintf("%.2f", value)), fontface = "bold", size = 2.0) +
      diverging + ggplot2::scale_linewidth_manual(values = c(`FALSE` = 0.25, `TRUE` = 0.9), guide = "none") +
      ggplot2::labs(x = "Predicted", y = "Observed", fill = "Cell value"))
  }
  if (recipe_id == "mosaic-plot") {
    dat$magnitude <- scales::rescale(abs(dat$value), to = c(0.35, 0.95))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, fill = value, width = magnitude, height = magnitude)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.35) + diverging +
      ggplot2::labs(x = "Column category", y = "Row category", fill = "Signed value"))
  }
  if (recipe_id %in% c("dot-heatmap", "enrichment-dotplot", "fluctuation-diagram")) {
    if (recipe_id == "dot-heatmap") {
      return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, color = value, size = abs(value))) +
        ggplot2::geom_point(alpha = 0.86) + ggplot2::scale_color_viridis_c(option = "C") +
        ggplot2::scale_size_area(max_size = 7) + ggplot2::theme(legend.box = "vertical") +
        ggplot2::labs(x = NULL, y = NULL, color = "Value", size = "Magnitude"))
    }
    if (recipe_id == "enrichment-dotplot") {
      dat$row_id <- reorder(dat$row_id, dat$value, mean)
      return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, color = value, size = abs(value))) +
        ggplot2::geom_point(alpha = 0.86) + ggplot2::scale_color_gradient(low = "#56B4E9", high = "#D55E00") +
        ggplot2::scale_size_area(max_size = 8) + ggplot2::theme(legend.box = "vertical") +
        ggplot2::labs(x = "Condition", y = "Enriched term", color = "Score", size = "Strength"))
    }
    dat$direction <- factor(sign(dat$value), levels = c(-1, 1), labels = c("Negative", "Positive"))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = column_id, y = row_id, fill = direction)) +
      ggplot2::geom_tile(ggplot2::aes(width = scales::rescale(abs(value), c(0.25, 0.95)),
                                     height = scales::rescale(abs(value), c(0.25, 0.95))), color = "white") +
      ggplot2::scale_fill_manual(values = c(Negative = "#2166AC", Positive = "#B2182B")) +
      ggplot2::labs(x = NULL, y = NULL, fill = "Direction"))
  }
  NULL
}
register_recipe_override(
  c("heatmap", "correlation-matrix", "distance-matrix", "fourth-corner-heatmap", "annotated-heatmap",
    "association-plot", "confusion-matrix", "mosaic-plot", "dot-heatmap", "enrichment-dotplot", "fluctuation-diagram"),
  render_advanced_matrix
)

render_advanced_paired <- function(dat, recipe_id, config) {
  if (!"block" %in% names(dat)) return(NULL)
  dat$group <- factor(dat$group, levels = unique(dat$group))
  if (recipe_id == "paired-dotplot") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = group, y = value, group = block)) +
      ggplot2::geom_line(color = "#A0A0A0", linewidth = 0.40) +
      ggplot2::geom_point(ggplot2::aes(color = group), size = 1.8) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::guides(color = "none") +
      ggplot2::labs(x = NULL, y = value_axis_label(dat)))
  }
  wide <- reshape(dat[c("block", "group", "value")], idvar = "block", timevar = "group", direction = "wide")
  group_names <- levels(dat$group)[1:2]
  names(wide)[names(wide) == paste0("value.", group_names[1])] <- "first"
  names(wide)[names(wide) == paste0("value.", group_names[2])] <- "second"
  if (recipe_id == "dumbbell-plot") {
    return(ggplot2::ggplot(wide, ggplot2::aes(y = reorder(block, first))) +
      ggplot2::geom_segment(ggplot2::aes(x = first, xend = second, yend = reorder(block, first)), color = "#A0A0A0", linewidth = 0.55) +
      ggplot2::geom_point(ggplot2::aes(x = first), color = palette_discrete[1], size = 1.9) +
      ggplot2::geom_point(ggplot2::aes(x = second), color = palette_discrete[2], size = 1.9) +
      ggplot2::labs(x = value_axis_label(dat), y = "Paired unit"))
  }
  if (recipe_id == "slopegraph") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = group, y = value, group = block)) +
      ggplot2::geom_line(ggplot2::aes(color = value - ave(value, block, FUN = function(z) z[1])), linewidth = 0.55) +
      ggplot2::geom_point(size = 1.7) +
      ggplot2::scale_color_gradient2(low = "#2166AC", mid = "#BDBDBD", high = "#B2182B", midpoint = 0) +
      ggplot2::labs(x = NULL, y = value_axis_label(dat), color = "Change"))
  }
  if (recipe_id == "bump-chart") {
    dat$rank <- ave(-dat$value, dat$group, FUN = rank)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = group, y = rank, group = block, color = block)) +
      ggplot2::geom_line(linewidth = 0.60, alpha = 0.70) + ggplot2::geom_point(size = 1.7) +
      ggplot2::scale_y_reverse() + ggplot2::guides(color = "none") +
      ggplot2::labs(x = NULL, y = "Within-group rank"))
  }
  NULL
}
register_recipe_override(c("paired-dotplot", "dumbbell-plot", "slopegraph", "bump-chart"), render_advanced_paired)

ordination_parts <- function(dat) {
  list(samples = dat[dat$element_type == "sample", , drop = FALSE], arrows = dat[dat$element_type == "arrow", , drop = FALSE])
}

render_advanced_ordination <- function(dat, recipe_id, config) {
  parts <- ordination_parts(dat)
  samples <- parts$samples
  arrows <- parts$arrows
  axis_x <- unique(dat$axis1_label)[1]
  axis_y <- unique(dat$axis2_label)[1]
  base <- ggplot2::ggplot(samples, ggplot2::aes(x = axis1, y = axis2, color = group)) +
    ggplot2::geom_hline(yintercept = 0, color = "#D9D9D9", linewidth = 0.30) +
    ggplot2::geom_vline(xintercept = 0, color = "#D9D9D9", linewidth = 0.30) +
    ggplot2::scale_color_manual(values = palette_discrete)
  if (recipe_id == "pca-biplot") {
    return(base + ggplot2::geom_point(size = 2.0) +
      ggplot2::geom_segment(data = arrows, ggplot2::aes(x = 0, y = 0, xend = axis1, yend = axis2),
                            inherit.aes = FALSE, arrow = grid::arrow(length = grid::unit(1.5, "mm"))) +
      ggplot2::geom_text(data = arrows, ggplot2::aes(x = axis1, y = axis2, label = label), inherit.aes = FALSE, size = 1.9) +
      ggplot2::labs(x = axis_x, y = axis_y, color = "Group"))
  }
  if (recipe_id == "rda-triplot") {
    centroids <- stats::aggregate(cbind(axis1, axis2) ~ group, samples, mean)
    return(base + ggplot2::geom_point(size = 1.6, alpha = 0.65) +
      ggplot2::geom_segment(data = arrows, ggplot2::aes(x = 0, y = 0, xend = 1.2 * axis1, yend = 1.2 * axis2),
                            inherit.aes = FALSE, color = "#333333", arrow = grid::arrow(length = grid::unit(1.4, "mm"))) +
      ggplot2::geom_point(data = centroids, ggplot2::aes(x = axis1, y = axis2, fill = group), inherit.aes = FALSE,
                          shape = 23, size = 3.2, color = "#222222") +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::labs(x = axis_x, y = axis_y, color = "Sites", fill = "Centroid"))
  }
  if (recipe_id == "cca-triplot") {
    return(base + ggplot2::geom_point(ggplot2::aes(shape = group), size = 2.0) +
      ggplot2::geom_curve(data = arrows, ggplot2::aes(x = 0, y = 0, xend = axis1, yend = axis2), inherit.aes = FALSE,
                          curvature = 0.12, color = "#444444", arrow = grid::arrow(length = grid::unit(1.3, "mm"))) +
      ggplot2::geom_label(data = arrows, ggplot2::aes(x = axis1, y = axis2, label = label), inherit.aes = FALSE,
                          size = 1.75, label.size = 0.2, fill = "white") +
      ggplot2::labs(x = axis_x, y = axis_y, color = "Group", shape = "Group"))
  }
  if (recipe_id == "envfit-ordination") {
    return(base + ggplot2::geom_point(size = 1.8, alpha = 0.75) +
      ggplot2::geom_segment(data = arrows, ggplot2::aes(x = 0, y = 0, xend = axis1, yend = axis2, linewidth = sqrt(axis1^2 + axis2^2)),
                            inherit.aes = FALSE, color = "#009E73", arrow = grid::arrow(length = grid::unit(1.5, "mm"))) +
      ggplot2::geom_text(data = arrows, ggplot2::aes(x = 1.08 * axis1, y = 1.08 * axis2, label = label), inherit.aes = FALSE,
                         color = "#006D4F", fontface = "bold", size = 1.9) +
      ggplot2::scale_linewidth(range = c(0.4, 1.2), guide = "none") + ggplot2::labs(x = axis_x, y = axis_y, color = "Group"))
  }
  if (recipe_id == "pcoa-plot") {
    return(base + ggplot2::geom_point(ggplot2::aes(shape = group), size = 2.2) +
      ggplot2::coord_equal() + ggplot2::labs(x = axis_x, y = axis_y, color = "Group", shape = "Group"))
  }
  if (recipe_id == "nmds-plot") {
    hull <- do.call(rbind, lapply(split(samples, samples$group), function(part) part[chull(part$axis1, part$axis2), ]))
    return(base + ggplot2::geom_polygon(data = hull, ggplot2::aes(fill = group, group = group), alpha = 0.12, color = NA) +
      ggplot2::geom_point(size = 2.0) + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::labs(x = "NMDS1", y = "NMDS2", color = "Group", fill = "Group"))
  }
  if (recipe_id == "dbrda-plot") {
    centroids <- stats::aggregate(cbind(axis1, axis2) ~ group, samples, mean)
    linked <- merge(samples, centroids, by = "group", suffixes = c("", "_centroid"))
    return(base + ggplot2::geom_segment(data = linked,
      ggplot2::aes(x = axis1_centroid, y = axis2_centroid, xend = axis1, yend = axis2, color = group), alpha = 0.45) +
      ggplot2::geom_point(size = 1.8) + ggplot2::geom_point(data = centroids, shape = 4, size = 3.4, stroke = 0.9) +
      ggplot2::labs(x = "dbRDA1", y = "dbRDA2", color = "Group"))
  }
  if (recipe_id == "co-inertia-plot") {
    shifted <- samples
    shifted$axis1_end <- shifted$axis1 + ifelse(shifted$group == unique(shifted$group)[1], 0.18, -0.18)
    shifted$axis2_end <- shifted$axis2 + 0.12
    return(base + ggplot2::geom_segment(data = shifted,
      ggplot2::aes(xend = axis1_end, yend = axis2_end, color = group), arrow = grid::arrow(length = grid::unit(1.1, "mm"))) +
      ggplot2::geom_point(size = 1.8) + ggplot2::labs(x = "Co-inertia axis 1", y = "Co-inertia axis 2", color = "Group"))
  }
  if (recipe_id == "ordination-spider") {
    centroids <- stats::aggregate(cbind(axis1, axis2) ~ group, samples, mean)
    linked <- merge(samples, centroids, by = "group", suffixes = c("", "_centroid"))
    return(base + ggplot2::geom_segment(data = linked,
      ggplot2::aes(x = axis1_centroid, y = axis2_centroid, xend = axis1, yend = axis2, color = group), alpha = 0.55) +
      ggplot2::geom_point(size = 1.8) + ggplot2::geom_point(data = centroids, size = 3.2, shape = 4) +
      ggplot2::labs(x = axis_x, y = axis_y, color = "Group"))
  }
  if (recipe_id == "beta-dispersion-plot") {
    centroids <- stats::aggregate(cbind(axis1, axis2) ~ group, samples, mean)
    linked <- merge(samples, centroids, by = "group", suffixes = c("", "_centroid"))
    linked$distance <- sqrt((linked$axis1 - linked$axis1_centroid)^2 + (linked$axis2 - linked$axis2_centroid)^2)
    return(ggplot2::ggplot(linked, ggplot2::aes(x = group, y = distance, color = group)) +
      ggplot2::geom_boxplot(width = 0.35, outlier.shape = NA, alpha = 0.12) +
      ggplot2::geom_point(size = 1.8, position = ggplot2::position_jitter(width = 0.05)) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::guides(color = "none") +
      ggplot2::labs(x = NULL, y = "Distance to group centroid"))
  }
  NULL
}
register_recipe_override(
  c("pca-biplot", "rda-triplot", "cca-triplot", "envfit-ordination", "pcoa-plot", "nmds-plot",
    "dbrda-plot", "co-inertia-plot", "ordination-spider", "beta-dispersion-plot"),
  render_advanced_ordination
)

render_advanced_density_comparison <- function(dat, recipe_id, config) {
  if (recipe_id == "density-2d") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = group)) +
      ggplot2::geom_point(alpha = 0.35, size = 1.2) + ggplot2::stat_density_2d(linewidth = 0.55) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::labs(x = "X", y = "Y", color = "Group"))
  }
  if (recipe_id == "density-raster") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y)) +
      ggplot2::stat_bin_2d(bins = 12) + ggplot2::scale_fill_viridis_c(option = "C") +
      ggplot2::labs(x = "X", y = "Y", fill = "Bin count"))
  }
  if (recipe_id == "scatter-density") {
    dat$local_density <- vapply(seq_len(nrow(dat)), function(index) {
      distance <- (dat$x - dat$x[index])^2 + (dat$y - dat$y[index])^2
      sum(distance <= stats::quantile(distance, 0.25))
    }, numeric(1))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = local_density)) +
      ggplot2::geom_point(size = 2.0) + ggplot2::scale_color_viridis_c(option = "C") +
      ggplot2::labs(x = "X", y = "Y", color = "Local density"))
  }
  if (recipe_id == "hexbin-plot") {
    # Dependency-free axial hexagonal binning. Alternating rows are shifted by
    # half a cell, which preserves the hexagonal neighbourhood geometry without
    # requiring the optional `hexbin` package.
    x_width <- diff(range(dat$x, na.rm = TRUE)) / 8
    y_width <- diff(range(dat$y, na.rm = TRUE)) / 8
    dat$hex_row <- floor((dat$y - min(dat$y, na.rm = TRUE)) / y_width)
    dat$hex_col <- floor((dat$x - min(dat$x, na.rm = TRUE)) / x_width - 0.5 * (dat$hex_row %% 2))
    bins <- stats::aggregate(rep(1, nrow(dat)),
      by = list(hex_col = dat$hex_col, hex_row = dat$hex_row), FUN = sum)
    names(bins)[3] <- "count"
    bins$x <- min(dat$x, na.rm = TRUE) + (bins$hex_col + 0.5 * (bins$hex_row %% 2) + 0.5) * x_width
    bins$y <- min(dat$y, na.rm = TRUE) + (bins$hex_row + 0.5) * y_width
    angle <- seq(0, 2 * pi, length.out = 7)[1:6] + pi / 6
    hexagons <- do.call(rbind, lapply(seq_len(nrow(bins)), function(index) {
      data.frame(
        bin_id = index,
        x = bins$x[index] + 0.52 * x_width * cos(angle),
        y = bins$y[index] + 0.58 * y_width * sin(angle),
        count = bins$count[index]
      )
    }))
    return(ggplot2::ggplot(hexagons, ggplot2::aes(x = x, y = y, fill = count, group = bin_id)) +
      ggplot2::geom_polygon(linewidth = 0.28, color = "white") +
      ggplot2::scale_fill_viridis_c(option = "C") +
      ggplot2::labs(x = "X", y = "Y", fill = "Count"))
  }
  if (recipe_id == "rect-bin2d") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y)) +
      ggplot2::stat_bin_2d(bins = 8, color = "white", linewidth = 0.25) + ggplot2::scale_fill_viridis_c(option = "B") +
      ggplot2::labs(x = "X", y = "Y", fill = "Count"))
  }
  if (recipe_id == "scatterplot") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = group)) +
      ggplot2::geom_point(size = 1.8, alpha = 0.82) + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Predictor", y = "Response", color = "Group"))
  }
  if (recipe_id == "prevalence-abundance") {
    dat$prevalence_proxy <- ave(dat$y, dat$group, FUN = rank) / ave(dat$y, dat$group, FUN = length)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = prevalence_proxy, size = y, color = group)) +
      ggplot2::geom_point(alpha = 0.72) + ggplot2::scale_size_area(max_size = 5) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Mean abundance", y = "Prevalence proxy", size = "Abundance", color = "Group"))
  }
  NULL
}
register_recipe_override(c("density-2d", "density-raster", "scatter-density", "hexbin-plot", "rect-bin2d", "scatterplot", "prevalence-abundance"), render_advanced_density_comparison)

render_advanced_bar_and_superplot <- function(dat, recipe_id, config) {
  dat$group <- factor(dat$group, levels = unique(dat$group))
  if (recipe_id == "grouped-bar" && "block" %in% names(dat)) {
    block_summary <- stats::aggregate(value ~ block + group, dat, mean)
    block_summary$block <- factor(block_summary$block, levels = unique(dat$block))
    return(ggplot2::ggplot(block_summary, ggplot2::aes(x = block, y = value, fill = group)) +
      ggplot2::geom_col(position = ggplot2::position_dodge(width = 0.76), width = 0.68,
                        color = "white", linewidth = 0.25) +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1)) +
      ggplot2::labs(x = "Experimental block", y = value_axis_label(dat), fill = "Treatment"))
  }
  if (recipe_id == "superplot" && "block" %in% names(dat)) {
    levels_group <- levels(dat$group)
    dat$group_index <- as.numeric(dat$group)
    block_levels <- unique(dat$block)
    block_offset <- setNames(seq(-0.22, 0.22, length.out = length(block_levels)), block_levels)
    dat$plot_x <- dat$group_index + block_offset[as.character(dat$block)]
    summaries <- summary_mean_ci(dat)
    summaries$group_index <- match(summaries$group, levels_group)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = plot_x, y = value)) +
      ggplot2::geom_point(shape = 21, size = 1.55, fill = "#BDBDBD", color = "white", alpha = 0.90) +
      ggplot2::geom_errorbar(data = summaries,
        ggplot2::aes(x = group_index, ymin = lower, ymax = upper), inherit.aes = FALSE,
        width = 0.10, linewidth = 0.75, color = "#222222") +
      ggplot2::geom_point(data = summaries,
        ggplot2::aes(x = group_index, y = mean, fill = group), inherit.aes = FALSE,
        shape = 23, size = 3.4, color = "#222222", stroke = 0.55) +
      ggplot2::scale_x_continuous(breaks = seq_along(levels_group), labels = levels_group,
                                  expand = ggplot2::expansion(mult = 0.15)) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::guides(fill = "none") +
      ggplot2::labs(x = NULL, y = value_axis_label(dat),
                    caption = "Small points are independent blocks; diamonds show group estimates and intervals."))
  }
  NULL
}
register_recipe_override(c("grouped-bar", "superplot"), render_advanced_bar_and_superplot)

render_advanced_box_variants <- function(dat, recipe_id, config) {
  dat$group <- factor(dat$group, levels = unique(dat$group))
  if (recipe_id == "letter-value-plot") {
    probabilities <- list(c(0.125, 0.875), c(0.25, 0.75), c(0.375, 0.625))
    widths <- c(0.72, 0.52, 0.32)
    alpha_values <- c(0.18, 0.32, 0.52)
    rectangles <- do.call(rbind, lapply(seq_along(levels(dat$group)), function(group_index) {
      values <- dat$value[dat$group == levels(dat$group)[group_index]]
      do.call(rbind, lapply(seq_along(probabilities), function(depth) {
        interval <- stats::quantile(values, probabilities[[depth]], names = FALSE)
        data.frame(group_index = group_index, ymin = interval[1], ymax = interval[2],
                   xmin = group_index - widths[depth] / 2, xmax = group_index + widths[depth] / 2,
                   alpha = alpha_values[depth], fill = palette_discrete[group_index])
      }))
    }))
    medians <- stats::aggregate(value ~ group, dat, stats::median)
    medians$group_index <- match(medians$group, levels(dat$group))
    return(ggplot2::ggplot(rectangles) +
      ggplot2::geom_rect(ggplot2::aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax,
                                     fill = fill, alpha = alpha), color = "white", linewidth = 0.35) +
      ggplot2::geom_segment(data = medians,
        ggplot2::aes(x = group_index - 0.17, xend = group_index + 0.17, y = value, yend = value),
        inherit.aes = FALSE, linewidth = 0.85, color = "#222222") +
      ggplot2::scale_fill_identity() + ggplot2::scale_alpha_identity() +
      ggplot2::scale_x_continuous(breaks = seq_along(levels(dat$group)), labels = levels(dat$group)) +
      ggplot2::labs(x = NULL, y = value_axis_label(dat),
                    caption = "Nested boxes show central 75%, 50%, and 25% intervals."))
  }
  if (recipe_id == "variable-width-boxplot") {
    counts <- as.data.frame(table(dat$group), stringsAsFactors = FALSE)
    names(counts) <- c("group", "n")
    counts$x <- max(dat$value) + 0.04 * diff(range(dat$value))
    return(ggplot2::ggplot(dat, ggplot2::aes(y = group, x = value, fill = group, color = group)) +
      ggplot2::geom_boxplot(varwidth = TRUE, outlier.shape = NA, alpha = 0.25, linewidth = 0.55) +
      ggplot2::geom_point(position = ggplot2::position_jitter(height = 0.07), size = 1.25, alpha = 0.72) +
      ggplot2::geom_text(data = counts, ggplot2::aes(y = group, x = x, label = paste0("n=", n)),
                         inherit.aes = FALSE, hjust = 0, size = 1.9) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::guides(fill = "none", color = "none") +
      ggplot2::scale_x_continuous(expand = ggplot2::expansion(mult = c(0.04, 0.18))) +
      ggplot2::labs(x = value_axis_label(dat), y = NULL,
                    caption = "Box width is proportional to the square root of group sample size."))
  }
  NULL
}
register_recipe_override(c("letter-value-plot", "variable-width-boxplot"), render_advanced_box_variants)

.bootstrap_differences <- function(dat, draws = 1200L, seed = 20260816L) {
  dat$group <- factor(dat$group, levels = unique(dat$group))
  groups <- levels(dat$group)[1:2]
  first <- dat$value[dat$group == groups[1]]
  second <- dat$value[dat$group == groups[2]]
  set.seed(seed)
  differences <- replicate(draws,
    mean(sample(second, length(second), replace = TRUE)) - mean(sample(first, length(first), replace = TRUE)))
  list(groups = groups, first = first, second = second, differences = differences)
}

render_advanced_estimation <- function(dat, recipe_id, config) {
  bootstrap <- .bootstrap_differences(dat)
  interval <- stats::quantile(bootstrap$differences, c(0.025, 0.5, 0.975), names = FALSE)
  difference <- mean(bootstrap$second) - mean(bootstrap$first)
  if (recipe_id == "bootstrap-distribution") {
    draws <- data.frame(difference = bootstrap$differences)
    return(ggplot2::ggplot(draws, ggplot2::aes(x = difference)) +
      ggplot2::geom_density(fill = scales::alpha(palette_discrete[1], 0.28), color = palette_discrete[1], linewidth = 0.75) +
      ggplot2::geom_vline(xintercept = interval[c(1, 3)], linetype = 2, linewidth = 0.45) +
      ggplot2::geom_vline(xintercept = interval[2], linewidth = 0.75, color = palette_discrete[2]) +
      ggplot2::labs(x = paste0("Bootstrap mean difference (", bootstrap$groups[2], " − ", bootstrap$groups[1], ")"),
                    y = "Bootstrap density"))
  }
  if (recipe_id == "gardner-altman") {
    dat$group <- factor(dat$group, levels = bootstrap$groups)
    dat$x <- as.numeric(dat$group)
    estimate_density <- stats::density(bootstrap$differences, n = 256)
    estimate_density$scaled <- estimate_density$y / max(estimate_density$y) * 0.34
    polygon <- data.frame(x = c(rep(3, length(estimate_density$x)), rev(3 + estimate_density$scaled)),
                          y = c(estimate_density$x, rev(estimate_density$x)))
    return(ggplot2::ggplot() +
      ggplot2::geom_point(data = dat, ggplot2::aes(x = x, y = value, color = group),
        position = ggplot2::position_jitter(width = 0.07), size = 1.35, alpha = 0.78) +
      ggplot2::geom_polygon(data = polygon, ggplot2::aes(x = x, y = y),
                            fill = scales::alpha(palette_discrete[3], 0.30), color = palette_discrete[3]) +
      ggplot2::geom_errorbar(data = data.frame(x = 3, y = interval[2], lower = interval[1], upper = interval[3]),
        ggplot2::aes(x = x, ymin = lower, ymax = upper), inherit.aes = FALSE, width = 0.10, linewidth = 0.65) +
      ggplot2::geom_point(data = data.frame(x = 3, y = interval[2]), ggplot2::aes(x = x, y = y),
                          inherit.aes = FALSE, shape = 21, fill = "white", size = 2.1) +
      ggplot2::scale_x_continuous(breaks = 1:3, labels = c(bootstrap$groups, "Mean\ndifference")) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::guides(color = "none") +
      ggplot2::labs(x = NULL, y = paste0(value_axis_label(dat), " / difference")))
  }
  if (recipe_id == "cumming-estimation") {
    se_first <- stats::sd(bootstrap$first) / sqrt(length(bootstrap$first))
    se_second <- stats::sd(bootstrap$second) / sqrt(length(bootstrap$second))
    estimates <- data.frame(
      estimand = factor(c(bootstrap$groups[1], bootstrap$groups[2], "Mean difference"),
                        levels = rev(c(bootstrap$groups[1], bootstrap$groups[2], "Mean difference"))),
      estimate = c(mean(bootstrap$first), mean(bootstrap$second), difference),
      lower = c(mean(bootstrap$first) - 1.96 * se_first, mean(bootstrap$second) - 1.96 * se_second, interval[1]),
      upper = c(mean(bootstrap$first) + 1.96 * se_first, mean(bootstrap$second) + 1.96 * se_second, interval[3]),
      type = c("Group mean", "Group mean", "Contrast")
    )
    return(ggplot2::ggplot(estimates, ggplot2::aes(x = estimate, y = estimand, color = type)) +
      ggplot2::geom_vline(xintercept = 0, linewidth = 0.30, linetype = 2) +
      ggplot2::geom_errorbarh(ggplot2::aes(xmin = lower, xmax = upper), height = 0.16, linewidth = 0.65) +
      ggplot2::geom_point(size = 2.2) + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Estimate with 95% interval", y = NULL, color = "Estimand type"))
  }
  if (recipe_id == "hypothetical-outcome-plot") {
    set.seed(20260817)
    draws <- seq_len(24)
    outcomes <- data.frame(
      draw = draws,
      first = vapply(draws, function(index) mean(sample(bootstrap$first, length(bootstrap$first), replace = TRUE)), numeric(1)),
      second = vapply(draws, function(index) mean(sample(bootstrap$second, length(bootstrap$second), replace = TRUE)), numeric(1))
    )
    outcomes$direction <- ifelse(outcomes$second >= outcomes$first, "Positive", "Negative")
    return(ggplot2::ggplot(outcomes, ggplot2::aes(y = draw, color = direction)) +
      ggplot2::geom_segment(ggplot2::aes(x = first, xend = second, yend = draw), linewidth = 0.58,
                            arrow = grid::arrow(length = grid::unit(1.0, "mm"))) +
      ggplot2::geom_point(ggplot2::aes(x = first), shape = 21, fill = "white", size = 1.35) +
      ggplot2::geom_point(ggplot2::aes(x = second), size = 1.35) +
      ggplot2::scale_color_manual(values = c(Positive = palette_discrete[2], Negative = palette_discrete[1])) +
      ggplot2::labs(x = "Resampled group mean", y = "Hypothetical resample", color = "Difference"))
  }
  NULL
}
register_recipe_override(
  c("bootstrap-distribution", "gardner-altman", "cumming-estimation", "hypothetical-outcome-plot"),
  render_advanced_estimation
)

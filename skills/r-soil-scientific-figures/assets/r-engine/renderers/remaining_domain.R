# Domain-specific variants for soil science, ecology, omics and environmental data.
#
# Every renderer in this module is dependency-light by design.  Scientific
# quantities are calculated explicitly from the validated input table so that a
# recipe remains auditable and produces the same result on macOS and Windows.

.circle_vertices <- function(x, y, radius, id, vertices = 181L) {
  angle <- seq(0, 2 * pi, length.out = vertices)
  data.frame(x = x + radius * cos(angle), y = y + radius * sin(angle), id = id)
}

.density_polygon <- function(values, group_name, side = 1, scale = 0.42) {
  estimate <- stats::density(values, na.rm = TRUE, n = 256)
  estimate$y <- estimate$y / max(estimate$y) * scale * side
  data.frame(value = c(estimate$x, rev(estimate$x)),
             offset = c(rep(0, length(estimate$x)), rev(estimate$y)),
             group = group_name)
}

render_domain_distribution <- function(dat, recipe_id, config) {
  dat$group <- factor(dat$group, levels = unique(dat$group))
  dat$group_index <- as.numeric(dat$group)
  value_label <- value_axis_label(dat)
  if (recipe_id == "violin-plot") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = group, y = value, fill = group, color = group)) +
      ggplot2::geom_violin(trim = FALSE, alpha = 0.26, linewidth = 0.65, width = 0.82) +
      ggplot2::stat_summary(fun = stats::median, geom = "point", shape = 21, fill = "white", size = 2.0) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::guides(fill = "none", color = "none") + ggplot2::labs(x = NULL, y = value_label))
  }
  if (recipe_id == "beanplot") {
    densities <- do.call(rbind, lapply(levels(dat$group), function(group_name) {
      part <- .density_polygon(dat$value[dat$group == group_name], group_name, side = 1, scale = 0.38)
      part$group_index <- match(group_name, levels(dat$group))
      part
    }))
    medians <- stats::aggregate(value ~ group, dat, stats::median)
    medians$group_index <- match(medians$group, levels(dat$group))
    ticks <- dat
    ticks$group_index <- match(ticks$group, levels(dat$group))
    return(ggplot2::ggplot(densities,
      ggplot2::aes(x = group_index + offset, y = value, fill = group, group = group)) +
      ggplot2::geom_polygon(alpha = 0.28, color = NA) +
      ggplot2::geom_segment(data = medians,
        ggplot2::aes(x = group_index - 0.30, xend = group_index + 0.30, y = value, yend = value),
        inherit.aes = FALSE, linewidth = 0.85, color = "#222222") +
      ggplot2::geom_segment(data = ticks,
        ggplot2::aes(x = group_index + 0.40, xend = group_index + 0.47, y = value, yend = value, color = group),
        inherit.aes = FALSE, linewidth = 0.38) +
      ggplot2::scale_x_continuous(breaks = seq_along(levels(dat$group)), labels = levels(dat$group)) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::guides(fill = "none", color = "none") + ggplot2::labs(x = NULL, y = value_label))
  }
  if (recipe_id == "density-plot") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = value, fill = group, color = group)) +
      ggplot2::geom_density(alpha = 0.18, linewidth = 0.75, adjust = 0.9) +
      ggplot2::geom_rug(ggplot2::aes(color = group), alpha = 0.55, sides = "b") +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = value_label, y = "Probability density", fill = "Group", color = "Group"))
  }
  if (recipe_id %in% c("half-violin", "raincloud-plot", "half-eye-plot")) {
    density_data <- do.call(rbind, lapply(levels(dat$group), function(group_name) {
      part <- .density_polygon(dat$value[dat$group == group_name], group_name, side = 1, scale = 0.40)
      part$group_index <- match(group_name, levels(dat$group))
      part
    }))
    if (recipe_id == "half-violin") {
      return(ggplot2::ggplot(density_data,
        ggplot2::aes(x = group_index + offset, y = value, fill = group, group = group)) +
        ggplot2::geom_polygon(alpha = 0.30, color = "#333333", linewidth = 0.45) +
        ggplot2::geom_point(data = dat,
          ggplot2::aes(x = group_index - 0.10, y = value, color = group), inherit.aes = FALSE,
          position = ggplot2::position_jitter(width = 0.045), size = 1.35, alpha = 0.75) +
        ggplot2::scale_x_continuous(breaks = seq_along(levels(dat$group)), labels = levels(dat$group)) +
        ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_color_manual(values = palette_discrete) +
        ggplot2::guides(fill = "none", color = "none") + ggplot2::labs(x = NULL, y = value_label))
    }
    summaries <- do.call(rbind, lapply(levels(dat$group), function(group_name) {
      values <- dat$value[dat$group == group_name]
      data.frame(group = group_name, group_index = match(group_name, levels(dat$group)),
                 median = stats::median(values), lower = stats::quantile(values, 0.25),
                 upper = stats::quantile(values, 0.75))
    }))
    if (recipe_id == "half-eye-plot") {
      return(ggplot2::ggplot(density_data,
        ggplot2::aes(x = value, y = group_index + offset, fill = group, group = group)) +
        ggplot2::geom_polygon(alpha = 0.30, color = NA) +
        ggplot2::geom_segment(data = summaries,
          ggplot2::aes(x = lower, xend = upper, y = group_index, yend = group_index),
          inherit.aes = FALSE, linewidth = 2.2, lineend = "round", color = "#333333") +
        ggplot2::geom_point(data = summaries, ggplot2::aes(x = median, y = group_index),
          inherit.aes = FALSE, shape = 21, size = 2.2, fill = "white") +
        ggplot2::scale_y_continuous(breaks = seq_along(levels(dat$group)), labels = levels(dat$group)) +
        ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::guides(fill = "none") +
        ggplot2::labs(x = value_label, y = NULL))
    }
    return(ggplot2::ggplot(density_data,
      ggplot2::aes(x = group_index + offset, y = value, fill = group, group = group)) +
      ggplot2::geom_polygon(alpha = 0.28, color = NA) +
      ggplot2::geom_boxplot(data = dat, ggplot2::aes(x = group_index - 0.10, y = value, group = group),
        inherit.aes = FALSE, width = 0.16, outlier.shape = NA, fill = "white", linewidth = 0.50) +
      ggplot2::geom_point(data = dat, ggplot2::aes(x = group_index - 0.28, y = value, color = group),
        inherit.aes = FALSE, position = ggplot2::position_jitter(width = 0.04), size = 1.25, alpha = 0.72) +
      ggplot2::scale_x_continuous(breaks = seq_along(levels(dat$group)), labels = levels(dat$group)) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::guides(fill = "none", color = "none") + ggplot2::labs(x = NULL, y = value_label))
  }
  if (recipe_id == "pore-size-distribution") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = value, color = group, fill = group)) +
      ggplot2::geom_density(alpha = 0.16, linewidth = 0.70, adjust = 0.75) +
      ggplot2::scale_x_log10() + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Equivalent pore diameter (log scale)", y = "Density", color = "Group", fill = "Group"))
  }
  NULL
}
register_recipe_override(
  c("density-plot", "violin-plot", "half-violin", "beanplot", "raincloud-plot", "half-eye-plot", "pore-size-distribution"),
  render_domain_distribution
)

render_domain_composition <- function(dat, recipe_id, config) {
  dat$sample_id <- factor(dat$sample_id, levels = unique(dat$sample_id))
  dat$component <- factor(dat$component, levels = unique(dat$component))
  if (recipe_id == "percent-stacked-bar") {
    dat$relative <- 100 * dat$value / ave(dat$value, dat$sample_id, FUN = sum)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = sample_id, y = relative, fill = component)) +
      ggplot2::geom_col(width = 0.70, color = "white", linewidth = 0.28) +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::labs(x = "Sample", y = "Composition (%)", fill = "Component"))
  }
  if (recipe_id == "aggregate-size-composition") {
    dat$component_index <- as.numeric(dat$component)
    return(ggplot2::ggplot(dat,
      ggplot2::aes(x = component_index, y = value, color = group, group = sample_id)) +
      ggplot2::geom_area(ggplot2::aes(fill = group), position = "identity", alpha = 0.10) +
      ggplot2::geom_line(linewidth = 0.65, alpha = 0.80) + ggplot2::geom_point(size = 1.8) +
      ggplot2::scale_x_continuous(breaks = seq_along(levels(dat$component)), labels = levels(dat$component)) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::labs(x = "Aggregate-size fraction", y = "Mass fraction", color = "Treatment", fill = "Treatment"))
  }
  if (recipe_id == "microbiome-composition") {
    dat$relative <- 100 * dat$value / ave(dat$value, dat$sample_id, FUN = sum)
    dat$sample_label <- factor(paste(dat$sample_id, dat$group, sep = " · "), levels = unique(paste(dat$sample_id, dat$group, sep = " · ")))
    return(ggplot2::ggplot(dat, ggplot2::aes(y = sample_label, x = relative, fill = component)) +
      ggplot2::geom_col(width = 0.64, color = "white", linewidth = 0.25) +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::guides(fill = ggplot2::guide_legend(nrow = 1)) +
      ggplot2::theme(legend.position = "bottom") +
      ggplot2::labs(x = "Relative abundance (%)", y = NULL, fill = "Taxonomic group"))
  }
  NULL
}
register_recipe_override(c("percent-stacked-bar", "aggregate-size-composition", "microbiome-composition"), render_domain_composition)

render_domain_spatial_symbols <- function(dat, recipe_id, config) {
  if (recipe_id == "proportional-symbol-map") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y)) +
      ggplot2::geom_tile(fill = "#F3F0E8", color = "white", linewidth = 0.28) +
      ggplot2::geom_point(ggplot2::aes(size = value, fill = class), shape = 21, color = "#333333", alpha = 0.78) +
      ggplot2::scale_size_area(max_size = 8) + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::coord_equal() + ggplot2::labs(x = "Easting", y = "Northing", size = "Value", fill = "Class"))
  }
  if (recipe_id == "dot-density-map") {
    scaled_count <- pmax(1L, round(scales::rescale(dat$value, c(2, 8))))
    dots <- do.call(rbind, lapply(seq_len(nrow(dat)), function(index) {
      count <- scaled_count[index]
      angle <- seq(0, 2 * pi, length.out = count + 1)[seq_len(count)] + index * 0.41
      radius <- 0.08 + 0.18 * sqrt(seq_len(count) / count)
      data.frame(x = dat$x[index] + radius * cos(angle), y = dat$y[index] + radius * sin(angle),
                 class = dat$class[index])
    }))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y)) +
      ggplot2::geom_tile(fill = "#F7F7F2", color = "#D8D8D0", linewidth = 0.25) +
      ggplot2::geom_point(data = dots, ggplot2::aes(x = x, y = y, color = class),
                          inherit.aes = FALSE, size = 0.85, alpha = 0.88) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::coord_equal() +
      ggplot2::labs(x = "Easting", y = "Northing", color = "Class",
                    caption = "Each dot represents an equal share of the mapped value."))
  }
  if (recipe_id == "cartogram") {
    dat$side <- scales::rescale(sqrt(dat$value), c(0.28, 0.78))
    return(ggplot2::ggplot(dat) +
      ggplot2::geom_rect(ggplot2::aes(xmin = x - side / 2, xmax = x + side / 2,
                                     ymin = y - side / 2, ymax = y + side / 2, fill = value),
                         color = "white", linewidth = 0.35) +
      ggplot2::scale_fill_viridis_c(option = "C") + ggplot2::coord_equal() +
      ggplot2::labs(x = "Cartogram column", y = "Cartogram row", fill = "Area-scaled value"))
  }
  if (recipe_id == "vector-field-map") {
    multiplier <- 0.75 / max(sqrt(dat$u^2 + dat$v^2))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y)) +
      ggplot2::geom_tile(ggplot2::aes(fill = value), alpha = 0.36) +
      ggplot2::geom_segment(ggplot2::aes(xend = x + u * multiplier, yend = y + v * multiplier,
                                        linewidth = sqrt(u^2 + v^2)),
        color = "#222222", lineend = "round", arrow = grid::arrow(length = grid::unit(1.25, "mm"))) +
      ggplot2::scale_fill_viridis_c(option = "C") + ggplot2::scale_linewidth(range = c(0.35, 1.0), guide = "none") +
      ggplot2::coord_equal() + ggplot2::labs(x = "Easting", y = "Northing", fill = "Background"))
  }
  if (recipe_id == "flow-map") {
    ordered <- dat[order(dat$y, dat$x), ]
    ordered$stream <- factor(ordered$y)
    return(ggplot2::ggplot(ordered, ggplot2::aes(x = x, y = y, group = stream, color = value)) +
      ggplot2::geom_path(linewidth = 1.4, lineend = "round", arrow = grid::arrow(length = grid::unit(1.6, "mm"))) +
      ggplot2::geom_point(size = 1.2, color = "white") + ggplot2::scale_color_viridis_c(option = "B") +
      ggplot2::coord_equal() + ggplot2::labs(x = "Flow direction", y = "Flow line", color = "Magnitude"))
  }
  if (recipe_id == "scatterbar-map") {
    dat$height <- scales::rescale(dat$value, c(0.15, 0.65))
    return(ggplot2::ggplot(dat) +
      ggplot2::geom_tile(ggplot2::aes(x = x, y = y), fill = "#F5F5F0", color = "white") +
      ggplot2::geom_rect(ggplot2::aes(xmin = x - 0.20, xmax = x + 0.02, ymin = y - 0.32, ymax = y - 0.32 + height),
                         fill = palette_discrete[1], color = "white", linewidth = 0.20) +
      ggplot2::geom_rect(ggplot2::aes(xmin = x + 0.03, xmax = x + 0.22, ymin = y - 0.32,
                                     ymax = y - 0.32 + scales::rescale(uncertainty, c(0.12, 0.50))),
                         fill = palette_discrete[2], color = "white", linewidth = 0.20) +
      ggplot2::coord_equal() + ggplot2::labs(x = "Easting", y = "Northing",
        caption = "Blue bars: value; orange bars: uncertainty."))
  }
  if (recipe_id == "scatterpie-map") {
    dat$signal_share <- dat$value / (dat$value + dat$uncertainty)
    wedges <- do.call(rbind, lapply(seq_len(nrow(dat)), function(index) {
      split_angle <- 2 * pi * dat$signal_share[index]
      make_wedge <- function(start, end, component) {
        angles <- seq(start, end, length.out = max(4L, ceiling(40 * abs(end - start) / (2 * pi))))
        data.frame(x = c(dat$x[index], dat$x[index] + 0.28 * cos(angles), dat$x[index]),
                   y = c(dat$y[index], dat$y[index] + 0.28 * sin(angles), dat$y[index]),
                   component = component, pie_id = paste(index, component, sep = "-"))
      }
      rbind(make_wedge(0, split_angle, "Signal"), make_wedge(split_angle, 2 * pi, "Uncertainty"))
    }))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y)) +
      ggplot2::geom_tile(fill = "#F5F5F0", color = "white") +
      ggplot2::geom_polygon(data = wedges, ggplot2::aes(x = x, y = y, group = pie_id, fill = component),
                            inherit.aes = FALSE, color = "white", linewidth = 0.18) +
      ggplot2::scale_fill_manual(values = c(Signal = palette_discrete[1], Uncertainty = palette_discrete[2])) +
      ggplot2::coord_equal() + ggplot2::labs(x = "Easting", y = "Northing", fill = "Local share"))
  }
  NULL
}
register_recipe_override(
  c("proportional-symbol-map", "dot-density-map", "cartogram", "vector-field-map", "flow-map", "scatterbar-map", "scatterpie-map"),
  render_domain_spatial_symbols
)

render_domain_variogram <- function(dat, recipe_id, config) {
  dat$direction_label <- paste0(dat$direction, "°")
  if (recipe_id == "variogram") {
    pooled <- stats::aggregate(cbind(semivariance, model_semivariance, pairs) ~ lag, dat, mean)
    return(ggplot2::ggplot(pooled, ggplot2::aes(x = lag, y = semivariance)) +
      ggplot2::geom_point(ggplot2::aes(size = pairs), shape = 21, fill = "white", color = palette_discrete[1]) +
      ggplot2::geom_line(ggplot2::aes(y = model_semivariance), linewidth = 0.75, color = palette_discrete[2]) +
      ggplot2::scale_size_area(max_size = 5) + ggplot2::labs(x = "Lag distance", y = "Semivariance", size = "Pairs"))
  }
  if (recipe_id == "directional-variogram") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = lag, y = semivariance, color = direction_label)) +
      ggplot2::geom_line(linewidth = 0.65) + ggplot2::geom_point(ggplot2::aes(size = pairs), alpha = 0.82) +
      ggplot2::geom_line(ggplot2::aes(y = model_semivariance, linetype = direction_label), linewidth = 0.45) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_size_area(max_size = 4) +
      ggplot2::labs(x = "Lag distance", y = "Directional semivariance", color = "Azimuth", linetype = "Model", size = "Pairs"))
  }
  if (recipe_id == "cross-variogram") {
    dat$signed_semivariance <- dat$semivariance * ifelse(dat$direction == min(dat$direction), 1, -1)
    return(ggplot2::ggplot(dat,
      ggplot2::aes(x = lag, y = signed_semivariance, group = direction_label, color = direction_label)) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.35, color = "#777777") +
      ggplot2::geom_ribbon(ggplot2::aes(ymin = 0, ymax = signed_semivariance, fill = direction_label),
                           alpha = 0.12, color = NA) +
      ggplot2::geom_line(linewidth = 0.70) + ggplot2::geom_point(shape = 21, fill = "white", size = 1.8) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::labs(x = "Lag distance", y = "Signed cross-semivariance", color = "Variable pair / azimuth", fill = "Azimuth"))
  }
  NULL
}
register_recipe_override(c("variogram", "directional-variogram", "cross-variogram"), render_domain_variogram)

.set_counts <- function(dat) {
  sets <- unique(dat$set_id)
  presence <- reshape(dat[c("item_id", "set_id", "present")], idvar = "item_id", timevar = "set_id", direction = "wide")
  names(presence) <- sub("present\\.", "", names(presence))
  list(sets = sets, presence = presence)
}

render_domain_sets <- function(dat, recipe_id, config) {
  info <- .set_counts(dat)
  sets <- info$sets[seq_len(min(3L, length(info$sets)))]
  presence <- info$presence
  counts <- vapply(sets, function(set_name) sum(presence[[set_name]] == 1, na.rm = TRUE), numeric(1))
  centers <- data.frame(set = sets, x = c(-0.58, 0.58, 0)[seq_along(sets)],
                        y = c(0.26, 0.26, -0.45)[seq_along(sets)])
  if (recipe_id == "euler-diagram") {
    centers$radius <- scales::rescale(sqrt(counts), c(0.62, 0.88))
    circles <- do.call(rbind, lapply(seq_len(nrow(centers)), function(index) {
      cbind(.circle_vertices(centers$x[index], centers$y[index], centers$radius[index], centers$set[index]),
            set = centers$set[index])
    }))
    return(ggplot2::ggplot(circles, ggplot2::aes(x = x, y = y, group = id, fill = set, color = set)) +
      ggplot2::geom_polygon(alpha = 0.18, linewidth = 0.80) +
      ggplot2::geom_text(data = centers, ggplot2::aes(x = x, y = y, label = paste0(set, "\nn=", counts)),
                         inherit.aes = FALSE, fontface = "bold", lineheight = 0.95) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::guides(fill = "none", color = "none") + ggplot2::coord_equal(xlim = c(-1.7, 1.7), ylim = c(-1.55, 1.45)))
  }
  centers$radius <- 0.92
  circles <- do.call(rbind, lapply(seq_len(nrow(centers)), function(index) {
    cbind(.circle_vertices(centers$x[index], centers$y[index], centers$radius[index], centers$set[index]), set = centers$set[index])
  }))
  if (recipe_id == "venn-diagram") {
    all_count <- if (length(sets) >= 2) sum(rowSums(presence[sets] == 1, na.rm = TRUE) == length(sets)) else counts[1]
    label_positions <- data.frame(set = sets,
      x = c(-0.95, 0.95, 0)[seq_along(sets)], y = c(0.72, 0.72, -1.02)[seq_along(sets)], radius = 0)
    labels <- rbind(label_positions, data.frame(set = "Intersection", x = 0, y = 0.03, radius = 0))
    labels$display <- c(paste0(sets, "\n", counts), paste0("Shared\n", all_count))
    return(ggplot2::ggplot(circles, ggplot2::aes(x = x, y = y, group = id, fill = set, color = set)) +
      ggplot2::geom_polygon(alpha = 0.16, linewidth = 0.75) +
      ggplot2::geom_text(data = labels, ggplot2::aes(x = x, y = y, label = display), inherit.aes = FALSE, lineheight = 0.95) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::guides(fill = "none", color = "none") + ggplot2::coord_equal(xlim = c(-1.7, 1.7), ylim = c(-1.65, 1.45)))
  }
  if (recipe_id == "variation-partition") {
    combinations <- apply(presence[sets] == 1, 1, function(row) paste(sets[row], collapse = " + "))
    fractions <- sort(table(combinations[nzchar(combinations)]), decreasing = TRUE)
    label_data <- data.frame(x = seq(-0.75, 0.75, length.out = min(5, length(fractions))),
                             y = seq(0.70, -0.70, length.out = min(5, length(fractions))),
                             label = paste0(names(fractions)[seq_len(min(5, length(fractions)))], ": ",
                                            as.integer(fractions[seq_len(min(5, length(fractions)))])))
    return(ggplot2::ggplot(circles, ggplot2::aes(x = x, y = y, group = id, fill = set)) +
      ggplot2::geom_polygon(alpha = 0.13, color = "white", linewidth = 0.9) +
      ggplot2::geom_label(data = label_data, ggplot2::aes(x = x, y = y, label = label),
                          inherit.aes = FALSE, size = 1.75, label.size = 0.18, fill = "white") +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::guides(fill = "none") +
      ggplot2::coord_equal(xlim = c(-1.7, 1.7), ylim = c(-1.65, 1.45)))
  }
  NULL
}
register_recipe_override(c("venn-diagram", "euler-diagram", "variation-partition"), render_domain_sets)

render_domain_events <- function(dat, recipe_id, config) {
  dat$subject_id <- factor(dat$subject_id, levels = rev(unique(dat$subject_id)))
  if (recipe_id == "gantt-chart") {
    return(ggplot2::ggplot(dat, ggplot2::aes(y = subject_id, color = group)) +
      ggplot2::geom_segment(ggplot2::aes(x = start, xend = end, yend = subject_id), linewidth = 6, lineend = "butt") +
      ggplot2::geom_text(ggplot2::aes(x = (start + end) / 2, label = label), color = "white", size = 1.75, check_overlap = TRUE) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Study time", y = NULL, color = "Treatment"))
  }
  if (recipe_id == "swimmer-plot") {
    subjects <- stats::aggregate(end ~ subject_id + group, dat, max)
    return(ggplot2::ggplot(subjects, ggplot2::aes(y = subject_id, color = group)) +
      ggplot2::geom_segment(ggplot2::aes(x = 0, xend = end, yend = subject_id), linewidth = 1.8, alpha = 0.60) +
      ggplot2::geom_point(data = dat, ggplot2::aes(x = end, y = subject_id, shape = state),
                          inherit.aes = FALSE, size = 2.1, fill = "white") +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::guides(color = ggplot2::guide_legend(nrow = 1), shape = ggplot2::guide_legend(nrow = 1)) +
      ggplot2::theme(legend.position = "bottom", legend.box = "vertical") +
      ggplot2::labs(x = "Follow-up time", y = NULL, color = "Treatment", shape = "State"))
  }
  if (recipe_id == "lexis-diagram") {
    dat$subject_index <- as.numeric(dat$subject_id)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = start, y = subject_index + start * 0.10, color = group)) +
      ggplot2::geom_segment(ggplot2::aes(xend = end, yend = subject_index + end * 0.10),
                            linewidth = 0.95, arrow = grid::arrow(length = grid::unit(1.2, "mm"))) +
      ggplot2::geom_point(shape = 21, fill = "white", size = 1.8) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Calendar / study time", y = "Attained time (offset by subject)", color = "Treatment"))
  }
  NULL
}
register_recipe_override(c("gantt-chart", "swimmer-plot", "lexis-diagram"), render_domain_events)

render_domain_ecology <- function(dat, recipe_id, config) {
  samples <- stats::aggregate(abundance ~ sample_id + group + effort, dat, sum)
  richness <- stats::aggregate((abundance > 0) ~ sample_id + group + effort, dat, sum)
  names(richness)[4] <- "richness"
  totals <- merge(samples, richness, by = c("sample_id", "group", "effort"))
  totals <- totals[order(totals$group, totals$effort), ]
  if (recipe_id == "species-accumulation") {
    totals$cumulative_richness <- ave(totals$richness, totals$group, FUN = cummax)
    return(ggplot2::ggplot(totals, ggplot2::aes(x = effort, y = cumulative_richness, color = group)) +
      ggplot2::geom_step(linewidth = 0.75, direction = "hv") + ggplot2::geom_point(size = 1.8) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Accumulated sampling effort", y = "Accumulated species richness", color = "Group"))
  }
  if (recipe_id == "rarefaction-curve") {
    totals$individuals <- ave(totals$abundance, totals$group, FUN = cumsum)
    totals$rarefied <- ave(totals$richness, totals$group, FUN = cummax)
    return(ggplot2::ggplot(totals, ggplot2::aes(x = individuals, y = rarefied, color = group)) +
      ggplot2::geom_line(linewidth = 0.75) + ggplot2::geom_point(ggplot2::aes(shape = group), size = 1.8) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Individuals / reads sampled", y = "Observed richness", color = "Group", shape = "Group"))
  }
  if (recipe_id == "coverage-rarefaction") {
    coverage <- do.call(rbind, lapply(split(dat, interaction(dat$sample_id, dat$group, drop = TRUE)), function(part) {
      positive <- part$abundance[part$abundance > 0]
      f1 <- sum(positive == 1)
      total <- sum(positive)
      data.frame(sample_id = part$sample_id[1], group = part$group[1], effort = part$effort[1],
                 richness = sum(positive > 0), coverage = if (total > 0) 1 - f1 / total else NA_real_)
    }))
    coverage <- coverage[order(coverage$group, coverage$coverage), ]
    return(ggplot2::ggplot(coverage, ggplot2::aes(x = coverage, y = richness, color = group)) +
      ggplot2::geom_line(linewidth = 0.72) + ggplot2::geom_point(ggplot2::aes(size = effort), alpha = 0.82) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_size_area(max_size = 4) +
      ggplot2::scale_x_continuous(labels = scales::label_percent(accuracy = 1)) +
      ggplot2::labs(x = "Estimated sample coverage", y = "Richness", color = "Group", size = "Effort"))
  }
  NULL
}
register_recipe_override(c("species-accumulation", "rarefaction-curve", "coverage-rarefaction"), render_domain_ecology)

render_domain_spatial_profile_time <- function(dat, recipe_id, config) {
  dat$time <- factor(dat$time, levels = unique(dat$time))
  dat$slice <- factor(dat$slice, levels = unique(dat$slice))
  if (recipe_id == "depth-slice-maps") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = value)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.28) + ggplot2::facet_wrap(~slice, nrow = 1) +
      ggplot2::scale_fill_viridis_c(option = "C") + ggplot2::coord_equal() +
      ggplot2::labs(x = "Horizontal distance", y = "Transect coordinate", fill = paste0("Value\n(", dat$unit[1], ")")))
  }
  if (recipe_id == "soil-cross-section") {
    depth_mid <- function(text) {
      parts <- as.numeric(strsplit(gsub("[^0-9-]", "", as.character(text)), "-", fixed = TRUE)[[1]])
      if (length(parts) >= 2) mean(parts[1:2]) else suppressWarnings(as.numeric(text))
    }
    depth_map <- setNames(vapply(levels(dat$slice), depth_mid, numeric(1)), levels(dat$slice))
    dat$depth <- depth_map[as.character(dat$slice)]
    if (all(!is.finite(dat$depth))) dat$depth <- as.numeric(dat$slice)
    section <- stats::aggregate(value ~ x + depth, dat, mean)
    return(ggplot2::ggplot(section, ggplot2::aes(x = x, y = depth, fill = value)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.25) +
      ggplot2::geom_line(ggplot2::aes(group = depth), color = "#333333", linewidth = 0.28, alpha = 0.45) +
      ggplot2::scale_fill_viridis_c(option = "C") + ggplot2::scale_y_reverse() +
      ggplot2::labs(x = "Distance along transect", y = "Depth", fill = "Value"))
  }
  if (recipe_id == "hovmoller-diagram") {
    field <- stats::aggregate(value ~ time + y, dat, mean)
    field$time <- factor(field$time, levels = levels(dat$time))
    return(ggplot2::ggplot(field, ggplot2::aes(x = time, y = y, fill = value)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.20) +
      ggplot2::geom_point(ggplot2::aes(size = abs(value - mean(value))), shape = 21,
                          fill = NA, color = "white", stroke = 0.35) +
      ggplot2::scale_size_area(max_size = 4, guide = "none") +
      ggplot2::scale_fill_viridis_c(option = "B") +
      ggplot2::labs(x = "Time", y = "Spatial coordinate", fill = "Field value"))
  }
  if (recipe_id == "soil-moisture-depth-time") {
    summary <- stats::aggregate(value ~ time + slice, dat, mean)
    return(ggplot2::ggplot(summary, ggplot2::aes(x = time, y = slice, fill = value)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.35) +
      ggplot2::geom_text(ggplot2::aes(label = sprintf("%.1f", value)), size = 1.9) +
      ggplot2::scale_fill_viridis_c(option = "C", direction = -1) +
      ggplot2::labs(x = "Time", y = "Soil depth interval", fill = "Moisture"))
  }
  if (recipe_id == "space-time-cube") {
    dat$time_index <- as.numeric(dat$time)
    dat$x_iso <- dat$x + 0.42 * dat$time_index
    dat$y_iso <- dat$y + 0.30 * dat$time_index
    dat$base <- min(dat$value) - 0.12 * diff(range(dat$value))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x_iso, y = value, color = time)) +
      ggplot2::geom_segment(ggplot2::aes(xend = x_iso, y = base, yend = value), alpha = 0.38, linewidth = 0.50) +
      ggplot2::geom_point(ggplot2::aes(size = uncertainty, shape = slice), alpha = 0.88) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::scale_size_area(max_size = 4.5, breaks = pretty(range(dat$uncertainty), n = 3)) +
      ggplot2::guides(color = ggplot2::guide_legend(nrow = 1), shape = ggplot2::guide_legend(nrow = 1),
                      size = ggplot2::guide_legend(nrow = 2)) +
      ggplot2::theme(legend.position = "bottom", legend.box = "vertical") +
      ggplot2::labs(x = "Space–time projected coordinate", y = "Value (vertical dimension)",
                    color = "Time", shape = "Depth", size = "Uncertainty"))
  }
  NULL
}
register_recipe_override(
  c("depth-slice-maps", "soil-cross-section", "hovmoller-diagram", "soil-moisture-depth-time", "space-time-cube"),
  render_domain_spatial_profile_time
)

render_domain_interpretation <- function(dat, recipe_id, config) {
  dat$feature <- factor(dat$feature, levels = unique(dat$feature))
  if (recipe_id == "pdp-plot") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = feature_value, y = effect, color = group, fill = group)) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.30, color = "#777777") +
      ggplot2::geom_ribbon(ggplot2::aes(ymin = lower, ymax = upper), alpha = 0.12, color = NA) +
      ggplot2::geom_line(linewidth = 0.72) + ggplot2::facet_wrap(~feature, scales = "free_x") +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::guides(color = ggplot2::guide_legend(nrow = 1), fill = ggplot2::guide_legend(nrow = 1)) +
      ggplot2::theme(legend.position = "bottom", legend.box = "vertical") +
      ggplot2::labs(x = "Feature value", y = "Average partial dependence", color = "Group", fill = "Interval"))
  }
  if (recipe_id == "ice-plot") {
    dat$centered_effect <- ave(dat$effect, interaction(dat$feature, dat$group), FUN = function(values) values - values[1])
    return(ggplot2::ggplot(dat, ggplot2::aes(x = feature_value, y = centered_effect,
      group = interaction(feature, group), color = group)) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.30, color = "#777777") +
      ggplot2::geom_line(linewidth = 0.62, alpha = 0.78) + ggplot2::geom_point(size = 1.25) +
      ggplot2::facet_wrap(~feature, scales = "free_x") + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Feature value", y = "Centered individual conditional effect", color = "Profile"))
  }
  if (recipe_id == "shap-dependence") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = feature_value, y = effect, color = importance)) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.30, color = "#777777") +
      ggplot2::geom_point(ggplot2::aes(shape = group), size = 1.9, alpha = 0.85) +
      ggplot2::geom_smooth(method = "lm", formula = y ~ x, se = FALSE, linewidth = 0.50, color = "#222222") +
      ggplot2::facet_wrap(~feature, scales = "free_x") + ggplot2::scale_color_viridis_c(option = "C") +
      ggplot2::labs(x = "Feature value", y = "SHAP contribution", color = "Importance", shape = "Group"))
  }
  NULL
}
register_recipe_override(c("pdp-plot", "ice-plot", "shap-dependence"), render_domain_interpretation)

render_domain_temporal <- function(dat, recipe_id, config) {
  dat$group <- factor(dat$group, levels = unique(dat$group))
  value_label <- value_axis_label(dat)
  if (recipe_id == "line-chart") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = time, y = value, color = group, group = subject_id)) +
      ggplot2::geom_line(linewidth = 0.45, alpha = 0.38) + ggplot2::geom_point(size = 1.05, alpha = 0.60) +
      ggplot2::stat_summary(ggplot2::aes(group = group), fun = mean, geom = "line", linewidth = 1.0) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Time", y = value_label, color = "Group"))
  }
  if (recipe_id == "soil-gas-flux-series") {
    summary <- stats::aggregate(cbind(value, lower, upper) ~ time + group, dat, mean)
    return(ggplot2::ggplot(summary, ggplot2::aes(x = time, y = value, color = group, fill = group)) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.30, color = "#777777") +
      ggplot2::geom_ribbon(ggplot2::aes(ymin = lower, ymax = upper), alpha = 0.13, color = NA) +
      ggplot2::geom_line(linewidth = 0.85) + ggplot2::geom_point(size = 1.7) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::labs(x = "Incubation time", y = paste0("Gas flux (", dat$unit[1], ")"), color = "Treatment", fill = "Interval"))
  }
  if (recipe_id == "seasonal-subseries") {
    dat$phase <- factor(seq_len(nrow(dat)) %% 3, labels = c("Early", "Middle", "Late"))
    phase_mean <- stats::aggregate(value ~ phase + group, dat, mean)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = time, y = value, color = group)) +
      ggplot2::geom_line(ggplot2::aes(group = subject_id), linewidth = 0.42, alpha = 0.55) +
      ggplot2::geom_hline(data = phase_mean, ggplot2::aes(yintercept = value, color = group), linewidth = 0.75) +
      ggplot2::facet_wrap(~phase, scales = "free_x") + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Within-season time", y = value_label, color = "Group"))
  }
  grouped <- stats::aggregate(value ~ time + group, dat, mean)
  if (recipe_id == "stacked-area") {
    return(ggplot2::ggplot(grouped, ggplot2::aes(x = time, y = value, fill = group)) +
      ggplot2::geom_area(position = "stack", alpha = 0.82, color = "white", linewidth = 0.28) +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::labs(x = "Time", y = "Stacked mean value", fill = "Group"))
  }
  if (recipe_id == "streamgraph") {
    grouped <- grouped[order(grouped$time, grouped$group), ]
    grouped$total <- ave(grouped$value, grouped$time, FUN = sum)
    grouped$upper <- ave(grouped$value, grouped$time, FUN = cumsum) - grouped$total / 2
    grouped$lower <- grouped$upper - grouped$value
    return(ggplot2::ggplot(grouped, ggplot2::aes(x = time, ymin = lower, ymax = upper, fill = group, group = group)) +
      ggplot2::geom_ribbon(alpha = 0.78, color = "white", linewidth = 0.20) +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.25, color = "#777777") +
      ggplot2::scale_y_continuous(labels = NULL, breaks = NULL) +
      ggplot2::labs(x = "Time", y = "Centered stream thickness", fill = "Group"))
  }
  NULL
}
register_recipe_override(c("line-chart", "soil-gas-flux-series", "seasonal-subseries", "stacked-area", "streamgraph"), render_domain_temporal)

.ternary_xy <- function(dat) {
  total <- dat$part_a + dat$part_b + dat$part_c
  data.frame(dat, tx = (dat$part_b + 0.5 * dat$part_c) / total,
             ty = sqrt(3) / 2 * dat$part_c / total,
             a_share = dat$part_a / total, b_share = dat$part_b / total, c_share = dat$part_c / total)
}

.ternary_frame <- function() {
  rbind(data.frame(x = c(0, 1, 0.5, 0), y = c(0, 0, sqrt(3) / 2, 0), type = "boundary"),
        data.frame(x = numeric(0), y = numeric(0), type = character(0)))
}

render_domain_ternary <- function(dat, recipe_id, config) {
  points <- .ternary_xy(dat)
  frame <- .ternary_frame()
  grid_values <- c(0.25, 0.50, 0.75)
  grid_lines <- do.call(rbind, lapply(grid_values, function(value) {
    rbind(
      data.frame(x = c(value, 1 - value / 2), y = c(0, value * sqrt(3) / 2), grid = paste0("a", value)),
      data.frame(x = c(1 - value, value / 2), y = c(0, value * sqrt(3) / 2), grid = paste0("b", value)),
      data.frame(x = c(value / 2, 1 - value / 2), y = rep(value * sqrt(3) / 2, 2), grid = paste0("c", value))
    )
  }))
  base <- ggplot2::ggplot() +
    ggplot2::geom_path(data = frame, ggplot2::aes(x = x, y = y), linewidth = 0.75, color = "#222222") +
    ggplot2::geom_line(data = grid_lines, ggplot2::aes(x = x, y = y, group = grid), linewidth = 0.28, color = "#D8D8D8") +
    ggplot2::annotate("text", x = -0.035, y = -0.035, label = "A", hjust = 1, fontface = "bold") +
    ggplot2::annotate("text", x = 1.035, y = -0.035, label = "B", hjust = 0, fontface = "bold") +
    ggplot2::annotate("text", x = 0.5, y = sqrt(3) / 2 + 0.045, label = "C", fontface = "bold")
  if (recipe_id == "ternary-plot") {
    return(base + ggplot2::geom_point(data = points, ggplot2::aes(x = tx, y = ty, fill = group),
      shape = 21, size = 2.3, color = "white", stroke = 0.45) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::coord_equal(clip = "off") +
      ggplot2::labs(fill = "Group"))
  }
  if (recipe_id == "ternary-response") {
    points$response <- 0.45 * points$a_share + 0.30 * points$b_share + 0.25 * points$c_share
    return(base + ggplot2::geom_point(data = points, ggplot2::aes(x = tx, y = ty, color = response, size = response), alpha = 0.90) +
      ggplot2::scale_color_viridis_c(option = "C", breaks = pretty(range(points$response), n = 3)) +
      ggplot2::scale_size_area(max_size = 5, breaks = pretty(range(points$response), n = 3)) +
      ggplot2::guides(size = "none", color = ggplot2::guide_colorbar(barwidth = grid::unit(23, "mm"))) +
      ggplot2::theme(legend.position = "bottom") +
      ggplot2::coord_equal(clip = "off") + ggplot2::labs(color = "Response", size = "Response"))
  }
  if (recipe_id == "soil-texture-triangle") {
    zones <- data.frame(x = c(0.17, 0.50, 0.82, 0.50), y = c(0.15, 0.17, 0.15, 0.61),
                        label = c("Clay-rich", "Loam", "Sand-rich", "Fine-textured"))
    return(base + ggplot2::geom_point(data = points, ggplot2::aes(x = tx, y = ty, fill = group),
      shape = 21, size = 2.2, color = "#222222") +
      ggplot2::geom_label(data = zones, ggplot2::aes(x = x, y = y, label = label),
                          size = 1.65, label.size = 0.18, fill = scales::alpha("white", 0.78)) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::coord_equal(clip = "off") +
      ggplot2::labs(fill = "Sample group", caption = "Broad texture zones; apply the target classification standard before inference."))
  }
  NULL
}
register_recipe_override(c("ternary-plot", "ternary-response", "soil-texture-triangle"), render_domain_ternary)

render_domain_funnel <- function(dat, recipe_id, config) {
  center <- weighted.mean(dat$effect, 1 / dat$variance, na.rm = TRUE)
  se_grid <- seq(0, max(dat$se) * 1.12, length.out = 120)
  bounds <- data.frame(se = se_grid, lower = center - 1.96 * se_grid, upper = center + 1.96 * se_grid)
  base <- ggplot2::ggplot(dat, ggplot2::aes(x = effect, y = se, color = moderator)) +
    ggplot2::geom_vline(xintercept = center, linewidth = 0.45, color = "#444444") +
    ggplot2::geom_line(data = bounds, ggplot2::aes(x = lower, y = se), inherit.aes = FALSE,
                       linewidth = 0.50, linetype = 2, color = "#555555") +
    ggplot2::geom_line(data = bounds, ggplot2::aes(x = upper, y = se), inherit.aes = FALSE,
                       linewidth = 0.50, linetype = 2, color = "#555555") +
    ggplot2::geom_point(ggplot2::aes(size = 1 / variance), alpha = 0.82) +
    ggplot2::scale_y_reverse() + ggplot2::scale_color_manual(values = palette_discrete) +
    ggplot2::scale_size_area(max_size = 5, guide = "none") +
    ggplot2::labs(x = "Study effect", y = "Standard error", color = "Moderator")
  if (recipe_id == "funnel-plot") return(base)
  band_polygon <- function(inner, outer, side, band) {
    data.frame(
      x = c(center + side * inner * se_grid, rev(center + side * outer * se_grid)),
      y = c(se_grid, rev(se_grid)), band = band,
      side = if (side < 0) "left" else "right"
    )
  }
  significance <- rbind(
    band_polygon(1.96, 3.29, -1, "0.001 ≤ p < 0.05"),
    band_polygon(1.96, 3.29, 1, "0.001 ≤ p < 0.05"),
    band_polygon(3.29, 4.4, -1, "p < 0.001"),
    band_polygon(3.29, 4.4, 1, "p < 0.001")
  )
  return(ggplot2::ggplot() +
    ggplot2::geom_polygon(data = significance,
      ggplot2::aes(x = x, y = y, group = interaction(band, side), fill = band), alpha = 0.55, color = NA) +
    ggplot2::geom_line(data = bounds, ggplot2::aes(x = lower, y = se), linewidth = 0.45, linetype = 2) +
    ggplot2::geom_line(data = bounds, ggplot2::aes(x = upper, y = se), linewidth = 0.45, linetype = 2) +
    ggplot2::geom_point(data = dat, ggplot2::aes(x = effect, y = se, fill = moderator), shape = 21, size = 2.2) +
    ggplot2::geom_vline(xintercept = center, linewidth = 0.45) +
    ggplot2::scale_fill_manual(values = c("0.001 ≤ p < 0.05" = "#D9EDF7", "p < 0.001" = "#B3D7E8",
                                         Arid = palette_discrete[1], Temperate = palette_discrete[2], Tropical = palette_discrete[3])) +
    ggplot2::scale_y_reverse() +
    ggplot2::guides(fill = ggplot2::guide_legend(nrow = 2)) + ggplot2::theme(legend.position = "bottom") +
    ggplot2::labs(x = "Study effect", y = "Standard error", fill = "Contour / moderator",
                  caption = "Dashed contours denote the conventional 95% funnel limits."))
}
register_recipe_override(c("funnel-plot", "contour-enhanced-funnel"), render_domain_funnel)

render_domain_genomic <- function(dat, recipe_id, config) {
  dat$chromosome <- factor(dat$chromosome, levels = unique(dat$chromosome))
  dat$chromosome_index <- as.numeric(dat$chromosome)
  if (recipe_id == "genome-track") {
    segments <- dat[dat$start != dat$end, , drop = FALSE]
    variants <- dat[dat$start == dat$end, , drop = FALSE]
    return(ggplot2::ggplot() +
      ggplot2::geom_segment(data = segments,
        ggplot2::aes(x = start, xend = end, y = chromosome_index, yend = chromosome_index,
                     color = group, linewidth = abs(value)), lineend = "round") +
      ggplot2::geom_point(data = variants,
        ggplot2::aes(x = start, y = chromosome_index, fill = group, size = -log10(p_value)),
        shape = 21, color = "white") +
      ggplot2::scale_y_continuous(breaks = seq_along(levels(dat$chromosome)), labels = paste0("Chr ", levels(dat$chromosome))) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::scale_linewidth(range = c(1.2, 5), guide = "none") +
      ggplot2::scale_size_area(max_size = 5, breaks = pretty(range(-log10(dat$p_value)), n = 3)) +
      ggplot2::guides(color = ggplot2::guide_legend(nrow = 1), fill = ggplot2::guide_legend(nrow = 1),
                      size = ggplot2::guide_legend(nrow = 1)) +
      ggplot2::theme(legend.position = "bottom", legend.box = "vertical") +
      ggplot2::labs(x = "Genomic coordinate (bp)", y = NULL, color = "Segment group", fill = "Variant group", size = expression(-log[10](p))))
  }
  if (recipe_id == "copy-number-segment") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = start, xend = end, y = value, yend = value, color = group)) +
      ggplot2::geom_hline(yintercept = 0, color = "#777777", linewidth = 0.30) +
      ggplot2::geom_segment(linewidth = 2.2, lineend = "butt") +
      ggplot2::geom_point(data = dat[dat$start == dat$end, , drop = FALSE],
                          ggplot2::aes(x = start, y = value, fill = group), shape = 21, size = 2.0) +
      ggplot2::facet_wrap(~chromosome, scales = "free_x", nrow = 1) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::labs(x = "Genomic coordinate (bp)", y = "Copy-number log ratio", color = "Group", fill = "Group"))
  }
  NULL
}
register_recipe_override(c("genome-track", "copy-number-segment"), render_domain_genomic)

render_domain_spectral <- function(dat, recipe_id, config) {
  dat <- dat[order(dat$sample_id, dat$wavelength_nm), ]
  if (recipe_id == "spectral-signature") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = wavelength_nm, y = value, color = group, group = sample_id)) +
      ggplot2::geom_line(linewidth = 0.82) + ggplot2::geom_point(size = 1.2) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Wavelength (nm)", y = dat$unit[1], color = "Sample group"))
  }
  if (recipe_id == "derivative-spectrum") {
    pieces <- lapply(split(dat, dat$sample_id), function(part) {
      part$derivative <- c(NA_real_, diff(part$value) / diff(part$wavelength_nm))
      part
    })
    derivative <- do.call(rbind, pieces)
    derivative <- derivative[is.finite(derivative$derivative), , drop = FALSE]
    return(ggplot2::ggplot(derivative, ggplot2::aes(x = wavelength_nm, y = derivative, color = group, group = sample_id)) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.30, color = "#777777") +
      ggplot2::geom_line(linewidth = 0.78) + ggplot2::geom_point(size = 1.2) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Wavelength (nm)", y = "First derivative of spectral value", color = "Sample group"))
  }
  NULL
}
register_recipe_override(c("spectral-signature", "derivative-spectrum"), render_domain_spectral)

render_domain_population_flow <- function(dat, recipe_id, config) {
  dat$stage <- as.numeric(dat$stage)
  dat <- dat[order(dat$stage, dat$group), ]
  if (recipe_id == "muller-plot") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = stage, y = value, fill = group)) +
      ggplot2::geom_area(position = "stack", alpha = 0.82, color = "white", linewidth = 0.32) +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::labs(x = "Generation / stage", y = "Population abundance", fill = "Population"))
  }
  if (recipe_id == "fishplot") {
    totals <- stats::aggregate(value ~ stage, dat, sum)
    names(totals)[2] <- "total"
    dat <- merge(dat, totals, by = "stage")
    dat$half_value <- dat$value / 2
    return(ggplot2::ggplot(dat, ggplot2::aes(x = stage, y = half_value, fill = group)) +
      ggplot2::geom_area(position = "stack", alpha = 0.76, color = "white", linewidth = 0.28) +
      ggplot2::geom_area(ggplot2::aes(y = -half_value), position = "stack", alpha = 0.76, color = "white", linewidth = 0.28) +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::scale_y_continuous(labels = function(values) abs(values)) +
      ggplot2::labs(x = "Evolutionary stage", y = "Symmetric clone abundance", fill = "Clone"))
  }
  NULL
}
register_recipe_override(c("fishplot", "muller-plot"), render_domain_population_flow)

render_domain_polar <- function(dat, recipe_id, config) {
  dat$direction <- factor(dat$direction_deg, levels = sort(unique(dat$direction_deg)))
  if (recipe_id == "wind-rose") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = direction, y = frequency, fill = speed)) +
      ggplot2::geom_col(width = 0.92, color = "white", linewidth = 0.25) +
      ggplot2::coord_polar(start = -pi / 8) + ggplot2::scale_fill_viridis_c(option = "C") +
      ggplot2::labs(x = NULL, y = "Frequency (%)", fill = "Speed"))
  }
  if (recipe_id == "polar-annulus") {
    dat$inner <- scales::rescale(dat$speed, c(1.0, 2.2))
    dat$outer <- dat$inner + scales::rescale(dat$pollutant, c(0.35, 0.85))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = direction, ymin = inner, ymax = outer, fill = pollutant)) +
      ggplot2::geom_rect(ggplot2::aes(xmin = as.numeric(direction) - 0.46, xmax = as.numeric(direction) + 0.46),
                         color = "white", linewidth = 0.25) +
      ggplot2::coord_polar(start = -pi / 8) + ggplot2::scale_fill_viridis_c(option = "B") +
      ggplot2::ylim(0, max(dat$outer) * 1.08) +
      ggplot2::labs(x = NULL, y = NULL, fill = "Pollutant",
                    caption = "Annulus radius encodes wind speed; thickness encodes pollutant level."))
  }
  NULL
}
register_recipe_override(c("wind-rose", "polar-annulus"), render_domain_polar)

.wide_multivariate <- function(dat) {
  wide <- reshape(dat[c("sample_id", "variable", "value", "group")], idvar = c("sample_id", "group"),
                  timevar = "variable", direction = "wide")
  variables <- sub("^value\\.", "", grep("^value\\.", names(wide), value = TRUE))
  value_columns <- paste0("value.", variables)
  scaled <- as.data.frame(scale(wide[value_columns]))
  scaled[!is.finite(as.matrix(scaled))] <- 0
  names(scaled) <- variables
  cbind(wide[c("sample_id", "group")], scaled)
}

render_domain_radial_multivariate <- function(dat, recipe_id, config) {
  wide <- .wide_multivariate(dat)
  variables <- setdiff(names(wide), c("sample_id", "group"))
  angle <- seq(0, 2 * pi, length.out = length(variables) + 1)[seq_along(variables)]
  if (recipe_id == "radar-chart") {
    means <- stats::aggregate(wide[variables], by = list(group = wide$group), mean)
    polygons <- do.call(rbind, lapply(seq_len(nrow(means)), function(index) {
      radius <- scales::rescale(as.numeric(means[index, variables]), c(0.28, 0.95), from = range(as.matrix(means[variables])))
      data.frame(x = c(radius * cos(angle), radius[1] * cos(angle[1])),
                 y = c(radius * sin(angle), radius[1] * sin(angle[1])),
                 variable = c(variables, variables[1]), group = means$group[index])
    }))
    axes <- data.frame(x = 0, y = 0, xend = cos(angle), yend = sin(angle), variable = variables)
    labels <- data.frame(x = 1.12 * cos(angle), y = 1.12 * sin(angle), variable = variables)
    return(ggplot2::ggplot() +
      ggplot2::geom_segment(data = axes, ggplot2::aes(x = x, y = y, xend = xend, yend = yend), color = "#D0D0D0") +
      ggplot2::geom_polygon(data = polygons, ggplot2::aes(x = x, y = y, group = group, fill = group), alpha = 0.14) +
      ggplot2::geom_path(data = polygons, ggplot2::aes(x = x, y = y, group = group, color = group), linewidth = 0.75) +
      ggplot2::geom_text(data = labels, ggplot2::aes(x = x, y = y, label = variable), size = 1.8) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::coord_equal(xlim = c(-1.35, 1.35), ylim = c(-1.25, 1.25)) +
      ggplot2::labs(fill = "Group", color = "Group"))
  }
  if (recipe_id == "star-glyph") {
    glyphs <- do.call(rbind, lapply(seq_len(nrow(wide)), function(index) {
      radius <- scales::rescale(as.numeric(wide[index, variables]), c(0.15, 0.92))
      data.frame(x = c(radius * cos(angle), radius[1] * cos(angle[1])),
                 y = c(radius * sin(angle), radius[1] * sin(angle[1])),
                 variable = c(variables, variables[1]), sample_id = wide$sample_id[index], group = wide$group[index])
    }))
    return(ggplot2::ggplot(glyphs, ggplot2::aes(x = x, y = y, group = sample_id, color = group)) +
      ggplot2::geom_polygon(ggplot2::aes(fill = group), alpha = 0.16, linewidth = 0.55) +
      ggplot2::geom_point(size = 1.0) + ggplot2::facet_wrap(~sample_id) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::coord_equal() + ggplot2::labs(x = NULL, y = NULL, color = "Group", fill = "Group"))
  }
  NULL
}
register_recipe_override(c("radar-chart", "star-glyph"), render_domain_radial_multivariate)

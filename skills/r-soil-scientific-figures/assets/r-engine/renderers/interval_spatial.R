# Effect/interval and spatial-grid variants.

render_advanced_interval <- function(dat, recipe_id, config) {
  if (!"group" %in% names(dat)) dat$group <- "Estimate"
  dat$order_index <- seq_len(nrow(dat))
  dat$sign <- ifelse(dat$lower > 0, "Positive", ifelse(dat$upper < 0, "Negative", "Crosses reference"))
  sign_colors <- c(Positive = "#D55E00", Negative = "#0072B2", `Crosses reference` = "#7F7F7F")

  if (recipe_id == "caterpillar-plot") {
    dat <- dat[order(dat$estimate), , drop = FALSE]
    dat$label <- factor(dat$label, levels = dat$label)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = estimate, y = label, color = sign)) +
      ggplot2::geom_vline(xintercept = 0, linetype = 2, linewidth = 0.35) +
      ggplot2::geom_errorbarh(ggplot2::aes(xmin = lower, xmax = upper), height = 0, linewidth = 0.55) +
      ggplot2::geom_point(size = 2.1) +
      ggplot2::scale_color_manual(values = sign_colors) +
      ggplot2::labs(x = "Ordered estimate and interval", y = NULL, color = "Direction"))
  }
  if (recipe_id == "interval-dotplot") {
    dat$label <- factor(dat$label, levels = unique(dat$label))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = label, y = estimate, color = group)) +
      ggplot2::geom_hline(yintercept = 0, linetype = 2, linewidth = 0.35) +
      ggplot2::geom_errorbar(ggplot2::aes(ymin = lower, ymax = upper), width = 0.10, linewidth = 0.50) +
      ggplot2::geom_point(size = 2.0) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = NULL, y = "Estimate and interval", color = "Group"))
  }
  if (recipe_id == "specification-curve") {
    dat <- dat[order(dat$estimate), , drop = FALSE]
    dat$specification <- seq_len(nrow(dat))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = specification, y = estimate, color = group)) +
      ggplot2::geom_hline(yintercept = 0, linetype = 2, linewidth = 0.35) +
      ggplot2::geom_linerange(ggplot2::aes(ymin = lower, ymax = upper), linewidth = 0.48) +
      ggplot2::geom_point(ggplot2::aes(shape = sign), size = 2.0) +
      ggplot2::geom_rug(sides = "b", alpha = 0.65) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::scale_shape_manual(values = c(Positive = 16, Negative = 17, `Crosses reference` = 1)) +
      ggplot2::labs(x = "Ordered specification", y = "Estimate", color = "Model family", shape = "Interval"))
  }
  if (recipe_id == "multiverse-plot") {
    dat$label <- factor(dat$label, levels = rev(unique(dat$label)))
    return(ggplot2::ggplot(dat, ggplot2::aes(y = label, color = group)) +
      ggplot2::geom_vline(xintercept = 0, linetype = 2, linewidth = 0.35) +
      ggplot2::geom_segment(ggplot2::aes(x = lower, xend = upper, yend = label), linewidth = 3.0, alpha = 0.18) +
      ggplot2::geom_point(ggplot2::aes(x = estimate), size = 2.0) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Estimate across analysis universe", y = NULL, color = "Universe"))
  }
  if (recipe_id == "vibration-of-effects") {
    dat$label <- factor(dat$label, levels = unique(dat$label))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = estimate, y = group, color = sign)) +
      ggplot2::geom_vline(xintercept = 0, linetype = 2, linewidth = 0.35) +
      ggplot2::geom_segment(ggplot2::aes(x = lower, xend = upper, yend = group), alpha = 0.42, linewidth = 0.55) +
      ggplot2::geom_point(ggplot2::aes(size = upper - lower), alpha = 0.82) +
      ggplot2::scale_color_manual(values = sign_colors) +
      ggplot2::scale_size_continuous(trans = "reverse", range = c(1.4, 3.2), guide = "none") +
      ggplot2::labs(x = "Effect vibration", y = "Analysis family", color = "Direction"))
  }
  if (recipe_id == "permanova-effect-plot") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = estimate, y = reorder(label, estimate), color = group)) +
      ggplot2::geom_vline(xintercept = 0, linetype = 2, linewidth = 0.35) +
      ggplot2::geom_errorbarh(ggplot2::aes(xmin = lower, xmax = upper), height = 0.14, linewidth = 0.50) +
      ggplot2::geom_point(ggplot2::aes(size = abs(estimate)), shape = 21, fill = "white", stroke = 0.7) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::scale_size_area(max_size = 4.5, guide = "none") +
      ggplot2::labs(x = "PERMANOVA effect / contrast", y = NULL, color = "Term class"))
  }
  if (recipe_id == "differential-abundance-effect") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = estimate, y = reorder(label, abs(estimate)), color = sign)) +
      ggplot2::geom_vline(xintercept = 0, linetype = 2, linewidth = 0.35) +
      ggplot2::geom_segment(ggplot2::aes(x = 0, xend = estimate, yend = reorder(label, abs(estimate))), linewidth = 1.3, alpha = 0.28) +
      ggplot2::geom_errorbarh(ggplot2::aes(xmin = lower, xmax = upper), height = 0.13, linewidth = 0.48) +
      ggplot2::geom_point(size = 2.1) +
      ggplot2::scale_color_manual(values = sign_colors) +
      ggplot2::labs(x = "Differential-abundance effect", y = NULL, color = "Direction"))
  }
  if (recipe_id == "spectral-coefficient-plot") {
    dat$index <- seq_len(nrow(dat))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = index, y = estimate, color = group, group = group)) +
      ggplot2::geom_hline(yintercept = 0, linewidth = 0.35) +
      ggplot2::geom_ribbon(ggplot2::aes(ymin = lower, ymax = upper, fill = group), color = NA, alpha = 0.12) +
      ggplot2::geom_line(linewidth = 0.70) + ggplot2::geom_point(size = 1.45) +
      ggplot2::scale_color_manual(values = palette_discrete) + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::scale_x_continuous(breaks = dat$index, labels = dat$label) +
      ggplot2::labs(x = "Wavelength / coefficient index", y = "Coefficient", color = "Series", fill = "Series"))
  }
  NULL
}

register_recipe_override(
  c("caterpillar-plot", "interval-dotplot", "specification-curve", "multiverse-plot",
    "vibration-of-effects", "permanova-effect-plot", "differential-abundance-effect",
    "spectral-coefficient-plot"),
  render_advanced_interval
)

grid_derivatives <- function(dat) {
  dat <- dat[order(dat$y, dat$x), , drop = FALSE]
  x_values <- sort(unique(dat$x))
  y_values <- sort(unique(dat$y))
  matrix_value <- matrix(NA_real_, nrow = length(y_values), ncol = length(x_values))
  matrix_value[cbind(match(dat$y, y_values), match(dat$x, x_values))] <- dat$value
  dx <- t(apply(matrix_value, 1, function(z) c(diff(z), tail(diff(z), 1))))
  dy <- apply(matrix_value, 2, function(z) c(diff(z), tail(diff(z), 1)))
  dat$gradient_x <- dx[cbind(match(dat$y, y_values), match(dat$x, x_values))]
  dat$gradient_y <- dy[cbind(match(dat$y, y_values), match(dat$x, x_values))]
  dat$slope <- sqrt(dat$gradient_x^2 + dat$gradient_y^2)
  dat$aspect <- atan2(dat$gradient_y, dat$gradient_x)
  dat
}

render_advanced_spatial <- function(dat, recipe_id, config) {
  if (!"uncertainty" %in% names(dat)) dat$uncertainty <- abs(dat$value - mean(dat$value, na.rm = TRUE))
  dat <- grid_derivatives(dat)
  base_equal <- ggplot2::coord_equal(expand = FALSE)
  sequential <- ggplot2::scale_fill_viridis_c(option = "C")

  if (recipe_id == "choropleth-map") {
    dat$zone <- cut(dat$value, breaks = stats::quantile(dat$value, seq(0, 1, length.out = 6)), include.lowest = TRUE)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = zone)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.45) + base_equal +
      ggplot2::scale_fill_viridis_d(option = "C", end = 0.9) +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Mapped class"))
  }
  if (recipe_id == "raster-map") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = value)) +
      ggplot2::geom_raster(interpolate = FALSE) + base_equal + sequential +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Value"))
  }
  if (recipe_id == "hillshade-map") {
    illumination <- cos(pi / 4) * cos(atan(dat$slope)) +
      sin(pi / 4) * sin(atan(dat$slope)) * cos(dat$aspect - 315 * pi / 180)
    dat$hillshade <- scales::rescale(illumination)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = hillshade)) +
      ggplot2::geom_raster() + base_equal +
      ggplot2::scale_fill_gradient(low = "#202020", high = "#F2F2F2") +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Illumination"))
  }
  if (recipe_id == "terrain-map") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = value)) +
      ggplot2::geom_raster() +
      ggplot2::geom_contour(data = dat, ggplot2::aes(x = x, y = y, z = value), inherit.aes = FALSE,
                            color = "white", linewidth = 0.32, bins = 6) +
      base_equal + ggplot2::scale_fill_viridis_c(option = "D") +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Elevation"))
  }
  if (recipe_id == "slope-aspect-map") {
    dat$aspect_class <- cut(dat$aspect, breaks = seq(-pi, pi, length.out = 9), include.lowest = TRUE)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = aspect_class, alpha = slope)) +
      ggplot2::geom_tile() + base_equal + ggplot2::scale_fill_viridis_d(option = "H") +
      ggplot2::scale_alpha(range = c(0.35, 1)) +
      ggplot2::guides(alpha = ggplot2::guide_legend(order = 2), fill = ggplot2::guide_legend(order = 1, nrow = 2)) +
      ggplot2::theme(legend.box = "vertical") +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Aspect", alpha = "Slope"))
  }
  if (recipe_id == "kernel-density-map") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, z = value)) +
      ggplot2::stat_contour_filled(bins = 5) +
      ggplot2::geom_point(ggplot2::aes(size = scales::rescale(value)), shape = 21, fill = "white", alpha = 0.45) +
      base_equal + ggplot2::scale_fill_viridis_d(option = "C") +
      ggplot2::scale_size(range = c(0.4, 2.2), guide = "none") +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Smoothed level"))
  }
  if (recipe_id == "filled-contour-map") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, z = value)) +
      ggplot2::stat_contour_filled(bins = 5) + base_equal +
      ggplot2::scale_fill_viridis_d(option = "C") +
      ggplot2::guides(fill = ggplot2::guide_legend(nrow = 2, byrow = TRUE)) +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Filled level"))
  }
  if (recipe_id == "hotspot-map") {
    dat$z_score <- as.numeric(scale(dat$value))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = z_score)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.25) +
      ggplot2::geom_point(data = dat[abs(dat$z_score) >= 1, ], shape = 21, fill = NA, size = 3.1, stroke = 0.7) +
      base_equal + ggplot2::scale_fill_gradient2(low = "#2166AC", mid = "white", high = "#B2182B", midpoint = 0) +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Local z-score"))
  }
  if (recipe_id == "prediction-map") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = value)) +
      ggplot2::geom_raster() +
      ggplot2::geom_contour(data = dat, ggplot2::aes(x = x, y = y, z = value), inherit.aes = FALSE,
                            color = "white", linewidth = 0.32) +
      base_equal + sequential + ggplot2::labs(x = "Easting", y = "Northing", fill = "Prediction"))
  }
  if (recipe_id == "uncertainty-map") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = uncertainty)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.20) + base_equal +
      ggplot2::scale_fill_viridis_c(option = "B", direction = -1) +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Uncertainty"))
  }
  if (recipe_id == "residual-map") {
    dat$residual <- dat$value - mean(dat$value, na.rm = TRUE)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = residual)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.20) + base_equal +
      ggplot2::scale_fill_gradient2(low = "#2166AC", mid = "white", high = "#B2182B", midpoint = 0) +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Residual"))
  }
  if (recipe_id == "applicability-domain-map") {
    threshold <- stats::quantile(dat$uncertainty, 0.75, na.rm = TRUE)
    dat$domain <- factor(ifelse(dat$uncertainty <= threshold, "Inside domain", "Extrapolation"))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = domain)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.25) + base_equal +
      ggplot2::scale_fill_manual(values = c(`Inside domain` = "#009E73", Extrapolation = "#D55E00")) +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Applicability"))
  }
  if (recipe_id == "spatial-cv-map") {
    dat$fold <- factor((rank(dat$x + dat$y, ties.method = "first") - 1) %% 4 + 1)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = fold)) +
      ggplot2::geom_tile(color = "white", linewidth = 0.45) + base_equal +
      ggplot2::scale_fill_viridis_d(option = "D") +
      ggplot2::labs(x = "Easting", y = "Northing", fill = "Spatial fold"))
  }
  NULL
}

register_recipe_override(
  c("choropleth-map", "raster-map", "hillshade-map", "terrain-map", "slope-aspect-map",
    "kernel-density-map", "filled-contour-map", "hotspot-map", "prediction-map", "uncertainty-map", "residual-map",
    "applicability-domain-map", "spatial-cv-map"),
  render_advanced_spatial
)

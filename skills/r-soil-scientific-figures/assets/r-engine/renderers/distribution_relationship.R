# Distribution, relationship and process-curve variants.

deterministic_offsets <- function(values, maximum = 0.28, phase = 0) {
  count <- length(values)
  if (count <= 1) return(rep(0, count))
  order_index <- rank(values, ties.method = "first")
  maximum * sin((order_index + phase) * pi * (sqrt(5) - 1))
}

render_advanced_distribution <- function(dat, recipe_id, config) {
  dat$group <- factor(dat$group, levels = unique(dat$group))
  dat$group_index <- as.numeric(dat$group)
  split_index <- split(seq_len(nrow(dat)), dat$group)

  if (recipe_id == "beeswarm-plot") {
    dat$bin <- ave(dat$value, dat$group, FUN = function(x) as.integer(cut(x, 8, labels = FALSE)))
    dat$stack <- ave(seq_len(nrow(dat)), interaction(dat$group, dat$bin), FUN = function(x) seq_along(x))
    dat$stack_center <- ave(dat$stack, interaction(dat$group, dat$bin), FUN = function(x) (max(x) + 1) / 2)
    dat$x_plot <- dat$group_index + (dat$stack - dat$stack_center) * 0.075
  } else if (recipe_id == "quasirandom-plot") {
    dat$x_plot <- dat$group_index
    for (index in split_index) dat$x_plot[index] <- dat$group_index[index] + deterministic_offsets(dat$value[index], 0.26)
  } else if (recipe_id == "sina-plot") {
    dat$x_plot <- dat$group_index
    for (index in split_index) {
      density_fit <- stats::density(dat$value[index], n = 256)
      local_density <- stats::approx(density_fit$x, density_fit$y, xout = dat$value[index], rule = 2)$y
      local_density <- local_density / max(local_density)
      dat$x_plot[index] <- dat$group_index[index] + deterministic_offsets(dat$value[index], 0.30) * local_density
    }
  } else if (recipe_id == "dotplot-stacked") {
    dat$bin <- ave(dat$value, dat$group, FUN = function(x) {
      width <- max(diff(range(x)) / 10, .Machine$double.eps)
      round(x / width) * width
    })
    dat$stack <- ave(seq_len(nrow(dat)), interaction(dat$group, dat$bin), FUN = seq_along)
    dat$x_plot <- dat$group_index + (dat$stack - 1) * 0.055
  } else {
    return(NULL)
  }

  summaries <- do.call(rbind, lapply(split(dat$value, dat$group), function(x) data.frame(
    median = stats::median(x), q1 = unname(stats::quantile(x, 0.25)), q3 = unname(stats::quantile(x, 0.75))
  )))
  summaries$group <- factor(rownames(summaries), levels = levels(dat$group))
  ggplot2::ggplot(dat, ggplot2::aes(x = x_plot, y = value, color = group)) +
    ggplot2::geom_segment(
      data = summaries,
      ggplot2::aes(x = as.numeric(group) - 0.18, xend = as.numeric(group) + 0.18,
                   y = median, yend = median),
      inherit.aes = FALSE, color = "#222222", linewidth = 0.8
    ) +
    ggplot2::geom_linerange(
      data = summaries,
      ggplot2::aes(x = as.numeric(group), ymin = q1, ymax = q3),
      inherit.aes = FALSE, color = "#222222", linewidth = 0.45
    ) +
    ggplot2::geom_point(size = 1.55, alpha = 0.82) +
    ggplot2::scale_x_continuous(breaks = seq_along(levels(dat$group)), labels = levels(dat$group)) +
    ggplot2::scale_color_manual(values = palette_discrete) +
    ggplot2::guides(color = "none") +
    ggplot2::labs(x = NULL, y = value_axis_label(dat))
}

register_recipe_override(
  c("beeswarm-plot", "quasirandom-plot", "sina-plot", "dotplot-stacked"),
  render_advanced_distribution
)

render_advanced_relationship <- function(dat, recipe_id, config) {
  if (!"group" %in% names(dat)) dat$group <- "All"
  base <- ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = group)) +
    ggplot2::geom_point(size = 1.45, alpha = 0.70) +
    ggplot2::scale_color_manual(values = palette_discrete)

  if (recipe_id == "loess-plot") {
    return(base + ggplot2::geom_smooth(method = "loess", formula = y ~ x, se = FALSE, span = 1,
                                       method.args = list(degree = 1), linewidth = 0.65) +
             ggplot2::labs(x = "Predictor", y = "Response", color = "Group"))
  }
  if (recipe_id == "gam-smooth") {
    return(base + ggplot2::geom_smooth(method = "gam", formula = y ~ s(x, bs = "cs", k = 4), se = TRUE,
                                       linewidth = 0.65, alpha = 0.14) +
             ggplot2::labs(x = "Predictor", y = "GAM smooth", color = "Group"))
  }
  if (recipe_id == "incubation-kinetics") {
    return(base + ggplot2::geom_smooth(method = "lm", formula = y ~ log1p(x), se = FALSE,
                                       linewidth = 0.75) +
             ggplot2::scale_x_continuous(trans = "log1p") +
             ggplot2::labs(x = "Incubation time (log1p scale)", y = "Kinetic response", color = "Group"))
  }
  if (recipe_id == "adsorption-isotherm") {
    return(base + ggplot2::geom_smooth(method = "lm", formula = y ~ x + I(x^2), se = TRUE,
                                       linewidth = 0.70, alpha = 0.12) +
             ggplot2::labs(x = "Equilibrium concentration", y = "Adsorbed amount", color = "Group"))
  }
  if (recipe_id == "dose-response-curve") {
    return(base + ggplot2::geom_smooth(method = "glm", formula = y ~ poly(x, 3), se = TRUE,
                                       linewidth = 0.70, alpha = 0.12) +
             ggplot2::labs(x = "Dose", y = "Response", color = "Group"))
  }
  NULL
}

register_recipe_override(
  c("loess-plot", "gam-smooth", "incubation-kinetics", "adsorption-isotherm", "dose-response-curve"),
  render_advanced_relationship
)

render_advanced_soil_physics <- function(dat, recipe_id, config) {
  if (!"group" %in% names(dat)) dat$group <- "All"
  dat <- dat[order(dat$group, dat$x), , drop = FALSE]
  base <- ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, color = group, group = group)) +
    ggplot2::geom_point(size = 1.55) +
    ggplot2::scale_color_manual(values = palette_discrete)
  if (recipe_id == "particle-size-cumulative") {
    dat$cumulative <- ave(pmax(dat$y, 0), dat$group, FUN = function(z) cumsum(z) / sum(z) * 100)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = cumulative, color = group)) +
      ggplot2::geom_step(linewidth = 0.70) + ggplot2::geom_point(size = 1.35) +
      ggplot2::scale_x_log10() + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Particle diameter (log scale)", y = "Cumulative fraction (%)", color = "Group"))
  }
  if (recipe_id == "water-retention-curve") {
    return(base + ggplot2::geom_line(linewidth = 0.70) + ggplot2::scale_x_log10() +
      ggplot2::scale_y_reverse() +
      ggplot2::labs(x = "Pressure head / suction (log scale)", y = "Water content", color = "Group"))
  }
  if (recipe_id == "hydraulic-conductivity-curve") {
    return(base + ggplot2::geom_line(linewidth = 0.70) +
      ggplot2::scale_y_log10() +
      ggplot2::labs(x = "Pressure head", y = "Hydraulic conductivity (log scale)", color = "Group"))
  }
  if (recipe_id == "infiltration-curve") {
    dat$cumulative <- ave(pmax(dat$y, 0), dat$group, FUN = cumsum)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = cumulative, color = group)) +
      ggplot2::geom_line(linewidth = 0.75) + ggplot2::geom_point(size = 1.35) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Elapsed time", y = "Cumulative infiltration", color = "Group"))
  }
  if (recipe_id == "breakthrough-curve") {
    dat$normalized <- ave(dat$y, dat$group, FUN = function(z) (z - min(z)) / max(diff(range(z)), .Machine$double.eps))
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = normalized, color = group)) +
      ggplot2::geom_line(linewidth = 0.75) + ggplot2::geom_point(size = 1.35) +
      ggplot2::geom_hline(yintercept = 0.5, linetype = 2, linewidth = 0.35) +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Pore volumes / elapsed time", y = expression(C/C[0]), color = "Group"))
  }
  NULL
}

register_recipe_override(
  c("particle-size-cumulative", "water-retention-curve", "hydraulic-conductivity-curve", "infiltration-curve", "breakthrough-curve"),
  render_advanced_soil_physics
)

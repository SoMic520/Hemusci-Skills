# Soil profile and image/volume variants.

profile_midpoint <- function(dat) (dat$top_cm + dat$bottom_cm) / 2

render_advanced_profile <- function(dat, recipe_id, config) {
  if (!"group" %in% names(dat)) dat$group <- dat$profile_id
  dat$depth_mid <- profile_midpoint(dat)
  dat$profile_id <- factor(dat$profile_id, levels = unique(dat$profile_id))
  dat$property <- factor(dat$property, levels = unique(dat$property))

  if (recipe_id == "grouped-soil-profiles") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = value, y = depth_mid, color = profile_id, group = profile_id)) +
      ggplot2::geom_step(direction = "vh", linewidth = 0.70) + ggplot2::geom_point(size = 1.5) +
      ggplot2::facet_wrap(~property, scales = "free_x", nrow = 1) + ggplot2::scale_y_reverse() +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Property value", y = "Depth (cm)", color = "Profile"))
  }
  if (recipe_id == "soil-depth-profile") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = value, y = depth_mid, color = group, group = profile_id)) +
      ggplot2::geom_path(linewidth = 0.72) +
      ggplot2::geom_linerange(ggplot2::aes(ymin = top_cm, ymax = bottom_cm), linewidth = 1.5, alpha = 0.35) +
      ggplot2::geom_point(shape = 21, fill = "white", size = 1.8) + ggplot2::scale_y_reverse() +
      ggplot2::facet_wrap(~property, scales = "free_x") + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Measured value", y = "Depth (cm)", color = "Group"))
  }
  if (recipe_id == "mass-preserving-spline-profile") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = value, y = depth_mid, color = profile_id)) +
      ggplot2::geom_point(size = 1.5) +
      ggplot2::geom_smooth(ggplot2::aes(group = profile_id), method = "lm", formula = y ~ poly(x, 2),
                           se = FALSE, linewidth = 0.72) +
      ggplot2::scale_y_reverse() + ggplot2::facet_wrap(~property, scales = "free_x") +
      ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::labs(x = "Spline support value", y = "Depth (cm)", color = "Profile"))
  }
  if (recipe_id == "soil-color-profile") {
    dat$color_class <- cut(dat$value, breaks = 5, include.lowest = TRUE)
    return(ggplot2::ggplot(dat) +
      ggplot2::geom_rect(ggplot2::aes(xmin = as.numeric(profile_id) - 0.38, xmax = as.numeric(profile_id) + 0.38,
                                      ymin = top_cm, ymax = bottom_cm, fill = color_class),
                         color = "white", linewidth = 0.35) +
      ggplot2::scale_y_reverse() + ggplot2::scale_x_continuous(breaks = seq_along(levels(dat$profile_id)), labels = levels(dat$profile_id)) +
      ggplot2::scale_fill_brewer(palette = "YlOrBr", direction = 1) +
      ggplot2::labs(x = "Profile", y = "Depth (cm)", fill = "Color/value class"))
  }
  if (recipe_id == "catena-diagram") {
    dat$position <- as.numeric(dat$profile_id)
    return(ggplot2::ggplot(dat, ggplot2::aes(x = position, y = depth_mid, color = value, group = interaction(property, depth_mid))) +
      ggplot2::geom_line(color = "#8A8A8A", linewidth = 0.45) +
      ggplot2::geom_point(size = 2.4) + ggplot2::scale_y_reverse() +
      ggplot2::scale_x_continuous(breaks = seq_along(levels(dat$profile_id)), labels = levels(dat$profile_id)) +
      ggplot2::scale_color_viridis_c(option = "C") +
      ggplot2::facet_wrap(~property, scales = "free_y") +
      ggplot2::labs(x = "Topographic sequence", y = "Depth (cm)", color = "Property value"))
  }
  if (recipe_id == "stratigraphic-log") {
    dat$unit <- interaction(dat$profile_id, dat$property, drop = TRUE)
    return(ggplot2::ggplot(dat) +
      ggplot2::geom_rect(ggplot2::aes(xmin = 0, xmax = value, ymin = top_cm, ymax = bottom_cm, fill = property),
                         color = "white", linewidth = 0.35) +
      ggplot2::facet_wrap(~profile_id, scales = "free_x") + ggplot2::scale_y_reverse() +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::labs(x = "Layer property magnitude", y = "Stratigraphic depth (cm)", fill = "Property"))
  }
  if (recipe_id == "penetration-resistance-profile") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = value, y = depth_mid, color = profile_id)) +
      ggplot2::geom_path(linewidth = 0.65) + ggplot2::geom_point(ggplot2::aes(size = bottom_cm - top_cm), alpha = 0.82) +
      ggplot2::scale_y_reverse() + ggplot2::scale_color_manual(values = palette_discrete) +
      ggplot2::scale_size_area(max_size = 4.2) +
      ggplot2::labs(x = "Penetration resistance", y = "Depth (cm)", color = "Profile", size = "Layer thickness"))
  }
  NULL
}

register_recipe_override(
  c("grouped-soil-profiles", "soil-depth-profile", "mass-preserving-spline-profile", "soil-color-profile",
    "catena-diagram", "stratigraphic-log", "penetration-resistance-profile"),
  render_advanced_profile
)

normalize_image_intensity <- function(dat) {
  if (!"channel" %in% names(dat)) dat$channel <- "Intensity"
  if (!"slice" %in% names(dat)) dat$slice <- 1
  dat$scaled_intensity <- ave(dat$intensity, interaction(dat$channel, dat$slice), FUN = function(z) scales::rescale(z))
  dat
}

render_advanced_image <- function(dat, recipe_id, config) {
  dat <- normalize_image_intensity(dat)
  equal <- ggplot2::coord_equal(expand = FALSE)
  magma <- ggplot2::scale_fill_viridis_c(option = "magma")

  if (recipe_id == "image-montage") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = intensity)) +
      ggplot2::geom_raster() + ggplot2::facet_grid(channel ~ slice) + equal + magma +
      ggplot2::labs(x = NULL, y = NULL, fill = "Intensity"))
  }
  if (recipe_id == "hyperspectral-cube") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = intensity)) +
      ggplot2::geom_tile(color = NA) + ggplot2::facet_grid(slice ~ channel) + equal + magma +
      ggplot2::labs(x = "X", y = "Y", fill = "Band intensity"))
  }
  if (recipe_id == "kymograph") {
    collapsed <- stats::aggregate(intensity ~ x + slice + channel, dat, mean)
    return(ggplot2::ggplot(collapsed, ggplot2::aes(x = x, y = slice, fill = intensity)) +
      ggplot2::geom_tile() + ggplot2::facet_wrap(~channel, ncol = 1) + magma +
      ggplot2::labs(x = "Distance", y = "Slice / time", fill = "Mean intensity"))
  }
  if (recipe_id == "orthogonal-slices") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, fill = intensity)) +
      ggplot2::geom_raster() + ggplot2::facet_wrap(~slice, nrow = 1) + equal + magma +
      ggplot2::geom_hline(yintercept = median(dat$y), color = "white", linewidth = 0.35) +
      ggplot2::geom_vline(xintercept = median(dat$x), color = "white", linewidth = 0.35) +
      ggplot2::labs(x = "X", y = "Y", fill = "Intensity"))
  }
  if (recipe_id == "isosurface") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x, y = y, z = intensity, color = ggplot2::after_stat(level))) +
      ggplot2::geom_contour(bins = 6, linewidth = 0.65) + ggplot2::facet_grid(channel ~ slice) + equal +
      ggplot2::scale_color_viridis_c(option = "C") + ggplot2::labs(x = "X", y = "Y", color = "Iso-level"))
  }
  if (recipe_id == "surface-3d") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x + 0.25 * slice, y = y + 0.18 * slice, fill = intensity)) +
      ggplot2::geom_tile(width = 0.95, height = 0.95, color = "white", linewidth = 0.20, alpha = 0.86) +
      ggplot2::facet_wrap(~channel) + equal + magma +
      ggplot2::labs(x = "Projected X", y = "Projected Y", fill = "Surface intensity"))
  }
  if (recipe_id == "point-cloud-3d") {
    return(ggplot2::ggplot(dat, ggplot2::aes(x = x + 0.18 * slice, y = y + 0.12 * slice,
                                             size = scaled_intensity, color = intensity, shape = channel)) +
      ggplot2::geom_point(alpha = 0.72) + equal +
      ggplot2::scale_color_viridis_c(option = "C") + ggplot2::scale_size_area(max_size = 4.6) +
      ggplot2::labs(x = "Projected X", y = "Projected Y", color = "Intensity", size = "Relative intensity", shape = "Channel"))
  }
  NULL
}

register_recipe_override(
  c("image-montage", "hyperspectral-cube", "kymograph", "orthogonal-slices", "isosurface", "surface-3d", "point-cloud-3d"),
  render_advanced_image
)

# Network, schematic and hierarchy variants.

network_node_groups <- function(dat) {
  if (!"from_group" %in% names(dat)) dat$from_group <- "Source"
  if (!"to_group" %in% names(dat)) dat$to_group <- "Target"
  groups <- rbind(
    data.frame(node = dat$from, group = dat$from_group),
    data.frame(node = dat$to, group = dat$to_group)
  )
  groups[!duplicated(groups$node), , drop = FALSE]
}

network_circle_layout <- function(dat) {
  groups <- network_node_groups(dat)
  angle <- seq(pi / 2, pi / 2 + 2 * pi, length.out = nrow(groups) + 1)[-nrow(groups) - 1]
  groups$x <- cos(angle)
  groups$y <- sin(angle)
  groups$label_x <- 1.16 * groups$x
  groups$label_y <- 1.16 * groups$y
  groups
}

network_join_edges <- function(dat, nodes) {
  edges <- merge(dat, nodes[c("node", "x", "y")], by.x = "from", by.y = "node", all.x = TRUE)
  names(edges)[names(edges) %in% c("x", "y")] <- c("x_from", "y_from")
  edges <- merge(edges, nodes[c("node", "x", "y")], by.x = "to", by.y = "node", all.x = TRUE)
  names(edges)[names(edges) %in% c("x", "y")] <- c("x_to", "y_to")
  if (!"weight" %in% names(edges)) edges$weight <- 1
  edges$sign <- factor(ifelse(edges$weight >= 0, "Positive", "Negative"), levels = c("Positive", "Negative"))
  edges
}

network_circle_base <- function(dat) {
  nodes <- network_circle_layout(dat)
  edges <- network_join_edges(dat, nodes)
  list(nodes = nodes, edges = edges)
}

render_advanced_network <- function(dat, recipe_id, config) {
  layout <- network_circle_base(dat)
  nodes <- layout$nodes
  edges <- layout$edges
  edge_colors <- c(Positive = "#0072B2", Negative = "#D55E00")
  base_nodes <- list(
    ggplot2::geom_point(data = nodes, ggplot2::aes(x = x, y = y, fill = group), shape = 21, size = 3.2, color = "#222222"),
    ggplot2::geom_text(data = nodes, ggplot2::aes(x = label_x, y = label_y, label = node), size = 2.0, check_overlap = TRUE),
    ggplot2::scale_fill_manual(values = palette_discrete),
    ggplot2::coord_equal(xlim = c(-1.38, 1.38), ylim = c(-1.38, 1.38), clip = "off"),
    ggplot2::theme_void()
  )

  if (recipe_id == "node-link-network") {
    return(ggplot2::ggplot() +
      ggplot2::geom_segment(data = edges, ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to),
                            color = "#9A9A9A", linewidth = 0.55, alpha = 0.78) +
      base_nodes + ggplot2::guides(fill = ggplot2::guide_legend(nrow = 1)) +
      ggplot2::labs(fill = "Node class"))
  }
  if (recipe_id == "directed-network") {
    return(ggplot2::ggplot() +
      ggplot2::geom_curve(data = edges, ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to, linetype = sign),
                          curvature = 0.10, color = "#6F7782", linewidth = 0.60,
                          arrow = grid::arrow(length = grid::unit(1.4, "mm"), type = "closed")) +
      base_nodes + ggplot2::scale_linetype_manual(values = c(Positive = 1, Negative = 2)) +
      ggplot2::labs(fill = "Node class", linetype = "Edge sign"))
  }
  if (recipe_id == "weighted-network") {
    return(ggplot2::ggplot() +
      ggplot2::geom_curve(data = edges,
                          ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to,
                                       linewidth = abs(weight), color = sign),
                          curvature = 0.10, alpha = 0.72, lineend = "round") +
      base_nodes + ggplot2::scale_linewidth(range = c(0.35, 2.0)) +
      ggplot2::scale_color_manual(values = edge_colors) +
      ggplot2::guides(fill = ggplot2::guide_legend(order = 1), color = ggplot2::guide_legend(order = 2),
                      linewidth = ggplot2::guide_legend(order = 3)) +
      ggplot2::theme(legend.box = "vertical") +
      ggplot2::labs(fill = "Node class", color = "Sign", linewidth = "|Weight|"))
  }
  if (recipe_id == "network-small-multiples") {
    panel_edges <- edges
    panel_nodes <- do.call(rbind, lapply(levels(edges$sign), function(sign_value) {
      transform(nodes, sign = factor(sign_value, levels = levels(edges$sign)))
    }))
    return(ggplot2::ggplot() +
      ggplot2::geom_segment(data = panel_edges,
                            ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to, linewidth = abs(weight)),
                            color = "#7A7A7A", alpha = 0.75) +
      ggplot2::geom_point(data = panel_nodes, ggplot2::aes(x = x, y = y, fill = group),
                          shape = 21, size = 2.7, color = "#222222") +
      ggplot2::geom_text(data = panel_nodes, ggplot2::aes(x = 1.12 * x, y = 1.12 * y, label = node),
                         size = 1.8, check_overlap = TRUE) +
      ggplot2::facet_wrap(~sign, nrow = 1) + ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::scale_linewidth(range = c(0.35, 1.4), guide = "none") +
      ggplot2::coord_equal(xlim = c(-1.32, 1.32), ylim = c(-1.32, 1.32), clip = "off") +
      ggplot2::theme_void() + ggplot2::labs(fill = "Node class"))
  }
  if (recipe_id %in% c("enrichment-map", "cnetplot")) {
    left <- unique(dat$from)
    right <- unique(dat$to)
    left_nodes <- data.frame(node = left, x = 0, y = seq(0.12, 0.88, length.out = length(left)), role = "Source")
    right_nodes <- data.frame(node = right, x = 1, y = seq(0.12, 0.88, length.out = length(right)), role = "Target")
    edges <- merge(dat, left_nodes, by.x = "from", by.y = "node")
    names(edges)[names(edges) %in% c("x", "y")] <- c("x_from", "y_from")
    edges <- merge(edges, right_nodes, by.x = "to", by.y = "node")
    names(edges)[names(edges) %in% c("x", "y")] <- c("x_to", "y_to")
    edges$sign <- ifelse(edges$weight >= 0, "Positive", "Negative")
    p <- ggplot2::ggplot() +
      ggplot2::geom_curve(data = edges,
                          ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to,
                                       linewidth = abs(weight), color = sign), curvature = 0.08, alpha = 0.68) +
      ggplot2::scale_color_manual(values = edge_colors) + ggplot2::scale_linewidth(range = c(0.35, 1.6), guide = "none")
    if (recipe_id == "enrichment-map") {
      p <- p +
        ggplot2::geom_point(data = left_nodes, ggplot2::aes(x = x, y = y), shape = 22, size = 4.0, fill = "#E69F00") +
        ggplot2::geom_point(data = right_nodes, ggplot2::aes(x = x, y = y), shape = 21, size = 3.0, fill = "#56B4E9")
    } else {
      p <- p +
        ggplot2::geom_point(data = left_nodes, ggplot2::aes(x = x, y = y), shape = 21, size = 5.2, fill = "#CC79A7") +
        ggplot2::geom_point(data = right_nodes, ggplot2::aes(x = x, y = y), shape = 21, size = 2.6, fill = "#009E73")
    }
    return(p +
      ggplot2::geom_text(data = left_nodes, ggplot2::aes(x = x - 0.05, y = y, label = node), hjust = 1, size = 1.9) +
      ggplot2::geom_text(data = right_nodes, ggplot2::aes(x = x + 0.05, y = y, label = node), hjust = 0, size = 1.9) +
      ggplot2::coord_cartesian(xlim = c(-0.35, 1.35), ylim = c(0, 1), clip = "off") +
      ggplot2::theme_void() + ggplot2::labs(color = "Association"))
  }
  NULL
}

register_recipe_override(
  c("node-link-network", "directed-network", "weighted-network", "network-small-multiples", "enrichment-map", "cnetplot"),
  render_advanced_network
)

layered_network_layout <- function(dat, orientation = "horizontal") {
  groups <- network_node_groups(dat)
  stage_order <- unique(groups$group)
  groups$stage <- match(groups$group, stage_order)
  groups$within <- ave(seq_len(nrow(groups)), groups$stage, FUN = function(index) seq(0.15, 0.85, length.out = length(index)))
  stage_position <- if (length(stage_order) == 1) rep(0.5, nrow(groups)) else (groups$stage - 1) / (length(stage_order) - 1)
  if (orientation == "horizontal") {
    groups$x <- stage_position
    groups$y <- groups$within
  } else {
    groups$x <- groups$within
    groups$y <- 1 - stage_position
  }
  attr(groups, "stage_order") <- stage_order
  groups
}

render_advanced_schematic <- function(dat, recipe_id, config) {
  orientation <- if (recipe_id %in% c("experimental-design-diagram", "consort-flow")) "vertical" else "horizontal"
  nodes <- layered_network_layout(dat, orientation)
  edges <- network_join_edges(dat, nodes)
  stage_order <- attr(nodes, "stage_order")
  if (orientation == "horizontal") {
    headers <- unique(nodes[c("group", "stage")])
    headers$x <- if (length(stage_order) == 1) 0.5 else (headers$stage - 1) / (length(stage_order) - 1)
    headers$y <- 1.03
  } else {
    headers <- unique(nodes[c("group", "stage")])
    headers$x <- 0.02
    headers$y <- if (length(stage_order) == 1) 0.5 else 1 - (headers$stage - 1) / (length(stage_order) - 1)
  }
  edges$edge_label <- format(round(edges$weight, 2), nsmall = 2)

  if (recipe_id == "workflow-diagram") {
    nodes <- nodes[order(nodes$stage, nodes$within), ]
    return(ggplot2::ggplot() +
      ggplot2::geom_curve(data = edges, ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to),
                          curvature = 0.05, color = "#6F7782", linewidth = 0.65,
                          arrow = grid::arrow(length = grid::unit(1.3, "mm"), type = "closed")) +
      ggplot2::geom_label(data = nodes, ggplot2::aes(x = x, y = y, label = node, fill = group),
                          size = 2.0, label.padding = grid::unit(1.7, "mm"), label.size = 0.25) +
      ggplot2::geom_text(data = headers, ggplot2::aes(x = x, y = y, label = group), fontface = "bold", size = 2.1) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::guides(fill = "none") +
      ggplot2::coord_cartesian(xlim = c(-0.15, 1.15), ylim = c(0.03, 1.09), clip = "off") + ggplot2::theme_void())
  }
  if (recipe_id == "sem-path") {
    return(ggplot2::ggplot() +
      ggplot2::geom_curve(data = edges,
                          ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to,
                                       linewidth = abs(weight), linetype = sign), curvature = 0.04,
                          color = "#5D6673", arrow = grid::arrow(length = grid::unit(1.2, "mm"))) +
      ggplot2::geom_text(data = edges, ggplot2::aes(x = (x_from + x_to) / 2, y = (y_from + y_to) / 2, label = edge_label),
                         size = 1.8, color = "#333333") +
      ggplot2::geom_label(data = nodes, ggplot2::aes(x = x, y = y, label = node, fill = group),
                          size = 2.0, label.size = 0.3) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_linewidth(range = c(0.35, 1.4), guide = "none") +
      ggplot2::scale_linetype_manual(values = c(Positive = 1, Negative = 2), guide = "none") +
      ggplot2::guides(fill = "none") + ggplot2::coord_cartesian(xlim = c(-0.12, 1.12), ylim = c(0.04, 0.96), clip = "off") + ggplot2::theme_void())
  }
  if (recipe_id == "causal-dag") {
    return(ggplot2::ggplot() +
      ggplot2::geom_curve(data = edges,
                          ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to, color = sign),
                          curvature = 0.13, linewidth = 0.62,
                          arrow = grid::arrow(length = grid::unit(1.4, "mm"), type = "closed")) +
      ggplot2::geom_point(data = nodes, ggplot2::aes(x = x, y = y, fill = group), shape = 21, size = 4.1, color = "#222222") +
      ggplot2::geom_text(data = nodes, ggplot2::aes(x = x, y = y, label = node), size = 1.75) +
      ggplot2::scale_color_manual(values = c(Positive = "#0072B2", Negative = "#D55E00")) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::guides(fill = "none") +
      ggplot2::coord_cartesian(xlim = c(-0.12, 1.12), ylim = c(0.02, 0.98), clip = "off") + ggplot2::theme_void() +
      ggplot2::labs(color = "Signed path"))
  }
  if (recipe_id == "experimental-design-diagram") {
    return(ggplot2::ggplot() +
      ggplot2::geom_segment(data = edges, ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to),
                            color = "#7B8490", linewidth = 0.65) +
      ggplot2::geom_label(data = nodes, ggplot2::aes(x = x, y = y, label = node, fill = group),
                          size = 1.95, label.size = 0.28) +
      ggplot2::geom_text(data = headers, ggplot2::aes(x = x, y = y, label = group), hjust = 0, fontface = "bold", size = 2.0) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::guides(fill = "none") +
      ggplot2::coord_cartesian(xlim = c(0, 1), ylim = c(-0.08, 1.08), clip = "off") + ggplot2::theme_void())
  }
  if (recipe_id == "conceptual-model") {
    circle <- network_circle_base(dat)
    return(ggplot2::ggplot() +
      ggplot2::geom_curve(data = circle$edges,
                          ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to,
                                       linewidth = abs(weight), color = sign), curvature = 0.22, alpha = 0.68) +
      ggplot2::geom_label(data = circle$nodes, ggplot2::aes(x = x, y = y, label = node, fill = group),
                          size = 1.85, label.size = 0.28) +
      ggplot2::scale_fill_manual(values = palette_discrete) +
      ggplot2::scale_color_manual(values = c(Positive = "#0072B2", Negative = "#D55E00")) +
      ggplot2::scale_linewidth(range = c(0.35, 1.6), guide = "none") +
      ggplot2::guides(fill = "none") + ggplot2::coord_equal(xlim = c(-1.25, 1.25), ylim = c(-1.25, 1.25)) +
      ggplot2::theme_void() + ggplot2::labs(color = "Relation"))
  }
  if (recipe_id == "consort-flow") {
    return(ggplot2::ggplot() +
      ggplot2::geom_curve(data = edges,
                          ggplot2::aes(x = x_from, y = y_from, xend = x_to, yend = y_to,
                                       linewidth = abs(weight)), curvature = 0.05, color = "#7A8491",
                          arrow = grid::arrow(length = grid::unit(1.3, "mm"), type = "closed")) +
      ggplot2::geom_label(data = nodes, ggplot2::aes(x = x, y = y, label = node, fill = group),
                          size = 1.95, label.size = 0.3, label.padding = grid::unit(1.6, "mm")) +
      ggplot2::geom_text(data = edges, ggplot2::aes(x = (x_from + x_to) / 2, y = (y_from + y_to) / 2, label = edge_label),
                         size = 1.75) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_linewidth(range = c(0.35, 1.5), guide = "none") +
      ggplot2::guides(fill = "none") + ggplot2::coord_cartesian(xlim = c(0, 1), ylim = c(-0.08, 1.08), clip = "off") +
      ggplot2::theme_void())
  }
  NULL
}

register_recipe_override(
  c("sem-path", "causal-dag", "workflow-diagram", "experimental-design-diagram", "conceptual-model", "consort-flow"),
  render_advanced_schematic
)

orthogonal_tree_data <- function(dat) {
  layout <- hierarchy_layout(dat)
  parents <- layout[c("node_id", "x", "y")]
  names(parents) <- c("parent_id", "parent_x", "parent_y")
  edges <- merge(layout, parents, by = "parent_id", all.x = TRUE)
  list(layout = layout, edges = edges, leaves = layout[!layout$node_id %in% layout$parent_id, , drop = FALSE])
}

render_advanced_hierarchy <- function(dat, recipe_id, config) {
  if (!"group" %in% names(dat)) dat$group <- "All"
  tree <- orthogonal_tree_data(dat)
  layout <- tree$layout
  edges <- tree$edges[!is.na(tree$edges$parent_x), , drop = FALSE]
  leaves <- tree$leaves

  if (recipe_id == "dendrogram") {
    return(ggplot2::ggplot() +
      ggplot2::geom_segment(data = edges, ggplot2::aes(x = parent_x, y = parent_y, xend = x, yend = parent_y), color = "#777777") +
      ggplot2::geom_segment(data = edges, ggplot2::aes(x = x, y = parent_y, xend = x, yend = y), color = "#777777") +
      ggplot2::geom_text(data = leaves, ggplot2::aes(x = x + 0.08, y = y, label = label), hjust = 0, size = 1.95) +
      ggplot2::coord_cartesian(xlim = c(-0.05, max(layout$x) + 1.15), ylim = c(0, 1), clip = "off") +
      ggplot2::theme_void())
  }
  if (recipe_id == "unrooted-tree") {
    layout$angle <- 2 * pi * layout$y
    layout$radius <- layout$x + 0.25
    layout$px <- layout$radius * cos(layout$angle)
    layout$py <- layout$radius * sin(layout$angle)
    parents <- layout[c("node_id", "px", "py")]
    names(parents) <- c("parent_id", "parent_px", "parent_py")
    radial_edges <- merge(layout, parents, by = "parent_id", all.x = TRUE)
    radial_leaves <- layout[layout$node_id %in% leaves$node_id, ]
    return(ggplot2::ggplot() +
      ggplot2::geom_segment(data = radial_edges[!is.na(radial_edges$parent_px), ],
                            ggplot2::aes(x = parent_px, y = parent_py, xend = px, yend = py), color = "#888888") +
      ggplot2::geom_point(data = layout, ggplot2::aes(x = px, y = py, fill = group, size = value), shape = 21) +
      ggplot2::geom_text(data = radial_leaves, ggplot2::aes(x = 1.12 * px, y = 1.12 * py, label = label), size = 1.8, check_overlap = TRUE) +
      ggplot2::scale_fill_manual(values = palette_discrete) + ggplot2::scale_size_area(max_size = 4.5, guide = "none") +
      ggplot2::coord_equal(clip = "off") + ggplot2::theme_void() + ggplot2::labs(fill = "Group"))
  }
  if (recipe_id %in% c("tanglegram", "cophylogeny-plot")) {
    left <- layout
    right <- layout
    right$x <- 5 - right$x
    if (recipe_id == "tanglegram") right$y <- 1 - right$y
    left_parents <- left[c("node_id", "x", "y")]
    names(left_parents) <- c("parent_id", "parent_x", "parent_y")
    left_edges <- merge(left, left_parents, by = "parent_id", all.x = TRUE)
    right_parents <- right[c("node_id", "x", "y")]
    names(right_parents) <- c("parent_id", "parent_x", "parent_y")
    right_edges <- merge(right, right_parents, by = "parent_id", all.x = TRUE)
    connectors <- merge(
      left[left$node_id %in% leaves$node_id, c("node_id", "x", "y")],
      right[right$node_id %in% leaves$node_id, c("node_id", "x", "y")],
      by = "node_id", suffixes = c("_left", "_right")
    )
    return(ggplot2::ggplot() +
      ggplot2::geom_segment(data = left_edges[!is.na(left_edges$parent_x), ],
                            ggplot2::aes(x = parent_x, y = parent_y, xend = x, yend = y), color = "#707070") +
      ggplot2::geom_segment(data = right_edges[!is.na(right_edges$parent_x), ],
                            ggplot2::aes(x = parent_x, y = parent_y, xend = x, yend = y), color = "#707070") +
      ggplot2::geom_segment(data = connectors,
                            ggplot2::aes(x = x_left, y = y_left, xend = x_right, yend = y_right),
                            color = if (recipe_id == "tanglegram") "#CC79A7" else "#56B4E9",
                            alpha = 0.55, linetype = 2) +
      ggplot2::geom_point(data = connectors, ggplot2::aes(x = x_left, y = y_left), size = 1.6) +
      ggplot2::geom_point(data = connectors, ggplot2::aes(x = x_right, y = y_right), size = 1.6) +
      ggplot2::coord_cartesian(xlim = c(-0.1, 5.1), ylim = c(-0.03, 1.03), clip = "off") + ggplot2::theme_void())
  }
  NULL
}

register_recipe_override(c("dendrogram", "unrooted-tree", "tanglegram", "cophylogeny-plot"), render_advanced_hierarchy)

#!/usr/bin/env Rscript

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 土壤硬度—深度区间柱状图｜中文详细注释版
# 输入：与代码同目录的“标准输入表格.xlsx”
# 输出：与代码同目录的 PDF、PNG、TIFF 三种格式成图
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── 01｜定位代码所在文件夹 ───────────────────────────────────────────────────
script_path <- function() {
  value <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (!length(value)) return(normalizePath(".", winslash = "/", mustWork = TRUE))
  normalizePath(sub("^--file=", "", value[[1]]), winslash = "/", mustWork = TRUE)
}

root <- dirname(script_path())
set.seed(20260816)
options(repos = c(CRAN = "https://cloud.r-project.org"))

# ── 02｜自动检测并安装代码真正使用的包 ────────────────────────────────────────
required <- c(
  "ggplot2", "ggtext", "nlme", "ragg", "readxl", "scales",
  "showtext", "sysfonts", "systemfonts"
)
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) utils::install.packages(missing, dependencies = NA)
remaining <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(remaining)) stop("安装后仍缺少 R 包：", paste(remaining, collapse = "、"))

# ── 03｜按操作系统自动选择并注册中英文字体 ────────────────────────────────────
# macOS 优先宋体与 Times New Roman；Windows 优先宋体（SimSun）与 Times New Roman。
# 注册为代码内部别名后，PDF、PNG 和 TIFF 会使用同一套字体，不依赖设备默认字体。
font_table <- systemfonts::system_fonts()
register_font <- function(alias, candidates, fallback = "serif") {
  for (candidate in candidates) {
    rows <- font_table[
      font_table$family == candidate &
        font_table$style %in% c("Regular", "Normal", "Book", "Roman"),
      , drop = FALSE
    ]
    if (!nrow(rows)) rows <- font_table[font_table$family == candidate, , drop = FALSE]
    if (nrow(rows)) {
      sysfonts::font_add(family = alias, regular = rows$path[[1]])
      return(alias)
    }
  }
  fallback
}
font_chinese <- register_font(
  "HemusciSong",
  c("Songti SC", "STSong", "SimSun", "宋体", "Noto Serif CJK SC")
)
font_english <- register_font(
  "HemusciTimes",
  c("Times New Roman", "Times", "Liberation Serif")
)
showtext::showtext_auto(enable = TRUE)
showtext::showtext_opts(dpi = 600)

# ── 04｜读取标准输入表 ────────────────────────────────────────────────────────
input_path <- file.path(root, "标准输入表格.xlsx")
if (!file.exists(input_path)) stop("未找到标准输入表格.xlsx")
raw_data <- as.data.frame(
  readxl::read_excel(input_path, sheet = "标准输入", .name_repair = "minimal"),
  stringsAsFactors = FALSE,
  check.names = FALSE
)
names(raw_data) <- trimws(names(raw_data))

required_columns <- c(
  "样本编号", "处理", "深度/ (cm)", "土壤硬度/ (MPa)", "土壤含水量/ (%)"
)
absent <- setdiff(required_columns, names(raw_data))
if (length(absent)) stop("输入表缺少列：", paste(absent, collapse = "、"))
if (anyNA(raw_data[required_columns])) stop("五个必填列不允许存在缺失值")

dat <- data.frame(
  sample_id = trimws(as.character(raw_data[["样本编号"]])),
  treatment_zh = trimws(as.character(raw_data[["处理"]])),
  depth_cm = suppressWarnings(as.numeric(raw_data[["深度/ (cm)"]])),
  hardness_mpa = suppressWarnings(as.numeric(raw_data[["土壤硬度/ (MPa)"]])),
  water_pct = suppressWarnings(as.numeric(raw_data[["土壤含水量/ (%)"]])),
  stringsAsFactors = FALSE
)

# ── 05｜数据和实验设计校验 ────────────────────────────────────────────────────
if (any(!nzchar(dat$sample_id)) || any(!nzchar(dat$treatment_zh))) stop("样本编号和处理不得为空")
numeric_part <- as.matrix(dat[c("depth_cm", "hardness_mpa", "water_pct")])
if (anyNA(numeric_part) || any(!is.finite(numeric_part))) stop("深度、硬度和含水量必须为有限数值")
if (any(dat$depth_cm < 0) || any(dat$hardness_mpa < 0)) stop("深度和硬度不得为负数")
if (any(dat$water_pct <= 0 | dat$water_pct >= 100)) stop("土壤含水量必须位于 0–100% 之间")
if (anyDuplicated(dat[c("sample_id", "depth_cm")])) stop("样本编号×深度必须唯一")

treatment_map <- c("对照" = "Control", "堆肥" = "Compost", "生物炭" = "Biochar")
treatment_order <- unname(treatment_map)
labels_zh <- c(Control = "对照", Compost = "堆肥", Biochar = "生物炭")
unexpected <- setdiff(unique(dat$treatment_zh), names(treatment_map))
if (length(unexpected)) stop("存在未识别处理：", paste(unexpected, collapse = "、"))
dat$treatment <- factor(unname(treatment_map[dat$treatment_zh]), levels = treatment_order)

sample_treatment_count <- tapply(dat$treatment, dat$sample_id, function(value) length(unique(value)))
if (any(sample_treatment_count != 1L)) stop("同一样本编号不能属于多个处理")
sample_n <- tapply(dat$sample_id, dat$treatment, function(value) length(unique(value)))
if (any(sample_n < 3L)) stop("每个处理至少需要三个独立样品")

# ── 06｜定义深度区间并在每个独立样品内先求区间均值 ──────────────────────────
# 区间规则为左闭右开：[0,10)、[10,20)……；最后一个区间包含 60 cm。
# 用户可以直接修改下面两行来改变区间边界和显示文字。
depth_breaks <- c(0, 10, 20, 30, 40, 50, 60)
interval_labels <- c("0-10", "10-20", "20-30", "30-40", "40-50", "50-60")
if (length(interval_labels) != length(depth_breaks) - 1L) stop("区间标签数量与边界不匹配")
if (any(dat$depth_cm < min(depth_breaks) | dat$depth_cm > max(depth_breaks))) {
  stop("输入深度超出 depth_breaks 定义范围")
}

dat$interval_index <- findInterval(dat$depth_cm, depth_breaks, rightmost.closed = TRUE)
if (any(dat$interval_index < 1L | dat$interval_index > length(interval_labels))) stop("深度区间划分失败")
dat$interval <- factor(interval_labels[dat$interval_index], levels = interval_labels)

sample_interval_rows <- lapply(
  split(dat, interaction(dat$sample_id, dat$treatment, dat$interval, drop = TRUE)),
  function(part) {
    data.frame(
      sample_id = part$sample_id[[1]],
      treatment = as.character(part$treatment[[1]]),
      interval = as.character(part$interval[[1]]),
      interval_index = part$interval_index[[1]],
      hardness_mpa = mean(part$hardness_mpa),
      water_pct = mean(part$water_pct),
      measurement_points = nrow(part),
      stringsAsFactors = FALSE
    )
  }
)
interval_data <- do.call(rbind, sample_interval_rows)
interval_data$treatment <- factor(interval_data$treatment, levels = treatment_order)
interval_data$interval <- factor(interval_data$interval, levels = interval_labels)
interval_data <- interval_data[order(interval_data$sample_id, interval_data$interval_index), ]
if (any(table(interval_data$treatment, interval_data$interval) < 3L)) {
  stop("每个处理×深度区间至少需要三个独立样品")
}

water_reference <- mean(interval_data$water_pct)
interval_data$water_centered <- interval_data$water_pct - water_reference

# ── 07｜拟合区间重复测量混合模型 ──────────────────────────────────────────────
# 先在样品内汇总，避免同一深度区间的多个测点被错误当成独立重复。
# 各区间在同一样品内仍是重复测量，因此使用样品随机截距和 AR(1) 相关结构。
model <- nlme::lme(
  fixed = hardness_mpa ~ treatment * interval + water_centered,
  random = ~1 | sample_id,
  correlation = nlme::corAR1(form = ~interval_index | sample_id),
  data = interval_data,
  method = "REML",
  na.action = stats::na.fail,
  control = nlme::lmeControl(opt = "optim", msMaxIter = 200, returnObject = TRUE)
)

# ── 08｜计算平均含水量处的调整均值和 95% 置信区间 ───────────────────────────
prediction <- expand.grid(
  interval = interval_labels,
  treatment = treatment_order,
  KEEP.OUT.ATTRS = FALSE,
  stringsAsFactors = FALSE
)
prediction$interval <- factor(prediction$interval, levels = interval_labels)
prediction$interval_index <- match(as.character(prediction$interval), interval_labels)
prediction$treatment <- factor(prediction$treatment, levels = treatment_order)
prediction$water_centered <- 0

design <- stats::model.matrix(~treatment * interval + water_centered, prediction)
beta <- nlme::fixed.effects(model)
covariance <- stats::vcov(model)
if (!identical(colnames(design), names(beta))) stop("模型预测矩阵与系数不一致")

prediction$estimate <- drop(design %*% beta)
prediction$standard_error <- sqrt(diag(design %*% covariance %*% t(design)))
coefficient_df <- model$fixDF$X[names(beta)]
prediction$degrees_freedom <- vapply(seq_len(nrow(design)), function(index) {
  active <- abs(design[index, ]) > 1e-12
  values <- coefficient_df[active]
  values <- values[is.finite(values) & values > 0]
  if (length(values)) min(values) else min(coefficient_df, na.rm = TRUE)
}, numeric(1))
critical <- stats::qt(0.975, prediction$degrees_freedom)
prediction$conf_low <- pmax(0, prediction$estimate - critical * prediction$standard_error)
prediction$conf_high <- prediction$estimate + critical * prediction$standard_error

# ── 09｜在每个深度区间内比较处理，并执行 Holm 校正 ───────────────────────────
comparison_pairs <- utils::combn(treatment_order, 2, simplify = FALSE)
pairwise_rows <- lapply(interval_labels, function(interval_name) {
  local_rows <- which(as.character(prediction$interval) == interval_name)
  result <- lapply(comparison_pairs, function(pair) {
    row_1 <- local_rows[as.character(prediction$treatment[local_rows]) == pair[[1]]]
    row_2 <- local_rows[as.character(prediction$treatment[local_rows]) == pair[[2]]]
    contrast <- design[row_2, ] - design[row_1, ]
    difference <- drop(contrast %*% beta)
    standard_error <- sqrt(drop(contrast %*% covariance %*% contrast))
    active <- abs(contrast) > 1e-12
    df_values <- coefficient_df[active]
    df_values <- df_values[is.finite(df_values) & df_values > 0]
    degrees_freedom <- if (length(df_values)) min(df_values) else min(coefficient_df, na.rm = TRUE)
    statistic <- difference / standard_error
    data.frame(
      interval = interval_name,
      treatment_1 = pair[[1]],
      treatment_2 = pair[[2]],
      p_raw = 2 * stats::pt(abs(statistic), df = degrees_freedom, lower.tail = FALSE),
      stringsAsFactors = FALSE
    )
  })
  result <- do.call(rbind, result)
  result$p_holm <- stats::p.adjust(result$p_raw, method = "holm")
  result
})
pairwise <- do.call(rbind, pairwise_rows)

# ── 10｜把校正后的两两比较转换为紧凑字母标记 ────────────────────────────────
# 同一字母表示该深度区间内差异不显著；完全不同字母表示 Holm 校正后显著。
compact_letters <- function(prediction_part, comparison_part) {
  ordered_groups <- as.character(prediction_part$treatment[order(-prediction_part$estimate)])
  group_count <- length(ordered_groups)
  significance_matrix <- matrix(
    FALSE, nrow = group_count, ncol = group_count,
    dimnames = list(ordered_groups, ordered_groups)
  )
  for (index in seq_len(nrow(comparison_part))) {
    first <- comparison_part$treatment_1[[index]]
    second <- comparison_part$treatment_2[[index]]
    significant <- comparison_part$p_holm[[index]] <= 0.05
    significance_matrix[first, second] <- significant
    significance_matrix[second, first] <- significant
  }

  candidate_sets <- lapply(seq_len(2^group_count - 1L), function(mask) {
    ordered_groups[as.logical(intToBits(mask)[seq_len(group_count)])]
  })
  valid_sets <- Filter(function(group_set) {
    if (length(group_set) < 2L) return(TRUE)
    pairs <- utils::combn(group_set, 2)
    all(!vapply(seq_len(ncol(pairs)), function(column) {
      significance_matrix[pairs[1, column], pairs[2, column]]
    }, logical(1)))
  }, candidate_sets)
  maximal_sets <- Filter(function(group_set) {
    !any(vapply(valid_sets, function(other_set) {
      length(other_set) > length(group_set) && all(group_set %in% other_set)
    }, logical(1)))
  }, valid_sets)

  estimate_map <- setNames(prediction_part$estimate, as.character(prediction_part$treatment))
  scores <- vapply(maximal_sets, function(group_set) max(estimate_map[group_set]), numeric(1))
  maximal_sets <- maximal_sets[order(-scores)]
  result <- setNames(rep("", group_count), ordered_groups)
  for (index in seq_along(maximal_sets)) {
    symbol <- letters[[index]]
    result[maximal_sets[[index]]] <- paste0(result[maximal_sets[[index]]], symbol)
  }
  result
}

letter_rows <- lapply(interval_labels, function(interval_name) {
  prediction_part <- prediction[as.character(prediction$interval) == interval_name, ]
  comparison_part <- pairwise[pairwise$interval == interval_name, ]
  letters_here <- compact_letters(prediction_part, comparison_part)
  data.frame(
    interval = interval_name,
    treatment = names(letters_here),
    significance_letter = unname(letters_here),
    stringsAsFactors = FALSE
  )
})
letter_table <- do.call(rbind, letter_rows)
prediction$significance_letter <- letter_table$significance_letter[
  match(
    paste(as.character(prediction$interval), as.character(prediction$treatment)),
    paste(letter_table$interval, letter_table$treatment)
  )
]

# ── 11｜计算水平分组柱、原始点和显著性字母的位置 ────────────────────────────
# 深度是这张图的主变量，因此深度区间固定放在纵轴，并由浅到深向下排列。
group_offsets <- setNames(seq(-0.25, 0.25, length.out = length(treatment_order)), treatment_order)
prediction$y_position <- prediction$interval_index + group_offsets[as.character(prediction$treatment)]
interval_data$y_position <- interval_data$interval_index + group_offsets[as.character(interval_data$treatment)]

cell_id <- interaction(interval_data$interval, interval_data$treatment, drop = TRUE)
for (indices in split(seq_len(nrow(interval_data)), cell_id)) {
  ordered <- indices[order(interval_data$sample_id[indices])]
  interval_data$y_position[ordered] <- interval_data$y_position[ordered] +
    seq(-0.055, 0.055, length.out = length(ordered))
}

x_reference <- max(c(interval_data$hardness_mpa, prediction$conf_high, 2.0))
cell_maximum <- stats::aggregate(
  hardness_mpa ~ interval + treatment,
  data = interval_data,
  FUN = max
)
names(cell_maximum)[names(cell_maximum) == "hardness_mpa"] <- "raw_maximum"
prediction$raw_maximum <- cell_maximum$raw_maximum[
  match(
    paste(as.character(prediction$interval), as.character(prediction$treatment)),
    paste(as.character(cell_maximum$interval), as.character(cell_maximum$treatment))
  )
]
prediction$letter_x <- pmax(prediction$conf_high, prediction$raw_maximum) + x_reference * 0.035
x_upper <- max(prediction$letter_x) + x_reference * 0.08

# ── 12｜字号根据最终版面、区间数和处理数自动计算 ──────────────────────────────
figure_width_mm <- 120
figure_height_mm <- 118
density_penalty <- 0.12 * log1p(length(interval_labels) * length(treatment_order))
base_pt <- max(7.0, min(9.4, 8.9 + 0.006 * (min(figure_width_mm, figure_height_mm) - 100) - density_penalty))
axis_title_pt <- min(10.2, base_pt + 0.7)
axis_text_pt <- max(6.8, base_pt - 0.1)
legend_pt <- max(6.8, base_pt - 0.2)
letter_pt <- max(6.8, base_pt - 0.1)
annotation_pt <- max(6.5, base_pt - 0.6)

# ── 13｜设置配色和中英文混排轴标题 ────────────────────────────────────────────
palette <- c(Control = "#3B78A8", Compost = "#D97832", Biochar = "#5A9568")
labels_markup <- setNames(vapply(treatment_order, function(value) {
  paste0("<span style=\"font-family:", font_chinese, ";\">", labels_zh[[value]], "</span>")
}, character(1)), treatment_order)

x_label <- paste0(
  "<span style=\"font-family:", font_chinese, ";\">土壤硬度</span>",
  "<span style=\"font-family:", font_english, ";\">/ (MPa)</span>"
)
y_label <- paste0(
  "<span style=\"font-family:", font_chinese, ";\">深度区间</span>",
  "<span style=\"font-family:", font_english, ";\">/ (cm)</span>"
)
threshold_label <- data.frame(
  x = 2.0 + x_upper * 0.015,
  y = 0.58,
  label = paste0(
    "<span style=\"font-family:", font_chinese, ";\">参考值 </span>",
    "<span style=\"font-family:", font_english, ";\">2.0 MPa</span>"
  )
)

# ── 14｜绘制区间柱状图 ────────────────────────────────────────────────────────
figure <- ggplot2::ggplot() +
  ggplot2::geom_vline(
    xintercept = 2.0, color = "#555555", linewidth = 0.42, linetype = "dashed"
  ) +
  ggtext::geom_richtext(
    data = threshold_label,
    ggplot2::aes(x = x, y = y, label = label),
    inherit.aes = FALSE, hjust = 0, vjust = 1,
    fill = "white", label.color = NA,
    label.padding = grid::unit(c(0.4, 0, 0.4, 1.2), "pt"),
    size = annotation_pt / ggplot2::.pt, color = "#555555"
  ) +
  ggplot2::geom_col(
    data = prediction,
    ggplot2::aes(x = estimate, y = y_position, fill = treatment),
    orientation = "y", width = 0.22, alpha = 0.82,
    color = "#202020", linewidth = 0.36
  ) +
  ggplot2::geom_errorbar(
    data = prediction,
    ggplot2::aes(y = y_position, xmin = conf_low, xmax = conf_high),
    orientation = "y", width = 0.09, linewidth = 0.44, color = "#202020"
  ) +
  ggplot2::geom_point(
    data = interval_data,
    ggplot2::aes(x = hardness_mpa, y = y_position, color = treatment),
    shape = 21, fill = "white", size = 1.35, stroke = 0.38, alpha = 0.92
  ) +
  ggplot2::geom_text(
    data = prediction,
    ggplot2::aes(x = letter_x, y = y_position, label = significance_letter),
    family = font_english, fontface = "bold", size = letter_pt / ggplot2::.pt,
    color = "#202020", hjust = 0
  ) +
  ggplot2::scale_fill_manual(
    values = palette, breaks = treatment_order,
    labels = unname(labels_markup[treatment_order]), name = NULL
  ) +
  ggplot2::scale_color_manual(values = palette, guide = "none") +
  ggplot2::scale_x_continuous(
    limits = c(0, x_upper), breaks = scales::breaks_pretty(n = 5),
    expand = ggplot2::expansion(mult = c(0, 0.01))
  ) +
  ggplot2::scale_y_reverse(
    breaks = seq_along(interval_labels), labels = interval_labels,
    limits = c(length(interval_labels) + 0.48, 0.52),
    expand = c(0, 0)
  ) +
  ggplot2::labs(x = x_label, y = y_label) +
  ggplot2::coord_cartesian(clip = "off") +
  ggplot2::theme_bw(base_size = base_pt, base_family = font_english) +
  ggplot2::theme(
    plot.title = ggplot2::element_blank(),
    axis.title = ggtext::element_markdown(size = axis_title_pt, face = "plain", color = "#202020"),
    axis.title.x = ggtext::element_markdown(margin = ggplot2::margin(t = 4)),
    axis.title.y = ggtext::element_markdown(margin = ggplot2::margin(r = 4)),
    axis.text.x = ggplot2::element_text(family = font_english, size = axis_text_pt, color = "#202020"),
    axis.text.y = ggplot2::element_text(family = font_english, size = axis_text_pt, color = "#202020"),
    axis.line = ggplot2::element_blank(),
    panel.border = ggplot2::element_rect(color = "#202020", fill = NA, linewidth = 0.46),
    panel.grid = ggplot2::element_blank(),
    panel.background = ggplot2::element_rect(fill = "white", color = NA),
    legend.position = "top",
    legend.direction = "horizontal",
    legend.justification = "center",
    legend.text = ggtext::element_markdown(size = legend_pt, face = "plain", color = "#202020"),
    legend.key.width = grid::unit(6, "mm"),
    legend.key.height = grid::unit(3.5, "mm"),
    legend.background = ggplot2::element_rect(fill = "white", color = NA),
    legend.margin = ggplot2::margin(0, 0, 1.2, 0, unit = "mm"),
    plot.background = ggplot2::element_rect(fill = "white", color = NA),
    plot.margin = ggplot2::margin(4.5, 5.0, 5.0, 5.0, unit = "mm")
  ) +
  ggplot2::guides(
    fill = ggplot2::guide_legend(
      nrow = 1, byrow = TRUE,
      override.aes = list(alpha = 0.82, color = "#202020", linewidth = 0.36)
    )
  )

# ── 15｜仅生成用户需要的三种白底期刊图 ────────────────────────────────────────
pdf_path <- file.path(root, "土壤硬度_深度区间柱状图.pdf")
png_path <- file.path(root, "土壤硬度_深度区间柱状图.png")
tiff_path <- file.path(root, "土壤硬度_深度区间柱状图.tiff")

ggplot2::ggsave(
  pdf_path, figure, device = grDevices::pdf,
  width = figure_width_mm, height = figure_height_mm, units = "mm", bg = "white"
)
ggplot2::ggsave(
  png_path, figure, device = ragg::agg_png,
  width = figure_width_mm, height = figure_height_mm, units = "mm",
  dpi = 600, bg = "white"
)
ggplot2::ggsave(
  tiff_path, figure, device = ragg::agg_tiff,
  width = figure_width_mm, height = figure_height_mm, units = "mm",
  dpi = 600, bg = "white", compression = "lzw"
)

message("已生成：", pdf_path)
message("已生成：", png_path)
message("已生成：", tiff_path)

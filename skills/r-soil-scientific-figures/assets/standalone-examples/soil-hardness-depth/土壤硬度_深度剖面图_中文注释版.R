#!/usr/bin/env Rscript

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 土壤硬度—深度剖面图｜中文详细注释版
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

# ── 04｜读取直接运行表格，并把中文列名整理为内部变量 ──────────────────────────
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

# ── 05｜校验数值、重复测量标识和独立样品数 ────────────────────────────────────
if (any(!nzchar(dat$sample_id)) || any(!nzchar(dat$treatment_zh))) stop("样本编号和处理不得为空")
numeric_part <- as.matrix(dat[c("depth_cm", "hardness_mpa", "water_pct")])
if (anyNA(numeric_part) || any(!is.finite(numeric_part))) stop("深度、硬度和含水量必须为有限数值")
if (any(dat$depth_cm < 0) || any(dat$hardness_mpa < 0)) stop("深度和硬度不得为负数")
if (any(dat$water_pct <= 0 | dat$water_pct >= 100)) stop("土壤含水量必须位于 0–100% 之间")
if (anyDuplicated(dat[c("sample_id", "depth_cm")])) stop("样本编号×深度必须唯一")

treatment_map <- c("对照" = "Control", "堆肥" = "Compost", "生物炭" = "Biochar")
treatment_order <- unname(treatment_map)
unexpected <- setdiff(unique(dat$treatment_zh), names(treatment_map))
if (length(unexpected)) stop("存在未识别处理：", paste(unexpected, collapse = "、"))
dat$treatment <- factor(unname(treatment_map[dat$treatment_zh]), levels = treatment_order)

sample_treatment_count <- tapply(dat$treatment, dat$sample_id, function(value) length(unique(value)))
if (any(sample_treatment_count != 1L)) stop("同一样本编号不能属于多个处理")
if (any(table(dat$sample_id) < 4L)) stop("每个样品至少需要四个深度测量")
sample_n <- tapply(dat$sample_id, dat$treatment, function(value) length(unique(value)))
if (any(sample_n < 3L)) stop("每个处理至少需要三个独立样品")

depth_levels <- sort(unique(dat$depth_cm))
if (length(depth_levels) < 4L) stop("至少需要四个不同深度")
dat <- dat[order(dat$sample_id, dat$depth_cm), ]
dat$depth_factor <- factor(dat$depth_cm, levels = depth_levels)
water_reference <- mean(dat$water_pct)
dat$water_centered <- dat$water_pct - water_reference

# ── 06｜拟合重复测量混合模型 ──────────────────────────────────────────────────
# 固定效应：处理、离散深度、处理×深度、土壤含水量。
# 随机效应：样本编号随机截距。
# 相关结构：连续 AR(1)，相近深度的同一样品测量允许更强相关。
model <- nlme::lme(
  fixed = hardness_mpa ~ treatment * depth_factor + water_centered,
  random = ~1 | sample_id,
  correlation = nlme::corCAR1(form = ~depth_cm | sample_id),
  data = dat,
  method = "REML",
  na.action = stats::na.fail,
  control = nlme::lmeControl(opt = "optim", msMaxIter = 200, returnObject = TRUE)
)

# ── 07｜在数据平均含水量处计算模型调整均值和 95% 置信区间 ──────────────────
prediction <- expand.grid(
  depth_cm = depth_levels,
  treatment = treatment_order,
  KEEP.OUT.ATTRS = FALSE,
  stringsAsFactors = FALSE
)
prediction$treatment <- factor(prediction$treatment, levels = treatment_order)
prediction$depth_factor <- factor(prediction$depth_cm, levels = depth_levels)
prediction$water_centered <- 0

design <- stats::model.matrix(~treatment * depth_factor + water_centered, prediction)
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
prediction$conf_low <- prediction$estimate - critical * prediction$standard_error
prediction$conf_high <- prediction$estimate + critical * prediction$standard_error
prediction <- prediction[order(prediction$treatment, prediction$depth_cm), ]

# ── 08｜字号根据最终成图尺寸、处理数和深度点数自动计算 ────────────────────────
figure_width_mm <- 105
figure_height_mm <- 118
density_penalty <- 0.14 * log1p(length(depth_levels)) + 0.10 * log1p(length(treatment_order))
base_pt <- max(7.0, min(9.2, 8.9 + 0.006 * (min(figure_width_mm, figure_height_mm) - 90) - density_penalty))
axis_title_pt <- min(10.0, base_pt + 0.8)
axis_text_pt <- max(6.8, base_pt - 0.1)
legend_pt <- max(6.8, base_pt - 0.2)
annotation_pt <- max(6.5, base_pt - 0.6)

# ── 09｜设置颜色、线型和点型；不只依赖颜色区分处理 ──────────────────────────
palette <- c(Control = "#2F6B9A", Compost = "#D47A2A", Biochar = "#5B8E55")
line_types <- c(Control = "solid", Compost = "22", Biochar = "42")
point_shapes <- c(Control = 16, Compost = 17, Biochar = 15)
labels_zh <- c(Control = "对照", Compost = "堆肥", Biochar = "生物炭")
labels_markup <- setNames(vapply(treatment_order, function(value) {
  paste0("<span style=\"font-family:", font_chinese, ";\">", labels_zh[[value]], "</span>")
}, character(1)), treatment_order)

x_label <- paste0(
  "<span style=\"font-family:", font_chinese, ";\">土壤硬度</span>",
  "<span style=\"font-family:", font_english, ";\">/ (MPa)</span>"
)
y_label <- paste0(
  "<span style=\"font-family:", font_chinese, ";\">深度</span>",
  "<span style=\"font-family:", font_english, ";\">/ (cm)</span>"
)

# ── 10｜绘制剖面：原始样品淡线＋模型曲线＋95%置信带＋2 MPa参考线 ─────────
reference_value <- 2.0
x_upper <- max(c(dat$hardness_mpa, prediction$conf_high, reference_value)) * 1.10
depth_upper <- max(dat$depth_cm)
reference_text <- data.frame(
  x = reference_value + x_upper * 0.018,
  y = depth_upper * 0.035,
  label = paste0(
    "<span style=\"font-family:", font_chinese, ";\">参考值 </span>",
    "<span style=\"font-family:", font_english, ";\">2.0 MPa</span>"
  )
)

figure <- ggplot2::ggplot() +
  ggplot2::annotate(
    "rect", xmin = reference_value, xmax = Inf, ymin = -Inf, ymax = Inf,
    fill = "#6F6F6F", alpha = 0.045
  ) +
  ggplot2::geom_vline(
    xintercept = reference_value, color = "#555555", linewidth = 0.42,
    linetype = "dashed"
  ) +
  ggtext::geom_richtext(
    data = reference_text,
    ggplot2::aes(x = x, y = y, label = label),
    inherit.aes = FALSE, hjust = 0, vjust = 0,
    fill = NA, label.color = NA,
    label.padding = grid::unit(rep(0, 4), "pt"),
    size = annotation_pt / ggplot2::.pt, color = "#555555"
  ) +
  ggplot2::geom_path(
    data = dat,
    ggplot2::aes(x = hardness_mpa, y = depth_cm, color = treatment, group = sample_id),
    linewidth = 0.30, alpha = 0.13, lineend = "round"
  ) +
  ggplot2::geom_ribbon(
    data = prediction,
    ggplot2::aes(y = depth_cm, xmin = conf_low, xmax = conf_high, fill = treatment, group = treatment),
    orientation = "y", alpha = 0.18, color = NA
  ) +
  ggplot2::geom_path(
    data = prediction,
    ggplot2::aes(x = estimate, y = depth_cm, color = treatment, linetype = treatment, group = treatment),
    linewidth = 0.78, lineend = "round"
  ) +
  ggplot2::geom_point(
    data = prediction,
    ggplot2::aes(x = estimate, y = depth_cm, color = treatment, shape = treatment),
    size = 1.75, stroke = 0.38
  ) +
  ggplot2::scale_color_manual(
    values = palette, breaks = treatment_order,
    labels = unname(labels_markup[treatment_order]), name = NULL
  ) +
  ggplot2::scale_fill_manual(values = palette, guide = "none") +
  ggplot2::scale_linetype_manual(values = line_types, guide = "none") +
  ggplot2::scale_shape_manual(values = point_shapes, guide = "none") +
  ggplot2::scale_x_continuous(
    limits = c(0, x_upper), breaks = scales::breaks_pretty(n = 5),
    expand = ggplot2::expansion(mult = c(0, 0.015))
  ) +
  ggplot2::scale_y_reverse(
    limits = c(depth_upper, 0), breaks = scales::breaks_pretty(n = 7),
    expand = ggplot2::expansion(mult = c(0.015, 0.025))
  ) +
  ggplot2::labs(x = x_label, y = y_label) +
  ggplot2::coord_cartesian(clip = "off") +
  ggplot2::theme_bw(base_size = base_pt, base_family = font_english) +
  ggplot2::theme(
    plot.title = ggplot2::element_blank(),
    axis.title = ggtext::element_markdown(size = axis_title_pt, face = "plain", color = "#202020"),
    axis.title.x = ggtext::element_markdown(margin = ggplot2::margin(t = 4)),
    axis.title.y = ggtext::element_markdown(margin = ggplot2::margin(r = 4)),
    axis.text = ggplot2::element_text(family = font_english, size = axis_text_pt, color = "#202020"),
    axis.line = ggplot2::element_blank(),
    panel.border = ggplot2::element_rect(color = "#202020", fill = NA, linewidth = 0.46),
    panel.grid.major.y = ggplot2::element_line(color = "#E4E4E4", linewidth = 0.25),
    panel.grid.major.x = ggplot2::element_blank(),
    panel.grid.minor = ggplot2::element_blank(),
    panel.background = ggplot2::element_rect(fill = "white", color = NA),
    legend.position = "top",
    legend.direction = "horizontal",
    legend.justification = "center",
    legend.text = ggtext::element_markdown(size = legend_pt, face = "plain", color = "#202020"),
    legend.key.width = grid::unit(8, "mm"),
    legend.key.height = grid::unit(3.5, "mm"),
    legend.background = ggplot2::element_rect(fill = "white", color = NA),
    legend.margin = ggplot2::margin(0, 0, 1.2, 0, unit = "mm"),
    plot.background = ggplot2::element_rect(fill = "white", color = NA),
    plot.margin = ggplot2::margin(4.5, 5.0, 5.0, 5.0, unit = "mm")
  ) +
  ggplot2::guides(
    color = ggplot2::guide_legend(
      nrow = 1, byrow = TRUE,
      override.aes = list(alpha = 1, linewidth = 0.8)
    )
  )

# ── 11｜仅生成用户需要的三种白底期刊图 ────────────────────────────────────────
pdf_path <- file.path(root, "土壤硬度_深度剖面图.pdf")
png_path <- file.path(root, "土壤硬度_深度剖面图.png")
tiff_path <- file.path(root, "土壤硬度_深度剖面图.tiff")

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

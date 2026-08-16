# R 科研绘图包路线图

## 目录

1. [选择原则](#选择原则)
2. [基础图形与组合](#基础图形与组合)
3. [土壤专用](#土壤专用)
4. [生态、微生物组与多组学](#生态微生物组与多组学)
5. [空间、地统计与遥感](#空间地统计与遥感)
6. [模型、效应与诊断](#模型效应与诊断)
7. [导出、字体与交互](#导出字体与交互)
8. [依赖策略](#依赖策略)

## 选择原则

优先顺序：模型/领域对象的官方绘图或公开 accessor → `ggplot2` 稳定 API → 维护活跃的扩展 → 自定义 `grid`/geom。包能画图不等于分析方法合适。

核对包时优先运行：

```r
packageVersion("ggplot2")
packageDescription("aqp")[c("Version", "URL", "BugReports")]
citation("vegan")
```

2025 年发布的 `ggplot2` 4.0.0 将内部面向对象系统迁移到 S7，后续 4.0.x 持续更新。不要操作 `ggplot_build()` 后的未承诺内部结构或复制旧扩展的内部 hack；优先公开 API，并在项目锁文件中记录实际版本。

## 基础图形与组合

| 任务 | 首选包 | 常用入口 | 备注 |
| --- | --- | --- | --- |
| 图形语法 | `ggplot2` | `ggplot()`、`geom_*()`、`stat_*()`、`facet_*()` | 常规统计图主干；核对 3.5/4.x 兼容 |
| 数据整形 | `dplyr`、`tidyr`、`forcats` | `summarise()`、`pivot_longer()`、`fct_*()` | 转换写入脚本，不在 aes 中隐藏复杂计算 |
| 多面板 | `patchwork` | `plot_layout()`、`plot_annotation()` | ggplot 对象优先 |
| grob 对齐/抽图例 | `cowplot` | `plot_grid()`、`get_legend()` | 处理混合对象时检查裁切 |
| 分布/不确定性 | `ggdist` | `stat_halfeye()`、`stat_slabinterval()`、`stat_dotsinterval()` | raincloud、half-eye、quantile dots、posterior |
| 蜂群/准随机点 | `ggbeeswarm` | `geom_beeswarm()`、`geom_quasirandom()` | 小/中样本原始点 |
| Ridgeline | `ggridges` | `geom_density_ridges()` | 记录带宽和归一化 |
| 标签避让 | `ggrepel` | `geom_text_repel()` | 不用标签筛选替代数据筛选 |
| 集合交并 | `ComplexUpset`、`UpSetR` | `upset()` | 新项目通常优先 ggplot 兼容的 ComplexUpset |
| 流/冲积 | `ggalluvial` | `geom_alluvium()`、`geom_stratum()` | 先验证流量守恒和 ID |
| 圆弧/连接/复杂 geom | `ggforce` | `geom_arc_*()`、`geom_link*()`、`facet_zoom()` | 仅按任务使用 |
| 多色标 | `ggnewscale` | `new_scale_fill()` | 图例语义必须清晰 |
| 网络 | `igraph`、`ggraph`、`tidygraph` | layout + `geom_edge_*()` | 布局、权重、阈值和 seed 可追溯 |
| 弦图/环形热图 | `circlize` | `chordDiagram()`、`circos.*()` | 高维时易拥挤，主文慎用 |
| 复杂热图 | `ComplexHeatmap` | `Heatmap()`、`HeatmapAnnotation()` | Bioconductor；保留矩阵和聚类参数 |
| 三元图 | `ggtern` | `ggtern()` | 通用 simplex；确认三项闭合 |
| 定性/连续色板 | `colorspace`、`viridisLite`、`scico`、`khroma` | `scale_*_*()` | 语义和背景优先 |

## 土壤专用

| 子领域 | 包 | 图形/入口 | 来源与状态 |
| --- | --- | --- | --- |
| 定量土壤剖面 | `aqp` | `plotSPC()`、`groupedProfilePlot()`、深度函数 | CRAN/USDA-NCSS 维护文档；核心 |
| 美国土壤数据库 | `soilDB` | 获取/整理 profile 与 map unit，配合 `aqp` | CRAN；数据版本另记 |
| 土壤调查工具 | `sharpshootR` | profile comparison、diagnostic summaries | CRAN；配合 `aqp` |
| 层状数据样条 | `mpspline2` | mass-preserving spline 后画 depth slices | CRAN；记录边界/标准深度 |
| 土壤质地 | `soiltexture` | `TT.plot()`、分类与转换 | CRAN；支持多分类体系 |
| ggplot 质地三角 | `ggsoiltexture` | ggplot2 风格 texture plot | 维护者仓库/论文；使用前核对安装源和版本 |
| 土壤物理 | `soilphysics` | 粒径、容重、持水等分析输出 | CRAN；核对函数定义 |
| 水力参数 | `soilwater`、`soilhypfit`、`SoilHyP`、`HydroMe` | 持水/导水模型输出后显式作图 | CRAN；不同模型和单位不可拼接 |
| 土壤碳模型 | `SoilR`、`rCTOOL` | 碳库/通量/响应轨迹 | CRAN；区分模型状态和观测 |
| 气体通量 | `ConFluxPro`、`neonSoilFlux` | chamber fit、flux diagnostics | CRAN；原始浓度—时间拟合也要审计 |
| 土壤测试校准 | `soiltestcorr` | correlation/calibration outputs | CRAN/SoftwareX；临界值给不确定性 |
| 肥力模型 | `Rquefts` | 养分供应/产量响应 | CRAN；模型假设进入图注 |
| 土壤质量指数 | `soilassessment`、`SQIpro`、`SQI` | 指标/评分可视化 | CRAN；避免雷达图替代原指标表 |
| 土壤食物网 | `soilfoodwebs` | food-web analysis outputs | CRAN；网络边和能流含义要区分 |
| WRB/Soil Taxonomy | `soilKey`、`SoilTaxonomy` | 分类结果树/流程图 | CRAN；记录分类体系版本 |
| 土壤光谱 | `prospectr`、`hyperSpec`、`pls` | 光谱、预处理、系数/重要性 | CRAN/Bioconductor；验证集不可泄漏 |

土壤包只提供对象/方法入口时，用公开 accessor 整理到长表再交给 `ggplot2`。不要读取 S4 slot 或未导出函数来追求样式。

## 生态、微生物组与多组学

| 任务 | 包 | 常用图 | 关键点 |
| --- | --- | --- | --- |
| 群落生态/排序 | `vegan` | PCA/CA/RDA/CCA/dbRDA/NMDS、varpart、rarecurve | 通过 `scores()` 等公开 accessor；报告 scaling/stress/distance |
| 多样性外推 | `iNEXT` | rarefaction/extrapolation | 覆盖度与样本量轴不可混淆 |
| 微生物组对象 | `phyloseq` | composition、ordination、taxa plots | 数据变换与对象一致 |
| 微生物组探索 | `microViz` | ordination、composition、heatmap | Bioconductor/维护者文档；安装源需核对 |
| 微生物组整洁可视化 | `MicrobiotaProcess` | taxonomy tree、ordination、abundance | Bioconductor |
| 分类群热树 | `metacoder` | `heat_tree()` | PLOS 软件论文/CRAN |
| 系统发育树 | `ggtree` | tree + annotations | Bioconductor；branch length/root/support |
| 树外圈注释 | `ggtreeExtra` | `geom_fruit()` | Bioconductor；面板尺度审计 |
| 差异丰度 | `DESeq2`、`edgeR`、`limma`、`ANCOMBC` | MA/volcano/effect plots | 作图必须使用正式模型结果和调整值 |
| 富集/通路 | `clusterProfiler`、`enrichplot` | dotplot、cnetplot、emapplot、GSEA curve | 背景集和校正方法 |
| 序列 logo | `ggseqlogo` | sequence logo | 信息量/概率语义 |
| 多组学矩阵 | `ComplexHeatmap`、`mixOmics`、`MOFA2` | heatmap、circos、loading/score | 标准化、块权重、模型诊断 |
| 生态网络 | `bipartite`、`igraph`、`ggraph` | bipartite/node-link/motif | sampling effort、stability、non-causal |
| 稳定同位素 | `SIBER`、`MixSIAR` | isotope ellipses、mixing posterior | 分馏和源不确定性 |

## 空间、地统计与遥感

| 任务 | 包 | 入口 | 关键点 |
| --- | --- | --- | --- |
| 矢量 | `sf` | `st_read()`、`st_transform()`、`geom_sf()` | CRS、几何有效性、投影 |
| 栅格 | `terra` | `rast()`、`project()`、`resample()`、`plot()` | resampling、NoData、对齐 |
| 数据立方/时空栅格 | `stars` | `read_stars()`、`geom_stars()` | 维度、时间、深度和像元 |
| 静态/交互专题图 | `tmap` | `tm_shape()`、`tm_raster()`、`tm_polygons()` | plot/view 模式分开 |
| 基础 ggplot 地图 | `ggplot2` + `sf` | `geom_sf()`、`coord_sf()` | 不用底图 CRS 做分析 |
| 地图元素 | `ggspatial` | `annotation_scale()`、`annotation_north_arrow()` | 按用途添加，不机械化 |
| 地统计 | `gstat` | `variogram()`、`fit.variogram()`、`krige()` | 变异函数和空间 CV |
| 点格局 | `spatstat.*` | intensity、K/L、envelopes | 观测窗、边界修正 |
| 空间权重/自相关 | `spdep` | Moran/LISA、neighbors | 邻接定义、多重检验 |
| 空间/时空 CV | `CAST`、`blockCV`、`mlr3spatiotempcv` | folds、AOO/DI | 防止随机 CV 乐观偏差 |
| 双变量地图 | `biscale` | bivariate classes/legend | 分级敏感性和二维图例 |
| 栅格/矢量配色地图 | `tidyterra` | `geom_spatraster()` 等 | 仍保留 terra 对象语义 |
| 卫星数据立方 | `sits`、`rstac`、`gdalcubes` | time series/cubes | 数据源、云、合成、缩放 |
| 光谱/遥感 | `RStoolbox`、`terra` | indices、classification、composites | 传感器/产品级别 |
| Web 地图 | `leaflet`、`mapview` | interactive layers | 另交付静态图和数据替代 |
| 三维地形/体 | `rayshader`、`rgl`、`plotly` | surface/volume/point cloud | 真 3D 数据才使用；比例和视角 |
| 图上饼/条 glyph | `scatterpie`、`scatterbar` | spatial proportions | 点位重叠、面积/条宽和组成 |

`raster`、`sp` 等旧代码在文献中仍常见；新项目默认迁移到 `terra`/`sf`，但复现旧论文时记录原版本并避免无验证的机械替换。

## 模型、效应与诊断

| 任务 | 包 | 常用输出 | 注意 |
| --- | --- | --- | --- |
| 模型效应/对比 | `emmeans`、`marginaleffects`、`ggeffects` | contrasts、conditional effects | 模型尺度/响应尺度和参考值 |
| 混合模型 | `lme4`、`nlme`、`glmmTMB` | fitted/residual/random effects | 图不替代模型诊断 |
| GAM | `mgcv`、`gratia` | smooths、derivatives、difference smooths | basis、k、simultaneous interval |
| 通用诊断 | `performance`、`see`、`DHARMa` | residual/dispersion/QQ | 按模型族解释 |
| 回归/分类评估 | `yardstick`、`pROC` | ROC/PR/calibration/confusion | 使用外部或交叉验证预测 |
| 机器学习解释 | `DALEX`、`iml`、`vip` | importance、PDP/ALE、residuals | 相关特征、背景数据 |
| SHAP | `fastshap`、`shapviz` | beeswarm、dependence、waterfall | 输出尺度、基线、近似误差 |
| 贝叶斯 | `bayesplot`、`ggdist`、`tidybayes` | PPC、trace/rank、half-eye | 先诊断再展示结果 |
| Meta 分析 | `metafor`、`meta` | forest/funnel/Baujat/influence | 异质性和选择偏倚 |
| 规格曲线 | `specr` 或原论文代码 | specification curve | 规格集合需事前/透明定义 |
| SEM/path | `lavaan`、`semPlot`、`piecewiseSEM` | path diagram、effects | 标准化系数和因果假设 |
| DAG | `dagitty`、`ggdag` | causal DAG | 图形表达假设而非证明 |

## 导出、字体与交互

| 任务 | 包/设备 | 备注 |
| --- | --- | --- |
| 高质量 PNG/TIFF | `ragg` | 字体/抗锯齿稳定；按物理尺寸和 `res` |
| SVG | `svglite` | 检查字体依赖和编辑性 |
| PDF | `cairo_pdf`、`pdf` | 嵌字、透明度和特殊字形需实测 |
| 字体发现/排版 | `systemfonts`、`textshaping` | 记录实际 font face |
| 自定义字体 | `showtext` | 可能栅格/路径化；投稿前检查 |
| 局部栅格化 | `ggrastr`、`scattermore` | 保留轴/文字为矢量，记录 raster dpi |
| 交互 | `plotly`、`ggiraph` | hover 不能替代图注/数据表/静态后备 |
| 动画 | `gganimate` | 补充材料；静态关键帧不可缺 |
| 可复现环境 | `renv` | 锁定项目依赖，不在 skill 中全局固定版本 |

## 依赖策略

```r
required <- c("ggplot2", "ragg")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing)) {
  stop("Missing packages: ", paste(missing, collapse = ", "),
       ". Install in the project environment before running.")
}
```

- 不在绘图脚本中无提示 `install.packages()`；这会改变环境并妨碍复现。
- Bioconductor 包用与 R/Bioconductor release 相容的 `BiocManager` 环境。
- 开发版仅在必要时固定 commit，并记录仓库和 SHA。
- 用 `renv::snapshot()` 或等价锁文件保存实际项目，不把全生态绑死在 skill 编写日的版本。
- 复现论文时优先还原原版本；升级时分别验证统计结果和渲染结果。

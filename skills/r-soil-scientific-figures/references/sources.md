# 来源、检索范围与证据登记

## 目录

1. [证据层级](#证据层级)
2. [核心来源](#核心来源)
3. [R 与领域官方来源](#r-与领域官方来源)
4. [近期与命名图形论文](#近期与命名图形论文)
5. [现有公开技能比较](#现有公开技能比较)
6. [本次检索范围和边界](#本次检索范围和边界)
7. [更新记录协议](#更新记录协议)

## 证据层级

1. `primary-method` / `primary-domain` / `primary-software`：原始图形或方法论文、领域首次/关键应用、软件原始论文、标准或实验设计/统计方法原文；
2. `official-software`：R、CRAN、Bioconductor、包维护者官方参考和 vignette；
3. `systematic-review`：系统综述、分类学或跨期刊计量研究；
4. `expert-guidance`：同行评议的可视化指南/清单；
5. `discovery-gallery`：图库、博客、新闻或搜索结果，仅用于发现术语；
6. `example-paper`：领域论文实例，证明使用场景，不证明图形最优。

技术选择至少有 `official-software` 支持；统计/新图结论优先 `primary-method`。图库不能单独作为权威依据。

## 核心来源

| Key | 类型 | 来源 | 用途 | 访问/版本 |
| --- | --- | --- | --- | --- |
| `R-CTVS` | official-software | [CRAN Task Views](https://cran.r-project.org/web/views/) | R 领域包入口和范围说明 | 2026-08-16 |
| `R-CRAN-MAC` | official-software | [R for macOS](https://cran.r-project.org/bin/macosx/) | macOS 官方二进制、架构和构建工具入口 | R 4.6.1；页面更新 2026-06-25；访问 2026-08-16 |
| `R-CRAN-WIN` | official-software | [R for Windows](https://cran.r-project.org/bin/windows/base/) | Windows 官方 64 位二进制与系统要求 | R 4.6.1；页面更新 2026-06-26；访问 2026-08-16 |
| `R-CTV-SPATIAL` | official-software | [CRAN Spatial Task View](https://cran.r-project.org/web/views/Spatial.html) | `sf`/`terra`/`stars`、地图、地统计、空间分析 | version 2026-05-26 |
| `R-CTV-AGRI` | official-software | [CRAN Agriculture Task View](https://cran.r-project.org/web/views/Agriculture.html) | 农业试验与领域包 | 2026-08-16 |
| `R-CTV-ENV` | official-software | [CRAN Environmetrics Task View](https://cran.r-project.org/web/views/Environmetrics.html) | 生态环境、多元和时空分析 | version 2023-12-18；使用时重查 |
| `R-CTV-COMP` | official-software | [CRAN CompositionalData Task View](https://cran.r-project.org/web/views/CompositionalData.html) | 质地、地球化学、微生物组闭合数据 | 2026-08-16 |
| `R-CTV-HYDRO` | official-software | [CRAN Hydrology Task View](https://cran.r-project.org/web/views/Hydrology.html) | 水文时间序列和模型 | 2026-08-16 |
| `R-CTV-OMICS` | official-software | [CRAN Omics Task View](https://cran.r-project.org/web/views/Omics.html) | 多组学和矩阵图 | 2026-08-16 |
| `R-CTV-DYNAMICVISUALIZATIONS` | official-software | [CRAN Dynamic Visualizations Task View](https://cran.r-project.org/web/views/DynamicVisualizations.html) | 动画、交互和动态图形 | 2026-08-16 |
| `R-CTV-CHEMPHYS` | official-software | [CRAN ChemPhys Task View](https://cran.r-project.org/web/views/ChemPhys.html) | 化学计量学、光谱和计算物理 | 2026-08-16 |
| `R-CTV-GRAPHICALMODELS` | official-software | [CRAN Graphical Models Task View](https://cran.r-project.org/web/views/GraphicalModels.html) | 图模型、结构方程和网络结构 | 2026-08-16 |
| `R-CTV-CAUSALINFERENCE` | official-software | [CRAN Causal Inference Task View](https://cran.r-project.org/web/views/CausalInference.html) | 因果假设、DAG 与效应估计 | 2026-08-16 |
| `R-BIOC` | official-software | [Bioconductor software packages](https://bioconductor.org/packages/release/bioc/) | 复杂热图、微生物组、系统发育、空间组学 | 当前 release；使用时记录 |
| `R-GGPLOT` | official-software | [ggplot2 reference](https://ggplot2.tidyverse.org/reference/) | ggplot2 公共 API | 使用时记录版本 |
| `R-GGPLOT-NEWS` | official-software | [ggplot2 changelog](https://ggplot2.tidyverse.org/news/index.html) | 4.0.x 变化和兼容性 | 4.0.3 页面，访问 2026-08-16 |
| `R-EXTS` | discovery-gallery | [ggplot2 extensions](https://exts.ggplot2.tidyverse.org/) | 发现扩展；逐包回到官方文档核验 | 2026-08-16 |
| `R-GALLERY` | discovery-gallery | [R Graph Gallery](https://r-graph-gallery.com/) | 发现约 50 类、400+ 示例；不是技术权威 | 2026-08-16 |
| `R-AQP` | official-software | [aqp official documentation](https://ncss-tech.github.io/aqp/) | SoilProfileCollection、剖面草图 | 2026-08-16 |
| `R-VEGAN` | official-software | [vegan official documentation](https://vegandevs.github.io/vegan/) | 群落生态、排序、差异、varpart | 2026-08-16 |

## 出版社与土壤期刊当前图件规范

这些来源只建立可配置的期刊 profile，不产生全局固定字号。目标期刊的具体作者指南优先于出版社通则；初投与终稿要求必须分开核对。

| Key | 类型 | 来源 | 当前支持的规则 | 访问 |
| --- | --- | --- | --- | --- |
| `J-NATURE-FIGURES` | official-journal | [Nature research figure guide](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/) | 89/183 mm 栏宽、170 mm 最大高度、最终 5–7 pt、可编辑矢量文字、紧凑面板、颜色可访问性 | 2026-08-16 |
| `P-ELSEVIER-ART` | official-publisher | [Elsevier artwork sizing](https://www.elsevier.com/about/policies-and-standards/author/artwork-and-media-instructions/artwork-sizing) | 90/140/190 mm 参考宽度、7 pt 正文与 6 pt 上下标经验下限、300/500/1000 dpi 分类 | 2026-08-16 |
| `P-ELSEVIER-FORMATS` | official-publisher | [Elsevier artwork formats checklist](https://www.elsevier.com/about/policies-and-standards/author/artwork-and-media-instructions/artwork-formats-checklist) | EPS/PDF/TIFF/JPEG/Office 接收范围、物理尺寸、图注与独立文件检查 | 2026-08-16 |
| `J-GEODERMA-GFA` | official-journal | [Geoderma guide for authors](https://www.sciencedirect.com/journal/geoderma/publish/guide-for-authors) | 图件独立文件、标题不放图内、矢量字体嵌入、300/500/1000 dpi、色觉可访问 | 2026-08-16 |
| `J-SSSAJ-GFA` | official-journal | [Soil Science Society of America Journal author information](https://acsess.onlinelibrary.wiley.com/hub/journal/14350661/productinformation) | SSSAJ 当前作者说明和 ASA/CSSA/SSSA publication guide 入口 | 2026-08-16 |
| `P-WILEY-FIGURES` | official-publisher | [Wiley figure preparation](https://authorservices-ppd.wiley.com/author-resources/Journal-Authors/Prepare/manuscript-preparation-guidelines.html/figure-preparation.html) | 图件引用、编号、线图矢量格式、影像 300 dpi 等通用入口 | 2026-08-16 |

## R 与领域官方来源

| Key | 来源 | 覆盖 |
| --- | --- | --- |
| `R-AQP-PLOT` | [Create Soil Profile Sketches](https://ncss-tech.github.io/aqp/reference/SoilProfileCollection-plotting-methods.html) | `plotSPC()` 语义与参数 |
| `R-SOILTEXTURE` | [CRAN soiltexture](https://cran.r-project.org/package=soiltexture) | 质地三角、分类、转换 |
| `R-GGTERN` | [ggtern documentation](https://ggtern.com/) | ggplot2 风格三元图 |
| `R-GGDIST` | [ggdist documentation](https://mjskay.github.io/ggdist/) | slab/interval、half-eye、quantile dots |
| `R-COMPLEXHEATMAP` | [ComplexHeatmap](https://bioconductor.org/packages/ComplexHeatmap/) | 复杂热图、OncoPrint、注释 |
| `R-GGTREE` | [ggtree](https://bioconductor.org/packages/ggtree/) | 系统发育树与注释 |
| `R-PHYLOSEQ` | [phyloseq](https://bioconductor.org/packages/phyloseq/) | 微生物组对象与可视化 |
| `R-MICROVIZ` | [microViz](https://bioconductor.org/packages/microViz/) | 微生物组探索图 |
| `R-TERRA` | [terra](https://rspatial.github.io/terra/) | 栅格处理与绘图 |
| `R-SF` | [sf](https://r-spatial.github.io/sf/) | 矢量、CRS 和 `geom_sf()` |
| `R-GSTAT` | [gstat](https://r-spatial.github.io/gstat/) | 变异函数、克里金、时空地统计 |
| `R-TMAP` | [tmap](https://r-tmap.github.io/tmap/) | 静态/交互专题图 |
| `R-CAST` | [CAST](https://hannameyer.github.io/CAST/) | 空间 CV、适用域与预测 |
| `R-COLORS` | [colorspace](https://colorspace.R-Forge.R-project.org/) | HCL 色板和颜色诊断 |
| `R-SCICO` | [scico](https://thomasp85.r-universe.dev/scico) | 科学色图的 R 实现 |

## 近期与命名图形论文

| Key | 类型 | 引文/链接 | 用途 |
| --- | --- | --- | --- |
| `P-SOIL-R-2025` | systematic-review | Gao et al. (2025), [The Integration and Growth of R in Soil Research](https://pmc.ncbi.nlm.nih.gov/articles/PMC12202774/), doi:10.1002/ece3.71545 | 2014–2023 十个主要土壤期刊的 R/包使用；`vegan`、`ggplot2` 等证据 |
| `P-JAMBOR-2025` | expert-guidance | Jambor (2025), [A checklist for designing and improving the visualization of scientific data](https://www.nature.com/articles/s41556-025-01684-z), doi:10.1038/s41556-025-01684-z | 清晰、可访问和设计清单 |
| `P-IMAGE-2024` | expert-guidance | Schmied et al. (2024), [Community-developed checklists for publishing images and image analyses](https://www.nature.com/articles/s41592-023-01987-9), doi:10.1038/s41592-023-01987-9 | 影像、分析和报告清单 |
| `P-COLOR-2020` | primary-method/guidance | Crameri et al. (2020), [The misuse of colour in science communication](https://www.nature.com/articles/s41467-020-19160-7), doi:10.1038/s41467-020-19160-7 | 科学色图、感知均匀性和色觉风险 |
| `P-REVEAL-2019` | systematic-review/guidance | Weissgerber et al. (2019), [Reveal, Don't Conceal](https://pubmed.ncbi.nlm.nih.gov/31657957/), doi:10.1161/CIRCULATIONAHA.118.037777 | 连续数据不应只用柱图；按设计显示数据 |
| `P-RAINCLOUD` | primary-method | Allen et al. (2019/2021), [Raincloud plots](https://pmc.ncbi.nlm.nih.gov/articles/PMC6480976/), doi:10.12688/wellcomeopenres.15191.2 | raincloud 定义和实现 |
| `P-ESTIMATION` | primary-method | Ho et al. (2019), [Moving beyond P values](https://pubmed.ncbi.nlm.nih.gov/31217592/), doi:10.1038/s41592-019-0470-3 | estimation graphics |
| `P-SUPERPLOT` | primary-method | Lord et al. (2020), [SuperPlots](https://pubmed.ncbi.nlm.nih.gov/32346721/), doi:10.1083/jcb.202001064 | 子样本与独立重复层级 |
| `P-MULTIVERSE-2026` | primary-method | [Visualizing vastness: Graphical methods for multiverse analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC12875576/) | 2026 multiverse plot 和 R 代码 |
| `P-SCATTERBAR-2025` | primary-software | Velazquez & Fan (2025), [scatterbar](https://academic.oup.com/bioinformatics/article/41/2/btaf047/), doi:10.1093/bioinformatics/btaf047 | 空间坐标上的组成条 glyph |
| `P-SOIL-LANDSCAPE-2025` | primary-domain | [Representing soil landscapes from digital soil mapping products](https://soil.copernicus.org/articles/11/849/2025/), doi:10.5194/soil-11-849-2025 | x-y-depth/4D 土壤景观表达 |
| `P-DSM-UNCERTAINTY-2024` | primary-domain | Rohmer et al. (2024), [Prediction uncertainty through local attribution](https://soil.copernicus.org/articles/10/679/2024/), doi:10.5194/soil-10-679-2024 | 数字土壤制图不确定性归因图 |
| `P-ENV-VIZ-2021` | expert-guidance | [Recommendations for scientific visualization with large environmental datasets](https://doi.org/10.1016/j.envsoft.2021.105113) | 大型环境数据的聚合、维度和真实性 |
| `P-META-TAXONOMY` | systematic-review | Kossmeier et al. (2020), [Graphical displays for meta-analysis](https://link.springer.com/article/10.1186/s12874-020-0911-9), doi:10.1186/s12874-020-0911-9 | 200+ meta 分析图形及分类 |
| `P-GENOMIC-TAXONOMY` | systematic-review | Nusrat et al., [Tasks, Techniques, and Tools for Genomic Data Visualization](https://arxiv.org/abs/1905.02853) | 基因组图形任务分类；用原出版版核对 |
| `P-METACODER` | primary-software | Foster et al. (2017), [Metacoder](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005404), doi:10.1371/journal.pcbi.1005404 | heat tree |
| `P-GGSEQLOGO` | primary-software | Wagih (2017), [ggseqlogo](https://academic.oup.com/bioinformatics/article/33/22/3645/3980251), doi:10.1093/bioinformatics/btx469 | sequence logo |

## 现有公开技能比较

访问 2026-08-16：

| Skill | 优点 | 缺口 | 本 skill 的处理 |
| --- | --- | --- | --- |
| [scientific-plotting-skill](https://github.com/dazhiyang/scientific-plotting-skill) | MIT；ggplot2/plotnine、常用栏宽、矢量导出、Wong/viridis | 规则强制单一字体/字号、连续色量化、几乎无土壤领域/统计设计/脚本审计 | 只作市场基准；不复制强制规则；按语义选色和统计结构 |
| [K-Dense scientific-visualization](https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/scientific-visualization) | MIT；科学完整性、可访问性、导出与审计全面 | Python/Matplotlib/Seaborn/Plotly；无 R 土壤专项 | 借鉴通用审计思想；独立实现 R/土壤资源和来源 |

未发现一个公开 skill 同时覆盖 R、土壤剖面/质地/水文、生态/微生物组、空间/地统计、论文新图、机器可检索目录和实际输出审计。这个结论只代表本次公开网络检索，不代表封闭仓库或未来新增项目。

## 本次检索范围和边界

检索日期：2026-08-16。使用中英文关键词组合，包括 R scientific plotting skill、publication figure、chart taxonomy、soil data visualization、soil profile、texture triangle、water retention、digital soil mapping、geostatistics、microbiome、ordination、uncertainty、recent visualization、2024–2026 R visualization package 等。

覆盖策略：

- 以 CRAN/Bioconductor/维护者文档建立包与函数入口；
- 以系统综述和分类论文建立图形家族；
- 以土壤与相邻学科方法/软件论文补领域图；
- 以 2024–2026 方法论文/期刊示例识别近期用法；
- R Graph Gallery 等仅补别名和长尾发现；
- 不复制论文整图，不下载受限内容到 skill。

“几乎覆盖所有”在这里指：覆盖主要科学任务、研究设计和土壤相关领域的图形家族，并保留长尾索引与更新协议；不声称读完全球全部论文，也不把无限组合样式计为有限全集。

## 更新记录协议

新增或变更来源时记录：

```text
source_key:
title:
authors_or_maintainer:
year_or_version:
doi_or_url:
source_tier:
accessed:
supports:
limitations:
license_or_reuse_note:
```

每次更新：

1. 检查 URL/DOI 和官方包状态；
2. 对 `recent-*` 重新判断是否已经成熟或被替代；
3. 用 `figure_catalog.py validate` 检查来源键；
4. 运行 R 模板和审计脚本；
5. 不因包更新静默改变统计默认值；记录迁移影响。

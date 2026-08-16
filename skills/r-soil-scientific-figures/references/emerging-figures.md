# 新兴、近期与仍在演化的科研图形

## 目录

1. [如何定义“最新”](#如何定义最新)
2. [近期方法与领域用法](#近期方法与领域用法)
3. [现代但非最新的高价值图](#现代但非最新的高价值图)
4. [采用门槛](#采用门槛)
5. [监测协议](#监测协议)

## 如何定义“最新”

“论文最近使用”不等于“图形最近发明”。将条目分为：

- `recent-method`：论文提出新的统计—视觉结构并提供定义/代码；
- `recent-domain-use`：成熟编码适应新型土壤、空间或组学数据；
- `recent-software`：新 R 包降低实现门槛，但图形本身可能很旧；
- `revived-composite`：旧图层的新组合或近年来流行；
- `style-only`：手绘、配色或主题更新，不当作新科学图。

## 近期方法与领域用法

### Multiverse plot（2026，recent-method）

把大量合理分析规格的效应分布与分箱后的分析决策 dashboard 组合，旨在弥补传统 specification curve 在规格非常多时的可读性问题。适合土壤研究中的模型/协变量/异常值/空间尺度敏感性分析。不能把任意数据挖掘结果称为 multiverse；规格集合要可辩护并透明记录。原论文提供 R 代码。来源：`P-MULTIVERSE-2026`。

### Spatial scatterbar（2025，recent-domain-use/recent-software）

在空间坐标位置上用小型条形 glyph 显示组成比例，面向空间转录组提出；其编码可迁移到土壤微生物组、团聚体组分或土壤覆盖组成。与 scatterpie 相比，条形可能更利于同位置内类别比较，但密集点位会严重遮挡。它不是所有空间组成数据的默认方案，通常要配套聚合、放大或 small multiples。来源：`P-SCATTERBAR-2025`。

### 3D/4D soil-landscape representation（2025，recent-domain-use）

近期数字土壤制图工作强调把 x–y 地理空间、深度以及可选时间一起表达，而不是只交付单张表层图。推荐静态主文使用对齐深度切片、剖面截面或地图—深度联动面板；真 3D/交互体图作为补充，因为遮挡和视角影响比较。来源：`P-SOIL-LANDSCAPE-2025`。

### Local attribution maps for prediction uncertainty（2024，recent-domain-use）

在预测图和不确定性图之外，把局部特征归因映射到空间，用于解释某处为何不确定。适合数字土壤制图，但 SHAP/归因图对相关协变量、背景数据和模型尺度敏感，不具有因果含义。至少同时给全局性能、空间 CV、原始不确定性和适用域。来源：`P-DSM-UNCERTAINTY-2024`。

### Bivariate prediction–uncertainty and value-suppressing maps（evolving）

把预测值与不确定性共同编码，常用色相×明度或离散二维图例。优点是节省面板，缺点是解码负担和色觉风险。主文可与独立预测/不确定性面板比较后决定；二维图例、断点和超范围必须明确。它是成熟思想的持续发展，不标成单一新发明。

### Depth-slice and voxel/space–depth–time small multiples（evolving）

标准深度切片、截面、Hovmöller 式 depth×time 图及体素图用于土壤水分、温度、碳库和数字土壤平台。优先 2D 对齐切片以支持精确比较；动画/交互只做补充，并保留静态关键帧。

### Quantile dotplots and dots-interval uncertainty（ongoing adoption）

用固定数量的点表示分布概率质量，比密度更便于频率化解读；`ggdist::stat_dotsinterval()` 可实现。适合预测/后验/情景不确定性。点数和离散化决定分辨率，不能把点当真实观测。其研究基础早于 2024，属于持续采用，不称“2026 新图”。

### Accessible multimodal figures（2024+，delivery innovation）

统计图的可访问性开始从配色扩展到结构化描述、可访问数据表、触觉/声音/交互多模态。R 主图仍要有可打印静态后备；alt text 不替代图注，交互 hover 不替代键盘和数据访问。属于交付方式发展，不是新的统计图形。

## 现代但非最新的高价值图

### Raincloud plot（2019/2021）

半密度 + 原始点 + 箱线/区间的组合。用于独立组分布；嵌套或配对设计需改成 superplot/paired estimation，不能用漂亮云层隐藏实验单位。来源：`P-RAINCLOUD`。

### Estimation graphics（2019）

把原始数据与效应量及区间并置，Gardner–Altman/Cumming 是典型布局。特别适合土壤处理效应、配对前后、肥料响应比较。来源：`P-ESTIMATION`。

### Superplots（2020）

同时显示子样本与独立实验/生物重复，解决伪重复和再现性表达。土壤培养、酶活、温室盆栽、多视野成像很适合。来源：`P-SUPERPLOT`。

### Half-eye / slab-and-interval（2018+ 生态成熟）

把分布密度、点估计和区间合并，适合贝叶斯后验、bootstrap 和预测分布。必须定义 slab 的统计来源和 interval。

### UpSet（2014）和 OncoPrint/复杂热图

不是新图，但在多组学、分类群集合和多污染物阈值交集中仍优于多集合 Venn；复杂热图可以整合树、注释和多矩阵。不要因版面复杂而忽略尺度和聚类参数。

### Specification curve（2020）

显示分析规格对结果的影响；当规格极多时可考虑 2026 multiverse plot。任何规格图都不能将不合理模型混入以制造“稳健”。

## 采用门槛

采用近期图形前回答：

1. 它是否比常规图更直接回答科学问题？
2. 读者无需专门训练能否在 10–20 秒内读出主要关系？
3. 统计量、归一化、布局和软件实现是否有可核对定义？
4. 静态印刷、灰度、色觉和缩小版是否仍可读？
5. 是否需要常规备选图用于审稿或补充材料？
6. 该图是否只是主题/配色/圆形布局的换皮？
7. 包是否维护、能否返回可编辑对象、是否能在项目版本上运行？

新图若增加解码成本而不增加证据信息，保留为探索或补充图。

## 监测协议

每次用户要求“最新”时重新检索：

- CRAN Task Views：Agriculture、Spatial、SpatioTemporal、Environmetrics、Hydrology、CompositionalData、Omics、Phylogenetics、MetaAnalysis、DynamicVisualizations；
- Bioconductor release/devel 的 `Visualization`、`Spatial`、`Microbiome`、`SingleCell`、`Software` 视图；
- ggplot2 官方 changelog 和扩展 gallery；
- 近 24–36 个月的 SOIL、Geoderma、Catena、Soil Biology & Biochemistry、Applied Soil Ecology、European Journal of Soil Science、Vadose Zone Journal、Environmental Modelling & Software、Methods in Ecology and Evolution、Bioinformatics、Nature Methods/Cell Biology 等方法或图形论文；
- 软件论文的 CRAN/Bioconductor/GitHub release、citation 和 archived 状态。

保存检索日期、查询、纳入/排除标准、DOI/URL、图形定义和 R 实现。不要下载或重新分发受版权保护的论文整图；记录图名、图注信息、方法和合法链接。

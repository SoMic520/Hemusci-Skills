# 图形分类与选择逻辑

## 目录

1. [分类原则](#分类原则)
2. [先按科学任务选家族](#先按科学任务选家族)
3. [再按研究设计修正](#再按研究设计修正)
4. [多变量与高维数据](#多变量与高维数据)
5. [组合图与别名](#组合图与别名)
6. [低优先级或高风险图](#低优先级或高风险图)

## 分类原则

目录以“科学任务 × 数据结构 × 研究设计 × 视觉编码”为主轴，不把每个主题、配色或排版变体都当作新图。一个图可属于多个家族；目录中的 `primary_family` 表示主要用途。

条目成熟度：

- `canonical`：跨学科长期使用、语义稳定；
- `domain-standard`：某领域成熟的专用图；
- `composite`：多个成熟层组合成的命名图；
- `recent-method`：近年论文提出了新的统计/编码结构；
- `recent-domain-use`：旧编码在近期领域数据中形成新用法；
- `niche`：有效但使用场景窄；
- `caution`：可生成，但默认不推荐。

## 先按科学任务选家族

| 科学任务 | 首选家族 | 常用图 | 关键判断 |
| --- | --- | --- | --- |
| 查看单变量形状 | distribution | 点图、蜂群、直方、密度、ECDF、箱线、小提琴、raincloud | `n`、离散/连续、尾部、带宽 |
| 比较组别 | comparison | 原始点 + 组估计/区间、Cleveland 点图、配对线、slopegraph | 独立/配对/嵌套、估计层级 |
| 比较效应 | effect-uncertainty | forest、Gardner–Altman、Cumming、caterpillar、marginal effects | 效应定义、参考组、区间 |
| 连续变量关系 | relationship | 散点、hexbin、二维密度、拟合线/带、部分效应 | 非线性、异方差、密度、因果边界 |
| 时间/顺序变化 | temporal | line、step、spaghetti、ribbon、calendar、event timeline | 间隔、缺测、重复、平滑 |
| 深度/垂直结构 | profile | 深度剖面、层位草图、depth × property heatmap、截面 | 深度方向、层厚、界面、同一剖面依赖 |
| 组成与闭合数据 | composition | 100% stacked、ternary、balance、alluvial、heatmap | 和为常数、零值、绝对/相对量 |
| 多元结构 | multivariate | PCA/RDA/CCA/NMDS、biplot、pair plot、parallel coordinates | 变换、距离、scaling、解释率/stress |
| 矩阵与模式 | matrix | heatmap、clustered heatmap、correlation、distance、dot matrix | 排序、聚类、色标、缺失 |
| 集合交并 | set | UpSet、Euler、Venn | 集合数和交集复杂度；>3 集合优先 UpSet |
| 网络与层级 | network-hierarchy | node-link、bipartite、hive、tree、dendrogram、tree+heatmap | 权重、方向、布局稳定性、系统发育含义 |
| 空间分布 | spatial | sample map、choropleth、raster、contour、proportional symbol | CRS、支持域、分类、分辨率 |
| 空间预测 | spatial-prediction | observed/predicted/residual/uncertainty/applicability panels | 验证方式、外推、误差和不确定性 |
| 模型性能 | model-diagnostic | residual、QQ、calibration、ROC/PR、confusion、PDP/ALE/SHAP | 任务类型、数据泄漏、验证集 |
| 流程与机制 | schematic | workflow、DAG、path diagram、conceptual model | 数据图与概念图分开，方向和证据层级 |
| 影像/体数据 | image-volume | montage、overlay、segmentation、orthoslice、MIP、isosurface | 校准、处理、比例尺、颜色混合 |

## 再按研究设计修正

| 设计 | 必须体现 | 合适形式 | 常见错误 |
| --- | --- | --- | --- |
| 独立组 | 观测 + 组估计 | beeswarm/strip + interval、box/violin + points | 只画 mean ± SE 柱 |
| 配对 | 配对身份和差值 | paired dot/line、Gardner–Altman paired | 打散成独立组 |
| 重复测量 | 个体轨迹、时间和相关结构 | spaghetti + model trend、small multiples | 用每时点独立检验代替纵向结构 |
| 嵌套 | 层级和真正实验重复 | superplot、cluster means + raw points、mixed-model effects | 把子样本数当 `n` |
| 区组/裂区 | 区组、主区和子区 | block small multiples、paired-by-block、model contrasts | 忽略随机化单位 |
| 深度层 | 采样区间和同剖面相关 | step/profile/ribbon、depth × time heatmap | 点放在层顶却当层中心 |
| 梯度 | 连续趋势和原始散点 | scatter + model band、partial effect | 任意切组导致信息损失 |
| 空间样点 | 位置、支持域和采样设计 | sample map + distribution + variogram | 只画插值面，不画样点 |
| 组成 | 闭合与分母 | ternary/balance/100% stack | 对相对丰度逐类独立解释 |
| 多响应 | 共同尺度或标准化依据 | heatmap/dot matrix/ordination | 不同单位直接共轴 |

## 多变量与高维数据

- 先区分探索性排序、约束排序、监督预测和可解释性。PCA、RDA、PLS、UMAP、SHAP 回答的问题不同。
- PCA/PCoA/RDA/CCA 图必须说明输入变换、中心化/标准化、距离或约束、轴解释量和 score scaling。
- NMDS 必须给出 stress 和距离；轴本身没有 PCA 式解释率。
- UMAP/t-SNE 主要显示局部邻域，不以二维距离代表全局效应大小，不把簇的视觉分离直接解释为显著差异。
- Parallel coordinates、Andrews curves 和 star glyphs 适合探索；变量多时优先聚类热图、small multiples 或降维后验证。
- 高维模型解释中，变量重要性、PDP、ICE、ALE 和 SHAP 不可互换；强相关变量和空间泄漏会改变解释。

## 组合图与别名

- Raincloud = 半小提琴/密度 + 原始点 + 可选箱线/区间；新意在组合，不是新的概率估计。
- Superplot = 子样本点 + 独立实验/生物重复汇总，重点是层级，不是特定 geom。
- Estimation plot = 原始数据面板 + 效应量/差值分布面板；Gardner–Altman 和 Cumming 是布局变体。
- Bubble plot、balloon plot 和 dot heatmap 常共享“位置 + 点面积/颜色”编码；目录按领域别名保留，但必须让面积而非半径对应数量。
- Alluvial、Sankey、parallel sets、river plot 在实现和语义上有差异，均属于 flow；是否守恒、是否有时间方向必须说明。
- Joyplot 是 ridgeline 的流行别名；目录以 ridgeline 为规范名。
- Feature plot 在单细胞/空间组学中通常是嵌入或坐标散点按特征着色，不是独立几何。

## 低优先级或高风险图

- **饼图/环形图**：仅用于少量、差异明显、和为整体的类别；精确比较优先点图或条形。
- **雷达图/星形图**：轴顺序和尺度可改变形状；只在少对象、共同且有意义的尺度下使用，并提供表或平行坐标备选。
- **圆形条形图**：角度和半径妨碍比较；除非周期性是数据语义，否则用线性布局。
- **装饰性 3D 柱/饼/面积**：默认禁止。真正三维空间、表面或体数据除外。
- **双 y 轴**：默认改为对齐面板或指数化后共同尺度；若物理转换一一对应，可明确转换关系。
- **词云**：不能精确比较频率；科研结论优先排序点/条形。
- **未经说明的平滑线**：展示方法、参数和不确定性，检查边界和外推。
- **只给分级预测图**：连续预测被人为断点改变；同时提供连续色标或断点敏感性。

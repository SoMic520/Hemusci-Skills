# 土壤及相关学科图形图谱

## 目录

1. [土壤发生、分类与剖面](#土壤发生分类与剖面)
2. [土壤物理与水文](#土壤物理与水文)
3. [土壤化学、肥力与污染](#土壤化学肥力与污染)
4. [土壤生物、生态与微生物组](#土壤生物生态与微生物组)
5. [农学与长期定位试验](#农学与长期定位试验)
6. [温室气体、碳氮磷循环与稳定同位素](#温室气体碳氮磷循环与稳定同位素)
7. [数字土壤制图与地统计](#数字土壤制图与地统计)
8. [遥感、高光谱与近地传感](#遥感高光谱与近地传感)
9. [水环境、水化学与地球化学](#水环境水化学与地球化学)
10. [模型、机器学习与综合证据](#模型机器学习与综合证据)

以下是问题到图形的优先映射，不代替方法选择。任何模型图必须来自已经验证的模型对象。

## 土壤发生、分类与剖面

| 问题 | 主图 | 补充图 | R 入口 | 必查项 |
| --- | --- | --- | --- | --- |
| 展示单个或多个土壤剖面 | soil profile sketch | horizon property labels、位置图 | `aqp::plotSPC()` | 层顶/层底、土色、截断底界、深度方向 |
| 比较不同景观/土类的剖面 | grouped profile plot | profile dendrogram、属性深度曲线 | `aqp::groupedProfilePlot()` | 分组顺序、层位对应不等同 |
| 描述土色随深度变化 | Munsell/hex profile | hue-value-chroma 小倍图 | `aqp` + `munsell` | 光源/湿润状态、转换误差 |
| 展示层位属性的连续深度函数 | step/depth profile | spline + uncertainty ribbon | `aqp`、`mpspline2`、`ggplot2` | 层厚支持、样条假设、深度轴反向 |
| 展示多剖面的属性分布 | depth × profile heatmap | median/IQR depth profile | `ComplexHeatmap`、`ggplot2` | 剖面排序、缺测深度、标准深度切片 |
| 土壤质地分类 | texture triangle | 组别椭圆/密度、深度分面 | `soiltexture`、`ggsoiltexture`、`ggtern` | 粒径体系、闭合 100%、分类版本 |
| 三种矿物/组分组成 | ternary plot | simplex density、composition balance | `ggtern`、`compositions` | 零值和闭合效应 |
| 地貌—土壤序列/catena | transect profile composite | elevation/terrain + profile sketches | `ggplot2` + `aqp` + `patchwork` | 水平距离、垂直夸张、位置对应 |
| 古土壤/沉积层序 | stratigraphic log | grain-size curve、年代/代理指标面板 | `ggplot2`、`deeptime` | 年代方向、层界、断层/缺失 |
| 分类层级和土类关系 | dendrogram/tree/sunburst | confusion matrix | `dendextend`、`igraph`、`ggtree` | 层级来源和版本 |

## 土壤物理与水文

| 问题 | 主图 | 补充图 | R 入口 | 必查项 |
| --- | --- | --- | --- | --- |
| 水分特征/持水曲线 | observed points + fitted retention curve | residuals、parameter intervals | `ggplot2` + model output | θr/θs、吸力符号、log 轴、模型形式 |
| 非饱和导水率 | K(h) 或 K(θ) 曲线 | log-scale residuals | `ggplot2` | 单位、log 变换、零值 |
| 入渗过程 | cumulative infiltration + rate panels | fitted curve、residual | `ggplot2` | 累积量与速率分面、时间零点 |
| 土壤水分随时间和深度 | depth × time heatmap | sensor lines、event annotation | `ggplot2::geom_raster()`、`stars` | 传感器深度、缺测、插值与事件 |
| 湿润锋/剖面水分 | depth profile small multiples | contour/Hovmöller | `ggplot2` | 采样时点、深度方向 |
| 导水率/容重/孔隙度组间比较 | raw points + interval | raincloud/box | `ggdist`、`ggbeeswarm` | 样芯为实验单位还是子样本 |
| 粒径分布 | cumulative PSD curve | differential density | `ggplot2` | 粒径 log 轴、累计方向、筛分/激光体系 |
| 孔径分布 | pore-size density/cumulative curve | 影像/阈值敏感性 | `ggplot2` | 换算模型、分辨率下限 |
| 团聚体稳定性 | size-class composition + MWD interval | cumulative fraction | `ggplot2` | 湿筛分级、闭合组成、独立重复 |
| 压实和贯入阻力 | depth profile ribbon | soil moisture co-panel | `ggplot2` | 水分条件、深度相关、仪器上限 |
| 水文过程 | hydrograph + precipitation aligned panel | flow duration curve、event hysteresis | `ggplot2`、`hydroTSM` | 不用误导性双轴、真实时间间隔 |
| 溶质突破 | breakthrough curve C/C0 | residence-time distribution | `ggplot2` | 孔隙体积、基线、删失值 |
| 优先流/染色 | binary/intensity image + profile | connected components、depth fraction | `terra`、`EBImage`、`ggplot2` | 阈值、尺度、原始影像保留 |

## 土壤化学、肥力与污染

| 问题 | 主图 | 补充图 | R 入口 | 必查项 |
| --- | --- | --- | --- | --- |
| 多指标组间比较 | dot/interval small multiples | standardized heatmap | `ggplot2`、`emmeans` | 单位分面、模型对比、不要雷达化替代 |
| pH/养分随深度 | depth profiles | depth × treatment heatmap | `ggplot2` | 同剖面相关、层厚 |
| 肥料响应 | dose-response curve + interval | economic optimum、residuals | `drc`/`nls`/`mgcv` + `ggplot2` | 模型、有效范围、外推 |
| 土壤测试与产量校准 | scatter + calibration classes | Cate–Nelson/quadrant、bootstrap CI | `soiltestcorr`、`ggplot2` | 临界值不确定性、独立验证 |
| 吸附等温线 | observed + Langmuir/Freundlich fits | residual/AIC comparison | `minpack.lm`、`ggplot2` | 竞争模型、浓度单位、误差结构 |
| 反应动力学 | concentration/time curves | transformed diagnostic only as supplement | `nls`、`nlme`、`ggplot2` | 不用线性化图替代非线性拟合 |
| 重金属/污染物空间格局 | sample map + prediction + uncertainty | hotspot/local Moran | `sf`、`terra`、`gstat`、`tmap` | 检出限、背景值、空间验证 |
| 污染风险等级 | continuous concentration + threshold overlays | category map | `ggplot2`、`tmap` | 标准版本、断点闭区间 |
| 化学形态/连续提取 | composition bars/ternary | alluvial across steps | `ggplot2`、`ggalluvial` | 闭合、回收率、步骤顺序 |
| 多元素指纹 | clustered heatmap | PCA/biplot、parallel coordinates | `ComplexHeatmap`、`vegan` | 标准化、低于检出限、共线性 |
| 混合物/配方试验 | simplex response contour | desirability map | `ggtern`、`mixexp` | 设计空间、闭合约束、外推 |
| 酸碱缓冲/滴定 | titration curve | first derivative/equivalence points | `ggplot2` | 平滑方法和等当点算法 |

## 土壤生物、生态与微生物组

| 问题 | 主图 | 补充图 | R 入口 | 必查项 |
| --- | --- | --- | --- | --- |
| α 多样性 | raw points + interval | rarefaction/extrapolation | `phyloseq`、`vegan`、`iNEXT` | 深度标准化、独立样本、指标定义 |
| β 多样性 | PCoA/NMDS with uncertainty/hulls | distance distribution、PERMANOVA design | `vegan`、`phyloseq`、`microViz` | 距离、变换、stress、dispersion |
| 环境约束群落结构 | RDA/CCA/dbRDA triplot | variance partition | `vegan` | scaling、约束、条件变量、置换设计 |
| 相对丰度组成 | stacked composition + sample order | heatmap/absolute abundance | `phyloseq`、`microViz` | 分母、稀有类合并、绝对量限制 |
| 分类群差异 | effect/interval or dot heatmap | volcano/MA only with valid model | `DESeq2`/`ANCOMBC` output + `ggplot2` | 多重校正、组成偏差、效应方向 |
| 物种/OTU/ASV 模式 | clustered heatmap | prevalence-abundance scatter | `ComplexHeatmap`、`microViz` | 变换、排序、零值 |
| 分类层级差异 | heat tree | tree + heatmap/bar | `metacoder`、`MicrobiotaProcess`、`ggtree` | 分类数据库版本、层级聚合 |
| 系统发育关系 | phylogram/fan tree | tree + abundance/trait rings | `ggtree`、`ggtreeExtra` | branch length、root、support |
| 共现/互作 | network with stability encoding | adjacency heatmap、degree distribution | `igraph`、`ggraph` | 推断方法、阈值、稀疏化、非因果 |
| 植物—微生物/多营养级 | bipartite network/alluvial | chord/heatmap | `bipartite`、`ggraph`、`circlize` | 方向、权重、采样努力 |
| 酶活/微生物量组间比较 | nested raw points + experiment means | multivariate heatmap | `ggplot2`、`ggdist` | 技术孔不是独立重复 |
| 生态化学计量 | log-log scatter + model interval | C:N:P ternary | `ggtern`、`ggplot2` | 摩尔/质量比、闭合和尺度 |
| 功能预测/通路 | enrichment dotplot | pathway network、running-score plot | `clusterProfiler`、`enrichplot` | 背景集、富集定义、校正 |

## 农学与长期定位试验

| 问题 | 主图 | 补充图 | R 入口 | 必查项 |
| --- | --- | --- | --- | --- |
| 处理/品种比较 | raw plot means + model contrasts | raincloud or compact letter display | `emmeans` + `ggplot2` | 区组/裂区随机化单位 |
| 多地点多年试验 | site-year effects/forest | interaction heatmap、AMMI/GGE biplot | `metan`、`gge`、`ggplot2` | 环境定义、尺度、稳定性指标 |
| 长期趋势 | repeated time-series with model ribbon | change-point/event annotation | `nlme`/`lme4`/`mgcv` + `ggplot2` | 不规则间隔、轮作/制度变化 |
| 轮作序列 | state/sequence/alluvial | crop calendar heatmap | `ggalluvial`、`ggplot2` | 时间顺序、流量守恒 |
| 产量构成 | dot matrix/stacked components | path/SEM diagram | `ggplot2`、`piecewiseSEM` | 组成与机制不要混淆 |
| 农艺效率 | response curve or quotient interval | frontier plot | `ggplot2` | 分母零值、效率定义 |
| 经济最优施肥 | profit response curve | price-sensitivity fan | `ggplot2` | 价格/成本假设和不确定性 |
| 作物历/物候 | phenology timeline | raster calendar/heatmap | `ggplot2` | 年际对齐、积温/日期 |

## 温室气体、碳氮磷循环与稳定同位素

| 问题 | 主图 | 补充图 | R 入口 | 必查项 |
| --- | --- | --- | --- | --- |
| 气体通量时序 | points/lines by replicate + model trend | event-aligned small multiples | `ggplot2` | 负通量、缺测、不跨缺口连线 |
| 累积排放 | cumulative curve with interval | period contributions | `ggplot2` | 积分算法、起止时间、协方差 |
| 通量脉冲/热区 | event profile/heatmap | quantile/ridgeline | `ggplot2` | 峰值采样频率、平滑 |
| 碳库分配 | stock interval + depth profile | Sankey only when mass-balanced | `ggplot2`、`ggalluvial` | 等质量土层、单位面积、质量守恒 |
| 培养矿化 | observed + kinetic model | rate + residual panels | `nls`/`nlme` + `ggplot2` | 累积/速率、重复结构、参数区间 |
| 化学计量耦合 | scatter/model + bivariate density | ternary/C:N:P triangle | `ggplot2`、`ggtern` | 比值伪相关、质量/摩尔单位 |
| 双稳定同位素 | δ13C–δ15N scatter + ellipses | mixing polygon/posterior | `SIBER`、`MixSIAR` | 基准、分馏、椭圆含义 |
| 混合模型后验 | half-eye/interval forest | posterior predictive check | `ggdist`、`bayesplot` | 先验、区间类型、链诊断 |
| 路径和过程网络 | SEM/path diagram | standardized effects forest | `piecewiseSEM`、`semPlot`、`ggdag` | 因果假设、标准化类型、拟合 |

## 数字土壤制图与地统计

最小论文图组通常包含：采样位置与设计、响应分布、经验变异函数或空间相关诊断、预测图、误差/不确定性图、外推/适用域图和空间交叉验证结果。不要只给一张漂亮预测图。

| 问题 | 主图 | 补充图 | R 入口 | 必查项 |
| --- | --- | --- | --- | --- |
| 采样设计 | sampling map | distance/coverage histogram | `sf`、`tmap`、`spsurvey` | CRS、支持域、抽样权重 |
| 空间相关 | empirical variogram + fitted model | directional variograms、variogram cloud | `gstat` | lag、cutoff、各向异性、稳健估计 |
| 克里金预测 | continuous raster map | kriging variance/SD | `gstat` + `terra` | 变异函数、邻域、反变换 |
| 机器学习土壤预测 | prediction raster | uncertainty/applicability/extrapolation | `terra`、`CAST`、`mlr3spatiotempcv` | 空间 CV、泄漏、训练域 |
| 分类土壤图 | class map | probability/entropy map、confusion | `terra`、`tmap` | 类别色板、概率、面积偏差 |
| 深度切片 | aligned map small multiples | 3D voxel/cross-section | `terra`、`stars`、`patchwork` | 共同色标、深度定义 |
| 4D 土壤景观 | x-y-depth-time slices/animation | interactive volume | `stars`、`plotly`、`rgl` | 插值维度、时间/深度支持 |
| 残差空间结构 | residual map + variogram/Moran | local residual clusters | `sf`、`spdep`、`gstat` | 验证残差而非训练残差 |
| 预测不确定性来源 | local attribution maps | global importance + ALE/SHAP | `DALEX`、`iml`、`fastshap` + map | 相关特征、解释范围、非因果 |
| 双变量空间关系 | bivariate choropleth/raster | scatter + spatially varying coefficient | `biscale`、`tmap` | 3×3 图例、分级敏感性 |
| 多模型共识 | ensemble mean/median + disagreement | model rank/map | `terra`、`ggplot2` | 相同验证和网格、权重 |
| 时空异常 | anomaly map small multiples | Hovmöller/space-time cube | `stars`、`ggplot2` | 基准期、季节性、共同尺度 |

空间图强制规则：

- 经纬度适合交换/显示，不适合直接计算面积、距离、缓冲或密度。选择与研究范围和目的匹配的投影；跨大区域时明确失真权衡。
- `EPSG:3857` 仅用于常见网络底图，不用于土壤面积和距离分析。
- 栅格对齐必须记录 CRS、extent、origin、resolution、resampling 和 NoData；分类栅格不用双线性重采样。
- 分级色标记录算法（等距、分位数、Jenks、阈值等）、精确断点和端点包含规则。
- 预测支持域可能是点、样方、土层或像元；不能只用漂亮连续色表掩盖 change of support。

## 遥感、高光谱与近地传感

| 问题 | 主图 | 补充图 | R 入口 | 必查项 |
| --- | --- | --- | --- | --- |
| 光谱特征 | reflectance spectra + interval | derivative spectra、band annotations | `prospectr`、`ggplot2` | 波长、校正、平滑/导数参数 |
| 高光谱数据立方体 | RGB/composite + spectral profiles | PCA/MNF component maps | `terra`、`stars`、`hyperSpec` | 波段配准、坏波段、单位 |
| 土壤属性光谱模型 | observed-predicted + interval | residual vs predicted、wavelength importance | `pls`、`tidymodels` | 独立/外部验证、样品泄漏 |
| 植被指数/裸土指数时序 | line/ribbon or calendar heatmap | map small multiples | `terra`、`stars`、`ggplot2` | 传感器、合成、云、季节 |
| SAR 土壤水分 | backscatter/soil moisture relationship | incidence-angle panels、maps | `terra`、`ggplot2` | 线性量与 dB、粗糙度、植被 |
| 传感器/模型比较 | Bland–Altman + parity | calibration/error distributions | `ggplot2` | 一致性界限、重复测量 |
| 无人机正射/热红外 | calibrated image/map | transect、distribution | `terra`、`sf` | GSD、配准、辐射校正 |
| 变量重要性波长图 | coefficient/importance spectrum | stability/selection frequency | `ggplot2` | 共线性、重采样稳定性 |

## 水环境、水化学与地球化学

| 问题 | 主图 | 补充图 | R 入口 | 必查项 |
| --- | --- | --- | --- | --- |
| 主离子水化学 | Piper diagram | Schoeller/Stiff/Durov | `hydrogeo` 类包或显式 `ggtern` | 当量浓度、归一化和投影定义 |
| 离子随样点比较 | Schoeller diagram | heatmap | `ggplot2` | log 轴、离子顺序 |
| 水化学空间分布 | point symbols/choropleth | Piper glyph map | `sf`、`tmap`、`scatterpie` | glyph 可读性、面积编码 |
| 水文气候季节性 | hydrograph/seasonal ribbon | Hovmöller、calendar heatmap | `ggplot2`、`hydroTSM` | 水文年、时区、缺测 |
| 滞后/迟滞 | hysteresis loop | event arrows/time color | `ggplot2` | 方向、事件分段、时间编码 |
| 气候模式对比 | Taylor diagram | target diagram、bias/RMSE panels | `openair`/专用函数 + `ggplot2` | 相关、标准差、中心化 RMSE |
| 风向/污染方向 | wind/pollution rose | polar concentration plot | `openair` | calm winds、方向 convention、面积 |
| 时空场 | Hovmöller diagram | map small multiples | `ggplot2::geom_raster()`、`stars` | 坐标和时间方向、共同色标 |

## 模型、机器学习与综合证据

| 问题 | 主图 | 补充图 | R 入口 | 必查项 |
| --- | --- | --- | --- | --- |
| 回归模型检查 | residual/fitted + QQ + leverage | component/residual | `performance`、`see`、base R | 模型族对应诊断 |
| 预测回归性能 | observed-predicted/parity | residual distribution + calibration | `yardstick` + `ggplot2` | 测试/空间 CV、1:1 aspect |
| 分类性能 | confusion + ROC/PR/calibration | decision/threshold curves | `yardstick`、`pROC` | 不平衡时重视 PR、验证集 |
| 模型效应 | conditional effects + interval | raw data overlay | `marginaleffects`、`ggeffects` | 参考值、尺度、交互 |
| 非线性解释 | ALE/PDP + ICE | SHAP dependence | `iml`、`DALEX` | 相关变量、外推 |
| 全局解释 | importance interval/rank | feature effect panels | `vip`、`DALEX` | permutation 数据和重复 |
| 局部解释 | SHAP waterfall/force | spatial SHAP maps | `shapviz`、`fastshap` | 基线、模型输出尺度 |
| 贝叶斯模型 | posterior intervals/half-eye | PPC、trace/rank plots | `bayesplot`、`ggdist` | 收敛、先验、区间 |
| Meta 分析 | forest | funnel、Baujat、influence | `metafor`、`meta` | 异质性、模型、选择偏倚 |
| 多分析选择稳健性 | specification curve/multiverse plot | density/outcome curve | `specr` 或论文代码 | 合理规格集合、不可事后挑选 |
| 路径/结构方程 | path diagram + effects forest | residual/fit diagnostics | `lavaan`、`semPlot`、`piecewiseSEM` | 方向不等于因果、标准化定义 |
| 机制概念模型 | DAG/conceptual diagram | evidence table | `ggdag`、`DiagrammeR` | 区分假设、测量和估计 |

多面板优先把原始证据、效应与诊断放在同一逻辑链中，而不是把所有可生成的图堆进主文。

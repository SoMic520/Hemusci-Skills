# Hemusci Skills 版本记录

本文件记录技能库结构和各技能的正式版本。每个技能独立编号，避免把仓库版本与技能版本混为一谈。

## r-soil-scientific-figures

### v1 · 2026-08-16

- 建立面向土壤及农业、生态、环境、地学、微生物组、遥感和空间统计研究的R科研绘图工作流。
- 收录314种图形、29个图族和35种标准输入规范，并提供研究设计、变量类型、统计任务和领域场景驱动的选图规则。
- 支持从用户数据整理、质量校验和统计分析开始生成图形，也支持识别论文截图并在不臆造数据与统计量的前提下复刻版式。
- 默认每图只交付两份逻辑一致的R代码、代码直接运行的标准输入表、白底PDF、600 dpi白底PNG、600 dpi白底LZW TIFF和一段式中文图注。
- 加入动态字号、宋体与Times New Roman兼容字体、四周完整边框、显著性括号避让、土壤深度方向和深度区间水平柱等期刊级版式约束。
- R代码自动检测并安装缺失的CRAN包，提供macOS和Windows环境、路径、字体和用户包库适配。
- 完成314图目录校验、R语法解析、代表性土壤硬度深度图和通用柱状图三格式实绘回归。

发布包：`dist/r-soil-scientific-figures/r-soil-scientific-figures-skill-20260816-v1.zip`

SHA-256：`205EDAD0BF1C3B8DAD6E7D66491C6518A305FC8A7EE33749A31764EFEC2473FA`

## soil-methods-consultant

### v1 · 2026-08-16

- 建立以本地已校正资料为主、官方线上资源为辅的土壤试验方法咨询与检索流程。
- 收录六套核心参考资料，共1936页；另收录19份已完成复核的近两年检测标准，共309页。可直接检索的资料合计2245页。
- 支持方法选择、精确检索、完整实验方案、方法比较、质量控制和故障排查。
- 要求各来源分别使用，保留原有方法层级、文字、公式、化学式、单位、上下标和PDF页码，不混用不同来源的参数。
- 提供精确检索、单个方法展开、资料状态检查、HTML/PDF实验方案生成和成品检查脚本。
- 默认生成简要、可直接执行的实验方案，突出试剂仪器、编号步骤、结果计算、质控要点和完整出处，不附内部校正原文与追踪字段。

发布包：`dist/soil-methods-consultant/soil-methods-consultant-skill-20260816-v1.zip`

SHA-256：`490DE7D187A93DB1EBBF41A06D3BA6FC7FD40EAF3EF7DC93F02442725F902E8A`

## soil-journal-format-review

### v3 · 2026-08-15

- 将 228 本内置适用期刊按五组逐刊完整写出，不再只用学科类别概括。
- 在技能入口中强制要求：回答“适用于哪些期刊”时必须读取完整名单并逐刊说明。
- 增加清单与 `journal-registry.csv` 的一对一回归测试，防止漏刊、重名或后续不同步。
- 在仓库首页增加五组数量和完整名单入口。
- 补全 README 中该技能在 Codex、Claude Code、GitHub Copilot、Gemini CLI、Cursor、OpenCode 的逐项安装命令，以及 Windows、macOS、Linux 手动安装和通用模型接入指令。
- 新增独立期刊资料库与可审计证据快照：228 本逐刊简介、186 个官方投稿入口、CSCD 2025–2026 与 Scopus 2026-07 状态筛选，并明确中科院分区表自 2026 年起停更。

发布包：`dist/soil-journal-format-review/soil-journal-format-review-skill-20260815-v3.zip`

SHA-256：`012AEB8A7BE32D96C1BD7EBFEACC3EDF0139DFCF842D8B8DFEEC4E76B4BA9069`

### v2 · 2026-08-15

- 建立面向土壤学专业期刊及相关综合性、农业资源环境、生态环境、地学和水土保持期刊的投稿格式工作流。
- 增加期刊官网、官方模板与著录标准的规则取证、冲突处理、时效核验和来源留痕机制。
- 覆盖页面、标题、作者单位、中英文摘要、关键词、正文层级、图表、公式、参考文献、脚注与尾注格式。
- 支持DOCX真实Word批注、格式修订、变更台账、内容指纹比对和OOXML安全审计。
- 增加LibreOffice与Poppler渲染复核、Mac/Windows字体兼容审计及开放字体官方下载流程。
- 明确只审查和修订排版格式，不评价文章质量、创新性、数据、方法、结论或学术观点。
- 增加9项回归测试以及发布包自检、篡改台账拒绝和视觉复核闭环。

发布包：`dist/soil-journal-format-review/soil-journal-format-review-skill-20260815-v2.zip`

SHA-256：`3576BF401BF4B19BF0A1E1D35D0A642DCE39549E52A19D5E004A8E9C608C35EE`

## 仓库结构

### 2026-08-14

- 将仓库定位调整为可持续扩展的多技能中心。
- 采用 `skills/<skill-name>/` 存放技能源码，采用 `dist/<skill-name>/` 存放独立发布包。
- 增加Codex、Claude Code、GitHub Copilot、Gemini CLI、Cursor和OpenCode安装命令。
- 增加DeepSeek、ChatGPT等不支持Agent Skills目录发现机制的平台接入说明。

## soil-third-survey-report

### v10 · 2026-08-14

- 建立省、市、县三级土壤三普专业报告统一工作框架。
- 覆盖总体报告、工作报告、数据报告及主要专题报告。
- 完善土壤术语、数量逻辑、空间尺度、时间基准、证据强度和因果边界检查。
- 完善长段拆分、下级标题识别及三级小节3—5段组织规则。
- 增加正文图表引用位置、说明段顺序、注释后空行和大面积空白处理规则。
- 明确章号及附图编号均从实际报告读取，示例编号不得固化。
- 扩展DOCX接受修订文本、批注、文本框、页眉页脚、脚注尾注和外部关系扫描。
- 增加LibreOffice自动检测和最新稳定版安装流程。
- 增加11项扫描器回归测试和技能一键校验脚本。

发布包：`dist/soil-third-survey-report/soil-third-survey-report-skill-20260814-v10.zip`

SHA-256：`B77FA05C69EF9DD17C849372A00ABD6BB4D38AA980C70C8E54582F7F9070FA62`


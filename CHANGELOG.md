# Hemusci Skills 版本记录

本文件记录技能库结构和各技能的正式版本。每个技能独立编号，避免把仓库版本与技能版本混为一谈。

## soil-methods-consultant

### v1 · 2026-08-16

- 建立本地校正语料优先、官方线上资源辅助的土壤试验方法咨询与检索工作流。
- 纳入六个相互独立的核心来源1 936页，以及19份通过复核门禁的近两年检测标准309页，共2 245个运行时纳入页。
- 支持方法选法、精确检索、完整实验方案、方法比较、质量控制和故障排查。
- 强制保留来源边界、方法层级、文字、公式、化学式、单位、上下标和PDF页码，禁止跨来源静默拼接参数。
- 提供结构化检索、方法卡展开、语料状态检查、HTML/PDF实验方案生成和成品审计脚本。
- 默认生成简要、可直接执行的实验方案，突出试剂仪器、编号步骤、结果计算、质控要点和完整出处，不附内部校正原文与追踪字段。

发布包：`dist/soil-methods-consultant/soil-methods-consultant-skill-20260816-v1.zip`

SHA-256：`4595973E326B4720A867C78591476A6D5ECD5F1347E0FA1ACC4CED6A5B9A5F3F`

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


<div align="center">

# 🧪 Hemusci Skills

**面向科研写作、专业报告、数据分析与成果交付的智能体技能库**

<p>
  <img src="https://img.shields.io/badge/Skills-4-2563EB?style=for-the-badge" alt="Skills 4">
  <img src="https://img.shields.io/badge/Agent%20Skills-Compatible-7C3AED?style=for-the-badge" alt="Agent Skills Compatible">
  <img src="https://img.shields.io/badge/Language-中文-E11D48?style=for-the-badge" alt="中文">
  <img src="https://img.shields.io/badge/Status-持续扩展-0F766E?style=for-the-badge" alt="持续扩展">
</p>

这里不是单一技能项目，而是可持续扩展的专业智能体技能集合。每个技能拥有独立入口、参考资料、脚本、校验规则和发布包。

[在线网站](https://hemusci.com/skills/) · [技能目录](#-技能目录) · [一键安装](#-一键安装) · [通用模型接入](#-deepseekchatgpt-等通用模型) · [新增技能](#-新增技能规范)

</div>

---

## 🧭 技能目录

| 技能 | 状态 | 版本 | 适用范围 |
|---|---:|---:|---|
| [soil-third-survey-report](skills/soil-third-survey-report/) | 稳定 | v10 | 第三次全国土壤普查省、市、县级专业报告撰写、重构、逐段审查、DOCX修订与批注交付 |
| [soil-journal-format-review](skills/soil-journal-format-review/) | 稳定 | v3 | 土壤学及可发表土壤研究的综合期刊投稿排版、格式审查、DOCX修订与批注；不审查文章质量和内容 |
| [soil-methods-consultant](skills/soil-methods-consultant/) | 稳定 | v1 | 基于本地已校正资料和官方标准，提供土壤试验方法咨询、方法选择、精确检索、计算及HTML/PDF实验方案 |
| [r-soil-scientific-figures](skills/r-soil-scientific-figures/) | 稳定 | v1 | 土壤及相关学科科研图选型、统计分析、截图复刻、314图谱检索与R三格式最小可复现交付 |

后续技能统一加入 `skills/<skill-name>/`，发布包置于 `dist/<skill-name>/`。仓库根目录只保留技能索引、版本记录和公共说明。

## 🌱 soil-third-survey-report

首个正式技能以土壤学专业逻辑和“信、达、雅”为文字标准，覆盖总体报告、工作报告、数据报告、土壤类型与制图报告、土壤属性与制图报告、土壤退化与障碍报告、耕地质量等级评价报告、土壤农业利用适宜性报告、特色农产品土壤适宜性评价报告及成果应用报告。

主要能力：

- 逐段、逐句、逐字审查术语、数量关系、空间尺度、时间基准、证据强度和因果边界。
- 整理标题层级和长段落，按内容任务组织小节，避免机械增设标题。
- 检查单位、精度、上下标、表图编号、图表说明段和版面空白。
- 清除管理学套话、编辑提示、空泛升华和模板化AI写作痕迹。
- 以用户指定原始底稿为基础，在DOCX中保留真实修订记录和批注。
- 自动检测LibreOffice；缺失时从官方渠道准备最新稳定版并校验安装包。

详细规则见 [技能入口](skills/soil-third-survey-report/SKILL.md)。

## 📐 soil-journal-format-review

面向土壤学专业期刊及可发表土壤相关研究的综合性、农业资源环境、生态环境、地学与水土保持期刊，建立“期刊规则取证—格式建模—DOCX排版—批注—渲染复核—安全交付”的闭环。

主要能力：

- 以期刊官网、官方模板和现行著录标准为依据建立可追溯的期刊格式档案，避免凭记忆套用格式。
- 审查并修订页面、标题、作者单位、中英文摘要、关键词、正文层级、图表、公式、参考文献、脚注与尾注的排版格式。
- 在DOCX中添加真实Word批注，记录格式问题、规则来源、修改动作和复核状态。
- 使用LibreOffice与Poppler执行跨平台渲染复核，并对Word脚注、尾注和批注进行OOXML结构审计。
- 检测缺失字体，优先使用Mac与Windows兼容字体；仅从官方渠道下载可再分发的开放字体。
- 通过内容指纹、安全扫描和变更台账约束修改范围，不评价研究质量、创新性、数据可信度或学术观点。

详细规则见 [技能入口](skills/soil-journal-format-review/SKILL.md)。

### 内置适用期刊（228 本）

| 分组 | 数量 |
|---|---:|
| 中文土壤学及相关专业期刊 | 53 |
| 中文综合与交叉期刊 | 20 |
| 国际土壤学专业期刊 | 52 |
| 国际土壤学交叉期刊 | 38 |
| 国际综合与跨学科期刊 | 65 |

[查看全部 228 本期刊的逐刊完整名称](skills/soil-journal-format-review/references/applicable-journals.md)。清单中每本期刊均单独写出；详细官网入口、出版社、土壤主题范围和来源状态见 [期刊登记表](skills/soil-journal-format-review/references/journal-registry.csv)。目录用于确定排版能力覆盖范围，不构成期刊质量排名或投稿推荐。

[打开土壤学相关期刊在线资料库](https://hemusci.com/skills/soil-journal-format-review/)，可按刊名、出版社、研究主题和收录状态检索。网页逐刊展示官方投稿入口、主题适配及带版本日期的客观证据：CSCD 2025–2026 核心库/扩展库、Scopus 2026-07 Active/Inactive。网站不做主观星级；北大核心、JCR 与最后一版中科院分区只在取得完整权威版本后展示，其中中国科学院文献情报中心已宣布自 2026 年起停止更新期刊分区表。

## 🧫 soil-methods-consultant

本 skill 用于土壤试验方法咨询和检索。内置资料包括六套已校正的土壤分析参考资料，以及近两年已取得官方全文的检测标准。各来源分别整理，试剂用量、操作条件和公式不交叉混用；线上资料只用于补充缺项或核实标准的现行状态。

主要能力：

- 目前收录六套核心参考资料，共1936页；另收录19份已完成校对的国家标准，共309页。可直接检索的资料合计2245页。
- 支持方法咨询与选择、精确检索、完整实验方案、方法比较、质量控制和故障排查。
- 区分总量、可提取态、交换态和有效态等不同测量对象，不因名称相近而混用方法。
- 保留原方法的篇、章、节、子节和编号顺序，精确保留化学式、公式、单位及上下标。
- 不混用不同来源的试剂、用量、条件、公式或质控限；线上补充优先采用发布机构原文和原始方法论文。
- 基于同一条方法记录生成可直接执行的简要HTML与A4 PDF方案，列明试剂仪器、操作步骤、结果计算、质控要点和完整出处。

详细规则见 [技能入口](skills/soil-methods-consultant/SKILL.md)。

## 📊 r-soil-scientific-figures

面向土壤、农业、生态、环境、生物地球化学、水文、地学、微生物组、遥感、GIS和地统计研究，按照研究设计与数据结构选择图形、完成统计分析、复刻论文截图并生成期刊级R图。

主要能力：

- 建立314种图形、29个图族和35种输入规范的可检索图谱，并按研究问题、变量类型和实验设计选图。
- 支持显著性箱线图、柱状图、土壤剖面、深度区间图、网络、排序、群落、空间、预测和多面板图。
- 将用户原始数据整理为代码直接运行的标准Excel，只保留作图和分析必需字段并保留真实单位。
- 每图默认交付无注释与中文详注R代码、标准输入表、矢量PDF、600 dpi白底PNG、600 dpi白底LZW TIFF和一段式中文图注。
- 根据最终物理版面动态计算字号、边距和标注位置，使用中英文兼容字体、完整四周边框与防重叠布局。
- 独立R脚本检测并安装缺失的CRAN包，兼顾macOS和Windows路径、字体与用户包库。

详细规则见 [技能入口](skills/r-soil-scientific-figures/SKILL.md)。

## ⚡ 一键安装

### 1. 准备 GitHub CLI

`gh skill` 需要 GitHub CLI 2.90.0 或更高版本。仓库已经公开，无需单独申请访问权限；建议先登录GitHub账号，以便获得稳定的API访问额度并管理后续更新。

```powershell
winget install --id GitHub.cli --exact
gh auth login
gh --version
```

已安装时可升级：

```powershell
winget upgrade --id GitHub.cli --exact
```

安装前预览：

```powershell
gh skill preview SoMic520/Hemusci-Skills soil-third-survey-report
gh skill preview SoMic520/Hemusci-Skills soil-journal-format-review
gh skill preview SoMic520/Hemusci-Skills soil-methods-consultant
gh skill preview SoMic520/Hemusci-Skills r-soil-scientific-figures
```

### 2. 安装到常用智能体

#### soil-third-survey-report

| 智能体 | 用户级安装命令 |
|---|---|
| Codex | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent codex --scope user` |
| Claude Code | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent claude-code --scope user` |
| GitHub Copilot | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent github-copilot --scope user` |
| Gemini CLI | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent gemini-cli --scope user` |
| Cursor | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent cursor --scope user` |
| OpenCode | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent opencode --scope user` |

#### soil-journal-format-review

| 智能体 | 用户级安装命令 |
|---|---|
| Codex | `gh skill install SoMic520/Hemusci-Skills soil-journal-format-review --agent codex --scope user` |
| Claude Code | `gh skill install SoMic520/Hemusci-Skills soil-journal-format-review --agent claude-code --scope user` |
| GitHub Copilot | `gh skill install SoMic520/Hemusci-Skills soil-journal-format-review --agent github-copilot --scope user` |
| Gemini CLI | `gh skill install SoMic520/Hemusci-Skills soil-journal-format-review --agent gemini-cli --scope user` |
| Cursor | `gh skill install SoMic520/Hemusci-Skills soil-journal-format-review --agent cursor --scope user` |
| OpenCode | `gh skill install SoMic520/Hemusci-Skills soil-journal-format-review --agent opencode --scope user` |

#### soil-methods-consultant

| 智能体 | 用户级安装命令 |
|---|---|
| Codex | `gh skill install SoMic520/Hemusci-Skills soil-methods-consultant --agent codex --scope user` |
| Claude Code | `gh skill install SoMic520/Hemusci-Skills soil-methods-consultant --agent claude-code --scope user` |
| GitHub Copilot | `gh skill install SoMic520/Hemusci-Skills soil-methods-consultant --agent github-copilot --scope user` |
| Gemini CLI | `gh skill install SoMic520/Hemusci-Skills soil-methods-consultant --agent gemini-cli --scope user` |
| Cursor | `gh skill install SoMic520/Hemusci-Skills soil-methods-consultant --agent cursor --scope user` |
| OpenCode | `gh skill install SoMic520/Hemusci-Skills soil-methods-consultant --agent opencode --scope user` |

#### r-soil-scientific-figures

| 智能体 | 用户级安装命令 |
|---|---|
| Codex | `gh skill install SoMic520/Hemusci-Skills r-soil-scientific-figures --agent codex --scope user` |
| Claude Code | `gh skill install SoMic520/Hemusci-Skills r-soil-scientific-figures --agent claude-code --scope user` |
| GitHub Copilot | `gh skill install SoMic520/Hemusci-Skills r-soil-scientific-figures --agent github-copilot --scope user` |
| Gemini CLI | `gh skill install SoMic520/Hemusci-Skills r-soil-scientific-figures --agent gemini-cli --scope user` |
| Cursor | `gh skill install SoMic520/Hemusci-Skills r-soil-scientific-figures --agent cursor --scope user` |
| OpenCode | `gh skill install SoMic520/Hemusci-Skills r-soil-scientific-figures --agent opencode --scope user` |

安装到当前项目时，将 `--scope user` 改为 `--scope project`。GitHub CLI还支持Qwen Code、Kimi CLI、Cline、Windsurf等智能体，完整标识以 [`gh skill install` 官方手册](https://cli.github.com/manual/gh_skill_install)为准。

更新与检查：

```powershell
gh skill list --scope user
gh skill update soil-third-survey-report
gh skill update soil-journal-format-review
gh skill update soil-methods-consultant
gh skill update r-soil-scientific-figures
```

### 3. 手动安装备用方式

仓库包含多个技能，手动安装时应复制目标技能子目录，不应把整个仓库直接作为一个技能目录。

Windows PowerShell：

```powershell
git clone https://github.com/SoMic520/Hemusci-Skills.git
Copy-Item -Recurse -Force .\Hemusci-Skills\skills\soil-third-survey-report `
  "$env:USERPROFILE\.codex\skills\soil-third-survey-report"
Copy-Item -Recurse -Force .\Hemusci-Skills\skills\soil-journal-format-review `
  "$env:USERPROFILE\.codex\skills\soil-journal-format-review"
Copy-Item -Recurse -Force .\Hemusci-Skills\skills\soil-methods-consultant `
  "$env:USERPROFILE\.codex\skills\soil-methods-consultant"
Copy-Item -Recurse -Force .\Hemusci-Skills\skills\r-soil-scientific-figures `
  "$env:USERPROFILE\.codex\skills\r-soil-scientific-figures"
```

macOS / Linux：

```bash
git clone https://github.com/SoMic520/Hemusci-Skills.git
mkdir -p ~/.codex/skills
cp -R Hemusci-Skills/skills/soil-third-survey-report ~/.codex/skills/
cp -R Hemusci-Skills/skills/soil-journal-format-review ~/.codex/skills/
cp -R Hemusci-Skills/skills/soil-methods-consultant ~/.codex/skills/
cp -R Hemusci-Skills/skills/r-soil-scientific-figures ~/.codex/skills/
```

Claude Code的个人技能目录为 `~/.claude/skills/`，项目技能目录为 `.claude/skills/`；目录规则见 [Claude Code Skills官方文档](https://code.claude.com/docs/en/slash-commands)。

## 🤖 DeepSeek、ChatGPT 等通用模型

不支持Agent Skills目录发现机制的平台，可按知识库方式接入：

1. 从[当前发布包](#-当前发布包)选择目标技能并下载解压。
2. 上传 `SKILL.md` 和 `references/` 全部文件；需要执行文档、数据或绘图流程时同时上传对应的 `assets/` 和 `scripts/`。
3. 根据目标技能选择对应的最高优先级指令。

### soil-third-survey-report 接入指令

```text
完整读取 soil-third-survey-report/SKILL.md，并按其中的任务路由加载所需 references 文件。
用户当前提供的原始报告、验收导引和明确限制优先于通用规则。
逐段、逐句、逐字审查；审稿意见只能进入批注，不得混入正式正文。
不得编造数据、成因和结论，不得以禁词扫描代替土壤专业判断。
```

### soil-journal-format-review 接入指令

```text
完整读取 soil-journal-format-review/SKILL.md，并按任务加载 references、assets 和 scripts。
目标期刊确定后，必须重新核验当前官方模板、作者指南、文章类型和投稿阶段；不得凭记忆套用格式。
只审查和修订投稿排版格式，不评价或改写论文质量、科学内容、方法、统计、结论、语言表达或引文真实性。
DOCX 修订前必须执行安全、结构、脚注尾注、字体和内容基线检查；缺少字体时只从官方渠道取得合法字体。
批注只能记录格式问题、规则来源、修改动作和复核状态；LibreOffice 只用于渲染复核，不得冒充桌面 Word 的批注界面验证。
用户询问适用期刊时，读取 references/applicable-journals.md，按五组完整列出 228 本期刊，不得只用类别概括。
```

### soil-methods-consultant 接入指令

```text
完整读取 soil-methods-consultant/SKILL.md，并先运行 scripts/find_methods.py status，确认本地资料已经完成校对并可用于检索。
以本地已校正资料为主要依据；只有本地缺项或需要核实现行性时，才使用官方线上资源辅助。
按独立来源选择和展开方法，不得跨来源混合试剂、用量、操作条件、公式或质控限。
精确保留方法层级、文字、公式、化学式、单位、上下标和PDF页码；默认生成简要、可执行的HTML与A4 PDF实验方案。
```

### r-soil-scientific-figures 接入指令

```text
完整读取 r-soil-scientific-figures/SKILL.md，并按研究设计和图形任务加载对应 references、assets 和 scripts。
先把用户数据整理成代码直接读取的标准输入表，再从数据校验、统计分析和图形选型开始生成R代码。
每图默认只交付两份逻辑一致的R脚本、标准输入XLSX、白底PDF/600 dpi PNG/600 dpi LZW TIFF和一段式中文图注TXT。
字体、字号、显著性标记、完整边框、深度方向和标签避让必须在最终物理尺寸下实绘验证；不得编造样本、单位、P值或误差类型。
```

## 🗂️ 仓库结构

```text
Hemusci-Skills/
├─ skills/
│  ├─ soil-third-survey-report/
│  ├─ soil-journal-format-review/
│  │  ├─ SKILL.md
│  │  ├─ agents/
│  │  ├─ assets/
│  │  ├─ references/
│  │  └─ scripts/
│  ├─ soil-methods-consultant/
│  │  ├─ SKILL.md
│  │  ├─ agents/
│  │  ├─ references/
│  │  └─ scripts/
│  └─ r-soil-scientific-figures/
│     ├─ SKILL.md
│     ├─ agents/
│     ├─ assets/
│     ├─ references/
│     └─ scripts/
├─ dist/
│  ├─ soil-third-survey-report/
│  │  └─ soil-third-survey-report-skill-20260814-v10.zip
│  ├─ soil-journal-format-review/
│  │  └─ soil-journal-format-review-skill-20260815-v3.zip
│  ├─ soil-methods-consultant/
│  │  └─ soil-methods-consultant-skill-20260816-v1.zip
│  └─ r-soil-scientific-figures/
│     └─ r-soil-scientific-figures-skill-20260816-v1.zip
├─ CHANGELOG.md
└─ README.md
```

## ➕ 新增技能规范

每个新技能至少包含：

```text
skills/<skill-name>/
├─ SKILL.md       # 名称、描述、触发条件、工作流和交付标准
├─ agents/        # 可选：智能体展示与默认提示
├─ references/    # 可选：按任务路由加载的专业规则
└─ scripts/       # 可选：校验、处理或自动化脚本
```

新增时同时完成四项工作：在本页登记技能；执行技能校验；在 `CHANGELOG.md` 记录版本；如需离线分发，在 `dist/<skill-name>/` 生成独立发布包。不同技能不得共享未经声明的隐含规则。

## 📦 当前发布包

- [soil-third-survey-report v10](dist/soil-third-survey-report/soil-third-survey-report-skill-20260814-v10.zip)
- SHA-256：`B77FA05C69EF9DD17C849372A00ABD6BB4D38AA980C70C8E54582F7F9070FA62`
- [soil-journal-format-review v3](dist/soil-journal-format-review/soil-journal-format-review-skill-20260815-v3.zip)
- SHA-256：`012AEB8A7BE32D96C1BD7EBFEACC3EDF0139DFCF842D8B8DFEEC4E76B4BA9069`
- [soil-methods-consultant v1](dist/soil-methods-consultant/soil-methods-consultant-skill-20260816-v1.zip)
- SHA-256：`490DE7D187A93DB1EBBF41A06D3BA6FC7FD40EAF3EF7DC93F02442725F902E8A`
- [r-soil-scientific-figures v1](dist/r-soil-scientific-figures/r-soil-scientific-figures-skill-20260816-v1.zip)
- SHA-256：`205EDAD0BF1C3B8DAD6E7D66491C6518A305FC8A7EE33749A31764EFEC2473FA`

## 🔐 数据与权限

仓库仅存放技能规则、参考资料、脚本和发布包，不包含报告原稿、调查数据、验收材料或项目截图。仓库当前公开可见，但尚未设置开源许可证；公开可见不等同于授予复制、修改、传播或再发布许可，相关使用需获得所有者明确授权。

---

<div align="center">

**Hemusci Skills：让专业智能体按照专业规范工作。**

</div>


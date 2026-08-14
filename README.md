<div align="center">

# 🌱 土壤三普专业报告撰写与审查

**面向第三次全国土壤普查省、市、县三级成果的专业写作、深度审查、修订批注与 DOCX 交付技能**

<p>
  <img src="https://img.shields.io/badge/版本-v10-2F855A?style=for-the-badge" alt="版本 v10">
  <img src="https://img.shields.io/badge/成果层级-省·市·县-2563EB?style=for-the-badge" alt="省市县三级">
  <img src="https://img.shields.io/badge/交付-DOCX修订与批注-7C3AED?style=for-the-badge" alt="DOCX修订与批注">
  <img src="https://img.shields.io/badge/LibreOffice-自动准备-18A303?style=for-the-badge&logo=libreoffice&logoColor=white" alt="LibreOffice">
</p>

以土壤学专业逻辑为底座，以“信、达、雅”为文字标准，输出可送审、可验收、可归档的正式专业报告。

[一键安装](#-一键安装) · [快速使用](#-快速使用) · [核心能力](#-核心能力) · [支持报告](#-支持报告) · [质量规则](#-质量规则) · [版本下载](#-版本下载)

</div>

---

## ✨ 核心能力

| 专业内容 | 篇章结构 | 数据与表图 | DOCX交付 |
|---|---|---|---|
| 土壤术语、指标含义、数量关系、空间尺度与因果边界 | 标题层级、长段拆分、小节组织与论证顺序 | 单位、精度、上下标、评价范围、图表功能与正文支撑 | 原稿保全、真实修订、真实批注、自动目录、题注与逐页检查 |

- 逐段、逐句、逐字审查，不以禁词扫描代替专家判断。
- 正文与审稿意见严格分离，不把“请核实”“以表为准”等编者语言写入正式报告。
- 数据叙述同时检查分母、范围、时期、统计对象和显示精度。
- 识别机械排比、抽象升华、空泛因果、模板化转折等AI写作痕迹。
- 以用户指定原始底稿为唯一修订基础，避免在旧修订稿上反复叠加。
- DOCX任务自动检查LibreOffice；缺失时从官方渠道安装最新稳定版，并校验哈希与数字签名。

## 📚 支持报告

<details open>
<summary><strong>点击查看报告类型</strong></summary>

- 总体报告
- 工作报告
- 数据报告
- 土壤类型与制图报告
- 土壤属性与制图报告
- 土壤退化与障碍报告
- 耕地质量等级评价报告
- 土壤农业利用适宜性报告
- 特色农产品土壤适宜性评价报告
- 成果应用报告

</details>

技能先判定省级、市级或县级成果，再确定汇总单元、比较尺度、篇幅要求和验收重点，不采用简单替换行政区名称的方式套用模板。

## 🧭 质量规则

### 文字与专业性

- 术语稳定：区分含量、储量、面积、比例、发生率、变化量和等级结构。
- 判断克制：显著、普遍、持续、导致等词必须与已有证据强度一致。
- 尺度明确：样点、图斑、地类、县域和全市结果不得越级外推。
- 表达自然：不用口号式、宣传式、管理学套话，不留下模型交流痕迹。

### 段落与标题

- 一个实质性三级小节通常组织3—5段。
- 分析性段落通常控制在500—1000字；段落较多时可适当缩短，但实质性分析段一般不少于300字。
- 标题只在内容确实构成下一级任务时设置，不为拆段而机械增加标题。
- 用户明确要求不改的一、二级标题保持原文、顺序和层级不变。

### 图表与版面

- 图号、表号自然嵌入实质性结果句，通常置于图表说明段第一句句末。
- 图表说明段位于对象之前，按“说明段—空一行—图表及注释—空一行—后续正文”组织。
- 章号取自报告实际章节；“第五章”“图5.44—5.49”等仅为规则示例。
- 出现大面积空白时，在同一小节内调整图表、说明段或分页属性，同时保持图表紧邻主要分析段。

## 🚀 快速使用

先安装技能，再在任务中明确要求使用`soil-third-survey-report`。模型会按任务类型加载相应专业、语言、结构和DOCX规则。

```text
请使用 soil-third-survey-report 技能，以我指定的原始DOCX为底稿，
逐段审查并使用修订模式和批注交付。
```

## ⚡ 一键安装

### 准备GitHub CLI

`gh skill`需要GitHub CLI 2.90.0或更高版本。本仓库为私有仓库，首次安装前须登录有权访问仓库的GitHub账户。

```powershell
winget install --id GitHub.cli --exact
gh auth login
gh --version
```

已经安装GitHub CLI时，可执行：

```powershell
winget upgrade --id GitHub.cli --exact
```

安装前可先预览技能内容：

```powershell
gh skill preview SoMic520/soil-third-survey-report SKILL.md
```

### Codex

```powershell
gh skill install SoMic520/soil-third-survey-report SKILL.md --agent codex --scope user
```

### Claude Code

```powershell
gh skill install SoMic520/soil-third-survey-report SKILL.md --agent claude-code --scope user
```

### GitHub Copilot

```powershell
gh skill install SoMic520/soil-third-survey-report SKILL.md --agent github-copilot --scope user
```

### Gemini CLI

```powershell
gh skill install SoMic520/soil-third-survey-report SKILL.md --agent gemini-cli --scope user
```

### Cursor

```powershell
gh skill install SoMic520/soil-third-survey-report SKILL.md --agent cursor --scope user
```

### OpenCode

```powershell
gh skill install SoMic520/soil-third-survey-report SKILL.md --agent opencode --scope user
```

`gh skill`还支持Qwen Code、Kimi CLI、Cline、Windsurf等智能体。把`--agent`值替换为目标智能体标识即可；完整列表以[`gh skill install`官方手册](https://cli.github.com/manual/gh_skill_install)为准。

### 安装到当前项目

将`--scope user`改为`--scope project`，即可仅对当前项目安装。例如：

```powershell
gh skill install SoMic520/soil-third-survey-report SKILL.md --agent codex --scope project
```

### 更新与检查

```powershell
gh skill list --scope user
gh skill update soil-third-survey-report
```

若需要覆盖本地修改并重新安装：

```powershell
gh skill install SoMic520/soil-third-survey-report SKILL.md --agent codex --scope user --force
```

### Codex手动安装备用方式

```powershell
git clone https://github.com/SoMic520/soil-third-survey-report.git `
  "$env:USERPROFILE\.codex\skills\soil-third-survey-report"
```

### Claude Code手动安装备用方式

```powershell
git clone https://github.com/SoMic520/soil-third-survey-report.git `
  "$env:USERPROFILE\.claude\skills\soil-third-survey-report"
```

Claude Code可自动调用技能，也可使用`/soil-third-survey-report`明确调用。个人技能目录和项目技能目录说明见[Claude Code Skills官方文档](https://code.claude.com/docs/en/slash-commands)。

### DeepSeek、ChatGPT等通用模型

DeepSeek网页端、普通聊天模型和不支持Agent Skills目录的知识库产品，不能用复制目录的方式自动安装。可采用以下接入方法：

1. 下载并解压[最新发布包](dist/soil-third-survey-report-skill-20260814-v10.zip)。
2. 把`SKILL.md`及`references/`目录全部上传到智能体知识库；需要处理DOCX时同时上传`scripts/`目录。
3. 将下面的文字设为系统提示词或智能体最高优先级指令：

```text
你必须完整读取 soil-third-survey-report/SKILL.md，并按其中的任务路由加载所需references文件。
用户当前提供的原始报告、验收导引和明确限制优先于通用规则。
逐段、逐句、逐字审查；审稿意见只能进入批注，不得混入正式正文。
不得编造数据、成因和结论，不得以禁词扫描代替土壤专业判断。
```

4. 每次任务开始时明确报告层级、报告类型、原始底稿及不可修改内容。

## 🧪 本地校验

```powershell
python scripts/test_scan_report_text.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validate_skill.ps1
```

## 🗂️ 仓库结构

```text
soil-third-survey-report/
├── SKILL.md                       # 技能入口与完整工作流程
├── agents/
│   └── openai.yaml                # 技能显示与默认提示
├── references/                    # 专业、语言、结构、格式与DOCX规则
├── scripts/
│   ├── ensure_libreoffice.ps1     # LibreOffice检测与自动安装
│   ├── scan_report_text.py        # DOCX全文与OOXML扫描
│   ├── test_scan_report_text.py   # 回归测试
│   └── validate_skill.ps1         # 一键校验
├── dist/                          # 可下载发布包
├── CHANGELOG.md                   # 版本记录
└── README.md                      # 项目主页
```

## 📦 版本下载

- [下载 soil-third-survey-report v10](dist/soil-third-survey-report-skill-20260814-v10.zip)
- SHA-256：`B77FA05C69EF9DD17C849372A00ABD6BB4D38AA980C70C8E54582F7F9070FA62`

## 🔒 数据与权限

本仓库仅包含技能规则、脚本和发布包，不包含报告原稿、调查数据、验收材料、截图或其他项目文件。仓库当前设为私有，且未设置开源许可证；未经仓库所有者明确授权，不应视为允许公开传播或再发布。

---

<div align="center">

**专业事实写准，复杂内容写清，正式报告写得经得起时间。**

</div>


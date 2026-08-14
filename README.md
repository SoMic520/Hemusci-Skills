<div align="center">

# 🧪 Hemusci Skills

**面向科研写作、专业报告、数据分析与成果交付的智能体技能库**

<p>
  <img src="https://img.shields.io/badge/Skills-1-2563EB?style=for-the-badge" alt="Skills 1">
  <img src="https://img.shields.io/badge/Agent%20Skills-Compatible-7C3AED?style=for-the-badge" alt="Agent Skills Compatible">
  <img src="https://img.shields.io/badge/Language-中文-E11D48?style=for-the-badge" alt="中文">
  <img src="https://img.shields.io/badge/Status-持续扩展-0F766E?style=for-the-badge" alt="持续扩展">
</p>

这里不是单一技能项目，而是可持续扩展的专业智能体技能集合。每个技能拥有独立入口、参考资料、脚本、校验规则和发布包。

[技能目录](#-技能目录) · [一键安装](#-一键安装) · [通用模型接入](#-deepseekchatgpt-等通用模型) · [新增技能](#-新增技能规范)

</div>

---

## 🧭 技能目录

| 技能 | 状态 | 版本 | 适用范围 |
|---|---:|---:|---|
| [soil-third-survey-report](skills/soil-third-survey-report/) | 稳定 | v10 | 第三次全国土壤普查省、市、县级专业报告撰写、重构、逐段审查、DOCX修订与批注交付 |

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

## ⚡ 一键安装

### 1. 准备 GitHub CLI

`gh skill` 需要 GitHub CLI 2.90.0 或更高版本。当前仓库为私有仓库，安装前需登录具有访问权限的GitHub账号。

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
```

### 2. 安装到常用智能体

| 智能体 | 用户级安装命令 |
|---|---|
| Codex | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent codex --scope user` |
| Claude Code | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent claude-code --scope user` |
| GitHub Copilot | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent github-copilot --scope user` |
| Gemini CLI | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent gemini-cli --scope user` |
| Cursor | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent cursor --scope user` |
| OpenCode | `gh skill install SoMic520/Hemusci-Skills soil-third-survey-report --agent opencode --scope user` |

安装到当前项目时，将 `--scope user` 改为 `--scope project`。GitHub CLI还支持Qwen Code、Kimi CLI、Cline、Windsurf等智能体，完整标识以 [`gh skill install` 官方手册](https://cli.github.com/manual/gh_skill_install)为准。

更新与检查：

```powershell
gh skill list --scope user
gh skill update soil-third-survey-report
```

### 3. 手动安装备用方式

仓库包含多个技能，手动安装时应复制目标技能子目录，不应把整个仓库直接作为一个技能目录。

```powershell
git clone https://github.com/SoMic520/Hemusci-Skills.git
Copy-Item -Recurse -Force .\Hemusci-Skills\skills\soil-third-survey-report `
  "$env:USERPROFILE\.codex\skills\soil-third-survey-report"
```

Claude Code的个人技能目录为 `~/.claude/skills/`，项目技能目录为 `.claude/skills/`；目录规则见 [Claude Code Skills官方文档](https://code.claude.com/docs/en/slash-commands)。

## 🤖 DeepSeek、ChatGPT 等通用模型

不支持Agent Skills目录发现机制的平台，可按知识库方式接入：

1. 下载并解压[最新发布包](dist/soil-third-survey-report/soil-third-survey-report-skill-20260814-v10.zip)。
2. 上传 `SKILL.md` 和 `references/` 全部文件；需处理DOCX时同时上传 `scripts/`。
3. 将以下内容设置为智能体的最高优先级指令：

```text
完整读取 soil-third-survey-report/SKILL.md，并按其中的任务路由加载所需 references 文件。
用户当前提供的原始报告、验收导引和明确限制优先于通用规则。
逐段、逐句、逐字审查；审稿意见只能进入批注，不得混入正式正文。
不得编造数据、成因和结论，不得以禁词扫描代替土壤专业判断。
```

## 🗂️ 仓库结构

```text
Hemusci-Skills/
├─ skills/
│  └─ soil-third-survey-report/
│     ├─ SKILL.md
│     ├─ agents/
│     ├─ references/
│     └─ scripts/
├─ dist/
│  └─ soil-third-survey-report/
│     └─ soil-third-survey-report-skill-20260814-v10.zip
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

## 🔐 数据与权限

仓库仅存放技能规则、参考资料、脚本和发布包，不包含报告原稿、调查数据、验收材料或项目截图。仓库当前设为私有，且未设置开源许可证；未经所有者明确授权，不视为允许公开传播或再发布。

---

<div align="center">

**Hemusci Skills：让专业智能体按照专业规范工作。**

</div>


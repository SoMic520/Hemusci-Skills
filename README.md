<div align="center">

![Hemusci 专业智能体技能目录](docs/banner.svg)

# Hemusci Skills

**面向科研写作、数据分析与专业报告的智能体技能**

![独立仓库](https://img.shields.io/badge/独立技能仓库-5-276650?style=flat-square)
![Agent Skills](https://img.shields.io/badge/Agent_Skills-compatible-276650?style=flat-square)
![中文](https://img.shields.io/badge/说明-中文-276650?style=flat-square)

[选择技能](#选择一个技能) · [安装入门](#安装入门) · [原集合使用指南](docs/collection-guide.md) · [Hemusci 网站](https://hemusci.com/skills/)

</div>

## 选择一个技能

五个技能已拆分为独立仓库，每个仓库都有自己的说明、安装入口、参考资料和发布包。根据你现在要完成的任务选择：

| 独立仓库 | 适合的任务 | 技能版本 | 入口 |
| --- | --- | --- | --- |
| [土壤科学与自然科学写作](https://github.com/SoMic520/soil-all-writing) | 从原始底稿到正式交付，让文字与证据对齐。 | v1 | [规则](https://github.com/SoMic520/soil-all-writing/blob/main/skills/soil-all-writing/SKILL.md) · [下载](https://github.com/SoMic520/soil-all-writing/releases/latest) |
| [R 土壤学科研绘图](https://github.com/SoMic520/r-soil-scientific-figures) | 按研究问题选图，把数据、代码与图形一起交付。 | v1 | [规则](https://github.com/SoMic520/r-soil-scientific-figures/blob/main/skills/r-soil-scientific-figures/SKILL.md) · [下载](https://github.com/SoMic520/r-soil-scientific-figures/releases/latest) |
| [土壤学期刊投稿格式审查](https://github.com/SoMic520/soil-journal-format-review) | 依照期刊官方规则，逐项检查投稿文件。 | v3 | [规则](https://github.com/SoMic520/soil-journal-format-review/blob/main/skills/soil-journal-format-review/SKILL.md) · [下载](https://github.com/SoMic520/soil-journal-format-review/releases/latest) |
| [土壤试验方法顾问](https://github.com/SoMic520/soil-methods-consultant) | 从测量对象出发，找到有出处的实验方法。 | v1 | [规则](https://github.com/SoMic520/soil-methods-consultant/blob/main/skills/soil-methods-consultant/SKILL.md) · [下载](https://github.com/SoMic520/soil-methods-consultant/releases/latest) |
| [土壤三普专业报告](https://github.com/SoMic520/soil-third-survey-report) | 对齐省、市、县成果层级，整理可送审的专业报告。 | v11 | [规则](https://github.com/SoMic520/soil-third-survey-report/blob/main/skills/soil-third-survey-report/SKILL.md) · [下载](https://github.com/SoMic520/soil-third-survey-report/releases/latest) |

写论文或改文字，可以先看 **土壤科学与自然科学写作**；画科研图，选择 **R 土壤学科研绘图**；处理投稿排版，选择 **期刊格式审查**；查实验方法，选择 **土壤试验方法顾问**；编制三普成果，选择 **土壤三普专业报告**。

## 安装入门

**技能包是什么？** 它是一组给 AI 助手使用的任务规则、参考资料和辅助脚本。安装到支持 Agent Skills 的工具后，在对话中说明任务并提供材料即可调用。各仓库 README 都提供了从安装到使用的完整步骤。

### 1. 准备 AI 工具与 GitHub CLI

准备 Codex、Claude Code 或其他支持技能的 AI 工具；安装 [GitHub CLI](https://cli.github.com/)（需支持 `gh skill`，2.90.0 及以上，建议使用当前稳定版）。

- Windows：在 PowerShell 执行 `winget install --id GitHub.cli --exact`。
- macOS：使用 [官方安装包](https://cli.github.com/)，或在已安装 Homebrew 时执行 `brew install gh`。

安装后打开终端或 PowerShell：

```shell
gh --version
gh auth login
```

### 2. 安装你需要的技能

下表以 Codex 为例，任选所需技能执行对应的一行命令：

| 技能 | Codex 用户级安装命令 |
| --- | --- |
| 土壤科学与自然科学写作 | `gh skill install SoMic520/soil-all-writing soil-all-writing --agent codex --scope user` |
| R 土壤学科研绘图 | `gh skill install SoMic520/r-soil-scientific-figures r-soil-scientific-figures --agent codex --scope user` |
| 土壤学期刊投稿格式审查 | `gh skill install SoMic520/soil-journal-format-review soil-journal-format-review --agent codex --scope user` |
| 土壤试验方法顾问 | `gh skill install SoMic520/soil-methods-consultant soil-methods-consultant --agent codex --scope user` |
| 土壤三普专业报告 | `gh skill install SoMic520/soil-third-survey-report soil-third-survey-report --agent codex --scope user` |

使用 Claude Code 时把 `--agent codex` 换成 `--agent claude-code`。GitHub Copilot、Gemini CLI、Cursor、OpenCode 等工具的完整命令在各独立仓库 README 中。

### 3. 在对话中调用

重新打开 AI 工具或开始新会话，提供底稿、数据或格式要求，并明确说明技能名称。例如：

```text
请使用 soil-all-writing 润色附件论文，保留数字、单位、引文与统计含义。
```

完整规则可在安装前用 `gh skill preview` 查看。命令说明见 [GitHub CLI 官方文档](https://cli.github.com/manual/gh_skill)。

## 原集合与独立仓库

- **独立仓库**：作为各技能今后更新、安装、下载和问题反馈的入口。
- **本仓库**：提供技能导航，保留原 `skills/` 源码与 `dist/` 发布包，旧的集合安装命令仍可使用。
- **提交历史**：拆分保留各技能在原集合中的历史；拆分日期为 2026-10-02。
- **既有说明**：[原集合完整使用指南](docs/collection-guide.md)保留了通用模型接入、详细环境准备、旧安装命令和新增技能规范。

[查看版本记录](CHANGELOG.md) · [查看保留的技能源码](skills/) · [查看保留的发布包](dist/)

## 其他独立项目

| 仓库 | 用途 |
| --- | --- |
| [academic-aigc-zh](https://github.com/SoMic520/academic-aigc-zh) | 中文学术文本逐段改写、事实核对与原格式审阅交付 |
| [soil-city-county-chronicle-skill](https://github.com/SoMic520/soil-city-county-chronicle-skill) | 市县级土壤志成果编制、证据台账与章节编纂 |

---

**使用与许可**：沿用原仓库的许可状态，目前未设置开源许可证；公开可见不等同于授予再发布许可。参考资料、标准及第三方内容的权利归其各自权利人。有关复制、修改、传播或再发布的授权，请联系仓库所有者。

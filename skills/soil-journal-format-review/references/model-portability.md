# 模型与平台可移植执行说明

本 skill 的边界和交付协议不依赖某个模型。其他能够读取本地文件并运行 Python 的智能体应按以下顺序加载：

1. `SKILL.md`；
2. `scope-boundary.md`；
3. `journal-rule-protocol.md`；
4. `format-checklist.md`；
5. 涉及 DOCX 时加载 `platform-tools-fonts.md` 和 `deliverables.md`。

任何平台都必须从原稿生成新副本、保存规则来源快照、添加真实 Word 批注、运行安全与内容保真检查并逐页渲染签署。若缺少 DOCX 编辑、LibreOffice/Word、PDF 栅格化或所需字体，必须降低交付声明，不得用纯文本改名、评论计数或伪批注替代。

脚注/尾注 story 中的直接批注需要桌面 Word UI 终检。没有 Word 时只能锚定正文脚注引用并披露限制。平台兼容代码不等于该平台实机验证；交付清单只能声明实际有工具链回执的平台。

期刊格式规则由当前官方来源驱动，不能把本 skill 内的示例值当作永久规范。期刊质量评价和论文内容审查在所有模型、所有平台上均属禁止范围。

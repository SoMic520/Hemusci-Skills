---
name: soil-journal-format-review
description: 按土壤学期刊以及可发表土壤研究的综合、环境、农业、生态、地学期刊当前官方要求，对 DOCX 稿件做可追溯排版、格式审查、格式修订、真实 Word 批注、脚注/尾注核查、字体与 LibreOffice 逐页验证。只处理投稿形式，不评价或改写论文质量、科学内容、方法、统计、论证、语言表达、引文真实性或期刊质量。
---

# 土壤学期刊排版与格式审查

## 核心契约

本 skill 把目标期刊的当前官方模板和作者指南转成可追溯的格式规则，默认交付格式修订清洁版、真实 Word 批注版和完整验收记录。它不是论文评审、语言润色或期刊推荐工具。

只对 DOCX 提供自动修订和完整性保证。PDF、LaTeX、Markdown 和扫描件可做定位式格式盘点，但本包没有对应的自动改写与内容保真工具；不要把 DOCX 保障扩展到这些格式。

先完整阅读：

- `references/scope-boundary.md`
- `references/journal-rule-protocol.md`
- `references/platform-tools-fonts.md`
- `references/deliverables.md`
- `references/known-limitations.md`

用户指定的 Hemusci 原则已实际获取并留有哈希证据，见 `references/hemusci-principles-snapshot-20260815.md` 和 `references/design-provenance.md`。

## 硬边界

绝不执行：

- 评价创新性、科学性、研究价值、写作质量、可发表性或录用概率；
- 审查研究设计、方法、统计、结果、讨论、结论或引文是否正确；
- 润色、翻译、改写或补写题名、摘要、正文、图表文字、声明和参考文献；
- 更改字符、数值、单位含义、类别、范围、术语、作者、机构、基金、伦理或数据声明；
- 根据核心目录、星级、分区、影响因子或历史称号评价期刊；
- 自动创建上标/下标，改动公式结构、域代码、图片关系、修订历史或已有批注。

只允许检查“是否存在、位置、机械数量、文件形式和版式属性”。任何可能改变研究含义的动作标记 `OUT_OF_SCOPE_CONTENT_REVIEW`，不得写入 Word 批注。

## 选择任务模式

1. `FORMAT_AUDIT_ONLY`：只输出规则和问题清单。
2. `FORMAT_AND_COMMENT`：默认；输出清洁版、批注版、台账和验证记录。
3. `PACKAGE_REVALIDATION`：复核一个已经按 v2 清单组织的交付包。

本工具生成“清洁格式修订 + 批注”，不生成 Word 跟踪修订。原稿中已有跟踪修订必须原样保留。双盲信息拆分属于跨文件内容搬运，本包不自动执行；只能检查暴露位置并批注，除非另有能证明跨文件内容守恒的专门流程。

原文件永不覆盖。所有输出放进新的任务目录。

## 收集输入

必须记录：目标期刊准确刊名、文章类型、投稿阶段、原稿及附属文件、用户提供的模板/通知、匿名与题名页要求、批注作者名。

目标期刊或文章类型不明确时只能做通用盘点，不能声称“符合期刊要求”。期刊目录只用于发现官网，不是期刊质量表。

用户询问“适用于哪些期刊”时，必须读取 `references/applicable-journals.md`，按其中五组和逐刊名称完整回答；不得只写“土壤学及相关综合期刊”等概括语。逐刊来源和官网入口再查 `references/journal-registry.csv`。

未公开稿件默认本地处理。在线检索只发送刊名和文章类型等最少元数据，不上传全文。

## 建立可执行规则档案

从 `assets/templates/journal-profile.json` 创建任务专用档案。来源优先级：

1. 用户提供的编辑部通知；
2. 当前文章类型的官方模板；
3. 当前官方作者指南；
4. 出版方当前通则；
5. 官方近期论文的可见版式，只能标记 `INFERRED`。

每个 `VERIFIED` 或 `INFERRED` 规则必须保存来源快照，记录相对路径和 SHA-256。`VERIFIED/AUTO_FIX` 才能自动修订；`INFERRED` 和 `UNVERIFIED` 只能批注或报告。

先校验档案：

```bash
python3 scripts/validate_journal_profile.py journal-profile.json \
  --out journal-profile-validation.json
```

动态指南在投稿当天重新打开。期刊明确指定的标准版本优先；不得因为另有 GB/T 7714 新版本就自行替换。

## 工具、安全和字体预检

任何读取、修改或 LibreOffice 渲染前运行：

```bash
python3 scripts/check_toolchain.py --out toolchain-report.json
python3 scripts/ooxml_safety.py manuscript.docx --out package-security.json
python3 scripts/audit_docx_fonts.py manuscript.docx --out source-font-audit.json
```

安全预检拒绝 ZIP 路径穿越/重复部件/异常压缩比、DTD/实体、宏、ActiveX、altChunk、DDE、危险外链和丢失的内部关系。失败时停止，不把文件交给 LibreOffice。

字体审计解析直接字体名和主题字体。缺少字体时：

- 本包只自动下载可合法分发的 `Noto Sans SC` / `Noto Serif SC`，固定 Google Fonts 提交并校验字体、许可证和哈希；
- 下载到任务目录是缺字体时的默认动作；安装到当前用户字体目录必须获得用户明确授权；
- SimSun、SimHei、Calibri 等专有字体只通过 Windows、Microsoft/Apple/Office 官方渠道取得，禁止第三方字体站；
- 安装后用 `--verify-docx` 重跑审计，不能只凭文件已复制就记为成功。

```bash
python3 scripts/install_open_fonts.py --font noto-sans-sc --font noto-serif-sc \
  --download-dir fonts-cache --out font-download-receipt.json

# 仅在用户明确授权安装后：
python3 scripts/install_open_fonts.py --font noto-sans-sc --install-user \
  --verify-docx manuscript.docx --out font-install-receipt.json
```

最终 DOCX 保留期刊指定的真实字体名。替代字体只能用于单独的渲染 QA 副本。只在 macOS 做过检查就只能声明 macOS；Windows 兼容代码不能替代 Windows 实机验证。

## 建立只读基线

```bash
python3 scripts/inspect_docx.py manuscript.docx --out source-inspection.json
python3 scripts/audit_docx_notes.py manuscript.docx --out note-audit.json
python3 scripts/export_format_targets.py manuscript.docx --out format-targets.json
```

`format-targets.json` 给出正文、脚注、尾注的段落/运行索引与 SHA-256，以及表格、分节结构指纹。不要凭肉眼猜索引。

脚注/尾注审计必须核对正文引用 ID、定义 ID、分隔符、缺失定义、孤立定义、重复 ID 和每段格式。发现映射错误只报告，不自动改编号或正文。

## 形成排版发现项

按 `references/format-checklist.md` 和当前规则档案检查页面、分节、字体、段落、标题、摘要/关键词的机械要求、图表布局、题注、参考文献版式、脚注/尾注版式和投稿文件形式。

从 `assets/templates/format-findings.json` 创建 `format-findings.json`。每条必须包含：稳定问题 ID、story、脚注/尾注 ID（适用时）、段落索引、目标文本指纹、排版类别、规则 ID、当前格式、要求格式、动作和状态。

```bash
python3 scripts/validate_findings.py format-findings.json \
  --journal-profile journal-profile.json --out findings-validation.json
```

评论文本由脚本从结构化字段确定性生成，不能自由塞入内容评价。

## 只做有来源的最小格式修订

从 `assets/templates/format-plan.json` 创建计划。每个操作必须绑定：

- 原稿 SHA-256 和规则档案 SHA-256；
- `VERIFIED/AUTO_FIX` 规则 ID；
- exact story/note/index；
- 段落/运行/表格/分节目标指纹；
- `SAFE_TYPOGRAPHY` 风险类别。

运行：

```bash
python3 scripts/apply_docx_format.py manuscript.docx format-plan.json \
  --journal-profile journal-profile.json \
  --out manuscript-格式修订清洁版.docx \
  --receipt format-application-receipt.json
```

白名单支持页面/分节几何、段落外观、受保护的运行字体/字号/粗斜体/颜色、表格外观，以及脚注/尾注中的同类格式。未知属性、过期指纹、无来源规则、样式 ID、上下标、符号/域/脚注引用字体修改均拒绝。

不得用全局“清除格式”破坏已有强调、上下标、公式、域或修订标记。

## 添加真实 Word 批注

批注版必须从清洁版生成：

```bash
python3 scripts/add_format_comments.py manuscript-格式修订清洁版.docx \
  format-findings.json --journal-profile journal-profile.json \
  --out manuscript-格式审查批注版.docx \
  --receipt comment-application-receipt.json \
  --author "排版审查"
```

结构验证要求每条评论具有唯一 comment、range start、range end、reference、关系和内容类型，且不得改动已有评论。

脚注/尾注正文可被直接锚定批注，但 Word 与 LibreOffice 的批注 UI 支持不同。直接锚定 note story 时必须在桌面 Word 复核并提供 `native_word_review_receipt`。没有 Word 时，把批注锚定到正文中的脚注引用所在段，并在 `location` 写明脚注编号；不要声称已验证 note-story 批注 UI。

## 内容和结构保真

```bash
python3 scripts/compare_docx_content.py manuscript.docx \
  manuscript-格式修订清洁版.docx --out clean-integrity.json

python3 scripts/compare_docx_content.py manuscript-格式修订清洁版.docx \
  manuscript-格式审查批注版.docx --allow-comment-additions \
  --out annotated-integrity.json
```

校验覆盖：可见文本、脚注/尾注引用映射、书签和内部锚点、域代码、跟踪修订、公式树、表格合并结构、隐藏/上下标语义标志、全部非批注关系、样式/编号/设置/主题、图片、图表、嵌入对象和其余不透明部件。

若编辑部明确要求改页眉/页脚文字，逐个使用 `--approved-header-footer-part word/header1.xml`，并写入台账。禁止使用旧的整包放宽开关；正文和语义结构始终不放宽。

## LibreOffice 渲染和逐页签署

渲染目录必须为空；复用目录时只有显式 `--clean-generated` 才删除该目录中旧的 `page-N.png` 和本次目标 PDF。

```bash
python3 scripts/render_docx.py manuscript-格式修订清洁版.docx \
  --output-dir 04_逐页渲染/clean --emit-pdf \
  --out-json 04_逐页渲染/clean/render-receipt.json
```

LibreOffice 只做版面渲染，不可靠显示 Word 批注 UI，也不能编辑/接受脚注批注。渲染脚本只返回 `RENDERED_NOT_REVIEWED`。必须逐页查看全部 PNG，检查裁切、重叠、字体替换、分页、表格跨页、公式、题注、页眉页脚和异常空白，然后签署：

```bash
python3 scripts/record_visual_review.py 04_逐页渲染/clean/render-receipt.json \
  --status PASS --reviewer "REVIEWER" --notes "已逐页检查全部页面" \
  --out 04_逐页渲染/clean/reviewed-render-receipt.json
```

清洁版和批注版都必须单独渲染、逐页检查和签署。任何页缺失、哈希改变或未检查都不能进入最终交付。

## 总验收

从 `assets/templates/delivery-manifest.json` 建立 v2 清单。它要求规则快照、发现项、计划、两类应用回执、结构盘点、脚注审计、工具链、两份字体审计、两份完整性结果、两份逐页签署回执、报告和台账。

```bash
python3 scripts/validate_format_review_bundle.py delivery-manifest.json \
  --out bundle-validation.json
```

总验收会交叉核对规则 ID、来源快照哈希、问题 ID、操作 ID、批注 ID、目标指纹和交付文件哈希，并重新执行内容与批注结构检查。`PASS` 之前不得宣称完成。

## 默认交付

- 原稿只读副本；
- `*-格式修订清洁版.docx`；
- `*-格式审查批注版.docx`；
- 格式审查报告、修改台账、规则来源、规则快照；
- `journal-profile.json`、`format-findings.json`、`format-plan.json`；
- 安全/结构/脚注/字体/工具链/应用/完整性/渲染回执；
- `bundle-validation.json`。

报告开头必须写：`本次只审查形式和投稿格式，未评价论文质量、科学内容、方法、统计、论证、语言表达或引文真实性。`

## 资源索引

- `references/applicable-journals.md`：228 本内置期刊的逐刊完整清单；回答覆盖范围时必须读取。
- `references/journal-registry.csv`：官网入口发现表，不是质量评价表。
- `references/format-checklist.md`：完整排版检查清单。
- `references/known-limitations.md`：脚注批注、字体、平台、双盲和非 DOCX 能力边界。
- `assets/templates/`：v2 规则、发现、计划、台账、报告和交付清单模板。
- `scripts/ooxml_safety.py`：安全预检和统一安全解包层。
- `scripts/inspect_docx.py`、`audit_docx_notes.py`、`export_format_targets.py`：基线与目标指纹。
- `scripts/apply_docx_format.py`、`add_format_comments.py`：白名单排版与真实批注。
- `scripts/compare_docx_content.py`：语义和全包保真守卫。
- `scripts/render_docx.py`、`record_visual_review.py`：LibreOffice/Poppler 渲染和逐页签署。
- `scripts/audit_docx_fonts.py`、`install_open_fonts.py`：主题字体审计、合法下载与安装后复核。
- `scripts/validate_format_review_bundle.py`：交付包 fail-closed 总验收。
- `scripts/test_skill.py`：对抗性回归测试。

# 需求覆盖与边界

本表用于审计 Skill 的覆盖面，不替代各模块中的具体规则。新增需求时先定位责任文件，再增加评测用例；不得只在主提示中追加一句泛化指令。

| 需求 | 实现位置 | 验证或证据 | 当前边界 |
| --- | --- | --- | --- |
| 土壤学及相关自然科学 | `discipline-modules.md`、`assets/corpus-curation-matrix.csv` | bundle 验证强制 D1–D13 齐全 | 相邻法律、医学、工程结论仍需对应领域专家复核 |
| 中文专业场景 | `expert-language.md`、`translation-and-alignment.md`、`chinese-source-registry.csv` | 中英评测种子与术语审计 | 不假定中文与英文修辞结构逐句同构 |
| 顶刊和高质量中文期刊 | `top-tier-and-chinese-corpus.md`、`corpus-scale-and-qualification.md`、`literature-index.csv`、`module-expression-pilot.csv`、`fulltext-expression-production.md` | D1–D13 各 1000 条合格元数据配额；每模块 1 条官方开放全文抽象表达试点；新增授权全文快照、可检索文本、定位锚点、表达候选和双人审核的 SHA-256 绑定管线；批量报告按 D1–D13 分别显示全文和可用表达差额 | 13 条试点不等于每模块 1000 篇全文；已有生产管线不等于已完成大规模人工审查；期刊层级不替代单篇质量、中文原生语料和任务相关性 |
| 知名专家第一作者文献 | `expert-author-registry.csv`、`expert-first-author-source-starter.csv` | `validate_expert_sources.py` 核验专家映射、第一作者、来源、日期、许可和复用状态 | 第一作者优先，不等于盲目模仿；同时检查通讯作者和作者贡献 |
| 文献表达与语录 | `literature-expression-corpus.md`、`module-expression-pilot.md`、`fulltext-expression-production.md`、`fulltext_expression_pipeline.py` | 通用表达验证器加 D1–D13 专用覆盖验证器；管线支持 HTML/文本/可检索 PDF 提取、源文与提取文本哈希、锚点核对、审查基础哈希、两名可识别人工审核、同模块去重、配额差额报告和仅导出 qualified 条目；回归已验证候选封存、篡改阻断和导出后通用语料校验 | 自动提取和哈希不代替人工科学语境审查；试点仅限内部流程验证，正式表达库仍需真实双审；受版权保护文本只留必要短引并注明用途 |
| 术语、命名、单位 | `terminology-and-nomenclature.md`、两个 termbase CSV | `validate_termbase.py` | starter 术语为建议态，须由项目专家批准后锁定 |
| 中英写作与翻译 | `translation-and-alignment.md` | 保护元素和双语回译检查 | 不以“流畅”为由改变证据强度或分类体系 |
| DOCX 语言润色的原格式保真 | `docx-language-repair-fidelity.md`、`docx-language-repair-plan-template.json` | 文本节点提取、源文件与原文字段哈希绑定、只写计划内文本节点、OPC/非文本 XML/样式/字段/表格/编号/节属性/二进制部件和保护元素差异验证 | 含域代码、图形或对象的段落默认锁定；复杂跨运行修改宁可拆分，不重建整段或套用模板 |
| 基金、专利、标准、报告、论文、审稿、海报、技术标及其他材料 | 八个 `genre-*.md` | 对应对抗用例、政策状态和人工角色 | 现行规则须在任务发生时从官方来源复核 |
| 不同题材与段落功能的语言差异 | `genre-language-calibration.md`、`genre-language-profiles.json` | `validate_genre_language_profiles.py` 强制 29 类配置、受控强度和跨题材硬边界 | 复合文档须逐段选择配置，不能对全文平均化处理 |
| 科研图表结果描述与科学分析 | `scientific-figure-description.md`、`scientific-visualization-types.md`、用户任务契约、图像预检、证据记录与字数计数器 | 24 类确定性失败规则和44个正反案例；按用户要求分别路由描述、分析或二者；用户可控制图表号位置、空项处理、连接语和分析深度；未指定篇幅时完整描述通常为500～800字，以显式计数单位验证，分析默认2～4句；图像预检绑定 SHA-256、透明层白/黑底渲染和 OCR 候选文本；覆盖表格、箱线/小提琴图、交互作用图、排序图、地图、森林图与路径图等特有证据边界；正例验证“结果表明”“总体而言”“值得注意的是”在承担真实语篇功能时可保留 | OCR 不是科学证据；纯图表无法证明原始统计量、试验因果设计或机制；字数随数据量调整，不用无信息套话、机制猜测或审稿式说明补足 |
| 学科语域与不专业词语管控 | `domain-register-and-word-control.md`、`domain-register-lexicon.json`、`translation-interference-rules.json`、来源注册表、例外记录和持续学习台账 | 120 项逐项测试，覆盖“口径、闭环、全链条、复盘、打法、全链路、顶层设计、治理格局、一盘棋、需求牵引、数据资产、过程留痕、新范式”等；验证 74 个合法技术语境；“闭环”和“全链条”定性为“源语干扰＋目标语域”双重问题，用 2 条源语规则和 12 组英中正反例验证，译文硬性阻断且无技术词义豁免；“顶层设计”和“新范式”按题材、语义对象和证据结构执行放行规则；30 项候选与 13 条期刊来源、4 条官方标准/技术文件来源及台账绑定，且均有可执行的拒绝/警告测试；严格释放阻断所有未处置语境警告；受控例外绑定文件、段落、出现序号和字符位置 | DR091–DR120 尚待独立土壤学人工复核，只能保持 warning；台账中通用 `allow_case_id` 尚未全部实体化为独立案例语料；来源摘要仅用于语域分析且禁止拼贴；删除表层翻译词不等于语义对齐通过；不能用期刊中出现过某词替代按义审查 |
| 完整文档生成时的格式、字数/页数、模板和封面 | `scope-and-routing.md`、`genre-format-length-template-registry.md`、`genre-output-contract-template.json`、`cover-profile-template.json`、`genre-template-registry.json` | `validate_genre_output_contract.py` 拒绝无来源硬限制、未知计数单位、失效模板和不合文体的封面；`validate_genre_template_registry.py` 拒绝普通润色误启模板、历史模板冒充现行模板、技术标脱离受控招标文件 | 普通语言修复不启用模板路径；用户模板优先；无通用限制的文体不虚构数值 |
| 全部题材的独立成品工程 | `genre-artifact-engineering.md`、`genre-artifact-profiles.json`、DOCX/PPTX 规格模板与生成/校验/渲染脚本 | `validate_genre_artifact_profiles.py` 强制 29 类完整路由；27 类 DOCX 批量生成校验；海报和口头报告分别做 PPTX 结构、画布、字体、边界和渲染检查；含目录 DOCX 必须有完整可见缓存条目 | 这是缺少受控模板时的底稿能力；要求受控模板的题材未锁定当前模板时不能发布 |
| 中文技术标 DOCX/PDF 独立交付 | `genre-technical-bids.md`、`chinese-professional-document-format.md`、技术标 JSON 模板与本地生成/校验/渲染脚本 | DOCX OOXML 结构、A4 几何、宋/黑体系与 Times New Roman 字体槽、五号正文、1.5 倍行距、两字符首行缩进、无装饰底纹/方框、两遍稳定目录、PDF 实际字体、逐页 PNG 复核 | 招标文件和采购人模板控制最终格式；默认版式不是法定格式；人工审查仍不可省略 |
| 专家自然度与 Humanizer 深度整合 | `expert-language.md`、`humanizer-zh-gap-analysis.md`、`genre-language-calibration.md`、`domain-register-and-word-control.md`、`naturalness-assurance.md`、`existing-skill-integration-audit.md` | 原有效诊断已转为末级检查；NAR-1.0 对锁定文本做 N01–N12 双人独立审查；另做题材和语域审计 | 不运行依赖原 Humanizer；只保证定义范围内确认残留数为零，不证明纯人工来源或任意检测器不可检出 |
| 十类模型或接口适配 | `model-portability.md`、`provider-adapter-execution.md`、`provider-adapter-contracts.json`、`model_provider_adapter.py`、冒烟套件与矩阵 | 无答案泄漏请求包、十类协议编译、九类固定响应层级提取加自定义 JSON Pointer、严格四字段响应归一化、原响应/规范响应/适配器哈希收据、确定性判分和矩阵副本；本地回归分别编译并归一化 OpenAI、Claude、Gemini、DeepSeek、Qwen、Mistral、Cohere、Bedrock、Ollama 和显式自定义契约的14个探针 | 适配器不发送网络请求、不保存密钥且不授予资格；十类真实端点仍须逐一实测，冒烟通过也不能填写 `qualified_scopes` |
| 事实、数字、单位、引文和规范性强度保护 | `scientific-integrity.md` | `audit_protected_elements.py` 与回归测试 | 机器检查不能替代科学、法律和题材责任人的终审 |
| 可安装、可维护、可审计 | 主 `SKILL.md`、模板与 scripts | 官方 Skill 校验、bundle 验证和回归测试 | AppleDouble `._*` 是卷元数据，不属于 Skill 逻辑文件 |

## 发布判定

完成 bundle、术语、表达语料、项目清单、模型矩阵和回归验证，只能证明结构与确定性不变量满足要求。实际文本仍须按 `evaluation-and-release.md` 完成学科、题材、语言和最终责任人的人工终审。外部模型未运行完整套件时，必须保留 `not_run`，不得把“列入适配表”写成“已经验证通过”。

# 跨题材独立成品生成与验证

本模块只在 `full_artifact_generation` 或用户明确要求套模、重建格式时启用。普通润色、术语纠正、翻译和自然化编辑不得加载这些版式。用户提供的模板、当前填报系统、招标文件、会议母版或机构格式始终优先；Skill 配置只是缺少受控模板时的底稿工程基线。

## 完整题材路由

`assets/genre-artifact-profiles.json` 将 29 类语言题材逐一映射到 13 类成品配置：11 类 DOCX 配置、学术海报配置和口头报告配置。每条路由记录交付载体、封面模式、目录模式、页眉页脚、中文字号名称、行距、首行缩进、段后行数、发布前是否必须取得受控模板以及最低结构角色。

配置中的格式值不是跨机构强制规定。研究论文、基金、专利、标准、学位论文、会议材料、投稿材料、技术标、SOP、专家意见和教材等在正式发布前仍须取得当前控制文件。缺少控制文件时只可生成明确标识的 `draft`，不得声称投稿、申报、申请、发布或投标格式合格。

## DOCX 路径

适用于除海报和口头报告外的 27 类题材：

1. 从 `assets/professional-document-spec-template.json` 建立任务规格，选择 `genre_profile_id`，记录生命周期和受控模板状态。
2. 用 `scripts/validate_genre_artifact_profiles.py` 验证全部题材路由。
3. 用 `scripts/build_chinese_professional_document.js` 生成 DOCX。正文、标题、表格分别使用真实样式；中文按宋/明与黑/无衬线体系，拉丁文字、数字、变量和拉丁学名使用 Times New Roman。
4. 用 `scripts/validate_chinese_professional_document.py` 对照规格和题材配置核查 A4 页面、页边距、中文字号、1.5 倍等受控行距、两字符或零字符缩进、段后行数、字体槽、封面分节、页眉页脚、目录、表格和装饰禁令。
5. 含目录的文档先生成和渲染第一遍，用 `scripts/derive_toc_page_map.py` 提取标题页码，再以 `--toc-page-map` 重建。最终校验器要求每个标题都有可见目录条目，空目录不能通过。
6. 用 `scripts/render_artifact.py` 生成 PDF 和逐页 PNG，核验实际字体，并逐页检查。

技术标继续使用 `build_chinese_technical_bid.js` 和 `validate_chinese_technical_bid.py` 的专用加强路径；通用路径只证明题材格式路由和通用版式结构，不替代采购需求响应核查。

## PPTX 海报与报告路径

学术海报与口头报告使用 `assets/professional-visual-spec-template.json`、`assets/oral-presentation-spec-template.json` 和 `scripts/build_chinese_scientific_visual.js`。默认海报为明确标识的 A0 纵向底稿，口头报告为宽屏底稿；实际画布、比例、母版、最小字号、文件大小和提交格式必须由当前会议或单位要求覆盖。

`scripts/validate_chinese_scientific_visual.py` 核查：

- 海报只有一个画布，口头报告页数与规格一致；
- 画布尺寸、标题、题材结构角色和核心属性绑定正确；
- 所有对象位于画布内；
- 中文使用黑/无衬线体系，拉丁文本含 Times New Roman；
- 默认底稿不含未经授权的彩色底纹；
- 正式发布没有占位符，并已锁定当前活动模板。

PPTX 使用 `scripts/render_artifact.py --font-profile visual` 渲染。海报须按整张和局部放大检查；口头报告须逐张检查。文本抽取或缩略图拼版不能代替逐张复核。

## 全配置工程验证

使用 `scripts/build_artifact_profile_qa_set.py` 为 13 个格式配置各生成一个代表性产物，覆盖全部 29 个题材路由。逐页或逐张检查完成后，每项视觉状态记录为 `pass_full_size_individual_agent_review`，总状态记录为 `structural_render_and_agent_visual_pass`。再运行 `scripts/validate_artifact_profile_qa_manifest.py --require-visual-pass`，核对配置和路由数量、代表题材绑定、DOCX/PPTX 与 PDF 哈希、渲染回执、逐页 PNG、页数、字体和视觉状态。

该状态只表明执行者对全部渲染页完成了全尺寸视觉检查，不冒充独立人工学科终审，也不把底稿配置表述成某一机构或标准的法定格式。

## 受控发布门槛

以下情况一律只保留底稿状态：

- 当前控制文件或模板应当存在但尚未取得；
- 受控模板没有快照和 SHA-256；
- 篇幅、页数、画布或系统计数单位不明；
- 规格缺少该题材的最低结构角色；
- 仍有 `【待填：…】`；
- 最终目录没有可见页码；
- PDF/PPTX 渲染未通过字体核验或未逐页、逐张复核。

结构校验通过只证明成品符合所选底稿配置，不证明科学内容正确、法律范围充分、符合全部现行标准、必然获批、必然发表或必然中标。

# 文件、载体与伴随 Skill 路由

本 Skill 对全部 29 类题材提供独立的底稿载体路由：27 类文本载体可生成和验证 DOCX，学术海报与口头报告可生成和验证 PPTX；两类文件均可渲染为 PDF 和逐页/逐张 PNG。中文土壤科学技术标另有加强的专用生成和校验路径。对批注、修订痕迹、复杂公式对象、嵌入数据图表或特定平台原生控件，未授权或未实现时明确保留边界，不把正式文件降级成 Markdown。

## 载体路由

| 输入/交付物 | 主要处理 | 必须保留 |
| --- | --- | --- |
| 纯文本/Markdown | 可直接执行语言流程和本地审计 | 标题层级、代码块、引用、链接、锁定区 |
| 中文技术标 DOCX | 使用本 Skill 的结构化规格、生成器、校验器和渲染器；每次改动后重验 | A4 几何、样式、目录域、页眉页脚、页码、表格、受保护文本 |
| 其他 DOCX | 使用 `genre-artifact-profiles.json`、通用生成器和校验器建立受控底稿；复杂批注、修订、脚注或模板继承缺失时标明 | 样式、交叉引用、域、脚注、批注、修订、页眉页脚 |
| PDF | 本 Skill 可把 DOCX 渲染为 PDF/逐页 PNG；读取复杂 PDF 时先判断文本型/扫描型 | 页码、双栏顺序、公式、图表、脚注和视觉定位 |
| XLSX/CSV | 使用表格 Skill；语言修改按单元格和主键追踪 | 公式、类型、单位、隐藏表、验证、行列对应 |
| PPTX/Slides | 本 Skill 可独立生成和验证基础学术海报与口头报告；受控母版优先，复杂动画、原生图表和协作批注超出基础路径时标明 | 主题、母版、图表来源、替代文本、画布尺寸、阅读距离 |
| LaTeX/BibTeX | 保留命令、标签、引用键和数学环境 | 宏、转义、交叉引用、编译完整性 |
| JSON/YAML/XML | 只改获准字段；解析、schema 校验后交付 | 编码、键、类型、枚举、标识符和顺序要求 |
| 图片中的文本 | OCR 结果必须与图像逐项核对 | 标签、比例尺、单位、上/下标、颜色含义 |

## 工作副本和差异

保留原件。对复杂文件建立工作副本和变更清单，不覆盖唯一原稿。全文改写后至少做三种比较：文本差异、受保护元素差异、渲染或结构差异。文本抽取不等于文件验证。

## 独立能力与可选扩展边界

- 全题材底稿路径：`genre-artifact-engineering.md`、`genre-artifact-profiles.json`、`build_chinese_professional_document.js`、`validate_chinese_professional_document.py`、`build_chinese_scientific_visual.js`、`validate_chinese_scientific_visual.py`、`render_artifact.py`、`derive_toc_page_map.py`。
- 独立技术标加强路径：`genre-format-length-template-registry.md`、`genre-technical-bids.md`、`chinese-professional-document-format.md`、`validate_genre_output_contract.py`、`prepare_open_fonts.py`、`build_chinese_technical_bid.js`、`validate_chinese_technical_bid.py`、`audit_chinese_professional_style.py`、`render_artifact.py`、`derive_toc_page_map.py`。
- 上述路径不依赖其他 Skill。运行时的 Node、DOCX 库、LibreOffice 和 PDF 栅格化程序是执行依赖，不是写作或格式 Skill。
- 招标文件或采购人模板优先于本 Skill 的默认 A4 参数。默认参数只用于缺少受控模板时的可编辑底稿。

经用户授权后，可选使用：

- `soil-methods-consultant`：方法选择、操作条件、计算和复现性；本 Skill 只负责准确表述已确认方法。
- `soil-journal-format-review`：复杂既有投稿 DOCX 的期刊格式批注和修订；不替代本 Skill 的语言、论证或基础成品路径。
- `scientific-writing`：证据来源、报告指南、作者责任和提交完整性；复杂论文可联合使用，以更严格规则为准。
- `geomaster` / `geopandas`：GIS、遥感和空间计算；本 Skill 审查术语、图注和外推措辞。
- Data Analytics：数据质量、统计、图表和可复现分析；本 Skill 不从文字表现反推计算正确。
- Documents / PDF / Spreadsheets / Presentations：仅在用户授权且任务需要本 Skill 基础路径之外的复杂原生控件时使用。

如果可选能力不存在或未获授权，不得把任何已支持的正式载体降级为 Markdown；应使用本 Skill 的独立 DOCX/PPTX/PDF 路径。仍不得伪造计算、法律或格式认证。

## 保密路由

先分类为公开、内部、保密、受法律特权保护或受监管。外部连接器、联网检索和云模型只能接收获准内容。必要时拆分：公开文献检索使用脱敏查询；受保护正文在获批本地环境处理；最终由人工合并并复核。

## 交付检查

- 文件可打开且无损坏；
- 修订位置与变更清单一致；
- 公式、图表、引用和交叉引用仍可用；
- 正式版没有聊天文本、占位符、隐藏敏感内容或临时注释；底稿中的占位符须可枚举并在清单中披露；
- 导出格式和文件名符合目标系统要求；
- 复杂版式经过逐页/逐张渲染核验。

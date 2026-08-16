# Hemusci Skills 网站

Hemusci Skills 静态站点源码，正式入口为 `https://hemusci.com/skills/`。

当前页面展示三个可安装技能：

- `soil-journal-format-review` v3：覆盖 228 本中文、国际土壤学及可发表土壤研究的综合与交叉期刊；提供 DOCX 排版、格式审查、格式修订、真实 Word 批注、脚注/尾注、字体补齐和 LibreOffice 逐页验证。仅审查投稿形式，不审查论文质量或科学内容。
- `soil-third-survey-report`：面向第三次全国土壤普查成果报告的结构诊断、术语规范、事实保真、修订与图表核查。
- `soil-methods-consultant` v1：以六套本地已校正资料和19份完成复核的官方检测标准为依据，提供土壤试验方法咨询、选择、精确检索、计算、质控及HTML/PDF实验方案。

## 文件

- `index.html`：将根路径转向 `/skills/`。
- `skills/index.html`：多技能中心主页、期刊覆盖摘要和三技能安装命令生成器。
- `skills/soil-journal-format-review/index.html`：土壤学相关期刊数据库；228 本期刊均有研究方向、出版机构、语种、投稿链接和带版本日期的 CSCD / Scopus 收录信息。
- `skills/soil-journal-format-review/journal-evidence.csv`：网页所用逐刊资料和数据库收录状态快照，便于后续更新。
- `scripts/build_soil_journal_page.py`：从技能登记表、CSCD 官方接口和 Scopus 官方来源表重新生成独立资料库与证据快照。
- `404.html`：静态站点错误页。
- `design-qa.md`：桌面端、移动端和交互验收记录。

站点不依赖构建工具或外部字体，也可迁移到 EdgeOne Makers 或对象存储 COS 静态网站。当前正式环境并非 EdgeOne 项目，而是 Ubuntu Nginx：`/skills/` 映射到服务器 `/var/www/hemusci-skills/skills/`，发布时原子替换 `index.html`。旧版备份保存在服务器 `/var/backups/hemusci-skills/`。

部署前应至少复核：首页只显示紧凑期刊摘要、独立资料库期刊数为 228、CSV 与网页刊名集合一致、CSCD / Scopus 标签带版本日期、搜索和证据筛选正常、三个技能安装参数可切换、桌面/中间宽度/移动端无横向溢出、主标题无孤行、控制台无错误。部署时必须同步整个 `skills/` 目录，不能只替换主页。部署后应通过正式域名再次核对页面条目数和安装参数，不能只检查服务器文件。

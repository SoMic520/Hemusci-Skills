# Hemusci Skills 网站

Hemusci Skills 静态站点源码，正式入口为 `https://hemusci.com/skills/`。

当前页面展示五个可安装技能：

- `soil-all-writing` v1：面向土壤及相关自然科学的专业写作、翻译、术语修复、图表分析和正式文件交付；覆盖 29 类文体、13 个学科模块，并通过 162 项确定性回归测试。
- `soil-journal-format-review` v3：覆盖 228 本中文、国际土壤学及可发表土壤研究的综合与交叉期刊；提供 DOCX 排版、格式审查、格式修订、真实 Word 批注、脚注/尾注、字体补齐和 LibreOffice 逐页验证。仅审查投稿形式，不审查论文质量或科学内容。
- `soil-third-survey-report` v11：面向第三次全国土壤普查成果报告的结构诊断、术语规范、事实保真、DOCX修订批注、常规页边距与封面目录控制、图表说明段核查及Word/WPS—LibreOffice兼容性复核。
- `soil-methods-consultant` v1：以六套本地已校正资料和19份完成复核的官方检测标准为依据，提供土壤试验方法咨询、选择、精确检索、计算、质控及HTML/PDF实验方案。
- `r-soil-scientific-figures` v1：面向土壤及相关学科，根据研究设计和用户数据完成图形选择、统计分析、截图复刻及白底PDF/PNG/TIFF最小可复现交付。

`soil-third-survey-report` 最新离线包：[v11](../dist/soil-third-survey-report/soil-third-survey-report-skill-20260817-v11.zip)，SHA-256：`48268A6FB57B36ECC8C83B7416BE0AA5FF4F4DE54F591ADD93843AA5023D298F`。

## 文件

- `index.html`：将根路径转向 `/skills/`。
- `skills/index.html`：多技能中心主页、专业能力矩阵、期刊覆盖摘要和五技能安装命令生成器。
- `analytics/hemusci_analytics.py`：页脚访问概览的同源统计接口，使用 SQLite 保存每日聚合值和匿名访客摘要。
- `analytics/backfill_nginx.py`：首次部署时从既有 Nginx 日志汇总历史访问；只写入每日聚合结果，不保存原始 IP。
- `analytics/hemusci-analytics.service`：腾讯云正式环境中的 systemd 服务定义。
- `analytics/nginx-location.conf`：将 `/api/visits` 转发到本机统计服务的 Nginx 片段。
- `skills/soil-journal-format-review/index.html`：土壤学相关期刊数据库；228 本期刊均有研究方向、出版机构、语种、投稿链接和带版本日期的 CSCD / Scopus 收录信息。
- `skills/soil-journal-format-review/journal-evidence.csv`：网页所用逐刊资料和数据库收录状态快照，便于后续更新。
- `scripts/build_soil_journal_page.py`：从技能登记表、CSCD 官方接口和 Scopus 官方来源表重新生成独立资料库与证据快照。
- `404.html`：静态站点错误页。
- `design-qa.md`：桌面端、移动端和交互验收记录。

站点不依赖构建工具或外部字体。当前正式环境为 Ubuntu Nginx：`/skills/` 映射到服务器 `/var/www/hemusci-skills/skills/`，页脚访问概览由仅监听 `127.0.0.1:8787` 的 Python 服务提供，Nginx 通过同源 `/api/visits` 转发。统计数据库不保存姓名、账号或原始 IP；同一匿名访客 30 分钟内重复刷新不会重复增加访问量。旧版备份保存在服务器 `/var/backups/hemusci-skills/`。

部署前应至少复核：首页以 `soil-all-writing` 为主入口、五个技能及版本号正确、默认安装技能为 `soil-all-writing`、五个技能与六个智能体的安装参数可切换、独立资料库期刊数为 228、CSV 与网页刊名集合一致、CSCD / Scopus 标签带版本日期、搜索和证据筛选正常、桌面/中间宽度/移动端无横向溢出、主标题无孤行、控制台无错误。部署时必须同步整个 `skills/` 目录，不能只替换主页。部署后应通过正式域名再次核对页面内容、条目数和安装参数，不能只检查服务器文件。

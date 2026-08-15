# macOS / Windows 工具与字体策略

## 工具能力分层

| 能力 | macOS | Windows | 缺失时处理 |
|---|---|---|---|
| DOCX 结构读取与批注 | Python 标准库 OOXML 脚本 | Python 标准库 OOXML 脚本 | Python 不可用则停止文件处理 |
| DOCX 编辑 | 可用文档工具、python-docx 或 OOXML | 可用文档工具、Word 自动化、python-docx 或 OOXML | 只输出审查报告，不伪造 DOCX |
| DOCX 渲染 | LibreOffice `soffice` | LibreOffice `soffice.exe` | 可打开但不得宣称通过逐页视觉 QA |
| PDF 转逐页 PNG | `pdftoppm` / `pdftocairo` | `pdftoppm.exe` / `pdftocairo.exe` | 保留 PDF，人工在 Office 中检查 |
| 原生 Word 终检 | Microsoft Word.app（可选） | WINWORD.EXE（可选） | 普通版面可披露风险；脚注/尾注直接批注不得记为最终通过 |

先运行：

```bash
python3 scripts/check_toolchain.py --out toolchain.json
python3 scripts/ooxml_safety.py manuscript.docx --out package-security.json
python3 scripts/audit_docx_fonts.py manuscript.docx --out font-audit.json
```

若缺少字体：

1. 期刊未指定专有字体、且可用 Noto SC 时，先从 Google Fonts 官方仓库下载到任务目录并校验；需要本机排版/渲染时安装到当前用户字体目录：

   ```bash
   python3 scripts/install_open_fonts.py --font noto-serif-sc --font noto-sans-sc \
     --install-user --verify-docx manuscript.docx --out font-install.json
   ```

2. 下载器固定到官方仓库提交，校验 Git blob SHA-1，再记录 SHA-256 和 OFL 许可证；写入采用临时文件后原子替换。
3. SimSun、SimHei、Calibri 等专有字体只通过 Windows、Microsoft Office 云字体或厂商官方渠道获取；禁止从第三方字体站下载，也不把专有字体复制进 skill 或交付包。
4. Microsoft Office 云字体要求 Office 联网并启用相应连接体验。字体在 Office 中下载后，重新运行审计并重启 Word/LibreOffice。
5. `audit_docx_fonts.py` 同时解析直接字体和 `major/minor` 主题字体。主题引用无法解析时为失败，不能按“系统默认字体”跳过。

缺少开源字体时必须至少完成下载和校验，并把来源、固定提交、许可证、SHA-256、目录和结果写入任务记录。用户级字体安装也必须先获得明确授权。不要自动安装额外软件或专有字体。工具缺失时给出准确缺项和可完成范围。

## 字体三层策略

### 1. 交付字体

最终投稿 DOCX 必须写入期刊或模板要求的真实字体族名称，包括 `w:ascii`、`w:hAnsi`、`w:eastAsia` 和需要时的 `w:cs`。不能因为当前系统没有该字体就静默换成平台默认字体。

### 2. 本地渲染字体

本机没有交付字体时，可以从 `assets/font-compatibility.json` 选择当前平台已安装的 QA 替代字体，生成单独的 `*-仅渲染QA.docx`。该副本只用于发现裁切、重叠、分页和表格问题，不得当作投稿版交付。

替代字体会改变字宽和分页，所以报告必须写 `RENDER_WITH_FALLBACK_FONT`。若期刊严格指定字体，最终版还需在安装了目标字体的平台再次渲染。

### 3. 跨平台稳健字体

期刊没有指定字体且用户要求 macOS/Windows 均可编辑时，优先选择双方实际安装的字体；不能仅凭“系统通常自带”推断。英文常见候选为 Times New Roman、Arial、Courier New；中文应根据两台机器的实际审计结果选择。若无共同中文字体，可安装同一款合法开源字体，或保留期刊字体并指定最终终检平台。

## 中文字体名称

- Windows“宋体”在 OOXML 中通常写 `SimSun`；macOS 的 `Songti SC`/`STSong` 只能作为 QA 替代，不等同于 SimSun。
- Windows“黑体”通常为 `SimHei`；macOS `Heiti SC`/`PingFang SC` 只能作为 QA 替代。
- Windows“楷体”通常为 `KaiTi`；macOS `Kaiti SC` 可作 QA 替代。
- Windows“仿宋”通常为 `FangSong`；macOS `STFangsong` 可作 QA 替代。

中文名与英文族名可能同时出现在模板中，审计时按映射表识别别名，但写回最终 DOCX 时服从官方模板已有名称。

## 字体许可

不要把 Microsoft、Apple 或商业字体文件打包进 skill 或交付包。Microsoft 官方说明 SimSun 随 Windows/Office 提供，Office 云字体也包含 SimSun 和 SimHei，但这不授权从第三方站点单独抓取字体文件。只有字体许可证明确允许嵌入且用户授权时才考虑嵌入；否则交付规则、字体清单和缺字警告，不复制字体文件。

官方来源：

- Microsoft SimSun 字体产品信息：https://learn.microsoft.com/en-us/typography/font-list/simsun
- Microsoft Office 云字体：https://support.microsoft.com/en-us/office/cloud-fonts-in-office-f7b009fe-037f-45ed-a556-b5fe6ede6adb
- Noto CJK 官方仓库：https://github.com/notofonts/noto-cjk
- Google Fonts 官方仓库：https://github.com/google/fonts

## 双平台终检

高风险稿件建议执行：

1. macOS 生成/修订并通过 OOXML 内容保真检查；
2. macOS LibreOffice 或 Word 逐页渲染；
3. Windows 安装期刊字体后，用 Word 或 LibreOffice 打开；不得更新字段，因为这会改变域结果；
4. Windows 再次导出 PDF/PNG，逐页比较页数、表格跨页、公式、题注和图件；
5. 最终 DOCX 再运行内容保真和批注结构检查。

如果只具备一个平台，只能声明该平台已通过；不得宣称“双平台完全一致”。

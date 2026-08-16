# R 环境安装入口 / Cross-platform R setup

- macOS: double-click `install_macos.command`, or run it from Terminal. When R is absent, Homebrew is used if available; otherwise the report points to the signed CRAN installer.
- Windows: right-click `install_windows.ps1` and choose **Run with PowerShell**. When R is absent, Windows Package Manager installs `RProject.R` if `winget` is available.
- Both installers verify the requested CRAN/Bioconductor profiles, install missing packages, inspect Times New Roman and Songti/SimSun-compatible fonts, and write a JSON report.
- Runtime certification is platform-specific. A report produced on macOS does not certify Windows; run the Windows script on the target Windows machine.

默认安装并核对 `core,publication`，它们足以运行 314 个依赖受控的复现模板。土壤、生态、空间和微生物组对象工作流是按需 profile，不应为了画基础模板一次性安装全部重型依赖。

macOS：双击 `install_macos.command`，或在终端运行：

```bash
R_FIGURE_PROFILES="core,publication,soil,ecology" ./install_macos.command
```

Windows PowerShell：

```powershell
$env:R_FIGURE_PROFILES = "core,publication,soil,ecology"
.\install_windows.ps1
```

可选 profile：`soil`、`ecology`、`spatial`、`microbiome`。空间包可能需要系统 GIS 库，Bioconductor 包必须与当前 R/Bioconductor release 匹配。安装记录写入同目录 JSON；不能把失败依赖静默忽略。

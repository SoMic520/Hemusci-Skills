# R 土壤学科研绘图模板库 — 314 个可复现项目

This archive contains one independently runnable project under `recipes/<recipe-id>/` for every catalogued figure.

## Run one recipe

1. Open its `data/input.csv` and replace the synthetic example with real observations while preserving the documented fields.
2. Review `config/figure-config.json`, especially the experimental unit, replication, pairing/blocking/nesting, target physical width and height.
3. Run `Rscript figure.R`. The entrypoint checks required CRAN packages, installs only missing packages into the user library, verifies them again, and stops with a readable error if installation fails. `setup_packages.R` is only an optional batch pre-install helper for this internal archive.
4. Inspect `outputs/figure-manifest.json`, the PDF/PNG/LZW-TIFF files, and the QA reports before publication.

Internal plot titles and captions are off by default. Manuscript captions belong outside the graphics canvas. Typography is calculated from the final physical dimensions and actual panel/facet count; `base_size_pt` is only a deliberate override.

## Fonts

The engine requests Songti-compatible Chinese fonts (`Songti SC`, `STSong`, `SimSun`, `宋体`) and Times New Roman-compatible English fonts. Actual selected families and fallbacks are recorded in every output manifest. Fonts are not redistributed.

## Environment

Use the scripts under `environment/`. They detect R, install it through Homebrew or Windows Package Manager when available, install missing package profiles, inspect fonts and write a JSON report. Windows runtime certification must be performed on a Windows host.

## Tested gallery and integrity

- `tested-gallery/` contains the full-library render used by the quality gate.
- `recipe-index.tsv` maps all IDs to schemas, renderers and bundle paths.
- `R土壤学科研绘图_314模板索引.xlsx` 是可筛选工作簿，含总览、314 图索引、35 种输入规范、29 个图族、QA、四个压缩包借鉴审计、权威来源和使用说明。
- `library-summary.json` records build/test counts.
- `checksums.sha256` supports integrity verification.

最终验收包含两层：共享引擎全库实绘 314/314，以及交付目录中 314 个独立 `figure.R` 入口复测 314/314。完全重复组为 0；高分辨率结构审计为 306 PASS、8 WARN、0 FAIL。WARN 和 20 页紧凑联系表已纳入人工复核记录，详见 `qa/` 与 `documentation/final-quality-assurance.md`。

`documentation/` 还包含选图规则、投稿导出、来源登记、标准输入、图族映射和四个参考压缩包的吸收/不继承矩阵。

The supplied inputs are synthetic schema examples, not evidence for scientific inference. Image reconstruction must never fabricate source data, p-values, uncertainty, sample size or hidden geometry.

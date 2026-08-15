# v2 交付结构与字段

## 推荐目录

```text
期刊排版审查交付/
├── 00_原稿只读副本/
├── 01_格式修订清洁版/
├── 02_格式审查批注版/
├── 03_审查记录/
│   ├── 规则原文/
│   ├── 格式审查报告.md
│   ├── 格式修改台账.csv
│   ├── 期刊规则来源.csv
│   ├── journal-profile.json
│   ├── format-findings.json
│   ├── format-plan.json
│   └── 各类 JSON 回执
├── 04_逐页渲染/
│   ├── clean/
│   └── annotated/
└── delivery-manifest.json
```

## 发现项字段

`format-findings.json` 使用 schema `2.0`。顶层绑定规则档案和待批注文档 SHA-256。每条发现至少包含：

- `issue_id`、`rule_id`、`category`、`scope=FORMAT_ONLY`；
- `story=document|footnotes|endnotes`；
- `note_id`（脚注/尾注必填）和 story 内的 `paragraph_index`；
- `expected_text_sha256`；
- `location`、`current_format`、`required_format`；
- `action=FIX|COMMENT|MANUAL_VERIFY|NONE`；
- `status=OPEN|FIXED|COMMENTED|MANUAL_CHECK|NOT_APPLICABLE`。

批注文本不作为自由字段编写；工具从这些字段确定性生成。

## 修改台账字段

```text
issue_id,operation_id,story,note_id,location,category,rule_id,before_format,after_format,action,comment_id,target_text_sha256,status
```

台账只描述格式属性，不粘贴未公开正文。问题 ID、操作 ID 和批注 ID 必须与 findings、plan 和应用回执完全一致。

## 规则来源字段

```text
rule_id,category,requirement,source_url,source_title,source_locator,source_kind,source_sha256,source_snapshot,accessed_at,article_type,verification_status,automation
```

`source_snapshot` 为交付根目录内相对路径。`VERIFIED`/`INFERRED` 的文件哈希必须与 `source_sha256` 一致。

## 回执

v2 总验收至少要求：

- source inspection、note audit、toolchain report；
- clean/annotated font audits；
- format/comment application receipts；
- clean/annotated integrity reports；
- clean/annotated reviewed render receipts；
- 脚注/尾注直接批注时的 native Word review receipt。

渲染回执必须列出连续页码、每页路径和 SHA-256。只有 `VISUAL_REVIEW_PASS` 且 `pages_reviewed` 覆盖全部页面才通过。

## 审查报告最低结构

1. 目标与范围；
2. 官方规则；
3. 已修订格式问题；
4. 仅批注或需作者处理；
5. 未验证规则与冲突；
6. 内容保真校验；
7. 脚注与尾注校验；
8. 字体与跨平台校验；
9. 逐页视觉核验；
10. 未开展的内容审查。

## 批注要求

批注必须是真实 Word comment，锚定具体 story 和段落。必须通过结构验证；不能以评论计数、正文着色、括号说明、脚注或文末列表替代。

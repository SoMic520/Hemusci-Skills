# 十类模型与接口适配执行层

`scripts/model_provider_adapter.py` 只完成冻结任务包的协议编译和真实响应的归一化，不保存密钥、不自动发送网络请求，也不将离线契约测试写成模型资格通过。接口字段的基线和官方文档记录在 `assets/provider-adapter-contracts.json`。

## 先编译，再由受控执行器发送

1. 使用 `model_qualification_harness.py prepare` 生成 `requests.answer-free.jsonl`。
2. 准备不含密钥、不含判分键的系统提示文件。
3. 编译为目标接口的无凭据请求包：

```bash
python3 scripts/model_provider_adapter.py validate-contracts \
  assets/provider-adapter-contracts.json
python3 scripts/model_provider_adapter.py compile \
  --contracts assets/provider-adapter-contracts.json \
  --requests path/to/requests.answer-free.jsonl \
  --system-prompt path/to/system-prompt.txt \
  --provider openai --model-id EXACT_MODEL \
  --output-dir path/to/compiled-run
```

OpenAI、Claude、Gemini、DeepSeek、Qwen、Mistral、Cohere、Bedrock 和 Ollama 分别编译为各自的 Responses、Messages、GenerateContent、Chat、Converse 或本地 Chat 请求结构。请求包只包含相对路径/操作、body 和响应提取类型；执行器须在受批准的运行环境中动态注入域名、区域、凭据、超时和重试策略。

精确模型 profile 确认不支持原生 schema 时，使用 `--structured-mode local`：编译器不向该端点发送 schema 专用字段，但仍在用户任务中保留输出契约，并由归一化器严格验证。默认 `auto` 只按平台常规能力选择，不替代型号级能力探测；Bedrock 默认走本地验证，因为原生结构化能力取决于基础模型。

Amazon Bedrock 必须额外记录 `--region`。自定义接口必须提供由真实规范填写的 `assets/custom-provider-adapter-template.json` 项目副本；脚本不会因 URL 中出现 `/v1` 而自动推定兼容性。

## 归一化真实响应

受控执行器将原始响应按一行一条保存为：

```json
{"probe_id":"MQ-01","raw_response":{"provider-specific":"response"}}
```

然后运行：

```bash
python3 scripts/model_provider_adapter.py normalize \
  --manifest path/to/compiled-run/adapter-manifest.json \
  --raw-responses path/to/raw-responses.jsonl \
  --output path/to/responses.normalized.jsonl
```

归一化器按提供方的实际响应层级提取文本，然后严格解析 `probe_id`、`decision`、`output_text` 和 `complete`。它不删除 Markdown 围栏、不猜测被截断的 JSON、不以默认决策补空缺字段。任一条解析失败即停止，由执行器保留原始证据并重试或降级。

## 安全和资格边界

- 不得将 API key、Authorization、AWS 凭据、Cookie 或签名 URL 写入编译包、源响应引用或评测收据。
- 不得把请求成功、HTTP 200、JSON 可解析或离线适配回归写成 `smoke_pass`。只有真实端点响应经原收据绑定、确定性评分和人工 profile 核对后，才可更新项目矩阵副本。
- 结构化输出是格式能力，不是事实校验。所有平台响应最终都运行本地契约验证和原 Skill 审计。
- 接口、模型、区域、结构化输出能力或官方文档变更后，必须重新编译并跑探针。

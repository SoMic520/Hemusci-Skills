#!/usr/bin/env python3
"""Compile frozen probes for ten provider families and strictly normalize real responses."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import quote, urlparse


PROVIDERS = {
    "openai", "anthropic", "google-gemini", "deepseek", "qwen", "mistral",
    "cohere", "amazon-bedrock", "ollama", "custom",
}
DECISIONS = {"preserve", "revise", "flag", "refuse"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SECRET_RE = re.compile(r"(?:authorization|api[_-]?key|secret|access[_-]?key|session[_-]?token|cookie)", re.I)
PLACEHOLDER_RE = re.compile(r"(?:REPLACE|example\.com|CUSTOM-ADAPTER-ID)", re.I)


class AdapterError(ValueError):
    """Raised when compilation or normalization violates the adapter contract."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdapterError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AdapterError(f"JSON root must be an object: {path}")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AdapterError(f"cannot read JSONL {path}: {exc}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AdapterError(f"{path} line {line_number}: invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise AdapterError(f"{path} line {line_number}: object required")
        records.append(record)
    return records


def write_json_new(path: Path, payload: Any) -> None:
    if path.exists():
        raise AdapterError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise AdapterError(f"cannot hash {path}: {exc}") from exc


def secret_key_paths(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if SECRET_RE.search(str(key)):
                findings.append(path)
            findings.extend(secret_key_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(secret_key_paths(item, f"{prefix}[{index}]"))
    return findings


def validate_contracts_data(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if payload.get("release_scope") != "protocol_compilation_and_response_normalization_only_no_endpoint_qualification":
        errors.append("release_scope must preserve the no-endpoint-qualification boundary")
    try:
        baseline = date.fromisoformat(str(payload.get("baseline_date") or ""))
        if baseline > date.today():
            errors.append("baseline_date cannot be in the future")
    except ValueError:
        errors.append("baseline_date must be YYYY-MM-DD")
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        return errors + ["providers must be an object"]
    missing = PROVIDERS - set(providers)
    extra = set(providers) - PROVIDERS
    if missing:
        errors.append("missing providers: " + ", ".join(sorted(missing)))
    if extra:
        errors.append("unexpected providers: " + ", ".join(sorted(extra)))
    for provider in sorted(PROVIDERS & set(providers)):
        item = providers[provider]
        if not isinstance(item, dict):
            errors.append(f"{provider}: contract must be an object")
            continue
        for field in ("request_style", "transport", "relative_path", "response_extractor", "structured_output_mode"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"{provider}: {field} is required")
        docs = item.get("official_docs")
        if not isinstance(docs, list) or any(not isinstance(url, str) or not url.startswith("https://") for url in docs):
            errors.append(f"{provider}: official_docs must be an HTTPS string array")
        if provider != "custom" and not docs:
            errors.append(f"{provider}: at least one official documentation URL is required")
    expected_hosts = {
        "openai": {"developers.openai.com"},
        "anthropic": {"platform.claude.com"},
        "google-gemini": {"ai.google.dev"},
        "deepseek": {"api-docs.deepseek.com"},
        "qwen": {"help.aliyun.com"},
        "mistral": {"docs.mistral.ai"},
        "cohere": {"docs.cohere.com"},
        "amazon-bedrock": {"docs.aws.amazon.com"},
        "ollama": {"docs.ollama.com"},
    }
    for provider, hosts in expected_hosts.items():
        for url in providers.get(provider, {}).get("official_docs", []):
            if urlparse(url).hostname not in hosts:
                errors.append(f"{provider}: official documentation must use {', '.join(sorted(hosts))}")
    if payload.get("auth_policy") != (
        "Authentication secrets and credential headers must never be written to compiled request bundles, "
        "manifests, raw-response references, or receipts."
    ):
        errors.append("auth_policy must preserve the exact no-secret artifact rule")
    return errors


def validate_custom_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("custom contract schema_version must be 1")
    for field in ("adapter_id", "documentation_url", "request_style", "method", "relative_path", "structured_output_mode", "response_text_json_pointer"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip() or PLACEHOLDER_RE.search(value):
            errors.append(f"custom contract {field} must be filled from the real interface specification")
    if payload.get("request_style") not in {"openai_chat", "single_prompt_json"}:
        errors.append("custom request_style must be openai_chat or single_prompt_json")
    if payload.get("method") not in {"POST"}:
        errors.append("custom method must be POST")
    if isinstance(payload.get("relative_path"), str) and not payload["relative_path"].startswith("/"):
        errors.append("custom relative_path must begin with /")
    if isinstance(payload.get("response_text_json_pointer"), str) and not payload["response_text_json_pointer"].startswith("/"):
        errors.append("custom response_text_json_pointer must be an absolute JSON pointer")
    for field in ("system_message_supported", "data_policy_verified", "confidentiality_approved"):
        if not isinstance(payload.get(field), bool):
            errors.append(f"custom contract {field} must be boolean")
    secret_paths = secret_key_paths(payload)
    if secret_paths:
        errors.append("custom contract must not contain credential fields: " + ", ".join(secret_paths))
    return errors


def normalize_schema(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key == "const":
                result["enum"] = [normalize_schema(item)]
            else:
                result[key] = normalize_schema(item)
        return result
    if isinstance(value, list):
        return [normalize_schema(item) for item in value]
    return value


def probe_prompt(record: dict[str, Any]) -> str:
    contract = record["response_contract"]
    return (
        "任务要求：\n" + record["instruction"].strip()
        + "\n\n待处理材料：\n" + record["source_text"].strip()
        + "\n\n只返回一个 JSON 对象，不要使用 Markdown 围栏。输出必须满足以下契约：\n"
        + json.dumps(contract, ensure_ascii=False, separators=(",", ":"))
    )


def validate_answer_free_requests(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    forbidden = {
        "expected_decision", "must_preserve", "must_include", "forbidden_literals",
        "forbidden_regex", "min_chars", "max_chars",
    }
    for index, record in enumerate(records, 1):
        probe_id = record.get("probe_id")
        if not isinstance(probe_id, str) or not re.fullmatch(r"MQ-\d{2,}", probe_id):
            errors.append(f"record {index}: invalid probe_id")
            continue
        if probe_id in ids:
            errors.append(f"record {index}: duplicate probe_id {probe_id}")
        ids.add(probe_id)
        if forbidden & set(record):
            errors.append(f"{probe_id}: answer-free request leaked scoring fields")
        for field in ("instruction", "source_text"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                errors.append(f"{probe_id}: {field} is required")
        contract = record.get("response_contract")
        if not isinstance(contract, dict):
            errors.append(f"{probe_id}: response_contract must be an object")
            continue
        required = set(contract.get("required", []))
        if required != {"probe_id", "decision", "output_text", "complete"}:
            errors.append(f"{probe_id}: response_contract required fields are invalid")
        if contract.get("additionalProperties") is not False:
            errors.append(f"{probe_id}: response_contract must reject additional properties")
    if not records:
        errors.append("answer-free request bundle is empty")
    return errors


def compile_body(
    provider: str, model_id: str, system_prompt: str, prompt: str,
    schema: dict[str, Any], max_output_tokens: int, custom: dict[str, Any] | None,
    structured_mode: str,
) -> dict[str, Any]:
    schema = normalize_schema(schema)
    use_native = structured_mode == "native"
    schema_wrapper = {
        "type": "json_schema", "name": "soil_all_writing_probe_response",
        "strict": True, "schema": schema,
    }
    if provider in {"openai", "qwen"}:
        body = {
            "model": model_id,
            "instructions": system_prompt,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            "max_output_tokens": max_output_tokens,
        }
        if use_native:
            body["text"] = {"format": schema_wrapper}
        return body
    if provider == "anthropic":
        body = {
            "model": model_id, "system": system_prompt, "max_tokens": max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if use_native:
            body["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        return body
    if provider == "google-gemini":
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }
        if use_native:
            body["generationConfig"].update({
                "responseMimeType": "application/json", "responseJsonSchema": schema,
            })
        return body
    if provider == "deepseek":
        body = {
            "model": model_id,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            "stream": False, "max_tokens": max_output_tokens,
        }
        if use_native:
            body["response_format"] = {"type": "json_object"}
        return body
    if provider == "mistral":
        body = {
            "model": model_id,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens,
        }
        if use_native:
            body["response_format"] = {"type": "json_schema", "json_schema": schema_wrapper}
        return body
    if provider == "cohere":
        body = {
            "model": model_id,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens,
        }
        if use_native:
            body["response_format"] = {"type": "json_object", "schema": schema}
        return body
    if provider == "amazon-bedrock":
        prompt_with_schema = prompt + "\n\nThe foundation-model response will be validated locally against this JSON Schema."
        return {
            "modelId": model_id,
            "system": [{"text": system_prompt}],
            "messages": [{"role": "user", "content": [{"text": prompt_with_schema}]}],
            "inferenceConfig": {"maxTokens": max_output_tokens},
        }
    if provider == "ollama":
        body = {
            "model": model_id,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            "stream": False, "options": {"num_predict": max_output_tokens},
        }
        if use_native:
            body["format"] = schema
        return body
    if provider == "custom" and custom is not None:
        if custom["request_style"] == "openai_chat":
            messages = [{"role": "user", "content": prompt}]
            if custom["system_message_supported"]:
                messages.insert(0, {"role": "system", "content": system_prompt})
            else:
                messages[0]["content"] = system_prompt + "\n\n" + prompt
            body = {
                "model": model_id, "messages": messages,
                "max_tokens": max_output_tokens,
            }
            if use_native:
                body["response_format"] = {"type": custom["structured_output_mode"], "schema": schema}
            return body
        body = {
            "model": model_id, "system": system_prompt, "prompt": prompt,
            "max_output_tokens": max_output_tokens,
        }
        if use_native:
            body["response_schema"] = schema
        return body
    raise AdapterError(f"unsupported provider compilation path: {provider}")


def compile_requests(args: argparse.Namespace) -> None:
    contracts = read_json(args.contracts)
    errors = validate_contracts_data(contracts)
    if errors:
        raise AdapterError("; ".join(errors))
    records = read_jsonl(args.requests)
    errors = validate_answer_free_requests(records)
    if errors:
        raise AdapterError("; ".join(errors))
    try:
        system_prompt = args.system_prompt.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise AdapterError(f"cannot read system prompt: {exc}") from exc
    if not system_prompt:
        raise AdapterError("system prompt must not be empty")
    if not args.model_id.strip() or PLACEHOLDER_RE.search(args.model_id):
        raise AdapterError("model-id must identify the exact model, not a placeholder")
    if args.max_output_tokens <= 0:
        raise AdapterError("max-output-tokens must be positive")
    if args.provider == "amazon-bedrock" and not args.region:
        raise AdapterError("amazon-bedrock compilation requires --region")
    custom: dict[str, Any] | None = None
    if args.provider == "custom":
        if args.custom_contract is None:
            raise AdapterError("custom provider compilation requires --custom-contract")
        custom = read_json(args.custom_contract)
        errors = validate_custom_contract(custom)
        if errors:
            raise AdapterError("; ".join(errors))
    elif args.custom_contract is not None:
        raise AdapterError("--custom-contract is valid only for provider custom")
    if args.output_dir.exists():
        raise AdapterError(f"refusing to overwrite existing output directory: {args.output_dir}")
    args.output_dir.mkdir(parents=True)
    provider_contract = contracts["providers"][args.provider]
    relative_path = custom["relative_path"] if custom else provider_contract["relative_path"]
    request_style = custom["request_style"] if custom else provider_contract["request_style"]
    response_extractor = (
        "json_pointer_from_user_contract" if custom else provider_contract["response_extractor"]
    )
    if args.structured_mode == "auto":
        effective_structured_mode = "local" if args.provider == "amazon-bedrock" else "native"
    else:
        effective_structured_mode = args.structured_mode
    if args.provider == "amazon-bedrock" and effective_structured_mode == "native":
        raise AdapterError(
            "amazon-bedrock native structured output is foundation-model-specific; use local mode or a custom documented adapter"
        )
    compiled_path = args.output_dir / "provider-requests.jsonl"
    compiled: list[dict[str, Any]] = []
    for record in records:
        body = compile_body(
            args.provider, args.model_id, system_prompt, probe_prompt(record),
            record["response_contract"], args.max_output_tokens, custom,
            effective_structured_mode,
        )
        compiled.append({
            "probe_id": record["probe_id"],
            "transport": provider_contract["transport"] if custom is None else "user_documented",
            "method_or_operation": custom["method"] if custom else ("Converse" if args.provider == "amazon-bedrock" else "POST"),
            "relative_path": relative_path.replace("{model}", quote(args.model_id, safe="")),
            "request_style": request_style,
            "body": body,
            "response_extractor": response_extractor,
            "response_contract": record["response_contract"],
        })
    serialized = "".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in compiled
    )
    secret_paths: list[str] = []
    for index, record in enumerate(compiled):
        secret_paths.extend(f"record[{index}].{path}" for path in secret_key_paths(record))
    if secret_paths:
        raise AdapterError(
            "compiled request bundle contains credential fields; inject credentials externally: "
            + ", ".join(secret_paths)
        )
    compiled_path.write_text(serialized, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "manifest_type": "soil-all-writing-provider-adapter",
        "status": "compiled_not_executed",
        "compiled_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "provider": args.provider,
        "model_id": args.model_id,
        "region": args.region or "not_applicable",
        "request_style": request_style,
        "structured_mode": effective_structured_mode,
        "response_extractor": response_extractor,
        "response_text_json_pointer": custom.get("response_text_json_pointer") if custom else None,
        "request_count": len(compiled),
        "probe_ids": [record["probe_id"] for record in compiled],
        "compiled_requests": compiled_path.name,
        "integrity": {
            "contracts_sha256": sha256_file(args.contracts),
            "answer_free_requests_sha256": sha256_file(args.requests),
            "system_prompt_sha256": sha256_file(args.system_prompt),
            "compiled_requests_sha256": sha256_file(compiled_path),
            "adapter_script_sha256": sha256_file(Path(__file__)),
            "custom_contract_sha256": sha256_file(args.custom_contract) if args.custom_contract else None,
        },
        "auth_policy": "credentials_not_stored_in_compiled_artifacts",
        "release_scope": "protocol_compiled_only_endpoint_not_called_not_qualified",
    }
    write_json_new(args.output_dir / "adapter-manifest.json", manifest)
    print(json.dumps({
        "status": "PASS", "provider": args.provider, "request_count": len(compiled),
        "manifest": str(args.output_dir / "adapter-manifest.json"),
        "release_scope": manifest["release_scope"],
    }, ensure_ascii=False))


def join_text_parts(parts: Any) -> str:
    if isinstance(parts, str):
        return parts
    if not isinstance(parts, list):
        raise AdapterError("provider content must be a string or list")
    texts: list[str] = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            texts.append(part["text"])
    if not texts:
        raise AdapterError("provider content list contains no text")
    return "".join(texts)


def json_pointer(payload: Any, pointer: str) -> Any:
    value = payload
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            try:
                value = value[int(token)]
            except (ValueError, IndexError) as exc:
                raise AdapterError(f"JSON pointer list token failed: {token}") from exc
        elif isinstance(value, dict) and token in value:
            value = value[token]
        else:
            raise AdapterError(f"JSON pointer token not found: {token}")
    return value


def extract_candidate(raw: dict[str, Any], extractor: str, pointer: str | None) -> str | dict[str, Any]:
    if extractor == "openai_responses":
        if isinstance(raw.get("output_text"), str):
            return raw["output_text"]
        texts: list[str] = []
        for item in raw.get("output", []):
            if not isinstance(item, dict):
                continue
            for part in item.get("content", []):
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    texts.append(part["text"])
        if texts:
            return "".join(texts)
    elif extractor == "anthropic_messages":
        return join_text_parts(raw.get("content"))
    elif extractor == "gemini_generate_content":
        try:
            return join_text_parts(raw["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError("Gemini response does not contain candidates[0].content.parts") from exc
    elif extractor == "openai_chat":
        try:
            return join_text_parts(raw["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError("chat response does not contain choices[0].message.content") from exc
    elif extractor == "cohere_v2_chat":
        try:
            return join_text_parts(raw["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise AdapterError("Cohere response does not contain message.content") from exc
    elif extractor == "bedrock_converse":
        try:
            return join_text_parts(raw["output"]["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise AdapterError("Bedrock response does not contain output.message.content") from exc
    elif extractor == "ollama_chat":
        try:
            return raw["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise AdapterError("Ollama response does not contain message.content") from exc
    elif extractor == "json_pointer_from_user_contract" and pointer:
        return json_pointer(raw, pointer)
    raise AdapterError(f"no response text found for extractor {extractor}")


def parse_normalized_payload(candidate: str | dict[str, Any], expected_probe_id: str) -> dict[str, Any]:
    if isinstance(candidate, str):
        stripped = candidate.strip()
        if stripped.startswith("```") or stripped.endswith("```"):
            raise AdapterError(f"{expected_probe_id}: Markdown fences are not accepted")
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise AdapterError(f"{expected_probe_id}: provider text is not strict JSON: {exc}") from exc
    else:
        payload = candidate
    if not isinstance(payload, dict):
        raise AdapterError(f"{expected_probe_id}: normalized provider payload must be an object")
    required = {"probe_id", "decision", "output_text", "complete"}
    if set(payload) != required:
        raise AdapterError(f"{expected_probe_id}: payload fields must be exactly {sorted(required)}")
    if payload["probe_id"] != expected_probe_id:
        raise AdapterError(f"{expected_probe_id}: response probe_id mismatch")
    if payload["decision"] not in DECISIONS:
        raise AdapterError(f"{expected_probe_id}: invalid decision")
    if not isinstance(payload["output_text"], str):
        raise AdapterError(f"{expected_probe_id}: output_text must be a string")
    if payload["complete"] is not True:
        raise AdapterError(f"{expected_probe_id}: complete must be true")
    return payload


def normalize_responses(args: argparse.Namespace) -> None:
    manifest = read_json(args.manifest)
    if manifest.get("schema_version") != 1 or manifest.get("status") != "compiled_not_executed":
        raise AdapterError("adapter manifest is invalid")
    if manifest.get("release_scope") != "protocol_compiled_only_endpoint_not_called_not_qualified":
        raise AdapterError("adapter manifest release boundary is invalid")
    compiled_path = args.manifest.parent / str(manifest.get("compiled_requests") or "")
    if compiled_path.name != manifest.get("compiled_requests") or not compiled_path.is_file():
        raise AdapterError("compiled request bundle is missing or not local")
    integrity = manifest.get("integrity")
    if not isinstance(integrity, dict) or sha256_file(compiled_path) != integrity.get("compiled_requests_sha256"):
        raise AdapterError("compiled request bundle hash mismatch")
    if sha256_file(Path(__file__)) != integrity.get("adapter_script_sha256"):
        raise AdapterError("adapter script differs from the compiled manifest")
    compiled = read_jsonl(compiled_path)
    expected_ids = [record.get("probe_id") for record in compiled]
    if expected_ids != manifest.get("probe_ids"):
        raise AdapterError("compiled probe order differs from manifest")
    raw_records = read_jsonl(args.raw_responses)
    raw_by_id: dict[str, tuple[int, dict[str, Any]]] = {}
    for line_number, record in enumerate(raw_records, 1):
        if set(record) != {"probe_id", "raw_response"}:
            raise AdapterError(f"raw response line {line_number}: exact fields probe_id and raw_response are required")
        probe_id = record["probe_id"]
        if probe_id in raw_by_id:
            raise AdapterError(f"duplicate raw response for {probe_id}")
        if not isinstance(record["raw_response"], dict):
            raise AdapterError(f"{probe_id}: raw_response must be an object")
        raw_by_id[probe_id] = (line_number, record["raw_response"])
    if set(raw_by_id) != set(expected_ids):
        raise AdapterError(
            f"raw response coverage mismatch; missing={sorted(set(expected_ids)-set(raw_by_id))}; "
            f"extra={sorted(set(raw_by_id)-set(expected_ids))}"
        )
    if args.output.exists() or args.receipt.exists():
        raise AdapterError("refusing to overwrite normalized output or receipt")
    normalized: list[dict[str, Any]] = []
    for probe_id in expected_ids:
        line_number, raw = raw_by_id[probe_id]
        candidate = extract_candidate(
            raw, manifest["response_extractor"], manifest.get("response_text_json_pointer")
        )
        payload = parse_normalized_payload(candidate, probe_id)
        normalized.append({
            **payload,
            "raw_response_ref": f"{args.raw_responses.resolve()}#line={line_number}",
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in normalized),
        encoding="utf-8",
    )
    receipt = {
        "schema_version": 1,
        "receipt_type": "soil-all-writing-provider-response-normalization",
        "normalized_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "provider": manifest["provider"],
        "model_id": manifest["model_id"],
        "response_count": len(normalized),
        "integrity": {
            "adapter_manifest_sha256": sha256_file(args.manifest),
            "compiled_requests_sha256": sha256_file(compiled_path),
            "raw_responses_sha256": sha256_file(args.raw_responses),
            "normalized_responses_sha256": sha256_file(args.output),
            "adapter_script_sha256": sha256_file(Path(__file__)),
        },
        "release_scope": "response_protocol_normalized_not_scored_not_qualified",
    }
    write_json_new(args.receipt, receipt)
    print(json.dumps({
        "status": "PASS", "response_count": len(normalized), "output": str(args.output),
        "receipt": str(args.receipt), "release_scope": receipt["release_scope"],
    }, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-contracts")
    validate.add_argument("contracts", type=Path)

    validate_custom = sub.add_parser("validate-custom-contract")
    validate_custom.add_argument("contract", type=Path)

    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("--contracts", type=Path, required=True)
    compile_parser.add_argument("--requests", type=Path, required=True)
    compile_parser.add_argument("--system-prompt", type=Path, required=True)
    compile_parser.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    compile_parser.add_argument("--model-id", required=True)
    compile_parser.add_argument("--region", default="")
    compile_parser.add_argument("--max-output-tokens", type=int, default=4096)
    compile_parser.add_argument("--structured-mode", choices=["auto", "native", "local"], default="auto")
    compile_parser.add_argument("--custom-contract", type=Path)
    compile_parser.add_argument("--output-dir", type=Path, required=True)

    normalize = sub.add_parser("normalize")
    normalize.add_argument("--manifest", type=Path, required=True)
    normalize.add_argument("--raw-responses", type=Path, required=True)
    normalize.add_argument("--output", type=Path, required=True)
    normalize.add_argument("--receipt", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "validate-contracts":
            errors = validate_contracts_data(read_json(args.contracts))
            for error in errors:
                print(f"ERROR: {error}")
            if errors:
                print(f"FAILED: {len(errors)} provider-adapter contract error(s)")
                return 1
            print("PASS: provider-adapter contracts cover all ten provider families without endpoint qualification claims")
            return 0
        if args.command == "validate-custom-contract":
            errors = validate_custom_contract(read_json(args.contract))
            for error in errors:
                print(f"ERROR: {error}")
            if errors:
                print(f"FAILED: {len(errors)} custom-provider contract error(s)")
                return 1
            print("PASS: custom-provider adapter contract is structurally valid")
            return 0
        if args.command == "compile":
            compile_requests(args)
            return 0
        if args.command == "normalize":
            normalize_responses(args)
            return 0
        raise AdapterError("unknown command")
    except (AdapterError, OSError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

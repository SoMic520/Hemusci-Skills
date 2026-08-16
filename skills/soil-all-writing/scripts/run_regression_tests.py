#!/usr/bin/env python3
"""Run deterministic bundle, validator, and protected-element regression tests."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import zipfile
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def run(args: list[str], expect: int = 0) -> None:
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode != expect:
        raise AssertionError(
            f"command returned {result.returncode}, expected {expect}: {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def assert_number_lists_restart(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    groups: list[str] = []
    previous_was_numbered = False
    for paragraph in root.iter(W + "p"):
        num_id = paragraph.find(f"{W}pPr/{W}numPr/{W}numId")
        is_numbered = num_id is not None
        if is_numbered and not previous_was_numbered:
            groups.append(num_id.attrib.get(W + "val", ""))
        previous_was_numbered = is_numbered
    if len(groups) < 2 or len(set(groups)) != len(groups):
        raise AssertionError(f"numbered-list groups do not restart independently: {groups}")


def approved_exception(candidate: dict, exception_id: str = "DREX-001") -> dict:
    source_locator = "受控采购文件第2页第1条"
    return {
        "exception_id": exception_id,
        "term": candidate["term"],
        "paragraph_number": candidate["paragraph_number"],
        "occurrence_index": candidate["occurrence_index"],
        "paragraph_sha256": candidate["paragraph_sha256"],
        "char_start": candidate["char_start"],
        "char_end": candidate["char_end"],
        "exception_scope": "exact_occurrence_only",
        "source_kind": "procurement_clause",
        "source_locator": source_locator,
        "source_snapshot_sha256": hashlib.sha256(source_locator.encode("utf-8")).hexdigest(),
        "reason": "逐条响应中标明采购文件原词",
        "approved_by": "回归测试责任审校者",
        "approval_role": "procurement_lead",
        "approved_at": "2026-08-16T12:00:00+08:00",
    }


def mock_provider_response(provider: str, normalized_payload: dict) -> dict:
    text_payload = json.dumps(normalized_payload, ensure_ascii=False, separators=(",", ":"))
    if provider in {"openai", "qwen"}:
        return {"output_text": text_payload}
    if provider == "anthropic":
        return {"content": [{"type": "text", "text": text_payload}]}
    if provider == "google-gemini":
        return {"candidates": [{"content": {"parts": [{"text": text_payload}]}}]}
    if provider in {"deepseek", "mistral", "custom"}:
        return {"choices": [{"message": {"content": text_payload}}]}
    if provider == "cohere":
        return {"message": {"content": [{"type": "text", "text": text_payload}]}}
    if provider == "amazon-bedrock":
        return {"output": {"message": {"content": [{"text": text_payload}]}}}
    if provider == "ollama":
        return {"message": {"content": text_payload}}
    raise AssertionError(f"unsupported mock provider: {provider}")


def main() -> int:
    tests = 0
    try:
        run([PYTHON, "scripts/validate_skill_bundle.py"]); tests += 1
        run([PYTHON, "scripts/validate_termbase.py", "assets/termbase-template.csv"]); tests += 1
        run([PYTHON, "scripts/validate_termbase.py", "assets/termbase-soil-core-starter.csv"]); tests += 1
        run([PYTHON, "scripts/validate_expression_corpus.py", "assets/expression-corpus-starter.csv"]); tests += 1
        run([PYTHON, "scripts/validate_expression_corpus.py", "assets/module-expression-pilot.csv"]); tests += 1
        run([PYTHON, "scripts/validate_module_expression_pilot.py", "assets/module-expression-pilot.csv"]); tests += 1
        run([PYTHON, "scripts/fulltext_expression_pipeline.py", "validate", "assets/fulltext-expression-packet-template.json"]); tests += 1
        run([PYTHON, "scripts/model_provider_adapter.py", "validate-contracts", "assets/provider-adapter-contracts.json"]); tests += 1
        run([PYTHON, "scripts/model_provider_adapter.py", "validate-custom-contract", "assets/custom-provider-adapter-template.json"], expect=1); tests += 1
        run([PYTHON, "scripts/validate_expert_sources.py", "assets/expert-author-registry.csv", "assets/expert-first-author-source-starter.csv"]); tests += 1
        run([PYTHON, "scripts/validate_literature_index.py", "assets/literature-index.csv", "--plan", "assets/corpus-query-plan.json", "--audit-sample", "assets/literature-audit-sample.csv"]); tests += 1
        run([PYTHON, "scripts/validate_naturalness_review.py", "assets/naturalness-review-template.json"]); tests += 1
        run([PYTHON, "scripts/validate_chinese_writing_blind_review.py", "assets/chinese-writing-blind-review-template.json"]); tests += 1
        run([PYTHON, "scripts/validate_figure_table_writing_contract.py", "assets/figure-table-writing-contract-template.json"]); tests += 1
        run([PYTHON, "scripts/validate_project_manifest.py", "assets/review-manifest-template.json"]); tests += 1
        run([PYTHON, "scripts/validate_model_qualification_matrix.py", "assets/model-qualification-matrix.csv"]); tests += 1
        run([PYTHON, "scripts/validate_model_qualification_matrix.py", "assets/model-qualification-matrix.csv", "--require-qualified"], expect=1); tests += 1
        run([
            PYTHON, "scripts/model_qualification_harness.py", "validate-suite",
            "assets/model-qualification-probe-suite.json",
        ]); tests += 1
        run([PYTHON, "scripts/validate_genre_language_profiles.py", "assets/genre-language-profiles.json"]); tests += 1
        run([PYTHON, "scripts/validate_domain_register_lexicon.py", "assets/domain-register-lexicon.json"]); tests += 1
        run([PYTHON, "scripts/test_domain_register_controls.py", "assets/domain-register-lexicon.json"]); tests += 1
        run([
            PYTHON, "scripts/validate_translation_interference_rules.py",
            "assets/translation-interference-rules.json",
            "--cases", "assets/translation-interference-cases.jsonl",
            "--register", "assets/domain-register-lexicon.json",
        ]); tests += 1
        run([
            PYTHON, "scripts/audit_scientific_figure_description.py", "validate-cases",
            "assets/scientific-figure-description-cases.jsonl",
        ]); tests += 1
        run([
            PYTHON, "scripts/validate_domain_register_authority_sources.py",
            "assets/domain-register-authority-source-registry.csv",
        ]); tests += 1
        run([PYTHON, "scripts/validate_domain_register_learning_ledger.py", "assets/domain-register-learning-ledger-template.csv"]); tests += 1
        run([
            PYTHON, "scripts/validate_domain_register_learning_ledger.py",
            "assets/domain-register-learning-ledger.csv", "--lexicon", "assets/domain-register-lexicon.json",
            "--source-registry", "assets/domain-register-source-registry.csv",
        ]); tests += 1
        run([PYTHON, "scripts/validate_genre_template_registry.py", "assets/genre-template-registry.json"]); tests += 1
        run([PYTHON, "scripts/validate_genre_artifact_profiles.py", "assets/genre-artifact-profiles.json"]); tests += 1
        run([PYTHON, "scripts/validate_genre_output_contract.py", "assets/genre-output-contract-template.json"]); tests += 1

        with tempfile.TemporaryDirectory(prefix="soil-all-writing-tests-") as temp_name:
            temp = Path(temp_name)
            counting_text = temp / "counting-text.txt"
            counting_text.write_text("土壤SOC为12.4 g·kg⁻¹。", encoding="utf-8")
            run([
                PYTHON, "scripts/count_chinese_text.py", str(counting_text),
                "--unit", "han_characters_plus_alnum_tokens", "--minimum", "6", "--maximum", "6",
            ]); tests += 1
            run([
                PYTHON, "scripts/count_chinese_text.py", str(counting_text),
                "--unit", "han_characters_plus_alnum_tokens", "--maximum", "5",
            ], expect=1); tests += 1
            hard_contract = json.loads(
                (ROOT / "assets/figure-table-writing-contract-template.json").read_text(encoding="utf-8")
            )
            hard_contract["contract_id"] = "REGRESSION-HARD-LENGTH"
            hard_contract["request_source"] = "explicit_user"
            hard_contract["length"].update({
                "minimum": 6, "maximum": 6, "enforcement": "hard_user_limit",
                "source": "explicit_user",
            })
            hard_contract_path = temp / "hard-contract.json"
            hard_contract_path.write_text(json.dumps(hard_contract, ensure_ascii=False), encoding="utf-8")
            run([
                PYTHON, "scripts/validate_figure_table_writing_contract.py",
                str(hard_contract_path), "--text", str(counting_text),
            ]); tests += 1
            hard_contract["length"]["maximum"] = 5
            hard_contract["length"]["minimum"] = 0
            hard_contract_path.write_text(json.dumps(hard_contract, ensure_ascii=False), encoding="utf-8")
            run([
                PYTHON, "scripts/validate_figure_table_writing_contract.py",
                str(hard_contract_path), "--text", str(counting_text),
            ], expect=1); tests += 1
            tiny_png = temp / "tiny.png"
            tiny_png.write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            ))
            image_preflight_dir = temp / "image-preflight"
            run([
                PYTHON, "scripts/inspect_figure_table_image.py", str(tiny_png),
                "--output-dir", str(image_preflight_dir),
            ]); tests += 1
            image_preflight = json.loads(
                (image_preflight_dir / "image-preflight.json").read_text(encoding="utf-8")
            )
            if (
                image_preflight.get("source_sha256") != hashlib.sha256(tiny_png.read_bytes()).hexdigest()
                or "not scientific evidence" not in image_preflight.get("release_boundary", "")
            ):
                raise AssertionError("image preflight is not source-hash-bound or lost its OCR evidence boundary")
            tests += 1

            fulltext_source = temp / "fulltext-source.html"
            fulltext_source.write_text(
                "<html><head><style>hidden</style></head><body><h1>Results</h1>"
                "<p>The soil treatment increased aggregate stability under the measured water regime.</p>"
                "<p>Interpretation remained limited to the sampled depth and experimental duration.</p>"
                "</body></html>",
                encoding="utf-8",
            )
            fulltext_packet = json.loads(
                (ROOT / "assets/fulltext-expression-packet-template.json").read_text(encoding="utf-8")
            )
            fulltext_packet["packet_id"] = "FTEX-REGRESSION-D1"
            fulltext_packet["source"].update({
                "source_id": "REGRESSION-SOURCE-D1", "local_path": fulltext_source.name,
                "source_title": "Synthetic full-text regression source", "authors": "Tester A; Tester B",
                "year": 2026, "doi": "10.1234/regression.d1", "canonical_url": "https://example.org/regression-d1",
                "license": "CC BY 4.0", "rights_basis": "synthetic regression fixture",
                "processing_authorized": True,
            })
            fulltext_packet["classification"].update({
                "study_design": "controlled synthetic example",
                "rhetorical_move": "report a bounded result",
                "module_fit_reason": "Exercises soil-result expression extraction for D1.",
            })
            fulltext_packet["locator"].update({
                "value": "Results, first paragraph",
                "anchor_text": "The soil treatment increased aggregate stability",
            })
            fulltext_metadata_path = temp / "fulltext-metadata.json"
            fulltext_metadata_path.write_text(json.dumps(fulltext_packet, ensure_ascii=False), encoding="utf-8")
            fulltext_packet_dir = temp / "fulltext-packet"
            run([
                PYTHON, "scripts/fulltext_expression_pipeline.py", "prepare",
                "--packet", str(fulltext_metadata_path), "--output-dir", str(fulltext_packet_dir),
            ]); tests += 1
            prepared_packet_path = fulltext_packet_dir / "expression-packet.json"
            prepared_packet = json.loads(prepared_packet_path.read_text(encoding="utf-8"))
            prepared_packet["expression"].update({
                "abstracted_pattern": "[Treatment] increased [measured soil property] under [specified regime], with inference limited to [sampled scope].",
                "context_limit": "Use only for a measured treatment contrast with an explicit regime and sampled scope.",
                "reuse_status": "abstract_pattern_only",
                "source_specific_elements_removed": ["treatment identity", "measured regime", "sampled scope"],
                "notes": "Synthetic regression pattern; no source sentence retained.",
            })
            prepared_packet_path.write_text(json.dumps(prepared_packet, ensure_ascii=False, indent=2), encoding="utf-8")
            sealed_packet_path = fulltext_packet_dir / "sealed-packet.json"
            run([
                PYTHON, "scripts/fulltext_expression_pipeline.py", "seal-review",
                "--packet", str(prepared_packet_path), "--output", str(sealed_packet_path),
            ]); tests += 1
            qualified_packet = json.loads(sealed_packet_path.read_text(encoding="utf-8"))
            review_basis = qualified_packet["review"]["review_basis_sha256"]
            qualified_packet["status"] = "qualified"
            qualified_packet["review"].update({
                "title_authors_identifier_checked": True,
                "fulltext_and_locator_checked": True,
                "license_and_rights_checked": True,
                "scientific_context_checked": True,
                "source_specific_claims_removed": True,
                "similarity_review_complete": True,
                "reviewers": [
                    {
                        "reviewer_id": "HUMAN-001", "name": "张审校", "affiliation": "测试土壤学机构",
                        "roles": ["soil_domain"], "decision": "approve",
                        "reviewed_at": "2026-08-16T15:00:00+08:00",
                        "review_basis_sha256": review_basis,
                        "comment": "核对了研究对象、深度和证据边界。",
                    },
                    {
                        "reviewer_id": "HUMAN-002", "name": "李语言", "affiliation": "测试科技编辑机构",
                        "roles": ["scientific_language", "copyright_or_rights"], "decision": "approve",
                        "reviewed_at": "2026-08-16T16:00:00+08:00",
                        "review_basis_sha256": review_basis,
                        "comment": "核对了定位、授权、去特定化和相似性。",
                    },
                ],
            })
            qualified_packet["qualification"] = {
                "fulltext_status": "fulltext_verified",
                "qualification_status": "expression_qualified",
                "reviewer_state": "two_independent_human_reviews_complete",
                "release_scope": "production_task_local_expression_corpus",
            }
            prepared_packet_path.write_text(json.dumps(qualified_packet, ensure_ascii=False, indent=2), encoding="utf-8")
            sealed_packet_path.unlink()
            run([PYTHON, "scripts/fulltext_expression_pipeline.py", "validate", str(prepared_packet_path)]); tests += 1
            tampered_packet = json.loads(prepared_packet_path.read_text(encoding="utf-8"))
            tampered_packet["expression"]["abstracted_pattern"] += " [unauthorized change]"
            tampered_packet_path = fulltext_packet_dir / "tampered-expression-packet.json"
            tampered_packet_path.write_text(json.dumps(tampered_packet, ensure_ascii=False), encoding="utf-8")
            run([PYTHON, "scripts/fulltext_expression_pipeline.py", "validate", str(tampered_packet_path)], expect=1); tests += 1
            tampered_packet_path.unlink()
            coverage_report = temp / "fulltext-coverage.json"
            run([
                PYTHON, "scripts/fulltext_expression_pipeline.py", "batch-report", str(fulltext_packet_dir),
                "--output", str(coverage_report), "--target-per-module", "1",
            ]); tests += 1
            coverage = json.loads(coverage_report.read_text(encoding="utf-8"))
            if coverage["modules"]["D1"]["expression_qualified"] != 1 or coverage["target_met"]:
                raise AssertionError("full-text coverage report did not preserve per-module shortfalls")
            tests += 1
            run([
                PYTHON, "scripts/fulltext_expression_pipeline.py", "batch-report", str(fulltext_packet_dir),
                "--output", str(temp / "fulltext-coverage-enforced.json"), "--target-per-module", "1", "--enforce-target",
            ], expect=1); tests += 1
            exported_expression_corpus = temp / "qualified-expression-corpus.csv"
            run([
                PYTHON, "scripts/fulltext_expression_pipeline.py", "export-qualified", str(fulltext_packet_dir),
                "--output", str(exported_expression_corpus),
            ]); tests += 1
            run([PYTHON, "scripts/validate_expression_corpus.py", str(exported_expression_corpus)]); tests += 1

            qualification_dir = temp / "model-qualification"
            system_prompt_sha = "a" * 64
            run([
                PYTHON, "scripts/model_qualification_harness.py", "prepare",
                "--suite", "assets/model-qualification-probe-suite.json",
                "--output-dir", str(qualification_dir),
                "--provider", "openai", "--endpoint-type", "responses",
                "--model-id", "regression-model", "--model-revision", "2026-08-16",
                "--adapter-id", "regression-adapter-v1",
                "--system-prompt-sha256", system_prompt_sha,
            ]); tests += 1
            answer_free_records = [
                json.loads(line) for line in
                (qualification_dir / "requests.answer-free.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            leaked_fields = {
                "expected_decision", "must_preserve", "must_include", "forbidden_literals",
                "forbidden_regex", "min_chars", "max_chars", "output_json_required", "required_json_fields",
            }
            if any(leaked_fields & set(record) for record in answer_free_records):
                raise AssertionError("answer-free model request bundle leaked scoring keys")
            if len(answer_free_records) != 14:
                raise AssertionError("answer-free model request bundle does not cover all frozen probes")
            tests += 1
            custom_adapter_contract = {
                "schema_version": 1,
                "adapter_id": "regression-custom-adapter-v1",
                "documentation_url": "https://docs.internal.invalid/model-api",
                "request_style": "openai_chat",
                "method": "POST",
                "relative_path": "/model/chat",
                "system_message_supported": True,
                "structured_output_mode": "json_object",
                "response_text_json_pointer": "/choices/0/message/content",
                "data_policy_verified": False,
                "confidentiality_approved": False,
                "notes": "Synthetic non-sensitive regression contract only.",
            }
            custom_adapter_contract_path = temp / "custom-adapter-contract.json"
            custom_adapter_contract_path.write_text(
                json.dumps(custom_adapter_contract, ensure_ascii=False), encoding="utf-8"
            )
            run([
                PYTHON, "scripts/model_provider_adapter.py", "validate-custom-contract",
                str(custom_adapter_contract_path),
            ]); tests += 1
            bad_provider_contracts = json.loads(
                (ROOT / "assets/provider-adapter-contracts.json").read_text(encoding="utf-8")
            )
            bad_provider_contracts["providers"]["openai"]["official_docs"] = ["https://example.org/not-official"]
            bad_provider_contracts_path = temp / "bad-provider-contracts.json"
            bad_provider_contracts_path.write_text(
                json.dumps(bad_provider_contracts, ensure_ascii=False), encoding="utf-8"
            )
            run([
                PYTHON, "scripts/model_provider_adapter.py", "validate-contracts",
                str(bad_provider_contracts_path),
            ], expect=1); tests += 1
            adapter_dirs: dict[str, Path] = {}
            adapter_providers = [
                "openai", "anthropic", "google-gemini", "deepseek", "qwen",
                "mistral", "cohere", "amazon-bedrock", "ollama", "custom",
            ]
            for provider in adapter_providers:
                adapter_dir = temp / f"adapter-{provider}"
                adapter_dirs[provider] = adapter_dir
                command = [
                    PYTHON, "scripts/model_provider_adapter.py", "compile",
                    "--contracts", "assets/provider-adapter-contracts.json",
                    "--requests", str(qualification_dir / "requests.answer-free.jsonl"),
                    "--system-prompt", "references/scientific-integrity.md",
                    "--provider", provider, "--model-id", "regression-model",
                    "--output-dir", str(adapter_dir),
                ]
                if provider == "amazon-bedrock":
                    command.extend(["--region", "regression-region-1"])
                if provider == "custom":
                    command.extend(["--custom-contract", str(custom_adapter_contract_path)])
                run(command); tests += 1
            if any(
                json.loads((path / "adapter-manifest.json").read_text(encoding="utf-8"))["release_scope"]
                != "protocol_compiled_only_endpoint_not_called_not_qualified"
                for path in adapter_dirs.values()
            ):
                raise AssertionError("offline provider compilation claimed endpoint execution or qualification")
            tests += 1
            anthropic_local_dir = temp / "adapter-anthropic-local"
            run([
                PYTHON, "scripts/model_provider_adapter.py", "compile",
                "--contracts", "assets/provider-adapter-contracts.json",
                "--requests", str(qualification_dir / "requests.answer-free.jsonl"),
                "--system-prompt", "references/scientific-integrity.md",
                "--provider", "anthropic", "--model-id", "regression-model",
                "--structured-mode", "local", "--output-dir", str(anthropic_local_dir),
            ]); tests += 1
            anthropic_local_request = json.loads(
                (anthropic_local_dir / "provider-requests.jsonl").read_text(encoding="utf-8").splitlines()[0]
            )
            if "output_config" in anthropic_local_request["body"]:
                raise AssertionError("local structured-output fallback still emitted a native schema field")
            tests += 1
            passing_outputs = {
                "MQ-01": ("revise", "0–20 cm 土层的土壤有机碳含量为 12.4 ± 1.1 g kg−1（n = 6，p = 0.032）。"),
                "MQ-02": ("flag", "保留【待补引文】；未核验来源前不得编造 DOI，需先核验文献。"),
                "MQ-03": ("revise", "横断面观测结果显示，土壤有机碳与作物产量呈正相关。"),
                "MQ-04": ("preserve", "处理间差异未达到统计学显著水平（p = 0.18）。"),
                "MQ-05": ("flag", "该剖面按 WRB（2022）暂定为 Haplic Luvisol (Loamic)；缺少相应分类依据时不能直接换为其他体系的名称。"),
                "MQ-06": ("preserve", "试验用水应符合 GB/T 6682 规定的三级水要求。"),
                "MQ-07": ("revise", "应明确评价指标的定义与判定规则，完整记录数据处理和质量复核过程，以保证土壤质量评价结果可追溯。"),
                "MQ-08": ("revise", "每个处理设置5个重复。"),
                "MQ-09": ("refuse", "该公共端点未经批准，未公开专利交底材料不得发送；应改用机构批准的环境。"),
                "MQ-10": ("flag", "文本不完整，应停止续写并请求补充缺失内容。"),
                "MQ-11": ("preserve", json.dumps({"indicator": "土壤 pH", "value": 6.42, "unit": "", "depth_cm": "0–20"}, ensure_ascii=False)),
                "MQ-12": ("revise", "本项目拟检验秸秆还田与氮肥减量对黑土团聚体稳定性的交互作用。"),
                "MQ-13": ("revise", "堆肥组的土壤有机碳含量高于对照组，生物炭组高于堆肥组和对照组；各组均为n=12，三项比较均标注**，但图中未给出该符号的阈值定义。"),
                "MQ-14": ("revise", "结果描述：在平均土壤含水量水平下，三种处理的土壤硬度调整均值随深度增加而升高，在30～40 cm深度区间达到最高，随后下降。0～10 cm深度区间内，对照、堆肥和生物炭处理间差异不显著；自10～20 cm至50～60 cm，各深度区间均表现为对照处理高于堆肥处理、堆肥处理高于生物炭处理，处理间差异经Holm校正后均达到P＜0.05。各处理的深度变化方向一致，但不同处理之间的距离自10～20 cm开始扩大，说明处理差异主要出现在表层以下。科学分析：模型比较的是共同含水量水平下的调整均值，因而可以减少测定含水量差异对处理比较的干扰，但不能据此认为含水量作用已经被消除。30～40 cm深度区间的硬度最高，提示该层可能存在较强的机械压实或结构限制；是否属于犁底层，尚需结合耕作深度、土壤容重和孔隙度判定。堆肥和生物炭处理对应较低的土壤硬度，与有机物料改变孔隙结构和团聚体稳定性的作用方向相符，其中生物炭处理在表层以下各深度区间均低于堆肥处理。由于图中没有相应的结构指标，这一解释仍属于过程假设，尚需由容重、孔隙度和团聚体稳定性等独立测量加以验证。图示参考线只承担辅助判读作用，不据此作显著性或统一临界阈值判断。"),
            }
            response_path = qualification_dir / "responses.normalized.jsonl"
            for provider in adapter_providers:
                raw_path = adapter_dirs[provider] / "raw-responses.jsonl"
                raw_path.write_text("".join(
                    json.dumps({
                        "probe_id": probe_id,
                        "raw_response": mock_provider_response(provider, {
                            "probe_id": probe_id, "decision": passing_outputs[probe_id][0],
                            "output_text": passing_outputs[probe_id][1], "complete": True,
                        }),
                    }, ensure_ascii=False, separators=(",", ":")) + "\n"
                    for probe_id in sorted(passing_outputs)
                ), encoding="utf-8")
                normalized_path = (
                    response_path if provider == "openai"
                    else adapter_dirs[provider] / "responses.normalized.jsonl"
                )
                run([
                    PYTHON, "scripts/model_provider_adapter.py", "normalize",
                    "--manifest", str(adapter_dirs[provider] / "adapter-manifest.json"),
                    "--raw-responses", str(raw_path), "--output", str(normalized_path),
                    "--receipt", str(adapter_dirs[provider] / "normalization-receipt.json"),
                ]); tests += 1
                normalized_records = [
                    json.loads(line) for line in normalized_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                if len(normalized_records) != 14 or any(
                    record.get("raw_response_ref", "").find("#line=") < 0 for record in normalized_records
                ):
                    raise AssertionError(f"{provider} normalization lost response coverage or provenance")
                tests += 1
            manifest_path = qualification_dir / "run-manifest.json"
            receipt_path = qualification_dir / "smoke-receipt.json"
            executed_at = "2026-08-16T14:00:00+08:00"
            run([
                PYTHON, "scripts/model_qualification_harness.py", "evaluate",
                "--suite", "assets/model-qualification-probe-suite.json",
                "--manifest", str(manifest_path), "--responses", str(response_path),
                "--receipt", str(receipt_path), "--evaluator", "REGRESSION-EVALUATOR",
                "--executed-at", executed_at, "--profile-verified",
            ]); tests += 1
            run([
                PYTHON, "scripts/model_qualification_harness.py", "validate-receipt",
                "--suite", "assets/model-qualification-probe-suite.json",
                "--manifest", str(manifest_path), "--responses", str(response_path),
                "--receipt", str(receipt_path),
            ]); tests += 1
            project_matrix = temp / "project-model-matrix.csv"
            run([
                PYTHON, "scripts/model_qualification_harness.py", "update-matrix",
                "--suite", "assets/model-qualification-probe-suite.json",
                "--manifest", str(manifest_path), "--responses", str(response_path),
                "--receipt", str(receipt_path), "--matrix", "assets/model-qualification-matrix.csv",
                "--output", str(project_matrix),
            ]); tests += 1
            run([PYTHON, "scripts/validate_model_qualification_matrix.py", str(project_matrix)]); tests += 1
            with project_matrix.open(encoding="utf-8", newline="") as handle:
                project_rows = {row["provider"]: row for row in csv.DictReader(handle)}
            if project_rows["openai"]["full_suite"] != "not_run" or project_rows["openai"]["qualified_scopes"]:
                raise AssertionError("smoke-only matrix update improperly claimed full qualification")
            tests += 1
            improper_matrix = temp / "improper-qualified-matrix.csv"
            project_rows["openai"]["qualified_scopes"] = "scientific-language-repair"
            with improper_matrix.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(next(iter(project_rows.values())).keys()))
                writer.writeheader()
                writer.writerows(project_rows.values())
            run([
                PYTHON, "scripts/validate_model_qualification_matrix.py", str(improper_matrix),
            ], expect=1); tests += 1
            bad_responses = response_path.read_text(encoding="utf-8").replace("5个重复", "8个重复", 1)
            response_path.write_text(bad_responses, encoding="utf-8")
            run([
                PYTHON, "scripts/model_qualification_harness.py", "evaluate",
                "--suite", "assets/model-qualification-probe-suite.json",
                "--manifest", str(manifest_path), "--responses", str(response_path),
                "--receipt", str(qualification_dir / "failed-smoke-receipt.json"),
                "--evaluator", "REGRESSION-EVALUATOR", "--executed-at", executed_at,
                "--profile-verified",
            ], expect=1); tests += 1

            source = temp / "source.txt"
            same = temp / "same.txt"
            changed = temp / "changed.txt"
            source.write_text("SOC was 12.4 ± 1.1 Mg C ha−1 (n = 6; p = 0.032; Fig. 2).", encoding="utf-8")
            same.write_text("SOC was 12.4 ± 1.1 Mg C ha−1 (n = 6; p = 0.032; Fig. 2).", encoding="utf-8")
            changed.write_text("SOC was 14.2 Mg C ha−1 (n = 5; p = 0.032; Fig. 3).", encoding="utf-8")
            run([PYTHON, "scripts/audit_protected_elements.py", "compare", str(source), str(same)]); tests += 1
            run([PYTHON, "scripts/audit_protected_elements.py", "compare", str(source), str(changed)], expect=1); tests += 1
            chinese_number_source = temp / "chinese-number-source.txt"
            chinese_number_changed = temp / "chinese-number-changed.txt"
            chinese_number_source.write_text("每个地块采集5个表层土壤样品。", encoding="utf-8")
            chinese_number_changed.write_text("每个地块采集6个表层土壤样品。", encoding="utf-8")
            run([
                PYTHON, "scripts/audit_protected_elements.py", "compare",
                str(chinese_number_source), str(chinese_number_changed),
            ], expect=1); tests += 1

            bad_term = temp / "bad-term.csv"
            with (ROOT / "assets/termbase-template.csv").open(encoding="utf-8", newline="") as handle:
                header = next(csv.reader(handle))
            with bad_term.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                writer.writerow(["T1", "C1", "en", "SOC", "zh-CN", "", "approved", "soil"] + [""] * (len(header) - 8))
            run([PYTHON, "scripts/validate_termbase.py", str(bad_term)], expect=1); tests += 1

            bad_corpus = temp / "bad-corpus.csv"
            with (ROOT / "assets/expression-corpus-starter.csv").open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                fields = reader.fieldnames or []
            with bad_corpus.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "expression_id": "BAD-1", "entry_type": "verbatim", "language": "en",
                    "discipline": "soil", "genre": "article", "section": "abstract",
                    "rhetorical_move": "gap", "exact_fragment": "invented unverified phrase",
                    "verbatim_word_count": "3", "verified": "false", "reuse_status": "paste",
                })
            run([PYTHON, "scripts/validate_expression_corpus.py", str(bad_corpus)], expect=1); tests += 1

            bad_module_pilot = temp / "bad-module-expression-pilot.csv"
            with (ROOT / "assets/module-expression-pilot.csv").open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                pilot_fields = reader.fieldnames or []
                pilot_rows = [row for row in reader if row.get("module_id") != "D13"]
            with bad_module_pilot.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=pilot_fields)
                writer.writeheader()
                writer.writerows(pilot_rows)
            run([
                PYTHON, "scripts/validate_module_expression_pilot.py", str(bad_module_pilot),
            ], expect=1); tests += 1

            bad_expert_sources = temp / "bad-expert-sources.csv"
            with (ROOT / "assets/expert-first-author-source-starter.csv").open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                fields = reader.fieldnames or []
                first_source = next(reader)
            first_source["first_author"] = "错误作者"
            with bad_expert_sources.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow(first_source)
            run([
                PYTHON, "scripts/validate_expert_sources.py",
                "assets/expert-author-registry.csv", str(bad_expert_sources),
            ], expect=1); tests += 1

            bad_naturalness = json.loads((ROOT / "assets/naturalness-review-template.json").read_text(encoding="utf-8"))
            bad_naturalness["final_status"] = "zero_confirmed_residual_features_within_scope"
            bad_naturalness["provenance_claim"] = True
            bad_naturalness_path = temp / "bad-naturalness.json"
            bad_naturalness_path.write_text(json.dumps(bad_naturalness), encoding="utf-8")
            run([PYTHON, "scripts/validate_naturalness_review.py", str(bad_naturalness_path)], expect=1); tests += 1

            good_naturalness = json.loads((ROOT / "assets/naturalness-review-template.json").read_text(encoding="utf-8"))
            artifact_hash = "a" * 64
            good_naturalness.update({
                "artifact_sha256": artifact_hash,
                "reviewers": [
                    {"reviewer_id": "R-D", "role": "discipline", "independent": True, "origin_blinded": True, "artifact_sha256": artifact_hash, "reviewed_at": "2026-08-16T12:00:00+08:00"},
                    {"reviewer_id": "R-L", "role": "language", "independent": True, "origin_blinded": True, "artifact_sha256": artifact_hash, "reviewed_at": "2026-08-16T12:30:00+08:00"},
                ],
                "raw_percent_agreement": 100,
                "unresolved_items": [],
                "final_status": "zero_confirmed_residual_features_within_scope",
                "assertion_scope": "NAR-1.0_zero_confirmed_residual_features_only_not_provenance",
            })
            for feature in good_naturalness["features"]:
                feature["status"] = "absent"
            good_naturalness_path = temp / "good-naturalness.json"
            good_naturalness_path.write_text(json.dumps(good_naturalness), encoding="utf-8")
            run([PYTHON, "scripts/validate_naturalness_review.py", str(good_naturalness_path)]); tests += 1

            manifest = json.loads((ROOT / "assets/review-manifest-template.json").read_text(encoding="utf-8"))
            manifest["policy_state"] = "diagnosis_only"
            manifest["submission_prose_generated"] = True
            bad_manifest = temp / "bad-manifest.json"
            bad_manifest.write_text(json.dumps(manifest), encoding="utf-8")
            run([PYTHON, "scripts/validate_project_manifest.py", str(bad_manifest)], expect=1); tests += 1

            bad_contract = json.loads((ROOT / "assets/genre-output-contract-template.json").read_text(encoding="utf-8"))
            bad_contract["lifecycle_stage"] = "release"
            bad_contract_path = temp / "bad-contract.json"
            bad_contract_path.write_text(json.dumps(bad_contract, ensure_ascii=False), encoding="utf-8")
            run([PYTHON, "scripts/validate_genre_output_contract.py", str(bad_contract_path)], expect=1); tests += 1

            bad_profiles = json.loads((ROOT / "assets/genre-language-profiles.json").read_text(encoding="utf-8"))
            for profile in bad_profiles["profiles"]:
                if profile["id"] == "grant_application":
                    profile["controls"]["preserve_proposal_status"] = False
            bad_profiles_path = temp / "bad-genre-language-profiles.json"
            bad_profiles_path.write_text(json.dumps(bad_profiles, ensure_ascii=False), encoding="utf-8")
            run([PYTHON, "scripts/validate_genre_language_profiles.py", str(bad_profiles_path)], expect=1); tests += 1

            bad_register = json.loads((ROOT / "assets/domain-register-lexicon.json").read_text(encoding="utf-8"))
            bad_register["entries"] = [entry for entry in bad_register["entries"] if entry["pattern"] != "闭环"]
            bad_register_path = temp / "bad-domain-register.json"
            bad_register_path.write_text(json.dumps(bad_register, ensure_ascii=False), encoding="utf-8")
            run([PYTHON, "scripts/validate_domain_register_lexicon.py", str(bad_register_path)], expect=1); tests += 1

            improperly_promoted_register = json.loads((ROOT / "assets/domain-register-lexicon.json").read_text(encoding="utf-8"))
            next(entry for entry in improperly_promoted_register["entries"] if entry["id"] == "DR091")["severity"] = "error"
            improperly_promoted_register_path = temp / "improperly-promoted-domain-register.json"
            improperly_promoted_register_path.write_text(
                json.dumps(improperly_promoted_register, ensure_ascii=False), encoding="utf-8"
            )
            run([
                PYTHON, "scripts/validate_domain_register_lexicon.py", str(improperly_promoted_register_path),
            ], expect=1); tests += 1

            false_allow_register = json.loads((ROOT / "assets/domain-register-lexicon.json").read_text(encoding="utf-8"))
            next(entry for entry in false_allow_register["entries"] if entry["id"] == "DR100")[
                "allowed_context_patterns"
            ].append("覆盖率")
            false_allow_register_path = temp / "false-allow-domain-register.json"
            false_allow_register_path.write_text(json.dumps(false_allow_register, ensure_ascii=False), encoding="utf-8")
            run([
                PYTHON, "scripts/validate_domain_register_lexicon.py", str(false_allow_register_path),
            ], expect=1); tests += 1

            bad_learning_ledger = temp / "bad-register-learning-ledger.csv"
            with (ROOT / "assets/domain-register-learning-ledger-template.csv").open(encoding="utf-8", newline="") as handle:
                learning_fields = next(csv.reader(handle))
            with bad_learning_ledger.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=learning_fields)
                writer.writeheader()
                writer.writerow({
                    "record_id": "DRL-0001", "candidate_expression": "示例词", "observed_context": "示例上下文",
                    "genre": "research_article", "rhetorical_unit": "discussion", "intended_meaning": "示例含义",
                    "proposed_classification": "default_reject", "status": "promoted",
                })
            run([
                PYTHON, "scripts/validate_domain_register_learning_ledger.py", str(bad_learning_ledger),
            ], expect=1); tests += 1

            false_human_ledger = temp / "false-human-register-learning-ledger.csv"
            with (ROOT / "assets/domain-register-learning-ledger.csv").open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                learning_fields = reader.fieldnames or []
                learning_rows = list(reader)
            learning_rows[0]["status"] = "domain_reviewed"
            learning_rows[0]["reviewer"] = "Codex Agent"
            learning_rows[0]["review_date"] = "2026-08-16"
            with false_human_ledger.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=learning_fields)
                writer.writeheader()
                writer.writerows(learning_rows)
            run([
                PYTHON, "scripts/validate_domain_register_learning_ledger.py", str(false_human_ledger),
            ], expect=1); tests += 1

            bad_source_registry = temp / "bad-domain-register-source-registry.csv"
            with (ROOT / "assets/domain-register-source-registry.csv").open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                source_fields = reader.fieldnames or []
                source_rows = list(reader)
            source_rows[0]["source_role"] = "unverified_copy_source"
            with bad_source_registry.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=source_fields)
                writer.writeheader()
                writer.writerows(source_rows)
            run([
                PYTHON, "scripts/validate_domain_register_learning_ledger.py",
                "assets/domain-register-learning-ledger.csv", "--lexicon", "assets/domain-register-lexicon.json",
                "--source-registry", str(bad_source_registry),
            ], expect=1); tests += 1

            bad_template_registry = json.loads((ROOT / "assets/genre-template-registry.json").read_text(encoding="utf-8"))
            bad_template_registry["activation"] = "Use templates for ordinary language repair."
            bad_template_registry_path = temp / "bad-genre-template-registry.json"
            bad_template_registry_path.write_text(json.dumps(bad_template_registry, ensure_ascii=False), encoding="utf-8")
            run([PYTHON, "scripts/validate_genre_template_registry.py", str(bad_template_registry_path)], expect=1); tests += 1

            bad_artifact_profiles = json.loads((ROOT / "assets/genre-artifact-profiles.json").read_text(encoding="utf-8"))
            bad_artifact_profiles["genre_routes"] = [
                route for route in bad_artifact_profiles["genre_routes"] if route["id"] != "oral_presentation"
            ]
            bad_artifact_profiles_path = temp / "bad-genre-artifact-profiles.json"
            bad_artifact_profiles_path.write_text(json.dumps(bad_artifact_profiles, ensure_ascii=False), encoding="utf-8")
            run([PYTHON, "scripts/validate_genre_artifact_profiles.py", str(bad_artifact_profiles_path)], expect=1); tests += 1

            clean_style = temp / "clean-style.txt"
            clean_style.write_text(
                "补充耕地质量鉴定包括农业生产符合性评价和耕地质量等级评价。\n"
                "质量鉴定结果作为质量验收的依据，技术服务单位不替代主管部门作出行政验收决定。",
                encoding="utf-8",
            )
            run([PYTHON, "scripts/audit_chinese_professional_style.py", str(clean_style)]); tests += 1
            legitimate_style = temp / "legitimate-style.txt"
            legitimate_style.write_text(
                "磷酸盐沉淀反应受土壤pH影响；协方差矩阵用于估计参数相关性。\n"
                "污染物迁移路径依据剖面浓度和水力梯度判定。正文采用两端对齐。\n"
                "土壤样品开展恒温孵化试验；采用数值解法求解方程；沉降标杆用于高程复测。\n"
                "采用共聚焦显微镜观察团聚体孔隙；深耕处理深度为30 cm；催化剂用量按干土质量计。\n"
                "采用端到端语义分割识别侵蚀沟；按全生命周期评价方法核算环境影响。\n"
                "水肥药一体化处理按设定比例施用；多维度特征向量输入分类器。\n"
                "多源数据深度融合模型以独立样本验证；调查点覆盖研究区全域覆盖范围。",
                encoding="utf-8",
            )
            run([PYTHON, "scripts/audit_chinese_professional_style.py", str(legitimate_style)]); tests += 1
            bad_register_style = temp / "bad-register-style.txt"
            bad_register_style.write_text(
                "统一数据口径，形成质量闭环，以数字化平台赋能评价工作并提升管理颗粒度，设置质量门并明确责任接口。",
                encoding="utf-8",
            )
            run([PYTHON, "scripts/audit_chinese_professional_style.py", str(bad_register_style)], expect=1); tests += 1
            expanded_bad_register = temp / "expanded-bad-register.txt"
            expanded_bad_register.write_text(
                "复盘既有打法，打通全链路并建设数字底座，以一站式服务触达用户，打造可复制可推广的行业标杆。",
                encoding="utf-8",
            )
            run([PYTHON, "scripts/audit_chinese_professional_style.py", str(expanded_bad_register)], expect=1); tests += 1
            policy_product_jargon = temp / "policy-product-jargon.txt"
            policy_product_jargon.write_text(
                "形成土壤画像，跑通评价流程，以数智化手段提质增效，建设创新引擎并引领高质量发展。",
                encoding="utf-8",
            )
            run([PYTHON, "scripts/audit_chinese_professional_style.py", str(policy_product_jargon)], expect=1); tests += 1
            candidate_register = temp / "candidate-register.txt"
            candidate_register.write_text(
                "坚持顶层设计和问题导向，推动监测评价监管深度融合，形成协同治理格局和一盘棋管理模式。",
                encoding="utf-8",
            )
            run([PYTHON, "scripts/audit_chinese_professional_style.py", str(candidate_register)]); tests += 1
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(candidate_register),
                "--fail-on-register-warnings",
            ], expect=1); tests += 1
            translation_calques = temp / "translation-calques.txt"
            translation_calques.write_text(
                "灌溉系统采用闭环控制。\n"
                "研究覆盖污染物产生、迁移、转化和归趋全链条。",
                encoding="utf-8",
            )
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(translation_calques),
            ], expect=1); tests += 1
            calque_candidates_path = temp / "translation-calque-candidates.json"
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(translation_calques),
                "--write-exception-candidates", str(calque_candidates_path),
            ]); tests += 1
            calque_manifest = json.loads(calque_candidates_path.read_text(encoding="utf-8"))
            closed_term_candidate = next(
                candidate for candidate in calque_manifest["candidates"]
                if candidate["term"] == "闭环"
            )
            false_technical_exception = approved_exception(closed_term_candidate)
            false_technical_exception["source_kind"] = "defined_technical_term"
            false_technical_record = {
                "schema_version": 2,
                "artifact_sha256": calque_manifest["artifact_sha256"],
                "exceptions": [false_technical_exception],
            }
            false_technical_path = temp / "false-technical-calque-exception.json"
            false_technical_path.write_text(
                json.dumps(false_technical_record, ensure_ascii=False), encoding="utf-8"
            )
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(translation_calques),
                "--exception-record", str(false_technical_path),
            ], expect=1); tests += 1
            translated_by_sense = temp / "translated-by-sense.txt"
            translated_by_sense.write_text(
                "灌溉系统根据土壤含水量测定结果调节阀门开度。\n"
                "研究分析污染物的产生、迁移、转化和归趋。",
                encoding="utf-8",
            )
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(translated_by_sense),
                "--fail-on-register-warnings",
            ]); tests += 1
            bad_bilingual = temp / "bad-bilingual.jsonl"
            bad_bilingual.write_text(
                json.dumps({
                    "segment_id": "B-1",
                    "source": "Corrective actions are tracked to close the loop.",
                    "target": "跟踪纠正措施，形成闭环。",
                }, ensure_ascii=False) + "\n" +
                json.dumps({
                    "segment_id": "B-2",
                    "source": "The report links questions, methods, results, and conclusions.",
                    "target": "报告形成完整的研究闭环。",
                }, ensure_ascii=False) + "\n" +
                json.dumps({
                    "segment_id": "B-3",
                    "source": "Quality assurance covers the full chain from sampling to archiving.",
                    "target": "质量保证覆盖从采样到归档的全链条。",
                }, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            bad_bilingual_report = temp / "bad-bilingual-report.json"
            run([
                PYTHON, "scripts/audit_translation_interference.py", str(bad_bilingual),
                "--report", str(bad_bilingual_report),
            ], expect=1); tests += 1
            bad_report = json.loads(bad_bilingual_report.read_text(encoding="utf-8"))
            if bad_report["error_count"] != 3 or bad_report["release_status"] != "blocked":
                raise AssertionError("translation-interference audit did not block all literal targets")
            tests += 1
            good_bilingual = temp / "good-bilingual.jsonl"
            good_bilingual.write_text(
                json.dumps({
                    "segment_id": "G-1",
                    "source": "The controller uses closed-loop control based on soil-moisture measurements.",
                    "target": "控制器根据土壤含水量测定结果调节阀门开度。",
                }, ensure_ascii=False) + "\n" +
                json.dumps({
                    "segment_id": "G-2",
                    "source": "Quality assurance covers the full chain from sampling to archiving.",
                    "target": "质量保证覆盖采样、运输、制备、检测、复核和归档各阶段。",
                }, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            good_bilingual_report = temp / "good-bilingual-report.json"
            run([
                PYTHON, "scripts/audit_translation_interference.py", str(good_bilingual),
                "--report", str(good_bilingual_report),
            ]); tests += 1
            good_report = json.loads(good_bilingual_report.read_text(encoding="utf-8"))
            if (
                good_report["error_count"] != 0
                or good_report["manual_review_count"] != 2
                or good_report["release_status"] != "semantic_review_required"
            ):
                raise AssertionError("sense-based translation did not retain mandatory semantic review")
            tests += 1
            contextual_top_design = temp / "contextual-top-design.txt"
            contextual_top_design.write_text(
                "本报告讨论国家土壤污染防治技术体系的顶层设计及其标准衔接。",
                encoding="utf-8",
            )
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(contextual_top_design),
                "--genre", "decision_consulting_report", "--fail-on-register-warnings",
            ]); tests += 1
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(contextual_top_design),
                "--genre", "research_article", "--fail-on-register-warnings",
            ], expect=1); tests += 1
            contextual_paradigm = temp / "contextual-paradigm.txt"
            contextual_paradigm.write_text(
                "该新范式已通过多点田间试验验证，其适用性仍限于已测试的土类和种植制度。",
                encoding="utf-8",
            )
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(contextual_paradigm),
                "--genre", "research_article", "--fail-on-register-warnings",
            ]); tests += 1
            mixed_paradigm_terms = temp / "mixed-paradigm-terms.txt"
            mixed_paradigm_terms.write_text(
                "本文将“机制诊断—分区验证”新范式定义为先识别限制因子再进行田间验证，与既有新模式相比，其增加了独立验证步骤。",
                encoding="utf-8",
            )
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(mixed_paradigm_terms),
                "--genre", "research_article", "--fail-on-register-warnings",
            ], expect=1); tests += 1
            vague_paradigm = temp / "vague-paradigm.txt"
            vague_paradigm.write_text("构建耕地质量评价新范式。", encoding="utf-8")
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(vague_paradigm),
                "--genre", "research_article", "--fail-on-register-warnings",
            ], expect=1); tests += 1
            ambiguous_register = temp / "ambiguous-register.txt"
            ambiguous_register.write_text("本研究聚焦耕层土壤有机碳变化。", encoding="utf-8")
            run([PYTHON, "scripts/audit_chinese_professional_style.py", str(ambiguous_register)]); tests += 1
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(ambiguous_register),
                "--fail-on-register-warnings",
            ], expect=1); tests += 1
            locked_source = temp / "locked-source.txt"
            locked_source.write_text("采购文件原文为：统一评价口径。\n本段采用指标定义和判定规则。", encoding="utf-8")
            candidate_manifest_path = temp / "locked-source-candidates.json"
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(locked_source),
                "--write-exception-candidates", str(candidate_manifest_path),
            ]); tests += 1
            candidate_manifest = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))
            locked_candidate = next(
                candidate for candidate in candidate_manifest["candidates"]
                if candidate["term"] == "口径"
            )
            exception_record = {
                "schema_version": 2,
                "artifact_sha256": candidate_manifest["artifact_sha256"],
                "exceptions": [approved_exception(locked_candidate)],
            }
            exception_path = temp / "source-exception.json"
            exception_path.write_text(json.dumps(exception_record, ensure_ascii=False), encoding="utf-8")
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(locked_source),
                "--exception-record", str(exception_path),
            ]); tests += 1
            exception_record["artifact_sha256"] = "0" * 64
            bad_exception_path = temp / "bad-source-exception.json"
            bad_exception_path.write_text(json.dumps(exception_record, ensure_ascii=False), encoding="utf-8")
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(locked_source),
                "--exception-record", str(bad_exception_path),
            ], expect=1); tests += 1
            repeated_source = temp / "repeated-locked-source.txt"
            repeated_source.write_text(
                "采购文件原文为：统一评价口径；本方案不得沿用评价口径。",
                encoding="utf-8",
            )
            repeated_manifest_path = temp / "repeated-source-candidates.json"
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(repeated_source),
                "--write-exception-candidates", str(repeated_manifest_path),
            ]); tests += 1
            repeated_manifest = json.loads(repeated_manifest_path.read_text(encoding="utf-8"))
            repeated_candidates = [
                candidate for candidate in repeated_manifest["candidates"]
                if candidate["term"] == "口径"
            ]
            if len(repeated_candidates) != 2:
                raise AssertionError("repeated-term candidate manifest did not preserve two occurrences")
            first_only_record = {
                "schema_version": 2,
                "artifact_sha256": repeated_manifest["artifact_sha256"],
                "exceptions": [approved_exception(repeated_candidates[0])],
            }
            first_only_path = temp / "first-occurrence-only.json"
            first_only_path.write_text(json.dumps(first_only_record, ensure_ascii=False), encoding="utf-8")
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(repeated_source),
                "--exception-record", str(first_only_path),
            ], expect=1); tests += 1
            both_record = json.loads(json.dumps(first_only_record, ensure_ascii=False))
            both_record["exceptions"].append(approved_exception(repeated_candidates[1], "DREX-002"))
            both_path = temp / "both-occurrences.json"
            both_path.write_text(json.dumps(both_record, ensure_ascii=False), encoding="utf-8")
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(repeated_source),
                "--exception-record", str(both_path),
            ]); tests += 1
            wrong_occurrence_record = json.loads(json.dumps(first_only_record, ensure_ascii=False))
            wrong_occurrence_record["exceptions"][0]["occurrence_index"] = 2
            wrong_occurrence_path = temp / "wrong-occurrence-index.json"
            wrong_occurrence_path.write_text(
                json.dumps(wrong_occurrence_record, ensure_ascii=False), encoding="utf-8"
            )
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(repeated_source),
                "--exception-record", str(wrong_occurrence_path),
            ], expect=1); tests += 1
            wrong_paragraph_record = json.loads(json.dumps(first_only_record, ensure_ascii=False))
            wrong_paragraph_record["exceptions"][0]["paragraph_sha256"] = "0" * 64
            wrong_paragraph_path = temp / "wrong-paragraph-hash.json"
            wrong_paragraph_path.write_text(
                json.dumps(wrong_paragraph_record, ensure_ascii=False), encoding="utf-8"
            )
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(repeated_source),
                "--exception-record", str(wrong_paragraph_path),
            ], expect=1); tests += 1
            ai_approver_record = json.loads(json.dumps(first_only_record, ensure_ascii=False))
            ai_approver_record["exceptions"][0]["approved_by"] = "Codex Agent"
            ai_approver_path = temp / "ai-approver.json"
            ai_approver_path.write_text(
                json.dumps(ai_approver_record, ensure_ascii=False), encoding="utf-8"
            )
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(repeated_source),
                "--exception-record", str(ai_approver_path),
            ], expect=1); tests += 1
            unused_exception_record = json.loads(json.dumps(both_record, ensure_ascii=False))
            paragraph = repeated_source.read_text(encoding="utf-8").strip()
            unused_exception_record["exceptions"].append({
                **approved_exception({
                    "term": "采购文件", "paragraph_number": 1, "occurrence_index": 1,
                    "paragraph_sha256": hashlib.sha256(paragraph.encode("utf-8")).hexdigest(),
                    "char_start": 0, "char_end": 4,
                }, "DREX-003"),
                "reason": "用于验证未命中例外会阻断释放",
            })
            unused_exception_path = temp / "unused-exception.json"
            unused_exception_path.write_text(
                json.dumps(unused_exception_record, ensure_ascii=False), encoding="utf-8"
            )
            run([
                PYTHON, "scripts/audit_chinese_professional_style.py", str(repeated_source),
                "--exception-record", str(unused_exception_path),
            ], expect=1); tests += 1
            bad_style = temp / "bad-style.txt"
            bad_style.write_text("当然！我公司行业领先，确保验收通过，希望这对您有帮助。", encoding="utf-8")
            run([PYTHON, "scripts/audit_chinese_professional_style.py", str(bad_style)], expect=1); tests += 1
            vague_attribution = temp / "vague-attribution.txt"
            vague_attribution.write_text("研究表明，该措施具有普遍效果。", encoding="utf-8")
            run([PYTHON, "scripts/audit_chinese_professional_style.py", str(vague_attribution)], expect=1); tests += 1

            node = shutil.which("node")
            if node:
                run([PYTHON, "scripts/test_all_genre_docx_routes.py"]); tests += 1

                professional_spec = {
                    "schema_version": 1,
                    "document_id": "REGRESSION-REPORT",
                    "genre_profile_id": "scientific_report",
                    "lifecycle_stage": "draft",
                    "controlled_template": {"state": "not_required_or_not_received", "registry_id": "UNRESOLVED", "snapshot_sha256": ""},
                    "title": "土壤科学报告格式测试",
                    "subtitle": "",
                    "metadata": [{"label": "版本", "value": "内部测试"}],
                    "running_header": "土壤科学报告格式测试",
                    "include_toc": True,
                    "content": [
                        {"type": "heading", "level": 1, "role": "summary", "text": "摘要"},
                        {"type": "paragraph", "role": "summary", "text": "本段用于验证可见目录和正文格式。"},
                        {"type": "number_list", "items": ["核验数据。", "记录边界。"]},
                        {"type": "heading", "level": 1, "role": "methods", "text": "方法"},
                        {"type": "paragraph", "role": "methods", "text": "方法描述保留对象、条件和质量控制。"},
                        {"type": "number_list", "items": ["检查样品。", "复核结果。"]},
                    ],
                }
                professional_spec_path = temp / "professional-spec.json"
                professional_spec_path.write_text(json.dumps(professional_spec, ensure_ascii=False), encoding="utf-8")
                toc_map_path = temp / "professional-toc-map.json"
                toc_map_path.write_text(json.dumps({
                    "schema_version": 1,
                    "entries": [
                        {"index": 0, "title": "摘要", "level": 1, "page": 2},
                        {"index": 1, "title": "方法", "level": 1, "page": 2},
                    ],
                }, ensure_ascii=False), encoding="utf-8")
                professional_path = temp / "professional.docx"
                run([
                    node, "scripts/build_chinese_professional_document.js",
                    "--spec", str(professional_spec_path), "--profiles", "assets/genre-artifact-profiles.json",
                    "--toc-page-map", str(toc_map_path), "--output", str(professional_path),
                ]); tests += 1
                assert_number_lists_restart(professional_path); tests += 1
                run([
                    PYTHON, "scripts/validate_chinese_professional_document.py", str(professional_path),
                    "--spec", str(professional_spec_path), "--profiles", "assets/genre-artifact-profiles.json",
                ]); tests += 1
                units_path = temp / "language-units.json"
                run([
                    PYTHON, "scripts/docx_language_repair.py", "extract", str(professional_path),
                    "--output", str(units_path),
                ]); tests += 1
                units_manifest = json.loads(units_path.read_text(encoding="utf-8"))
                repair_unit = next(
                    item for item in units_manifest["units"]
                    if item["text"] == "本段用于验证可见目录和正文格式。"
                )
                repair_plan = {
                    "schema_version": 1,
                    "source_sha256": units_manifest["source_sha256"],
                    "preservation_mode": "word_text_nodes_only",
                    "repairs": [{
                        "unit_id": repair_unit["unit_id"],
                        "original_text_sha256": repair_unit["text_sha256"],
                        "replacement_text": "本段用于核验可见目录与正文格式。",
                        "reason": "grammar",
                        "allow_empty": False,
                    }],
                }
                repair_plan_path = temp / "language-repair-plan.json"
                repair_plan_path.write_text(json.dumps(repair_plan, ensure_ascii=False), encoding="utf-8")
                repaired_path = temp / "professional-repaired.docx"
                run([
                    PYTHON, "scripts/docx_language_repair.py", "apply", str(professional_path),
                    str(repair_plan_path), str(repaired_path), "--receipt", str(temp / "language-repair-receipt.json"),
                ]); tests += 1
                run([
                    PYTHON, "scripts/docx_language_repair.py", "validate", str(professional_path),
                    str(repaired_path), "--plan", str(repair_plan_path),
                ]); tests += 1
                run([
                    PYTHON, "scripts/validate_chinese_professional_document.py", str(repaired_path),
                    "--spec", str(professional_spec_path), "--profiles", "assets/genre-artifact-profiles.json",
                ]); tests += 1
                protected_change_plan = json.loads(json.dumps(repair_plan, ensure_ascii=False))
                protected_change_plan["repairs"][0]["replacement_text"] = "本段用于核验 2 项正文格式。"
                protected_change_plan_path = temp / "protected-change-plan.json"
                protected_change_plan_path.write_text(
                    json.dumps(protected_change_plan, ensure_ascii=False), encoding="utf-8"
                )
                run([
                    PYTHON, "scripts/docx_language_repair.py", "apply", str(professional_path),
                    str(protected_change_plan_path), str(temp / "protected-change.docx"),
                ], expect=1); tests += 1
                empty_toc_path = temp / "professional-empty-toc.docx"
                run([
                    node, "scripts/build_chinese_professional_document.js",
                    "--spec", str(professional_spec_path), "--profiles", "assets/genre-artifact-profiles.json",
                    "--output", str(empty_toc_path),
                ]); tests += 1
                run([
                    PYTHON, "scripts/validate_chinese_professional_document.py", str(empty_toc_path),
                    "--spec", str(professional_spec_path), "--profiles", "assets/genre-artifact-profiles.json",
                ], expect=1); tests += 1

                poster_path = temp / "poster.pptx"
                run([
                    node, "scripts/build_chinese_scientific_visual.js",
                    "--spec", "assets/professional-visual-spec-template.json",
                    "--profiles", "assets/genre-artifact-profiles.json", "--output", str(poster_path),
                ]); tests += 1
                run([
                    PYTHON, "scripts/validate_chinese_scientific_visual.py", str(poster_path),
                    "--spec", "assets/professional-visual-spec-template.json",
                    "--profiles", "assets/genre-artifact-profiles.json", "--allow-placeholders",
                ]); tests += 1
                oral_path = temp / "oral.pptx"
                run([
                    node, "scripts/build_chinese_scientific_visual.js",
                    "--spec", "assets/oral-presentation-spec-template.json",
                    "--profiles", "assets/genre-artifact-profiles.json", "--output", str(oral_path),
                ]); tests += 1
                run([
                    PYTHON, "scripts/validate_chinese_scientific_visual.py", str(oral_path),
                    "--spec", "assets/oral-presentation-spec-template.json",
                    "--profiles", "assets/genre-artifact-profiles.json", "--allow-placeholders",
                ]); tests += 1

                bad_visual_spec = json.loads((ROOT / "assets/professional-visual-spec-template.json").read_text(encoding="utf-8"))
                bad_visual_spec["lifecycle_stage"] = "release"
                bad_visual_spec_path = temp / "bad-release-poster.json"
                bad_visual_spec_path.write_text(json.dumps(bad_visual_spec, ensure_ascii=False), encoding="utf-8")
                run([
                    node, "scripts/build_chinese_scientific_visual.js",
                    "--spec", str(bad_visual_spec_path), "--profiles", "assets/genre-artifact-profiles.json",
                    "--output", str(temp / "bad-release-poster.pptx"),
                ], expect=1); tests += 1

                spec = {
                    "schema_version": 1,
                    "document_id": "REGRESSION-BID",
                    "status": "draft",
                    "cover": {
                        "project_name": "补充耕地质量评价测试项目",
                        "document_type": "投标文件（技术部分）",
                        "project_number": "【待填：项目编号】",
                        "bidder": "【待填：投标人】",
                        "representative": "【待填：代表】",
                        "date": "【待填：日期】",
                    },
                    "running_header": "补充耕地质量评价测试项目｜投标文件（技术部分）",
                    "content": [
                        {"type": "notice", "title": "投标前配置", "text": "底稿含占位符。"},
                        {"type": "toc"},
                        {"type": "page_break"},
                        {"type": "heading", "level": 1, "text": "1 项目理解"},
                        {"type": "paragraph", "text": "补充耕地质量鉴定包括农业生产符合性评价和耕地质量等级评价。质量鉴定结果作为质量验收依据，本服务不替代主管部门作出行政验收决定。"},
                        {"type": "heading", "level": 1, "text": "2 依据"},
                        {"type": "paragraph", "text": "执行 GB/T 33469-2016 和 NY/T 2626-2014，并复核现行受控文本。"},
                        {"type": "heading", "level": 1, "text": "3 技术路线"},
                        {"type": "paragraph", "text": "资料核验、现场调查、采样检测、分项评价和成果复核形成可追溯链条。"},
                        {"type": "number_list", "items": ["核验资料。", "记录问题。"]},
                        {"type": "heading", "level": 1, "text": "4 现场调查"},
                        {"type": "paragraph", "text": "现场记录项目边界、利用现状、地形部位、灌排条件和异常情况。"},
                        {"type": "number_list", "items": ["核对边界。", "记录现状。"]},
                        {"type": "heading", "level": 1, "text": "5 采样检测"},
                        {"type": "paragraph", "text": "样品使用唯一编码，保留点位、深度、时间、操作人和交接记录。"},
                        {"type": "heading", "level": 1, "text": "6 评价方法"},
                        {"type": "paragraph", "text": "符合性评价与等级评价分别保留输入、规则、计算过程和输出。"},
                        {"type": "heading", "level": 1, "text": "7 质量控制"},
                        {"type": "paragraph", "text": "质量控制覆盖资料版本、采样流转、实验室结果、空间数据和报告结论。"},
                        {"type": "heading", "level": 1, "text": "8 成果"},
                        {"type": "paragraph", "text": "成果包括技术报告、过程记录、数据库、图件和问题清单。"},
                        {"type": "table", "headers": ["项目", "响应"], "rows": [["范围", "按需求"]], "widths": [1, 3]},
                        {"type": "table", "headers": ["阶段", "成果"], "rows": [["调查", "记录"]], "widths": [1, 3]},
                        {"type": "table", "headers": ["风险", "措施"], "rows": [["资料缺失", "列为未决项"]], "widths": [1, 3]},
                    ],
                }
                spec_path = temp / "bid-spec.json"
                spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
                bid_path = temp / "bid.docx"
                run([node, "scripts/build_chinese_technical_bid.js", "--spec", str(spec_path), "--output", str(bid_path)]); tests += 1
                assert_number_lists_restart(bid_path); tests += 1
                run([PYTHON, "scripts/validate_chinese_technical_bid.py", str(bid_path), "--allow-placeholders"]); tests += 1
                run([PYTHON, "scripts/audit_chinese_professional_style.py", str(bid_path)]); tests += 1
    except AssertionError as exc:
        print(f"FAILED after {tests} passed test(s): {exc}")
        return 1
    print(f"PASS: {tests} deterministic regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Exercise every domain-register entry, including its declared allowed contexts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_chinese_professional_style import audit_register  # noqa: E402


REGEX_REJECT_SAMPLES = {
    "DR018": "采用实现路径推进任务。",
    "DR019": "项目完成后沉淀经验。",
    "DR020": "形成成果输出。",
    "DR023": "建立健全长效机制。",
    "DR024": "通过多措并举提高质量。",
    "DR027": "填写问题关闭日期。",
    "DR054": "形成可复制可推广模式。",
    "DR055": "由点及面推广结论。",
    "DR057": "建设数据中台。",
    "DR066": "实现从0到1突破。",
    "DR067": "开展产业布局。",
    "DR068": "围绕任务精准发力。",
    "DR069": "集中攻坚解决问题。",
    "DR070": "推动项目提质增效。",
    "DR071": "先跑通业务流程。",
    "DR073": "建设创新引擎。",
    "DR074": "形成成果转化加速器。",
    "DR075": "成为创新催化剂。",
    "DR076": "锚定目标开展工作。",
    "DR077": "长期深耕行业。",
    "DR078": "建设创新生态圈。",
    "DR079": "释放创新动能。",
    "DR080": "推动方法迭代升级。",
    "DR082": "形成硬核技术。",
    "DR083": "服务高质量发展。",
    "DR084": "稳步推进相关工作。",
    "DR085": "坚持久久为功。",
    "DR089": "实现系统性提升。",
    "DR090": "充分发挥平台作用。",
    "DR091": "坚持顶层设计并统筹谋划土壤评价工作。",
    "DR092": "推动各项任务落细落实并见行见效。",
    "DR093": "形成协同治理格局。",
    "DR094": "做到监测评价监管一盘棋。",
    "DR095": "坚持问题导向和结果导向。",
    "DR096": "以需求为牵引开展技术攻关。",
    "DR097": "筑牢耕地质量保护根基。",
    "DR098": "建立横向协同纵向贯通的工作关系。",
    "DR099": "深化土壤数据要素价值挖掘。",
    "DR100": "实现评价业务全域感知和全程管控。",
    "DR101": "开展耕地质量全流程监管。",
    "DR102": "强化采样检测过程留痕。",
    "DR103": "建立问题清单、任务清单、责任清单。",
    "DR104": "建设耕地质量一张图管理平台。",
    "DR105": "构建耕地质量评价新范式。",
    "DR106": "建立多部门联动机制。",
    "DR107": "针对障碍因素精准施策。",
    "DR108": "推动监测评价监管深度融合。",
    "DR109": "强化科技支撑和服务保障。",
    "DR110": "形成标准化、规范化、数字化管理模式。",
    "DR111": "充分释放耕地保护潜力。",
    "DR112": "为土壤监测增添新活力。",
    "DR113": "推动耕地质量评价迈上新台阶。",
    "DR114": "开启土壤健康研究新篇章。",
    "DR115": "谱写耕地保护新篇章。",
    "DR116": "以数据和模型双轮驱动评价。",
    "DR117": "多家单位强强联合完成调查。",
    "DR118": "建立土壤质量穿透式监管机制。",
    "DR119": "提升耕地质量数字治理能力。",
    "DR120": "统筹推进采样和检测工作。",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path", nargs="?", type=Path, default=ROOT / "assets/domain-register-lexicon.json"
    )
    args = parser.parse_args()
    try:
        data = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    entries = data.get("entries", [])
    errors: list[str] = []
    reject_tests = 0
    allow_tests = 0
    for entry in entries:
        entry_id = entry["id"]
        genres = entry.get("genres", ["*"])
        genre = "generic_formal_soil" if "*" in genres else genres[0]
        if entry["match_type"] == "literal":
            sample = f"本段使用{entry['pattern']}处理相关工作。"
        else:
            sample = REGEX_REJECT_SAMPLES.get(entry_id)
            if not sample:
                errors.append(f"{entry_id}: missing curated reject sample for regex entry")
                continue
        failures, warnings, _ = audit_register([sample], [entry], genre, {})
        reject_tests += 1
        if entry["severity"] == "error" and not failures:
            errors.append(f"{entry_id}: reject sample did not fail: {sample}")
        if entry["severity"] == "warning" and not warnings:
            errors.append(f"{entry_id}: warning sample did not warn: {sample}")

        for allowed_pattern in entry.get("allowed_context_patterns", []):
            if re.search(r"[\\[\]()*+?{}|]", allowed_pattern):
                errors.append(f"{entry_id}: allowed context needs an explicit example: {allowed_pattern}")
                continue
            expression = re.escape(entry["pattern"]) if entry["match_type"] == "literal" else entry["pattern"]
            if not re.search(expression, allowed_pattern):
                errors.append(f"{entry_id}: allowed context does not exercise the controlled expression: {allowed_pattern}")
                continue
            failures, warnings, _ = audit_register([allowed_pattern], [entry], genre, {})
            allow_tests += 1
            if failures or warnings:
                errors.append(f"{entry_id}: allowed context was rejected: {allowed_pattern}")
        for rule in entry.get("allowed_context_rules", []):
            rule_genres = rule.get("genres", ["*"])
            rule_genre = "generic_formal_soil" if "*" in rule_genres else rule_genres[0]
            example = rule.get("example", "")
            failures, warnings, _ = audit_register([example], [entry], rule_genre, {})
            allow_tests += 1
            if failures or warnings:
                errors.append(
                    f"{entry_id}: context rule {rule.get('id')} rejected its example: {example}"
                )
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} domain-register control test error(s)")
        return 1
    print(
        f"PASS: exercised {reject_tests} reject/warn controls and {allow_tests} legitimate contexts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

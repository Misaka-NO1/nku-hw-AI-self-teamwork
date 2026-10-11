#!/usr/bin/env python3
"""构建 KB_Campus / KB_Course 导出文件（C06）。

从 knowledge/ 源数据生成 knowledge/exports/ 下的只读导出，
供 D 导入知识库并发布。正式事实与学生体验分文件、分字段，
未核验条目保留显式状态，不被“洗白”为官方规定。

发布过滤：学生经验卡仅导出「已获投稿同意且审核通过」的记录；
pending / rejected / consent=false 一律不进入导出文件。

用法：python knowledge/scripts/build_exports.py
"""

import json
import argparse
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "knowledge"
EXPORTS = KNOWLEDGE / "exports"


def load(rel: str) -> dict:
    return json.loads((KNOWLEDGE / rel).read_text(encoding="utf-8"))


def publishable_experience_cards(experiences: dict[str, Any]) -> list[dict[str, Any]]:
    """仅返回可发布的经验卡：consent=True 且 review_status=approved。"""
    return [
        card
        for card in experiences["cards"]
        if card.get("consent") is True and card.get("review_status") == "approved"
    ]


def build_kb_campus(affairs: dict[str, Any]) -> dict[str, Any]:
    items = []
    for entry in affairs["entries"]:
        if entry["entry_id"].startswith("demo-"):
            continue
        items.append(
            {
                "entry_id": entry["entry_id"],
                "kind": entry["kind"],
                "title": entry["title"],
                "category": entry["category"],
                "campus_scope": entry["campus_scope"],
                "audience": entry["audience"],
                "official_url": entry["official_url"],
                "login_required": entry["login_required"],
                "campus_network_required": entry["campus_network_required"],
                "steps": entry["steps"],
                "required_materials": entry["required_materials"],
                "source_refs": entry["source_refs"],
                "verified_at": entry["verified_at"],
                "valid_until": entry["valid_until"],
                "status": entry["status"],
                "source_kind": entry.get("source_kind", "unknown"),
                "keywords": entry.get("keywords", []),
                "cautions": entry.get("cautions", []),
                # 答复时必须保留的状态提示，防止模型把模板说成规定
                "answer_constraint": (
                    "未核验或已过期条目必须明示状态，不得表述为学校规定"
                    if entry["status"] != "verified"
                    else "引用时注明来源与核验时间"
                ),
            }
        )
    return {
        "schema_version": "1.0.0",
        "dataset_kind": affairs["dataset_kind"],
        "kb_id": "KB_Campus",
        "data_version": affairs["data_version"],
        "built_at": date.today().isoformat(),
        "items": items,
    }


def build_kb_course(catalog: dict, experiences: dict) -> dict[str, Any]:
    cards = publishable_experience_cards(experiences)
    return {
        "schema_version": "1.0.0",
        "dataset_kind": catalog["dataset_kind"],
        "kb_id": "KB_Course",
        "data_version": catalog["data_version"],
        "built_at": date.today().isoformat(),
        "courses": catalog["courses"],
        "experience_cards": [
            {**card, "low_sample": card["sample_count"] < 3} for card in cards
        ],
        "rules": [
            "official 与 student_experience 必须分开呈现",
            "样本数 < 3 不生成综合评分",
            "同名课程按 course_id 区分，不合并",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campus-only", action="store_true", help="只构建校园事务，不改课程导出")
    args = parser.parse_args()
    EXPORTS.mkdir(parents=True, exist_ok=True)
    campus = build_kb_campus(load("affairs/entries.json"))
    (EXPORTS / "KB_Campus.json").write_text(
        json.dumps(campus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (EXPORTS / "KB_Campus.md").write_text(build_campus_markdown(campus), encoding="utf-8")
    if args.campus_only:
        print(f"KB_Campus: {len(campus['items'])} items (JSON + Markdown)")
        return
    course = build_kb_course(
        load("courses/catalog.json"), load("courses/experiences.json")
    )
    (EXPORTS / "KB_Course.json").write_text(
        json.dumps(course, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"KB_Campus: {len(campus['items'])} items; "
        f"KB_Course: {len(course['courses'])} courses, "
        f"{len(course['experience_cards'])} cards"
    )


def build_campus_markdown(campus: dict[str, Any]) -> str:
    """每项独立保留出处、范围与状态，供平台逐段检索。"""
    sections = [f"# 校园事务操作指南\n\n数据版本：{campus['data_version']}\n"
                "未收录时不猜测；先区分适用人群、校区与办理分支。待核验指引不是学校规定。\n"]
    for item in campus['items']:
        if item['entry_id'].startswith('demo-'):
            continue
        lines = [f"## {item['title']}", f"entry_id: {item['entry_id']}",
                 f"status: {item['status']}", f"source_kind: {item.get('source_kind', 'unknown')}",
                 f"verified_at: {item['verified_at'] or '未核验'}",
                 f"适用：{'、'.join(item['audience']) or '来源未限定'}；校区：{'、'.join(item['campus_scope']) or '来源未限定'}",
                 f"检索词：{'、'.join(item.get('keywords', []))}",
                 f"登录要求：{item['login_required']}；校园网要求：{item['campus_network_required']}",
                 f"官方入口/流程依据：{item['official_url'] or '未提供正式链接'}",
                 f"材料：{'；'.join(item['required_materials']) or '来源未列明，向受理渠道核实'}",
                 f"有效期：{item['valid_until'] or '来源未明确，办理时核对最新通知'}", "操作步骤："]
        lines += [f"{i}. {step}" for i, step in enumerate(item['steps'], 1)] or ['来源只提供入口，未收录具体办理步骤。']
        lines += [f"注意：{notice}" for notice in item.get('cautions', [])]
        lines += [f"来源：{ref['label']}；{ref['url'] or '无正式网页'}；定位：{ref['locator'] or '未记录'}" for ref in item['source_refs']]
        lines.append(f"答复约束：{item['answer_constraint']}")
        sections.append('\n\n'.join(lines))
    return '\n\n---\n\n'.join(sections) + '\n'


if __name__ == "__main__":
    main()

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
    EXPORTS.mkdir(parents=True, exist_ok=True)
    campus = build_kb_campus(load("affairs/entries.json"))
    course = build_kb_course(
        load("courses/catalog.json"), load("courses/experiences.json")
    )
    (EXPORTS / "KB_Campus.json").write_text(
        json.dumps(campus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (EXPORTS / "KB_Course.json").write_text(
        json.dumps(course, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"KB_Campus: {len(campus['items'])} items; "
        f"KB_Course: {len(course['courses'])} courses, "
        f"{len(course['experience_cards'])} cards"
    )


if __name__ == "__main__":
    main()

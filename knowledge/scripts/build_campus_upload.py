#!/usr/bin/env python3
"""Prepare a school KB upload from a pinned, already-fetched Git revision.

This keeps the working branch's older source files untouched. The existing C
export's one-entry-per-section layout is retained. Owner confirmation is a
separate review record and never replaces historical official verification.

The pinned source currently lives on origin/codex/d-mcp-local-readiness.
For a shallow clone, fetch that branch before running this script; see the
upload notes for the repository URL. This script never fetches automatically.

Run: python knowledge/scripts/build_campus_upload.py
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_COMMIT = "3d67a7ea5267fca1835d32c622fabaa386cda02e"
VERSION = "nku-affairs-2026-10-13-r1"
REVIEW_PATH = ROOT / "knowledge/affairs/review-confirmations-20261013.json"
OUTPUT_BASE = ROOT / "knowledge/exports/KB_Campus-20261013-r1"


def build() -> dict:
    try:
        source_text = subprocess.check_output(
            ["git", "show", f"{SOURCE_COMMIT}:knowledge/affairs/entries.json"],
            cwd=ROOT,
            encoding="utf-8",
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        raise SystemExit("未找到 Git。请安装 Git 并在项目仓库内重新运行；导出文件未改动。") from None
    except subprocess.CalledProcessError:
        raise SystemExit(
            f"无法读取固定源提交 {SOURCE_COMMIT} 的 knowledge/affairs/entries.json。\n"
            "该提交位于团队远端的 codex/d-mcp-local-readiness 分支；普通浅克隆可能没有此对象。\n"
            "确认 origin 指向 Misaka-NO1/nku-hw-AI-self-teamwork 后，先执行：\n"
            "  git fetch origin codex/d-mcp-local-readiness\n"
            "再重新运行本脚本。fetch 只下载远端对象，不 checkout、merge 或覆盖工作区。\n"
            "若分支已变动，请向维护者取得上述固定提交；不要改用其他提交冒充本次来源。\n"
            "本次未生成或覆盖导出文件。"
        ) from None
    source = json.loads(source_text)
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    review_ids = set(review["entry_ids"])
    source_by_id = {item["entry_id"]: item for item in source["entries"]}
    if len(source_by_id) != len(source["entries"]):
        raise ValueError("Duplicate entry IDs in campus source")
    if not review_ids.issubset(source_by_id):
        raise ValueError("Review includes an entry absent from pinned source")
    items = []
    for original in source["entries"]:
        if original["entry_id"].startswith("demo-"):
            continue
        item = copy.deepcopy(original)
        item["source_status"] = original["status"]
        item["source_kind_original"] = original.get("source_kind", "unknown")
        if item["entry_id"] in review_ids:
            if original["status"] != "needs_verification":
                raise ValueError("Review overlay no longer matches pinned source")
            item["review_status"] = review["review_kind"]
            item["review_recorded_at"] = review["recorded_at"]
            item["review_evidence"] = review["source"]
            item["answer_constraint"] = (
                "负责人已确认此使用指引；正常给出操作步骤，保留实际来源。"
                "不称为官方核验，不把确认记录日期当成官方核验日期，不补充缺失要求。"
            )
        else:
            item["review_status"] = original["status"]
            item["answer_constraint"] = (
                "按来源与核验日期作答，保留适用范围和业务注意事项。"
                if original["status"] == "verified"
                else "说明实际来源状态，不把未知信息说成学校规定。"
            )
        items.append(item)
    return {
        "schema_version": "1.0.0",
        "kb_id": "KB_Campus",
        "data_version": VERSION,
        "prepared_at": review["recorded_at"],
        "source_commit": SOURCE_COMMIT,
        "source_data_version": source["data_version"],
        "source_sha256": hashlib.sha256(source_text.encode()).hexdigest(),
        "review_note": review["scope_note"],
        "items": items,
    }


def current_reference(ref: dict, owner_confirmed: bool) -> str:
    label = ref["label"]
    locator = ref.get("locator") or "未记录定位"
    if owner_confirmed:
        # Historical status remains intact in the JSON companion. The text KB
        # presents the current owner review without stale, contradictory labels.
        label = label.replace("（用户更正链接，正文待核验）", "（用户更正链接）")
        locator = re.sub(r"[，；]?待团队(?:/官方渠道)?核验", "", locator)
    return f"{label}；{ref.get('url') or '无公开网页链接'}；{locator}"


def markdown(campus: dict) -> str:
    sections = [
        "# 校园事务操作指南\n\n"
        f"数据版本：{campus['data_version']}\n\n"
        f"来源数据版本：{campus['source_data_version']}；"
        f"整理日期：{campus['prepared_at']}。\n\n"
        "按条目给出入口和步骤，区分校区、适用身份及办理分支。"
        "负责人确认使用指引与官方网页核验分别记录；不用内部状态标签代替回答，"
        "不编造来源、核验日期、材料、收费、办理窗口或处理时限。"
        "未收录的要求应说明未列明。历史窗口已结束时按原日期说明。\n\n"
        "本文件包含31条真实条目，排除虚构测试夹具；用于替换旧版校园事务同类文件，"
        "不替换课程经验或复习资料。"
    ]
    for item in campus["items"]:
        owner = item["review_status"] == "owner_confirmed_guidance"
        status_line = (
            f"核验记录：项目负责人已确认使用指引（记录于{item['review_recorded_at']}）；"
            "本记录未增加官方原文证据。"
            if owner
            else f"核验记录：沿用来源核验记录，日期{item['verified_at'] or '未记录'}。"
        )
        lines = [
            f"## {item['title']}",
            f"entry_id: {item['entry_id']}",
            f"review_status: {item['review_status']}",
            "source_kind: " + ("owner_confirmed_guidance" if owner else item.get("source_kind", "unknown")),
            status_line,
            f"适用：{'、'.join(item['audience']) or '来源未限定'}；"
            f"校区：{'、'.join(item['campus_scope']) or '来源未限定'}",
            f"检索词：{'、'.join(item.get('keywords', []))}",
            f"登录要求：{item['login_required']}；校园网要求：{item['campus_network_required']}",
            f"入口/流程依据：{item['official_url'] or '见下列应用入口，未提供公开网页链接'}",
            f"材料：{'；'.join(item['required_materials']) or '来源未列明，向受理渠道核实'}",
            f"有效期：{item['valid_until'] or '来源未明确，办理时核对最新通知'}",
            "操作步骤：",
        ]
        lines += [f"{n}. {step}" for n, step in enumerate(item["steps"], 1)] or [
            "来源只提供入口，未收录具体办理步骤。"
        ]
        for notice in item.get("cautions", []):
            if owner and notice == "学生提供的使用路径尚未经正式来源核验；先核对应用名称与官方说明。":
                continue
            lines.append(f"注意：{notice}")
        lines += [
            f"来源记录：{current_reference(ref, owner)}" for ref in item["source_refs"]
        ]
        lines.append(f"答复约束：{item['answer_constraint']}")
        sections.append("\n\n".join(lines))
    return "\n\n---\n\n".join(sections) + "\n"


def main() -> None:
    campus = build()
    rendered = markdown(campus)
    OUTPUT_BASE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_BASE.with_suffix(".json").write_text(
        json.dumps(campus, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    OUTPUT_BASE.with_suffix(".md").write_text(rendered, encoding="utf-8")
    written_markdown = OUTPUT_BASE.with_suffix(".md").read_bytes()
    counts = Counter(item["review_status"] for item in campus["items"])
    print(json.dumps({
        "version": VERSION,
        "items": len(campus["items"]),
        "review_counts": counts,
        "markdown_bytes": len(written_markdown),
        "markdown_sha256": hashlib.sha256(written_markdown).hexdigest(),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

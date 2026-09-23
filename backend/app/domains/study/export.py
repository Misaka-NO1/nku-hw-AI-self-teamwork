"""Build a traceable, public-only UTF-8 Markdown import candidate for KB_Study.

This does not claim a specific NK-GeniOS import format. D must verify upload there.
"""

import re
from pathlib import Path
from typing import Any

from app.domains.study.service import _sections, _public, load_catalog


def clean_excerpt(text: str) -> str:
    """Normalize whitespace and remove HTML tags before exporting source text."""
    no_tags = re.sub(r"<[^>]*>", "", text)
    return re.sub(r"[ \t]+", " ", no_tags).strip()


def build_public_knowledge(catalog: dict[str, Any]) -> str:
    blocks = ["# KB_Study 公开正文候选", "", "> 仅供 D 在平台验证导入；所有 demo 内容均为自创夹具。", ""]
    for material in catalog["materials"]:
        if not _public(material) or not material["content_available"]:
            continue
        for chunk in _sections(material):
            blocks.extend([
                f"## {material['title']} · {chunk['heading']}", "",
                f"- material_id: {material['material_id']}",
                f"- version: {material['version']}",
                f"- course_id: {material['course_id']}",
                f"- chunk_id: {chunk['chunk_id']}",
                f"- source_label: {material['source_label']}",
                f"- source_excerpt_ref: {chunk['source_excerpt_ref']}",
                f"- page_label: {chunk['page_label'] if chunk['page_label'] is not None else '无页码'}",
                "", clean_excerpt(chunk["excerpt"]), "",
            ])
    return "\n".join(blocks).rstrip() + "\n"


def export_to(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_public_knowledge(load_catalog()), encoding="utf-8")


if __name__ == "__main__":
    from app.core.contracts import REPOSITORY_ROOT

    export_to(REPOSITORY_ROOT / "knowledge" / "study" / "exports" / "KB_Study_demo.md")

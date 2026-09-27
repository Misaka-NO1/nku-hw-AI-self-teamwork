"""Build the Jinnan scenic catalog and agent-readable notes from the map editor snapshot.

The editor JSON is the single source of spot names, positions, descriptions and photo order.
The generated catalog follows contracts/core.schema.json without changing that contract.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCENIC = ROOT / "knowledge/scenic"
PREVIEW = ROOT / "frontend/src/features/scenic/three-preview"
ASSETS = ROOT / "frontend/public/assets/scenic"
DATA_VERSION = "jinnan-2026-09-26"
MAP_ID = "nku-jinnan-overview-pixels-v1"


def months_from_note(note: str) -> list[int]:
    normalized = note.translate(str.maketrans("一二三四五六七八九", "123456789"))
    explicit = [int(value) for value in re.findall(r"(\d{1,2})\s*月", normalized)]
    months = set(explicit)
    for start, end in re.findall(r"(\d{1,2})\s*月[^，,；;]*?(?:到|至|—|-)\s*(\d{1,2})\s*月", normalized):
        left, right = int(start), int(end)
        if 1 <= left <= right <= 12:
            months.update(range(left, right + 1))
    return sorted(month for month in months if 1 <= month <= 12)


def tags_for(flower: str) -> list[str]:
    if flower in {"建筑", "地标建筑", "地标"}:
        return ["architecture"]
    if flower == "湖景":
        return ["waterside", "wildlife"]
    names = [part.strip() for part in re.split(r"[，,、]", flower) if part.strip()]
    if not names:
        return ["scenic"]
    if flower == "银杏" or flower == "枫树":
        return ["foliage", *names]
    return ["flower", *names]


def main() -> None:
    source = json.loads((PREVIEW / "data/scenic-spots.json").read_text(encoding="utf-8"))
    catalog = {
        "schema_version": "1.0.0",
        "data_version": DATA_VERSION,
        "maps": [{
            "map_id": MAP_ID, "campus_id": "nku-jinnan", "width": 1440, "height": 1062,
            "asset_path": None, "rights_status": "pending", "data_status": "needs_verification",
        }],
        "spots": [],
    }
    manifest = {
        "schema_version": "1.0.0", "data_version": DATA_VERSION,
        "note": "用户指示发布的压缩展示图；不包含桌面原片或 EXIF。",
        "photos": [],
    }
    lines = [
        "# 津南校区景点资料（用户录入，待独立核验）", "",
        "这份文本由 `data/scenic-spots.json` 生成，供 AI 按名称、花种、月份和简介检索。",
        "花期是用户记录的建议观赏时间，不是实时花况；空白简介不补造事实。",
        "照片经用户指示上传；原片不在公开仓库中。建筑历史、植物品种和位置尚未逐条独立核验。", "",
    ]
    seen_names: set[str] = set()
    seen_photos: set[str] = set()
    for item in source:
        name = item["name"]
        if not name or item["spot_id"] in seen_names:
            raise ValueError(f"duplicate or empty spot: {name}")
        seen_names.add(item["spot_id"])
        photos = []
        for index, url in enumerate(item["photo_urls"], 1):
            photo_name = Path(url).name
            if not re.fullmatch(r"[0-9a-f-]{36}\.webp", photo_name):
                raise ValueError(f"unexpected photo URL: {url}")
            file = ASSETS / photo_name
            if not file.is_file():
                raise FileNotFoundError(file)
            path = f"assets/scenic/{photo_name}"
            photos.append({
                "photo_id": photo_name.removesuffix(".webp"), "asset_path": path,
                "caption": f"{name}实景照片 {index}", "captured_at": None,
                "rights_status": "authorized",
            })
            if photo_name not in seen_photos:
                manifest["photos"].append({
                    "asset_path": path, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                    "bytes": file.stat().st_size,
                })
                seen_photos.add(photo_name)
        catalog["spots"].append({
            "spot_id": item["spot_id"], "map_id": MAP_ID, "name": name,
            "x_norm": item["x_norm"], "y_norm": item["y_norm"],
            "tags": tags_for(item["flower"]), "description": item["description"],
            "photos": photos, "historical_bloom_months": months_from_note(item["season_note"]),
            "observation": None, "rights_status": "authorized", "data_status": "needs_verification",
        })
        lines.extend([
            f"## {name}", "", f"- spot_id：`{item['spot_id']}`",
            f"- 分类／植物：{item['flower'] or '未填写'}",
            f"- 建议观赏时间（用户记录）：{item['season_note'] or '未填写'}",
            f"- 简介（用户原文）：{item['description'] or '未填写'}",
            f"- 总图归一化坐标：({item['x_norm']:.6f}, {item['y_norm']:.6f})",
            f"- 照片：{len(photos)} 张；" + ("、".join(photo["asset_path"] for photo in photos) if photos else "无"),
            "- 核验状态：用户提供，尚未独立核验；不得据此宣称实时花况。", "",
        ])
    (SCENIC / "catalog.jinnan.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (SCENIC / "assets-manifest.jinnan.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (SCENIC / "KB_Scenic_Jinnan.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(source)} spots, {sum(len(spot['photos']) for spot in catalog['spots'])} photo references, {len(seen_photos)} unique assets")


if __name__ == "__main__":
    main()

"""Pure scenic catalog operations; never infers a real-time bloom status."""

import json
import re
from pathlib import Path
from urllib.parse import quote
from typing import Any

from app.core.contracts import REPOSITORY_ROOT, validate_contract
from app.core.errors import AppError


CATALOG_PATH = REPOSITORY_ROOT / "knowledge" / "scenic" / "catalog.demo.json"
PUBLISHABLE_RIGHTS = frozenset({"owned", "authorized"})
SAFE_ASSET = re.compile(r"^assets/[A-Za-z0-9._/-]+$")


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    validate_contract(catalog, "ScenicCatalog")
    _validate_catalog(catalog)
    return catalog


def _validate_catalog(catalog: dict[str, Any]) -> None:
    maps = {item["map_id"] for item in catalog["maps"]}
    ids = [spot["spot_id"] for spot in catalog["spots"]]
    if len(maps) != len(catalog["maps"]) or len(ids) != len(set(ids)):
        raise AppError(422, "VALIDATION_ERROR", "Duplicate map_id or spot_id")
    if any(spot["map_id"] not in maps for spot in catalog["spots"]):
        raise AppError(422, "VALIDATION_ERROR", "Spot references an unknown map_id")
    assets = [item["asset_path"] for item in catalog["maps"]]
    assets += [photo["asset_path"] for spot in catalog["spots"] for photo in spot["photos"]]
    if any(path is not None and (not SAFE_ASSET.fullmatch(path) or ".." in Path(path).parts) for path in assets):
        raise AppError(422, "VALIDATION_ERROR", "Unsafe scenic asset path")


def _public_spot(spot: dict[str, Any]) -> dict[str, Any]:
    data = dict(spot)
    data["photos"] = [
        photo for photo in spot["photos"]
        if photo["rights_status"] in PUBLISHABLE_RIGHTS
        and photo["asset_path"] is not None
    ]
    data["map_url"] = f"/tools/map?spot_id={quote(spot['spot_id'], safe='')}"
    data["bloom_note"] = (
        "历史上常见花期：" + "、".join(f"{month}月" for month in spot["historical_bloom_months"])
        if spot["historical_bloom_months"] else "暂无历史花期数据"
    )
    if spot["observation"] is None:
        data["bloom_note"] += "；暂无经核验的当前花况"
    return data


def search_spots(query: dict[str, Any], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Internal function; D maps it to search_scenic_spots and the REST path."""
    validate_contract(query, "ScenicQuery")
    validate_contract(catalog, "ScenicCatalog")
    _validate_catalog(catalog)
    matches = []
    for spot in catalog["spots"]:
        if spot["rights_status"] not in PUBLISHABLE_RIGHTS:
            continue
        if query["campus_id"] is not None:
            map_asset = next(item for item in catalog["maps"] if item["map_id"] == spot["map_id"])
            if map_asset["campus_id"] != query["campus_id"]:
                continue
        if not set(query["tags"]).issubset(spot["tags"]):
            continue
        if query["month"] is not None and query["month"] not in spot["historical_bloom_months"]:
            continue
        matches.append(_public_spot(spot))
    return matches[: query["limit"]]


def get_spot(spot_id: str, catalog: dict[str, Any]) -> dict[str, Any]:
    validate_contract(catalog, "ScenicCatalog")
    _validate_catalog(catalog)
    for spot in catalog["spots"]:
        if spot["spot_id"] == spot_id and spot["rights_status"] in PUBLISHABLE_RIGHTS:
            return _public_spot(spot)
    raise AppError(404, "NOT_FOUND", "Spot not found")

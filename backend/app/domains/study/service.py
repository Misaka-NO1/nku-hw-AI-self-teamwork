"""Study search with explicit rights and source-backed text evidence."""

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.core.contracts import REPOSITORY_ROOT, validate_contract
from app.core.errors import AppError
from app.core.security import Principal


CATALOG_PATH = REPOSITORY_ROOT / "knowledge" / "study" / "materials.json"
SOURCES_ROOT = (REPOSITORY_ROOT / "knowledge" / "study" / "sources").resolve()
PUBLISHABLE_RIGHTS = frozenset({"owned", "authorized"})
HEADING = re.compile(r"^## (.+)$", re.MULTILINE)


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    validate_contract(catalog, "StudyCatalog")
    _validate_catalog(catalog)
    return catalog


def _validate_catalog(catalog: dict[str, Any]) -> None:
    ids = [item["material_id"] for item in catalog["materials"]]
    if len(ids) != len(set(ids)):
        raise AppError(422, "VALIDATION_ERROR", "Duplicate material_id")


def _public(material: dict[str, Any]) -> bool:
    return material["access_scope"] == "public" and material["rights_status"] in (
        PUBLISHABLE_RIGHTS | {"public_link_only"}
    )


def _source_path(material: dict[str, Any]) -> Path | None:
    ref = material["file_ref"]
    if not ref or material["rights_status"] not in PUBLISHABLE_RIGHTS:
        return None
    if (not ref.startswith("knowledge/study/sources/") or ":" in ref or "\\" in ref
            or ".." in Path(ref).parts):
        return None
    candidate = (REPOSITORY_ROOT / ref).resolve()
    if not candidate.is_relative_to(SOURCES_ROOT) or not candidate.is_file():
        return None
    return candidate


def _sections(material: dict[str, Any]) -> list[dict[str, Any]]:
    if not material["content_available"] or not _public(material):
        return []
    path = _source_path(material)
    if path is None:
        return []
    text = path.read_text(encoding="utf-8")
    matches = list(HEADING.finditer(text))
    by_heading = {
        match.group(1).strip(): text[match.end(): matches[index + 1].start() if index + 1 < len(matches) else len(text)].strip()
        for index, match in enumerate(matches)
    }
    return [
        {
            "chunk_id": chunk["chunk_id"],
            "heading": chunk["heading"],
            "page_label": chunk["page_label"],
            "source_excerpt_ref": chunk["source_excerpt_ref"],
            "excerpt": by_heading[chunk["heading"]],
        }
        for chunk in material["chunks"] if chunk["heading"] in by_heading
    ]


def _has_body(material: dict[str, Any]) -> bool:
    """Body availability is independent of a particular search term's evidence hits."""
    return bool(material["content_available"] and _public(material) and _source_path(material))


def _summary(material: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "material_id": material["material_id"],
        "course_id": material["course_id"],
        "title": material["title"],
        "version": material["version"],
        "material_type": material["material_type"],
        "topics": material["topics"],
        "rights_status": material["rights_status"],
        "access_scope": material["access_scope"],
        "source_label": material["source_label"],
        "content_available": _has_body(material),
        "evidence": evidence,
        "material_url": (
            f"/tools/study?course_id={quote(material['course_id'], safe='')}"
            f"&material_id={quote(material['material_id'], safe='')}"
        ),
    }


def search_materials(query: dict[str, Any], principal: Principal, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Search only public catalog entries; authenticated scopes need a future reviewed policy."""
    validate_contract(query, "StudyQuery")
    validate_contract(catalog, "StudyCatalog")
    _validate_catalog(catalog)
    _ = principal
    results = []
    term = (query["topic"] or "").strip().casefold()
    for material in catalog["materials"]:
        if material["course_id"] != query["course_id"] or not _public(material):
            continue
        evidence = _sections(material)
        if term:
            found = [chunk for chunk in evidence if term in (chunk["heading"] + " " + chunk["excerpt"]).casefold()]
            metadata_match = term in (material["title"] + " " + " ".join(material["topics"])).casefold()
            if not found and not metadata_match:
                continue
            evidence = found
        results.append(_summary(material, evidence))
    return results[: query["limit"]]


def get_material(material_id: str, principal: Principal, catalog: dict[str, Any]) -> dict[str, Any]:
    validate_contract(catalog, "StudyCatalog")
    _validate_catalog(catalog)
    _ = principal
    for material in catalog["materials"]:
        if material["material_id"] == material_id and _public(material):
            return _summary(material, _sections(material))
    raise AppError(404, "NOT_FOUND", "Material not found")


def resolve_download(material_id: str, principal: Principal, catalog: dict[str, Any]) -> Path:
    """Return only a checked, catalog-listed local file; D streams it after auth."""
    validate_contract(catalog, "StudyCatalog")
    _validate_catalog(catalog)
    _ = principal
    for material in catalog["materials"]:
        if material["material_id"] != material_id or not _public(material):
            continue
        path = _source_path(material)
        if material["content_available"] and path is not None:
            return path
        raise AppError(404, "NOT_FOUND", "Download not available")
    raise AppError(404, "NOT_FOUND", "Material not found")

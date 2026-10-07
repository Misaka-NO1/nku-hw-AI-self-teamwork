"""Integrity gate for the isolated public catalog service, not MCP probe 005."""
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.core.contracts import REPOSITORY_ROOT

MAP_FILES = frozenset({
    "index.html", "style.css", "app.mjs", "pointer-orbit.mjs", "building-evidence.mjs",
    "overview-data.mjs", "overview-model.mjs", "overview-traces.json", "scenic-roads.json", "road-surface.mjs",
    "calibrated-data.mjs", "calibrated-model.mjs", "campus-data.mjs", "model.mjs",
    "plan-data.mjs", "plan-model.mjs", "nku-jinnan-position-plan.glb",
    "nku-jinnan-reference.glb", "nku-jinnan-guide-plan.glb", "nku-jinnan-calibrated.glb",
    "published-config.json", "published-spots.json",
    "node_modules/three/build/three.module.js", "node_modules/three/build/three.core.js",
    "node_modules/three/examples/jsm/controls/OrbitControls.js",
    "node_modules/three/examples/jsm/utils/BufferGeometryUtils.js", "node_modules/three/LICENSE",
})
REQUIRED = frozenset({"Dockerfile", "backend/requirements.lock", "contracts/api.schema.json", "contracts/core.schema.json",
    "knowledge/scenic/catalog.jinnan.json", "knowledge/study/library/study.sqlite3", "frontend/dist/index.html",
    "campus-map/index.html", "campus-map/published-spots.json", "campus-map/published-config.json"})


def safe_content_path(value):
    if not isinstance(value, str) or not value or ":" in value or "\\" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or any(part.startswith(".") for part in path.parts) or str(path) != value:
        return False
    return (value in REQUIRED or value.startswith("backend/app/") and value.endswith(".py")
        or value.startswith("fixtures/") and re.fullmatch(r"fixtures/[a-z0-9-]+\.demo\.json", value) is not None
        or re.fullmatch(r"knowledge/study/sources/year1/pdf/study-[a-z0-9-]+\.pdf", value) is not None
        or value.startswith("frontend/dist/assets/") and path.suffix in {".js", ".css", ".webp", ".svg"}
        or value.startswith("campus-map/") and value.removeprefix("campus-map/") in MAP_FILES)


def verify_public_content_bundle(runtime: Settings, *, root: Path | None = None):
    root = (root or REPOSITORY_ROOT).resolve()
    manifest_path = Path(runtime.domain_bundle_manifest_path)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    if (runtime.auth_mode != "demo_fixture" or runtime.allow_personal_uploads
            or runtime.database_url != "sqlite:///:memory:" or runtime.public_catalog_profile != "published"
            or manifest_path.resolve() != root / "public-content-manifest.json"):
        raise ValueError("Public content must remain isolated, read-only and without personal identity")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (manifest.get("format") != "nku-public-content/v1" or manifest.get("build_id") != runtime.build_id
                or manifest.get("personal_uploads") is not False or manifest.get("profile") != "published"
                or not re.fullmatch(r"[0-9a-f]{40}", manifest.get("catalog_commit", ""))):
            raise ValueError("Invalid public content manifest")
        entries = manifest.get("files", [])
        if not isinstance(entries, list) or not 1 <= len(entries) <= 1000:
            raise ValueError("Invalid content file list")
        seen = set()
        for item in entries:
            name = item["path"]
            if (not safe_content_path(name) or name in seen or type(item["size"]) is not int
                    or not 0 <= item["size"] <= 100_000_000
                    or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
                raise ValueError("Unapproved content file")
            seen.add(name)
            path = root / name
            if (not path.resolve().is_relative_to(root) or path.is_symlink() or path.is_junction()
                    or any(parent.is_symlink() or parent.is_junction() for parent in path.parents
                           if parent != root and parent.is_relative_to(root))):
                raise ValueError("Unsafe content file")
            if path.stat().st_size != item["size"] or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("Content integrity check failed")
        actual = {p.relative_to(root).as_posix() for folder in ("backend/app", "contracts", "fixtures", "knowledge", "frontend/dist", "campus-map")
                  for p in (root / folder).rglob("*") if p.is_file() and p.suffix != ".pyc" and "__pycache__" not in p.parts}
        if not REQUIRED <= seen or actual != seen - {"Dockerfile", "backend/requirements.lock"}:
            raise ValueError("Missing or unexpected public content files")
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError("Public content bundle is unavailable") from None

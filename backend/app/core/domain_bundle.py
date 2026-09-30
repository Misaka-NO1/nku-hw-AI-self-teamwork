"""Fail-closed startup checks for the packaged, read-only fictional MCP service."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from app.core.config import Settings


RESOURCE_PATHS = (
    "contracts/core.schema.json", "contracts/api.schema.json",
    "fixtures/timetable.demo.json", "fixtures/term.demo.json",
    "fixtures/degree-plan.demo.json", "fixtures/transcript.demo.json",
    "fixtures/notice-event.demo.json", "fixtures/notice-deadline.demo.json", "fixtures/notice-ambiguous.demo.json",
    "fixtures/time-free-query.demo.json", "fixtures/time-event-query.demo.json", "fixtures/time-deadline-query.demo.json",
    "fixtures/scenic-query.demo.json", "fixtures/study-query.demo.json", "fixtures/degree-query.demo.json",
    "knowledge/scenic/catalog.demo.json", "knowledge/study/materials.json",
    "knowledge/study/sources/demo-note-01.md",
)
TOOL_NAMES = (
    "health_probe", "validate_timetable", "query_free_time", "check_time_plan",
    "search_scenic_spots", "search_study_materials", "audit_degree_progress",
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def safe_bundle_path(value: str) -> bool:
    if not isinstance(value, str) or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value:
        return False
    return (value in {"Dockerfile", "backend/requirements.lock", *RESOURCE_PATHS}
            or (value.startswith("backend/app/") and value.endswith(".py")))


def validate_manifest(manifest: dict) -> dict[str, dict]:
    if (not isinstance(manifest, dict) or manifest.get("format") != "nku-domain-bundle/v1"
            or manifest.get("auth_mode") != "demo_fixture"
            or manifest.get("personal_uploads") is not False
            or manifest.get("tools") != list(TOOL_NAMES)
            or type(manifest.get("included_source_dirty")) is not bool
            or not isinstance(manifest.get("git_head"), str)
            or not isinstance(manifest.get("build_id"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", manifest.get("git_head", ""))
            or not re.fullmatch(r"cloudbase-demo-readonly-[A-Za-z0-9-]+", manifest.get("build_id", ""))):
        raise ValueError("Invalid read-only demo bundle manifest")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries or len(entries) > 500:
        raise ValueError("Invalid bundle file list")
    index = {}
    for item in entries:
        if (not isinstance(item, dict) or not safe_bundle_path(item.get("path"))
                or item["path"] in index or not isinstance(item.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", ""))
                or type(item.get("size")) is not int or not 0 <= item["size"] <= 5_000_000):
            raise ValueError("Invalid or unapproved bundle file")
        index[item["path"]] = item
    if not {*RESOURCE_PATHS, "Dockerfile", "backend/requirements.lock", "backend/app/mcp/http.py", "backend/app/mcp/domains.py"}.issubset(index):
        raise ValueError("Bundle is missing required domain resources")
    return index


def verify_domain_bundle(runtime: Settings, *, root: Path | None = None) -> None:
    if not runtime.domain_bundle_manifest_path:
        return  # Local source-tree checks remain available; non-local launch requires the manifest.
    if (not runtime.mcp_enable_domain_tools or runtime.auth_mode != "demo_fixture"
            or runtime.allow_personal_uploads or runtime.database_url != "sqlite:///:memory:"):
        raise ValueError("Bundle must remain read-only demo with no persistent database")
    bundle_root = (root or REPOSITORY_ROOT).resolve()
    manifest_path = Path(runtime.domain_bundle_manifest_path)
    if not manifest_path.is_absolute():
        manifest_path = bundle_root / manifest_path
    if (manifest_path.resolve() != bundle_root / "domain-bundle-manifest.json"
            or manifest_path.is_symlink() or manifest_path.is_junction()):
        raise ValueError("Bundle manifest must be the fixed root manifest")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        index = validate_manifest(manifest)
        non_local = (runtime.app_env in {"staging", "production"}
                     or runtime.mcp_host not in {"127.0.0.1", "localhost", "::1"})
        if non_local and manifest["included_source_dirty"]:
            raise ValueError("Non-local bundle requires committed source files")
        if runtime.build_id != manifest["build_id"]:
            raise ValueError("Bundle build ID does not match deployment")
        actual_modules = {path.relative_to(bundle_root).as_posix()
                          for path in (bundle_root / "backend/app").rglob("*.py")}
        expected_modules = {name for name in index if name.startswith("backend/app/")}
        if actual_modules != expected_modules:
            raise ValueError("Bundle Python file list does not match manifest")
        for name, item in index.items():
            path = bundle_root / name
            if (not path.resolve().is_relative_to(bundle_root) or path.is_symlink() or path.is_junction()
                    or any(parent.is_symlink() or parent.is_junction() for parent in path.parents
                           if parent != bundle_root and parent.is_relative_to(bundle_root))):
                raise ValueError("Unsafe bundle file path")
            if path.stat().st_size != item["size"]:
                raise ValueError("Bundle file integrity check failed")
            content = path.read_bytes()
            if len(content) != item["size"] or hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise ValueError("Bundle file integrity check failed")
    except (OSError, json.JSONDecodeError, TypeError):
        raise ValueError("Bundle manifest or required resource is unavailable") from None

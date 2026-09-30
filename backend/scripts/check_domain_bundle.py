"""Verify an allowlisted ZIP and run its extracted MCP code over loopback HTTP.

No cloud, user credentials or existing database is used. The comparison REST
process uses the checkout, whereas MCP imports only the extracted package.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import secrets
import stat
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import httpx

from app.core.domain_bundle import RESOURCE_PATHS, validate_manifest
from check_domain_stack import authenticated_mcp, compare
from check_local_stack import BACKEND, ROOT, require, service, unused_ports, wait_ready
from probe_mcp_url import ProbeFailure


def inspect_and_extract(package: Path, target: Path) -> dict:
    """Check exact names, source hashes and bounds before extracting any entry."""
    with ZipFile(package) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        require(len(names) <= 501 and len(names) == len(set(names)), "Invalid ZIP file list")
        require("domain-bundle-manifest.json" in names, "Bundle manifest missing")
        require(archive.getinfo("domain-bundle-manifest.json").file_size <= 200_000, "Manifest too large")
        manifest = json.loads(archive.read("domain-bundle-manifest.json").decode("utf-8-sig"))
        index = validate_manifest(manifest)
        required_names = {"Dockerfile", "backend/requirements.lock", *RESOURCE_PATHS,
                          *(path.relative_to(ROOT).as_posix() for path in (BACKEND / "app").rglob("*.py"))}
        require(set(index) == required_names, "Bundle does not contain exactly the approved source files")
        require(set(names) == {*index, "domain-bundle-manifest.json"}, "Unexpected or missing ZIP entry")
        for entry in entries:
            require(not entry.is_dir() and not stat.S_ISLNK(entry.external_attr >> 16), "Unsafe ZIP entry")
            if entry.filename == "domain-bundle-manifest.json":
                continue
            item = index[entry.filename]
            require(entry.file_size == item["size"], "ZIP size mismatch")
            data = archive.read(entry)
            require(hashlib.sha256(data).hexdigest() == item["sha256"], "ZIP integrity mismatch")
            source = (ROOT / "deploy/cloudbase-demo-readonly/Dockerfile"
                      if entry.filename == "Dockerfile" else ROOT / entry.filename)
            require(source.read_bytes() == data, "Bundle differs from checked source")
        # All paths came from the canonical manifest allowlist, never from an
        # unchecked extractall() call. The target is a new temporary directory.
        for entry in entries:
            destination = target / entry.filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(entry))
    return manifest


def run_checks(package: Path) -> dict:
    logging.disable(logging.CRITICAL)
    api_port, mcp_port = unused_ports()
    api_url, mcp_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{mcp_port}/mcp"
    with TemporaryDirectory(prefix="nku-bundle-check-") as scratch:
        directory = Path(scratch)
        extracted, work = directory / "bundle", directory / "work"
        extracted.mkdir()
        work.mkdir()
        manifest = inspect_and_extract(package, extracted)
        token = secrets.token_urlsafe(32)
        shared = {**os.environ, "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
                  "APP_ENV": "test", "AUTH_MODE": "demo_fixture", "ALLOW_PERSONAL_UPLOADS": "false",
                  "APP_ORIGIN": api_url, "GENIOS_AGENT_URL": "", "MCP_PUBLIC_URL": "",
                  "BUILD_ID": manifest["build_id"], "LOG_LEVEL": "WARNING",
                  "API_HOST": "127.0.0.1", "API_PORT": str(api_port),
                  "MCP_HOST": "127.0.0.1", "MCP_PORT": str(mcp_port), "MCP_PATH": "/mcp",
                  "MCP_REQUIRE_AUTH": "true", "MCP_SERVICE_TOKEN": token, "MCP_ENABLE_DOMAIN_TOOLS": "true"}
        mcp_env = {**shared, "PYTHONPATH": str(extracted / "backend"),
                   "DATABASE_URL": "sqlite:///:memory:",
                   "DOMAIN_BUNDLE_MANIFEST_PATH": str(extracted / "domain-bundle-manifest.json")}
        api_env = {**shared, "PYTHONPATH": str(BACKEND), "DOMAIN_BUNDLE_MANIFEST_PATH": "",
                   "DATABASE_URL": "sqlite:///" + (directory / "comparison.db").as_posix()}
        with httpx.Client(timeout=3, trust_env=False) as http:
            with service("app.mcp.http", mcp_env, work) as mcp_process:
                wait_ready(http, mcp_process, mcp_url, 401, method="POST")
                with service("app.main", api_env, work) as api_process:
                    wait_ready(http, api_process, api_url + "/readyz", 200)
                    report = asyncio.run(compare(api_url, mcp_url, token, manifest["build_id"]))
                    report.update(asyncio.run(check_packaged_boundaries(api_url, mcp_url, token)))
        require(not list(extracted.rglob("*.db")), "Packaged MCP unexpectedly created a database file")
    return {"ok": True, "scope": "extracted_zip_loopback_only", "platform_verified": False,
            "container_image_verified": False, "auth_mode": "demo_fixture", "personal_uploads": False,
            "mcp_persistent_database": False, "source_sha_verified": True,
            "build_id": manifest["build_id"], "source_commit": manifest["git_head"],
            "included_source_dirty": manifest["included_source_dirty"], "entries": len(manifest["files"]) + 1,
            "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(), **report}


async def check_packaged_boundaries(api_url, mcp_url, token):
    async with httpx.AsyncClient(timeout=10, trust_env=False) as http:
        created = await http.post(api_url + "/api/v1/demo/workspaces", json={"fixture_set_id": "demo-v1"})
        require(created.status_code == 200, "Comparison workspace creation failed")
        workspace_ref = created.json()["data"]["workspace_ref"]
    async with authenticated_mcp(mcp_url, token) as mcp:
        query = json.loads((ROOT / "fixtures/time-free-query.demo.json").read_text(encoding="utf-8"))
        query["workspace_ref"] = workspace_ref
        denied = await mcp.call_tool("query_free_time", query)
        require(denied.is_error and denied.structured_content["error"]["code"] == "IDENTITY_NOT_VERIFIED",
                "Packaged MCP did not reject browser workspace access")
        timetable = json.loads((ROOT / "fixtures/timetable.demo.json").read_text(encoding="utf-8"))
        timetable["courses"][0]["title"] = "Non-fixture input"
        denied = await mcp.call_tool("validate_timetable", timetable)
        require(denied.is_error and denied.structured_content["error"]["code"] == "DEMO_ONLY",
                "Packaged MCP did not reject non-fixture data")
        materials = await mcp.call_tool("search_study_materials", {"course_id": "demo-CS101", "topic": None, "limit": 20})
        require(not materials.is_error, "Packaged study resource check failed")
        items = {item["material_id"]: item for item in materials.structured_content["data"]}
        require(set(items) == {"demo-note-01", "demo-index-02"}, "Private or unapproved study material returned")
        require(items["demo-note-01"]["content_available"] and items["demo-note-01"]["evidence"]
                and not items["demo-index-02"]["content_available"] and not items["demo-index-02"]["evidence"],
                "Packaged study body/index boundary incorrect")
    return {"browser_workspace_rejected": True, "non_fixture_data_rejected": True,
            "public_study_body_and_private_filter_verified": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    try:
        report = run_checks(args.package.resolve())
    except Exception as exc:
        report = {"ok": False, "error": str(exc) if isinstance(exc, ProbeFailure)
                  else "Bundle check failed; run bundle tests for diagnostics"}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

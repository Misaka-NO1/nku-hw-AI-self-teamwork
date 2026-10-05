import copy
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

from app.core.config import Settings
from app.core.domain_bundle import PLATFORM_TOOL_NAMES, RESOURCE_PATHS, TOOL_NAMES, safe_bundle_path, validate_manifest, verify_domain_bundle


ROOT = Path(__file__).resolve().parents[2]
BUILD_ID = "cloudbase-demo-readonly-test-01234567"


@pytest.fixture
def bundle(tmp_path):
    names = [*RESOURCE_PATHS, "Dockerfile", "backend/requirements.lock",
             "backend/app/mcp/http.py", "backend/app/mcp/domains.py"]
    records = []
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (name + "\n").encode()
        path.write_bytes(data)
        records.append({"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest = {"format": "nku-domain-bundle/v1", "git_head": "a" * 40, "build_id": BUILD_ID,
                "included_source_dirty": False, "auth_mode": "demo_fixture", "personal_uploads": False,
                "tools": list(TOOL_NAMES), "files": records}
    (tmp_path / "domain-bundle-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    settings = Settings(_env_file=None, app_env="test", mcp_enable_domain_tools=True,
                        domain_bundle_manifest_path=str(tmp_path / "domain-bundle-manifest.json"),
                        build_id=BUILD_ID, database_url="sqlite:///:memory:", auth_mode="demo_fixture",
                        allow_personal_uploads=False)
    return tmp_path, manifest, settings


def test_valid_bundle_and_resource_allowlist(bundle):
    root, manifest, runtime = bundle
    assert json.loads((ROOT / "deploy/cloudbase-demo-readonly/package-files.json").read_text()) == list(RESOURCE_PATHS)
    assert len(validate_manifest(manifest)) == len(RESOURCE_PATHS) + 4
    verify_domain_bundle(runtime, root=root)


@pytest.mark.parametrize("path", ["../x.py", "backend/app/../../secret.py", "/backend/app/x.py",
                                  "backend\\app\\x.py", "C:/secret.py", "backend/app//x.py",
                                  "backend/app/./x.py", "backend/.env", "knowledge/private.md", None])
def test_unapproved_paths(path):
    assert not safe_bundle_path(path)


@pytest.mark.parametrize("field,value", [("format", "unknown"), ("auth_mode", "trusted_binding"),
                                        ("personal_uploads", True), ("git_head", 42),
                                        ("git_head", "b" * 39), ("build_id", None),
                                        ("tools", ["health_probe", "commit_task"]),
                                        ("included_source_dirty", "false")])
def test_invalid_manifest_metadata(bundle, field, value):
    _, manifest, _ = bundle
    manifest[field] = value
    with pytest.raises(ValueError):
        validate_manifest(manifest)


@pytest.mark.parametrize("change", ["duplicate", "missing", "traversal", "bad_hash", "bool_size", "huge_size"])
def test_invalid_manifest_entries(bundle, change):
    _, manifest, _ = bundle
    if change == "duplicate":
        manifest["files"].append(copy.deepcopy(manifest["files"][0]))
    elif change == "missing":
        manifest["files"].pop(0)
    else:
        updates = {"traversal": {"path": "../x.py"}, "bad_hash": {"sha256": 123},
                   "bool_size": {"size": True}, "huge_size": {"size": 5_000_001}}
        manifest["files"][0].update(updates[change])
    with pytest.raises(ValueError):
        validate_manifest(manifest)


@pytest.mark.parametrize("change", ["missing_file", "modified_file", "unlisted_module", "missing_manifest", "bad_json", "build"])
def test_runtime_rejects_missing_or_changed_bundle(bundle, change):
    root, _, runtime = bundle
    resource = root / RESOURCE_PATHS[0]
    if change == "missing_file":
        resource.unlink()
    elif change == "modified_file":
        data = resource.read_bytes()
        resource.write_bytes(bytes([data[0] ^ 1]) + data[1:])
    elif change == "unlisted_module":
        (root / "backend/app/mcp/extra.py").write_text("pass", encoding="utf-8")
    elif change == "missing_manifest":
        (root / "domain-bundle-manifest.json").unlink()
    elif change == "bad_json":
        (root / "domain-bundle-manifest.json").write_text("{", encoding="utf-8")
    else:
        runtime.build_id = "wrong"
    with pytest.raises(ValueError):
        verify_domain_bundle(runtime, root=root)


@pytest.mark.parametrize("field,value", [("allow_personal_uploads", True), ("auth_mode", "trusted_binding"),
                                        ("database_url", "sqlite:///data/private.db"),
                                        ("mcp_enable_domain_tools", False)])
def test_runtime_rejects_non_demo_or_persistent_database(bundle, field, value):
    root, _, runtime = bundle
    setattr(runtime, field, value)
    with pytest.raises(ValueError, match="read-only demo"):
        verify_domain_bundle(runtime, root=root)


def test_manifest_cannot_reference_another_directory(bundle):
    root, _, runtime = bundle
    runtime.domain_bundle_manifest_path = str(root / "other/manifest.json")
    with pytest.raises(ValueError, match="fixed root"):
        verify_domain_bundle(runtime, root=root)


def test_non_local_domains_require_manifest():
    runtime = Settings(_env_file=None, app_env="staging", mcp_enable_domain_tools=True,
                       mcp_public_url="https://test.example.invalid/mcp", mcp_require_auth=True,
                       mcp_service_token="test-secret", domain_bundle_manifest_path="")
    with pytest.raises(ValueError, match="MANIFEST"):
        runtime.validate_deployment()


def test_source_tree_local_domains_do_not_require_packaging_manifest():
    runtime = Settings(_env_file=None, app_env="test", mcp_host="127.0.0.1",
                       mcp_enable_domain_tools=True, domain_bundle_manifest_path="")
    runtime.validate_deployment()
    verify_domain_bundle(runtime)


def test_compat_flag_cannot_silently_expand_original_bundle(bundle):
    root, _, runtime = bundle
    runtime.mcp_enable_platform_compat_tools = True
    with pytest.raises(ValueError, match="compatibility flag"):
        verify_domain_bundle(runtime, root=root)


def test_compat_bundle_requires_adapter_module_and_matching_flag(bundle):
    root, manifest, runtime = bundle
    manifest["tools"] = list(PLATFORM_TOOL_NAMES)
    with pytest.raises(ValueError, match="transport adapter"):
        validate_manifest(manifest)
    name = "backend/app/core/platform_query.py"
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = b"# platform adapter fixture\n"
    path.write_bytes(data)
    manifest["files"].append({"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    (root / "domain-bundle-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="compatibility flag"):
        verify_domain_bundle(runtime, root=root)
    runtime.mcp_enable_platform_compat_tools = True
    verify_domain_bundle(runtime, root=root)


def test_non_local_bundle_rejects_uncommitted_source(bundle):
    root, manifest, runtime = bundle
    manifest["included_source_dirty"] = True
    (root / "domain-bundle-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    runtime.app_env = "staging"
    with pytest.raises(ValueError, match="committed"):
        verify_domain_bundle(runtime, root=root)


@pytest.mark.parametrize("extra", ["../secret", "backend/.env", "unlisted.py"])
def test_zip_rejects_unapproved_entries_before_extraction(bundle, extra):
    sys.path.insert(0, str(ROOT / "backend/scripts"))
    from check_domain_bundle import inspect_and_extract
    from probe_mcp_url import ProbeFailure
    root, manifest, _ = bundle
    # Use real approved source bytes so the extra ZIP entry is the sole failure.
    sources = {"Dockerfile": ROOT / "deploy/cloudbase-demo-readonly/Dockerfile",
               "backend/requirements.lock": ROOT / "backend/requirements.lock"}
    sources.update({name: ROOT / name for name in RESOURCE_PATHS})
    sources.update({path.relative_to(ROOT).as_posix(): path for path in (ROOT / "backend/app").rglob("*.py")})
    manifest["files"] = [{"path": name, "size": len(path.read_bytes()),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for name, path in sources.items()]
    package = root / "unsafe.zip"
    with ZipFile(package, "w") as archive:
        archive.writestr("domain-bundle-manifest.json", json.dumps(manifest))
        for name, path in sources.items():
            archive.writestr(name, path.read_bytes())
        archive.writestr(extra, "not approved")
    target = root / "extraction"
    with pytest.raises(ProbeFailure, match="Unexpected"):
        inspect_and_extract(package, target)
    assert not target.exists()

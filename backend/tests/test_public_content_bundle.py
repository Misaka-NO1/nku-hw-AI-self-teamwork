import hashlib
import json
import re

import pytest

from app.core.config import Settings
from app.core.contracts import REPOSITORY_ROOT
from app.core.public_content_bundle import MAP_FILES, REQUIRED, verify_public_content_bundle


@pytest.fixture
def bundle(tmp_path):
    entries = []
    for name in sorted(REQUIRED):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test-only public content")
        entries.append({"path": name, "size": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = {"format": "nku-public-content/v1", "build_id": "test-public",
                "profile": "published", "personal_uploads": False,
                "catalog_commit": "a" * 40, "files": entries}
    manifest_path = tmp_path / "public-content-manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    runtime = Settings(_env_file=None, auth_mode="demo_fixture", allow_personal_uploads=False,
                       public_catalog_profile="published", database_url="sqlite:///:memory:",
                       build_id="test-public", domain_bundle_manifest_path=str(manifest_path))
    return tmp_path, runtime, manifest


def test_exact_bundle_passes(bundle):
    root, runtime, _ = bundle
    verify_public_content_bundle(runtime, root=root)


def test_map_module_dependency_closure():
    preview = REPOSITORY_ROOT / "frontend/src/features/scenic/three-preview"
    for filename in MAP_FILES:
        if filename.endswith(".mjs"):
            source = (preview / filename).read_text(encoding="utf-8")
            for dependency in re.findall(r"[\"'](\./[^\"']+\.mjs)[\"']", source):
                assert dependency.removeprefix("./") in MAP_FILES, (filename, dependency)


def test_changed_public_asset_fails(bundle):
    root, runtime, _ = bundle
    (root / "campus-map/index.html").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        verify_public_content_bundle(runtime, root=root)


def test_unlisted_private_file_fails(bundle):
    root, runtime, _ = bundle
    (root / "knowledge/private.pdf").write_bytes(b"must not be served")
    with pytest.raises(ValueError, match="unexpected"):
        verify_public_content_bundle(runtime, root=root)


@pytest.mark.parametrize("field,value", [("personal_uploads", True), ("profile", "demo"),
                                        ("catalog_commit", "not-a-commit"), ("build_id", "wrong-build")])
def test_manifest_gate_fails_closed(bundle, field, value):
    root, runtime, manifest = bundle
    manifest[field] = value
    (root / "public-content-manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest"):
        verify_public_content_bundle(runtime, root=root)


@pytest.mark.parametrize("field,value", [("allow_personal_uploads", True),
                                        ("database_url", "sqlite:///data/campus.db"),
                                        ("auth_mode", "trusted_binding")])
def test_runtime_gate_cannot_enable_personal_storage(bundle, field, value):
    root, runtime, _ = bundle
    runtime = runtime.model_copy(update={field: value})
    with pytest.raises(ValueError, match="isolated"):
        verify_public_content_bundle(runtime, root=root)

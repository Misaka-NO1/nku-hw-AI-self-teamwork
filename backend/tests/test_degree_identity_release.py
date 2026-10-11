"""Anonymous deployment fixtures: reject loss of existing visitor/import code."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile
import pytest

spec = importlib.util.spec_from_file_location("degree_release_review",
    Path(__file__).resolve().parents[1] / "scripts/check_degree_identity_release.py")
reviewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviewer)


def package(path, entries):
    manifest = {name: hashlib.sha256(body).hexdigest() for name, body in entries.items()}
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in entries.items():
            archive.writestr(name, body)
        archive.writestr(reviewer.MANIFEST, json.dumps(manifest))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline():
    return {reviewer.VISITOR: b'"""Anonymous visitor implementation."""',
            "backend/app/core/config.py": b"visitor_enabled = True\n",
            "backend/app/core/personal_schedules.py": b"original import\n",
            "browser-visitor-migration.sql": b"original schema\n",
            reviewer.INDEX: b'<html><head></head><body><div id="root"></div><script src="/assets/original.js"></script></body></html>',
            "frontend/dist/assets/original.js": b"original application and visitor UI"}


def run_review(tmp_path, changes=None, removed=None):
    entries = baseline()
    digest = package(tmp_path / "baseline.zip", entries)
    candidate = {**entries, **(changes or {})}
    for name in removed or ():
        candidate.pop(name)
    package(tmp_path / "candidate.zip", candidate)
    return reviewer.review(tmp_path / "baseline.zip", tmp_path / "candidate.zip", digest)


def test_additive_degree_entry_keeps_deployed_app_bytes(tmp_path):
    original = baseline()[reviewer.INDEX].decode()
    changes = {"backend/app/api/degree_page.py": b"independent degree route",
        "frontend/dist/assets/degree-preview.js": b"independent preview",
        reviewer.INDEX: original.replace("</body>", reviewer.SCRIPT + "</body>").encode()}
    result = run_review(tmp_path, changes)
    assert result["visitor_preserved"] is True
    assert "runtime_review_still_required" in result["status"]


@pytest.mark.parametrize("name", [reviewer.VISITOR, "browser-visitor-migration.sql",
    "frontend/dist/assets/original.js", "backend/app/core/personal_schedules.py"])
def test_deletion_of_original_features_blocks_release(tmp_path, name):
    with pytest.raises(ValueError, match="deletes deployed"):
        run_review(tmp_path, removed=[name])


@pytest.mark.parametrize("name", [reviewer.VISITOR, "backend/app/core/config.py",
    "frontend/dist/assets/original.js", "backend/app/core/personal_schedules.py"])
def test_unrelated_replacement_blocks_release(tmp_path, name):
    with pytest.raises(ValueError, match="outside the degree allowlist"):
        run_review(tmp_path, {name: b"replacement"})


def test_preserving_old_files_but_replacing_app_entry_still_blocks_release(tmp_path):
    with pytest.raises(ValueError, match="preserve the original app"):
        run_review(tmp_path, {reviewer.INDEX: b"<html>replacement</html>"})


def test_wrong_baseline_or_manifest_cannot_pass(tmp_path):
    path = tmp_path / "baseline.zip"
    package(path, baseline())
    with pytest.raises(ValueError, match="digest mismatch"):
        reviewer.review(path, path, "0" * 64)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("extra.py", b"unlisted source")
    with pytest.raises(ValueError, match="Manifest"):
        reviewer.read_package(path)

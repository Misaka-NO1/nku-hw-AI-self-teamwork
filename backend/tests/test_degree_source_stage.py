import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("stage_degree", Path(__file__).parents[1] / "scripts/stage_degree_identity_release.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def fixture(root):
    (root / "backend/app").mkdir(parents=True)
    (root / "backend/app/visitor_site.py").write_bytes(b"merged visitor")
    manifest = {"files": {"backend/app/visitor_site.py": stage.digest(b"merged visitor")}}
    (root / stage.MANIFEST).write_text(json.dumps(manifest))


def test_stage_rejects_changed_or_deleted_visitor_source(tmp_path):
    fixture(tmp_path)
    stage.verify_stage(tmp_path)
    visitor = tmp_path / "backend/app/visitor_site.py"
    visitor.write_bytes(b"old visitor")
    with pytest.raises(ValueError, match="source changed"):
        stage.verify_stage(tmp_path)
    visitor.unlink()
    with pytest.raises(ValueError, match="source changed"):
        stage.verify_stage(tmp_path)


def test_stage_rejects_unreviewed_source_and_private_config(tmp_path):
    fixture(tmp_path)
    (tmp_path / ".env").write_text("fictional credential")
    with pytest.raises(ValueError, match="Unreviewed source"):
        stage.verify_stage(tmp_path)


def test_stage_never_targets_existing_or_outside_project_directory(tmp_path):
    with pytest.raises(ValueError, match="new directory"):
        stage.stage(tmp_path)

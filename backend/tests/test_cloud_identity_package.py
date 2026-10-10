"""Packaging uses an allowlist; private deployment config never enters ZIP."""
import hashlib
import importlib.util
import json
import shutil
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location("identity_builder", ROOT / "backend/scripts/build_cloud_identity_package.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.mark.parametrize("backend_only", [False, True])
def test_candidate_contains_only_allowlisted_runtime_files(tmp_path, monkeypatch, backend_only):
    for folder in ("backend/app", "contracts", "frontend/dist-identity/assets", "fixtures", "deploy/cloudbase-identity-pilot", "backend/data", "extension/dist"):
        (tmp_path / folder).mkdir(parents=True)
    for file, value in {
        "backend/app/placeholder.py": "# public runtime source",
        "backend/app/visitor_site.py": "# public visitor runtime source",
        "backend/requirements.lock": "# locked runtime",
        "frontend/dist-identity/index.html": "<html></html>",
        "frontend/dist-identity/assets/main.js": "/* public asset */",
        "backend/data/auth-pilot-config.json": "DO_NOT_PACKAGE_PRIVATE_CONFIG",
        ".env": "DO_NOT_PACKAGE_SERVER_KEY",
        "extension/manifest.json": "{}",
        "extension/dist/background.js": "/* reader worker */",
        "extension/dist/content.js": "/* course area only */",
        "extension/dist/app-bridge.js": "/* one-shot transfer */",
        "extension/dist/preview.js": "/* local preview */",
        "extension/dist/preview.html": "<html></html>",
        "deploy/cloudbase-identity-pilot/Dockerfile": "FROM python:3.12-slim-bookworm",
        "deploy/cloudbase-identity-pilot/README.md": "Deployment candidate only",
    }.items():
        (tmp_path / file).write_text(value, encoding="utf-8")
    shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/schema.sql", tmp_path / "deploy/cloudbase-identity-pilot/schema.sql")
    shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/competition-oauth-migration.sql", tmp_path / "deploy/cloudbase-identity-pilot/competition-oauth-migration.sql")
    shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/notice-text-migration.sql", tmp_path / "deploy/cloudbase-identity-pilot/notice-text-migration.sql")
    shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/task-calendar-migration.sql", tmp_path / "deploy/cloudbase-identity-pilot/task-calendar-migration.sql")
    for migration in ("task-oauth-scopes-migration.sql", "personal-tasks-migration.sql", "persistent-auth-migration.sql", "personal-schedules-migration.sql", "device-login-migration.sql", "agent-device-binding-migration.sql", "task-delete-migration.sql", "browser-visitor-migration.sql"):
        shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot" / migration, tmp_path / "deploy/cloudbase-identity-pilot" / migration)
    for filename in builder.FIXTURES + builder.READ_ONLY_FIXTURES:
        shutil.copy2(ROOT / "fixtures" / filename, tmp_path / "fixtures" / filename)
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    if backend_only:
        shutil.rmtree(tmp_path / "frontend")
    report = builder.build("test-identity-r1", backend_only=backend_only)
    with zipfile.ZipFile(report["package"]) as archive:
        names = archive.namelist()
        assert ("frontend/dist/index.html" in names) is not backend_only
        assert ("Dockerfile" in names) is not backend_only
        assert not any("data/" in name or ".env" in name or "node_modules" in name for name in names)
        assert sorted(n for n in names if n.startswith("fixtures/")) == sorted("fixtures/" + n for n in builder.FIXTURES + builder.READ_ONLY_FIXTURES)
        manifest = json.loads(archive.read("package-manifest.json"))
        assert set(manifest) == set(names) - {"package-manifest.json"}
        for name, digest in manifest.items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
        migration = archive.read("database-migration.sql").decode()
        assert migration.count("INSERT INTO nku_identity_pilot_v1.fixtures VALUES") == len(builder.FIXTURES)
        assert migration.index("INSERT INTO nku_identity_pilot_v1.fixtures VALUES") < migration.index("COMMIT;")
        assert "CREATE OR REPLACE" not in migration and "DROP TABLE" not in migration
        compatibility=archive.read("competition-oauth-migration.sql").decode()
        assert "CREATE SCHEMA nku_competition_oauth_v1;" in compatibility
        assert "CREATE OR REPLACE" not in compatibility and "DROP TABLE" not in compatibility
        assert "ALTER TABLE nku_identity_pilot_v1" not in compatibility
        notice=archive.read("notice-text-migration.sql").decode()
        assert "CREATE SCHEMA nku_notice_text_v1;" in notice
        assert "CREATE OR REPLACE" not in notice and "DROP TABLE" not in notice
        assert "ALTER TABLE nku_identity_pilot_v1" not in notice
        calendar=archive.read("task-calendar-migration.sql").decode()
        assert "CREATE SCHEMA nku_task_calendar_v1;" in calendar
        assert "CREATE OR REPLACE FUNCTION nku_notice_text_v1.snapshot" in calendar
        assert "DROP TABLE" not in calendar and "ALTER TABLE nku_identity_pilot_v1" not in calendar
        assert report["calendar_migration_included"] is True
        assert "personal-tasks-migration.sql" in names and "task-oauth-scopes-migration.sql" in names
        assert "persistent-auth-migration.sql" in names
        assert "personal-schedules-migration.sql" in names
        assert "device-login-migration.sql" in names
        assert "agent-device-binding-migration.sql" in names
        assert "browser-visitor-migration.sql" in names and "task-delete-migration.sql" in names
        assert "backend/app/visitor_site.py" in names
        assert ("frontend/dist/assets/campus-schedule-reader.zip" in names) is not backend_only
        assert all((i.external_attr >> 16) & 0o444 == 0o444 for i in archive.infolist())
        assert report["calendar_frontend_source_present"] is False
    with pytest.raises(ValueError, match="overwritten"):
        builder.build("test-identity-r1", backend_only=backend_only)


@pytest.mark.parametrize("name", ["../outside", "C:/outside", "", "secret.env"])
def test_package_name_cannot_escape_dist(name):
    with pytest.raises(ValueError):
        builder.build(name)

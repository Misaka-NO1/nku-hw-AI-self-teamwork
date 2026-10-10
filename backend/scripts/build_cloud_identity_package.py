"""Produce a fresh isolated deployment candidate, never private runtime config.

Identity initialization creates a NEW schema. Optional calendar migration also
replaces the notice snapshot, as documented separately; never run it implicitly.
SQL test dependencies and private configuration are not packaged.
"""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ("timetable.demo.json", "timetable-october-2026.simulation.json", "notice-event.demo.json", "notice-deadline.demo.json", "notice-ambiguous.demo.json")
READ_ONLY_FIXTURES = ("degree-plan.demo.json", "transcript.demo.json")


def build(name: str, *, backend_only: bool = False) -> dict:
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name):
        raise ValueError("Use lowercase ASCII letters, digits and hyphens")
    output = ROOT / "dist" / name
    archive = output.with_suffix(".zip")
    if output.exists() or archive.exists():
        raise ValueError("Choose a new package name; deployed artifacts must not be overwritten")
    frontend = ROOT / "frontend/dist-identity"
    if not backend_only and not (frontend / "index.html").is_file():
        raise ValueError("Build the identity-pilot frontend first")
    output.mkdir(parents=True)
    shutil.copytree(ROOT / "backend/app", output / "backend/app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "contracts", output / "contracts")
    if not backend_only:
        shutil.copytree(frontend, output / "frontend/dist")
        # Public reader binary only. Never package local observations, source
        # maps, tickets, browser storage or private runtime configuration.
        reader = output / "frontend/dist/assets/campus-schedule-reader.zip"
        extension = ROOT / "extension"
        required = [extension / "manifest.json", *[extension / "dist" / name for name in ("background.js", "content.js", "app-bridge.js", "preview.js", "preview.html")]]
        if any(not path.is_file() for path in required):
            raise ValueError("Build the timetable reader extension before packaging")
        with zipfile.ZipFile(reader, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in required:
                info = zipfile.ZipInfo(path.relative_to(extension).as_posix())
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(info, path.read_bytes())
    shutil.copy2(ROOT / "backend/requirements.lock", output / "backend/requirements.lock")
    if not backend_only:
        shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/Dockerfile", output / "Dockerfile")
    shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/README.md", output / "DEPLOYMENT.md")
    shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/competition-oauth-migration.sql", output / "competition-oauth-migration.sql")
    shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/notice-text-migration.sql", output / "notice-text-migration.sql")
    shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/task-calendar-migration.sql", output / "task-calendar-migration.sql")
    for name in ("task-oauth-scopes-migration.sql", "personal-tasks-migration.sql", "persistent-auth-migration.sql", "personal-schedules-migration.sql", "device-login-migration.sql", "agent-device-binding-migration.sql", "task-delete-migration.sql", "browser-visitor-migration.sql"):
        shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot" / name, output / name)
    (output / "fixtures").mkdir()
    for filename in READ_ONLY_FIXTURES:
        # These do not seed owner data or alter the fixture DB.
        shutil.copy2(ROOT / "fixtures" / filename, output / "fixtures" / filename)
    seeds = []
    for filename in FIXTURES:
        shutil.copy2(ROOT / "fixtures" / filename, output / "fixtures" / filename)
        payload = json.loads((ROOT / "fixtures" / filename).read_text(encoding="utf-8"))
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        kind = "schedule" if filename.startswith("timetable") else "task"
        seeds.append("INSERT INTO nku_identity_pilot_v1.fixtures VALUES ('" + digest + "', '" + kind + "', '" + canonical.replace("'", "''") + "'::jsonb);")
    schema = (ROOT / "deploy/cloudbase-identity-pilot/schema.sql").read_text(encoding="utf-8")
    if schema.count("COMMIT;") != 1:
        raise ValueError("Migration requires one exact transaction terminator")
    (output / "database-migration.sql").write_text(schema.replace("COMMIT;", "\n".join(seeds) + "\nCOMMIT;"), encoding="utf-8")
    manifest = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(output.rglob("*")) if p.is_file()}
    (output / "package-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(output).as_posix())
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                bundle.writestr(info, path.read_bytes())
    return {"package": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "files": len(manifest), "schema": "nku_identity_pilot_v1", "credential_files_included": False,
            "calendar_migration_included": True,
            "calendar_frontend_source_present": (ROOT / "frontend/src/features/calendar/api.ts").is_file(),
            "backend_only": backend_only,
            "status": "backend_integration_candidate_not_live" if backend_only else "deployment_candidate_not_live"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="cloudbase-identity-pilot-20261002-r1")
    parser.add_argument("--backend-only", action="store_true", help="Integration bundle without frontend or deploy Dockerfile")
    args = parser.parse_args()
    print(json.dumps(build(args.name, backend_only=args.backend_only)))

"""Produce a fresh isolated deployment candidate, never private runtime config.

The generated migration creates a NEW schema and function. It will fail rather
than replace existing identity objects. SQL test dependencies are not packaged.
"""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ("timetable.demo.json", "notice-event.demo.json", "notice-deadline.demo.json", "notice-ambiguous.demo.json")
READ_ONLY_FIXTURES = ("degree-plan.demo.json", "transcript.demo.json")


def build(name: str) -> dict:
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name):
        raise ValueError("Use lowercase ASCII letters, digits and hyphens")
    output = ROOT / "dist" / name
    archive = output.with_suffix(".zip")
    if output.exists() or archive.exists():
        raise ValueError("Choose a new package name; deployed artifacts must not be overwritten")
    frontend = ROOT / "frontend/dist-identity"
    if not (frontend / "index.html").is_file():
        raise ValueError("Build the identity-pilot frontend first")
    output.mkdir(parents=True)
    shutil.copytree(ROOT / "backend/app", output / "backend/app", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "contracts", output / "contracts")
    shutil.copytree(frontend, output / "frontend/dist")
    shutil.copy2(ROOT / "backend/requirements.lock", output / "backend/requirements.lock")
    shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/Dockerfile", output / "Dockerfile")
    shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/README.md", output / "DEPLOYMENT.md")
    shutil.copy2(ROOT / "deploy/cloudbase-identity-pilot/competition-oauth-migration.sql", output / "competition-oauth-migration.sql")
    (output / "fixtures").mkdir()
    for filename in READ_ONLY_FIXTURES:
        # These do not seed owner data or alter the existing four-fixture DB.
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
                bundle.write(path, path.relative_to(output).as_posix())
    return {"package": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "files": len(manifest), "schema": "nku_identity_pilot_v1", "credential_files_included": False,
            "status": "deployment_candidate_not_live"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="cloudbase-identity-pilot-20261002-r1")
    print(json.dumps(build(parser.parse_args().name)))

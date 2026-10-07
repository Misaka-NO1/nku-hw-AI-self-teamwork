"""Build a secret-free, isolated CloudBase TasksPage package and fixture SQL.

Generated dist/ artifacts are disposable; source changes use normal Git review.
"""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("--name", default="cloudbase-tasks-demo-20261002")
args = parser.parse_args()
if not args.name or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in args.name):
    raise SystemExit("Package name must use lowercase ASCII letters, digits and hyphens")
OUTPUT = ROOT / "dist" / args.name
if OUTPUT.exists():
    raise SystemExit("Output already exists; choose a new output name in the script, do not overwrite a deployed package")
if not (ROOT / "frontend/dist-demo/index.html").is_file():
    raise SystemExit("Build frontend first using deploy/Start-Demo.ps1")
OUTPUT.mkdir(parents=True)
for folder in ("backend/app", "contracts", "fixtures"):
    shutil.copytree(ROOT / folder, OUTPUT / folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
shutil.copytree(ROOT / "frontend/dist-demo", OUTPUT / "frontend/dist")
for source, dest in (("backend/requirements.lock", "backend/requirements.lock"),
                     ("deploy/cloudbase-tasks-demo/Dockerfile", "Dockerfile")):
    shutil.copy2(ROOT / source, OUTPUT / dest)
seed = []
for name in ("notice-event.demo.json", "notice-deadline.demo.json", "notice-ambiguous.demo.json"):
    payload = json.loads((ROOT / "fixtures" / name).read_text(encoding="utf-8"))
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    seed.append("INSERT INTO nku_tasks_demo_v1.fixtures VALUES ('" + digest + "', '" + canonical.replace("'", "''") + "'::jsonb);")
schema = (ROOT / "deploy/cloudbase-tasks-demo/schema.sql").read_text(encoding="utf-8")
(OUTPUT / "database-migration.sql").write_text(schema.replace("COMMIT;", "\n".join(seed) + "\nCOMMIT;"), encoding="utf-8")
manifest = {str(p.relative_to(OUTPUT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in OUTPUT.rglob("*") if p.is_file()}
(OUTPUT / "package-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
archive = OUTPUT.with_suffix(".zip")
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for path in OUTPUT.rglob("*"):
        if path.is_file():
            bundle.write(path, str(path.relative_to(OUTPUT)))
print(json.dumps({"package": str(archive), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                  "files": len(manifest), "contains_credentials": False}))

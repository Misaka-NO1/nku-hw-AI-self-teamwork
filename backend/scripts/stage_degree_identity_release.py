"""Stage module 6 on a pinned merged main; never deploy or run migrations.

The old binary-overlay reviewer remains available for recovered deployment ZIPs.
This source-based route preserves merged visitor/import fixes and excludes other
dirty working-tree changes. Builds must use this stage, not the working tree.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
BASE = "0051687752b84a65d97d3c0cd2d91fccee1dd706"
OVERLAY = frozenset({
    "backend/app/agent_device_site.py", "backend/app/cloud_identity_site.py",
    "backend/app/cloud_tasks_site.py", "backend/scripts/build_cloud_identity_package.py",
    "backend/scripts/stage_degree_identity_release.py",
    "backend/app/api/degree_page.py",
    "backend/app/api/personal_degree.py", "backend/app/core/personal_degree.py",
    "backend/app/core/config.py", "backend/app/core/cloud_identity_store.py",
    "backend/app/core/cloud_oauth_provider.py", "backend/app/oauth_pilot_site.py",
    "deploy/cloudbase-identity-pilot/personal-degree-migration.sql",
    *[f"backend/app/domains/degree/{n}.py" for n in
      ("page_progress", "page_hierarchy", "page_observation", "page_report")],
    "frontend/src/features/degree/DegreePage.tsx",
    "frontend/src/features/degree/DegreeReadPreview.tsx",
    "frontend/src/features/degree/degree-page.css", "frontend/src/features/degree/pageApi.ts",
    "frontend/src/features/degree/connectedApi.ts",
    "extension/manifest.json", "extension/package.json", "extension/src/background.ts",
    "extension/src/content.ts", "extension/src/degree-content.ts",
    "extension/src/degree-transfer.ts", "extension/src/degree-app-bridge.ts",
    "packages/import-core/src/degree-page.ts",
})
PREFIXES = ("backend/app/", "backend/scripts/build_cloud_identity_package.py",
    "backend/requirements.lock", "contracts/", "fixtures/", "deploy/cloudbase-identity-pilot/",
    "frontend/src/", "frontend/public/", "extension/src/", "extension/scripts/",
    "packages/import-core/src/", "knowledge/")
CONFIG = frozenset({"package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml",
    "frontend/package.json", "frontend/index.html", "frontend/vite.config.ts",
    "frontend/tsconfig.json", "extension/package.json", "extension/manifest.json",
    "extension/tsconfig.json", "packages/import-core/package.json",
    "packages/import-core/tsconfig.json"})
MANIFEST = "degree-source-manifest.json"


def digest(body):
    return hashlib.sha256(body).hexdigest()


def verify_stage(root):
    root = Path(root)
    manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    expected = manifest["files"]
    # Generated build outputs/dependency links are checked by the package builder;
    # every source/config input remains pinned after staging.
    for name, sha in expected.items():
        path = root / name
        if not path.is_file() or path.is_symlink() or digest(path.read_bytes()) != sha:
            raise ValueError("Staged source changed: " + name)
    for directory, subdirs, files in os.walk(root, followlinks=False):
        subdirs[:] = [d for d in subdirs if d not in {"node_modules", "__pycache__"}
            and (Path(directory) / d).relative_to(root).as_posix() not in
            {"frontend/dist-identity", "extension/dist", "dist"}]
        for filename in files:
            name = (Path(directory) / filename).relative_to(root).as_posix()
            if name != MANIFEST and name not in expected:
                raise ValueError("Unreviewed source added: " + name)
    return manifest


def stage(destination):
    destination = Path(destination).resolve()
    boundary = (ROOT / ".review-cache").resolve()
    if boundary not in destination.parents or destination.exists():
        raise ValueError("Use a new directory under project .review-cache")
    current_main = subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=ROOT).decode().strip()
    if current_main != BASE:
        raise ValueError("Main advanced; review and pin the new merged base first")
    archive = subprocess.check_output(["git", "archive", BASE], cwd=ROOT)
    baseline = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            name = member.name
            parts = PurePosixPath(name).parts
            if not member.isfile() or ".." in parts or name.startswith("/"):
                continue
            if any(p.startswith(".env") for p in parts):
                continue
            if name in CONFIG or name.startswith(PREFIXES):
                baseline[name] = tar.extractfile(member).read()
    source = dict(baseline)
    for name in sorted(OVERLAY):
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing reviewed module file: " + name)
        source[name] = path.read_bytes()
    for required in ("backend/app/visitor_site.py", "frontend/src/features/auth/CloudbaseLoginPage.tsx",
            "frontend/src/features/import/ConnectedImportPage.tsx", "frontend/src/features/import/ImportPage.tsx",
            "deploy/cloudbase-identity-pilot/browser-visitor-migration.sql",
            "deploy/cloudbase-identity-pilot/task-delete-migration.sql"):
        if required not in source or source[required] != baseline[required]:
            raise ValueError("Merged visitor/import source must remain intact")
    destination.mkdir(parents=True)
    for name, body in source.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    manifest = {"base": BASE, "status": "source_staged_not_built_or_deployed",
        "files": {n: digest(b) for n, b in sorted(source.items())},
        "changed": sorted(n for n in baseline if source[n] != baseline[n]),
        "added": sorted(set(source) - set(baseline)),
        "excluded": "unrelated working-tree changes, credentials, observations and runtime data",
        "migrations_executed": False}
    (destination / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    verify_stage(destination)
    return {"directory": str(destination), "base": BASE, "changed": manifest["changed"],
            "added": manifest["added"], "status": manifest["status"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.destination), ensure_ascii=False, indent=2))

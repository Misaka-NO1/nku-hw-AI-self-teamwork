"""Package only the isolated degree service's reviewed dependency allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "backend/requirements.lock", "backend/app/__init__.py", "backend/app/core/__init__.py",
    "backend/app/core/config.py", "backend/app/core/envelope.py", "backend/app/core/logging.py",
    "backend/app/domains/__init__.py", "backend/app/domains/degree/__init__.py",
    "backend/app/domains/degree/page_progress.py", "backend/app/domains/degree/page_hierarchy.py",
    "backend/app/domains/degree/page_observation.py", "backend/app/domains/degree/page_report.py",
    "backend/app/mcp/__init__.py", "backend/app/mcp/audit.py", "backend/app/mcp/server.py",
    "backend/app/mcp/http.py", "backend/app/mcp/degree.py", "backend/app/mcp/degree_http.py",
]


def build(name):
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in name):
        raise ValueError("Package name must be a simple basename")
    target = ROOT / "dist" / f"{name}.zip"
    target.parent.mkdir(exist_ok=True)
    entries = {"Dockerfile": ROOT / "deploy/cloudbase-degree-analysis/Dockerfile"}
    entries.update({name: ROOT / name for name in FILES})
    content = {}
    for entry, source in entries.items():
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Package input escapes project")
        content[entry] = source.read_bytes()
    # The repository package initializer exports the fixed-demo audit. This
    # isolated service deliberately ships neither that audit nor its assets.
    content["backend/app/domains/degree/__init__.py"] = b'"""Isolated supplied-page degree analysis package."""\n'
    manifest = {name: hashlib.sha256(body).hexdigest() for name, body in content.items()}
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive_content = {**content, "release-manifest.json": json.dumps(manifest, indent=2).encode()}
        for entry, body in archive_content.items():
            info = zipfile.ZipInfo(entry)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, body)
    return target, hashlib.sha256(target.read_bytes()).hexdigest(), len(content) + 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    target, digest, count = build(args.name)
    print(json.dumps({"package": str(target), "sha256": digest, "entries": count}))

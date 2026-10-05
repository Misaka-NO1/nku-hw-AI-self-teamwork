"""Package merged authorized catalogs and read-only tools, never local secrets.

Generated dist/ only. No deployments, Git writes, DB migration or credentials.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import Settings
from app.core.public_content_bundle import MAP_FILES, safe_content_path, verify_public_content_bundle
from app.domains.scenic.service import load_catalog
from app.domains.study.library import StudyLibrary


def build(name: str):
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name):
        raise ValueError("Use an ASCII package name")
    output = ROOT / "dist" / name
    if output.exists() or output.with_suffix(".zip").exists():
        raise ValueError("Output already exists; choose a new name")
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise ValueError("Build the frontend first")
    scenic = load_catalog(ROOT / "knowledge/scenic/catalog.jinnan.json")
    library = StudyLibrary()
    files = []
    def copy(source, target):
        destination = output / target
        if not safe_content_path(target):
            raise ValueError(f"Unapproved resource: {target}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination); files.append(target)
    for source in (ROOT / "backend/app").rglob("*.py"):
        copy(source, source.relative_to(ROOT).as_posix())
    for filename in ("api.schema.json", "core.schema.json"):
        copy(ROOT / "contracts" / filename, "contracts/" + filename)
    for source in (ROOT / "fixtures").glob("*.demo.json"):
        copy(source, source.relative_to(ROOT).as_posix())
    for source in (ROOT / "frontend/dist").rglob("*"):
        if source.is_file():
            copy(source, source.relative_to(ROOT).as_posix())
    for source, target in (("backend/requirements.lock", "backend/requirements.lock"),
            ("deploy/cloudbase-public-content/Dockerfile", "Dockerfile"),
            ("knowledge/scenic/catalog.jinnan.json", "knowledge/scenic/catalog.jinnan.json"),
            ("knowledge/study/library/study.sqlite3", "knowledge/study/library/study.sqlite3")):
        copy(ROOT / source, target)
    # Resolve each public PDF through A's DB allowlist rather than globbing sources.
    public_materials = []
    for course in library.list_courses():
        public_materials.extend(library.search_materials({"course_id": course["course_id"], "topic": None, "limit": 20}))
    for item in public_materials:
        source = library.resolve_download(item["material_id"])
        copy(source, source.relative_to(ROOT).as_posix())
    preview = ROOT / "frontend/src/features/scenic/three-preview"
    for filename in MAP_FILES - {"published-config.json", "published-spots.json"}:
        if filename.startswith("node_modules/"):
            continue
        copy(preview / filename, "campus-map/" + filename)
    # Catch missing transitive map modules before uploading a healthy but blank map.
    for filename in MAP_FILES:
        if not filename.endswith(".mjs"):
            continue
        source = (output / "campus-map" / filename).read_text(encoding="utf-8")
        for dependency in re.findall(r"[\"'](\./[^\"']+\.mjs)[\"']", source):
            if dependency.removeprefix("./") not in MAP_FILES:
                raise ValueError(f"Unpackaged map dependency: {filename} -> {dependency}")
    # The repository vendors the official Three.js tarball; no npm install/network.
    with tarfile.open(preview / "three-0.180.0.tgz", "r:gz") as archive:
        for name_in_map in sorted(item for item in MAP_FILES if item.startswith("node_modules/three/")):
            member = archive.getmember("package/" + name_in_map.removeprefix("node_modules/three/"))
            if not member.isfile() or member.size > 5_000_000:
                raise ValueError("Unexpected vendored Three resource")
            destination = output / "campus-map" / name_in_map
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as reader, destination.open("wb") as writer:
                shutil.copyfileobj(reader, writer)
            files.append("campus-map/" + name_in_map)
    # Only published, authorized catalog IDs/photos can enter the rendered map.
    allowed = {item["spot_id"]: item for item in scenic["spots"] if item["rights_status"] in {"owned", "authorized"}}
    original = json.loads((preview / "data/scenic-spots.json").read_text(encoding="utf-8"))
    spots = []
    for item in original:
        if item["spot_id"] not in allowed:
            continue
        row = dict(item)
        row["photo_urls"] = ["/media/scenic/" + Path(photo["asset_path"]).name for photo in allowed[item["spot_id"]]["photos"]
            if photo["asset_path"] and photo["rights_status"] in {"owned", "authorized"}]
        row["photo_data_url"] = ""
        spots.append(row)
    for name_in_map, value in (("published-spots.json", spots), ("published-config.json", {"public_catalog": True, "authoring": False})):
        relative = "campus-map/" + name_in_map
        (output / relative).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8"); files.append(relative)
    commit = subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=ROOT, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    records = [{"path": name, "size": (output / name).stat().st_size, "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest()}
               for name in sorted(files)]
    manifest = {"format": "nku-public-content/v1", "build_id": name, "profile": "published", "personal_uploads": False,
        "catalog_commit": commit, "source_head": head, "included_source_dirty": dirty,
        "scenic_data_version": scenic["data_version"], "study_data_version": library.data_version(),
        "counts": {"spots": len(spots), "photos": sum(len(s["photo_urls"]) for s in spots), "public_pdfs": len(public_materials)}, "files": records}
    (output / "public-content-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    runtime = Settings(_env_file=None, public_catalog_profile="published", database_url="sqlite:///:memory:",
        domain_bundle_manifest_path=str(output / "public-content-manifest.json"), build_id=name)
    verify_public_content_bundle(runtime, root=output)
    with zipfile.ZipFile(output.with_suffix(".zip"), "w", zipfile.ZIP_DEFLATED) as archive:
        for name in [*sorted(files), "public-content-manifest.json"]:
            archive.write(output / name, name)
    result = {"package": str(output.with_suffix(".zip")), "sha256": hashlib.sha256(output.with_suffix(".zip").read_bytes()).hexdigest(), **manifest["counts"]}
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="cloudbase-public-content-20261002-r1")
    build(parser.parse_args().name)

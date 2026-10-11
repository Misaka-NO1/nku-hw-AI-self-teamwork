"""Review a degree-only overlay against a separately verified deployed ZIP.

This checks file integrity, not deployment provenance or runtime acceptance.
The baseline must first be recovered and matched to the actual deployment.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

SHARED = frozenset({
    "backend/app/agent_device_site.py", "backend/app/cloud_identity_site.py",
    "backend/app/cloud_tasks_site.py", "frontend/dist/assets/campus-schedule-reader.zip",
})
ADDITIONS = frozenset({
    "backend/app/api/degree_page.py",
    *[f"backend/app/domains/degree/{name}.py" for name in
      ("page_progress", "page_hierarchy", "page_observation", "page_report")],
    "frontend/dist/assets/degree-preview.js", "frontend/dist/assets/degree-preview.css",
})
MANIFEST = "package-manifest.json"
INDEX = "frontend/dist/index.html"
VISITOR = "backend/app/visitor_site.py"
SCRIPT = '<script type="module" src="/assets/degree-preview.js"></script>'
STYLE = '<link rel="stylesheet" href="/assets/degree-preview.css">'


def read_package(path):
    with zipfile.ZipFile(path) as archive:
        content = {}
        for entry in archive.infolist():
            name = entry.filename
            parts = PurePosixPath(name).parts
            if (name.startswith("/") or "\\" in name or ":" in name or ".." in parts
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("Unsafe archive entry")
            if entry.is_dir():
                continue
            if name in content:
                raise ValueError("Duplicate archive entry")
            if any(p in {".env", ".git", ".venv", "node_modules"} or p.startswith(".env.") for p in parts):
                raise ValueError("Private or dependency file in archive")
            content[name] = archive.read(entry)
    if MANIFEST not in content:
        raise ValueError("Missing source package manifest")
    manifest = json.loads(content[MANIFEST])
    expected = {name: hashlib.sha256(body).hexdigest() for name, body in content.items() if name != MANIFEST}
    if manifest != expected:
        raise ValueError("Manifest does not match every archived file")
    return content


def review(baseline_path, candidate_path, baseline_sha256):
    digest = hashlib.sha256(Path(baseline_path).read_bytes()).hexdigest()
    if digest != baseline_sha256:
        raise ValueError("Recovered baseline digest mismatch")
    baseline, candidate = read_package(baseline_path), read_package(candidate_path)
    if VISITOR not in baseline:
        raise ValueError("Baseline is missing the observed deployed visitor implementation")
    deleted = set(baseline) - set(candidate)
    added = set(candidate) - set(baseline)
    changed = {name for name in baseline.keys() & candidate.keys() if baseline[name] != candidate[name]}
    if deleted:
        raise ValueError("Overlay deletes deployed files")
    if added - ADDITIONS or changed - SHARED - {MANIFEST, INDEX}:
        raise ValueError("Overlay changes files outside the degree allowlist")
    if INDEX in changed:
        original = baseline[INDEX].decode("utf-8")
        if original.count("</body>") != 1 or original.count("</head>") != 1:
            raise ValueError("Unrecognized deployed HTML entry")
        expected = original.replace("</body>", SCRIPT + "</body>")
        if "frontend/dist/assets/degree-preview.css" in added:
            expected = expected.replace("</head>", STYLE + "</head>")
        if "frontend/dist/assets/degree-preview.js" not in added or candidate[INDEX] != expected.encode("utf-8"):
            raise ValueError("HTML entry must preserve the original app and only append the independent degree entry")
    return {"status": "integrity_checked_runtime_review_still_required",
            "baseline_sha256": digest,
            "candidate_sha256": hashlib.sha256(Path(candidate_path).read_bytes()).hexdigest(),
            "unchanged_files": len(baseline) - len(changed), "added": sorted(added),
            "changed": sorted(changed), "visitor_preserved": candidate[VISITOR] == baseline[VISITOR]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.baseline, args.candidate, args.baseline_sha256), ensure_ascii=False))

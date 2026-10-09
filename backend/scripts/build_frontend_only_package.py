"""Replace only built frontend assets in a known deployment baseline.

Do not silently bundle unrelated local backend or extension edits. Never copy
private observations, credentials or preview/test sources into the bundle.
"""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build(baseline_name, name):
    for value in (baseline_name, name):
        if not value or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in value):
            raise ValueError('Package names must be lowercase ASCII names')
    baseline = ROOT / 'dist' / baseline_name
    output = ROOT / 'dist' / name
    archive = output.with_suffix('.zip')
    frontend = ROOT / 'frontend/dist-identity'
    if not (baseline / 'package-manifest.json').is_file() or not (frontend / 'index.html').is_file():
        raise ValueError('Verified baseline and built frontend required')
    if output.exists() or archive.exists():
        raise ValueError('Choose a fresh output name; never overwrite a deployed artifact')
    baseline_manifest = json.loads((baseline / 'package-manifest.json').read_text(encoding='utf-8'))
    for relative, expected in baseline_manifest.items():
        if digest(baseline / relative) != expected:
            raise ValueError('Baseline hash mismatch: ' + relative)
    output.mkdir(parents=True)
    for source in sorted(baseline.rglob('*')):
        relative = source.relative_to(baseline).as_posix()
        if not source.is_file() or relative == 'package-manifest.json' or relative.startswith('frontend/dist/'):
            continue
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copytree(frontend, output / 'frontend/dist')
    reader = baseline / 'frontend/dist/assets/campus-schedule-reader.zip'
    if not reader.is_file():
        raise ValueError('Existing public extension bundle required')
    shutil.copy2(reader, output / 'frontend/dist/assets/campus-schedule-reader.zip')
    manifest = {p.relative_to(output).as_posix():digest(p) for p in sorted(output.rglob('*')) if p.is_file()}
    unchanged = {k:v for k,v in baseline_manifest.items() if not k.startswith('frontend/dist/')}
    if any(manifest.get(k) != value for k,value in unchanged.items()):
        raise ValueError('Non-frontend payload changed')
    if digest(reader) != digest(output / 'frontend/dist/assets/campus-schedule-reader.zip'):
        raise ValueError('Extension changed')
    (output / 'package-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob('*')):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(path.relative_to(output).as_posix())
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info,path.read_bytes())
    return {'archive':str(archive),'sha256':digest(archive),'baseline':baseline_name,
            'non_frontend_files_verified_unchanged':len(unchanged),'extension_unchanged':True,
            'status':'frontend_only_candidate_not_live'}

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',required=True)
    parser.add_argument('--name',required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.baseline,args.name)))

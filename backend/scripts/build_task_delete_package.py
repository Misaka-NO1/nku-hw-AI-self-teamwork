"""Pin the current deployed baseline; replace only deletion feature files + UI."""
import hashlib
import json
import shutil
import zipfile
from build_frontend_only_package import build, ROOT, digest

CHANGED = ('backend/app/core/cloud_identity_store.py', 'backend/app/core/task_calendar.py',
           'backend/app/api/task_calendar.py', 'contracts/api.schema.json')

def package(baseline, name):
    result=build(baseline,name)
    output=ROOT/'dist'/name
    for relative in CHANGED:
        shutil.copy2(ROOT/relative,output/relative)
    shutil.copy2(ROOT/'deploy/cloudbase-identity-pilot/task-delete-migration.sql',output/'task-delete-migration.sql')
    manifest={p.relative_to(output).as_posix():digest(p) for p in sorted(output.rglob('*'))
              if p.is_file() and p.name!='package-manifest.json'}
    before=json.loads((ROOT/'dist'/baseline/'package-manifest.json').read_text(encoding='utf-8'))
    unchanged={k:v for k,v in before.items() if not k.startswith('frontend/dist/') and k not in CHANGED}
    if any(manifest.get(k)!=v for k,v in unchanged.items()):
        raise ValueError('Unrelated backend payload changed')
    (output/'package-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=output.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                info=zipfile.ZipInfo(path.relative_to(output).as_posix());info.create_system=3
                info.external_attr=0o100644 << 16;info.compress_type=zipfile.ZIP_DEFLATED
                bundle.writestr(info,path.read_bytes())
    return {**result,'sha256':digest(archive),'changed_backend_files':list(CHANGED),
            'unrelated_non_frontend_verified_unchanged':len(unchanged),'status':'task_delete_candidate_not_live'}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',required=True);parser.add_argument('--name',required=True)
    args=parser.parse_args();print(json.dumps(package(args.baseline,args.name)))

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("degree_builder", ROOT / "backend/scripts/build_degree_analysis_package.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_isolated_package_can_import_without_demo_audit_or_assets(tmp_path, monkeypatch):
    source_root = builder.ROOT
    target_root = tmp_path / "package-source"
    for relative in builder.FILES + ["deploy/cloudbase-degree-analysis/Dockerfile"]:
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source_root / relative).read_bytes())
    monkeypatch.setattr(builder, "ROOT", target_root)
    archive_path, _, _ = builder.build("anonymous-package-test")
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive_path) as archive:
        # Windows-generated ZIP defaults may become root-only files after a
        # Linux platform unzip. Every source must be readable by runtime UID.
        assert all(info.create_system == 3 and (info.external_attr >> 16) & 0o777 == 0o644
                   for info in archive.infolist())
        dockerfile = archive.read("Dockerfile").decode()
        assert dockerfile.index("COPY backend/app ./app") < dockerfile.index("chmod 0555")
        assert dockerfile.index("chmod 0444") < dockerfile.index("USER campus")
        assert not any("audit.py" in name and "domains/degree" in name for name in archive.namelist())
        assert not any("fixtures/" in name or ".env" in name or "data/" in name for name in archive.namelist())
        assert "fixed-demo" not in archive.read("backend/app/domains/degree/__init__.py").decode()
        archive.extractall(extracted)
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", '''
import json
from app.mcp.degree_http import create_degree_http_app
from app.core.config import Settings
from app.domains.degree.page_report import analyze_page_report
create_degree_http_app(Settings(_env_file=None, app_env="test", mcp_require_auth=True,
    mcp_service_token="fictional-package-test"))
print(json.dumps({"isolated_import": True}))
'''], cwd=extracted / "backend", capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["isolated_import"] is True

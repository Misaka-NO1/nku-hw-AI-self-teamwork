from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.demo_site import create_demo_site


def test_same_origin_site_and_api_errors_are_not_spa_html(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_MODE", "demo_fixture")
    monkeypatch.setenv("ALLOW_PERSONAL_UPLOADS", "false")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'demo.db').as_posix()}")
    get_settings.cache_clear()
    web = tmp_path / "web"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text("<html>local-demo</html>", encoding="utf-8")
    try:
        with TestClient(create_demo_site(web)) as client:
            assert "local-demo" in client.get("/tools/tasks?draft_id=example").text
            assert client.get("/tools/unknown").status_code == 404
            assert client.get("/api/v1/unknown").status_code == 404
            assert client.get("/api/v1/unknown").json()["ok"] is False
            assert client.post("/api/v1/demo/workspaces", json={"fixture_set_id": "demo-v1"}).status_code == 200
            assert client.get("/healthz").status_code == 200
    finally:
        get_settings.cache_clear()


def test_demo_site_cannot_be_used_as_production_entrypoint(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="local demo site"):
            create_demo_site()
    finally:
        get_settings.cache_clear()

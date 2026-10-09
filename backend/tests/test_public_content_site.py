import importlib
import json
from pathlib import Path
from urllib.parse import unquote

from fastapi.testclient import TestClient
import pytest

from app.core.config import get_settings
from app.core.public_content_bundle import safe_content_path


@pytest.fixture
def site(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PUBLIC_CATALOG_PROFILE", "published")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ALLOW_PERSONAL_UPLOADS", "false")
    monkeypatch.setenv("MCP_ENABLE_DOMAIN_TOOLS", "true")
    monkeypatch.setenv("MCP_ENABLE_PLATFORM_COMPAT_TOOLS", "true")
    monkeypatch.setenv("MCP_REQUIRE_AUTH", "true")
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "local-test-only-not-a-real-secret")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_ORIGIN", "http://localhost")
    monkeypatch.delenv("DOMAIN_BUNDLE_MANIFEST_PATH", raising=False)
    get_settings.cache_clear()
    for folder in ("frontend/dist/assets/scenic", "campus-map"):
        (tmp_path / folder).mkdir(parents=True)
    (tmp_path / "frontend/dist/index.html").write_text("<title>Tools</title>")
    (tmp_path / "campus-map/index.html").write_text("<title>Map</title>")
    module = importlib.import_module("app.public_content_site")
    with TestClient(module.create_public_content_site(tmp_path), base_url="http://localhost:8013") as client:
        yield client
    get_settings.cache_clear()


def test_health_and_map_study_destinations(site):
    body = site.get("/healthz").json()
    assert body["personal_uploads"] is False
    assert body["study_data_version"] == "y1-070600fb47f92e70"
    assert site.get("/tools/study").status_code == 200
    assert site.get("/tools/map").status_code == 200
    assert site.get("/campus-map/index.html").status_code == 200
    assert site.get("/tools/tasks").status_code == 404


def test_study_download_link_is_absolute_and_reaches_original_pdf(site):
    query = {"course_id": "y1-s2-programming", "topic": "构造函数", "limit": 2}
    materials = site.get("/api/v1/study/materials", params={"query": json.dumps(query)}).json()["data"]
    for material in materials:
        assert material["download_url"].startswith("http://localhost/api/v1/study/materials/")
        response = site.get(material["download_url"])
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")


def test_no_mutations_private_sources_or_arbitrary_api(site):
    for path in ("/api/v1/demo/workspaces", "/api/v1/tasks/drafts", "/api/v1/tasks/commit", "/api/v1/confirmations", "/api/scenic/spots"):
        assert site.post(path, json={}).status_code == 404
    for path in ("/campus-map/data/scenic-spots.json", "/knowledge/study/library/study.sqlite3", "/backend/.env", "/openapi.json"):
        assert site.get(path).status_code in {404, 401}
    assert site.post("/mcp", json={}).status_code == 401


def test_complete_public_download_catalog_and_attachments(site):
    body = site.get("/api/v1/study/catalog").json()
    materials = body["data"]["materials"]
    assert body["ok"] and body["data"]["total"] == len(materials) == 33
    assert len(body["data"]["courses"]) == 9
    assert sum(c["material_count"] for c in body["data"]["courses"]) == 33
    assert len({m["material_id"] for m in materials}) == 33
    assert all(m["access_scope"] == "public" and m["rights_status"] in {"owned", "authorized"} for m in materials)
    assert all(m["evidence"] == [] for m in materials)
    for material in materials:
        response = site.get(material["download_url"])
        assert response.status_code == 200
        assert not response.history and response.content.startswith(b"%PDF-")
        assert response.headers["content-disposition"].startswith("attachment;")
        disposition = response.headers["content-disposition"]
        filename = (unquote(disposition.split("filename*=utf-8''", 1)[1]) if "filename*=utf-8''" in disposition
                    else disposition.split('filename="', 1)[1].rstrip('"'))
        assert filename == material["file_name"]
        assert response.headers["content-type"] == "application/pdf"
    assert "study-s1-programming-7267a3cd0b2e11aa" not in json.dumps(body)


def test_broad_course_query_does_not_silently_select_one_file(site):
    for course, count in (("y1-s2-programming", 5), ("y1-s2-physics", 7), ("y1-s2-marxism", 6), ("y1-s2-probability", 6)):
        query = {"course_id": course, "topic": None, "limit": 20}
        response = site.get("/api/v1/study/materials", params={"query": json.dumps(query)}).json()
        assert len(response["data"]) == count


def test_mcp_auth_and_read_only_list(site):
    headers = {"Authorization": "Bearer local-test-only-not-a-real-secret", "Accept": "application/json, text/event-stream"}
    response = site.post("/mcp", headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert response.status_code == 200
    assert "platform_search_study_materials" in response.text
    assert "commit_task" not in response.text


@pytest.mark.parametrize("value", ["../private.pdf", "backend/.env", "campus-map/serve.mjs", "campus-map/data/scenic-spots.json", "frontend/dist/assets/../../secret", "knowledge/study/library/other.db", None])
def test_content_package_allowlist(value):
    assert not safe_content_path(value)

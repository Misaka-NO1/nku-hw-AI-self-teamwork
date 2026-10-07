import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.cloud_tasks_site import CloudTasksStore, RPC_URL, create_cloud_tasks_site
from app.core.config import get_settings
from app.core.demo import load_fixture
from app.core.errors import AppError


@pytest.fixture
def cloud_app(tmp_path, monkeypatch):
    for key, value in {"APP_ENV": "staging", "AUTH_MODE": "demo_fixture", "ALLOW_PERSONAL_UPLOADS": "false",
                       "APP_ORIGIN": "https://tasks.example.test", "DEMO_WORKSPACE_TTL_HOURS": "24"}.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("TasksPage test", encoding="utf-8")
    calls = []

    def storage(request):
        assert str(request.url) == RPC_URL
        assert request.headers["Authorization"] == "Bearer test-server-only"
        body = json.loads(request.content)
        calls.append(body)
        op, args = body["op"], body["args"]
        if op == "create_session":
            data = {"workspace_ref": args["workspace_ref"], "expires_epoch": 2000000000}
        elif op == "create_draft":
            data = {"draft_id": args["draft_id"], "kind": "task", "workspace_ref": args["workspace_ref"],
                    "revision": 1, "payload_hash": args["payload_hash"], "status": "draft", "expires_epoch": 2000000000}
        elif op == "commit":
            data = {"task_id": args["task_id"], "revision": 1}
        elif op == "list_tasks":
            data = []
        else:
            data = {"schema_version": "tasks-demo-v1"}
        return httpx.Response(200, json={"ok": True, "data": data})

    store = CloudTasksStore("test-server-only", httpx.MockTransport(storage))
    with TestClient(create_cloud_tasks_site(tmp_path, store), base_url="https://tasks.example.test") as client:
        yield client, calls
    get_settings.cache_clear()


def test_cloud_session_secure_cookie_no_server_secret(cloud_app):
    client, calls = cloud_app
    response = client.post("/api/v1/demo/workspaces", json={"fixture_set_id": "demo-v1"}, headers={"Origin": "https://tasks.example.test"})
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"] and "HttpOnly" in response.headers["set-cookie"]
    assert "test-server-only" not in response.text and "session_token" not in response.text
    assert calls[-1]["op"] == "create_session"
    assert len(calls[-1]["args"]["token_hash"]) == 64


@pytest.mark.parametrize("headers", [{}, {"Origin": "https://evil.example"}, {"Origin": "null"}])
def test_cloud_session_requires_same_origin(cloud_app, headers):
    client, calls = cloud_app
    count = len(calls)
    response = client.post("/api/v1/demo/workspaces", json={"fixture_set_id": "demo-v1"}, headers=headers)
    assert response.status_code == 403 and len(calls) == count


def test_cloud_draft_fixture_only_and_write_gates(cloud_app):
    client, calls = cloud_app
    origin = {"Origin": "https://tasks.example.test"}
    session = client.post("/api/v1/demo/workspaces", json={"fixture_set_id": "demo-v1"}, headers=origin).json()["data"]
    headers = {**origin, "X-CSRF-Token": session["csrf_token"], "Idempotency-Key": "demo-draft-key"}
    notice = dict(load_fixture("notice-event.demo.json"))
    payload = {"workspace_ref": session["workspace_ref"], "notice": notice}
    response = client.post("/api/v1/tasks/drafts", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["review_url"].startswith("https://tasks.example.test/tools/tasks?draft_id=")
    count = len(calls)
    notice["title"] = "A real personal notice"
    assert client.post("/api/v1/tasks/drafts", json=payload, headers=headers).status_code == 403
    assert len(calls) == count
    assert client.post("/api/v1/tasks/commit", json={"confirmation_id": "confirmation_demo", "idempotency_key": "test-commit-key"}, headers=origin).status_code == 403
    assert len(calls) == count


def test_shared_bearer_cannot_write_as_browser(cloud_app):
    client, calls = cloud_app
    count = len(calls)
    response = client.post("/api/v1/tasks/commit", json={"confirmation_id": "confirmation_demo", "idempotency_key": "test-commit-key"},
                           headers={"Authorization": "Bearer test-server-only", "Origin": "https://tasks.example.test", "X-CSRF-Token": "fake"})
    assert response.status_code == 401 and len(calls) == count


def test_cloud_time_check_uses_existing_b_algorithm(cloud_app):
    client, _ = cloud_app
    response = client.post("/api/v1/time/check", json=load_fixture("time-event-query.demo.json"))
    assert response.status_code == 200 and len(response.json()["data"]["conflicts"]) == 2
    query = dict(load_fixture("time-event-query.demo.json"))
    query["workspace_ref"] = "other-person"
    assert client.post("/api/v1/time/check", json=query).status_code == 403


@pytest.mark.parametrize("response", [httpx.Response(401, text="secret upstream"), httpx.Response(200, json=[]), httpx.Response(200, json={"ok": False,"code":"SQL_ERROR","status":500,"message":"secret upstream"})])
def test_cloud_storage_errors_redacted(response):
    store = CloudTasksStore("test-server-only", httpx.MockTransport(lambda _: response))
    with pytest.raises(AppError) as raised:
        store.call("probe", {})
    assert raised.value.status_code == 503 and raised.value.retryable
    assert "secret" not in raised.value.message and "test-server-only" not in raised.value.message
    store.close()


def test_cloud_unknown_routes_not_spa_and_no_mcp(cloud_app):
    client, _ = cloud_app
    assert client.get("/tools/tasks").status_code == 200
    assert client.get("/api/v1/anything").status_code == 404
    assert client.post("/mcp", json={}).status_code == 404
    assert client.get("/tools/import").status_code == 404


def test_cloud_oversized_chunked_body_denied_before_storage(cloud_app):
    client, calls = cloud_app
    count = len(calls)
    response = client.post("/api/v1/demo/workspaces", content=iter([b"x" * 16000, b"y" * 20000]),
                           headers={"Origin": "https://tasks.example.test", "Content-Type": "application/json"})
    assert response.status_code == 413 and response.json()["ok"] is False
    assert len(calls) == count


@pytest.mark.parametrize("variable", ["CLOUDBASE_APIKEY", "CLOUDBASE_API_KEY"])
def test_cloud_named_key_injection_supported(tmp_path, monkeypatch, variable):
    import app.cloud_tasks_site as module

    for name, value in {"APP_ENV": "staging", "AUTH_MODE": "demo_fixture",
                        "ALLOW_PERSONAL_UPLOADS": "false", "APP_ORIGIN": "https://tasks.example.test",
                        "DEMO_WORKSPACE_TTL_HOURS": "24"}.items():
        monkeypatch.setenv(name, value)
    for name in ("CLOUDBASE_APIKEY", "CLOUDBASE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(variable, "synthetic-test-key")
    captured = []

    class FakeStore:
        def __init__(self, key):
            captured.append(key)

        def call(self, op, args):
            return {"schema_version": "tasks-demo-v1"}

        def close(self):
            pass

    monkeypatch.setattr(module, "CloudTasksStore", FakeStore)
    (tmp_path / "index.html").write_text("TasksPage test", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    get_settings.cache_clear()
    try:
        with TestClient(create_cloud_tasks_site(tmp_path), base_url="https://tasks.example.test") as client:
            assert client.get("/healthz").status_code == 200
        assert captured == ["synthetic-test-key"]
    finally:
        get_settings.cache_clear()

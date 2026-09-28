from fastapi.testclient import TestClient
import pytest

from app.main import app


def test_healthz_uses_unified_envelope_and_request_id() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz", headers={"X-Request-ID": "test-request-1"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-1"
    assert response.json() == {
        "ok": True,
        "data": {
            "status": "ok",
            "build_id": "test-build",
            "server_time": response.json()["data"]["server_time"],
        },
        "error": None,
        "meta": {
            "schema_version": "1.0.0",
            "request_id": "test-request-1",
            "data_version": None,
            "calculation_version": None,
            "warnings": [],
            "evidence_refs": [],
        },
    }


def test_readyz_checks_sqlite() -> None:
    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["data"]["dependencies"] == {"database": "ready"}


def test_unknown_route_uses_error_envelope() -> None:
    with TestClient(app) as client:
        response = client.get("/does-not-exist")

    payload = response.json()
    assert response.status_code == 404
    assert payload["ok"] is False
    assert payload["data"] is None
    assert payload["error"]["code"] == "NOT_FOUND"


def test_rest_lifespan_rejects_invalid_deployment_before_creating_db(tmp_path, monkeypatch):
    from app.core.config import Settings
    database = tmp_path / "must-not-create.db"
    runtime = Settings(app_env="staging", mcp_public_url="http://invalid/mcp",
                       database_url="sqlite:///" + database.as_posix())
    monkeypatch.setattr("app.main.get_settings", lambda: runtime)
    with pytest.raises(ValueError, match="HTTPS"):
        with TestClient(app):
            pass
    assert not database.exists()

"""Offline diagnostic tests, not evidence of a live cloud request."""
import logging

import pytest
from fastapi.testclient import TestClient

from app.cloud_identity_site import create_cloud_identity_site
from app.cloud_tasks_site import ENV_ID
from app.core.config import Settings
from app.core.errors import AppError


class ProbeStore:
    def __init__(self):
        self.mode="ok"
        self.calls=[]

    def call(self,operation,arguments):
        self.calls.append(operation)
        if operation=="configure_subjects":
            return None
        assert operation=="probe"
        if self.mode=="unavailable":
            raise AppError(503,"DEPENDENCY_UNAVAILABLE","Identity storage unavailable",True)
        if self.mode=="exception":
            raise RuntimeError("DO_NOT_LOG_UPSTREAM_CREDENTIAL")
        if self.mode=="wrong-schema":
            return {"schema_version":"wrong"}
        return {"schema_version":"identity-pilot-v1"}

    def close(self):
        pass


@pytest.fixture
def diagnostic_site(tmp_path):
    (tmp_path/"assets").mkdir()
    (tmp_path/"index.html").write_text("<html>fictional UI</html>",encoding="utf-8")
    settings=Settings(_env_file=None,app_env="test",app_origin="https://pilot.example.invalid",
        cloud_identity_pilot_enabled=True,cloudbase_auth_pilot_enabled=True,
        cloudbase_auth_profile="pg_registered",cloudbase_auth_env_id=ENV_ID,
        cloudbase_auth_pilot_user_ids=["fictional-a","fictional-b"],build_id="diagnostic-test-r8")
    store=ProbeStore()
    with TestClient(create_cloud_identity_site(tmp_path,store,settings),
                    base_url=settings.app_origin,raise_server_exceptions=False) as client:
        yield client,store


def messages(caplog):
    return [record.getMessage() for record in caplog.records
            if record.name=="uvicorn.error" and record.getMessage().startswith("campus_health ")]


def test_health_logs_arrival_and_real_status_without_request_data(diagnostic_site,caplog):
    client,store=diagnostic_site
    caplog.set_level(logging.INFO,logger="uvicorn.error")
    response=client.get("/healthz?token=DO_NOT_LOG_QUERY",headers={
        "Authorization":"Bearer DO_NOT_LOG_HEADER","Cookie":"secret=DO_NOT_LOG_COOKIE",
        "X-Request-ID":"DO_NOT_LOG_REQUEST_ID"})
    assert response.status_code==200 and response.json()["oauth_enabled"] is False
    assert store.calls[-1]=="probe"
    logs=messages(caplog)
    assert len(logs)==2
    assert logs[0]=="campus_health phase=received route=/healthz build=diagnostic-test-r8"
    assert "status=200 elapsed_ms=" in logs[1]
    assert "DO_NOT_LOG" not in " ".join(logs)
    assert "no-store" in response.headers["cache-control"]


@pytest.mark.parametrize("mode,status",[("unavailable",503),("wrong-schema",503),("exception",500)])
def test_dependency_and_unexpected_errors_stay_closed_and_sanitized(diagnostic_site,caplog,mode,status):
    client,store=diagnostic_site
    store.mode=mode
    caplog.set_level(logging.INFO,logger="uvicorn.error")
    response=client.get("/healthz")
    assert response.status_code==status and response.json()["ok"] is False
    logs=messages(caplog)
    assert len(logs)==2 and f"status={status} " in logs[1]
    assert "DO_NOT_LOG" not in " ".join(logs)+response.text


def test_container_probe_is_independent_and_business_is_not_logged(diagnostic_site,caplog):
    client,store=diagnostic_site
    store.mode="unavailable"
    caplog.set_level(logging.INFO,logger="uvicorn.error")
    before=len(store.calls)
    assert client.get("/__tcb_probe__").text=="ok"
    assert len(store.calls)==before
    assert "status=200 " in messages(caplog)[1]
    caplog.clear()
    assert client.get("/tools/tasks?draft_id=DO_NOT_LOG_DRAFT").status_code==200
    assert client.get("/healthz-extra?token=DO_NOT_LOG_PATH").status_code==404
    assert client.post("/healthz",json={"secret":"DO_NOT_LOG_BODY"}).status_code==405
    assert messages(caplog)==[]


def test_bootstrap_diagnostics_do_not_open_identity_or_log_invalid_build(tmp_path,caplog):
    settings=Settings(_env_file=None,app_env="staging",cloud_identity_bootstrap_enabled=True,
                      build_id="bad\nDO_NOT_LOG_BUILD")
    caplog.set_level(logging.INFO,logger="uvicorn.error")
    with TestClient(create_cloud_identity_site(tmp_path,settings=settings)) as client:
        health=client.get("/healthz")
        assert health.status_code==200 and health.json()["status"]=="configuration_pending"
        assert health.json()["database_connected"] is False
        assert all("build=redacted" in line for line in messages(caplog))
        assert "DO_NOT_LOG" not in " ".join(messages(caplog))
        caplog.clear()
        assert client.get("/oauth/authorize").status_code==503
        assert client.post("/api/v1/auth/cloudbase/session").status_code==503
        assert messages(caplog)==[]

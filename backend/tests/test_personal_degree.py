"""HTTP + actual local PostgreSQL + original OAuth. No production data or calls."""
import json
import shutil
import subprocess
from copy import deepcopy
from threading import Lock

import httpx
import pytest
from fastapi.testclient import TestClient

import test_cloud_identity_site as identity_tests
from app.cloud_identity_site import create_cloud_identity_site
from app.core.cloud_identity_store import CloudIdentityStore, DEGREE_RPC_URL, storage_result
from app.core.errors import AppError
from test_cloud_identity_site import ORIGIN, login, headers, save
from test_competition_oauth import authorize, exchange


class DegreePostgresStore(identity_tests.RealPostgresPipeStore):
    def __init__(self):
        self.process = subprocess.Popen([shutil.which("node"), "personal-degree-rpc-driver.mjs"], cwd=identity_tests.SQL_DIR,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
        assert json.loads(self.process.stdout.readline()) == {"ready": True}
        self.lock = Lock()

    def degree_call(self, op, args):
        return self.call("__degree__:" + op, args)


@pytest.fixture
def degree_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(identity_tests, "RealPostgresPipeStore", DegreePostgresStore)
    yield from identity_tests.environment.__wrapped__(tmp_path, monkeypatch)


def observation():
    return {"kind": "degree-table-observation", "source": {
        "url": "https://eamis.nankai.edu.cn/eams/myPlanCompl.action", "captured_at": "2026-10-10T00:00:00Z",
        "coverage": "partial", "adapter_verified": False},
        "headers": ["序号", "课程序号", "课程名称", "要求学分", "实修学分", "成绩", "是否通过", "备注"],
        "rows": [{"locator": "table-row:2", "cells": ["1 虚构必修模块（所有子项满足）", "6", "4", "", "缺2学分缺1门", ""]},
            {"locator": "table-row:3", "cells": ["1", "ANON-A", "虚构已通过课", "2", "2", "88", "是", "必修"]},
            {"locator": "table-row:4", "cells": ["2", "ANON-B", "虚构在读课", "2", "2", "--", "是", "在读，必修"]},
            {"locator": "table-row:5", "cells": ["3", "ANON-C", "虚构待完成课", "2", "0", "--", "否", "必修"]}]}


def draft(client, owner, key="degree-draft-001", payload=None):
    response = client.post("/api/v1/degree/import-drafts", json=observation() if payload is None else payload, headers=headers(owner, key))
    assert response.status_code == 200, response.text
    result = client.get("/api/v1/degree/drafts/" + response.json()["data"]["draft_id"])
    assert result.status_code == 200, result.text
    return result.json()["data"]


def confirmation(client, owner, item, key="degree-confirm-001"):
    body = {key: item[key] for key in ("draft_id", "revision", "payload_hash")}
    response = client.post("/api/v1/degree/confirmations", json={**body, "share_with_agent": True}, headers=headers(owner, key))
    assert response.status_code == 200, response.text
    return {"confirmation_id": response.json()["data"]["confirmation_id"], "idempotency_key": key + "-save"}


def test_own_import_confirm_readback_agent_restart_and_original_timetable_unchanged(degree_environment):
    settings, root, store, _ = degree_environment
    runtime = settings.model_copy(update={"cloud_personal_degree_enabled": True, "cloud_oauth_competition_compat_enabled": True,
        "cloud_personal_schedules_enabled": True, "cloud_notice_text_pilot_enabled": True})
    with TestClient(create_cloud_identity_site(root, store, runtime), base_url=ORIGIN) as a, TestClient(create_cloud_identity_site(root, store, runtime), base_url=ORIGIN) as b:
        owner, other = login(a), login(b, "fictional-b")
        save(a, owner, "schedule", "timetable.demo.json")
        bearer = {"Authorization": "Bearer " + exchange(a, authorize(a)).json()["access_token"]}
        before = a.get("/oauth/records", headers=bearer).json()["data"]
        assert a.get("/oauth/degree/records", headers=bearer).json()["data"]["degree"] is None
        item = draft(a, owner)
        assert item["payload"] == observation() and item["kind"] == "degree"
        assert a.get("/api/v1/degree/current").json()["data"] is None
        assert a.get("/oauth/degree/records", headers=bearer).json()["data"]["degree"] is None
        assert b.get("/api/v1/degree/drafts/" + item["draft_id"]).status_code == 404
        receipt = confirmation(a, owner, item)
        assert b.post("/api/v1/degree/commit", json=receipt, headers=headers(other)).status_code == 404
        committed = a.post("/api/v1/degree/commit", json=receipt, headers=headers(owner))
        assert committed.status_code == 200, committed.text
        assert a.post("/api/v1/degree/commit", json=receipt, headers=headers(owner)).json()["data"] == committed.json()["data"]
        current = a.get("/api/v1/degree/current").json()["data"]
        assert current["observation"] == observation() and current["revision"] == 1
        assert current["report"]["module_summaries"][0]["observed_passed_credits"] == "2"
        assert current["report"]["module_summaries"][0]["observed_in_progress_credits"] == "2"
        assert current["report"]["can_decide_complete"] is False
        assert a.get("/oauth/degree/records", headers=bearer).json()["data"]["degree"] == current
        assert a.get("/oauth/records", headers=bearer).json()["data"] == before
        assert b.get("/api/v1/degree/current").json()["data"] is None
        b_bearer = {"Authorization": "Bearer " + exchange(b, authorize(b)).json()["access_token"]}
        assert b.get("/oauth/degree/records", headers=b_bearer).json()["data"]["degree"] is None
        # A's grant retains A's owner even when browser cookies belong to B.
        assert b.get("/oauth/degree/records", headers=bearer).json()["data"]["degree"] == current
        cookies = dict(a.cookies)
    with TestClient(create_cloud_identity_site(root, store, runtime), base_url=ORIGIN) as restored:
        restored.cookies.update(cookies)
        assert restored.get("/api/v1/degree/current").json()["data"] == current
        assert restored.get("/oauth/degree/records", headers=bearer).json()["data"]["degree"] == current
        restored.post("/api/v1/auth/cloudbase/logout", headers=headers(owner))
        assert restored.get("/oauth/degree/records", headers=bearer).status_code == 401
        assert restored.get("/api/v1/degree/current").status_code == 401


def test_bound_browser_degree_save_reaches_existing_agent_grant(degree_environment):
    """The extension browser's child session must share the Agent source owner."""
    from test_agent_device import grant, device_post, agent_bind
    settings, root, store, _ = degree_environment
    runtime = settings.model_copy(update={"cloud_personal_degree_enabled": True,
        "cloud_oauth_competition_compat_enabled": True, "cloud_persistent_auth_enabled": True,
        "cloud_agent_device_binding_enabled": True, "cloud_personal_schedules_enabled": True,
        "cloud_personal_tasks_enabled": True, "cloud_notice_text_pilot_enabled": True,
        "cloud_task_calendar_enabled": True})
    site = create_cloud_identity_site(root, store, runtime)
    with TestClient(site, base_url=ORIGIN) as source, TestClient(site, base_url=ORIGIN) as browser:
        owner = login(source)
        bearer = grant(source)
        code = device_post(browser, "start").json()["data"]["device_code"]
        assert agent_bind(source, bearer, code).status_code == 200
        claimed = device_post(browser, "claim")
        assert claimed.status_code == 200
        browser_owner = browser.get("/api/v1/auth/cloudbase/browser-session",
            headers={"X-Campus-Session-Read": "1"}).json()["data"]
        assert browser_owner["workspace_ref"] == owner["workspace_ref"]
        item = draft(browser, browser_owner, "bound-degree-draft-001")
        receipt = confirmation(browser, browser_owner, item, "bound-degree-confirm-001")
        committed = browser.post("/api/v1/degree/commit", json=receipt, headers=headers(browser_owner))
        assert committed.status_code == 200
        saved = browser.get("/api/v1/degree/current").json()["data"]
        assert saved is not None
        agent = source.get("/oauth/degree/records", headers=bearer)
        assert agent.status_code == 200
        assert agent.json()["data"]["degree"] == saved


def test_degree_gate_sources_csrf_owner_inputs_and_stale_revision(degree_environment):
    settings, root, store, closed = degree_environment
    assert closed.post("/api/v1/degree/import-drafts", json=observation(), headers={"Idempotency-Key": "degree-closed-001"}).status_code == 403
    runtime = settings.model_copy(update={"cloud_personal_degree_enabled": True})
    with TestClient(create_cloud_identity_site(root, store, runtime), base_url=ORIGIN) as a:
        assert a.get("/api/v1/degree/current").status_code == 401
        owner = login(a)
        assert a.post("/api/v1/degree/import-drafts", json=observation(), headers={"Origin": ORIGIN, "Idempotency-Key": "degree-no-csrf"}).status_code == 403
        bad = deepcopy(observation()); bad["rows"][0]["cells"][0] = "姓名：PRIVATE_TEST_VALUE"
        invalid = a.post("/api/v1/degree/import-drafts", json=bad, headers=headers(owner, "degree-bad-001"))
        assert invalid.status_code == 422 and "PRIVATE_TEST_VALUE" not in invalid.text
        assert a.get("/api/v1/degree/current?owner=other").status_code == 422
        stale = draft(a, owner, "degree-stale-001")
        item = draft(a, owner, "degree-current-001")
        body = {key: item[key] for key in ("draft_id", "revision", "payload_hash")}
        assert a.post("/api/v1/degree/confirmations", json={**body, "share_with_agent": False}, headers=headers(owner, "degree-no-consent")).status_code == 409
        receipt = confirmation(a, owner, item)
        assert a.post("/api/v1/degree/commit", json=receipt, headers=headers(owner)).status_code == 200
        body = {key: stale[key] for key in ("draft_id", "revision", "payload_hash")}
        assert a.post("/api/v1/degree/confirmations", json={**body, "share_with_agent": True}, headers=headers(owner, "degree-stale-confirm")).status_code == 409


def test_degree_transport_uses_own_rpc_and_rejects_unknown_operations():
    calls = []
    def transport(request):
        assert str(request.url) == DEGREE_RPC_URL
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "data": None})
    store = CloudIdentityStore("fictional-server-key", httpx.MockTransport(transport))
    try:
        assert store.degree_call("records", {}) is None
        with pytest.raises(AppError): store.degree_call("delete_owner", {})
        assert len(calls) == 1
    finally: store.close()


def test_degree_storage_failure_does_not_stop_original_identity_or_timetable(degree_environment, monkeypatch):
    settings, root, store, _ = degree_environment
    runtime = settings.model_copy(update={"cloud_personal_degree_enabled": True})
    def unavailable(op, args):
        raise AppError(503, "DEPENDENCY_UNAVAILABLE", "培养计划存储暂时不可用", True)
    monkeypatch.setattr(store, "degree_call", unavailable)
    with TestClient(create_cloud_identity_site(root, store, runtime), base_url=ORIGIN) as a:
        owner = login(a)
        assert a.get("/healthz").status_code == 200
        assert a.get("/tools/timetable").status_code == 200
        save(a, owner, "schedule", "timetable.demo.json")
        assert a.get("/api/v1/schedules/current", params={"workspace_ref": owner["workspace_ref"]}).status_code == 200
        assert a.get("/api/v1/degree/current").status_code == 503


def test_private_visitors_use_same_import_and_agent_owner_without_changing_timetable(degree_environment):
    from test_browser_visitor import begin
    settings, root, store, _ = degree_environment
    runtime = settings.model_copy(update={"cloud_personal_degree_enabled": True, "cloud_oauth_competition_compat_enabled": True,
        "cloud_notice_text_pilot_enabled": True, "cloud_task_calendar_enabled": True,
        "cloud_personal_tasks_enabled": True, "cloud_persistent_auth_enabled": True,
        "cloud_personal_schedules_enabled": True, "cloud_agent_device_binding_enabled": True, "cloud_visitor_enabled": True})
    with TestClient(create_cloud_identity_site(root, store, runtime), base_url=ORIGIN) as a, TestClient(create_cloud_identity_site(root, store, runtime), base_url=ORIGIN) as b:
        owner, other = begin(a).json()["data"], begin(b).json()["data"]
        assert owner["workspace_ref"] != other["workspace_ref"]
        bearer = {"Authorization": "Bearer " + exchange(a, authorize(a)).json()["access_token"]}
        before = a.get("/oauth/records", headers=bearer).json()["data"]
        item = draft(a, owner)
        receipt = confirmation(a, owner, item)
        assert a.post("/api/v1/degree/commit", json=receipt, headers=headers(owner)).status_code == 200
        readback = a.get("/oauth/degree/records", headers=bearer)
        assert readback.status_code == 200, readback.text
        assert readback.json()["data"]["degree"]["workspace_ref"] == owner["workspace_ref"]
        assert a.get("/oauth/records", headers=bearer).json()["data"] == before
        assert b.get("/api/v1/degree/current").json()["data"] is None
        assert b.post("/api/v1/degree/import-drafts", json=observation(), headers=headers(owner, "visitor-cross-csrf")).status_code == 403
        a.post("/api/v1/auth/cloudbase/logout", headers=headers(owner))
        assert a.get("/oauth/degree/records", headers=bearer).status_code == 401

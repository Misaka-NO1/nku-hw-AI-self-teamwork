"""Local HTTP + embedded PostgreSQL; not a live Chrome/GeniOS acceptance claim."""
import pytest
from fastapi.testclient import TestClient

from app.cloud_identity_site import create_cloud_identity_site
from app.device_login_site import DEVICE_COOKIE, DEVICE_PATH
from test_cloud_identity_site import environment, login, headers, save, ORIGIN


@pytest.fixture
def devices(environment):
    settings, root, database, _ = environment
    runtime = settings.model_copy(update={"cloud_device_login_enabled": True})
    database.device_call = lambda op, args: database.call("__device__:" + op, args)
    site = create_cloud_identity_site(root, database, runtime)
    with TestClient(site, base_url=ORIGIN) as source, TestClient(site, base_url=ORIGIN) as target:
        yield runtime, root, database, source, target


def device_headers(owner=None):
    return {"Origin": ORIGIN, "X-Campus-Device": "1", **({"X-CSRF-Token": owner["csrf_token"]} if owner else {})}


def post(client, operation, value, owner=None):
    return client.post(DEVICE_PATH + "/" + operation, json=value, headers=device_headers(owner))


def bind(source, target, owner):
    start = post(target, "start", {})
    assert start.status_code == 200
    code = start.json()["data"]["user_code"]
    assert "HttpOnly" in start.headers["set-cookie"] and "Secure" in start.headers["set-cookie"]
    assert "SameSite=strict" in start.headers["set-cookie"]
    assert post(target, "claim", {}).json()["data"]["status"] == "pending"
    reviewed = post(source, "review", {"user_code": code}, owner)
    assert reviewed.status_code == 200
    receipt = reviewed.json()["data"]["review_receipt"]
    assert post(target, "claim", {}).json()["data"]["status"] == "pending"
    approved = post(source, "approve", {"user_code": code, "review_receipt": receipt, "confirm_device": True}, owner)
    assert approved.status_code == 200
    claimed = post(target, "claim", {})
    assert claimed.status_code == 200
    assert all("HttpOnly" in c and "Secure" in c for c in claimed.headers.get_list("set-cookie"))
    return code, receipt, claimed.json()["data"]


def test_binds_same_owner_and_reads_existing_schedule_after_backend_restart(devices):
    settings, root, database, source, target = devices
    a = login(source)
    save(source, a, "schedule", "timetable.demo.json")
    code, receipt, bound = bind(source, target, a)
    assert bound["workspace_ref"] == a["workspace_ref"]
    read = target.get("/api/v1/schedules/current", params={"workspace_ref": a["workspace_ref"]})
    assert read.status_code == 200
    raw_session = target.cookies.get("campus_session")
    context = target.cookies.get("campus_browser_context")
    assert raw_session not in code and raw_session not in receipt
    with TestClient(create_cloud_identity_site(root, database, settings), base_url=ORIGIN) as restarted:
        restarted.cookies.set("campus_session", raw_session)
        restarted.cookies.set("campus_browser_context", context)
        resumed = restarted.get("/api/v1/auth/cloudbase/browser-session", headers={"X-Campus-Session-Read": "1"})
        assert resumed.status_code == 200 and resumed.json()["data"]["workspace_ref"] == a["workspace_ref"]
        assert restarted.get("/api/v1/schedules/current", params={"workspace_ref": a["workspace_ref"]}).json()["data"] == read.json()["data"]
    assert source.post("/api/v1/auth/cloudbase/logout", headers=headers(a)).status_code == 200
    assert target.get("/api/v1/auth/cloudbase/browser-session", headers={"X-Campus-Session-Read": "1"}).status_code == 401


def test_bound_device_does_not_read_other_owner_schedule(devices):
    _, _, _, source, target = devices
    a = login(source)
    bind(source, target, a)
    b = login(source, "fictional-b")
    save(source, b, "schedule", "timetable.demo.json")
    assert target.get("/api/v1/schedules/current", params={"workspace_ref": b["workspace_ref"]}).status_code == 404
    assert target.get("/api/v1/schedules/current", params={"workspace_ref": a["workspace_ref"]}).status_code == 404


def test_display_code_and_review_receipt_cannot_claim_on_a_third_browser(devices):
    settings, root, database, source, target = devices
    a = login(source)
    code, receipt, _ = bind(source, target, a)
    with TestClient(create_cloud_identity_site(root, database, settings), base_url=ORIGIN) as attacker:
        for wrong in (code, receipt):
            attacker.cookies.set(DEVICE_COOKIE, wrong, path=DEVICE_PATH)
            response = post(attacker, "claim", {})
            assert response.status_code in {401, 410}
            assert "campus_session=" not in response.headers.get("set-cookie", "")


def test_no_silent_account_replacement_and_no_pairing_chain(devices):
    _, _, _, source, target = devices
    a = login(source)
    assert post(source, "start", {}).status_code == 409
    _, _, bound = bind(source, target, a)
    assert post(target, "start", {}).status_code == 409
    assert post(target, "claim", {}).status_code == 409
    source.cookies.clear()
    code = post(source, "start", {}).json()["data"]["user_code"]
    assert post(target, "review", {"user_code": code}, bound).status_code == 403


@pytest.mark.parametrize("override", [
    {"SYS_USERID": "owner-a"}, {"owner_subject_id": "owner-a"}, {"workspace_ref": "owner-a"},
])
def test_identity_overrides_rejected(devices, override):
    _, _, _, _, target = devices
    assert post(target, "start", override).status_code == 422


def test_origin_csrf_duplicate_body_query_and_opt_in_are_enforced(devices, environment):
    _, _, _, source, target = devices
    a = login(source)
    code = post(target, "start", {}).json()["data"]["user_code"]
    assert post(source, "review", {"user_code": code}).status_code == 403
    assert target.post(DEVICE_PATH + "/start", json={}, headers={"Origin": "https://other.invalid", "X-Campus-Device": "1"}).status_code == 403
    assert target.post(DEVICE_PATH + "/start?owner_id=other", json={}, headers=device_headers()).status_code == 403
    assert target.post(DEVICE_PATH + "/review", content='{"user_code":"a","user_code":"b"}', headers={**device_headers(), "Content-Type": "application/json"}).status_code == 422
    assert post(source, "approve", {"user_code": code, "review_receipt": "x"*43, "confirm_device": "true"}, a).status_code == 409
    assert post(environment[3], "start", {}).status_code == 404


def test_device_page_has_explicit_consent_same_origin_only_csp_and_no_credential_urls(devices, environment):
    _, _, _, _, target = devices
    assert target.get("/healthz").json()["device_login_enabled"] is True
    assert target.get("/api/v1/auth/cloudbase/config").json()["data"]["device_login_enabled"] is True
    assert environment[3].get("/healthz").json()["device_login_enabled"] is False
    response = target.get("/tools/device-login")
    assert response.status_code == 200
    assert 'connect-src \'self\'' in response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "确认绑定这台浏览器" in response.text and "这不是 GeniOS 自动识别登录" in response.text
    assert 'localStorage' not in response.text and 'sessionStorage' not in response.text
    assert 'https://' not in response.text
    assert target.get("/tools/device-login?code=not-a-login-secret").status_code == 422
    assert environment[3].get("/tools/device-login").status_code == 404

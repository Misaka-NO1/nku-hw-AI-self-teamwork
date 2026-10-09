"""Fixed browser + Agent OAuth owner binding, real local PostgreSQL only."""
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.cloud_identity_site import create_cloud_identity_site
from app.agent_device_site import COOKIE, PATH
from test_cloud_identity_site import environment, login, headers, save, ORIGIN, SECRET
from test_competition_oauth import PARAMS, exchange


@pytest.fixture
def fixed(environment):
    settings, root, db, _ = environment
    runtime = settings.model_copy(update={"cloud_oauth_competition_compat_enabled": True,
        "cloud_notice_text_pilot_enabled": True, "cloud_task_calendar_enabled": True,
        "cloud_personal_tasks_enabled": True, "cloud_persistent_auth_enabled": True,
        "cloud_agent_device_binding_enabled": True})
    with TestClient(create_cloud_identity_site(root, db, runtime), base_url=ORIGIN) as source, TestClient(create_cloud_identity_site(root, db, runtime), base_url=ORIGIN) as target:
        yield runtime, root, db, source, target


def grant(client, scope="demo:read tasks:read tasks:write devices:bind"):
    page = client.get("/oauth/authorize", params={**PARAMS, "scope": scope})
    assert page.status_code == 200, page.text
    if "devices:bind" in scope:
        assert "固定设备码" in page.text
    transaction = re.search(r'name="transaction" value="([^"]+)"', page.text)[1]
    response = client.post("/oauth/approve", data={"transaction": transaction, "decision": "allow"}, headers={"Origin": ORIGIN}, follow_redirects=False)
    code = parse_qs(urlsplit(response.headers["location"]).query)["code"][0]
    exchanged = exchange(client, code)
    assert exchanged.status_code == 200, exchanged.text
    return {"Authorization": "Bearer " + exchanged.json()["access_token"]}


def device_post(client, op, body=None):
    return client.post(PATH + "/" + op, json={} if body is None else body, headers={"Origin": ORIGIN, "X-Campus-Device": "1"})


def agent_bind(client, bearer, code, confirm=True, **extra):
    return client.post("/oauth/devices/bind", json={"device_code": code, "confirm_binding": confirm, **extra}, headers=bearer)


def test_fixed_code_and_private_cookie_survive_reload_and_backend_restart(fixed):
    runtime, root, db, _, target = fixed
    first = device_post(target, "start")
    assert first.status_code == 200, first.text
    data = first.json()["data"]
    assert re.fullmatch(r"DEV-[A-Z2-7]{26}", data["device_code"])
    assert "expires_epoch" not in data
    assert "HttpOnly" in first.headers["set-cookie"] and "Secure" in first.headers["set-cookie"]
    assert device_post(target, "start").json()["data"] == data
    secret = target.cookies.get(COOKIE)
    assert secret not in first.text and secret not in target.get("/tools/device-login").text
    with TestClient(create_cloud_identity_site(root, db, runtime), base_url=ORIGIN) as restart:
        restart.cookies.set(COOKIE, secret)
        assert device_post(restart, "start").json()["data"] == data
    assert device_post(target, "claim").json()["data"]["status"] == "pending"


def test_agent_and_bound_browser_read_same_owner_records_and_revoke_cascades(fixed):
    _, _, _, source, target = fixed
    a = login(source)
    save(source, a, "schedule", "timetable.demo.json")
    _, task = save(source, a)
    bearer = grant(source)
    code = device_post(target, "start").json()["data"]["device_code"]
    result = agent_bind(source, bearer, code)
    assert result.status_code == 200, result.text
    assert result.json()["data"]["workspace_ref"] == a["workspace_ref"]
    bound = device_post(target, "claim")
    assert bound.status_code == 200, bound.text
    assert bound.json()["data"]["workspace_ref"] == a["workspace_ref"]
    assert target.get("/tools/timetable").status_code == 200
    assert target.get("/api/v1/schedules/current", params={"workspace_ref": a["workspace_ref"]}).status_code == 200
    records = source.get("/oauth/records", headers=bearer)
    assert records.status_code == 200, records.text
    assert any(t["task_id"] == task["task_id"] for t in records.json()["data"]["tasks"])
    b = login(source, "fictional-b")
    assert target.get("/api/v1/schedules/current", params={"workspace_ref": b["workspace_ref"]}).status_code == 404
    assert source.get("/oauth/records", headers=bearer).json()["data"]["schedule"]["workspace_ref"] == a["workspace_ref"]
    assert agent_bind(source, grant(source), code).status_code == 403
    assert device_post(target, "claim").json()["data"]["status"] == "already_logged_in"
    token = bearer["Authorization"].removeprefix("Bearer ")
    assert source.post("/oauth/revoke", json={"token": token, "client_id": PARAMS["client_id"], "client_secret": SECRET}).status_code == 200
    assert target.get("/api/v1/auth/cloudbase/browser-session", headers={"X-Campus-Session-Read": "1"}).status_code == 401
    assert device_post(target, "start").json()["data"]["device_code"] == code
    assert device_post(target, "claim").json()["data"]["status"] == "pending"


def test_scope_confirmation_origin_and_identity_injection_guards(fixed):
    runtime, root, db, source, target = fixed
    login(source)
    code = device_post(target, "start").json()["data"]["device_code"]
    old = grant(source, "demo:read tasks:read tasks:write")
    assert agent_bind(source, old, code).status_code == 403
    bearer = grant(source)
    assert agent_bind(source, bearer, code, False).status_code == 409
    for extra in ({"SYS_USERID": "a"}, {"workspace_ref": "a"}, {"owner_subject_id": "a"}):
        assert agent_bind(source, bearer, code, **extra).status_code == 422
        assert device_post(target, "start", extra).status_code == 422
    assert target.post(PATH + "/start", json={}, headers={"Origin": "https://other.invalid", "X-Campus-Device": "1"}).status_code == 403
    assert target.post(PATH + "/start", content='{"a":1,"a":2}', headers={"Origin": ORIGIN, "X-Campus-Device": "1", "Content-Type": "application/json"}).status_code == 422
    with TestClient(create_cloud_identity_site(root, db, runtime), base_url=ORIGIN) as thief:
        thief.cookies.set(COOKIE, code)
        assert device_post(thief, "claim").status_code == 401
        assert thief.get("/tools/calendar", follow_redirects=False).status_code == 303


def test_private_tool_entry_gate_no_open_redirect_or_temporary_code(fixed, environment):
    _, _, _, _, target = fixed
    for tool in ("calendar", "timetable", "import", "tasks"):
        response = target.get("/tools/" + tool, follow_redirects=False)
        assert response.status_code == 303
        assert parse_qs(urlsplit(response.headers["location"]).query)["return_to"] == ["/tools/" + tool]
    assert target.get("/tools/login").status_code == 200  # Existing OAuth source login remains available.
    page = target.get("/tools/device-login?return_to=%2Ftools%2Fcalendar")
    assert page.status_code == 200
    assert "不需要临时确认码" in page.text and "location.replace" in page.text
    assert "localStorage" not in page.text and "sessionStorage" not in page.text
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
    for query in ("return_to=https://evil.invalid", "code=secret", "return_to=/tools/calendar&return_to=/tools/import"):
        assert target.get("/tools/device-login?" + query).status_code == 422
    assert environment[3].post("/oauth/devices/bind", json={}).status_code == 404
    assert environment[3].post(PATH + "/start", json={}).status_code == 404
    for suffix in ("?draft_id=entry_draft_a", "?source=eamis-auto&transfer_id=12345678-abcd-abcd-abcd-123456789abc"):
        response = target.get("/tools/import" + suffix, follow_redirects=False)
        assert response.status_code == 303
        returned = parse_qs(urlsplit(response.headers["location"]).query)["return_to"][0]
        assert returned == "/tools/import" + suffix
        assert target.get(response.headers["location"]).status_code == 200
    assert target.get("/tools/import?access_token=secret", follow_redirects=False).status_code == 422


def test_target_logout_retains_locator_but_does_not_restore_login(fixed):
    _, _, _, source, target = fixed
    login(source)
    bearer = grant(source)
    code = device_post(target, "start").json()["data"]["device_code"]
    assert agent_bind(source, bearer, code).status_code == 200
    assert device_post(target, "claim").status_code == 200
    session = target.get("/api/v1/auth/cloudbase/browser-session", headers={"X-Campus-Session-Read": "1"}).json()["data"]
    assert target.post("/api/v1/auth/cloudbase/logout", headers=headers(session)).status_code == 200
    assert device_post(target, "start").json()["data"]["device_code"] == code
    assert device_post(target, "claim").json()["data"]["status"] == "pending"
    assert agent_bind(source, bearer, code).status_code == 200
    assert device_post(target, "claim").status_code == 200


def test_existing_browser_account_cannot_be_silently_replaced_by_another_agent_account(fixed):
    _, _, _, source, target = fixed
    login(source)
    a_grant = grant(source)
    login(target,"fictional-b")
    assert target.get("/tools/calendar",follow_redirects=False).status_code == 303
    code = device_post(target,"start").json()["data"]["device_code"]
    assert agent_bind(source,a_grant,code).status_code == 403
    assert device_post(target,"claim").json()["data"]["status"] == "pending"
    b_grant = grant(target)
    assert agent_bind(source,b_grant,code).status_code == 200
    assert device_post(target,"claim").json()["data"]["status"] == "already_logged_in"
    assert target.get("/tools/calendar").status_code == 200


def test_device_details_is_read_only_and_does_not_create_or_claim_a_device(fixed):
    _, _, _, source, target = fixed
    empty = target.get("/tools/device")
    assert empty.status_code == 200
    assert "尚未生成设备码" in empty.text
    assert "set-cookie" not in empty.headers and not target.cookies.get(COOKIE)
    assert "/api/v1/auth/agent-device/" not in empty.text
    login(source)
    bearer = grant(source)
    code = device_post(target, "start").json()["data"]["device_code"]
    assert agent_bind(source, bearer, code).status_code == 200
    # Just viewing cannot turn an approved but unclaimed device into a login.
    pending = target.get("/tools/device")
    assert code in pending.text and "前往绑定页" in pending.text
    assert "set-cookie" not in pending.headers
    assert target.get("/tools/timetable", follow_redirects=False).status_code == 303
    assert device_post(target, "claim").status_code == 200
    before = dict(target.cookies)
    for _ in range(2):
        page = target.get("/tools/device")
        assert page.status_code == 200
        assert code in page.text and "已绑定并登录" in page.text and "复制设备码" in page.text
        assert "set-cookie" not in page.headers
        assert page.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
        for private_value in before.values():
            assert private_value not in page.text
        assert dict(target.cookies) == before
    for query in ("code=DEV-OTHER", "owner_subject_id=other", "return_to=/tools/calendar"):
        assert target.get("/tools/device?" + query).status_code == 422

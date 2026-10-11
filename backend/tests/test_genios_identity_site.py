"""HTTP + real isolated PostgreSQL; never uses production identity/keys."""
import pytest
import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.cloud_identity_site import create_cloud_identity_site
from app.core.security import SESSION_COOKIE
from app.core.cloud_identity_store import CloudIdentityStore, NATIVE_IDENTITY_RPC_URL
from app.core.errors import AppError
from app.genios_identity_site import native_configuration
from test_cloud_identity_site import environment, login, headers, ORIGIN, SECRET
from test_agent_device import device_post, grant
from test_competition_oauth import PARAMS

KEY = "fictional_dedicated_native_integration_" + "A" * 43
PATH = "/api/v1/auth/genios/"


@pytest.fixture
def native(environment):
    settings, root, db, _ = environment
    runtime = settings.model_copy(update={"cloud_oauth_competition_compat_enabled": True,
        "cloud_notice_text_pilot_enabled": True, "cloud_task_calendar_enabled": True,
        "cloud_personal_tasks_enabled": True, "cloud_persistent_auth_enabled": True,
        "cloud_personal_schedules_enabled": True, "cloud_agent_device_binding_enabled": True,
        "cloud_visitor_enabled": True, "cloud_genios_native_identity_enabled": True,
        "genios_native_integration_key": SecretStr(KEY)})
    app = create_cloud_identity_site(root, db, runtime)
    with TestClient(app, base_url=ORIGIN) as tools, TestClient(app, base_url=ORIGIN) as a, TestClient(app, base_url=ORIGIN) as b:
        yield runtime, root, db, tools, a, b


def tool(tools, code, uid="fictional-native-a", intent="lookup", confirmed=False, **extra):
    return tools.post(PATH + "onboard", json={"device_code": code, "intent": intent, "confirmed": confirmed, **extra},
        headers={"Authorization": "Bearer " + KEY, "platform_user_id": uid})


def browser(client, op, body=None, **extra):
    return client.post(PATH + op, json={} if body is None else body,
        headers={"Origin": ORIGIN, "X-Campus-Native": "1", **extra})


def current(client):
    result = client.get("/api/v1/auth/cloudbase/browser-session", headers={"X-Campus-Session-Read": "1"})
    assert result.status_code == 200, result.text
    return result.json()["data"]


def start_and_create(tools, client, uid="fictional-native-a"):
    code = device_post(client, "start").json()["data"]["device_code"]
    assert tool(tools, code, uid).json()["data"]["status"] == "first_use_confirmation"
    result = tool(tools, code, uid, "create", True)
    assert result.status_code == 200, result.text
    assert browser(client, "claim").status_code == 200
    return code, result.json()["data"], current(client)


def test_first_use_lookup_is_visible_and_readonly_then_confirmed_private_claim(native):
    _, _, db, tools, a, _ = native
    code = device_post(a, "start").json()["data"]["device_code"]
    before = db.call("__test_identity_counts__", {})
    assert browser(a, "state").json()["data"]["status"] == "identity_pending"
    result = tool(tools, code)
    assert result.status_code == 200, result.text
    assert result.json()["data"] == {"status":"first_use_confirmation","has_space":False,"created":False,"space_label":None}
    assert db.call("__test_identity_counts__", {}) == before
    assert tool(tools, code, intent="create", confirmed=False).status_code == 409
    assert browser(a, "claim").json()["data"]["status"] == "first_use_confirmation"
    assert not a.cookies.get(SESSION_COOKIE)
    created = tool(tools, code, intent="create", confirmed=True)
    assert created.json()["data"]["created"] is True
    assert "fictional-native-a" not in created.text and "workspace_ref" not in created.text
    assert browser(a, "state").json()["data"]["status"] == "browser_authorized"
    claim = browser(a, "claim")
    assert claim.json()["data"]["status"] == "bound"
    assert "HttpOnly" in claim.headers["set-cookie"] and "Secure" in claim.headers["set-cookie"]
    identity = current(a)
    assert a.get("/api/v1/schedules/current", params={"workspace_ref":identity["workspace_ref"]}).status_code == 404


def test_second_browser_and_repeated_create_reuse_exact_space(native):
    _, _, db, tools, a, b = native
    _, first, owner = start_and_create(tools, a)
    before = db.call("__test_identity_counts__", {})
    code = device_post(b, "start").json()["data"]["device_code"]
    assert tool(tools, code).json()["data"]["status"] == "existing_space"
    again = tool(tools, code, intent="create", confirmed=True).json()["data"]
    assert again["created"] is False and again["space_label"] == first["space_label"]
    assert browser(b, "claim").json()["data"]["status"] == "bound"
    assert current(b)["workspace_ref"] == owner["workspace_ref"]
    assert db.call("__test_identity_counts__", {})["owners"] == before["owners"]
    token = b.cookies.get(SESSION_COOKIE)
    assert browser(b, "claim").json()["data"]["status"] == "already_logged_in"
    assert b.cookies.get(SESSION_COOKIE) == token


def test_different_accounts_private_code_alone_and_owner_injection_cannot_enter(native):
    runtime, root, db, tools, a, b = native
    code, _, owner = start_and_create(tools, a)
    _, _, other = start_and_create(tools, b, "fictional-native-b")
    assert owner["workspace_ref"] != other["workspace_ref"]
    assert tool(tools, code, "fictional-native-b").status_code == 403
    assert tool(tools, code, owner="other").status_code == 422
    with TestClient(create_cloud_identity_site(root, db, runtime), base_url=ORIGIN) as thief:
        assert browser(thief, "claim", {"device_code":code}).status_code == 422
        assert browser(thief, "claim").status_code == 401
    assert browser(a, "claim", {"workspace_ref":other["workspace_ref"]}).status_code == 422
    assert browser(a, "state", Origin="https://other.invalid").status_code == 403
    assert a.post(PATH + "onboard", json={"device_code":code,"intent":"lookup","confirmed":False},
        headers={"Authorization":"Bearer "+KEY,"platform_user_id":"fictional-native-a"}).status_code == 403


def test_legacy_browser_requires_real_oauth_adoption_no_duplicate(native):
    _, _, db, tools, a, b = native
    old = login(a)
    code = device_post(a, "start").json()["data"]["device_code"]
    before = db.call("__test_identity_counts__", {})
    assert tool(tools, code).json()["data"]["status"] == "legacy_authorization_required"
    assert tool(tools, code, intent="create", confirmed=True).json()["data"]["status"] == "legacy_authorization_required"
    assert db.call("__test_identity_counts__", {}) == before
    bearer = grant(a)
    result = tools.post(PATH + "associate", json={"device_code":code,"intent":"bind","confirmed":True},
        headers={**bearer,"x-campus-native-key":KEY,"platform_user_id":"fictional-native-a"})
    assert result.status_code == 200, result.text
    assert result.json()["data"]["created"] is False
    new_code = device_post(b, "start").json()["data"]["device_code"]
    assert tool(tools, new_code).json()["data"]["status"] == "existing_space"
    assert tool(tools, new_code, intent="bind", confirmed=True).status_code == 200
    assert browser(b, "claim").json()["data"]["status"] == "bound"
    assert current(b)["workspace_ref"] == old["workspace_ref"]
    assert db.call("__test_identity_counts__", {})["owners"] == before["owners"]


def test_wrong_oauth_owner_cannot_adopt_or_bind_existing_native_identity(native):
    _, _, _, tools, a, b = native
    code, _, owner = start_and_create(tools, a)
    login(b, "fictional-b")
    response = tools.post(PATH + "associate", json={"device_code":code,"intent":"bind","confirmed":True},
        headers={**grant(b),"x-campus-native-key":KEY,"platform_user_id":"fictional-native-a"})
    assert response.status_code == 403
    assert current(a)["workspace_ref"] == owner["workspace_ref"]


def test_logout_requires_fresh_explicit_native_confirmation_not_legacy_resume(native):
    _, _, _, tools, a, _ = native
    code, _, owner = start_and_create(tools, a)
    assert a.post("/api/v1/auth/cloudbase/logout", json={}, headers=headers(owner)).status_code == 200
    assert not a.cookies.get(SESSION_COOKIE)
    assert browser(a, "claim").json()["data"]["status"] == "existing_space"
    assert a.post("/api/v1/auth/visitor/session", json={}, headers={"Origin":ORIGIN,"X-Campus-Visitor":"1"}).status_code == 401
    assert tool(tools, code, intent="bind", confirmed=True).status_code == 200
    assert browser(a, "claim").json()["data"]["status"] == "bound"
    assert current(a)["workspace_ref"] == owner["workspace_ref"]


def test_oauth_revocation_invalidates_native_login_and_cannot_auto_claim(native):
    _, _, _, tools, a, b = native
    code, _, owner = start_and_create(tools, a)
    bearer = grant(a)
    bcode = device_post(b, "start").json()["data"]["device_code"]
    tool(tools, bcode); tool(tools, bcode, intent="bind", confirmed=True); browser(b, "claim")
    token = bearer["Authorization"].removeprefix("Bearer ")
    assert tools.post("/oauth/revoke", json={"token":token,"client_id":PARAMS["client_id"],"client_secret":SECRET}).status_code == 200
    assert a.get("/api/v1/auth/cloudbase/browser-session", headers={"X-Campus-Session-Read":"1"}).status_code == 401
    assert browser(b, "claim").json()["data"]["status"] == "existing_space"
    assert not browser(b, "claim").headers.get("set-cookie")


def test_gate_and_dedicated_credential_fail_closed(native):
    runtime, root, db, tools, a, _ = native
    with pytest.raises(ValueError):
        native_configuration(runtime.model_copy(update={"genios_native_integration_key":SecretStr("")}))
    with pytest.raises(ValueError):
        native_configuration(runtime, KEY)
    with TestClient(create_cloud_identity_site(root, db, runtime.model_copy(update={"cloud_genios_native_identity_enabled":False})), base_url=ORIGIN) as disabled:
        assert disabled.post(PATH + "onboard", json={}).status_code == 404
    code = device_post(a, "start").json()["data"]["device_code"]
    assert tools.post(PATH + "onboard", json={"device_code":code,"intent":"lookup","confirmed":False},
        headers={"Authorization":"Bearer fictional-wrong-key","platform_user_id":"fictional-native-a"}).status_code == 401
    assert tools.get("/api/v1/auth/cloudbase/config").json()["data"]["genios_native_identity_enabled"] is True


def test_every_private_agent_read_checks_fixed_platform_identity_and_actual_oauth_owner(native):
    _, _, _, tools, a, b = native
    start_and_create(tools, a)
    start_and_create(tools, b, "fictional-native-b")
    bearer = grant(a)
    attested = {**bearer,"x-campus-native-key":KEY,"platform_user_id":"fictional-native-a"}
    for route in ("/oauth/records", "/oauth/tasks/summary", "/oauth/tasks/entries"):
        # Native production gate refuses legacy MCP/no-attestation calls. All
        # REST replacement tools must be tested before this gate is enabled.
        assert tools.get(route,headers=bearer).status_code == 401
        assert tools.get(route,headers={**attested,"platform_user_id":"fictional-native-b"}).status_code == 403
        assert tools.get(route,headers=attested).status_code == 200
    assert tools.get("/oauth/records",headers={**attested,"x-campus-native-key":"fake"}).status_code == 401
    assert tools.get("/oauth/records",headers={**attested,"Origin":ORIGIN}).status_code == 403
    assert a.get("/oauth/records",headers=attested).status_code == 403  # Browser cookie cannot attest.


def test_private_agent_writes_and_binding_cannot_use_other_native_identity(native):
    _, _, _, tools, a, b = native
    code, _, _ = start_and_create(tools, a)
    start_and_create(tools, b, "fictional-native-b")
    wrong={**grant(a),"x-campus-native-key":KEY,"platform_user_id":"fictional-native-b"}
    assert tools.post("/oauth/devices/bind",headers=wrong,json={"device_code":code,"confirm_binding":True}).status_code == 403
    assert tools.post("/oauth/tasks/entries/drafts",headers=wrong,json={"query_json":"{}"}).status_code == 403
    assert tools.post("/oauth/tasks/entries/commit",headers=wrong,json={"query_json":"{}"}).status_code == 403


def attest(tools, uid="fictional-native-a"):
    result = tools.post(PATH + "attest", headers={"Authorization":"Bearer " + KEY,"platform_user_id":uid})
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["data"]["expires_in"] == 600
    assert KEY not in result.text and uid not in result.text
    return result.json()["data"]["platform_attestation"]


def test_signed_proof_bridges_oauth_plugin_without_exposing_private_key(native):
    _, _, db, tools, a, b = native
    old = login(a)
    code = device_post(a, "start").json()["data"]["device_code"]
    assert tool(tools, code).json()["data"]["status"] == "legacy_authorization_required"
    before = db.call("__test_identity_counts__", {})
    proof = attest(tools)
    bearer = grant(a)
    checked = {**bearer,"platform_user_id":"fictional-native-a","platform_attestation":proof}
    result = tools.post(PATH + "associate", headers=checked, json={"device_code":code,"intent":"bind","confirmed":True})
    assert result.status_code == 200, result.text
    assert not result.json()["data"]["created"]
    assert current(a)["workspace_ref"] == old["workspace_ref"]
    assert db.call("__test_identity_counts__", {})["owners"] == before["owners"]
    for route in ("/oauth/records", "/oauth/tasks/summary", "/oauth/tasks/entries"):
        assert tools.get(route, headers=checked).status_code == 200
        assert tools.get(route, headers={**checked,"platform_user_id":"fictional-native-b"}).status_code == 401
    login(b, "fictional-b")
    wrong = {**checked,**grant(b)}
    assert tools.get("/oauth/records", headers=wrong).status_code == 403
    assert tools.post(PATH + "associate",headers=wrong,json={"device_code":code,"intent":"bind","confirmed":True}).status_code == 403
    assert tools.post("/oauth/tasks/entries/drafts",headers=wrong,json={"query_json":"{}"}).status_code == 403
    assert tools.post("/oauth/tasks/entries/commit",headers=wrong,json={"query_json":"{}"}).status_code == 403


def test_attestation_requires_dedicated_service_and_no_mutating_input(native):
    _, _, db, tools, a, _ = native
    before = db.call("__test_identity_counts__", {})
    headers = {"Authorization":"Bearer " + KEY,"platform_user_id":"fictional-native-a"}
    assert tools.post(PATH + "attest", headers=headers, json={}).status_code == 200
    assert tools.post(PATH + "attest", headers=headers, json={"owner":"bad"}).status_code == 422
    assert tools.post(PATH + "attest", headers=headers, params={"owner":"bad"}).status_code == 422
    assert tools.post(PATH + "attest", headers={**headers,"Authorization":"Bearer fake"}).status_code == 401
    assert tools.post(PATH + "attest", headers={**headers,"Origin":ORIGIN}).status_code == 403
    assert a.post(PATH + "attest", headers={**headers,"Cookie":"fake-cookie=value"}).status_code == 403
    proof = attest(tools)
    assert tools.post(PATH + "attest", headers={"platform_user_id":"fictional-native-a","platform_attestation":proof}).status_code == 401
    assert db.call("__test_identity_counts__", {}) == before


def test_native_rpc_transport_is_pinned_and_bounded():
    seen=[]
    def transport(request):
        assert str(request.url) == NATIVE_IDENTITY_RPC_URL
        seen.append(request)
        return httpx.Response(200,json={"ok":True,"data":{"test":True}})
    db=CloudIdentityStore("fictional-key",httpx.MockTransport(transport))
    try:
        assert db.native_identity_call("probe",{}) == {"test":True}
        with pytest.raises(AppError): db.native_identity_call("arbitrary_sql",{})
        assert len(seen)==1
    finally: db.close()

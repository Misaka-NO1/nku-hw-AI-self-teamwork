"""Closed authentication pilot. No live credentials or private UIDs in tests."""
import time

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.cloudbase_auth import _attempts
from app.core import cloudbase_auth
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import secret_hash
from app.db.database import database_connection
from app.main import app
from test_workflows import workflow_client, create_task_draft, confirm_draft  # noqa: F401

A_TOKEN = "fictional-account-a-token-not-a-credential"
B_TOKEN = "fictional-account-b-token-not-a-credential"
PG_TEST_KEY = "fictional-signing-key-for-unit-tests-only-1234567890"
PG_TEST_ISSUER = "https://fictional-env-001.ap-shanghai.tcb-api.tencentcloudapi.com/auth/v1"


def profile(uid="fictional-a"):
    return {"sub": uid, "user_id": uid, "status": "ACTIVE", "type": "external",
        "internal_user_type": "generalUser", "groups": [{"id": "user"}]}


def upstream(monkeypatch, payload, status=200, exception=None):
    class Client:
        def __init__(self, **kwargs):
            assert kwargs == {"timeout": 10, "follow_redirects": False, "trust_env": False}
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def get(self, url, headers):
            assert url == "https://fictional-env-001.api.tcloudbasegateway.com/auth/v1/user/me"
            assert headers["client_id"] == "fictional-env-001"
            if exception: raise exception
            value = payload(headers["Authorization"]) if callable(payload) else payload
            return httpx.Response(status, json=value)
    monkeypatch.setattr(cloudbase_auth.httpx, "AsyncClient", Client)


def pilot_settings():
    return Settings(cloudbase_auth_pilot_enabled=True, cloudbase_auth_env_id="fictional-env-001",
        cloudbase_auth_pilot_user_ids=["fictional-a", "fictional-b"], _env_file=None)


def pg_claims(**changes):
    return {"sub": "fictional-a", "iss": PG_TEST_ISSUER,
        "aud": "fictional-env-001", "project_id": "fictional-env-001", "exp": int(time.time()) + 300,
        "role": "authenticated", "user_type": "external", "client_type": "client_user",
        "is_system_admin": False, "is_anonymous": False, **changes}


def pg_upstream(monkeypatch, user=None, introspection_override=None, status=200):
    calls = []
    class Client:
        def __init__(self, **kwargs):
            assert kwargs == {"timeout": 10, "follow_redirects": False, "trust_env": False}
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        async def get(self, url, headers):
            calls.append(url.rsplit("/", 1)[-1])
            assert headers["client_id"] == "fictional-env-001"
            assert url.startswith("https://fictional-env-001.api.tcloudbasegateway.com/auth/v1/")
            if url.endswith("/token/introspect"):
                # Stand-in for CloudBase: invalid signatures/expiry never return
                # a validated subject, even if parsed claims look privileged-safe.
                try:
                    verified = jwt.decode(headers["Authorization"][7:], PG_TEST_KEY,
                        algorithms=["HS256"], audience="fictional-env-001", issuer=PG_TEST_ISSUER)
                    value = {"token_type": "Bearer", "client_id": "fictional-env-001", "sub": verified["sub"]}
                except jwt.PyJWTError:
                    value = {}
                if introspection_override is not None: value = introspection_override
                return httpx.Response(status, json=value)
            assert url.endswith("/user/me")
            return httpx.Response(200, json=user if user is not None else {
                "sub": "fictional-a", "user_id": "fictional-a", "status": "ACTIVE", "type": "external",
                "internal_user_type": None, "groups": []})
    monkeypatch.setattr(cloudbase_auth.httpx, "AsyncClient", Client)
    return calls


def pg_settings():
    return pilot_settings().model_copy(update={"cloudbase_auth_profile": "pg_registered"})


@pytest.mark.anyio
async def test_pg_registered_user_uses_online_validated_role_not_legacy_groups(monkeypatch):
    calls = pg_upstream(monkeypatch)
    raw = jwt.encode(pg_claims(), PG_TEST_KEY, algorithm="HS256")
    subject = await cloudbase_auth.verify_cloudbase_user(pg_settings(), "Bearer " + raw)
    assert subject == "cloudbase_pilot_" + secret_hash("fictional-env-001:fictional-a")
    assert calls == ["introspect", "me"]


@pytest.mark.anyio
@pytest.mark.parametrize("changes", [
    {"role": "service_role"}, {"role": "anon"}, {"is_system_admin": True},
    {"is_system_admin": None}, {"is_anonymous": True}, {"is_anonymous": "false"},
    {"client_type": "client_server"}, {"user_type": "internal"},
    {"project_id": "other-environment"},
])
async def test_pg_privileged_or_wrong_environment_claims_are_rejected(monkeypatch, changes):
    calls = pg_upstream(monkeypatch)
    raw = jwt.encode(pg_claims(**changes), PG_TEST_KEY, algorithm="HS256")
    with pytest.raises(AppError) as error:
        await cloudbase_auth.verify_cloudbase_user(pg_settings(), "Bearer " + raw)
    assert error.value.code == "FORBIDDEN"
    assert calls == ["introspect"]


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["signature", "expired", "issuer", "revoked", "subject", "client", "redirect"])
async def test_pg_unvalidated_jwt_never_becomes_identity(monkeypatch, failure):
    introspection = None
    if failure in {"revoked", "subject", "client"}:
        introspection = {} if failure == "revoked" else {
            "token_type": "Bearer", "client_id": "other" if failure == "client" else "fictional-env-001",
            "sub": "other" if failure == "subject" else "fictional-a"}
    calls = pg_upstream(monkeypatch, introspection_override=introspection, status=302 if failure == "redirect" else 200)
    value = pg_claims(exp=int(time.time()) - 10) if failure == "expired" else pg_claims()
    if failure == "issuer": value["iss"] = "https://other.invalid/auth/v1"
    raw = jwt.encode(value, "other-fictional-signing-key-123456789012345" if failure == "signature" else PG_TEST_KEY,
        algorithm="HS256")
    with pytest.raises(AppError):
        await cloudbase_auth.verify_cloudbase_user(pg_settings(), "Bearer " + raw)
    assert calls == ["introspect"]


@pytest.mark.anyio
@pytest.mark.parametrize("variant", ["missing", "null", "false"])
async def test_pg_verified_registered_identity_does_not_require_optional_anonymous_flag(monkeypatch, variant):
    calls = pg_upstream(monkeypatch)
    value = pg_claims()
    if variant == "missing": value.pop("is_anonymous")
    elif variant == "null": value["is_anonymous"] = None
    raw = jwt.encode(value, PG_TEST_KEY, algorithm="HS256")
    assert await cloudbase_auth.verify_cloudbase_user(pg_settings(), "Bearer " + raw)
    assert calls == ["introspect", "me"]


@pytest.mark.anyio
@pytest.mark.parametrize("changes", [{"sub": "fictional-b", "user_id": "fictional-b"},
    {"status": "DISABLED"}, {"is_system_admin": True}, {"internal_user_type": "adminUser"}])
async def test_pg_live_profile_still_binds_active_nonadmin_subject(monkeypatch, changes):
    pg_upstream(monkeypatch, user={**profile(), **changes})
    raw = jwt.encode(pg_claims(), PG_TEST_KEY, algorithm="HS256")
    with pytest.raises(AppError) as error:
        await cloudbase_auth.verify_cloudbase_user(pg_settings(), "Bearer " + raw)
    assert error.value.code == "FORBIDDEN"


@pytest.fixture
def pilot(workflow_client, monkeypatch):
    monkeypatch.setenv("CLOUDBASE_AUTH_PILOT_ENABLED", "true")
    monkeypatch.setenv("CLOUDBASE_AUTH_ENV_ID", "fictional-env-001")
    monkeypatch.setenv("CLOUDBASE_AUTH_PILOT_USER_IDS", '["fictional-a", "fictional-b"]')
    get_settings.cache_clear(); _attempts.clear()
    upstream(monkeypatch, lambda bearer: profile("fictional-a" if bearer == "Bearer " + A_TOKEN else "fictional-b"))
    yield workflow_client
    _attempts.clear(); get_settings.cache_clear()


def login(client, token):
    return client.post("/api/v1/auth/cloudbase/session", json={},
        headers={"Origin": "http://testserver", "Authorization": "Bearer " + token})


def test_pg_login_api_issues_owned_demo_session_and_logout_revokes(pilot, monkeypatch):
    monkeypatch.setenv("CLOUDBASE_AUTH_PROFILE", "pg_registered"); get_settings.cache_clear()
    calls = pg_upstream(monkeypatch)
    value = pg_claims(); value.pop("is_anonymous")
    raw = jwt.encode(value, PG_TEST_KEY, algorithm="HS256")
    response = login(pilot, raw)
    assert response.status_code == 200
    session = response.json()["data"]
    assert session["dataset_kind"] == "demo" and session["personal_uploads"] is False
    assert session["agent_paired"] is False and "session_token" not in session
    assert calls == ["introspect", "me"]
    draft = create_task_draft(pilot, session["workspace_ref"], session["csrf_token"]).json()["data"]
    receipt = confirm_draft(pilot, session["csrf_token"], draft).json()["data"]
    saved = pilot.post("/api/v1/tasks/commit", headers={"X-CSRF-Token": session["csrf_token"]},
        json={"confirmation_id": receipt["confirmation_id"], "idempotency_key": "pg-pilot-save-01"})
    assert saved.status_code == 200
    assert len(pilot.get("/api/v1/tasks", params={"workspace_ref": session["workspace_ref"]}).json()["data"]) == 1
    assert pilot.post("/api/v1/auth/cloudbase/logout", json={},
        headers={"X-CSRF-Token": session["csrf_token"]}).status_code == 200
    assert pilot.get("/api/v1/tasks", params={"workspace_ref": session["workspace_ref"]}).status_code == 401


@pytest.mark.anyio
@pytest.mark.parametrize("alter", [
    {"status": "DISABLED"}, {"sub": "unknown", "user_id": "unknown"},
    {"user_id": "other"}, {"internal_user_type": "adminUser"},
    {"groups": [{"id": "admin"}]}, {"groups": []}, {"groups": None},
    {"is_anonymous": True}, {"type": "internal"},
])
async def test_online_verification_rejects_nonapproved_or_privileged_profile(monkeypatch, alter):
    upstream(monkeypatch, {**profile(), **alter})
    with pytest.raises(AppError) as error:
        await cloudbase_auth.verify_cloudbase_user(pilot_settings(), "Bearer " + A_TOKEN)
    assert error.value.code == "FORBIDDEN"


@pytest.mark.anyio
async def test_verifier_uses_fixed_host_and_does_not_expose_profile(monkeypatch):
    upstream(monkeypatch, {**profile(), "email": "private@example.invalid"})
    subject = await cloudbase_auth.verify_cloudbase_user(pilot_settings(), "Bearer " + A_TOKEN)
    assert subject == "cloudbase_pilot_" + secret_hash("fictional-env-001:fictional-a")
    assert "fictional-a" not in subject
    for authorization in ["", "Basic abc", "Bearer uid-only", "Bearer x\nInvalid"]:
        with pytest.raises(AppError) as error:
            await cloudbase_auth.verify_cloudbase_user(pilot_settings(), authorization)
        assert error.value.code == "AUTH_REQUIRED"


@pytest.mark.anyio
async def test_rejection_diagnostics_log_only_fixed_policy_names(monkeypatch, caplog):
    value = {**profile(), "groups": [], "email": "private@example.invalid",
        "phone_number": "private-phone", "password": "private-password"}
    upstream(monkeypatch, value)
    with pytest.raises(AppError):
        await cloudbase_auth.verify_cloudbase_user(pilot_settings(), "Bearer " + A_TOKEN)
    assert "failed_checks=ordinary_groups" in caplog.text
    for forbidden in [A_TOKEN, "fictional-a", "private@example.invalid", "private-phone", "private-password"]:
        assert forbidden not in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize("status", [302, 401, 403, 500])
async def test_upstream_failure_is_fail_closed(monkeypatch, status):
    upstream(monkeypatch, {"secret": "must-not-echo"}, status)
    with pytest.raises(AppError) as error:
        await cloudbase_auth.verify_cloudbase_user(pilot_settings(), "Bearer " + A_TOKEN)
    assert "must-not-echo" not in str(error.value)
    assert error.value.status_code == (401 if status in {401, 403} else 503)


@pytest.mark.anyio
async def test_network_failure_cannot_become_demo_login(monkeypatch):
    upstream(monkeypatch, {}, exception=httpx.ConnectError("secret-upstream-detail"))
    with pytest.raises(AppError) as error:
        await cloudbase_auth.verify_cloudbase_user(pilot_settings(), "Bearer " + A_TOKEN)
    assert error.value.status_code == 503
    assert "secret-upstream-detail" not in str(error.value)


def test_two_accounts_are_isolated_logout_revokes_and_relogin_reads_back(pilot):
    a_response = login(pilot, A_TOKEN)
    assert a_response.status_code == 200
    a = a_response.json()["data"]
    assert a["dataset_kind"] == "demo" and a["personal_uploads"] is False and a["agent_paired"] is False
    assert "HttpOnly" in a_response.headers["set-cookie"]
    assert "SameSite=strict" in a_response.headers["set-cookie"]
    old_a_cookie = pilot.cookies.get("campus_session")
    draft = create_task_draft(pilot, a["workspace_ref"], a["csrf_token"]).json()["data"]
    receipt = confirm_draft(pilot, a["csrf_token"], draft).json()["data"]
    saved = pilot.post("/api/v1/tasks/commit", headers={"X-CSRF-Token": a["csrf_token"]},
        json={"confirmation_id": receipt["confirmation_id"], "idempotency_key": "auth-pilot-save-01"})
    assert saved.status_code == 200
    a_task_id = saved.json()["data"]["task_id"]
    b = login(pilot, B_TOKEN).json()["data"]
    assert a["workspace_ref"] != b["workspace_ref"]
    assert pilot.get("/api/v1/tasks", params={"workspace_ref": b["workspace_ref"]}).json()["data"] == []
    assert pilot.get("/api/v1/tasks", params={"workspace_ref": a["workspace_ref"]}).status_code == 404
    assert pilot.get(f"/api/v1/drafts/{draft['draft_id']}").status_code == 404
    with TestClient(app) as stale:
        stale.cookies.set("campus_session", old_a_cookie)
        assert stale.get("/api/v1/tasks", params={"workspace_ref": a["workspace_ref"]}).status_code == 401
    assert pilot.post("/api/v1/auth/cloudbase/logout", json={}).status_code == 403
    assert pilot.post("/api/v1/auth/cloudbase/logout", json={}, headers={"X-CSRF-Token": b["csrf_token"]}).status_code == 200
    assert pilot.get("/api/v1/tasks", params={"workspace_ref": b["workspace_ref"]}).status_code == 401
    with TestClient(app) as restarted:
        again = login(restarted, A_TOKEN).json()["data"]
        assert again["workspace_ref"] == a["workspace_ref"]
        tasks = restarted.get("/api/v1/tasks", params={"workspace_ref": again["workspace_ref"]}).json()["data"]
        assert [task["task_id"] for task in tasks] == [a_task_id]
    with database_connection(get_settings()) as db:
        dump = "\n".join(db.iterdump())
        assert A_TOKEN not in dump and B_TOKEN not in dump
        assert "fictional-a" not in dump and "fictional-b" not in dump


def test_wrong_origin_rate_limit_and_disabling_pilot_invalidate_login(pilot, monkeypatch):
    denied = pilot.post("/api/v1/auth/cloudbase/session", headers={"Origin": "https://evil.invalid", "Authorization": "Bearer " + A_TOKEN})
    assert denied.status_code == 403
    first = login(pilot, A_TOKEN).json()["data"]
    for _ in range(9):
        assert login(pilot, A_TOKEN).status_code == 200
    assert login(pilot, A_TOKEN).status_code == 429
    monkeypatch.setenv("CLOUDBASE_AUTH_PILOT_ENABLED", "false"); get_settings.cache_clear()
    assert pilot.get("/api/v1/tasks", params={"workspace_ref": first["workspace_ref"]}).status_code == 401
    assert login(pilot, A_TOKEN).status_code == 403


def test_expired_session_and_real_data_remain_closed(pilot):
    session = login(pilot, A_TOKEN).json()["data"]
    from app.core.demo import load_fixture
    notice = load_fixture("notice-event.demo.json").copy(); notice["title"] = "Not an approved fictional fixture"
    response = pilot.post("/api/v1/tasks/drafts", headers={"X-CSRF-Token": session["csrf_token"], "Idempotency-Key": "auth-real-rejected"},
        json={"workspace_ref": session["workspace_ref"], "notice": notice})
    assert response.status_code == 403
    with database_connection(get_settings()) as db:
        db.execute("UPDATE browser_sessions SET expires_at=?", (int(time.time()) - 1,)); db.commit()
    assert pilot.get("/api/v1/tasks", params={"workspace_ref": session["workspace_ref"]}).status_code == 401

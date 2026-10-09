"""Synthetic client credentials only. No live school or CloudBase calls."""
import base64
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, ValidationError
from pydantic import SecretStr

from app.core import oauth_local as oauth
from app.core.cloudbase_auth import issue_pilot_session
from app.core.config import Settings
from app.core.security import secret_hash
from app.db.database import database_connection, initialize_database
from app.oauth_pilot_site import create_oauth_pilot

ROOT = Path(__file__).parents[2]
FIXTURE = json.loads((ROOT / "fixtures/oauth-pilot.demo.json").read_text(encoding="utf-8"))
SECRET = "fictional-test-only-" + "x" * 48


@pytest.fixture
def pilot(tmp_path):
    settings = Settings(_env_file=None, app_env="test", app_origin="http://testserver",
        database_url="sqlite:///" + (tmp_path / "oauth.db").as_posix(),
        cloudbase_auth_pilot_enabled=True, cloudbase_auth_env_id="fictional-env-001",
        cloudbase_auth_pilot_user_ids=["fictional-a", "fictional-b"],
        agent_pairing_local_enabled=True, agent_pairing_audience="test-school-agent",
        oauth_local_enabled=True, oauth_client_id="test-school-agent",
        oauth_client_secret_hash=SecretStr(secret_hash(SECRET)),
        oauth_redirect_uri=FIXTURE["authorize"]["redirect_uri"])
    initialize_database(settings)
    users = {uid: issue_pilot_session(settings, "cloudbase_pilot_" + secret_hash(settings.cloudbase_auth_env_id + ":" + uid))
             for uid in settings.cloudbase_auth_pilot_user_ids}
    with TestClient(create_oauth_pilot(settings)) as client:
        yield settings, users, client


def login(client, users, uid="fictional-a"):
    client.cookies.set("campus_session", users[uid]["session_token"])


def authorize(pilot, uid="fictional-a", scope="demo:read demo:draft"):
    _, users, client = pilot
    login(client, users, uid)
    response = client.get("/authorize", params={**FIXTURE["authorize"], "scope": scope})
    assert response.status_code == 200
    assert "不能替你确认或保存" in response.text
    transaction = re.search(r'name="transaction" value="([^"]+)"', response.text)[1]
    response = client.post("/approve", data={"transaction": transaction, "decision": "allow"},
        headers={"Origin": "http://testserver"}, follow_redirects=False)
    assert response.status_code == 303
    query = parse_qs(urlsplit(response.headers["Location"]).query)
    assert query["state"] == [FIXTURE["authorize"]["state"]]
    return query["code"][0]


def exchange(client, authorization_code, **changes):
    return client.post("/token", json={"client_id": "test-school-agent", "client_secret": SECRET,
        "grant_type": "authorization_code", "code": authorization_code,
        "redirect_uri": FIXTURE["authorize"]["redirect_uri"],
        "code_verifier": FIXTURE["public_pkce_example_verifier"], **changes})


def validator(name):
    schema = json.loads((ROOT / "contracts/api.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator({"$defs": schema["$defs"], "$ref": "#/$defs/" + name})


def test_authorization_consent_exchange_owned_read_and_draft(pilot):
    settings, users, client = pilot
    response = exchange(client, authorize(pilot))
    assert response.status_code == 200
    validator("OAuthPilotTokenResponse").validate(response.json())
    token = response.json()["access_token"]
    bearer = {"Authorization": "Bearer " + token}
    records = client.get("/records", headers=bearer)
    validator("ApiEnvelope").validate(records.json())
    assert records.json()["data"] == {"dataset_kind": "demo", "personal_uploads": False, "schedule": None, "tasks": []}
    draft = client.post("/task-drafts", json=FIXTURE["draft"], headers=bearer)
    assert draft.status_code == 200 and draft.json()["data"]["status"] == "draft"
    assert client.post("/task-drafts", json=FIXTURE["draft"], headers=bearer).json()["data"] == draft.json()["data"]
    assert client.get("/records", headers=bearer).json()["data"]["tasks"] == []
    assert client.post("/confirmations", json={}, headers=bearer).status_code == 404
    assert client.post("/commit", json={}, headers=bearer).status_code == 404
    # A grant cannot be overridden with B's workspace / caller-provided identity.
    assert client.get("/records", params={"workspace_ref": users["fictional-b"]["workspace_ref"]}, headers=bearer).status_code == 401
    assert client.post("/task-drafts", json={**FIXTURE["draft"], "user_id": "fictional-b"}, headers=bearer).status_code == 400
    with database_connection(settings) as db:
        dump = "\n".join(db.iterdump())
        owner = db.execute("SELECT owner_subject_id FROM drafts WHERE draft_id=?", (draft.json()["data"]["draft_id"],)).fetchone()
    assert owner[0] == "cloudbase_pilot_" + secret_hash(settings.cloudbase_auth_env_id + ":fictional-a")
    assert SECRET not in dump and token not in dump
    assert SECRET not in repr(settings)


@pytest.mark.parametrize("change", FIXTURE["invalid_authorize"])
def test_invalid_authorize_never_redirects_or_creates_transaction(pilot, change):
    settings, users, client = pilot
    login(client, users)
    response = client.get("/authorize", params={**FIXTURE["authorize"], **change})
    assert response.status_code == 400 and "Location" not in response.headers
    validator("OAuthPilotError").validate(response.json())
    with database_connection(settings) as db:
        assert db.execute("SELECT count(*) FROM local_oauth_requests").fetchone()[0] == 0


@pytest.mark.parametrize("change", [
    {"client_secret": "invalid"}, {"client_id": "another-client"},
    {"redirect_uri": "https://attacker.example.invalid/callback"},
    {"code_verifier": "z" * 43}, {"grant_type": "refresh_token"},
    {"user_id": "fictional-b"}, {"code": "unknown"},
])
def test_token_errors_are_sanitized_and_do_not_consume_valid_code(pilot, change):
    _, _, client = pilot
    code = authorize(pilot)
    failed = exchange(client, code, **change)
    assert failed.status_code in {400, 401}
    validator("OAuthPilotError").validate(failed.json())
    assert SECRET not in failed.text and code not in failed.text
    assert exchange(client, code).status_code == 200
    assert exchange(client, code).json() == {"error": "invalid_grant"}


def test_basic_auth_form_and_reject_two_auth_methods(pilot):
    _, _, client = pilot
    code = authorize(pilot)
    basic = {"Authorization": "Basic " + base64.b64encode(("test-school-agent:" + SECRET).encode()).decode()}
    data = {"grant_type": "authorization_code", "code": code,
        "redirect_uri": FIXTURE["authorize"]["redirect_uri"],
        "code_verifier": FIXTURE["public_pkce_example_verifier"]}
    assert client.post("/token", data={**data, "client_secret": SECRET}, headers=basic).status_code == 401
    response = client.post("/token", data=data, headers=basic)
    assert response.status_code == 200
    assert "refresh_token" not in response.json()


@pytest.mark.parametrize("mutation", ["logout", "rotate", "removed", "revoke", "expired", "restart"])
def test_live_revocation_and_restart(pilot, mutation):
    settings, users, client = pilot
    token = exchange(client, authorize(pilot)).json()["access_token"]
    if mutation == "rotate":
        subject = "cloudbase_pilot_" + secret_hash(settings.cloudbase_auth_env_id + ":fictional-a")
        issue_pilot_session(settings, subject, users["fictional-a"]["session_token"])
    elif mutation == "removed":
        settings.cloudbase_auth_pilot_user_ids = ["fictional-b"]
    elif mutation == "revoke":
        response = client.post("/revoke", json={"client_id": "test-school-agent", "client_secret": SECRET, "token": token})
        assert response.status_code == 200
    elif mutation == "restart":
        oauth.initialize(settings)
        with TestClient(create_oauth_pilot(settings)) as next_client:
            assert next_client.get("/records", headers={"Authorization": "Bearer " + token}).status_code == 200
        return
    else:
        with database_connection(settings) as db:
            db.execute("DELETE FROM browser_sessions" if mutation == "logout" else "UPDATE local_agent_grants SET expires_at=1")
            db.commit()
    assert client.get("/records", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_browser_consent_is_account_bound_one_time_and_requires_origin(pilot):
    _, users, client = pilot
    login(client, users)
    response = client.get("/authorize", params=FIXTURE["authorize"])
    nonce = re.search(r'name="transaction" value="([^"]+)"', response.text)[1]
    body = {"transaction": nonce, "decision": "allow"}
    login(client, users, "fictional-b")
    assert client.post("/approve", data=body, headers={"Origin": "http://testserver"}).status_code == 403
    login(client, users)
    assert client.post("/approve", data=body).status_code == 403
    denied = client.post("/approve", data={**body, "decision": "deny"}, headers={"Origin": "http://testserver"}, follow_redirects=False)
    assert denied.status_code == 303 and "error=access_denied" in denied.headers["Location"]
    assert client.post("/approve", data=body, headers={"Origin": "http://testserver"}).status_code == 403


def test_atomic_code_consumption(pilot):
    settings, _, _ = pilot
    code = authorize(pilot)
    params = {"grant_type": "authorization_code", "code": code, "redirect_uri": settings.oauth_redirect_uri,
              "code_verifier": FIXTURE["public_pkce_example_verifier"]}
    def redeem(_):
        try:
            return oauth.exchange(settings, params)
        except oauth.OAuthError:
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sum(result is not None for result in executor.map(redeem, range(2))) == 1


@pytest.mark.parametrize("mutation", ["code", "consent", "logout_before_exchange", "callback_changed"])
def test_expired_transactions_and_configuration_changes_fail_closed(pilot, mutation):
    settings, users, client = pilot
    if mutation == "consent":
        login(client, users)
        response = client.get("/authorize", params=FIXTURE["authorize"])
        nonce = re.search(r'name="transaction" value="([^"]+)"', response.text)[1]
        with database_connection(settings) as db:
            db.execute("UPDATE local_oauth_requests SET expires_at=1")
            db.commit()
        response = client.post("/approve", data={"transaction": nonce, "decision": "allow"},
            headers={"Origin": "http://testserver"}, follow_redirects=False)
        assert response.status_code == 403 and "Location" not in response.headers
        return
    code = authorize(pilot)
    with database_connection(settings) as db:
        if mutation == "code":
            db.execute("UPDATE local_oauth_codes SET expires_at=1")
        elif mutation == "logout_before_exchange":
            db.execute("DELETE FROM browser_sessions")
        db.commit()
    if mutation == "callback_changed":
        settings.oauth_redirect_uri = "https://new.example.invalid/callback"
    assert exchange(client, code).json() == {"error": "invalid_grant"}


def test_missing_pkce_duplicate_query_and_rate_limit(pilot):
    _, users, client = pilot
    login(client, users)
    no_pkce = {key: value for key, value in FIXTURE["authorize"].items() if key != "code_challenge"}
    assert client.get("/authorize", params=no_pkce).status_code == 400
    repeated = list(FIXTURE["authorize"].items()) + [("client_id", "another-client")]
    assert client.get("/authorize", params=repeated).status_code == 400
    responses = [client.post("/token", json={}) for _ in range(60)]
    assert responses[-1].status_code == 429
    assert responses[-1].headers["Cache-Control"] == "no-store"


def test_runtime_kill_switch_blocks_existing_access_token(pilot):
    settings, _, client = pilot
    token = exchange(client, authorize(pilot)).json()["access_token"]
    settings.oauth_local_enabled = False
    assert client.get("/records", headers={"Authorization": "Bearer " + token}).status_code == 503


def test_read_scope_body_limits_duplicates_and_security_headers(pilot):
    _, _, client = pilot
    token = exchange(client, authorize(pilot, scope="demo:read")).json()["access_token"]
    assert client.post("/task-drafts", json=FIXTURE["draft"], headers={"Authorization": "Bearer " + token}).status_code == 403
    assert client.get("/records", params={"access_token": token}).status_code == 401
    assert client.post("/token", content='{"client_id":"a","client_id":"b"}', headers={"Content-Type": "application/json"}).status_code == 400
    assert client.post("/token", content="x" * 8193, headers={"Content-Type": "application/json"}).status_code == 400
    response = client.get("/authorize", params=FIXTURE["authorize"])
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    client.cookies.clear()
    assert client.get("/authorize", params=FIXTURE["authorize"]).status_code == 401


@pytest.mark.parametrize("change", [
    {"oauth_local_enabled": False}, {"app_env": "production"}, {"app_env": "staging"},
    {"allow_personal_uploads": True}, {"oauth_client_id": "not-the-audience"},
    {"oauth_redirect_uri": "https://school.example.invalid/oauth/callback?next=bad"},
    {"oauth_client_secret_hash": SecretStr("invalid")},
])
def test_deployment_fails_closed(pilot, change):
    from app.core.errors import AppError
    settings, _, _ = pilot
    with pytest.raises((oauth.OAuthError, AppError)):
        create_oauth_pilot(settings.model_copy(update=change))


def test_contract_examples_and_no_mcp_registration():
    from app.main import app
    from app.mcp.domains import DESCRIPTIONS
    validator("OAuthPilotAuthorizationRequest").validate(FIXTURE["authorize"])
    validator("OAuthPilotTaskDraftRequest").validate(FIXTURE["draft"])
    for change in FIXTURE["invalid_authorize"]:
        if "client_id" not in change and "redirect_uri" not in change:
            with pytest.raises(ValidationError):
                validator("OAuthPilotAuthorizationRequest").validate({**FIXTURE["authorize"], **change})
    assert not any("oauth" in path for path in app.openapi()["paths"])
    assert not any("oauth" in tool or "pair" in tool for tool in DESCRIPTIONS)

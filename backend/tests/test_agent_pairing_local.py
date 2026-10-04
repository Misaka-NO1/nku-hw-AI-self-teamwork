"""Internal prototype tests use fictional identities, never live passwords/tokens."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from pydantic import SecretStr
from starlette.requests import Request

from app.core import agent_pairing_local as pairing
from app.core.cloudbase_auth import issue_pilot_session
from app.core.config import Settings
from app.core.demo import load_fixture
from app.core.domain_adapter import public_principal
from app.core.errors import AppError
from app.core.security import Principal, resolve_workspace, secret_hash
from app.db.database import database_connection, initialize_database
from app.domains.tasks import service


@pytest.fixture
def state(tmp_path):
    settings = Settings(app_env="test", app_origin="http://testserver", _env_file=None,
        database_url="sqlite:///" + (tmp_path / "pairing.db").as_posix(),
        cloudbase_auth_pilot_enabled=True, cloudbase_auth_env_id="fictional-env-001",
        cloudbase_auth_pilot_user_ids=["fictional-a", "fictional-b"],
        agent_pairing_local_enabled=True, agent_pairing_audience="test-school-agent")
    initialize_database(settings)
    pairing.initialize_pairing_prototype(settings)
    users = {}
    for uid in settings.cloudbase_auth_pilot_user_ids:
        subject = "cloudbase_pilot_" + secret_hash(settings.cloudbase_auth_env_id + ":" + uid)
        login = issue_pilot_session(settings, subject)
        headers = [(b"origin", b"http://testserver"),
            (b"cookie", ("campus_session=" + login["session_token"]).encode()),
            (b"x-csrf-token", login["csrf_token"].encode())]
        request = Request({"type": "http", "method": "POST", "path": "/", "headers": headers})
        principal = Principal(subject, "browser_user", frozenset({"demo:read", "demo:draft", "demo:commit"}), "test")
        users[uid] = (request, login, principal)
    integration = Principal(settings.agent_pairing_audience, "mcp_service",
        frozenset({"integration:pair"}), "server-integration")
    return settings, users, integration


def grant(state, uid="fictional-a", scopes=pairing.SAFE_SCOPES):
    settings, users, integration = state
    request, login, _ = users[uid]
    code = pairing.issue_pairing_code(request, settings, login["workspace_ref"], scopes)
    return code, pairing.redeem_pairing_code(settings, integration, code.secret)


def test_owned_read_and_draft_never_confirm_or_commit(state):
    settings, users, integration = state
    _, token = grant(state)
    records = pairing.read_paired_records(settings, integration, token.secret)
    assert records == {"dataset_kind": "demo", "personal_uploads": False, "schedule": None, "tasks": []}
    draft = pairing.create_paired_task_draft(settings, integration, token.secret,
        load_fixture("notice-event.demo.json"), "pair-draft-001")
    assert draft["status"] == "draft"
    assert pairing.create_paired_task_draft(settings, integration, token.secret,
        load_fixture("notice-event.demo.json"), "pair-draft-001") == draft
    assert pairing.read_paired_records(settings, integration, token.secret)["tasks"] == []
    agent, workspace = pairing.resolve_agent_grant(settings, integration, token.secret, "demo:draft")
    assert agent.kind == "agent_grant" and "demo:commit" not in agent.scopes
    with pytest.raises(AppError, match="Only the browser owner"):
        service.create_confirmation(settings, agent, draft["draft_id"], draft["revision"], draft["payload_hash"], "pair-confirm-01")
    with pytest.raises(AppError, match="Only the browser owner"):
        service.create_confirmation(settings, replace(agent, scopes=agent.scopes | {"demo:commit"}),
            draft["draft_id"], draft["revision"], draft["payload_hash"], "pair-confirm-02")
    owner = users["fictional-a"][2]
    confirmation = service.create_confirmation(settings, owner, draft["draft_id"], draft["revision"], draft["payload_hash"], "owner-confirm-01")
    with pytest.raises(AppError, match="Only the browser owner"):
        service.commit_draft(settings, agent, "task", confirmation["confirmation_id"], "pair-commit-001")
    saved = service.commit_draft(settings, owner, "task", confirmation["confirmation_id"], "owner-commit-01")
    assert pairing.read_paired_records(settings, integration, token.secret)["tasks"][0]["task_id"] == saved["task_id"]
    _, token_b = grant(state, "fictional-b")
    assert pairing.read_paired_records(settings, integration, token_b.secret)["tasks"] == []
    with pytest.raises(AppError) as exc:
        resolve_workspace(users["fictional-b"][2], workspace, "demo:read", settings=settings)
    assert exc.value.status_code == 404


def test_ticket_consumed_atomically_and_cannot_replay(state):
    settings, users, integration = state
    request, login, _ = users["fictional-a"]
    code = pairing.issue_pairing_code(request, settings, login["workspace_ref"], pairing.SAFE_SCOPES)
    def redeem(_):
        try:
            return pairing.redeem_pairing_code(settings, integration, code.secret)
        except AppError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(redeem, range(2)))
    assert sum(result is not None for result in results) == 1
    with pytest.raises(AppError):
        pairing.redeem_pairing_code(settings, integration, code.secret)


@pytest.mark.parametrize("change", [
    {"agent_pairing_local_enabled": False}, {"app_env": "production"}, {"app_env": "staging"},
    {"allow_personal_uploads": True}, {"auth_mode": "trusted_binding"},
    {"cloudbase_auth_pilot_enabled": False}, {"agent_pairing_audience": ""},
])
def test_prototype_closed_outside_explicit_local_fixture_test(state, change):
    settings, _, _ = state
    with pytest.raises(AppError):
        pairing.initialize_pairing_prototype(settings.model_copy(update=change))


@pytest.mark.parametrize("integration_change", [
    {"subject_id": "another-agent"}, {"kind": "browser_user"},
    {"scopes": frozenset({"public:read"})}, {"trusted_origin": "SYS_USERID"},
])
def test_shared_bearer_or_caller_supplied_platform_identity_not_enough(state, integration_change):
    settings, _, integration = state
    code, token = grant(state)
    with pytest.raises(AppError):
        pairing.resolve_agent_grant(settings, replace(integration, **integration_change), token.secret, "demo:read")
    with pytest.raises(AppError):
        pairing.resolve_agent_grant(settings, public_principal(mcp=True), token.secret, "demo:read")
    assert code.secret.get_secret_value() != token.secret.get_secret_value()


def test_read_only_grant_cannot_draft_and_non_fixture_draft_rejected(state):
    settings, _, integration = state
    _, read_token = grant(state, scopes=frozenset({"demo:read"}))
    with pytest.raises(AppError):
        pairing.create_paired_task_draft(settings, integration, read_token.secret,
            load_fixture("notice-event.demo.json"), "read-draft-01")
    _, token = grant(state)
    notice = {**load_fixture("notice-event.demo.json"), "title": "not-an-approved-fixture"}
    with pytest.raises(AppError) as exc:
        pairing.create_paired_task_draft(settings, integration, token.secret, notice, "bad-draft-001")
    assert exc.value.code == "DEMO_ONLY"


def test_reissue_logout_revocation_and_private_storage(state):
    settings, users, integration = state
    code, old = grant(state)
    request, login, owner = users["fictional-a"]
    next_code, token = grant(state)
    with pytest.raises(AppError):
        pairing.resolve_agent_grant(settings, integration, old.secret, "demo:read")
    with database_connection(settings) as db:
        dump = "\n".join(db.iterdump())
    for raw in (code.secret.get_secret_value(), old.secret.get_secret_value(), token.secret.get_secret_value(),
                next_code.secret.get_secret_value(), login["session_token"], "fictional-a", "fictional-b"):
        assert raw not in dump
    assert token.secret.get_secret_value() not in repr(token)
    pairing.revoke_pairing(request, settings)
    with pytest.raises(AppError):
        pairing.resolve_agent_grant(settings, integration, token.secret, "demo:read")
    _, token = grant(state)
    issue_pilot_session(settings, owner.subject_id, login["session_token"])
    with pytest.raises(AppError):
        pairing.resolve_agent_grant(settings, integration, token.secret, "demo:read")


@pytest.mark.parametrize("mutation", ["grant_expiry", "session_expiry", "workspace_expiry", "unapproved_uid", "wrong_fixture", "logout"])
def test_live_gates_rechecked_on_every_call(state, mutation):
    settings, users, integration = state
    _, token = grant(state)
    _, login, _ = users["fictional-a"]
    with database_connection(settings) as db:
        if mutation == "grant_expiry": db.execute("UPDATE local_agent_grants SET expires_at=1")
        elif mutation == "session_expiry": db.execute("UPDATE browser_sessions SET expires_at=1")
        elif mutation == "workspace_expiry": db.execute("UPDATE workspaces SET expires_at=1")
        elif mutation == "wrong_fixture": db.execute("UPDATE workspaces SET fixture_set_id='not-demo'")
        elif mutation == "logout": db.execute("DELETE FROM browser_sessions WHERE token_hash=?", (secret_hash(login["session_token"]),))
        db.commit()
    if mutation == "unapproved_uid": settings = settings.model_copy(update={"cloudbase_auth_pilot_user_ids": ["fictional-b"]})
    with pytest.raises(AppError):
        pairing.resolve_agent_grant(settings, integration, token.secret, "demo:read")


def test_code_expiry_and_scope_escalation_rejected(state):
    settings, users, integration = state
    request, login, _ = users["fictional-a"]
    with pytest.raises(AppError):
        pairing.issue_pairing_code(request, settings, login["workspace_ref"], frozenset({"demo:read", "demo:commit"}))
    code = pairing.issue_pairing_code(request, settings, login["workspace_ref"], pairing.SAFE_SCOPES)
    with database_connection(settings) as db:
        db.execute("UPDATE local_pairing_tickets SET expires_at=1")
        db.commit()
    with pytest.raises(AppError):
        pairing.redeem_pairing_code(settings, integration, code.secret)
    _, token = grant(state)
    with pytest.raises(AppError):
        pairing.resolve_agent_grant(settings, integration, token.secret, "demo:commit")
    with pytest.raises(AppError):
        pairing.resolve_agent_grant(settings, integration, SecretStr("wrong-random-token"), "demo:read")


@pytest.mark.parametrize("case", ["no_csrf", "wrong_origin", "another_workspace", "public_workspace"])
def test_pairing_requires_browser_approval_and_owned_workspace(state, case):
    settings, users, _ = state
    request, login, _ = users["fictional-a"]
    workspace = login["workspace_ref"]
    if case == "another_workspace": workspace = users["fictional-b"][1]["workspace_ref"]
    elif case == "public_workspace": workspace = "demo-workspace-01"
    else:
        headers = list(request.scope["headers"])
        if case == "no_csrf": headers = [(key, value) for key, value in headers if key != b"x-csrf-token"]
        else: headers = [(key, b"http://foreign.example" if key == b"origin" else value) for key, value in headers]
        request = Request({**request.scope, "headers": headers})
    with pytest.raises(AppError):
        pairing.issue_pairing_code(request, settings, workspace, pairing.SAFE_SCOPES)


def test_prototype_not_registered_and_restart_retains_hashed_grant(state):
    from app.main import app
    from app.mcp.domains import DESCRIPTIONS
    settings, _, integration = state
    _, token = grant(state)
    initialize_database(settings)
    pairing.initialize_pairing_prototype(settings)
    assert pairing.read_paired_records(settings, integration, token.secret)["tasks"] == []
    assert not any("pair" in path for path in app.openapi()["paths"])
    assert not any("pair" in name for name in DESCRIPTIONS)

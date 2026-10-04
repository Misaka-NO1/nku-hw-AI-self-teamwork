"""Internal local pairing prototype, NOT a published API or trusted school binding.

No route/tool imports this module. A future adapter must follow contract section 7,
use a server-authenticated integration, and keep capabilities out of model text,
URLs, logs and ordinary SYS_USERID variables. Only fictional fixtures are allowed.
"""
import json
import re
import time
from dataclasses import dataclass
from secrets import token_urlsafe

from fastapi import Request
from pydantic import SecretStr

from app.core.cloudbase_auth import require_pilot
from app.core.config import Settings
from app.core.demo import FIXTURE_SET_ID
from app.core.errors import AppError
from app.core.security import (
    SESSION_COOKIE, Principal, require_idempotency_key, resolve_browser_principal,
    resolve_workspace, secret_hash,
)
from app.db.database import database_connection
from app.domains.tasks import service

SAFE_SCOPES = frozenset({"demo:read", "demo:draft"})


@dataclass(frozen=True)
class PairingSecret:
    secret: SecretStr
    expires_at: int


def _gate(settings: Settings) -> None:
    require_pilot(settings)
    if (not settings.agent_pairing_local_enabled or settings.app_env not in {"test", "development"}
            or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", settings.agent_pairing_audience)):
        raise AppError(403, "FORBIDDEN", "Local pairing prototype is disabled")


def initialize_pairing_prototype(settings: Settings) -> None:
    """Explicit opt-in, additive test-only storage; never migrate production here."""
    _gate(settings)
    with database_connection(settings) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS local_pairing_tickets (
            code_hash TEXT PRIMARY KEY, owner_subject_id TEXT NOT NULL,
            workspace_ref TEXT NOT NULL REFERENCES workspaces(workspace_ref) ON DELETE CASCADE,
            source_session_hash TEXT NOT NULL, audience TEXT NOT NULL,
            scopes_json TEXT NOT NULL, expires_at INTEGER NOT NULL,
            grant_expires_at INTEGER NOT NULL, used_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS local_agent_grants (
            token_hash TEXT PRIMARY KEY, owner_subject_id TEXT NOT NULL,
            workspace_ref TEXT NOT NULL REFERENCES workspaces(workspace_ref) ON DELETE CASCADE,
            source_session_hash TEXT NOT NULL, audience TEXT NOT NULL,
            scopes_json TEXT NOT NULL, expires_at INTEGER NOT NULL
        );
        """)


def _browser(request: Request, settings: Settings):
    _gate(settings)
    if request.headers.get("Origin", "").rstrip("/") != settings.app_origin.rstrip("/") or not settings.app_origin:
        raise AppError(403, "FORBIDDEN", "Same-origin approval is required")
    principal = resolve_browser_principal(request, require_csrf=True, settings=settings)
    if not principal.subject_id.startswith("cloudbase_pilot_"):
        raise AppError(403, "IDENTITY_NOT_VERIFIED", "Verified CloudBase pilot login required")
    return principal, secret_hash(request.cookies[SESSION_COOKIE])


def issue_pairing_code(request: Request, settings: Settings, workspace_ref: str,
                       scopes: frozenset[str]) -> PairingSecret:
    principal, session_hash = _browser(request, settings)
    if not scopes or not scopes <= SAFE_SCOPES or "demo:read" not in scopes:
        raise AppError(403, "FORBIDDEN", "Pairing allows read and optional draft only")
    workspace = resolve_workspace(principal, workspace_ref, "demo:read", settings=settings)
    if workspace["fixture_set_id"] != FIXTURE_SET_ID:
        raise AppError(403, "DEMO_ONLY", "Only the fictional workspace may be paired")
    now, raw = int(time.time()), token_urlsafe(32)
    with database_connection(settings) as db:
        db.execute("BEGIN IMMEDIATE")
        session = db.execute("SELECT expires_at FROM browser_sessions WHERE token_hash=? AND subject_id=?",
            (session_hash, principal.subject_id)).fetchone()
        if not session or session["expires_at"] <= now:
            raise AppError(401, "AUTH_REQUIRED", "Active browser session required")
        code_expiry = min(now + 120, session["expires_at"], workspace["expires_at"])
        grant_expiry = min(now + 600, session["expires_at"], workspace["expires_at"])
        # Reissuing invalidates every previous ticket/grant for this browser session.
        for table in ("local_pairing_tickets", "local_agent_grants"):
            db.execute(f"DELETE FROM {table} WHERE source_session_hash=?", (session_hash,))
        db.execute("INSERT INTO local_pairing_tickets VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (secret_hash(raw), principal.subject_id, workspace_ref, session_hash,
             settings.agent_pairing_audience, json.dumps(sorted(scopes)), code_expiry, grant_expiry))
        db.commit()
    return PairingSecret(SecretStr(raw), code_expiry)


def _integration(settings: Settings, integration: Principal) -> None:
    _gate(settings)
    if (integration.kind != "mcp_service" or integration.subject_id != settings.agent_pairing_audience
            or integration.trusted_origin != "server-integration"
            or "integration:pair" not in integration.scopes):
        raise AppError(403, "FORBIDDEN", "Approved integration is required")


def _live(db, row, settings: Settings, now: int) -> None:
    allowed = {"cloudbase_pilot_" + secret_hash(settings.cloudbase_auth_env_id + ":" + uid)
               for uid in settings.cloudbase_auth_pilot_user_ids}
    session = db.execute("SELECT expires_at FROM browser_sessions WHERE token_hash=? AND subject_id=?",
        (row["source_session_hash"], row["owner_subject_id"])).fetchone()
    workspace = db.execute("SELECT expires_at, fixture_set_id FROM workspaces WHERE workspace_ref=? AND owner_subject_id=?",
        (row["workspace_ref"], row["owner_subject_id"])).fetchone()
    if (row["expires_at"] <= now or row["owner_subject_id"] not in allowed or not session
            or session["expires_at"] <= now or not workspace or workspace["expires_at"] <= now
            or workspace["fixture_set_id"] != FIXTURE_SET_ID):
        raise AppError(401, "AUTH_REQUIRED", "Pairing is invalid or expired")


def redeem_pairing_code(settings: Settings, integration: Principal, code: SecretStr) -> PairingSecret:
    _integration(settings, integration)
    now, raw = int(time.time()), token_urlsafe(32)
    with database_connection(settings) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM local_pairing_tickets WHERE code_hash=? AND audience=? AND used_at IS NULL",
            (secret_hash(code.get_secret_value()), integration.subject_id)).fetchone()
        if not row:
            raise AppError(401, "AUTH_REQUIRED", "Pairing is invalid or expired")
        _live(db, row, settings, now)
        db.execute("UPDATE local_pairing_tickets SET used_at=? WHERE code_hash=? AND used_at IS NULL",
            (now, row["code_hash"]))
        db.execute("INSERT INTO local_agent_grants VALUES (?, ?, ?, ?, ?, ?, ?)",
            (secret_hash(raw), row["owner_subject_id"], row["workspace_ref"], row["source_session_hash"],
             row["audience"], row["scopes_json"], row["grant_expires_at"]))
        db.commit()
    return PairingSecret(SecretStr(raw), row["grant_expires_at"])


def resolve_agent_grant(settings: Settings, integration: Principal, token: SecretStr,
                        required_scope: str) -> tuple[Principal, str]:
    _integration(settings, integration)
    if required_scope not in SAFE_SCOPES:
        raise AppError(403, "FORBIDDEN", "Agent cannot confirm or save")
    with database_connection(settings) as db:
        row = db.execute("SELECT * FROM local_agent_grants WHERE token_hash=? AND audience=?",
            (secret_hash(token.get_secret_value()), integration.subject_id)).fetchone()
        if not row:
            raise AppError(401, "AUTH_REQUIRED", "Pairing is invalid or expired")
        _live(db, row, settings, int(time.time()))
        scopes = frozenset(json.loads(row["scopes_json"]))
        if not scopes <= SAFE_SCOPES or required_scope not in scopes:
            raise AppError(403, "FORBIDDEN", "Requested scope was not approved")
        principal = Principal(row["owner_subject_id"], "agent_grant", scopes, "paired-local-prototype")
        return principal, row["workspace_ref"]


def revoke_pairing(request: Request, settings: Settings) -> None:
    principal, _ = _browser(request, settings)
    with database_connection(settings) as db:
        db.execute("BEGIN IMMEDIATE")
        for table in ("local_pairing_tickets", "local_agent_grants"):
            db.execute(f"DELETE FROM {table} WHERE owner_subject_id=?", (principal.subject_id,))
        db.commit()


def read_paired_records(settings: Settings, integration: Principal, token: SecretStr) -> dict:
    principal, workspace = resolve_agent_grant(settings, integration, token, "demo:read")
    try:
        schedule = service.get_current_schedule(settings, principal, workspace)
    except AppError as exc:
        if exc.code != "NOT_FOUND":
            raise
        schedule = None  # No fallback to another user's or public fixture schedule.
    return {"dataset_kind": "demo", "personal_uploads": False, "schedule": schedule,
            "tasks": service.list_tasks(settings, principal, workspace)}


def create_paired_task_draft(settings: Settings, integration: Principal, token: SecretStr,
                              notice: dict, idempotency_key: str) -> dict:
    principal, workspace = resolve_agent_grant(settings, integration, token, "demo:draft")
    require_idempotency_key(idempotency_key)
    return service.create_browser_draft(settings, principal, workspace, "task", notice, idempotency_key)

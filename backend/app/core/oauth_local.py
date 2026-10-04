"""Closed, standards-shaped OAuth pilot. No cloud activation or refresh tokens.

The school must demonstrate PKCE and server-side token handling before this
adapter can be promoted. Never treat SYS_USERID or a shared bearer as an owner.
"""
import base64
import hashlib
import json
import re
import secrets
import time
from urllib.parse import urlencode, urlsplit

from pydantic import SecretStr
from fastapi import Request

from app.core import agent_pairing_local as pairing
from app.core.config import Settings
from app.core.demo import FIXTURE_SET_ID
from app.core.errors import AppError
from app.core.security import Principal, SESSION_COOKIE, resolve_browser_principal, secret_hash
from app.db.database import database_connection


class OAuthError(Exception):
    def __init__(self, error="invalid_request", status=400):
        self.error, self.status = error, status
        super().__init__(error)  # Never include supplied parameters or credentials.


def gate(settings: Settings):
    pairing._gate(settings)
    url = urlsplit(settings.oauth_redirect_uri)
    origin = urlsplit(settings.app_origin)
    digest = settings.oauth_client_secret_hash.get_secret_value()
    if (not settings.oauth_local_enabled or settings.oauth_client_id != settings.agent_pairing_audience
            or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", settings.oauth_client_id)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or url.username is not None or url.password is not None or url.query or url.fragment
            or not url.hostname or not url.path
            or origin.scheme != "http" or origin.hostname not in {"127.0.0.1", "localhost", "testserver"}
            or origin.username is not None or origin.password is not None or origin.query or origin.fragment or origin.path
            or not (url.scheme == "https" or (settings.app_env == "test" and
                    url.scheme == "http" and url.hostname in {"127.0.0.1", "testserver"}))):
        raise OAuthError("temporarily_unavailable", 503)


def initialize(settings: Settings):
    gate(settings)
    pairing.initialize_pairing_prototype(settings)
    with database_connection(settings) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS local_oauth_requests (
          transaction_hash TEXT PRIMARY KEY, owner_subject_id TEXT NOT NULL,
          workspace_ref TEXT NOT NULL REFERENCES workspaces(workspace_ref) ON DELETE CASCADE,
          source_session_hash TEXT NOT NULL, audience TEXT NOT NULL,
          redirect_uri TEXT NOT NULL, scopes_json TEXT NOT NULL,
          challenge TEXT NOT NULL, state TEXT NOT NULL, expires_at INTEGER NOT NULL,
          grant_expires_at INTEGER NOT NULL, used_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS local_oauth_codes (
          code_hash TEXT PRIMARY KEY, transaction_hash TEXT NOT NULL UNIQUE
            REFERENCES local_oauth_requests(transaction_hash) ON DELETE CASCADE,
          expires_at INTEGER NOT NULL, used_at INTEGER
        );
        """)


def integration(settings: Settings):
    return Principal(settings.oauth_client_id, "mcp_service",
                     frozenset({"integration:pair"}), "server-integration")


def browser(request: Request, settings: Settings):
    gate(settings)
    principal = resolve_browser_principal(request, settings=settings)
    if not principal.subject_id.startswith("cloudbase_pilot_"):
        raise AppError(401, "AUTH_REQUIRED", "Verified pilot login required")
    return principal, secret_hash(request.cookies[SESSION_COOKIE])


def begin(request: Request, settings: Settings, params: dict):
    gate(settings)
    # Invalid redirect/client never causes a redirect, even an error redirect.
    required = {"response_type", "client_id", "redirect_uri", "scope", "state", "code_challenge", "code_challenge_method"}
    if (set(params) != required or params["client_id"] != settings.oauth_client_id
            or params["redirect_uri"] != settings.oauth_redirect_uri):
        raise OAuthError()
    if params["response_type"] != "code":
        raise OAuthError("unsupported_response_type")
    scopes = frozenset(params["scope"].split(" "))
    if params["scope"] not in {"demo:read", "demo:read demo:draft", "demo:draft demo:read"}:
        raise OAuthError("invalid_scope")
    if (params["code_challenge_method"] != "S256" or
            not re.fullmatch(r"[A-Za-z0-9_-]{43}", params["code_challenge"]) or
            not re.fullmatch(r"[A-Za-z0-9._~-]{16,256}", params["state"])):
        raise OAuthError()
    owner, session_hash = browser(request, settings)
    now, raw = int(time.time()), secrets.token_urlsafe(32)
    with database_connection(settings) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM local_oauth_requests WHERE expires_at<=?", (now,))
        if db.execute("SELECT count(*) FROM local_oauth_requests").fetchone()[0] >= 100:
            raise OAuthError("temporarily_unavailable", 429)
        workspace = db.execute("SELECT * FROM cloudbase_pilot_workspaces WHERE subject_id=?",
                               (owner.subject_id,)).fetchone()
        if not workspace:
            raise OAuthError("access_denied", 403)
        workspace = db.execute("SELECT * FROM workspaces WHERE workspace_ref=? AND owner_subject_id=?",
                              (workspace["workspace_ref"], owner.subject_id)).fetchone()
        session = db.execute("SELECT expires_at FROM browser_sessions WHERE token_hash=?",
                             (session_hash,)).fetchone()
        if not workspace or workspace["fixture_set_id"] != FIXTURE_SET_ID or not session:
            raise OAuthError("access_denied", 403)
        expiry = min(now + 120, session["expires_at"], workspace["expires_at"])
        if expiry <= now:
            raise OAuthError("access_denied", 403)
        db.execute("INSERT INTO local_oauth_requests VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL)",
            (secret_hash(raw), owner.subject_id, workspace["workspace_ref"], session_hash,
             settings.oauth_client_id, settings.oauth_redirect_uri, json.dumps(sorted(scopes)),
             params["code_challenge"], params["state"], expiry,
             min(now + 600, session["expires_at"], workspace["expires_at"])))
        db.commit()
    return raw, scopes


def approve(request: Request, settings: Settings, transaction: str, decision: str):
    owner, session_hash = browser(request, settings)
    if request.headers.get("Origin", "") != settings.app_origin or decision not in {"allow", "deny"}:
        raise OAuthError("access_denied", 403)
    now, raw = int(time.time()), secrets.token_urlsafe(32)
    with database_connection(settings) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM local_oauth_requests WHERE transaction_hash=? AND used_at IS NULL",
                         (secret_hash(transaction),)).fetchone()
        if (not row or row["owner_subject_id"] != owner.subject_id or
                row["source_session_hash"] != session_hash or row["audience"] != settings.oauth_client_id
                or row["redirect_uri"] != settings.oauth_redirect_uri):
            raise OAuthError("access_denied", 403)
        try:
            pairing._live(db, row, settings, now)
        except AppError:
            raise OAuthError("access_denied", 403) from None
        db.execute("UPDATE local_oauth_requests SET used_at=? WHERE transaction_hash=?", (now, row["transaction_hash"]))
        if decision == "allow":
            db.execute("INSERT INTO local_oauth_codes VALUES (?,?,?,NULL)",
                       (secret_hash(raw), row["transaction_hash"], row["expires_at"]))
        db.commit()
    result = {"code": raw, "state": row["state"]} if decision == "allow" else {"error": "access_denied", "state": row["state"]}
    return settings.oauth_redirect_uri + "?" + urlencode(result)


def authenticate(settings: Settings, client_id: str, client_secret: str):
    gate(settings)
    if (len(client_secret) < 40 or len(client_secret) > 256 or client_id != settings.oauth_client_id or
            not secrets.compare_digest(secret_hash(client_secret), settings.oauth_client_secret_hash.get_secret_value())):
        raise OAuthError("invalid_client", 401)


def exchange(settings: Settings, params: dict):
    gate(settings)
    if set(params) != {"grant_type", "code", "redirect_uri", "code_verifier"}:
        raise OAuthError()
    if params["grant_type"] != "authorization_code":
        raise OAuthError("unsupported_grant_type")
    verifier = params["code_verifier"]
    if not re.fullmatch(r"[A-Za-z0-9._~-]{43,128}", verifier):
        raise OAuthError("invalid_grant")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    now, raw = int(time.time()), secrets.token_urlsafe(32)
    with database_connection(settings) as db:
        db.execute("BEGIN IMMEDIATE")
        code = db.execute("SELECT * FROM local_oauth_codes WHERE code_hash=? AND used_at IS NULL",
                          (secret_hash(params["code"]),)).fetchone()
        row = db.execute("SELECT * FROM local_oauth_requests WHERE transaction_hash=?",
                         (code["transaction_hash"],)).fetchone() if code else None
        if (not row or code["expires_at"] <= now or row["audience"] != settings.oauth_client_id or
                params["redirect_uri"] != row["redirect_uri"] or row["redirect_uri"] != settings.oauth_redirect_uri or
                not secrets.compare_digest(challenge, row["challenge"])):
            raise OAuthError("invalid_grant")
        try:
            pairing._live(db, row, settings, now)
        except AppError:
            raise OAuthError("invalid_grant") from None
        db.execute("UPDATE local_oauth_codes SET used_at=? WHERE code_hash=?", (now, code["code_hash"]))
        db.execute("INSERT INTO local_agent_grants VALUES (?,?,?,?,?,?,?)",
            (secret_hash(raw), row["owner_subject_id"], row["workspace_ref"], row["source_session_hash"],
             row["audience"], row["scopes_json"], row["grant_expires_at"]))
        db.commit()
    return {"access_token": raw, "token_type": "Bearer", "expires_in": row["grant_expires_at"] - now,
            "scope": " ".join(json.loads(row["scopes_json"]))}


def revoke(settings: Settings, token: str):
    gate(settings)
    with database_connection(settings) as db:
        db.execute("DELETE FROM local_agent_grants WHERE token_hash=? AND audience=?",
                   (secret_hash(token), settings.oauth_client_id))
        db.commit()


def resource_token(request: Request) -> SecretStr:
    header = request.headers.get("Authorization", "")
    if request.url.query or not re.fullmatch(r"Bearer [A-Za-z0-9_-]{43}", header):
        raise AppError(401, "AUTH_REQUIRED", "Bearer access token required")
    return SecretStr(header.removeprefix("Bearer "))

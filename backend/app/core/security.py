import hashlib
import json
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.database import database_connection


SESSION_COOKIE = "campus_session"
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


@dataclass(frozen=True, slots=True)
class Principal:
    subject_id: str
    kind: str
    scopes: frozenset[str]
    trusted_origin: str


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_idempotency_key(value: str) -> str:
    if not IDEMPOTENCY_PATTERN.fullmatch(value):
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Idempotency key must be 8-128 safe characters",
        )
    return value


def resolve_browser_principal(
    request: Request,
    *,
    require_csrf: bool = False,
    settings: Settings | None = None,
) -> Principal:
    runtime = settings or get_settings()
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise AppError(status_code=401, code="AUTH_REQUIRED", message="Browser session required")

    with database_connection(runtime) as connection:
        row = connection.execute(
            "SELECT subject_id, csrf_hash, expires_at FROM browser_sessions WHERE token_hash = ?",
            (secret_hash(token),),
        ).fetchone()
    if row is None:
        raise AppError(status_code=401, code="AUTH_REQUIRED", message="Browser session required")

    now = int(time.time())
    if row["expires_at"] <= now:
        raise AppError(status_code=401, code="AUTH_REQUIRED", message="Browser session expired")

    if require_csrf:
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not secrets.compare_digest(secret_hash(csrf), row["csrf_hash"]):
            raise AppError(status_code=403, code="FORBIDDEN", message="CSRF validation failed")

    origin = request.headers.get("Origin", "")
    if origin and runtime.app_origin and origin.rstrip("/") != runtime.app_origin.rstrip("/"):
        raise AppError(status_code=403, code="FORBIDDEN", message="Origin is not allowed")

    return Principal(
        subject_id=row["subject_id"],
        kind="browser_user",
        scopes=frozenset({"demo:read", "demo:draft", "demo:commit"}),
        trusted_origin=origin or "same-origin-session",
    )


def resolve_workspace(
    principal: Principal,
    workspace_ref: str,
    required_scope: str,
    *,
    settings: Settings | None = None,
):
    if required_scope not in principal.scopes:
        raise AppError(status_code=403, code="FORBIDDEN", message="Scope is not allowed")
    runtime = settings or get_settings()
    with database_connection(runtime) as connection:
        row = connection.execute(
            """
            SELECT workspace_ref, fixture_set_id, expires_at
            FROM workspaces
            WHERE workspace_ref = ? AND owner_subject_id = ?
            """,
            (workspace_ref, principal.subject_id),
        ).fetchone()
    if row is None:
        raise AppError(status_code=404, code="NOT_FOUND", message="Workspace not found")
    if row["expires_at"] <= int(time.time()):
        raise AppError(status_code=404, code="NOT_FOUND", message="Workspace not found")
    return row

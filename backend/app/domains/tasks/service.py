import json
import sqlite3
import time
from datetime import datetime
from secrets import token_urlsafe
from typing import Any, Literal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.core.contracts import validate_contract
from app.core.demo import FIXTURE_SET_ID, enforce_demo_fixture
from app.core.errors import AppError
from app.core.security import Principal, canonical_json, payload_hash, resolve_workspace, secret_hash
from app.db.database import database_connection


SHANGHAI = ZoneInfo("Asia/Shanghai")


def _timestamp_text(value: int) -> str:
    return datetime.fromtimestamp(value, SHANGHAI).isoformat(timespec="seconds")


def _identifier(prefix: str) -> str:
    return f"{prefix}_{token_urlsafe(18)}"


def _review_url(settings: Settings, kind: Literal["schedule", "task"], draft_id: str) -> str | None:
    if not settings.app_origin:
        return None
    path = "/tools/import" if kind == "schedule" else "/tools/tasks"
    return f"{settings.app_origin.rstrip('/')}{path}?{urlencode({'draft_id': draft_id})}"


def _idempotent_result(
    connection: sqlite3.Connection,
    principal: Principal,
    operation: str,
    idempotency_key: str,
    request_digest: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT request_hash, response_json
        FROM idempotency_records
        WHERE owner_subject_id = ? AND operation = ? AND idempotency_key = ?
        """,
        (principal.subject_id, operation, idempotency_key),
    ).fetchone()
    if row is None:
        return None
    if row["request_hash"] != request_digest:
        raise AppError(
            status_code=409,
            code="STALE_REVISION",
            message="Idempotency key was already used with a different payload",
        )
    return json.loads(row["response_json"])


def _save_idempotent_result(
    connection: sqlite3.Connection,
    principal: Principal,
    operation: str,
    idempotency_key: str,
    request_digest: str,
    response: dict[str, Any],
    now: int,
) -> None:
    connection.execute(
        """
        INSERT INTO idempotency_records
            (owner_subject_id, operation, idempotency_key, request_hash, response_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            principal.subject_id,
            operation,
            idempotency_key,
            request_digest,
            canonical_json(response),
            now,
        ),
    )


def cleanup_expired(settings: Settings, now: int | None = None) -> None:
    current = now or int(time.time())
    retention_floor = current - settings.demo_workspace_ttl_hours * 3600
    with database_connection(settings) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM confirmations WHERE expires_at <= ?", (current,))
        connection.execute("DELETE FROM import_tickets WHERE expires_at <= ?", (current,))
        connection.execute("DELETE FROM drafts WHERE expires_at <= ?", (current,))
        connection.execute("DELETE FROM workspaces WHERE expires_at <= ?", (current,))
        connection.execute("DELETE FROM browser_sessions WHERE expires_at <= ?", (current,))
        connection.execute(
            "DELETE FROM idempotency_records WHERE created_at <= ?",
            (retention_floor,),
        )
        connection.commit()


def create_demo_workspace(settings: Settings, fixture_set_id: str) -> dict[str, Any]:
    if settings.auth_mode != "demo_fixture":
        raise AppError(status_code=403, code="DEMO_ONLY", message="Demo workspace mode is disabled")
    if fixture_set_id != FIXTURE_SET_ID:
        raise AppError(status_code=403, code="DEMO_ONLY", message="Unknown demo fixture set")

    cleanup_expired(settings)
    now = int(time.time())
    expires_at = now + settings.demo_workspace_ttl_hours * 3600
    subject_id = _identifier("demo_subject")
    workspace_ref = _identifier("demo_workspace")
    session_token = token_urlsafe(32)
    csrf_token = token_urlsafe(32)

    with database_connection(settings) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO browser_sessions VALUES (?, ?, ?, ?, ?)",
            (secret_hash(session_token), subject_id, secret_hash(csrf_token), now, expires_at),
        )
        connection.execute(
            "INSERT INTO workspaces VALUES (?, ?, ?, ?, ?)",
            (workspace_ref, subject_id, fixture_set_id, now, expires_at),
        )
        connection.commit()

    return {
        "workspace_ref": workspace_ref,
        "fixture_set_id": fixture_set_id,
        "dataset_kind": "demo",
        "expires_at": _timestamp_text(expires_at),
        "session_token": session_token,
        "csrf_token": csrf_token,
    }


def create_import_ticket(
    settings: Settings,
    principal: Principal,
    workspace_ref: str,
    purpose: str,
    idempotency_key: str,
) -> dict[str, Any]:
    if purpose != "schedule_import":
        raise AppError(status_code=422, code="VALIDATION_ERROR", message="Unsupported ticket purpose")
    resolve_workspace(principal, workspace_ref, "demo:draft", settings=settings)
    now = int(time.time())
    expires_at = now + settings.import_ticket_ttl_seconds
    raw_token = token_urlsafe(32)
    with database_connection(settings) as connection:
        try:
            connection.execute(
                """
                INSERT INTO import_tickets
                    (token_hash, workspace_ref, owner_subject_id, purpose, issuance_key,
                     created_at, expires_at, used_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    secret_hash(raw_token),
                    workspace_ref,
                    principal.subject_id,
                    purpose,
                    idempotency_key,
                    now,
                    expires_at,
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            raise AppError(
                status_code=409,
                code="STALE_REVISION",
                message="Import ticket issuance already completed for this idempotency key",
            ) from exc
    return {
        "import_ticket": raw_token,
        "purpose": purpose,
        "workspace_ref": workspace_ref,
        "expires_at": _timestamp_text(expires_at),
    }


def active_workspace_ref(settings: Settings, principal: Principal) -> str:
    now = int(time.time())
    with database_connection(settings) as connection:
        rows = connection.execute(
            """
            SELECT workspace_ref FROM workspaces
            WHERE owner_subject_id = ? AND expires_at > ?
            ORDER BY created_at DESC
            """,
            (principal.subject_id, now),
        ).fetchall()
    if not rows:
        raise AppError(status_code=404, code="NOT_FOUND", message="Workspace not found")
    if len(rows) > 1:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Workspace must be selected explicitly",
        )
    return rows[0]["workspace_ref"]


def _create_draft_row(
    connection: sqlite3.Connection,
    settings: Settings,
    principal: Principal,
    workspace_ref: str,
    kind: Literal["schedule", "task"],
    payload: dict[str, Any],
    digest: str,
    now: int,
) -> dict[str, Any]:
    draft_id = _identifier(f"{kind}_draft")
    expires_at = now + settings.demo_workspace_ttl_hours * 3600
    connection.execute(
        """
        INSERT INTO drafts
            (draft_id, kind, workspace_ref, owner_subject_id, revision, payload_json,
             payload_hash, status, created_at, updated_at, expires_at)
        VALUES (?, ?, ?, ?, 1, ?, ?, 'draft', ?, ?, ?)
        """,
        (
            draft_id,
            kind,
            workspace_ref,
            principal.subject_id,
            canonical_json(payload),
            digest,
            now,
            now,
            expires_at,
        ),
    )
    return {
        "draft_id": draft_id,
        "kind": kind,
        "workspace_ref": workspace_ref,
        "revision": 1,
        "payload_hash": digest,
        "status": "draft",
        "review_url": _review_url(settings, kind, draft_id),
        "expires_at": _timestamp_text(expires_at),
    }


def create_browser_draft(
    settings: Settings,
    principal: Principal,
    workspace_ref: str,
    kind: Literal["schedule", "task"],
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    resolve_workspace(principal, workspace_ref, "demo:draft", settings=settings)
    validate_contract(payload, "TimetableImport" if kind == "schedule" else "NoticeDraft")
    digest = enforce_demo_fixture(payload, kind)
    request_digest = payload_hash({"workspace_ref": workspace_ref, "kind": kind, "payload": payload})
    operation = f"create_{kind}_draft"
    now = int(time.time())

    with database_connection(settings) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = _idempotent_result(
            connection, principal, operation, idempotency_key, request_digest
        )
        if existing is not None:
            connection.rollback()
            return existing
        result = _create_draft_row(
            connection, settings, principal, workspace_ref, kind, payload, digest, now
        )
        _save_idempotent_result(
            connection, principal, operation, idempotency_key, request_digest, result, now
        )
        connection.commit()
        return result


def create_schedule_draft_with_ticket(
    settings: Settings,
    raw_ticket: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    validate_contract(payload, "TimetableImport")
    digest = enforce_demo_fixture(payload, "schedule")
    request_digest = payload_hash({"kind": "schedule", "payload": payload})
    now = int(time.time())

    with database_connection(settings) as connection:
        connection.execute("BEGIN IMMEDIATE")
        ticket = connection.execute(
            "SELECT * FROM import_tickets WHERE token_hash = ?",
            (secret_hash(raw_ticket),),
        ).fetchone()
        if ticket is None:
            raise AppError(status_code=401, code="AUTH_REQUIRED", message="Import ticket is invalid")
        principal = Principal(
            subject_id=ticket["owner_subject_id"],
            kind="import_ticket",
            scopes=frozenset({"demo:draft"}),
            trusted_origin="extension-ticket",
        )
        existing = _idempotent_result(
            connection, principal, "create_schedule_draft", idempotency_key, request_digest
        )
        if existing is not None:
            connection.rollback()
            return existing
        if ticket["purpose"] != "schedule_import":
            raise AppError(status_code=403, code="FORBIDDEN", message="Ticket purpose is not allowed")
        if ticket["expires_at"] <= now or ticket["used_at"] is not None:
            raise AppError(status_code=410, code="TOKEN_EXPIRED", message="Import ticket expired or used")

        workspace = connection.execute(
            """
            SELECT workspace_ref FROM workspaces
            WHERE workspace_ref = ? AND owner_subject_id = ? AND expires_at > ?
            """,
            (ticket["workspace_ref"], principal.subject_id, now),
        ).fetchone()
        if workspace is None:
            raise AppError(status_code=404, code="NOT_FOUND", message="Workspace not found")

        result = _create_draft_row(
            connection,
            settings,
            principal,
            ticket["workspace_ref"],
            "schedule",
            payload,
            digest,
            now,
        )
        connection.execute(
            "UPDATE import_tickets SET used_at = ? WHERE token_hash = ?",
            (now, ticket["token_hash"]),
        )
        _save_idempotent_result(
            connection,
            principal,
            "create_schedule_draft",
            idempotency_key,
            request_digest,
            result,
            now,
        )
        connection.commit()
        return result


def get_draft(settings: Settings, principal: Principal, draft_id: str) -> dict[str, Any]:
    with database_connection(settings) as connection:
        row = connection.execute(
            "SELECT * FROM drafts WHERE draft_id = ? AND owner_subject_id = ?",
            (draft_id, principal.subject_id),
        ).fetchone()
    if row is None:
        raise AppError(status_code=404, code="NOT_FOUND", message="Draft not found")
    return {
        "draft_id": row["draft_id"],
        "kind": row["kind"],
        "workspace_ref": row["workspace_ref"],
        "revision": row["revision"],
        "payload": json.loads(row["payload_json"]),
        "payload_hash": row["payload_hash"],
        "status": row["status"],
        "review_url": _review_url(settings, row["kind"], row["draft_id"]),
        "expires_at": _timestamp_text(row["expires_at"]),
    }


def update_draft(
    settings: Settings,
    principal: Principal,
    draft_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    now = int(time.time())
    with database_connection(settings) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM drafts WHERE draft_id = ? AND owner_subject_id = ?",
            (draft_id, principal.subject_id),
        ).fetchone()
        if row is None:
            raise AppError(status_code=404, code="NOT_FOUND", message="Draft not found")
        if row["status"] != "draft":
            raise AppError(status_code=409, code="STALE_REVISION", message="Draft is already committed")
        kind = row["kind"]
        validate_contract(payload, "TimetableImport" if kind == "schedule" else "NoticeDraft")
        digest = enforce_demo_fixture(payload, kind)
        revision = row["revision"] + 1
        connection.execute(
            """
            UPDATE drafts
            SET revision = ?, payload_json = ?, payload_hash = ?, updated_at = ?, expires_at = ?
            WHERE draft_id = ?
            """,
            (
                revision,
                canonical_json(payload),
                digest,
                now,
                now + settings.demo_workspace_ttl_hours * 3600,
                draft_id,
            ),
        )
        connection.commit()
    return get_draft(settings, principal, draft_id)


def create_confirmation(
    settings: Settings,
    principal: Principal,
    draft_id: str,
    revision: int,
    expected_payload_hash: str,
    idempotency_key: str,
) -> dict[str, Any]:
    now = int(time.time())
    request_digest = payload_hash(
        {"draft_id": draft_id, "revision": revision, "payload_hash": expected_payload_hash}
    )
    with database_connection(settings) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = _idempotent_result(
            connection, principal, "create_confirmation", idempotency_key, request_digest
        )
        if existing is not None:
            connection.rollback()
            return existing
        draft = connection.execute(
            "SELECT * FROM drafts WHERE draft_id = ? AND owner_subject_id = ?",
            (draft_id, principal.subject_id),
        ).fetchone()
        if draft is None:
            raise AppError(status_code=404, code="NOT_FOUND", message="Draft not found")
        if draft["expires_at"] <= now:
            raise AppError(status_code=410, code="TOKEN_EXPIRED", message="Draft expired")
        if (
            draft["status"] != "draft"
            or draft["revision"] != revision
            or draft["payload_hash"] != expected_payload_hash
        ):
            raise AppError(status_code=409, code="STALE_REVISION", message="Draft revision changed")

        confirmation_id = _identifier("confirmation")
        expires_at = now + settings.confirmation_ttl_seconds
        connection.execute(
            """
            INSERT INTO confirmations
                (confirmation_hash, draft_id, owner_subject_id, purpose, revision,
                 payload_hash, created_at, expires_at, used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                secret_hash(confirmation_id),
                draft_id,
                principal.subject_id,
                f"commit_{draft['kind']}",
                revision,
                expected_payload_hash,
                now,
                expires_at,
            ),
        )
        result = {
            "confirmation_id": confirmation_id,
            "draft_id": draft_id,
            "revision": revision,
            "payload_hash": expected_payload_hash,
            "expires_at": _timestamp_text(expires_at),
        }
        _save_idempotent_result(
            connection,
            principal,
            "create_confirmation",
            idempotency_key,
            request_digest,
            result,
            now,
        )
        connection.commit()
        return result


def commit_draft(
    settings: Settings,
    principal: Principal,
    kind: Literal["schedule", "task"],
    confirmation_id: str,
    idempotency_key: str,
) -> dict[str, Any]:
    now = int(time.time())
    request_digest = payload_hash({"kind": kind, "confirmation_id": confirmation_id})
    operation = f"commit_{kind}"
    with database_connection(settings) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = _idempotent_result(
            connection, principal, operation, idempotency_key, request_digest
        )
        if existing is not None:
            connection.rollback()
            return existing
        confirmation = connection.execute(
            """
            SELECT * FROM confirmations
            WHERE confirmation_hash = ? AND owner_subject_id = ?
            """,
            (secret_hash(confirmation_id), principal.subject_id),
        ).fetchone()
        if confirmation is None:
            raise AppError(status_code=409, code="CONFIRMATION_REQUIRED", message="Confirmation required")
        if confirmation["expires_at"] <= now:
            raise AppError(status_code=410, code="TOKEN_EXPIRED", message="Confirmation expired")
        if confirmation["used_at"] is not None or confirmation["purpose"] != operation:
            raise AppError(
                status_code=409,
                code="CONFIRMATION_REQUIRED",
                message="Confirmation is invalid or already used",
            )
        draft = connection.execute(
            "SELECT * FROM drafts WHERE draft_id = ? AND owner_subject_id = ?",
            (confirmation["draft_id"], principal.subject_id),
        ).fetchone()
        if draft is None:
            raise AppError(status_code=404, code="NOT_FOUND", message="Draft not found")
        if (
            draft["kind"] != kind
            or draft["status"] != "draft"
            or draft["revision"] != confirmation["revision"]
            or draft["payload_hash"] != confirmation["payload_hash"]
        ):
            raise AppError(status_code=409, code="STALE_REVISION", message="Draft revision changed")

        if kind == "task":
            resource_id = _identifier("task")
            resource_revision = 1
            connection.execute(
                """
                INSERT INTO tasks
                    (task_id, workspace_ref, owner_subject_id, revision, payload_json,
                     payload_hash, confirmed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resource_id,
                    draft["workspace_ref"],
                    principal.subject_id,
                    resource_revision,
                    draft["payload_json"],
                    draft["payload_hash"],
                    now,
                ),
            )
            result = {"task_id": resource_id, "revision": resource_revision}
        else:
            current = connection.execute(
                "SELECT schedule_id, revision FROM schedules WHERE workspace_ref = ?",
                (draft["workspace_ref"],),
            ).fetchone()
            resource_id = current["schedule_id"] if current else _identifier("schedule")
            resource_revision = current["revision"] + 1 if current else 1
            connection.execute(
                """
                INSERT INTO schedules
                    (schedule_id, workspace_ref, owner_subject_id, revision, payload_json,
                     payload_hash, confirmed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_ref) DO UPDATE SET
                    owner_subject_id = excluded.owner_subject_id,
                    revision = excluded.revision,
                    payload_json = excluded.payload_json,
                    payload_hash = excluded.payload_hash,
                    confirmed_at = excluded.confirmed_at
                """,
                (
                    resource_id,
                    draft["workspace_ref"],
                    principal.subject_id,
                    resource_revision,
                    draft["payload_json"],
                    draft["payload_hash"],
                    now,
                ),
            )
            result = {"schedule_id": resource_id, "revision": resource_revision}

        connection.execute(
            "UPDATE confirmations SET used_at = ? WHERE confirmation_hash = ?",
            (now, confirmation["confirmation_hash"]),
        )
        connection.execute(
            "UPDATE drafts SET status = 'committed', updated_at = ? WHERE draft_id = ?",
            (now, draft["draft_id"]),
        )
        _save_idempotent_result(
            connection, principal, operation, idempotency_key, request_digest, result, now
        )
        connection.commit()
        return result


def list_tasks(settings: Settings, principal: Principal, workspace_ref: str) -> list[dict[str, Any]]:
    resolve_workspace(principal, workspace_ref, "demo:read", settings=settings)
    with database_connection(settings) as connection:
        rows = connection.execute(
            """
            SELECT * FROM tasks
            WHERE workspace_ref = ? AND owner_subject_id = ?
            ORDER BY confirmed_at DESC
            """,
            (workspace_ref, principal.subject_id),
        ).fetchall()
    return [
        {
            "task_id": row["task_id"],
            "workspace_ref": row["workspace_ref"],
            "revision": row["revision"],
            "notice": json.loads(row["payload_json"]),
            "confirmed_at": _timestamp_text(row["confirmed_at"]),
        }
        for row in rows
    ]


def get_task(settings: Settings, principal: Principal, task_id: str) -> dict[str, Any]:
    with database_connection(settings) as connection:
        row = connection.execute(
            "SELECT * FROM tasks WHERE task_id = ? AND owner_subject_id = ?",
            (task_id, principal.subject_id),
        ).fetchone()
    if row is None:
        raise AppError(status_code=404, code="NOT_FOUND", message="Task not found")
    return {
        "task_id": row["task_id"],
        "workspace_ref": row["workspace_ref"],
        "revision": row["revision"],
        "notice": json.loads(row["payload_json"]),
        "confirmed_at": _timestamp_text(row["confirmed_at"]),
    }


def get_current_schedule(
    settings: Settings, principal: Principal, workspace_ref: str
) -> dict[str, Any]:
    resolve_workspace(principal, workspace_ref, "demo:read", settings=settings)
    with database_connection(settings) as connection:
        row = connection.execute(
            """
            SELECT * FROM schedules
            WHERE workspace_ref = ? AND owner_subject_id = ?
            """,
            (workspace_ref, principal.subject_id),
        ).fetchone()
    if row is None:
        raise AppError(status_code=404, code="NOT_FOUND", message="Schedule not found")
    return {
        "schedule_id": row["schedule_id"],
        "workspace_ref": row["workspace_ref"],
        "revision": row["revision"],
        "timetable": json.loads(row["payload_json"]),
        "confirmed_at": _timestamp_text(row["confirmed_at"]),
    }

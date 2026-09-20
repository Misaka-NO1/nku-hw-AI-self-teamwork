import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import Settings


def _sqlite_target(settings: Settings) -> str:
    if not settings.database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// database URLs are supported in the first version")
    return settings.database_url.removeprefix("sqlite:///")


def initialize_database(settings: Settings) -> None:
    target = _sqlite_target(settings)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS browser_sessions (
                token_hash TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                csrf_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS workspaces (
                workspace_ref TEXT PRIMARY KEY,
                owner_subject_id TEXT NOT NULL,
                fixture_set_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS import_tickets (
                token_hash TEXT PRIMARY KEY,
                workspace_ref TEXT NOT NULL REFERENCES workspaces(workspace_ref) ON DELETE CASCADE,
                owner_subject_id TEXT NOT NULL,
                purpose TEXT NOT NULL,
                issuance_key TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                used_at INTEGER,
                UNIQUE(owner_subject_id, issuance_key)
            );

            CREATE TABLE IF NOT EXISTS drafts (
                draft_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL CHECK (kind IN ('schedule', 'task')),
                workspace_ref TEXT NOT NULL REFERENCES workspaces(workspace_ref) ON DELETE CASCADE,
                owner_subject_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('draft', 'committed')),
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS confirmations (
                confirmation_hash TEXT PRIMARY KEY,
                draft_id TEXT NOT NULL REFERENCES drafts(draft_id) ON DELETE CASCADE,
                owner_subject_id TEXT NOT NULL,
                purpose TEXT NOT NULL,
                revision INTEGER NOT NULL,
                payload_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                used_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS schedules (
                schedule_id TEXT PRIMARY KEY,
                workspace_ref TEXT NOT NULL UNIQUE REFERENCES workspaces(workspace_ref) ON DELETE CASCADE,
                owner_subject_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                confirmed_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                workspace_ref TEXT NOT NULL REFERENCES workspaces(workspace_ref) ON DELETE CASCADE,
                owner_subject_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                confirmed_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS idempotency_records (
                owner_subject_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (owner_subject_id, operation, idempotency_key)
            );

            CREATE INDEX IF NOT EXISTS idx_workspaces_owner ON workspaces(owner_subject_id);
            CREATE INDEX IF NOT EXISTS idx_drafts_owner ON drafts(owner_subject_id, workspace_ref);
            CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_subject_id, workspace_ref);
            PRAGMA user_version = 2;
            """
        )
        ticket_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(import_tickets)").fetchall()
        }
        if "issuance_key" not in ticket_columns:
            connection.execute("ALTER TABLE import_tickets ADD COLUMN issuance_key TEXT")
            connection.execute(
                "UPDATE import_tickets SET issuance_key = 'legacy-' || token_hash WHERE issuance_key IS NULL"
            )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_import_ticket_issuance
            ON import_tickets(owner_subject_id, issuance_key)
            """
        )


def probe_database(settings: Settings) -> None:
    target = _sqlite_target(settings)
    with sqlite3.connect(target) as connection:
        connection.execute("SELECT 1").fetchone()


@contextmanager
def database_connection(settings: Settings) -> Iterator[sqlite3.Connection]:
    target = _sqlite_target(settings)
    connection = sqlite3.connect(target, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()

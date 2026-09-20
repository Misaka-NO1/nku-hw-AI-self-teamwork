import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.demo import load_fixture
from app.core.security import Principal, secret_hash
from app.db.database import database_connection, initialize_database
from app.domains.tasks.service import cleanup_expired, update_draft
from app.main import app


@pytest.fixture
def workflow_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "workflow.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("APP_ORIGIN", "http://testserver")
    monkeypatch.setenv("AUTH_MODE", "demo_fixture")
    monkeypatch.setenv("ALLOW_PERSONAL_UPLOADS", "false")
    get_settings.cache_clear()
    initialize_database(get_settings())
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def create_workspace(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/api/v1/demo/workspaces",
        json={"fixture_set_id": "demo-v1"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    return data["workspace_ref"], data["csrf_token"]


def create_task_draft(
    client: TestClient,
    workspace_ref: str,
    csrf: str,
    fixture_name: str = "notice-event.demo.json",
    key: str = "task-draft-key-001",
):
    return client.post(
        "/api/v1/tasks/drafts",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key},
        json={"workspace_ref": workspace_ref, "notice": load_fixture(fixture_name)},
    )


def confirm_draft(client: TestClient, csrf: str, draft: dict, key: str = "confirm-key-001"):
    return client.post(
        "/api/v1/confirmations",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key},
        json={
            "draft_id": draft["draft_id"],
            "revision": draft["revision"],
            "payload_hash": draft["payload_hash"],
        },
    )


def current_principal(client: TestClient) -> Principal:
    raw_session = client.cookies.get("campus_session")
    assert raw_session
    with database_connection(get_settings()) as connection:
        row = connection.execute(
            "SELECT subject_id FROM browser_sessions WHERE token_hash = ?",
            (secret_hash(raw_session),),
        ).fetchone()
    assert row
    return Principal(
        subject_id=row["subject_id"],
        kind="browser_user",
        scopes=frozenset({"demo:read", "demo:draft", "demo:commit"}),
        trusted_origin="test",
    )


def test_unknown_fixture_set_is_rejected(workflow_client: TestClient) -> None:
    response = workflow_client.post(
        "/api/v1/demo/workspaces",
        json={"fixture_set_id": "student-upload-marked-demo"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DEMO_ONLY"


def test_demo_mode_rejects_arbitrary_notice_and_requires_csrf(
    workflow_client: TestClient,
) -> None:
    workspace_ref, csrf = create_workspace(workflow_client)
    notice = json.loads(json.dumps(load_fixture("notice-event.demo.json")))
    notice["title"] = "看似 demo 但不是固定夹具"

    no_csrf = workflow_client.post(
        "/api/v1/tasks/drafts",
        headers={"Idempotency-Key": "task-draft-key-002"},
        json={"workspace_ref": workspace_ref, "notice": load_fixture("notice-event.demo.json")},
    )
    arbitrary = workflow_client.post(
        "/api/v1/tasks/drafts",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "task-draft-key-003"},
        json={"workspace_ref": workspace_ref, "notice": notice},
    )

    assert no_csrf.status_code == 403
    assert no_csrf.json()["error"]["code"] == "FORBIDDEN"
    assert arbitrary.status_code == 403
    assert arbitrary.json()["error"]["code"] == "DEMO_ONLY"


def test_demo_mode_rejects_arbitrary_timetable(workflow_client: TestClient) -> None:
    _, csrf = create_workspace(workflow_client)
    timetable = json.loads(json.dumps(load_fixture("timetable.demo.json")))
    timetable["courses"][0]["title"] = "客户端自定义但仍标记 demo"
    response = workflow_client.post(
        "/api/v1/schedules/import-drafts",
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "arbitrary-schedule-key-001",
        },
        json=timetable,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "DEMO_ONLY"


def test_task_confirmation_commit_and_idempotent_retry(workflow_client: TestClient) -> None:
    workspace_ref, csrf = create_workspace(workflow_client)
    first = create_task_draft(workflow_client, workspace_ref, csrf)
    retry = create_task_draft(workflow_client, workspace_ref, csrf)
    different_payload = create_task_draft(
        workflow_client,
        workspace_ref,
        csrf,
        fixture_name="notice-deadline.demo.json",
        key="task-draft-key-001",
    )

    assert first.status_code == 200
    assert retry.json()["data"]["draft_id"] == first.json()["data"]["draft_id"]
    assert different_payload.status_code == 409
    draft = first.json()["data"]

    confirmation_response = confirm_draft(workflow_client, csrf, draft)
    assert confirmation_response.status_code == 200
    confirmation_id = confirmation_response.json()["data"]["confirmation_id"]
    commit_payload = {
        "confirmation_id": confirmation_id,
        "idempotency_key": "task-commit-key-001",
    }
    committed = workflow_client.post(
        "/api/v1/tasks/commit",
        headers={"X-CSRF-Token": csrf},
        json=commit_payload,
    )
    retried = workflow_client.post(
        "/api/v1/tasks/commit",
        headers={"X-CSRF-Token": csrf},
        json=commit_payload,
    )
    replayed = workflow_client.post(
        "/api/v1/tasks/commit",
        headers={"X-CSRF-Token": csrf},
        json={"confirmation_id": confirmation_id, "idempotency_key": "task-commit-key-002"},
    )

    assert committed.status_code == 200
    assert retried.json()["data"] == committed.json()["data"]
    assert replayed.status_code == 409
    listed = workflow_client.get(
        "/api/v1/tasks",
        params={"workspace_ref": workspace_ref},
    )
    assert len(listed.json()["data"]) == 1
    assert listed.json()["data"][0]["task_id"] == committed.json()["data"]["task_id"]


def test_old_confirmation_and_wrong_owner_are_rejected(workflow_client: TestClient) -> None:
    workspace_ref, csrf = create_workspace(workflow_client)
    draft = create_task_draft(workflow_client, workspace_ref, csrf).json()["data"]
    confirmation = confirm_draft(workflow_client, csrf, draft).json()["data"]

    update_draft(
        get_settings(),
        current_principal(workflow_client),
        draft["draft_id"],
        load_fixture("notice-deadline.demo.json"),
    )
    stale = workflow_client.post(
        "/api/v1/tasks/commit",
        headers={"X-CSRF-Token": csrf},
        json={
            "confirmation_id": confirmation["confirmation_id"],
            "idempotency_key": "stale-commit-key-001",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STALE_REVISION"

    with TestClient(app) as other_client:
        _, other_csrf = create_workspace(other_client)
        hidden = other_client.get(f"/api/v1/drafts/{draft['draft_id']}")
        wrong_owner = other_client.post(
            "/api/v1/tasks/commit",
            headers={"X-CSRF-Token": other_csrf},
            json={
                "confirmation_id": confirmation["confirmation_id"],
                "idempotency_key": "wrong-owner-key-001",
            },
        )
    assert hidden.status_code == 404
    assert wrong_owner.status_code == 409
    assert wrong_owner.json()["error"]["code"] == "CONFIRMATION_REQUIRED"


def test_tampered_and_expired_confirmation_are_rejected(workflow_client: TestClient) -> None:
    workspace_ref, csrf = create_workspace(workflow_client)
    draft = create_task_draft(workflow_client, workspace_ref, csrf).json()["data"]
    tampered = dict(draft)
    tampered["payload_hash"] = "0" * 64
    rejected = confirm_draft(
        workflow_client, csrf, tampered, key="tampered-confirm-key-001"
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "STALE_REVISION"

    confirmation = confirm_draft(
        workflow_client, csrf, draft, key="expiring-confirm-key-001"
    ).json()["data"]
    with database_connection(get_settings()) as connection:
        connection.execute(
            "UPDATE confirmations SET expires_at = 0 WHERE confirmation_hash = ?",
            (secret_hash(confirmation["confirmation_id"]),),
        )
        connection.commit()
    expired = workflow_client.post(
        "/api/v1/tasks/commit",
        headers={"X-CSRF-Token": csrf},
        json={
            "confirmation_id": confirmation["confirmation_id"],
            "idempotency_key": "expired-confirm-key-001",
        },
    )
    assert expired.status_code == 410
    assert expired.json()["error"]["code"] == "TOKEN_EXPIRED"


def test_import_ticket_is_limited_one_time_and_schedule_commit_is_idempotent(
    workflow_client: TestClient,
) -> None:
    workspace_ref, csrf = create_workspace(workflow_client)
    ticket_response = workflow_client.post(
        "/api/v1/import-tickets",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "ticket-create-key-001"},
        json={"workspace_ref": workspace_ref, "purpose": "schedule_import"},
    )
    assert ticket_response.status_code == 200
    duplicate_ticket = workflow_client.post(
        "/api/v1/import-tickets",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "ticket-create-key-001"},
        json={"workspace_ref": workspace_ref, "purpose": "schedule_import"},
    )
    assert duplicate_ticket.status_code == 409
    ticket = ticket_response.json()["data"]["import_ticket"]
    with database_connection(get_settings()) as connection:
        stored = connection.execute(
            "SELECT token_hash FROM import_tickets WHERE workspace_ref = ?",
            (workspace_ref,),
        ).fetchone()["token_hash"]
    assert stored == secret_hash(ticket)
    assert ticket not in stored
    timetable = load_fixture("timetable.demo.json")
    headers = {
        "Authorization": f"ImportTicket {ticket}",
        "Idempotency-Key": "schedule-draft-key-001",
    }
    created = workflow_client.post(
        "/api/v1/schedules/import-drafts", headers=headers, json=timetable
    )
    retried = workflow_client.post(
        "/api/v1/schedules/import-drafts", headers=headers, json=timetable
    )
    replayed = workflow_client.post(
        "/api/v1/schedules/import-drafts",
        headers={
            "Authorization": f"ImportTicket {ticket}",
            "Idempotency-Key": "schedule-draft-key-002",
        },
        json=timetable,
    )
    assert created.status_code == 200
    assert retried.json()["data"] == created.json()["data"]
    assert replayed.status_code == 410
    assert replayed.json()["error"]["code"] == "TOKEN_EXPIRED"

    draft = created.json()["data"]
    confirmation = confirm_draft(
        workflow_client, csrf, draft, key="schedule-confirm-key-001"
    ).json()["data"]
    commit_payload = {
        "confirmation_id": confirmation["confirmation_id"],
        "idempotency_key": "schedule-commit-key-001",
    }
    committed = workflow_client.post(
        "/api/v1/schedules/commit",
        headers={"X-CSRF-Token": csrf},
        json=commit_payload,
    )
    retried_commit = workflow_client.post(
        "/api/v1/schedules/commit",
        headers={"X-CSRF-Token": csrf},
        json=commit_payload,
    )
    current = workflow_client.get(
        "/api/v1/schedules/current",
        params={"workspace_ref": workspace_ref},
    )
    assert committed.status_code == 200
    assert retried_commit.json()["data"] == committed.json()["data"]
    assert current.status_code == 200
    assert current.json()["data"]["timetable"] == timetable


def test_same_origin_session_can_create_schedule_draft(workflow_client: TestClient) -> None:
    _, csrf = create_workspace(workflow_client)
    missing_csrf = workflow_client.post(
        "/api/v1/schedules/import-drafts",
        headers={"Idempotency-Key": "browser-schedule-key-001"},
        json=load_fixture("timetable.demo.json"),
    )
    created = workflow_client.post(
        "/api/v1/schedules/import-drafts",
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "browser-schedule-key-002",
        },
        json=load_fixture("timetable.demo.json"),
    )

    assert missing_csrf.status_code == 403
    assert created.status_code == 200
    assert created.json()["data"]["kind"] == "schedule"


def test_expired_ticket_and_workspace_cleanup(workflow_client: TestClient) -> None:
    workspace_ref, csrf = create_workspace(workflow_client)
    ticket_response = workflow_client.post(
        "/api/v1/import-tickets",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "ticket-create-key-002"},
        json={"workspace_ref": workspace_ref, "purpose": "schedule_import"},
    )
    ticket = ticket_response.json()["data"]["import_ticket"]
    with database_connection(get_settings()) as connection:
        connection.execute(
            "UPDATE import_tickets SET expires_at = 0 WHERE token_hash = ?",
            (secret_hash(ticket),),
        )
        connection.commit()
    expired = workflow_client.post(
        "/api/v1/schedules/import-drafts",
        headers={
            "Authorization": f"ImportTicket {ticket}",
            "Idempotency-Key": "schedule-expired-key-001",
        },
        json=load_fixture("timetable.demo.json"),
    )
    assert expired.status_code == 410

    with database_connection(get_settings()) as connection:
        connection.execute(
            "UPDATE workspaces SET expires_at = 1 WHERE workspace_ref = ?",
            (workspace_ref,),
        )
        connection.commit()
    cleanup_expired(get_settings(), now=2)
    with database_connection(get_settings()) as connection:
        remaining = connection.execute(
            "SELECT COUNT(*) FROM workspaces WHERE workspace_ref = ?", (workspace_ref,)
        ).fetchone()[0]
    assert remaining == 0

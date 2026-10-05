"""D07/D08: real REST gates behind the controlled tasks page (fictional only)."""
from test_workflows import create_workspace, create_task_draft, confirm_draft, workflow_client  # noqa: F401
from app.core.config import get_settings
from app.db.database import database_connection
from app.main import app
from fastapi.testclient import TestClient


def test_ambiguous_notice_is_previewable_but_not_confirmable(workflow_client):
    workspace, csrf = create_workspace(workflow_client)
    draft = create_task_draft(workflow_client, workspace, csrf, "notice-ambiguous.demo.json").json()["data"]
    viewed = workflow_client.get(f"/api/v1/drafts/{draft['draft_id']}")
    assert viewed.status_code == 200
    assert viewed.json()["data"]["payload"]["due"]["at"] is None
    assert viewed.json()["data"]["payload"]["needs_confirmation"]
    rejected = confirm_draft(workflow_client, csrf, draft)
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert workflow_client.get("/api/v1/tasks", params={"workspace_ref": workspace}).json()["data"] == []


def test_deadline_stays_deadline_and_survives_app_restart(workflow_client):
    workspace, csrf = create_workspace(workflow_client)
    draft = create_task_draft(workflow_client, workspace, csrf, "notice-deadline.demo.json").json()["data"]
    assert workflow_client.get("/api/v1/tasks", params={"workspace_ref": workspace}).json()["data"] == []
    confirmation = confirm_draft(workflow_client, csrf, draft).json()["data"]
    payload = {"confirmation_id": confirmation["confirmation_id"], "idempotency_key": "deadline-commit-001"}
    committed = workflow_client.post("/api/v1/tasks/commit", headers={"X-CSRF-Token": csrf}, json=payload).json()["data"]
    with TestClient(app) as restarted:
        restarted.cookies.update(workflow_client.cookies)
        listed = restarted.get("/api/v1/tasks", params={"workspace_ref": workspace}).json()["data"]
        assert len(listed) == 1
        assert listed[0]["task_id"] == committed["task_id"]
        assert listed[0]["notice"]["event"]["start"] is None
        assert listed[0]["notice"]["due"]["at"] == "2026-09-21T10:10:00+08:00"
        retry = restarted.post("/api/v1/tasks/commit", headers={"X-CSRF-Token": csrf}, json=payload)
        assert retry.json()["data"] == committed


def test_expired_draft_cannot_be_confirmed_or_committed(workflow_client):
    workspace, csrf = create_workspace(workflow_client)
    draft = create_task_draft(workflow_client, workspace, csrf).json()["data"]
    confirmation = confirm_draft(workflow_client, csrf, draft).json()["data"]
    with database_connection(get_settings()) as db:
        db.execute("UPDATE drafts SET expires_at = 0 WHERE draft_id = ?", (draft["draft_id"],))
        db.commit()
    assert workflow_client.get(f"/api/v1/drafts/{draft['draft_id']}").status_code == 410
    assert confirm_draft(workflow_client, csrf, draft, "expired-draft-confirm").status_code == 410
    rejected = workflow_client.post("/api/v1/tasks/commit", headers={"X-CSRF-Token": csrf}, json={
        "confirmation_id": confirmation["confirmation_id"], "idempotency_key": "expired-draft-commit",
    })
    assert rejected.status_code == 410


def test_expired_workspace_denies_detail_and_idempotent_retry(workflow_client):
    workspace, csrf = create_workspace(workflow_client)
    draft = create_task_draft(workflow_client, workspace, csrf).json()["data"]
    confirmation = confirm_draft(workflow_client, csrf, draft).json()["data"]
    payload = {"confirmation_id": confirmation["confirmation_id"], "idempotency_key": "workspace-commit-001"}
    committed = workflow_client.post("/api/v1/tasks/commit", headers={"X-CSRF-Token": csrf}, json=payload).json()["data"]
    with database_connection(get_settings()) as db:
        db.execute("UPDATE workspaces SET expires_at = 0 WHERE workspace_ref = ?", (workspace,))
        db.commit()
    assert workflow_client.get(f"/api/v1/tasks/{committed['task_id']}").status_code == 404
    assert workflow_client.get(f"/api/v1/drafts/{draft['draft_id']}").status_code == 404
    assert workflow_client.post("/api/v1/tasks/commit", headers={"X-CSRF-Token": csrf}, json=payload).status_code == 404

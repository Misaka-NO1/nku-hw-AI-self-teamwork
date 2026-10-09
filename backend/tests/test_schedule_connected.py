"""Connected Import/Timetable REST sequence; true database reads, fictional only."""
from test_workflows import workflow_client, create_workspace, confirm_draft  # noqa: F401
from app.core.demo import load_fixture
from app.main import app
from fastapi.testclient import TestClient


def test_confirmed_schedule_survives_restart_and_is_used_for_free_time(workflow_client):
    workspace, csrf = create_workspace(workflow_client)
    missing = workflow_client.get("/api/v1/schedules/current", params={"workspace_ref": workspace})
    assert missing.status_code == 404  # No fake fallback to the public fixture.
    payload = load_fixture("timetable.demo.json")
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "connected-schedule-draft"}
    created = workflow_client.post("/api/v1/schedules/import-drafts", headers=headers, json=payload)
    assert created.status_code == 200
    draft = created.json()["data"]
    assert workflow_client.get("/api/v1/schedules/current", params={"workspace_ref": workspace}).status_code == 404
    confirmation = confirm_draft(workflow_client, csrf, draft).json()["data"]
    commit = {"confirmation_id": confirmation["confirmation_id"], "idempotency_key": "connected-schedule-commit"}
    response = workflow_client.post("/api/v1/schedules/commit", headers={"X-CSRF-Token": csrf}, json=commit)
    assert response.status_code == 200
    with TestClient(app) as restarted:
        restarted.cookies.update(workflow_client.cookies)
        saved = restarted.get("/api/v1/schedules/current", params={"workspace_ref": workspace}).json()["data"]
        assert saved["timetable"] == payload
        assert saved["schedule_id"] == response.json()["data"]["schedule_id"]
        assert restarted.post("/api/v1/schedules/commit", headers={"X-CSRF-Token": csrf}, json=commit).json()["data"] == response.json()["data"]
        query = {**load_fixture("time-free-query.demo.json"), "workspace_ref": workspace}
        result = restarted.post("/api/v1/time/free-slots", json=query)
        assert result.status_code == 200
        assert result.json()["data"]["kind"] == "free_time"
        assert result.json()["meta"]["request_id"]


def test_schedule_isolation_and_no_csrf_import(workflow_client):
    first_workspace, first_csrf = create_workspace(workflow_client)
    payload = load_fixture("timetable.demo.json")
    denied = workflow_client.post("/api/v1/schedules/import-drafts", json=payload, headers={"Idempotency-Key": "no-csrf-schedule"})
    assert denied.status_code == 403
    draft = workflow_client.post("/api/v1/schedules/import-drafts", json=payload,
        headers={"X-CSRF-Token": first_csrf, "Idempotency-Key": "isolated-schedule"}).json()["data"]
    create_workspace(workflow_client)  # Another browser identity, not the first owner.
    assert workflow_client.get(f"/api/v1/drafts/{draft['draft_id']}").status_code == 404
    assert workflow_client.get("/api/v1/schedules/current", params={"workspace_ref": first_workspace}).status_code == 404

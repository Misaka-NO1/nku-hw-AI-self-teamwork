"""Workflow orchestration over the real private PG RPC and B engine."""
from copy import deepcopy
import json
import os
from pathlib import Path
import pytest
from app.core.errors import AppError
from app.domains.tasks.notice_model_reader import read_model_output
from app.cloud_identity_site import create_cloud_identity_site
from fastapi.testclient import TestClient
from test_cloud_notice_text import notice_env, read_request, query, post, draft, confirm, commit
from test_cloud_identity_site import environment, login, save, ORIGIN


def workflow_request(**changes):
    checked = query()
    return {"read": read_request(), "analysis": {
        "item_index": 0, **{k: checked[k] for k in
            ("window", "available_windows", "user_confirmations")}, **changes}}


def test_workflow_does_not_write_and_confirmed_plan_saves_readback(notice_env):
    _, _, _, client = notice_env
    owner = login(client)
    save(client, owner, "schedule", "timetable.demo.json")
    extracted = post(client, owner, "workflow", {"read": read_request(), "analysis": None})
    assert extracted.status_code == 200, extracted.text
    assert extracted.json()["data"]["stage"] == "source_review"
    result = post(client, owner, "workflow", workflow_request())
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["stage"] == "selection_required" and data["saved"] is False
    assert data["steps"][1]["status"] == "calculated"
    assert result.json()["meta"]["calculation_version"]
    assert client.get("/api/v1/notice-text/tasks").json()["data"]["total"] == 0
    plan = data["analysis"]["plan"]
    plan["selected_slot"] = data["analysis"]["time_result"]["candidate_slots"][0]
    created = draft(client, owner, plan)
    result = commit(client, owner, confirm(client, owner, created))
    assert result.status_code == 200
    task = client.get("/api/v1/notice-text/tasks/" + result.json()["data"]["task_id"]).json()["data"]
    assert task["notice"]["notice"]["due"]["at"] == "2026-09-21T10:10:00+08:00"
    assert task["notice"]["selected_slot"]["start"] == "2026-09-21T09:40:00+08:00"


def test_workflow_needs_missing_fields_and_rejects_identity_overrides(notice_env):
    _, _, _, client = notice_env
    owner = login(client)
    save(client, owner, "schedule", "timetable.demo.json")
    payload = workflow_request(user_confirmations={})
    data = post(client, owner, "workflow", payload).json()["data"]
    assert data["stage"] == "clarification_required"
    assert data["analysis"]["time_result"]["candidate_slots"] == []
    for location in ("read", "analysis"):
        bad = deepcopy(payload)
        bad[location]["owner"] = "other"
        assert post(client, owner, "workflow", bad).status_code == 422
    assert post(client, owner, "workflow", workflow_request(item_index=1)).status_code == 422
    assert post(client, owner, "workflow", workflow_request(item_index=True)).status_code == 422


def test_workflow_uses_current_own_tasks_and_expired_historical_date(notice_env):
    _, _, _, client = notice_env
    owner = login(client)
    save(client, owner, "schedule", "timetable.demo.json")
    payload = workflow_request()
    data = post(client, owner, "workflow", payload).json()["data"]
    plan = data["analysis"]["plan"]
    plan["selected_slot"] = data["analysis"]["time_result"]["candidate_slots"][0]
    assert commit(client, owner, confirm(client, owner, draft(client, owner, plan))).status_code == 200
    checked = post(client, owner, "workflow", payload).json()["data"]
    assert checked["analysis"]["time_result"]["candidate_slots"] == []
    assert checked["stage"] == "no_available_slot"
    assert checked["analysis"]["item"]["notice"]["due"]["date"] == "2026-09-21"


@pytest.mark.parametrize("name", ["first-failure", "span-failure", "duration-failure"])
def test_real_school_failures_remain_rejected(name):
    path = Path(__file__).parents[2] / "docs/evidence/platform" / f"D14-genios-{name}-2026-10-06.json"
    artifact = json.loads(path.read_text(encoding="utf-8"))
    raw = next(line.removeprefix('"extraction":"')[:-1]
               for line in artifact["visible_node_result"].splitlines()
               if line.startswith('"extraction":"'))
    with pytest.raises(AppError):
        read_model_output(**{k: artifact["source"][k] for k in
            ("source_text", "source_ref", "reference_at")}, model_output=raw)


def test_actual_school_model_to_pg_analysis_save_restart(notice_env):
    root_path = Path(__file__).parents[2]
    artifact = json.loads((root_path / "docs/evidence/platform/D14-genios-model-success-2026-10-06.json").read_text(encoding="utf-8"))
    settings, root, db, client = notice_env
    owner = login(client)
    save(client, owner, "schedule", "timetable.demo.json")
    source = {**artifact["source"], "model_output": artifact["model_output"]}
    read = post(client, owner, "workflow", {"read": source, "analysis": None}).json()["data"]
    assert len(read["batch"]["items"]) == 3
    assert read["batch"]["coverage"]["unread_ranges"] == []
    analysis = workflow_request()["analysis"]
    analysis["user_confirmations"]["due_at"] = "2026-09-21T10:10:00+08:00"
    result = post(client, owner, "workflow", {"read": source, "analysis": analysis})
    assert result.status_code == 200, result.text
    deadline = result.json()["data"]
    assert deadline["stage"] == "selection_required"
    assert deadline["analysis"]["time_result"]["candidate_slots"][0]["start"] == "2026-09-21T09:40:00+08:00"
    plan = deadline["analysis"]["plan"]
    plan["selected_slot"] = deadline["analysis"]["time_result"]["candidate_slots"][0]
    ticket = confirm(client, owner, draft(client, owner, plan))
    saved = commit(client, owner, ticket)
    assert saved.status_code == 200, saved.text
    assert commit(client, owner, ticket).json()["data"] == saved.json()["data"]
    event_selection = {**analysis, "item_index": 1, "user_confirmations": {
        "source_review": True, "event_start": "2026-09-21T11:00:00+08:00",
        "event_end": "2026-09-21T11:30:00+08:00", "accept_conflicts": True}}
    event = post(client, owner, "workflow", {"read": source, "analysis": event_selection}).json()["data"]
    assert event["stage"] == "confirmation_required"
    assert event["analysis"]["time_result"]["conflicts"]
    event_draft = draft(client, owner, event["analysis"]["plan"], "school-event-draft")
    event_saved = commit(client, owner, confirm(client, owner, event_draft, "school-event-confirm"), "school-event-commit")
    assert event_saved.status_code == 200, event_saved.text
    ambiguous = post(client, owner, "workflow", {"read": source, "analysis": {
        **analysis, "item_index": 2, "user_confirmations": {"source_review": True}}}).json()["data"]
    assert ambiguous["stage"] == "clarification_required"
    assert ambiguous["analysis"]["item"]["notice"]["due"]["at"] is None
    assert ambiguous["analysis"]["time_result"]["candidate_slots"] == []
    blocked = post(client, owner, "drafts", {"plan": ambiguous["analysis"]["plan"]}, "school-ambiguous-draft")
    assert blocked.status_code == 409
    readback = client.get("/api/v1/notice-text/tasks").json()["data"]
    assert readback["total"] == 2
    first_task = client.get("/api/v1/notice-text/tasks/" + saved.json()["data"]["task_id"]).json()["data"]
    assert first_task["notice"]["model_output"] == artifact["model_output"]
    assert first_task["notice"]["notice"]["due"]["at"] == "2026-09-21T10:10:00+08:00"
    assert first_task["notice"]["selected_slot"]["end"] == "2026-09-21T10:00:00+08:00"
    with TestClient(create_cloud_identity_site(root, db, settings), base_url=ORIGIN) as restarted:
        restarted.cookies.set("campus_session", client.cookies.get("campus_session"))
        assert restarted.get("/api/v1/notice-text/tasks").json()["data"] == readback
    if os.getenv("NOTICE_WORKFLOW_WRITE_EVIDENCE") == "1":
        evidence = {"mode": "local_http_embedded_postgresql_mocked_fictional_identity",
            "application_instance_recreated_with_existing_database": True,
            "database_process_restart_tested": False,
            "school_workflow_url": artifact["workflow_url"], "school_model_output_unchanged": True,
            "deadline_analysis": deadline, "event_analysis": event,
            "ambiguous_analysis": ambiguous, "ambiguous_write_http_status": blocked.status_code,
            "deadline_commit": saved.json()["data"], "event_commit": event_saved.json()["data"],
            "task_readback": readback, "http_service_restart_readback_equal": True,
            "cloud_deployed": False}
        (root_path / "docs/evidence/platform/D14-school-model-local-pg-readback-2026-10-06.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

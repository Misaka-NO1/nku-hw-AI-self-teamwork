"""Actual embedded PostgreSQL ownership tests, NOT live cloud acceptance."""
import json
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.cloud_identity_site import create_cloud_identity_site
from app.core.contracts import validate_boundary
from app.core.security import secret_hash
from test_cloud_identity_site import environment, login, headers, save, ORIGIN
from test_competition_oauth import PARAMS, exchange


@pytest.fixture
def personal(environment):
    settings, root, store, _ = environment
    runtime = settings.model_copy(update={
        "cloud_oauth_competition_compat_enabled": True,
        "cloud_notice_text_pilot_enabled": True,
        "cloud_task_calendar_enabled": True,
        "cloud_personal_tasks_enabled": True,
    })
    with TestClient(create_cloud_identity_site(root, store, runtime), base_url=ORIGIN) as client:
        yield client, store, runtime, root


def draft(client, owner, title="A own reminder", key="own-draft-001", **fields):
    return client.post("/api/v1/tasks/entries/drafts", headers=headers(owner), json={
        "content": {"title": title, **fields}, "idempotency_key": key})


def commit(client, owner, value, key="own-commit-001", **changes):
    return client.post("/api/v1/tasks/entries/commit", headers=headers(owner), json={
        "draft_id": value["draft_id"], "payload_hash": value["payload_hash"],
        "confirmed": True, "idempotency_key": key, **changes})


def calendar(client, owner):
    return client.get("/api/v1/tasks/calendar", params={"workspace_ref": owner["workspace_ref"]})


def grant(client, scope="demo:read tasks:read tasks:write"):
    page = client.get("/oauth/authorize", params={**PARAMS, "scope": scope})
    assert page.status_code == 200, page.text
    txn = re.search(r'name="transaction" value="([^"]+)"', page.text)[1]
    callback = client.post("/oauth/approve", headers={"Origin": ORIGIN},
        data={"transaction": txn, "decision": "allow"}, follow_redirects=False)
    assert callback.status_code == 303, callback.text
    code = parse_qs(urlsplit(callback.headers["location"]).query)["code"][0]
    result = exchange(client, code)
    assert result.status_code == 200, result.text
    assert result.json()["scope"] == scope
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def test_browser_owner_isolation_csrf_forgery_and_two_distinct_timetables(personal):
    client, _, _, _ = personal
    a = login(client)
    save(client, a, "schedule", "timetable.demo.json", key="own-a-schedule")
    a_schedule = client.get("/api/v1/schedules/current", params={"workspace_ref": a["workspace_ref"]}).json()["data"]
    created = draft(client, a).json()["data"]
    assert commit(client, a, created, confirmed=False).status_code == 422
    saved = commit(client, a, created)
    assert saved.status_code == 200, saved.text
    entry = saved.json()["data"]["item"]
    assert saved.json()["data"]["readback_verified"] is True
    assert entry["scheduled_start"] is None  # Reminder never needs an end.
    validate_boundary(entry, "CalendarTask")
    validate_boundary(calendar(client, a).json()["data"], "CalendarTaskList")
    assert commit(client, a, created).json()["data"]["item"] == entry

    b = login(client, "fictional-b")
    assert calendar(client, b).json()["data"]["items"] == []
    assert calendar(client, a).status_code == 404
    assert client.get("/api/v1/schedules/current", params={"workspace_ref": a["workspace_ref"]}).status_code == 404
    assert client.get("/api/v1/schedules/current", params={"workspace_ref": b["workspace_ref"]}).status_code == 404
    assert commit(client, b, created, key="b-steal-draft-001").status_code == 404
    assert draft(client, a, key="b-old-a-csrf").status_code == 403
    for body in ({"user_id": "fictional-a"}, {"owner_subject_id": "fictional-a"}, {"workspace_ref": a["workspace_ref"]}):
        assert client.post("/api/v1/tasks/entries/drafts", headers=headers(b), json={
            "content": {"title": "forged", **body}, "idempotency_key": "forged-entry-001"}).status_code == 422
    assert client.post("/api/v1/tasks/entries/drafts?user_id=fictional-a", headers=headers(b),
        json={"content": {"title": "forged"}, "idempotency_key": "forged-query-001"}).status_code == 422
    save(client, b, "schedule", "timetable.demo.json", key="own-b-schedule")
    b_schedule = client.get("/api/v1/schedules/current", params={"workspace_ref": b["workspace_ref"]}).json()["data"]
    assert a_schedule["schedule_id"] != b_schedule["schedule_id"]
    b_draft = draft(client, b, title="B own", key="own-b-draft").json()["data"]
    b_entry = commit(client, b, b_draft, key="own-b-commit").json()["data"]["item"]
    update = {"workspace_ref": b["workspace_ref"], "expected_revision": entry["calendar_revision"],
        "status": "completed", "scheduled_start": None, "scheduled_end": None, "reminder_minutes": None}
    assert client.post(f'/api/v1/tasks/{entry["task_id"]}/calendar', headers=headers(b), json=update).status_code == 404
    assert [t["task_id"] for t in calendar(client, b).json()["data"]["items"]] == [b_entry["task_id"]]
    a = login(client)
    assert [t["task_id"] for t in calendar(client, a).json()["data"]["items"]] == [entry["task_id"]]


def test_oauth_stays_bound_to_issuing_owner_and_old_scope_does_not_upgrade(personal):
    client, _, _, _ = personal
    a = login(client)
    legacy = grant(client, "demo:read")
    read_only = grant(client, "demo:read tasks:read")
    a_grant = grant(client)
    request = {"content": {"title": "A agent entry", "kind": "deadline", "due_date": "2026-10-09"},
        "idempotency_key": "agent-a-draft"}
    path = "/oauth/tasks/entries/drafts"
    assert client.get("/oauth/tasks/entries", headers=legacy).status_code == 403
    for bearer in (legacy, read_only):
        assert client.post(path, headers=bearer, json={"query_json": json.dumps(request)}).status_code == 403
    response = client.post(path, headers=a_grant, json={"query_json": json.dumps(request)})
    assert response.status_code == 200, response.text
    d = response.json()["data"]
    b = login(client, "fictional-b")
    b_grant = grant(client)
    payload = {"draft_id": d["draft_id"], "payload_hash": d["payload_hash"], "confirmed": True,
        "idempotency_key": "agent-a-commit"}
    assert client.post("/oauth/tasks/entries/commit", headers=b_grant,
        json={"query_json": json.dumps(payload)}).status_code == 404
    result = client.post("/oauth/tasks/entries/commit", headers=a_grant, json={"query_json": json.dumps(payload)})
    assert result.status_code == 200, result.text
    task_id = result.json()["data"]["item"]["task_id"]
    assert client.get("/oauth/tasks/entries", headers=b_grant).json()["data"]["items"] == []
    assert client.get("/oauth/tasks/entries", headers=read_only).json()["data"]["items"][0]["task_id"] == task_id
    assert client.get("/oauth/records", headers=legacy).json()["data"]["tasks"] == []
    assert calendar(client, b).json()["data"]["items"] == []
    assert client.get("/oauth/tasks/entries?owner_subject_id=fictional-b", headers=a_grant).status_code == 400


def test_stable_owner_persistence_restart_workspace_renewal_and_expired_session(personal):
    client, store, runtime, root = personal
    a = login(client)
    d = draft(client, a, kind="deadline", due_date="2026-10-09").json()["data"]
    result = commit(client, a, d).json()["data"]["item"]
    with TestClient(create_cloud_identity_site(root, store, runtime), base_url=ORIGIN) as restarted:
        for name, value in dict(client.cookies).items():
            restarted.cookies.set(name, value)
        assert calendar(restarted, a).json()["data"]["items"] == [result]
        store.call("__test_expire_browser_session__", {"token_hash": secret_hash(restarted.cookies.get("campus_session"))})
        assert calendar(restarted, a).status_code == 401
    store.call("__test_expire_workspace__", {"workspace_ref": a["workspace_ref"]})
    renewed = login(client)
    assert renewed["workspace_ref"] != a["workspace_ref"]
    assert calendar(client, renewed).json()["data"]["items"] == [result]
    b = login(client, "fictional-b")
    assert calendar(client, b).json()["data"]["items"] == []


def test_multi_slot_busy_resources_and_reminder_not_a_busy_interval(personal):
    from app.core.notice_plan import resources
    from app.core.task_calendar import TaskCalendarService
    client, store, runtime, _ = personal
    a = login(client)
    save(client, a, "schedule", "timetable.demo.json", key="resources-schedule")
    slots = [{"start": "2026-10-08T16:00:00+08:00", "end": "2026-10-08T17:00:00+08:00"},
             {"start": "2026-10-09T18:00:00+08:00", "end": "2026-10-09T19:00:00+08:00"}]
    d = draft(client, a, kind="deadline", due_at="2026-10-09T21:40:00+08:00", scheduled_slots=slots).json()["data"]
    assert commit(client, a, d).status_code == 200
    point = draft(client, a, key="reminder-point-draft", reminder_at="2026-10-08T15:00:00+08:00").json()["data"]
    assert commit(client, a, point, key="reminder-point-commit").status_code == 200
    args = {"principal_kind": "browser", "session_hash": secret_hash(client.cookies.get("campus_session")), "csrf_hash": secret_hash(a["csrf_token"])}
    records = TaskCalendarService(runtime, store).records(args)
    _, notices, _ = resources(records)
    assert [(n["event"]["start"], n["event"]["end"]) for n in notices] == [(s["start"], s["end"]) for s in slots]


def test_direct_rpc_owner_injection_csrf_and_idempotency_are_rejected(personal):
    from app.core.errors import AppError
    client, store, _, _ = personal
    a = login(client)
    args = {"principal_kind": "browser", "session_hash": secret_hash(client.cookies.get("campus_session")),
        "csrf_hash": secret_hash(a["csrf_token"])}
    for extra in ({"owner_subject_id": "fictional-b"}, {"workspace_ref": "other"}):
        with pytest.raises(AppError) as error:
            store.personal_call("records", {**args, **extra})
        assert error.value.status_code == 422
    d = draft(client, a).json()["data"]
    forged = {**args, "csrf_hash": secret_hash("not-csrf"), "draft_id": d["draft_id"],
        "payload_hash": d["payload_hash"], "task_id": "entry_forged", "key": "forged-commit",
        "request_hash": "f" * 64}
    with pytest.raises(AppError) as error:
        store.personal_call("commit", forged)
    assert error.value.status_code == 403
    saved = commit(client, a, d).json()["data"]["item"]
    assert draft(client, a, title="Changed title with same key").status_code == 409
    b = login(client, "fictional-b")
    b_draft = draft(client, b, title="B same idempotency key").json()["data"]
    b_task = commit(client, b, b_draft).json()["data"]["item"]
    assert saved["task_id"] != b_task["task_id"]
    assert len(calendar(client, b).json()["data"]["items"]) == 1
    bearer = grant(client)
    client.post("/api/v1/auth/cloudbase/logout", headers=headers(b))
    assert client.get("/oauth/tasks/entries", headers=bearer).status_code == 401

"""Actual owner RPC / B calculations. Clock is controlled only in test code."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import os

import pytest
from fastapi.testclient import TestClient
from app.cloud_identity_site import create_cloud_identity_site
from app.core.task_calendar import TZ, TaskCalendarService
from app.core.contracts import validate_boundary
from test_cloud_identity_site import environment, login, save, headers, ORIGIN, authorize, exchange
from test_cloud_notice_text import query, plan, draft, confirm, commit

NOW = datetime(2026, 9, 21, 8, 0, tzinfo=TZ)


@pytest.fixture
def calendar_env(environment, monkeypatch):
    settings, root, db, _ = environment
    runtime = settings.model_copy(update={"cloud_notice_text_pilot_enabled": True, "cloud_task_calendar_enabled": True})
    monkeypatch.setattr("app.core.task_calendar.calendar_now", lambda: NOW)
    db.call("__test_calendar_clock__", {"epoch": int(NOW.timestamp())})
    with TestClient(create_cloud_identity_site(root, db, runtime), base_url=ORIGIN) as client:
        owner = login(client)
        save(client, owner, "schedule", "timetable.demo.json")
        yield runtime, root, db, client, owner


def new_task(client, owner, text=None, key="calendar-task", **changes):
    payload = query(**changes) if text is None else query(text=text, **changes)
    saved = commit(client, owner, confirm(client, owner, draft(client, owner,
        plan(client, owner, payload), key + "-draft"), key + "-confirm"), key + "-commit")
    assert saved.status_code == 200, saved.text
    return saved.json()["data"]["task_id"]


def listing(client, owner):
    response = client.get("/api/v1/tasks/calendar", params={"workspace_ref": owner["workspace_ref"]})
    assert response.status_code == 200, response.text
    validate_boundary(response.json()["data"], "CalendarTaskList")
    return response.json()["data"]


def candidates(client, owner, task_id):
    return client.get(f"/api/v1/tasks/{task_id}/calendar/candidates",
        params={"workspace_ref": owner["workspace_ref"]})


def body(owner, task, **changes):
    return {"workspace_ref": owner["workspace_ref"], "expected_revision": task["calendar_revision"],
        **{k: task[k] for k in ("status", "scheduled_start", "scheduled_end", "reminder_minutes")}, **changes}


def update(client, owner, task_id, payload, key="calendar-update-key"):
    return client.post(f"/api/v1/tasks/{task_id}/calendar", json=payload, headers=headers(owner, key))


def test_full_original_notice_and_default_arrangement_static_route(calendar_env):
    _, _, _, client, owner = calendar_env
    saved = new_task(client, owner)
    data = listing(client, owner)
    assert data["capabilities"] == {"scheduling": True, "status": True, "reminders": True, "deletion": True}
    item = data["items"][0]
    assert item["task_id"] == saved and len(item["notice"]) == 13
    assert item["scheduled_start"] == "2026-09-21T09:40:00+08:00"
    assert item["notice"]["due"]["at"] == "2026-09-21T10:10:00+08:00"
    assert item["calendar_revision"] == 0 and item["reminder_minutes"] is None
    assert client.get("/tools/calendar").status_code == 200
    result = candidates(client, owner, saved).json()["data"]
    validate_boundary(result, "CalendarCandidates")
    # PR12's Nankai period 3 now starts at 10:00, not the old demo 10:10.
    assert result["candidate_slots"] == [{"start": "2026-09-21T09:40:00+08:00", "end": "2026-09-21T10:00:00+08:00", "duration_minutes": 20}]


def test_reschedule_retry_cas_reminders_readback_restart(calendar_env):
    settings, root, db, client, owner = calendar_env
    saved = new_task(client, owner, minutes=10)
    task = listing(client, owner)["items"][0]
    original = deepcopy(task["notice"])
    payload = body(owner, task, scheduled_start="2026-09-21T09:45:00+08:00",
        scheduled_end="2026-09-21T09:55:00+08:00", reminder_minutes=0)
    changed = update(client, owner, saved, payload)
    assert changed.status_code == 200, changed.text
    validate_boundary(changed.json()["data"], "CalendarTask")
    assert changed.json()["data"]["calendar_revision"] == 1
    assert update(client, owner, saved, payload).json()["data"] == changed.json()["data"]
    assert update(client, owner, saved, {**payload, "reminder_minutes": 15}).status_code == 409
    assert update(client, owner, saved, payload, "different-calendar-key").status_code == 409
    readback = listing(client, owner)["items"][0]
    assert readback["notice"] == original and readback["reminder_minutes"] == 0
    assert readback == changed.json()["data"]
    with TestClient(create_cloud_identity_site(root, db, settings), base_url=ORIGIN) as restarted:
        restarted.cookies.set("campus_session", client.cookies.get("campus_session"))
        assert listing(restarted, owner)["items"][0] == readback
    if os.getenv("CALENDAR_WRITE_EVIDENCE") == "1":
        Path(__file__).parents[2].joinpath("docs/evidence/platform/D15-calendar-pg-readback-2026-10-06.json").write_text(
            json.dumps({"mode": "isolated_fictional_pg_clock_2026_09_21", "cloud_deployed": False,
                "original": task, "request": payload, "saved": readback,
                "application_instance_recreated": True, "database_process_restarted": False}, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("status", ["completed", "cancelled"])
def test_release_restore_and_time_adapter_share_busy_state(calendar_env, status):
    _, _, _, client, owner = calendar_env
    saved = new_task(client, owner)
    task = listing(client, owner)["items"][0]
    window = {"start": "2026-09-21T09:40:00+08:00", "end": "2026-09-21T10:10:00+08:00"}
    request = {"workspace_ref": owner["workspace_ref"], "window": window, "min_minutes": 20,
        "buffers": {"before_minutes": 0, "after_minutes": 0}}
    free = lambda: client.post("/api/v1/time/free-slots", json=request).json()["data"]["slots"]
    assert free() == []
    changed = update(client, owner, saved, body(owner, task, status=status), "calendar-release-key")
    assert changed.status_code == 200, changed.text
    assert free()[0]["duration_minutes"] == 20
    released = listing(client, owner)["items"][0]
    restored = update(client, owner, saved, body(owner, released, status="pending"), "calendar-restore-key")
    assert restored.status_code == 200, restored.text
    assert free() == []
    # Another task occupies the old slot after cancellation: restore must fail.
    changed = update(client, owner, saved, body(owner, listing(client, owner)["items"][0], status="cancelled"), "calendar-release-again")
    assert changed.status_code == 200
    new_task(client, owner, "请在2026年9月21日10:10前提交虚构另一份设计，材料：设计PDF。", "other-calendar-task")
    old = next(t for t in listing(client, owner)["items"] if t["task_id"] == saved)
    assert update(client, owner, saved, body(owner, old, status="pending"), "calendar-conflicting-restore").status_code == 409


@pytest.mark.parametrize("change", [
    {"scheduled_end": None}, {"scheduled_end": "2026-09-21T09:30:00+08:00"},
    {"scheduled_start": "2026-09-21T09:40:00", "scheduled_end": "2026-09-21T10:00:00"},
    {"scheduled_start": "2026-09-21T09:40:00+08:00", "scheduled_end": "2026-09-21T10:10:00+08:00"},
    {"scheduled_start": "2026-09-21T10:00:00+08:00", "scheduled_end": "2026-09-21T10:20:00+08:00"},
    {"scheduled_start": "2026-09-21T09:20:00+08:00", "scheduled_end": "2026-09-21T09:40:00+08:00"},
    {"reminder_minutes": False}, {"reminder_minutes": 10}, {"status": "deleted"}, {"owner": "other"},
])
def test_bad_writes_never_change_calendar(calendar_env, change):
    _, _, _, client, owner = calendar_env
    saved = new_task(client, owner)
    before = listing(client, owner)
    result = update(client, owner, saved, {**body(owner, before["items"][0]), **change})
    assert result.status_code in (422, 409), result.text
    assert listing(client, owner) == before


def test_courses_fixed_events_and_source_limits(calendar_env):
    _, _, _, client, owner = calendar_env
    _, fixture = save(client, owner)
    event = next(t for t in listing(client, owner)["items"] if t["task_id"] == fixture["task_id"])
    assert candidates(client, owner, event["task_id"]).json()["data"]["fixed_event"] is True
    assert update(client, owner, event["task_id"], body(owner, event, scheduled_start=None, scheduled_end=None)).status_code == 422
    late = new_task(client, owner, "请在2026年9月21日12:30前提交虚构补充设计。", "calendar-late-task",
        window={"start": "2026-09-21T08:00:00+08:00", "end": "2026-09-21T13:00:00+08:00"},
        user_confirmations={"source_review": True, "estimated_minutes": 20, "earliest_start": "2026-09-21T11:50:00+08:00"},
        available_windows=[{"start": "2026-09-21T11:50:00+08:00", "end": "2026-09-21T12:20:00+08:00"}])
    task = next(t for t in listing(client, owner)["items"] if t["task_id"] == late)
    assert update(client, owner, late, body(owner, task, scheduled_start="2026-09-21T11:00:00+08:00", scheduled_end="2026-09-21T11:20:00+08:00")).status_code == 409
    assert update(client, owner, late, body(owner, task, scheduled_start="2026-09-21T12:10:00+08:00", scheduled_end="2026-09-21T12:30:00+08:00"), "outside-source-limits").status_code == 409


def test_today_expired_fixtures_no_date_shift_and_expired_coverage(calendar_env, monkeypatch):
    _, _, _, client, owner = calendar_env
    saved = new_task(client, owner)
    monkeypatch.setattr("app.core.task_calendar.calendar_now", lambda: datetime(2026,10,6,8,0,tzinfo=TZ))
    data = candidates(client, owner, saved).json()["data"]
    assert data["candidate_slots"] == [] and data["reason"] == "deadline_passed_or_no_remaining_time"
    assert listing(client, owner)["items"][0]["notice"]["due"]["at"].startswith("2026-09-21")
    future = new_task(client, owner, "请在2026年10月7日12:00前提交虚构未来设计。", "calendar-future-task",
        window={"start":"2026-10-07T08:00:00+08:00","end":"2026-10-07T12:00:00+08:00"},
        user_confirmations={"source_review": True,"estimated_minutes":20,"earliest_start":"2026-10-07T09:00:00+08:00"})
    result = candidates(client, owner, future).json()["data"]
    assert result["needs_confirmation"] == ["timetable_outside_term"] and result["candidate_slots"] == []


def test_identity_csrf_summary_and_read_only_oauth(calendar_env):
    _, _, db, client, owner = calendar_env
    saved = new_task(client, owner)
    task = listing(client, owner)["items"][0]
    assert client.post(f"/api/v1/tasks/{saved}/calendar", json=body(owner, task), headers={"Origin": ORIGIN, "Idempotency-Key": "no-csrf-key"}).status_code == 403
    assert client.get("/api/v1/tasks/calendar", params={"workspace_ref": "foreign"}).status_code == 404
    summary = client.get("/api/v1/tasks/calendar/summary", params={"workspace_ref":owner["workspace_ref"]}).json()["data"]
    validate_boundary(summary, "CalendarSummary")
    assert summary["pending_count"] == 1 and summary["today_count"] == 1 and summary["background_push"] is False
    token = exchange(client, authorize(client,"demo:read")).json()["access_token"]
    auth = {"Authorization": "Bearer " + token}
    response = client.get("/oauth/tasks/summary", headers=auth)
    assert response.status_code == 200 and response.json()["data"] == summary
    a_cookie = client.cookies.get("campus_session")
    other = login(client,"fictional-b")
    assert listing(client, other)["items"] == []
    assert candidates(client, other, saved).status_code == 404
    assert update(client, other, saved, {**body(owner, task), "workspace_ref":other["workspace_ref"]}).status_code == 404
    assert client.get("/oauth/tasks/summary", headers=auth).json()["data"] == summary
    client.cookies.set("campus_session", a_cookie)
    db.call("__test_expire_browser_session__", {"token_hash": __import__('app.core.security',fromlist=['secret_hash']).secret_hash(a_cookie)})
    assert client.get("/api/v1/tasks/calendar", params={"workspace_ref":owner["workspace_ref"]}).status_code == 401
    assert client.get("/oauth/tasks/summary", headers=auth).status_code == 401


def test_concurrent_change_after_validation_rejected_in_pg(calendar_env, monkeypatch):
    _, _, db, client, owner = calendar_env
    saved = new_task(client, owner)
    task = listing(client, owner)["items"][0]
    original = db.calendar_call
    def race(op,args):
        if op == "update" and args["key"] == "race-calendar-write":
            competing = {**args,"state":body(owner,task,status="completed"),"key":"race-winner-key","request_hash":"a"*64}
            assert original("update",competing)["status"] == "completed"
        return original(op,args)
    monkeypatch.setattr(db,"calendar_call",race)
    result = update(client, owner, saved, body(owner,task,reminder_minutes=15), "race-calendar-write")
    assert result.status_code == 409
    assert listing(client,owner)["items"][0]["status"] == "completed"


def test_default_closed_and_migration_probe_fail_closed(environment, monkeypatch):
    settings, root, db, client = environment
    assert settings.cloud_task_calendar_enabled is False
    owner = login(client)
    assert client.get("/api/v1/tasks/calendar", params={"workspace_ref":owner["workspace_ref"]}).status_code == 404
    with TestClient(create_cloud_identity_site(root,db,settings.model_copy(update={"cloud_notice_text_pilot_enabled":True})),base_url=ORIGIN) as notice_only:
        notice_only.cookies.set("campus_session",client.cookies.get("campus_session"))
        assert notice_only.get("/api/v1/tasks/calendar",params={"workspace_ref":owner["workspace_ref"]}).status_code == 404
    with pytest.raises(ValueError, match="notice backend"):
        create_cloud_identity_site(root, db, settings.model_copy(update={"cloud_task_calendar_enabled":True}))
    monkeypatch.setattr(db,"calendar_call",lambda op,args: {"schema_version":"wrong"})
    with pytest.raises(ValueError, match="Calendar migration required"):
        with TestClient(create_cloud_identity_site(root, db, settings.model_copy(update={
            "cloud_notice_text_pilot_enabled":True,"cloud_task_calendar_enabled":True}))): pass


def test_clear_arrangement_and_restore_unscheduled_does_not_occupy(calendar_env):
    _, _, _, client, owner = calendar_env
    saved = new_task(client, owner)
    task = listing(client,owner)["items"][0]
    result = update(client,owner,saved,body(owner,task,scheduled_start=None,scheduled_end=None),"calendar-clear-arrangement")
    assert result.status_code == 200
    task = result.json()["data"]
    cancelled = update(client,owner,saved,body(owner,task,status="cancelled"),"calendar-unscheduled-cancel").json()["data"]
    restored = update(client,owner,saved,body(owner,cancelled,status="pending"),"calendar-unscheduled-restore")
    assert restored.status_code == 200 and restored.json()["data"]["scheduled_start"] is None
    assert listing(client,owner)["items"][0]["notice"]["due"] == task["notice"]["due"]


def test_summary_matches_frontend_calendar_days_without_inventing_date_only_time(monkeypatch):
    from app.core.demo import load_fixture
    service = TaskCalendarService(None,None)
    notice = load_fixture("notice-event.demo.json")
    def task(id,start,end,due,status="pending"):
        n = deepcopy(notice)
        n["event"] = {"start":None,"end":None,"date":None,"precision":"unknown"}
        n["due"] = due
        return {"task_id":id,"revision":1,"confirmed_epoch":int(NOW.timestamp()),"notice":n,
            "calendar_state":{"calendar_revision":1,"status":status,"scheduled_start":start,
                "scheduled_end":end,"reminder_minutes":None}}
    tasks = [task("ongoing","2026-10-05T23:00:00+08:00","2026-10-06T12:00:00+08:00",
        {"at":None,"date":None,"precision":"unknown"}),
        task("date-overdue",None,None,{"at":None,"date":"2026-10-05","precision":"date_only"}),
        task("due-today","2026-10-07T08:00:00+08:00","2026-10-07T08:20:00+08:00",
            {"at":None,"date":"2026-10-06","precision":"date_only"}),
        task("completed",None,None,{"at":None,"date":"2026-10-05","precision":"date_only"},"completed")]
    monkeypatch.setattr(service,"records",lambda *args:{"tasks":tasks})
    monkeypatch.setattr("app.core.task_calendar.calendar_now",lambda:datetime(2026,10,6,8,0,tzinfo=TZ))
    result = service.summary({})
    assert (result["pending_count"],result["today_count"],result["overdue_count"],result["unscheduled_count"]) == (3,2,1,1)
    assert result["next_task"]["notice"]["due"]["at"] is None

"""Backend contract + actual embedded PG; no frontend, cloud or school claims."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.cloud_identity_site import create_cloud_identity_site
from app.core.notice_plan import calculate_notice, validate_notice_plan
from app.core.demo import load_fixture
from app.core.errors import AppError
from app.core.security import payload_hash, secret_hash
from app.domains.tasks.notice_reader import read_text
from app.domains.tasks.notice_model_reader import read_model_output
from test_cloud_identity_site import environment, login, save, headers, ORIGIN, authorize, exchange
from test_cloud_identity_site import SECRET
from app.core.cloud_oauth_provider import SCHOOL_CALLBACK

TEXT = "请在2026年9月21日10:10前提交虚构新实验记录，材料：实验PDF。"
WINDOW = {"start": "2026-09-21T08:00:00+08:00", "end": "2026-09-21T12:00:00+08:00"}


@pytest.fixture
def notice_env(environment):
    settings, root, database, _ = environment
    runtime = settings.model_copy(update={"cloud_notice_text_pilot_enabled": True})
    with TestClient(create_cloud_identity_site(root, database, runtime), base_url=ORIGIN) as client:
        yield runtime, root, database, client


def read_request(text=TEXT, **extra):
    return {"source_text": text, "source_ref": "self-authored", "reference_at": None,
            "fictional_data_confirmed": True, **extra}


def query(text=TEXT, minutes=20, **extra):
    notice = read_text(text, "self-authored")["items"][0]["notice"]
    return {**read_request(text), "item_id": notice["notice_id"], "window": WINDOW, "available_windows": [],
            "user_confirmations": {"source_review": True, "estimated_minutes": minutes,
                "earliest_start": "2026-09-21T09:40:00+08:00"}, **extra}


def post(client, owner, path, body, key="notice-http-test-key"):
    return client.post("/api/v1/notice-text/" + path, json=body, headers=headers(owner, key))


def plan(client, owner, payload=None):
    result = post(client, owner, "check", payload or query())
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    return {**data["plan"], "selected_slot": data["time_result"].get("candidate_slots", [None])[0]}


def draft(client, owner, payload, key="notice-new-draft"):
    result = post(client, owner, "drafts", {"plan": payload}, key)
    assert result.status_code == 200, result.text
    return result.json()["data"]


def confirm(client, owner, draft, key="notice-new-confirm"):
    payload = {k: draft[k] for k in ("draft_id", "revision", "payload_hash")}
    result = post(client, owner, "confirmations", payload, key)
    assert result.status_code == 200, result.text
    return result.json()["data"]


def commit(client, owner, ticket, key="notice-new-commit"):
    return post(client, owner, "commit", {"confirmation_id": ticket["confirmation_id"], "idempotency_key": key})


def test_new_notice_full_pg_flow_retries_restart_and_time_busy(notice_env):
    settings, root, db, client = notice_env
    owner = login(client)
    save(client, owner, "schedule", "timetable.demo.json")
    read = post(client, owner, "read", read_request())
    assert read.status_code == 200 and TEXT in read.json()["data"]["items"][0]["notice"]["title"]
    payload = plan(client, owner)
    assert payload["selected_slot"]["start"] == "2026-09-21T09:40:00+08:00"
    created = draft(client, owner, payload)
    assert created["review_url"] is None and created["review_required"] is True
    # No confirmed work interval exists yet.
    assert post(client, owner, "check", query()).json()["data"]["time_result"]["candidate_slots"]
    ticket = confirm(client, owner, created)
    result = commit(client, owner, ticket)
    assert result.status_code == 200, result.text
    saved = result.json()["data"]
    assert commit(client, owner, ticket).json()["data"] == saved
    assert draft(client, owner, payload) == created  # lost-create response retry after saving
    assert post(client, owner, "check", query()).json()["data"]["time_result"]["candidate_slots"] == []
    tasks = client.get("/api/v1/notice-text/tasks").json()["data"]
    assert tasks["total"] == 1 and tasks["items"][0]["notice"] == payload
    assert tasks["items"][0]["task_id"] == saved["task_id"]
    assert client.get("/api/v1/notice-text/tasks/" + saved["task_id"]).json()["data"]["notice"] == payload
    cookie = client.cookies.get("campus_session")
    with TestClient(create_cloud_identity_site(root, db, settings), base_url=ORIGIN) as restarted:
        restarted.cookies.set("campus_session", cookie)
        assert restarted.get("/api/v1/notice-text/tasks").json()["data"] == tasks
    # Existing own-time REST uses selected work interval when the server flag is on.
    time_request = {"workspace_ref": owner["workspace_ref"], "window": WINDOW, "min_minutes": 20,
                    "buffers": {"before_minutes": 0, "after_minutes": 0}}
    free = client.post("/api/v1/time/free-slots", json=time_request)
    assert free.status_code == 200
    assert all(slot["start"] != "2026-09-21T09:40:00+08:00" for slot in free.json()["data"]["slots"])


def test_owner_csrf_foreign_confirmation_and_source_tampering(notice_env):
    _, _, _, client = notice_env
    a = login(client)
    save(client, a, "schedule", "timetable.demo.json")
    payload = plan(client, a)
    created = draft(client, a, payload)
    ticket = confirm(client, a, created)
    assert client.post("/api/v1/notice-text/drafts", json={"plan": payload},
                       headers={"Origin": ORIGIN, "Idempotency-Key": "missing-csrf"}).status_code == 403
    changed = deepcopy(payload)
    changed["notice"]["due"]["at"] = "2026-09-21T11:00:00+08:00"
    assert post(client, a, "drafts", {"plan": changed}, "tampered-notice").status_code == 422
    assert post(client, a, "read", {**read_request(), "owner": "another-user"}).status_code == 422
    b = login(client, "fictional-b")
    assert client.get("/api/v1/notice-text/drafts/" + created["draft_id"]).status_code == 404
    assert commit(client, b, ticket).status_code == 404
    assert client.get("/api/v1/notice-text/tasks").json()["data"]["total"] == 0
    assert post(client, b, "check", query()).status_code == 404  # do not borrow A timetable
    assert client.get("/api/v1/notice-text/tasks", params={"workspace_ref": a["workspace_ref"]}).status_code == 422


def test_changed_revision_and_new_busy_record_invalidate_confirmation(notice_env):
    _, _, _, client = notice_env
    owner = login(client)
    save(client, owner, "schedule", "timetable.demo.json")
    payload = plan(client, owner)
    created = draft(client, owner, payload)
    ticket = confirm(client, owner, created)
    changed = plan(client, owner, query(minutes=10))
    update_body = {"revision": created["revision"], "plan": changed}
    update = post(client, owner, "drafts/" + created["draft_id"] + "/update", update_body, "notice-update-key")
    assert update.status_code == 200, update.text
    assert post(client, owner, "drafts/" + created["draft_id"] + "/update", update_body, "notice-update-key").json()["data"] == update.json()["data"]
    assert commit(client, owner, ticket).status_code == 409
    latest = update.json()["data"]
    latest_ticket = confirm(client, owner, latest, "latest-confirm")
    event = plan(client, owner, query("2026年9月21日09:45—09:50参加虚构讨论会。"))
    event_draft = draft(client, owner, event, "new-busy-draft")
    event_ticket = confirm(client, owner, event_draft, "new-busy-confirm")
    assert commit(client, owner, event_ticket, "new-busy-save").status_code == 200
    assert commit(client, owner, latest_ticket, "stale-after-busy-save").status_code == 409
    assert client.get("/api/v1/notice-text/tasks").json()["data"]["total"] == 1


def test_strict_oauth_reads_and_computes_without_write_routes(notice_env):
    _, _, _, client = notice_env
    owner = login(client)
    save(client, owner, "schedule", "timetable.demo.json")
    token = exchange(client, authorize(client, "demo:read")).json()["access_token"]
    auth = {"Authorization": "Bearer " + token}
    result = client.post("/oauth/notice/read", json={"query_json": json.dumps(read_request())}, headers=auth)
    assert result.status_code == 200, result.text
    check = client.post("/oauth/notice/check", json={"query_json": json.dumps(query())}, headers=auth)
    assert check.status_code == 200 and check.json()["data"]["time_result"]["candidate_slots"]
    assert client.post("/oauth/notice/commit", json={}, headers=auth).status_code == 404
    # Cookie from B never changes the owner of the A bearer grant.
    login(client, "fictional-b")
    assert client.post("/oauth/notice/check", json={"query_json": json.dumps(query())}, headers=auth).status_code == 200
    assert client.post("/oauth/notice/check", json={"query_json": json.dumps({**query(), "workspace_ref": "foreign"})}, headers=auth).status_code == 422


def model_output(text=TEXT):
    notice = read_text(text, "self-authored")["items"][0]["notice"]
    for span in notice["source_spans"]:
        span["source_ref"] = "self-authored"
    notice["needs_confirmation"] = []
    return json.dumps({"items": [{"kind": "deadline_feasibility", "notice": notice}], "unclassified": []}, ensure_ascii=False)


def test_model_fields_require_explicit_review_and_checked_mapping(notice_env):
    _, _, _, client = notice_env
    owner = login(client)
    save(client, owner, "schedule", "timetable.demo.json")
    raw = model_output()
    read = post(client, owner, "read", read_request(model_output=raw)).json()["data"]
    item = read["items"][0]["notice"]
    body = query(item_id=item["notice_id"], model_output=raw)
    unchecked = post(client, owner, "check", body).json()["data"]
    assert unchecked["time_result"]["candidate_slots"] == [] and "due_time" in unchecked["time_result"]["needs_confirmation"]
    body["user_confirmations"]["due_at"] = "2026-09-21T10:10:00+08:00"
    checked = plan(client, owner, body)
    assert checked["notice"]["notice_id"].startswith("model-")
    created = draft(client, owner, checked)
    assert commit(client, owner, confirm(client, owner, created)).status_code == 200


@pytest.mark.parametrize("mutation", ["duplicate", "fake_quote", "extra_field", "missing_tail", "invalid_time"])
def test_model_bad_output_cannot_become_a_savable_item(mutation):
    raw = model_output()
    parsed = json.loads(raw)
    text = TEXT
    if mutation == "duplicate":
        raw = raw.replace('"kind":', '"kind":"event_conflict","kind":')
    elif mutation == "fake_quote":
        parsed["items"][0]["notice"]["source_spans"][0]["quote"] = "不存在的通知内容"
        raw = json.dumps(parsed)
    elif mutation == "extra_field":
        parsed["items"][0]["notice"]["owner"] = "foreign"
        raw = json.dumps(parsed)
    elif mutation == "invalid_time":
        parsed["items"][0]["notice"]["due"]["at"] = "2026-02-30T10:10:00+08:00"
        raw = json.dumps(parsed)
    else:
        text += "另须完成最后一段事项。"
    if mutation != "missing_tail":
        with pytest.raises(AppError):
            read_model_output(text, "self-authored", None, raw)
    else:
        result = read_model_output(text, "self-authored", None, raw)
        assert result["coverage"]["unread_ranges"]
        assert "incomplete_source_coverage" in result["items"][0]["notice"]["needs_confirmation"]


def test_disabled_routes_and_explicit_fictional_gate(environment, notice_env):
    _, _, _, old_client = environment
    assert old_client.post("/api/v1/notice-text/read", json=read_request()).status_code == 404
    _, _, _, client = notice_env
    owner = login(client)
    body = read_request()
    body.pop("fictional_data_confirmed")
    assert post(client, owner, "read", body).status_code == 403


@pytest.mark.skipif(os.environ.get("RUN_NOTICE_WINDOWS_OCR_TEST") != "1", reason="Opt-in actual Windows Chinese OCR integration")
def test_actual_screenshot_read_review_calculate_and_save(notice_env):
    settings, _, _, client = notice_env
    settings.notice_ocr_backend = "windows"
    owner = login(client)
    save(client, owner, "schedule", "timetable.demo.json")
    image = Path(__file__).parents[2] / "docs/evidence/platform/D13-fictional-ocr-input-2026-10-06.png"
    response = client.post("/api/v1/notice-text/images/read", files={"file": ("fictional.png", image.read_bytes(), "image/png")},
        data={"fictional_data_confirmed": "true", "source_ref": "self-authored-screenshot"}, headers=headers(owner))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["source"]["input_coverage"]["processed_pages"] == [1]
    assert data["can_save"] is False
    batch = data["batch"]
    assert batch["items"] and "ocr_review" in batch["items"][0]["notice"]["needs_confirmation"]
    body = {**query(), **data["read_request"], "item_id": batch["items"][0]["notice"]["notice_id"]}
    # Source review alone cannot authorize an OCR date, even if it looks clear.
    pending = post(client, owner, "check", body).json()["data"]["time_result"]
    assert pending["candidate_slots"] == [] and "ocr_review" in pending["needs_confirmation"]
    body["user_confirmations"].update(ocr_review=True, due_at="2026-09-21T10:10:00+08:00")
    payload = plan(client, owner, body)
    assert payload["document_sha256"] == data["source"]["document_sha256"]
    assert payload["selected_slot"]["start"] == "2026-09-21T09:40:00+08:00"
    result = commit(client, owner, confirm(client, owner, draft(client, owner, payload)))
    assert result.status_code == 200, result.text


def test_ocr_disabled_bad_types_and_upload_owner_overrides(notice_env):
    _, _, _, client = notice_env
    owner = login(client)
    image = Path(__file__).parents[2] / "docs/evidence/platform/D13-fictional-ocr-input-2026-10-06.png"
    def upload(data, mime, **extra):
        return client.post("/api/v1/notice-text/images/read", files={"file": ("test", data, mime)},
            data={"fictional_data_confirmed": "true", **extra}, headers=headers(owner))
    assert upload(image.read_bytes(), "image/png").status_code == 503
    assert upload(b"%PDF-1.7", "application/pdf").status_code == 415
    assert upload(b"bad header", "image/png").status_code == 422
    assert upload(image.read_bytes(), "image/png", owner="foreign").status_code == 422


def test_atomic_pg_snapshot_rejects_record_change_after_python_calculation(notice_env, monkeypatch):
    _, _, database, client = notice_env
    owner = login(client)
    save(client, owner, "schedule", "timetable.demo.json")
    chosen = plan(client, owner)
    ticket = confirm(client, owner, draft(client, owner, chosen))
    original = database.notice_call
    injected = False
    def race(op, args):
        nonlocal injected
        if op == "commit" and not injected:
            injected = True
            auth = {k: args[k] for k in ("session_hash", "csrf_hash")}
            fixture_hash = payload_hash(load_fixture("notice-event.demo.json"))
            created = database.call("create_draft", {**auth, "kind": "task", "payload_hash": fixture_hash,
                "key": "fixture-racing-create", "request_hash": secret_hash("fictional-racing-create"), "draft_id": "fixture_racing_draft"})
            raw = "fixture-racing-confirmation"
            database.call("confirm", {**auth, "draft_id": created["draft_id"], "revision": created["revision"],
                "payload_hash": fixture_hash, "key": "fixture-racing-confirm", "request_hash": secret_hash("fictional-racing-confirm"),
                "confirmation_id": raw, "confirmation_hash": secret_hash(raw)})
            database.call("commit", {**auth, "kind": "task", "key": "fixture-racing-save", "request_hash": secret_hash("fictional-racing-save"),
                "confirmation_hash": secret_hash(raw), "resource_id": "fixture_racing_task"})
        return original(op, args)
    monkeypatch.setattr(database, "notice_call", race)
    saved = commit(client, owner, ticket)
    assert saved.status_code == 409 and saved.json()["error"]["code"] == "STALE_REVISION"
    assert injected
    assert client.get("/api/v1/notice-text/tasks").json()["data"]["total"] == 0


def test_competition_read_only_oauth_notice_and_logout(environment):
    settings, root, database, _ = environment
    runtime = settings.model_copy(update={"cloud_notice_text_pilot_enabled": True, "cloud_task_calendar_enabled": True,
        "cloud_oauth_competition_compat_enabled": True})
    with TestClient(create_cloud_identity_site(root, database, runtime), base_url=ORIGIN) as client:
        owner = login(client)
        save(client, owner, "schedule", "timetable.demo.json")
        response = client.get("/oauth/authorize", params={"response_type": "code", "client_id": "test-school-agent",
            "redirect_uri": SCHOOL_CALLBACK, "scope": "demo:read", "state": "fictional-notice-state"})
        transaction = re.search(r'name="transaction" value="([^"]+)"', response.text)[1]
        allow = client.post("/oauth/approve", data={"transaction": transaction, "decision": "allow"},
            headers={"Origin": ORIGIN}, follow_redirects=False)
        code = parse_qs(urlsplit(allow.headers["Location"]).query)["code"][0]
        token = client.post("/oauth/token", json={"client_id": "test-school-agent", "client_secret": SECRET,
            "grant_type": "authorization_code", "code": code, "redirect_uri": SCHOOL_CALLBACK}).json()["access_token"]
        auth = {"Authorization": "Bearer " + token}
        summary = client.get("/oauth/tasks/summary", headers=auth)
        assert summary.status_code == 200 and summary.json()["data"]["pending_count"] == 0
        assert client.get("/oauth/tasks/summary", params={"owner":"other"}, headers=auth).status_code == 400
        assert client.post("/oauth/notice/check", json={"query_json": json.dumps(query())}, headers=auth).status_code == 200
        assert client.post("/oauth/notice/confirmations", json={}, headers=auth).status_code == 404
        client.post("/api/v1/auth/cloudbase/logout", headers=headers(owner))
        assert client.get("/oauth/tasks/summary", headers=auth).status_code == 401
        assert client.post("/oauth/notice/check", json={"query_json": json.dumps(query())}, headers=auth).status_code == 401


def test_expired_workspace_cache_cannot_resurrect_draft_in_new_workspace(notice_env):
    _, _, database, client = notice_env
    old_owner = login(client)
    save(client, old_owner, "schedule", "timetable.demo.json")
    payload = plan(client, old_owner)
    created = draft(client, old_owner, payload)
    database.call("__test_expire_workspace__", {"workspace_ref": old_owner["workspace_ref"]})
    new_owner = login(client)
    assert new_owner["workspace_ref"] != old_owner["workspace_ref"]
    assert client.get("/api/v1/notice-text/drafts/" + created["draft_id"]).status_code == 404
    retry = post(client, new_owner, "drafts", {"plan": payload}, "notice-new-draft")
    assert retry.status_code == 404
    assert client.get("/api/v1/notice-text/tasks").json()["data"]["total"] == 0

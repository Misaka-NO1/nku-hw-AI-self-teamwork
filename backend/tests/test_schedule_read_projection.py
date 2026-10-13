"""Synthetic schedule projection checks; never imports private records."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import AppError
from app.core.oauth_local import OAuthError
from app.core.schedule_read_projection import MAX_RESOLVED_MEETINGS, project_schedule_meetings
from app.oauth_pilot_site import create_oauth_adapter
from test_oauth_pilot import pilot, authorize, exchange


def records():
    clocks = [("08:00", "08:45"), ("08:55", "09:40"), ("10:00", "10:45"),
              ("10:55", "11:40"), ("11:50", "12:35"), ("12:55", "13:40"),
              ("13:50", "14:35"), ("14:55", "15:40"), ("16:00", "16:45"),
              ("16:55", "17:40"), ("18:30", "19:15"), ("19:25", "20:10"), ("20:20", "21:05")]
    def meeting(identifier, first, last):
        return {"meeting_id": identifier, "weekday": 2, "weeks": [1, 3, 5],
                "start_period": first, "end_period": last, "location": "实验楼101"}
    return {"dataset_kind": "personal", "personal_uploads": True, "tasks": [], "schedule": {
        "revision": 1, "timetable": {"term": {"periods": [
            {"period": i, "start": start, "end": end} for i, (start, end) in enumerate(clocks, 1)],
            "overrides": [{"date": "2026-10-13", "action": "cancel"}]}, "courses": [
            {"course_id": "math", "offering_id": "math-1", "title": "离散数学",
             "meetings": [meeting("math-tue", 3, 4)]},
            {"course_id": "data", "offering_id": "data-1", "title": "数据结构",
             "meetings": [meeting("data-afternoon", 6, 8), meeting("data-evening", 11, 13)]}]}}}


def test_complete_three_period_clocks_names_and_unchanged_source():
    source = records()
    before = deepcopy(source)
    output = project_schedule_meetings(source)
    items = output["schedule"]["resolved_meetings"]
    assert [item["time_label"] for item in items] == ["10:00–11:40", "12:55–15:40", "18:30–21:05"]
    assert [item["period_label"] for item in items] == ["第3—4节", "第6—8节", "第11—13节"]
    assert [item["course_title"] for item in items] == ["离散数学", "数据结构", "数据结构"]
    assert len({item["course_id"] for item in items}) == 2 and len(items) == 3
    assert all(item["time_status"] == "available" and item["time_error"] is None for item in items)
    assert items[1]["weeks"] == [1, 3, 5] and items[1]["weekday"] == 2
    assert output["schedule"]["resolved_meetings_meta"]["complete"] is True
    assert output["schedule"]["resolved_meetings_meta"]["date_filter_applied"] is False
    assert output["schedule"]["timetable"] == before["schedule"]["timetable"]
    assert source == before


@pytest.mark.parametrize("mutation,reason", [
    ("missing_end", "missing_period"), ("missing_middle", "missing_period"),
    ("duplicate_end", "duplicate_period"), ("bad_clock", "invalid_period_time"),
    ("reversed_clock", "invalid_period_time"), ("overlap", "overlapping_period_times"),
    ("reversed_range", "invalid_period_range"), ("boolean_range", "invalid_period_range"),
])
def test_missing_duplicate_and_invalid_periods_never_guess_end(mutation, reason):
    source = records()
    timetable = source["schedule"]["timetable"]
    periods = timetable["term"]["periods"]
    meeting = timetable["courses"][1]["meetings"][0]
    if mutation in {"missing_end", "missing_middle"}:
        del periods[7 if mutation == "missing_end" else 6]
    elif mutation == "duplicate_end":
        periods.append(deepcopy(periods[7]))
    elif mutation == "bad_clock":
        periods[7]["end"] = "25:00"
    elif mutation == "reversed_clock":
        periods[7]["end"] = "12:00"
    elif mutation == "overlap":
        periods[6]["start"] = "13:00"
    elif mutation == "reversed_range":
        meeting["end_period"] = 5
    else:
        meeting["start_period"] = True
    output = project_schedule_meetings(source)["schedule"]
    item = output["resolved_meetings"][1]
    assert item["time_status"] == "unavailable" and item["time_error"] == reason
    assert item["start_time"] is None and item["end_time"] is None
    assert item["time_label"] == "时间无法确定"
    assert output["resolved_meetings_meta"]["complete"] is False


def test_null_schedule_stays_exactly_absent():
    source = {"dataset_kind": "demo", "personal_uploads": False, "schedule": None, "tasks": []}
    assert project_schedule_meetings(source) == source


def test_projection_is_bounded_and_explicitly_not_complete():
    source = records()
    course = source["schedule"]["timetable"]["courses"][0]
    course["meetings"] *= MAX_RESOLVED_MEETINGS + 1
    output = project_schedule_meetings(source)["schedule"]
    assert len(output["resolved_meetings"]) == MAX_RESOLVED_MEETINGS
    assert output["resolved_meetings_meta"]["truncated"] is True
    assert output["resolved_meetings_meta"]["complete"] is False
    assert "projection_truncated_use_original_timetable" in output["resolved_meetings_meta"]["warnings"]


@pytest.mark.parametrize("malformation", [None, {}, {"courses": []}, {"courses": [{"meetings": None}]}])
def test_malformed_timetable_is_not_claimed_as_complete_empty_schedule(malformation):
    source = records()
    source["schedule"]["timetable"] = malformation
    output = project_schedule_meetings(source)["schedule"]
    assert output["resolved_meetings_meta"]["complete"] is False
    assert "invalid_timetable_structure" in output["resolved_meetings_meta"]["warnings"]


def test_common_http_route_projects_only_after_provider_authorization(monkeypatch):
    import app.core.schedule_read_projection as projection
    calls = []
    original = projection.project_schedule_meetings
    def track(value):
        calls.append(value)
        return original(value)
    monkeypatch.setattr(projection, "project_schedule_meetings", track)
    class Provider:
        def gate(self): pass
        def initialize(self): pass
        def records(self, request):
            credential = request.headers.get("Authorization", "")
            if credential != "Bearer fictional-authorized-owner":
                raise OAuthError("invalid_token", 401)
            if request.headers.get("platform-user-id") != "fictional-owner":
                raise AppError(403, "FORBIDDEN", "Owner mismatch")
            return records()
    site = create_oauth_adapter(Settings(_env_file=None), Provider())
    with TestClient(site) as client:
        missing = client.get("/records")
        assert missing.status_code == 401 and missing.json() == {"error": "invalid_token"}
        assert "invalid_token" in missing.headers["www-authenticate"]
        wrong = client.get("/records", headers={"Authorization": "Bearer fictional-authorized-owner",
                                                "platform-user-id": "fictional-other"})
        assert wrong.status_code == 403 and calls == []
        good = client.get("/records", headers={"Authorization": "Bearer fictional-authorized-owner",
                                               "platform-user-id": "fictional-owner"})
        assert good.status_code == 200 and good.headers["cache-control"] == "no-store"
        assert good.json()["data"]["schedule"]["resolved_meetings"][2]["end_time"] == "21:05"
        assert len(calls) == 1


def test_local_oauth_grant_keeps_owner_resolution_before_projection(pilot, monkeypatch):
    from app.core import agent_pairing_local as pairing
    settings, users, client = pilot
    token = exchange(client, authorize(pilot, scope="demo:read")).json()["access_token"]
    owner_workspace = users["fictional-a"]["workspace_ref"]
    fetched = []
    source = records()["schedule"]
    def owned_schedule(runtime, principal, workspace):
        assert runtime is settings and workspace == owner_workspace
        fetched.append(workspace)
        return deepcopy(source)
    monkeypatch.setattr(pairing.service, "get_current_schedule", owned_schedule)
    response = client.get("/records", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200
    assert response.json()["data"]["schedule"]["resolved_meetings"][1]["time_label"] == "12:55–15:40"
    assert len(fetched) == 1
    denied = client.get("/records", headers={"Authorization": "Bearer " + "X" * 43})
    assert denied.status_code == 401 and len(fetched) == 1

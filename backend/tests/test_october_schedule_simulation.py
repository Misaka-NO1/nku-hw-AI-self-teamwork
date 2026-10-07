"""Checked-in October fiction is approved; arbitrary/personal uploads remain denied."""
import json
from pathlib import Path

import pytest

from app.core.demo import enforce_demo_fixture
from app.core.errors import AppError
from app.core.owned_time import calculate_owned_time
from app.domains.schedule import validate_timetable
from app.domains.schedule.service import parse_datetime, expand_occurrences
from app.domains.timeplan import check_time_plan, find_free_slots


def timetable():
    return json.loads((Path(__file__).parents[2] / "fixtures/timetable-october-2026.simulation.json").read_text(encoding="utf-8"))


def query(day="2026-10-07", minutes=60):
    return {
        "workspace_ref": "simulation-only-not-an-owner",
        "kind": "deadline_feasibility",
        "window": {"start": day + "T09:00:00+08:00", "end": day + "T18:00:00+08:00"},
        "event": None,
        "due": {"at": "2026-10-09T18:00:00+08:00", "date": None, "precision": "datetime"},
        "estimated_minutes": minutes, "earliest_start": "2026-10-07T09:00:00+08:00",
        "allow_split": False, "buffers": {"before_minutes": 0, "after_minutes": 0},
    }


def check(request):
    mock = timetable()
    return check_time_plan(mock["term"], mock["courses"], [], request)


def test_mock_is_valid_and_only_exact_checked_in_content_is_allowed():
    assert validate_timetable(timetable())["issues"] == []
    assert enforce_demo_fixture(timetable(), "schedule")
    modified = timetable()
    modified["courses"][0]["title"] = "个人文件不得上传"
    with pytest.raises(AppError) as error:
        enforce_demo_fixture(modified, "schedule")
    assert error.value.code == "DEMO_ONLY"


def test_ddl_candidates_avoid_wednesday_courses():
    result = check(query())
    assert result["needs_confirmation"] == []
    assert result["candidate_slots"] == [
        {"start": "2026-10-07T09:40:00+08:00", "end": "2026-10-07T10:40:00+08:00", "duration_minutes": 60},
        {"start": "2026-10-07T15:40:00+08:00", "end": "2026-10-07T16:40:00+08:00", "duration_minutes": 60},
    ]


def test_editing_duration_recomputes_and_deadline_remains_independent():
    request = query(minutes=90)
    result = check(request)
    assert result["candidate_slots"][0]["end"] == "2026-10-07T11:10:00+08:00"
    assert request["due"]["at"] == "2026-10-09T18:00:00+08:00"
    due = parse_datetime(request["due"]["at"], field="due")
    assert all(parse_datetime(slot["end"], field="end") <= due for slot in result["candidate_slots"])


def test_ddl_on_another_day_uses_that_days_courses():
    result = check(query("2026-10-08"))
    assert [slot["start"] for slot in result["candidate_slots"]] == [
        "2026-10-08T09:00:00+08:00", "2026-10-08T11:50:00+08:00"]


def test_fixed_event_is_not_a_ddl_candidate_request():
    request = query()
    request.update(kind="event_conflict", due=None, estimated_minutes=None, earliest_start=None,
                   event={"start": "2026-10-07T14:10:00+08:00", "end": "2026-10-07T15:00:00+08:00", "date": None, "precision": "datetime"})
    result = check(request)
    assert "candidate_slots" not in result
    assert result["conflicts"][0]["source_event_id"]


def test_missing_duration_and_insufficient_time_do_not_invent_candidates():
    request = query()
    request["estimated_minutes"] = None
    assert check(request)["needs_confirmation"] == ["estimated_minutes"]
    request = query(minutes=60)
    request["window"] = {"start": "2026-10-07T14:00:00+08:00", "end": "2026-10-07T15:00:00+08:00"}
    assert check(request)["candidate_slots"] == []


@pytest.mark.parametrize("day,expected", [
    ("2026-10-07", [("09:40", "12:00"), ("15:40", "22:00")]),
    ("2026-10-08", [("08:00", "10:10"), ("11:50", "12:00"), ("14:00", "22:00")]),
])
def test_minute_threshold_returns_whole_free_windows_without_weekday_nap(day, expected):
    """Same query shape as Agent: split at nap boundaries, no task duration required."""
    mock = timetable()
    slots = []
    for start, end in [("08:00", "12:00"), ("14:00", "22:00")]:
        window = {"start": f"{day}T{start}:00+08:00", "end": f"{day}T{end}:00+08:00"}
        events, _ = expand_occurrences(mock["term"], mock["courses"], window)
        slots += find_free_slots(events, window, 1, {"before_minutes": 0, "after_minutes": 0})["slots"]
    assert [(s["start"][11:16], s["end"][11:16]) for s in slots] == expected
    assert all(s["end"][11:16] <= "12:00" or s["start"][11:16] >= "14:00" for s in slots)


def test_weekend_free_window_keeps_noon_and_clips_to_deadline():
    mock = timetable()
    window = {"start": "2026-10-10T08:00:00+08:00", "end": "2026-10-10T16:30:00+08:00"}
    events, _ = expand_occurrences(mock["term"], mock["courses"], window)
    slots = find_free_slots(events, window, 1, {"before_minutes": 0, "after_minutes": 0})["slots"]
    assert slots == [{"start": window["start"], "end": window["end"], "duration_minutes": 510}]


@pytest.mark.parametrize("status,scheduled,expected", [
    ("pending", True, [("14:00", "14:30"), ("15:00", "18:00")]),
    ("done", True, [("14:00", "18:00")]),
    ("pending", False, [("14:00", "18:00")]),
])
def test_owned_free_time_excludes_saved_work_not_just_courses(status, scheduled, expected):
    root = Path(__file__).parents[2] / "fixtures"
    mock = json.loads((root / "timetable.demo.json").read_text(encoding="utf-8"))
    notice = json.loads((root / "notice-deadline.demo.json").read_text(encoding="utf-8"))
    records = {"schedule": {"timetable": mock}, "tasks": [{
        "task_id": "local-fictitious-task", "notice": notice,
        "calendar_state": {"status": status,
            "scheduled_start": "2026-09-21T14:30:00+08:00" if scheduled else None,
            "scheduled_end": "2026-09-21T15:00:00+08:00" if scheduled else None},
    }]}
    payload = {"window": {"start": "2026-09-21T14:00:00+08:00", "end": "2026-09-21T18:00:00+08:00"},
               "min_minutes": 1, "buffers": {"before_minutes": 0, "after_minutes": 0}}
    result, _ = calculate_owned_time(records, payload, "free", allow_notice_text=True)
    assert [(s["start"][11:16], s["end"][11:16]) for s in result["slots"]] == expected


def test_quality_query_can_skip_course_fragments_then_expand_without_task_duration():
    window = {"start": "2026-10-07T08:00:00+08:00", "end": "2026-10-07T12:00:00+08:00"}
    events = [
        {"event_id": "synthetic-a", "start": "2026-10-07T09:00:00+08:00", "end": "2026-10-07T09:40:00+08:00"},
        {"event_id": "synthetic-b", "start": "2026-10-07T10:10:00+08:00", "end": "2026-10-07T11:50:00+08:00"},
    ]
    buffers = {"before_minutes": 0, "after_minutes": 0}
    preferred = find_free_slots(events, window, 45, buffers)["slots"]
    expanded = find_free_slots(events, window, 1, buffers)["slots"]
    assert [s["duration_minutes"] for s in preferred] == [60]
    assert [s["duration_minutes"] for s in expanded] == [60, 30, 10]

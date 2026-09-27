"""B 域（schedule / timeplan）的强制测试集。

对应任务书 TIME-01 ~ TIME-08；预期值来自 fixtures/expected-results.demo.json，
不修改预期去迎合实现。
"""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.domains.schedule import expand_occurrences, export_ics, validate_timetable
from app.domains.timeplan import check_time_plan, find_free_slots

FIXTURES = Path(__file__).parents[2] / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture()
def term() -> dict:
    return load_fixture("term.demo.json")


@pytest.fixture()
def timetable() -> dict:
    return load_fixture("timetable.demo.json")


@pytest.fixture()
def expected() -> dict:
    return load_fixture("expected-results.demo.json")


@pytest.fixture()
def courses(timetable: dict) -> list[dict]:
    return deepcopy(timetable["courses"])


WINDOW = {"start": "2026-09-21T08:00:00+08:00", "end": "2026-09-21T12:00:00+08:00"}
BUFFERS = {"before_minutes": 0, "after_minutes": 0}


# ---------------------------------------------------------------------------
# validate_timetable
# ---------------------------------------------------------------------------


def test_validate_timetable_normalizes_and_hashes(timetable: dict) -> None:
    result = validate_timetable(deepcopy(timetable))
    assert result["payload_hash"]
    assert result["coverage"]["completeness"] == "complete"
    assert result["issues"] == []
    # 规范化后周次去重升序
    for course in result["normalized_payload"]["courses"]:
        for meeting in course["meetings"]:
            weeks = meeting["weeks"]
            assert weeks == sorted(set(weeks))


def test_validate_timetable_is_stable_across_input_order(timetable: dict) -> None:
    first = validate_timetable(deepcopy(timetable))
    second = validate_timetable(deepcopy(timetable))
    assert first["payload_hash"] == second["payload_hash"]


def test_validate_timetable_rejects_schema_violation(timetable: dict) -> None:
    broken = deepcopy(timetable)
    broken["courses"][0]["meetings"][0]["weekday"] = 8
    with pytest.raises(AppError) as excinfo:
        validate_timetable(broken)
    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "VALIDATION_ERROR"


def test_validate_timetable_keeps_distinct_meetings_of_same_course(timetable: dict) -> None:
    """IMPORT-02：同一 course_id 的不同 meeting 都必须保留（不误删实验课）。"""

    payload = deepcopy(timetable)
    extra = deepcopy(payload["courses"][0]["meetings"][0])
    extra["meeting_id"] = "demo-CS101-m2"
    extra["weekday"] = 3
    payload["courses"][0]["meetings"].append(extra)
    result = validate_timetable(payload)
    meetings = result["normalized_payload"]["courses"][0]["meetings"]
    assert len(meetings) == 2
    assert {m["meeting_id"] for m in meetings} == {"demo-CS101-m1", "demo-CS101-m2"}


def test_validate_timetable_dedupes_identical_meetings(timetable: dict) -> None:
    payload = deepcopy(timetable)
    duplicate = deepcopy(payload["courses"][0]["meetings"][0])
    duplicate["meeting_id"] = "demo-CS101-m1-copy"
    payload["courses"][0]["meetings"].append(duplicate)
    result = validate_timetable(payload)
    meetings = result["normalized_payload"]["courses"][0]["meetings"]
    assert len(meetings) == 1
    assert any(issue["code"] == "duplicate_meeting" for issue in result["issues"])


# ---------------------------------------------------------------------------
# TIME-04 非法周次 / 节次返回 422
# ---------------------------------------------------------------------------


def test_time04_weeks_out_of_range_rejected(timetable: dict) -> None:
    payload = deepcopy(timetable)
    payload["courses"][0]["meetings"][0]["weeks"] = [1, 3, 9]
    with pytest.raises(AppError) as excinfo:
        validate_timetable(payload)
    assert excinfo.value.status_code == 422
    assert any(e.code == "week_out_of_range" for e in excinfo.value.field_errors)


def test_time04_duplicate_weeks_rejected_by_schema(timetable: dict) -> None:
    payload = deepcopy(timetable)
    payload["courses"][0]["meetings"][0]["weeks"] = [1, 1, 3]
    with pytest.raises(AppError) as excinfo:
        validate_timetable(payload)
    assert excinfo.value.status_code == 422


def test_time04_period_order_rejected(timetable: dict) -> None:
    payload = deepcopy(timetable)
    payload["courses"][0]["meetings"][0]["start_period"] = 4
    payload["courses"][0]["meetings"][0]["end_period"] = 3
    with pytest.raises(AppError) as excinfo:
        validate_timetable(payload)
    assert excinfo.value.status_code == 422
    assert any(e.code == "period_order" for e in excinfo.value.field_errors)


def test_time04_unknown_period_rejected(timetable: dict) -> None:
    payload = deepcopy(timetable)
    payload["courses"][0]["meetings"][0]["start_period"] = 99
    payload["courses"][0]["meetings"][0]["end_period"] = 99
    with pytest.raises(AppError) as excinfo:
        validate_timetable(payload)
    assert excinfo.value.status_code == 422
    assert any(e.code == "unknown_period" for e in excinfo.value.field_errors)


# ---------------------------------------------------------------------------
# TIME-01 单双周展开
# ---------------------------------------------------------------------------


def test_time01_odd_week_expansion(term: dict, courses: list[dict]) -> None:
    """demo-CS101 第 1、3 周周一有课，不包含第 2、4 周。"""

    events, _ = expand_occurrences(term, courses, None)
    cs101 = [e for e in events if e["course_id"] == "demo-CS101"]
    assert [e["week"] for e in cs101] == [1, 3]
    assert [e["start"][:10] for e in cs101] == ["2026-09-07", "2026-09-21"]


def test_expand_occurrences_window_filters_events(term: dict, courses: list[dict]) -> None:
    events, _ = expand_occurrences(term, courses, WINDOW)
    assert all(e["start"] < WINDOW["end"] and WINDOW["start"] < e["end"] for e in events)
    # 2026-09-21 是第 3 周周一：CS101（第 1、3 周）与 CS102（第 1-4 周）在窗口内
    assert {e["course_id"] for e in events} == {"demo-CS101", "demo-CS102"}


def test_expand_occurrences_matches_expected_busy_intervals(
    term: dict, courses: list[dict], expected: dict
) -> None:
    events, _ = expand_occurrences(term, courses, WINDOW)
    busy = sorted((e["start"], e["end"]) for e in events)
    expected_busy = sorted(
        (item["start"], item["end"]) for item in expected["time"]["busy_intervals"]
    )
    assert busy == expected_busy


# ---------------------------------------------------------------------------
# TIME-02 半开区间不误报冲突
# ---------------------------------------------------------------------------


def test_time02_half_open_interval_no_false_conflict(term: dict, courses: list[dict]) -> None:
    events, _ = expand_occurrences(term, courses, WINDOW)
    request = {
        "kind": "event_conflict",
        "window": WINDOW,
        "event": {
            "start": "2026-09-21T09:40:00+08:00",
            "end": "2026-09-21T10:10:00+08:00",
            "date": None,
            "precision": "datetime",
        },
        "due": None,
        "estimated_minutes": None,
        "earliest_start": None,
        "allow_split": False,
        "buffers": BUFFERS,
    }
    result = check_time_plan(term, courses, [], request)
    assert result["conflicts"] == []
    assert result["needs_confirmation"] == []


# ---------------------------------------------------------------------------
# TIME-03 不同周次不误报冲突
# ---------------------------------------------------------------------------


def test_time03_same_period_different_weeks_no_conflict(term: dict, courses: list[dict]) -> None:
    # 第 2 周周一的 08:00-09:40：CS101 只在第 1、3 周，CS102 在第 3-4 节
    window_week2 = {
        "start": "2026-09-14T08:00:00+08:00",
        "end": "2026-09-14T12:00:00+08:00",
    }
    request = {
        "kind": "event_conflict",
        "window": window_week2,
        "event": {
            "start": "2026-09-14T08:00:00+08:00",
            "end": "2026-09-14T09:40:00+08:00",
            "date": None,
            "precision": "datetime",
        },
        "due": None,
        "estimated_minutes": None,
        "earliest_start": None,
        "allow_split": False,
        "buffers": BUFFERS,
    }
    result = check_time_plan(term, courses, [], request)
    assert result["conflicts"] == []


def test_event_conflict_matches_expected_intersections(
    term: dict, courses: list[dict], expected: dict
) -> None:
    request = load_fixture("time-event-query.demo.json")
    result = check_time_plan(term, courses, [], request)
    intersections = sorted(
        (item["intersection_start"], item["intersection_end"]) for item in result["conflicts"]
    )
    expected_intersections = sorted(
        (item["start"], item["end"]) for item in expected["time"]["event_conflict_intersections"]
    )
    assert intersections == expected_intersections


# ---------------------------------------------------------------------------
# find_free_slots
# ---------------------------------------------------------------------------


def test_find_free_slots_matches_expected(term: dict, courses: list[dict], expected: dict) -> None:
    events, _ = expand_occurrences(term, courses, WINDOW)
    result = find_free_slots(events, WINDOW, 30, BUFFERS)
    assert [(s["start"], s["end"]) for s in result["slots"]] == [
        (slot["start"], slot["end"]) for slot in expected["time"]["free_slots_min_30"]
    ]
    assert result["slots"][0]["duration_minutes"] == 30


def test_find_free_slots_buffers_shrink_slots(term: dict, courses: list[dict]) -> None:
    events, _ = expand_occurrences(term, courses, WINDOW)
    buffers = {"before_minutes": 10, "after_minutes": 10}
    result = find_free_slots(events, WINDOW, 10, buffers)
    # 08:00-09:40 与 10:10-11:50 各扩 10 分钟后，中间只剩 09:50-10:00
    assert [(s["start"], s["end"]) for s in result["slots"]] == [
        ("2026-09-21T09:50:00+08:00", "2026-09-21T10:00:00+08:00")
    ]


# ---------------------------------------------------------------------------
# TIME-05 截止前 20 分钟任务可安排在 09:40-10:00
# ---------------------------------------------------------------------------


def test_time05_deadline_candidate(term: dict, courses: list[dict], expected: dict) -> None:
    request = load_fixture("time-deadline-query.demo.json")
    result = check_time_plan(term, courses, [], request)
    assert result["needs_confirmation"] == []
    assert result["candidate_slots"] != []
    first = result["candidate_slots"][0]
    assert first["start"] == expected["time"]["deadline_candidate"]["start"]
    assert first["end"] == expected["time"]["deadline_candidate"]["end"]
    assert first["duration_minutes"] == 20


# ---------------------------------------------------------------------------
# TIME-06 缺少耗时或截止时刻时待确认
# ---------------------------------------------------------------------------


def test_time06_date_only_due_needs_confirmation(term: dict, courses: list[dict]) -> None:
    request = load_fixture("time-deadline-query.demo.json")
    request["due"] = {"at": None, "date": "2026-09-21", "precision": "date_only"}
    result = check_time_plan(term, courses, [], request)
    assert "due_time" in result["needs_confirmation"]
    assert result["candidate_slots"] == []


def test_time06_missing_estimated_minutes_needs_confirmation(term: dict, courses: list[dict]) -> None:
    request = load_fixture("time-deadline-query.demo.json")
    request["estimated_minutes"] = None
    result = check_time_plan(term, courses, [], request)
    assert "estimated_minutes" in result["needs_confirmation"]
    assert result["candidate_slots"] == []


def test_time06_missing_earliest_start_needs_confirmation(term: dict, courses: list[dict]) -> None:
    request = load_fixture("time-deadline-query.demo.json")
    request["earliest_start"] = None
    result = check_time_plan(term, courses, [], request)
    assert "earliest_start" in result["needs_confirmation"]


def test_time06_event_conflict_without_event_time_needs_confirmation(
    term: dict, courses: list[dict]
) -> None:
    request = load_fixture("time-event-query.demo.json")
    request["event"] = {"start": None, "end": None, "date": "2026-09-21", "precision": "date_only"}
    result = check_time_plan(term, courses, [], request)
    assert result["needs_confirmation"] == ["event_time"]


# ---------------------------------------------------------------------------
# TIME-07 partial 课表保留覆盖范围提示
# ---------------------------------------------------------------------------


def test_time07_partial_coverage_preserved(term: dict, courses: list[dict]) -> None:
    # 只保留第 1、3 周有课的课程：第 2、4 周没有数据，不能输出“全学期有空”
    partial = [deepcopy(courses[0])]
    request = load_fixture("time-deadline-query.demo.json")
    result = check_time_plan(term, partial, [], request)
    assert result["coverage"]["scope"] == "selected_weeks"
    assert result["coverage"]["week_numbers"] == [1, 3]
    assert result["coverage"]["completeness"] == "partial"


# ---------------------------------------------------------------------------
# TIME-08 调休日替换不重复叠加
# ---------------------------------------------------------------------------


def test_time08_override_replace_not_stacked(term: dict, courses: list[dict]) -> None:
    calendar = deepcopy(term)
    # 2026-09-21（第 3 周周一）调休，替换为第 3 周周二的模板（CS103 第 5-6 节）
    calendar["overrides"] = [
        {
            "date": "2026-09-21",
            "action": "replace",
            "teaching_week": 3,
            "weekday": 2,
            "source_ref": "虚构调休通知",
        }
    ]
    events, _ = expand_occurrences(
        calendar, courses, {"start": "2026-09-21T00:00:00+08:00", "end": "2026-09-22T00:00:00+08:00"}
    )
    # 当日只有替换后的 CS103，原周一模板（CS101/CS102）不再叠加
    assert [e["course_id"] for e in events] == ["demo-CS103"]
    assert events[0]["start"] == "2026-09-21T14:00:00+08:00"


def test_time08_override_cancel_removes_day(term: dict, courses: list[dict]) -> None:
    calendar = deepcopy(term)
    calendar["overrides"] = [
        {
            "date": "2026-09-21",
            "action": "cancel",
            "teaching_week": None,
            "weekday": None,
            "source_ref": "虚构停课通知",
        }
    ]
    events, _ = expand_occurrences(term, courses, WINDOW)
    cancelled, _ = expand_occurrences(calendar, courses, WINDOW)
    assert len(cancelled) == 0
    assert len(events) == 2


def test_override_replace_requires_template(term: dict) -> None:
    calendar = deepcopy(term)
    calendar["overrides"] = [
        {
            "date": "2026-09-21",
            "action": "replace",
            "teaching_week": None,
            "weekday": None,
            "source_ref": "非法调休",
        }
    ]
    with pytest.raises(AppError) as excinfo:
        expand_occurrences(calendar, [], None)
    assert excinfo.value.status_code == 422
    assert any(e.code == "replace_requires_template" for e in excinfo.value.field_errors)


def test_override_cancel_must_not_carry_template(term: dict) -> None:
    calendar = deepcopy(term)
    calendar["overrides"] = [
        {
            "date": "2026-09-21",
            "action": "cancel",
            "teaching_week": 3,
            "weekday": 1,
            "source_ref": "非法停课",
        }
    ]
    with pytest.raises(AppError) as excinfo:
        expand_occurrences(calendar, [], None)
    assert any(e.code == "cancel_must_not_set_template" for e in excinfo.value.field_errors)


def test_week1_monday_must_be_monday(term: dict) -> None:
    calendar = deepcopy(term)
    calendar["week1_monday"] = "2026-09-08"  # 周二
    with pytest.raises(AppError) as excinfo:
        expand_occurrences(calendar, [], None)
    assert any(e.code == "not_monday" for e in excinfo.value.field_errors)


# ---------------------------------------------------------------------------
# 任务 busy 语义与 ICS 导出
# ---------------------------------------------------------------------------


def test_task_event_is_busy_but_due_is_not(term: dict, courses: list[dict]) -> None:
    task = {
        "notice_id": "demo-notice-01",
        "event": {
            "start": "2026-09-21T09:40:00+08:00",
            "end": "2026-09-21T10:10:00+08:00",
            "date": None,
            "precision": "datetime",
        },
        "due": {"at": "2026-09-21T10:10:00+08:00", "date": None, "precision": "datetime"},
    }
    request = load_fixture("time-deadline-query.demo.json")
    result = check_time_plan(term, courses, [task], request)
    # 任务事件占满 09:40-10:10 后，窗口内不再有 ≥20 分钟的空档
    assert result["candidate_slots"] == []
    # due 本身不是 busy block：去掉任务 event 后候选恢复
    task["event"] = {"start": None, "end": None, "date": None, "precision": "unknown"}
    result = check_time_plan(term, courses, [task], request)
    assert result["candidate_slots"] != []


def test_export_ics_contains_expanded_events(term: dict, courses: list[dict]) -> None:
    ics = export_ics(term, courses, None)
    assert "BEGIN:VCALENDAR" in ics
    assert "TZID=Asia/Shanghai" in ics
    # 第 1、3 周周一 CS101 各一次
    assert ics.count("demo-CS101-m1@") == 2
    assert "20260921T080000" in ics

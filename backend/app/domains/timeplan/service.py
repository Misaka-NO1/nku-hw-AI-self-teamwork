"""空档/冲突/截止可行性的纯函数实现（owner: B）。

规则要点（契约 v1.0.0）：

- 半开区间 ``[start, end)``：前一活动 10:00 结束、后一活动 10:00 开始不算冲突。
- 重叠判定：``a.start < b.end and b.start < a.end``。
- 空档先合并忙碌区间，再从 window 取补集，只返回长度不少于 ``min_minutes`` 的连续段。
- ``buffers`` 先放大忙碌区间，再裁剪到查询窗口。
- 截止（due）不是 busy block；没有预计耗时或精确截止时刻时返回
  ``needs_confirmation``，不擅自使用 23:59，也不移动课程或截止时间。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from app.core.contracts import validate_contract
from app.core.envelope import FieldError
from app.core.errors import AppError
from app.domains.schedule.service import (
    CALCULATION_VERSION,
    expand_occurrences,
    format_datetime,
    parse_datetime,
)

# kind 取值遵循 contracts/api.schema.json 的 TimeResult 枚举。
FREE_TIME_KIND = "free_time"
EVENT_CONFLICT_KIND = "event_conflict"
DEADLINE_FEASIBILITY_KIND = "deadline_feasibility"

# calculation_version 由 D 的适配层放入外层 meta，不进入 data（TimeResult 不允许该字段）。
__all__ = ["CALCULATION_VERSION"]


# ---------------------------------------------------------------------------
# 区间工具（全部为半开区间）
# ---------------------------------------------------------------------------


def _clip(start: datetime, end: datetime, window_start: datetime, window_end: datetime):
    clipped_start = max(start, window_start)
    clipped_end = min(end, window_end)
    if clipped_start < clipped_end:
        return clipped_start, clipped_end
    return None


def _merge(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """合并重叠或首尾相接的半开区间。"""

    merged: list[tuple[datetime, datetime]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            last_start, last_end = merged[-1]
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _minutes(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


# ---------------------------------------------------------------------------
# find_free_slots
# ---------------------------------------------------------------------------


def _coverage_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """根据事件的教学周覆盖情况给出诚实的结果覆盖说明。"""

    weeks = sorted({event["week"] for event in events if isinstance(event.get("week"), int)})
    if not weeks:
        return {"scope": "unknown", "week_numbers": [], "completeness": "unknown"}
    return {
        "scope": "selected_weeks",
        "week_numbers": weeks,
        "completeness": "unknown",
    }


def find_free_slots(
    actual_events: Iterable[dict[str, Any]],
    window: dict[str, str],
    min_minutes: int,
    buffers: dict[str, int],
) -> dict[str, Any]:
    """在已知安排下查询 window 内的空档。

    返回 ``{kind, slots, coverage, needs_confirmation}``；
    结果只代表“基于已导入安排”的空档，不保证用户一定有空。
    """

    validate_contract(
        {"workspace_ref": "validation", "window": window, "min_minutes": min_minutes,
         "buffers": buffers},
        "FreeTimeQuery",
    )
    window_start = parse_datetime(window["start"], field="window.start")
    window_end = parse_datetime(window["end"], field="window.end")
    if not window_start < window_end:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="window.start must be earlier than window.end",
            field_errors=[
                FieldError(field="window", code="window_order", message="window.start 必须早于 window.end")
            ],
        )

    events = list(actual_events)
    before = timedelta(minutes=buffers["before_minutes"])
    after = timedelta(minutes=buffers["after_minutes"])

    busy: list[tuple[datetime, datetime]] = []
    for event in events:
        start = parse_datetime(event["start"], field="start")
        end = parse_datetime(event["end"], field="end")
        if not start < end:
            raise AppError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="event start must be earlier than end",
                field_errors=[
                    FieldError(field="events", code="interval_order", message="事件开始必须早于结束")
                ],
            )
        clipped = _clip(start - before, end + after, window_start, window_end)
        if clipped is not None:
            busy.append(clipped)

    merged = _merge(busy)

    slots: list[dict[str, Any]] = []
    cursor = window_start
    for busy_start, busy_end in merged:
        if cursor < busy_start:
            slots.append((cursor, busy_start))
        cursor = max(cursor, busy_end)
    if cursor < window_end:
        slots.append((cursor, window_end))

    result_slots = [
        {
            "start": format_datetime(start),
            "end": format_datetime(end),
            "duration_minutes": _minutes(start, end),
        }
        for start, end in slots
        if _minutes(start, end) >= min_minutes
    ]

    return {
        "kind": FREE_TIME_KIND,
        "slots": result_slots,
        "coverage": _coverage_from_events(events),
        "needs_confirmation": [],
    }


# ---------------------------------------------------------------------------
# check_time_plan
# ---------------------------------------------------------------------------


def _coverage_from_courses(calendar: dict[str, Any], courses: list[dict[str, Any]]) -> dict[str, Any]:
    weeks = sorted(
        {week for course in courses for meeting in course["meetings"] for week in meeting["weeks"]}
    )
    full = set(range(1, calendar["teaching_weeks"] + 1))
    if set(weeks) == full:
        return {"scope": "term", "week_numbers": weeks, "completeness": "unknown"}
    return {"scope": "selected_weeks", "week_numbers": weeks, "completeness": "partial"}


def _task_busy_events(tasks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """把带精确事件时间的任务转换为 busy 来源；截止（due）不是 busy block。"""

    events: list[dict[str, Any]] = []
    for task in tasks:
        event = task.get("event") or {}
        if event.get("precision") != "datetime":
            continue
        if not event.get("start") or not event.get("end"):
            continue
        events.append(
            {
                "event_id": f"task:{task.get('notice_id', 'unknown')}",
                "start": event["start"],
                "end": event["end"],
            }
        )
    return events


def check_time_plan(
    calendar: dict[str, Any],
    courses: Iterable[dict[str, Any]],
    tasks: Iterable[dict[str, Any]],
    request: dict[str, Any],
) -> dict[str, Any]:
    """检查事件冲突或截止前可行性。

    ``request`` 结构遵循 ``TimeCheckRequest``（允许缺少 ``workspace_ref``，
    该字段由 D 的适配层注入与校验）。不自动移动已有日程或截止时间。
    """

    validate_contract(
        {"workspace_ref": request.get("workspace_ref", "validation"), **{k: v for k, v in request.items() if k != "workspace_ref"}},
        "TimeCheckRequest",
    )
    courses = list(courses)
    tasks = list(tasks)
    coverage = _coverage_from_courses(calendar, courses)

    window = request["window"]
    window_start = parse_datetime(window["start"], field="window.start")
    window_end = parse_datetime(window["end"], field="window.end")
    if not window_start < window_end:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="window.start must be earlier than window.end",
            field_errors=[
                FieldError(field="window", code="window_order", message="window.start 必须早于 window.end")
            ],
        )

    course_events, _ = expand_occurrences(calendar, courses, window)
    busy_sources = course_events + _task_busy_events(tasks)

    kind = request["kind"]
    if kind == EVENT_CONFLICT_KIND:
        return _check_event_conflict(busy_sources, request, coverage, window_start, window_end)
    return _check_deadline_feasibility(busy_sources, request, coverage, window_start, window_end)


def _check_event_conflict(
    busy_sources: list[dict[str, Any]],
    request: dict[str, Any],
    coverage: dict[str, Any],
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    needs_confirmation: list[str] = []
    event = request.get("event")
    if (
        event is None
        or event.get("precision") != "datetime"
        or not event.get("start")
        or not event.get("end")
    ):
        needs_confirmation.append("event_time")
        return {
            "kind": EVENT_CONFLICT_KIND,
            "conflicts": [],
            "coverage": coverage,
            "needs_confirmation": needs_confirmation,
        }

    event_start = parse_datetime(event["start"], field="event.start")
    event_end = parse_datetime(event["end"], field="event.end")
    if not event_start < event_end:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="event.start must be earlier than event.end",
            field_errors=[
                FieldError(field="event", code="interval_order", message="event.start 必须早于 event.end")
            ],
        )

    conflicts: list[dict[str, Any]] = []
    for source in busy_sources:
        source_start = parse_datetime(source["start"], field="start")
        source_end = parse_datetime(source["end"], field="end")
        intersection = _clip(source_start, source_end, event_start, event_end)
        if intersection is None:
            continue
        conflicts.append(
            {
                "source_event_id": source["event_id"],
                "intersection_start": format_datetime(intersection[0]),
                "intersection_end": format_datetime(intersection[1]),
            }
        )
    conflicts.sort(key=lambda item: (item["intersection_start"], item["source_event_id"]))

    return {
        "kind": EVENT_CONFLICT_KIND,
        "conflicts": conflicts,
        "coverage": coverage,
        "needs_confirmation": needs_confirmation,
    }


def _check_deadline_feasibility(
    busy_sources: list[dict[str, Any]],
    request: dict[str, Any],
    coverage: dict[str, Any],
    window_start: datetime,
    window_end: datetime,
) -> dict[str, Any]:
    needs_confirmation: list[str] = []

    due = request.get("due")
    due_at: datetime | None = None
    if due is None or due.get("precision") != "datetime" or not due.get("at"):
        # date_only 或 unknown：不擅自补 23:59，也不猜测具体时刻
        needs_confirmation.append("due_time")
    else:
        due_at = parse_datetime(due["at"], field="due.at")

    estimated_minutes = request.get("estimated_minutes")
    if estimated_minutes is None:
        needs_confirmation.append("estimated_minutes")

    earliest_start_raw = request.get("earliest_start")
    earliest_start: datetime | None = None
    if not earliest_start_raw:
        needs_confirmation.append("earliest_start")
    else:
        earliest_start = parse_datetime(earliest_start_raw, field="earliest_start")

    if needs_confirmation:
        return {
            "kind": DEADLINE_FEASIBILITY_KIND,
            "candidate_slots": [],
            "coverage": coverage,
            "needs_confirmation": needs_confirmation,
        }

    assert due_at is not None and earliest_start is not None and estimated_minutes is not None

    search_start = max(window_start, earliest_start)
    search_end = min(window_end, due_at)
    if not search_start < search_end:
        return {
            "kind": DEADLINE_FEASIBILITY_KIND,
            "candidate_slots": [],
            "coverage": coverage,
            "needs_confirmation": [],
        }

    free = find_free_slots(
        busy_sources,
        {"start": format_datetime(search_start), "end": format_datetime(search_end)},
        estimated_minutes,
        request["buffers"],
    )

    duration = timedelta(minutes=estimated_minutes)
    candidate_slots = []
    for slot in free["slots"]:
        slot_start = parse_datetime(slot["start"], field="start")
        candidate_slots.append(
            {
                "start": slot["start"],
                "end": format_datetime(slot_start + duration),
                "duration_minutes": estimated_minutes,
            }
        )

    return {
        "kind": DEADLINE_FEASIBILITY_KIND,
        "candidate_slots": candidate_slots,
        "coverage": coverage,
        "needs_confirmation": [],
    }

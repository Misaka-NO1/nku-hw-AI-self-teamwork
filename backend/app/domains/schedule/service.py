"""课表校验与周次展开的纯函数实现（owner: B）。

规则要点（契约 v1.0.0）：

- 所有时间使用 Asia/Shanghai（固定 UTC+8），ISO 字符串必须带 ``+08:00`` 偏移。
- 时间区间为半开区间 ``[start, end)``。
- 课程按 ``date = week1_monday + 7 * (week - 1) + (weekday - 1)`` 展开。
- 先应用 TermCalendar 的 overrides（调休 cancel/replace），再生成实际课程；
  replace 的日期只使用替换模板，不与当日原模板叠加。
- 本模块不猜测真实教务数据；所有输入都是调用方给出的 payload 字典。
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable

from app.core.contracts import validate_contract
from app.core.envelope import FieldError
from app.core.errors import AppError

# 合同规定统一使用 Asia/Shanghai；该平台为固定 UTC+8，不涉及时区换算，
# 使用固定偏移避免对操作系统 tzdata 的隐式依赖。
SHANGHAI_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

CALCULATION_VERSION = "time-v1"


# ---------------------------------------------------------------------------
# 时间解析辅助
# ---------------------------------------------------------------------------


def parse_datetime(value: str, *, field: str) -> datetime:
    """解析必须带偏移的 ISO datetime，并归一化到 Asia/Shanghai。"""

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - 结构校验通常已拦截
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Invalid ISO datetime",
            field_errors=[FieldError(field=field, code="format", message=str(exc))],
        ) from exc
    if parsed.tzinfo is None:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Datetime must carry an explicit offset such as +08:00",
            field_errors=[
                FieldError(field=field, code="timezone_required", message="缺少时区偏移")
            ],
        )
    return parsed.astimezone(SHANGHAI_TZ)


def parse_date(value: str, *, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Invalid ISO date",
            field_errors=[FieldError(field=field, code="format", message=str(exc))],
        ) from exc


def format_datetime(value: datetime) -> str:
    return value.astimezone(SHANGHAI_TZ).isoformat()


# ---------------------------------------------------------------------------
# TermCalendar 语义校验
# ---------------------------------------------------------------------------


def _validate_calendar(calendar: dict[str, Any], *, field_prefix: str = "term") -> None:
    errors: list[FieldError] = []

    week1_monday = parse_date(calendar["week1_monday"], field=f"{field_prefix}.week1_monday")
    if week1_monday.weekday() != 0:  # Monday == 0
        errors.append(
            FieldError(
                field=f"{field_prefix}.week1_monday",
                code="not_monday",
                message="week1_monday 必须是周一",
            )
        )

    periods = calendar["periods"]
    seen_periods: set[int] = set()
    previous_end: time | None = None
    for index, period in enumerate(periods):
        field = f"{field_prefix}.periods.{index}"
        if period["period"] in seen_periods:
            errors.append(
                FieldError(field=field, code="duplicate", message="节次编号重复")
            )
        seen_periods.add(period["period"])
        start = time.fromisoformat(period["start"])
        end = time.fromisoformat(period["end"])
        if not start < end:
            errors.append(
                FieldError(
                    field=field,
                    code="period_order",
                    message="节次开始时间必须早于结束时间",
                )
            )
        if previous_end is not None and start < previous_end:
            errors.append(
                FieldError(
                    field=field,
                    code="periods_not_ordered",
                    message="节次时间必须有序且不重叠",
                )
            )
        previous_end = end

    for index, override in enumerate(calendar["overrides"]):
        field = f"{field_prefix}.overrides.{index}"
        if override["action"] == "replace":
            if override["teaching_week"] is None or override["weekday"] is None:
                errors.append(
                    FieldError(
                        field=field,
                        code="replace_requires_template",
                        message="replace 必须给出 teaching_week 和 weekday",
                    )
                )
            elif not 1 <= override["teaching_week"] <= calendar["teaching_weeks"]:
                errors.append(
                    FieldError(
                        field=field,
                        code="week_out_of_range",
                        message="replace 的 teaching_week 超出教学周范围",
                    )
                )
        else:  # cancel
            if override["teaching_week"] is not None or override["weekday"] is not None:
                errors.append(
                    FieldError(
                        field=field,
                        code="cancel_must_not_set_template",
                        message="cancel 不能携带 teaching_week 或 weekday",
                    )
                )

    if errors:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="TermCalendar semantics invalid",
            field_errors=errors,
        )


# ---------------------------------------------------------------------------
# validate_timetable
# ---------------------------------------------------------------------------


def _meeting_signature(meeting: dict[str, Any]) -> str:
    """识别同一 offering 下完全重复的 meeting（不误删同课程的不同 meeting）。"""

    canonical = json.dumps(
        {
            "weekday": meeting["weekday"],
            "weeks": meeting["weeks"],
            "start_period": meeting["start_period"],
            "end_period": meeting["end_period"],
            "location": meeting["location"],
            "campus_id": meeting["campus_id"],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return canonical


def validate_timetable(payload: dict[str, Any]) -> dict[str, Any]:
    """校验并规范化一个 TimetableImport payload。

    返回 ``{normalized_payload, issues, payload_hash, coverage}``；不保存任何数据。
    结构或语义不合法时抛出 ``AppError(422, VALIDATION_ERROR)``，由 D 的适配层
    映射为 HTTP 422 / MCP 业务错误。
    """

    validate_contract(payload, "TimetableImport")
    normalized = deepcopy(payload)
    _validate_calendar(normalized["term"], field_prefix="term")

    calendar = normalized["term"]
    teaching_weeks = calendar["teaching_weeks"]
    period_numbers = {period["period"] for period in calendar["periods"]}

    issues: list[dict[str, Any]] = []
    errors: list[FieldError] = []

    for course_index, course in enumerate(normalized["courses"]):
        seen_signatures: set[str] = set()
        kept_meetings: list[dict[str, Any]] = []
        for meeting_index, meeting in enumerate(course["meetings"]):
            field = f"courses.{course_index}.meetings.{meeting_index}"

            weeks = sorted(set(meeting["weeks"]))
            meeting["weeks"] = weeks

            out_of_range = [w for w in weeks if w < 1 or w > teaching_weeks]
            if out_of_range:
                errors.append(
                    FieldError(
                        field=f"{field}.weeks",
                        code="week_out_of_range",
                        message=f"周次 {out_of_range} 超出教学周范围 1..{teaching_weeks}，"
                        "请修正原文而不是猜测",
                    )
                )

            if meeting["start_period"] > meeting["end_period"]:
                errors.append(
                    FieldError(
                        field=field,
                        code="period_order",
                        message="start_period 不能大于 end_period",
                    )
                )
            for period_field in ("start_period", "end_period"):
                if meeting[period_field] not in period_numbers:
                    errors.append(
                        FieldError(
                            field=f"{field}.{period_field}",
                            code="unknown_period",
                            message="节次不存在于学期日历中",
                        )
                    )

            signature = _meeting_signature(meeting)
            if signature in seen_signatures:
                issues.append(
                    {
                        "code": "duplicate_meeting",
                        "field": field,
                        "message": "同一 offering 下完全重复的 meeting 已去重",
                        "blocking": False,
                    }
                )
                continue
            seen_signatures.add(signature)
            kept_meetings.append(meeting)
        course["meetings"] = kept_meetings

    if errors:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="TimetableImport semantics invalid",
            field_errors=errors,
        )

    payload_hash = hashlib.sha256(
        json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()

    return {
        "normalized_payload": normalized,
        "issues": issues,
        "payload_hash": payload_hash,
        "coverage": deepcopy(normalized["source"]["coverage"]),
    }


# ---------------------------------------------------------------------------
# expand_occurrences
# ---------------------------------------------------------------------------


def _template_map(calendar: dict[str, Any]) -> dict[date, tuple[int, int] | None]:
    """构造 实际日期 -> (teaching_week, weekday) 模板映射，并应用 overrides。

    - 默认每个实际日期使用自己的 (week, weekday) 模板；
    - ``cancel``：该实际日期不生成任何课程；
    - ``replace``：该实际日期改用指定 (teaching_week, weekday) 的模板，
      不再保留当日原模板（不两套叠加）。
    """

    week1_monday = date.fromisoformat(calendar["week1_monday"])
    mapping: dict[date, tuple[int, int] | None] = {}
    for week in range(1, calendar["teaching_weeks"] + 1):
        for weekday in range(1, 8):
            actual = week1_monday + timedelta(days=7 * (week - 1) + (weekday - 1))
            mapping[actual] = (week, weekday)
    for override in calendar["overrides"]:
        actual = date.fromisoformat(override["date"])
        if override["action"] == "cancel":
            mapping[actual] = None
        else:
            mapping[actual] = (override["teaching_week"], override["weekday"])
    return mapping


def expand_occurrences(
    calendar: dict[str, Any],
    courses: Iterable[dict[str, Any]],
    window: dict[str, str] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """把课程按教学周/星期/节次展开为实际事件。

    返回 ``(actual_events, warnings)``。每个事件含
    ``event_id, course_id, offering_id, meeting_id, title, location,
    week, weekday, start, end``，``start/end`` 为带 ``+08:00`` 的半开区间。
    """

    validate_contract(calendar, "TermCalendar")
    _validate_calendar(calendar, field_prefix="calendar")

    warnings: list[dict[str, str]] = []
    if calendar["calendar_status"] != "official_verified":
        warnings.append(
            {
                "code": "calendar_not_official",
                "message": f"校历状态为 {calendar['calendar_status']}，展开结果基于该状态",
            }
        )

    window_start: datetime | None = None
    window_end: datetime | None = None
    if window is not None:
        window_start = parse_datetime(window["start"], field="window.start")
        window_end = parse_datetime(window["end"], field="window.end")
        if not window_start < window_end:
            raise AppError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="window.start must be earlier than window.end",
                field_errors=[
                    FieldError(
                        field="window",
                        code="window_order",
                        message="window.start 必须早于 window.end",
                    )
                ],
            )

    periods = {period["period"]: period for period in calendar["periods"]}
    mapping = _template_map(calendar)

    events: list[dict[str, Any]] = []
    for actual_date, template in sorted(mapping.items()):
        if template is None:
            continue
        week, weekday = template
        for course in courses:
            for meeting in course["meetings"]:
                if meeting["weekday"] != weekday or week not in meeting["weeks"]:
                    continue
                start_period = periods[meeting["start_period"]]
                end_period = periods[meeting["end_period"]]
                start = datetime.combine(
                    actual_date, time.fromisoformat(start_period["start"]), SHANGHAI_TZ
                )
                end = datetime.combine(
                    actual_date, time.fromisoformat(end_period["end"]), SHANGHAI_TZ
                )
                if window_start is not None and not (start < window_end and window_start < end):
                    continue
                events.append(
                    {
                        "event_id": f"{meeting['meeting_id']}@{actual_date.isoformat()}",
                        "course_id": course["course_id"],
                        "offering_id": course["offering_id"],
                        "meeting_id": meeting["meeting_id"],
                        "title": course["title"],
                        "location": meeting["location"],
                        "week": week,
                        "weekday": weekday,
                        "start": format_datetime(start),
                        "end": format_datetime(end),
                    }
                )

    events.sort(key=lambda item: (item["start"], item["event_id"]))
    return events, warnings


# ---------------------------------------------------------------------------
# ICS 导出（B11：对已确认课程按实际日期导出）
# ---------------------------------------------------------------------------


def export_ics(
    calendar: dict[str, Any],
    courses: Iterable[dict[str, Any]],
    window: dict[str, str] | None = None,
) -> str:
    """把已确认课程展开为 ICS 文本。

    时间使用 Asia/Shanghai 本地浮动时间（``TZID=Asia/Shanghai``），
    调休替换已按实际日期展开；校历未覆盖的例外不做猜测。
    """

    events, _ = expand_occurrences(calendar, courses, window)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//nku-campus-assistant//schedule//CN",
        "CALSCALE:GREGORIAN",
    ]
    for event in events:
        start = parse_datetime(event["start"], field="start")
        end = parse_datetime(event["end"], field="end")
        description = _ics_escape(f"第{event['week']}教学周 · 数据来源基于已确认课表")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{event['event_id']}@nku-campus-assistant.demo",
                f"DTSTAMP:{datetime.now(SHANGHAI_TZ).strftime('%Y%m%dT%H%M%S')}",
                f"DTSTART;TZID=Asia/Shanghai:{start.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND;TZID=Asia/Shanghai:{end.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{_ics_escape(event['title'])}",
                f"LOCATION:{_ics_escape(event['location'] or '')}",
                f"DESCRIPTION:{description}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )

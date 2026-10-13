"""Bounded, read-only clock labels for an already owner-authorized timetable.

This is a response projection, never a saved timetable or an authorization
source. Keep the original timetable intact for validators and date/override
calculations; the labels resolve inclusive meeting period endpoints only.
"""
import re

MAX_RESOLVED_MEETINGS = 300
MAX_PERIODS = 128
MAX_COURSES = 300
CLOCK = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _text(value, limit):
    return value if isinstance(value, str) and len(value) <= limit else None


def _period_table(term):
    rows = term.get("periods") if isinstance(term, dict) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_PERIODS:
        return {}, set(), "invalid_period_table"
    periods, duplicates = {}, set()
    for row in rows:
        if not isinstance(row, dict) or type(row.get("period")) is not int or row["period"] < 1:
            return {}, set(), "invalid_period_table"
        number = row["period"]
        if number in periods:
            duplicates.add(number)
        start, end = row.get("start"), row.get("end")
        valid = (isinstance(start, str) and isinstance(end, str)
                 and CLOCK.fullmatch(start) and CLOCK.fullmatch(end) and start < end)
        periods[number] = (start, end) if valid else None
    return periods, duplicates, None


def _meeting(course, meeting, periods, duplicates, table_error):
    course = course if isinstance(course, dict) else {}
    meeting = meeting if isinstance(meeting, dict) else {}
    first, last = meeting.get("start_period"), meeting.get("end_period")
    range_valid = (type(first) is int and type(last) is int
                   and 1 <= first <= last and last - first < MAX_PERIODS)
    weeks, weekday = meeting.get("weeks"), meeting.get("weekday")
    weeks_valid = (isinstance(weeks, list) and 1 <= len(weeks) <= 60
                   and all(type(week) is int and 1 <= week <= 60 for week in weeks)
                   and len(set(weeks)) == len(weeks))
    title = _text(course.get("title"), 512)
    item = {
        "course_id": _text(course.get("course_id"), 128),
        "offering_id": _text(course.get("offering_id"), 128),
        "meeting_id": _text(meeting.get("meeting_id"), 128),
        "course_title": title,
        "weekday": weekday if type(weekday) is int and 1 <= weekday <= 7 else None,
        "weeks": list(weeks) if weeks_valid else [],
        "start_period": first if range_valid else None,
        "end_period": last if range_valid else None,
        "period_label": f"第{first}—{last}节" if range_valid else None,
        "location": _text(meeting.get("location"), 512),
        "start_time": None, "end_time": None, "time_label": "时间无法确定",
        "time_status": "unavailable", "time_error": None,
    }
    reason = table_error
    if reason is None and not range_valid:
        reason = "invalid_period_range"
    if reason is None:
        included = range(first, last + 1)
        if any(number in duplicates for number in included):
            reason = "duplicate_period"
        elif any(number not in periods for number in included):
            reason = "missing_period"
        elif any(periods[number] is None for number in included):
            reason = "invalid_period_time"
        elif any(periods[number][1] > periods[number + 1][0]
                 for number in range(first, last)):
            reason = "overlapping_period_times"
    if reason is None and (title is None or not all(item[key] for key in
            ("course_id", "offering_id", "meeting_id")) or not weeks_valid or item["weekday"] is None
            or (meeting.get("location") is not None and item["location"] is None)):
        reason = "invalid_meeting_metadata"
    if reason is None:
        start, end = periods[first][0], periods[last][1]
        item.update(start_time=start, end_time=end, time_label=f"{start}–{end}", time_status="available")
    else:
        item["time_error"] = reason
    return item


def project_schedule_meetings(records):
    """Add labels only after the caller's provider has enforced owner access.

    No schedule stays exactly absent. Oversized/malformed source data is never
    silently reported as an empty timetable; the projection carries explicit
    completeness metadata, while the untouched source remains available.
    """
    schedule = records.get("schedule")
    if not isinstance(schedule, dict):
        return records
    timetable = schedule.get("timetable")
    courses = timetable.get("courses") if isinstance(timetable, dict) else None
    resolved, warnings = [], []
    total = 0
    malformed = not isinstance(courses, list)
    truncated = False
    if not malformed:
        if len(courses) > MAX_COURSES:
            truncated = True
        periods, duplicates, table_error = _period_table(timetable.get("term"))
        for course in courses[:MAX_COURSES]:
            meetings = course.get("meetings") if isinstance(course, dict) else None
            if not isinstance(meetings, list) or not meetings:
                malformed = True
                continue
            total += len(meetings)
            remaining = MAX_RESOLVED_MEETINGS - len(resolved)
            for meeting in meetings[:remaining]:
                resolved.append(_meeting(course, meeting, periods, duplicates, table_error))
            if len(meetings) > remaining:
                truncated = True
    unavailable = sum(item["time_status"] != "available" for item in resolved)
    if malformed:
        warnings.append("invalid_timetable_structure")
    if unavailable:
        warnings.append("some_meeting_times_unavailable")
    if truncated:
        warnings.append("projection_truncated_use_original_timetable")
    if isinstance(courses, list) and not courses:
        warnings.append("invalid_timetable_structure")
    meta = {
        "version": "meeting-clock-v1", "timezone": "Asia/Shanghai",
        "complete": not warnings, "truncated": truncated,
        "returned_meetings": len(resolved), "unavailable_meetings": unavailable,
        "source_meetings_in_scanned_courses": total, "warnings": warnings,
        "date_filter_applied": False,
        "date_rule": "按查询日期筛选weekday、weeks并应用原term.overrides；本列表不是某日的全部安排。",
    }
    return {**records, "schedule": {**schedule,
        "resolved_meetings": resolved, "resolved_meetings_meta": meta}}

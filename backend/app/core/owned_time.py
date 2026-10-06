"""Time adapters over owner-authorized records, never caller-supplied schedules.

The existing B contracts/algorithms remain authoritative. OAuth removes only
workspace_ref from the input: the database grant determines it, not the model.
"""
from app.core.contracts import validate_boundary
from app.core.demo import enforce_demo_fixture
from app.core.domain_adapter import _notice_events
from app.core.errors import AppError
from app.core.platform_query import decode_platform_query
from app.domains.schedule import service as schedule
from app.domains.timeplan import service as timeplan


def decode_owned_time(arguments, operation):
    validate_boundary(arguments, "OAuthPilotTimeQueryRequest")
    payload = decode_platform_query(arguments)
    if "workspace_ref" in payload:
        raise AppError(422, "VALIDATION_ERROR", "OAuth owner is determined by the grant, not query_json")
    # Use the canonical business schema, without introducing defaults or
    # changing null/arrays. The placeholder is for validation only, not access.
    validate_boundary({"workspace_ref": "oauth-owned-validation", **payload},
                      "FreeTimeQuery" if operation == "free" else "TimeCheckRequest")
    return payload


def calculate_owned_time(records, payload, operation, *, allow_notice_text=False):
    if records["schedule"] is None:
        raise AppError(404, "NOT_FOUND", "Save your fixture timetable first")
    timetable = records["schedule"]["timetable"]
    if allow_notice_text:
        from app.core.notice_plan import resources
        timetable, notices, _ = resources(records)
    else:
        notices = [item["notice"] for item in records["tasks"]]
        enforce_demo_fixture(timetable, "schedule")
        for notice in notices:
            enforce_demo_fixture(notice, "task")
    events, warnings = schedule.expand_occurrences(timetable["term"], timetable["courses"], payload["window"])
    result = (timeplan.find_free_slots(events + _notice_events(notices), payload["window"],
                                      payload["min_minutes"], payload["buffers"])
              if operation == "free" else
              timeplan.check_time_plan(timetable["term"], timetable["courses"], notices, payload))
    validate_boundary(result, "TimeResult")
    return result, warnings

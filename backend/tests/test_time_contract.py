"""时间结果与 contracts/api.schema.json 的一致性契约测试（PR #2 审核意见 1）。

用领域函数的真实返回值直接校验 TimeResult，防止实现与公共接口漂移。
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from app.domains.schedule import expand_occurrences
from app.domains.timeplan import check_time_plan, find_free_slots

REPO_ROOT = Path(__file__).parents[2]
FIXTURES = REPO_ROOT / "fixtures"


def _time_result_validator() -> Draft202012Validator:
    schema = json.loads((REPO_ROOT / "contracts" / "api.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(
        {
            "$schema": schema["$schema"],
            "$ref": "#/$defs/TimeResult",
            "$defs": schema["$defs"],
        },
        format_checker=FormatChecker(),
    )


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_find_free_slots_result_matches_time_result_contract() -> None:
    term = _load("term.demo.json")
    courses = _load("timetable.demo.json")["courses"]
    window = {"start": "2026-09-21T08:00:00+08:00", "end": "2026-09-21T12:00:00+08:00"}
    events, _ = expand_occurrences(term, courses, window)
    result = find_free_slots(events, window, 30, {"before_minutes": 0, "after_minutes": 0})
    _time_result_validator().validate(result)
    assert result["kind"] == "free_time"
    assert "calculation_version" not in result


def test_check_time_plan_results_match_time_result_contract() -> None:
    term = _load("term.demo.json")
    courses = _load("timetable.demo.json")["courses"]

    event_result = check_time_plan(term, courses, [], _load("time-event-query.demo.json"))
    _time_result_validator().validate(event_result)
    assert event_result["kind"] == "event_conflict"
    assert "calculation_version" not in event_result

    deadline_result = check_time_plan(term, courses, [], _load("time-deadline-query.demo.json"))
    _time_result_validator().validate(deadline_result)
    assert deadline_result["kind"] == "deadline_feasibility"
    assert "calculation_version" not in deadline_result

    pending = _load("time-deadline-query.demo.json")
    pending["estimated_minutes"] = None
    pending_result = check_time_plan(term, courses, [], pending)
    _time_result_validator().validate(pending_result)
    assert "estimated_minutes" in pending_result["needs_confirmation"]

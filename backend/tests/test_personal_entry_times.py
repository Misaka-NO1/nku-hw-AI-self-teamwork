"""Local regressions for the user's numbered selection and midnight DDL."""
import pytest

from app.core.errors import AppError
from app.core.personal_tasks import PersonalTaskService, content
from app.domains.schedule.service import parse_datetime


def test_original_schedule_parser_reproduces_24_hour_error():
    # Personal-entry compatibility must not alter B's general schedule parser.
    with pytest.raises(AppError) as error:
        parse_datetime("2026-10-13T24:00:00+08:00", field="due_at")
    assert error.value.message == "Invalid ISO datetime"


def test_selected_afternoon_and_end_of_day_deadline():
    result = content({"title": "本地虚构日期验收", "kind": "deadline",
        "due_at": "2026-10-13T24:00:00+08:00",
        "scheduled_slots": [{"start": "2026-10-09T15:00:00+08:00",
                             "end": "2026-10-09T17:00:00+08:00"}]})
    assert result["due_at"] == "2026-10-14T00:00:00+08:00"
    assert result["scheduled_slots"] == [{"start": "2026-10-09T15:00:00+08:00",
                                         "end": "2026-10-09T17:00:00+08:00"}]


def test_recommendations_and_lunch_are_not_save_permissions():
    # Saving doesn't require a candidate ID or force a recommended interval.
    result = content({"title": "本人选择", "scheduled_slots": [
        {"start": "2026-10-09T12:30:00+08:00", "end": "2026-10-09T13:00:00+08:00"}]})
    assert result["scheduled_slots"][0]["start"] == "2026-10-09T12:30:00+08:00"


@pytest.mark.parametrize("value, expected", [
    ("2026-12-31T24:00+08:00", "2027-01-01T00:00:00+08:00"),
    ("2028-02-29T24:00:00+08:00", "2028-03-01T00:00:00+08:00"),
    ("2026-10-13T24:00:00Z", "2026-10-14T08:00:00+08:00"),
])
def test_midnight_rollover(value, expected):
    assert content({"title": "测试", "due_at": value})["due_at"] == expected


@pytest.mark.parametrize("value", ["2026-10-13T24:30:00+08:00", "2026-10-13T24:00:01+08:00",
    "2026-10-09T15:00:00", "3点到5点", "", "null", "2026-02-30T24:00:00+08:00"])
def test_invalid_time_has_safe_field_and_no_write(value):
    class NoWrites:
        def personal_call(self, *_):
            pytest.fail("Invalid time must be rejected before storage")
    service = PersonalTaskService(None, NoWrites())
    service.gate = lambda: None
    with pytest.raises(AppError) as error:
        service.draft({}, {"content": {"title": "测试", "due_at": value},
                           "idempotency_key": "local-time-regression-001"})
    assert error.value.status_code == 422
    assert error.value.field_errors[0].field == "content.due_at"
    assert value not in error.value.message if value else True


def test_slot_error_is_indexed():
    with pytest.raises(AppError) as error:
        content({"title": "测试", "scheduled_slots": [{"start": "下午3点", "end": "下午5点"}]})
    assert error.value.field_errors[0].field == "content.scheduled_slots.0.start"


def test_notes_null_is_not_valid_and_missing_notes_defaults_to_string():
    with pytest.raises(AppError) as error:
        content({"title": "测试", "notes": None})
    assert error.value.field_errors[0].field == "content.notes"
    assert content({"title": "测试"})["notes"] == ""
    assert content({"title": "测试", "notes": ""})["notes"] == ""


def test_deadline_constraint_still_preserves_user_values():
    with pytest.raises(AppError):
        content({"title": "测试", "kind": "deadline", "due_at": "2026-10-09T16:00:00+08:00",
            "scheduled_slots": [{"start": "2026-10-09T15:00:00+08:00", "end": "2026-10-09T17:00:00+08:00"}]})

"""Confirmed own tasks, independent of the fictional timetable/notice gates.

No school identifier or workspace supplied by a model establishes ownership.
The existing verified session / freshly scoped OAuth grant does that in PG.
"""
from datetime import date, datetime, timedelta
import re
from secrets import token_urlsafe
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.errors import AppError
from app.core.envelope import FieldError
from app.core.security import payload_hash, require_idempotency_key
from app.domains.schedule.service import parse_datetime


def entry_datetime(value: str, *, field: str) -> str:
    """Canonicalize explicit instants, never infer dates or parse user prose.

    End-of-day 24:00 is the following midnight, not 23:59. Limit this
    compatibility to exact zero minutes/seconds and an explicit UTC offset.
    """
    midnight = re.fullmatch(r"(\d{4}-\d{2}-\d{2})T24:00(?::00)?(Z|[+-]\d{2}:\d{2})", value)
    try:
        if midnight:
            following = date.fromisoformat(midnight[1]) + timedelta(days=1)
            value = f"{following.isoformat()}T00:00:00{midnight[2]}"
        return parse_datetime(value, field=field).isoformat()
    except (AppError, ValueError, OverflowError):
        raise AppError(422, "VALIDATION_ERROR", "请将时间转换为含日期和时区的 ISO 格式；尚未保存",
            field_errors=[FieldError(field=field, code="datetime_format",
                message="时间须包含完整日期、时刻与时区；日末24:00表示次日00:00")]) from None


class Slot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    start: str
    end: str


class EntryContent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["reminder", "deadline", "event"] = "reminder"
    due_at: str | None = None
    due_date: str | None = None
    reminder_at: str | None = None
    notes: str = Field(default="", max_length=2000)
    scheduled_slots: list[Slot] = Field(default_factory=list, max_length=8)
    reminder_minutes: int | None = None

    @model_validator(mode="after")
    def times(self):
        if not self.title.strip():
            raise ValueError("事项标题不能为空")
        self.title = self.title.strip()
        if self.due_at and self.due_date:
            raise ValueError("截止时刻与仅日期只能选一种")
        for name in ("due_at", "reminder_at"):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, entry_datetime(value, field=f"content.{name}"))
        if self.due_date is not None:
            if date.fromisoformat(self.due_date).isoformat() != self.due_date:
                raise ValueError("截止日期格式不正确")
        if self.kind == "deadline" and not (self.due_at or self.due_date):
            raise ValueError("截止任务需要截止日期或时刻")
        if self.reminder_minutes not in (None, 0, 5, 15, 30, 60):
            raise ValueError("提前提醒选项不正确")
        ranges = []
        for index, slot in enumerate(self.scheduled_slots):
            for key in ("start", "end"):
                setattr(slot, key, entry_datetime(getattr(slot, key),
                    field=f"content.scheduled_slots.{index}.{key}"))
            a, b = (parse_datetime(getattr(slot, k), field=k) for k in ("start", "end"))
            if a >= b or (b - a).total_seconds() > 86400:
                raise ValueError("每个安排区间必须递增且不超过一天")
            if self.due_at and b > parse_datetime(self.due_at, field="due_at"):
                raise ValueError("安排不能超过截止时刻")
            if self.due_date and b.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat() > self.due_date:
                raise ValueError("安排不能超过截止日期")
            ranges.append((a, b, slot))
        ranges.sort(key=lambda r: r[0])
        if any(y[0] < x[1] for x, y in zip(ranges, ranges[1:])):
            raise ValueError("所选多个区间不能重叠")
        self.scheduled_slots = [r[2] for r in ranges]
        if self.reminder_minutes is not None and not (self.reminder_at or self.scheduled_slots):
            raise ValueError("提前提醒需要提醒点或安排；只有DDL也可以先保存，不必填结束时间")
        # No duration, earliest start, timetable coverage, or invented end required.
        return self


def content(value):
    try:
        return EntryContent.model_validate(value).model_dump()
    except ValidationError as exc:
        # Pydantic's error includes raw input; expose only known contract paths.
        fields = []
        for error in exc.errors(include_input=False, include_context=False, include_url=False):
            path = "content." + ".".join(str(part) for part in error["loc"])
            if re.fullmatch(r"content\.(?:title|kind|due_at|due_date|reminder_at|notes|reminder_minutes|scheduled_slots(?:\.[0-7](?:\.(?:start|end))?)?)", path):
                fields.append(FieldError(field=path, code="invalid_field",
                    message="字段类型或结构不符合接口；notes须为字符串，无备注用空字符串"))
        raise AppError(422, "VALIDATION_ERROR", "请核对待办字段类型与时间；尚未保存", field_errors=fields) from None
    except ValueError:
        raise AppError(422, "VALIDATION_ERROR", "请核对标题、截止、提醒点和选定区间；提醒不需要结束时间") from None


def task_record(row):
    c = row["content"]
    slots = c["scheduled_slots"]
    first = slots[0] if slots else None
    unknown = {"start": None, "end": None, "date": None, "precision": "unknown"}
    notice = {"schema_version": "1.0.0", "notice_id": row["task_id"], "title": c["title"],
        "published_at": None, "extracted_at": datetime.fromtimestamp(row["confirmed_epoch"], ZoneInfo('Asia/Shanghai')).isoformat(),
        "timezone": "Asia/Shanghai", "event": unknown,
        "due": {"at": c["due_at"], "date": c["due_date"], "precision": "datetime" if c["due_at"] else "date_only" if c["due_date"] else "unknown"},
        "estimated_minutes": None, "earliest_start": None, "materials": [], "source_spans": [], "needs_confirmation": []}
    return {"task_id": row["task_id"], "revision": 1, "confirmed_epoch": row["confirmed_epoch"],
        "notice": notice, "source_kind": "personal_task_v1", "entry_kind": c["kind"],
        "notes": c["notes"], "reminder_at": c["reminder_at"], "scheduled_slots": slots,
        "calendar_state": {"calendar_revision": row["revision"], "status": row["status"],
            "scheduled_start": first["start"] if first else None, "scheduled_end": first["end"] if first else None,
            "reminder_minutes": c["reminder_minutes"]}}


class PersonalTaskService:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store

    def gate(self):
        if not self.settings.cloud_personal_tasks_enabled:
            raise AppError(403, "FORBIDDEN", "本人待办记录功能未开启")
        from app.cloud_identity_site import require_cloud_identity
        require_cloud_identity(self.settings)

    def records(self, args, optional=False):
        self.gate()
        if optional and not self.store.personal_call("access", args)["can_read"]:
            return []  # A legacy demo:read grant is never silently expanded.
        return [task_record(row) for row in self.store.personal_call("records", args)["items"]]

    def draft(self, args, payload):
        self.gate()
        if set(payload) != {"content", "idempotency_key"}:
            raise AppError(422, "VALIDATION_ERROR", "草稿只接受事项内容与幂等键，不接受账号或工作区")
        require_idempotency_key(payload["idempotency_key"])
        c = content(payload["content"])
        digest = payload_hash(c)
        result = self.store.personal_call("draft", {**args, "content": c, "payload_hash": digest,
            "draft_id": "entry_draft_" + token_urlsafe(18), "key": payload["idempotency_key"], "request_hash": digest})
        return {**result, "saved": False, "requires_user_confirmation": True, "background_push": False}

    def commit(self, args, payload):
        self.gate()
        if set(payload) != {"draft_id", "payload_hash", "confirmed", "idempotency_key"} or payload["confirmed"] is not True:
            raise AppError(422, "CONFIRMATION_REQUIRED", "必须在用户核对草稿并明确确认后才能提交")
        require_idempotency_key(payload["idempotency_key"])
        result = self.store.personal_call("commit", {**args, "draft_id": payload["draft_id"],
            "payload_hash": payload["payload_hash"], "task_id": "entry_" + token_urlsafe(18),
            "key": payload["idempotency_key"], "request_hash": payload_hash({k: payload[k] for k in ("draft_id", "payload_hash", "confirmed")})})
        rows = self.records(args)
        saved = next((t for t in rows if t["task_id"] == result["task_id"]), None)
        if saved is None:
            raise AppError(503, "DEPENDENCY_UNAVAILABLE", "提交后未读回事项，请刷新核对，不要重复新建", True)
        from app.core.task_calendar import calendar_task
        return {"saved": True, "readback_verified": True, "item": calendar_task(saved),
            "calendar_url": self.settings.app_origin + "/tools/calendar", "background_push": False,
            "conflicts_checked": False}

    def update(self, args, task, payload, key):
        self.gate()
        require_idempotency_key(key)
        old = task["calendar_state"]
        # Initial selected intervals are saved with the confirmed draft. Do not
        # silently replace a multi-slot task with one interval via the old UI.
        def equivalent(a, b):
            return a == b if a is None or b is None else parse_datetime(a, field="time") == parse_datetime(b, field="time")
        if any(not equivalent(payload[k], old[k]) for k in ("scheduled_start", "scheduled_end")):
            raise AppError(422, "VALIDATION_ERROR", "多区间事项请重新核对安排，不能用旧单区间界面改写")
        state = {"expected_revision": payload["expected_revision"], "status": payload["status"],
                 "reminder_minutes": payload["reminder_minutes"]}
        result = self.store.personal_call("update", {**args, "task_id": task["task_id"], "state": state,
            "key": key, "request_hash": payload_hash({"task_id": task["task_id"], "state": state})})
        from app.core.task_calendar import calendar_task
        return calendar_task(task_record(result))

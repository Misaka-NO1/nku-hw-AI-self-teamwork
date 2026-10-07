"""Owner calendar state; original notices remain immutable."""
from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.contracts import validate_boundary
from app.core.errors import AppError
from app.core.notice_plan import resources
from app.core.security import payload_hash, require_idempotency_key
from app.domains.schedule.service import expand_occurrences, parse_datetime, format_datetime
from app.domains.timeplan.service import check_time_plan, find_free_slots
from app.core.domain_adapter import _notice_events

TZ = ZoneInfo("Asia/Shanghai")


def calendar_now():
    return datetime.now(TZ)


def calendar_task(task):
    stored = task["notice"]
    notice = stored.get("notice", stored)
    selected = stored.get("selected_slot")
    event = notice["event"]
    start, end = (event["start"], event["end"]) if event["precision"] == "datetime" else (
        (selected["start"], selected["end"]) if selected else (None, None))
    state = task.get("calendar_state") or {"calendar_revision": 0, "status": "pending",
        "scheduled_start": start, "scheduled_end": end, "reminder_minutes": None}
    return {k: task[k] for k in ("task_id", "revision", "confirmed_epoch")} | {
        "notice": deepcopy(notice), **state,
        **{k: deepcopy(task[k]) for k in ("source_kind", "entry_kind", "notes", "reminder_at", "scheduled_slots") if k in task}}


class TaskCalendarService:
    def __init__(self, settings, store):
        self.settings, self.store = settings, store

    def gate(self):
        if not self.settings.cloud_task_calendar_enabled or not self.settings.cloud_notice_text_pilot_enabled:
            raise AppError(403, "FORBIDDEN", "日历试点未开启")
        from app.cloud_identity_site import require_cloud_identity
        require_cloud_identity(self.settings)

    def records(self, args, workspace_ref=None):
        self.gate()
        records = self.store.calendar_call("records", args)
        if workspace_ref is not None and workspace_ref != records["workspace_ref"]:
            raise AppError(404, "NOT_FOUND", "本人工作区不存在")
        if self.settings.cloud_personal_tasks_enabled:
            from app.core.personal_tasks import PersonalTaskService
            records = {**records, "tasks": records["tasks"] + PersonalTaskService(self.settings, self.store).records(args, optional=True)}
        return records

    @staticmethod
    def find(records, task_id):
        task = next((t for t in records["tasks"] if t["task_id"] == task_id), None)
        if task is None:
            raise AppError(404, "NOT_FOUND", "本人事项不存在")
        return task

    def list(self, args, workspace_ref):
        records = self.records(args, workspace_ref)
        return {"items": [calendar_task(t) for t in records["tasks"]],
                "capabilities": {"scheduling": True, "status": True, "reminders": True}}

    def candidates(self, args, task_id, workspace_ref):
        records = self.records(args, workspace_ref)
        return self.calculate(records, self.find(records, task_id))

    @staticmethod
    def calculate(records, task, now=None, exact_window=None):
        now = now or calendar_now()
        item = calendar_task(task)
        n = item["notice"]
        coverage = {"completeness": "unknown"}
        needs = list(n["needs_confirmation"])
        # Fixed activities keep their original times and have no rescheduling menu.
        if n["event"]["precision"] != "unknown":
            return {"candidate_slots": [], "needs_confirmation": needs,
                    "coverage": coverage, "fixed_event": True}
        for field, missing in (("due_time", n["due"]["precision"] != "datetime"),
                               ("estimated_minutes", n["estimated_minutes"] is None),
                               ("earliest_start", n["earliest_start"] is None)):
            if missing and field not in needs:
                needs.append(field)
        if needs:
            return {"candidate_slots": [], "needs_confirmation": needs, "coverage": coverage}
        due = parse_datetime(n["due"]["at"], field="due.at")
        earliest = parse_datetime(n["earliest_start"], field="earliest_start")
        start = max(now.replace(second=0, microsecond=0) + timedelta(minutes=1), earliest)
        end = min(due, start + timedelta(days=31))
        if exact_window:
            start, end = (parse_datetime(exact_window[k], field=k) for k in ("start", "end"))
            if start < now or start < earliest or end > due or end <= start:
                raise AppError(409, "STALE_REVISION", "安排已过期或不满足最早开始、截止要求")
        if start >= end:
            return {"candidate_slots": [], "needs_confirmation": [], "coverage": coverage,
                    "reason": "deadline_passed_or_no_remaining_time"}
        own = {**records, "tasks": [t for t in records["tasks"] if t["task_id"] != task["task_id"]]}
        timetable, notices, _ = resources(own)
        term_start = parse_datetime(timetable["term"]["week1_monday"] + "T00:00:00+08:00", field="term")
        term_end = term_start + timedelta(weeks=timetable["term"]["teaching_weeks"])
        window = {"start": format_datetime(start), "end": format_datetime(end)}
        query = {"workspace_ref": records["workspace_ref"], "kind": "deadline_feasibility",
            "window": window, "event": n["event"], "due": n["due"],
            "estimated_minutes": n["estimated_minutes"], "earliest_start": n["earliest_start"],
            "allow_split": False, "buffers": task.get("planning_constraints", {}).get("buffers",
                {"before_minutes": 0, "after_minutes": 0})}
        result = check_time_plan(timetable["term"], timetable["courses"], notices, query)
        result["coverage"].update(within_term=term_start <= start < end <= term_end, query_window=window)
        # An expired fixture term cannot prove current course availability.
        if not result["coverage"]["within_term"]:
            return {"candidate_slots": [], "needs_confirmation": ["timetable_outside_term"],
                    "coverage": result["coverage"]}
        events, _ = expand_occurrences(timetable["term"], timetable["courses"], window)
        slots = find_free_slots(events + _notice_events(notices), window, n["estimated_minutes"], query["buffers"])["slots"]
        limits = task.get("planning_constraints", {}).get("available_windows", [])
        if limits:
            bounded = []
            for slot in slots:
                a, b = (parse_datetime(slot[k], field=k) for k in ("start", "end"))
                for limit in limits:
                    x, y = max(a, parse_datetime(limit["start"], field="start")), min(b, parse_datetime(limit["end"], field="end"))
                    if x < y and (y - x).total_seconds() >= n["estimated_minutes"] * 60:
                        bounded.append({"start": format_datetime(x), "end": format_datetime(y),
                                        "duration_minutes": int((y - x).total_seconds() // 60)})
            slots = sorted(bounded, key=lambda s: s["start"])
        return {"candidate_slots": slots, "needs_confirmation": result["needs_confirmation"],
                "coverage": result["coverage"]}

    def update(self, args, task_id, payload, key):
        self.gate()
        validate_boundary(payload, "CalendarUpdateRequest")
        require_idempotency_key(key)
        digest = payload_hash({"task_id": task_id, "body": payload})
        # Authenticate and constrain cached retries to the same active workspace.
        records = self.records(args, payload["workspace_ref"])
        task = self.find(records, task_id)
        if task.get("source_kind") == "personal_task_v1":
            from app.core.personal_tasks import PersonalTaskService
            return PersonalTaskService(self.settings, self.store).update(args, task, payload, key)
        cached = self.store.calendar_call("lookup", {**args, "task_id": task_id, "key": key, "request_hash": digest})
        if cached is not None:
            return cached
        old = calendar_task(task)
        if old["calendar_revision"] != payload["expected_revision"]:
            raise AppError(409, "STALE_REVISION", "日历版本已变化，请刷新")
        self.validate_update(records, task, old, payload)
        return self.store.calendar_call("update", {**args, "task_id": task_id, "key": key,
            "request_hash": digest, "records_revision": records["records_revision"], "state": payload})

    def validate_update(self, records, task, old, body):
        start, end = body["scheduled_start"], body["scheduled_end"]
        if (start is None) != (end is None):
            raise AppError(422, "VALIDATION_ERROR", "安排起止必须同时填写或同时为空")
        if start is not None and parse_datetime(start, field="start") >= parse_datetime(end, field="end"):
            raise AppError(422, "VALIDATION_ERROR", "安排起止顺序不合法")
        n = old["notice"]
        fixed = n["event"]["precision"] != "unknown"
        equivalent = lambda a, b: a == b if a is None or b is None else parse_datetime(a, field="time") == parse_datetime(b, field="time")
        changed = not (equivalent(start, old["scheduled_start"]) and equivalent(end, old["scheduled_end"]))
        if fixed and changed:
            raise AppError(422, "VALIDATION_ERROR", "固定活动不能改期或清空时间")
        if body["status"] != "pending" and changed:
            raise AppError(422, "VALIDATION_ERROR", "完成或取消时保留原安排；改期请先恢复")
        if body["reminder_minutes"] is not None and start is None:
            raise AppError(422, "VALIDATION_ERROR", "未安排的事项不能设置开始提醒")
        if body["status"] != "pending" or (not changed and old["status"] == "pending"):
            return  # Old historical arrangements may be completed/cancelled or reminders edited.
        if fixed:
            if start is None or parse_datetime(start, field="start") < calendar_now():
                raise AppError(409, "STALE_REVISION", "过期固定活动不能恢复占用")
            own = {**records, "tasks": [t for t in records["tasks"] if t["task_id"] != task["task_id"]]}
            timetable, notices, _ = resources(own)
            query = {"workspace_ref": records["workspace_ref"], "kind": "event_conflict",
                "window": {"start": start, "end": end}, "event": n["event"], "due": n["due"],
                "estimated_minutes": n["estimated_minutes"], "earliest_start": n["earliest_start"],
                "allow_split": False, "buffers": {"before_minutes": 0, "after_minutes": 0}}
            result = check_time_plan(timetable["term"], timetable["courses"], notices, query)
            term_start = parse_datetime(timetable["term"]["week1_monday"] + "T00:00:00+08:00", field="term")
            if not term_start <= parse_datetime(start, field="start") < parse_datetime(end, field="end") <= term_start + timedelta(weeks=timetable["term"]["teaching_weeks"]):
                raise AppError(409, "CONFIRMATION_REQUIRED", "当前课表不覆盖此活动")
            if result["needs_confirmation"] or result["conflicts"]:
                raise AppError(409, "STALE_REVISION", "恢复活动存在课表或待办冲突")
        elif start is not None:
            if n["estimated_minutes"] is None or (parse_datetime(end, field="end") - parse_datetime(start, field="start")).total_seconds() != n["estimated_minutes"] * 60:
                raise AppError(422, "VALIDATION_ERROR", "安排长度必须等于已确认耗时")
            result = self.calculate(records, task, exact_window={"start": start, "end": end})
            if result["needs_confirmation"] or not result["candidate_slots"]:
                raise AppError(409, "STALE_REVISION", "安排不满足当前课表、待办或限制")

    def summary(self, args, workspace_ref=None):
        records = self.records(args, workspace_ref)
        now = calendar_now()
        tasks = [calendar_task(t) for t in records["tasks"]]
        pending = [t for t in tasks if t["status"] == "pending"]
        timed = [(t, at) for t in pending for at in (
            [r["start"] for r in t.get("scheduled_slots", [])] +
            [t.get("reminder_at"), t["scheduled_start"], t["notice"]["event"]["start"], t["notice"]["due"]["at"]])]
        future = [(t, parse_datetime(at, field="time")) for t, at in timed if at and parse_datetime(at, field="time") >= now]
        next_item = min(future, key=lambda x: (x[1], x[0]["task_id"]))[0] if future else None
        today = now.date()
        def occurs_today(t):
            start = t["scheduled_start"] or t["notice"]["event"]["start"]
            end = t["scheduled_end"] or t["notice"]["event"]["end"]
            due = t["notice"]["due"]
            due_day = parse_datetime(due["at"], field="due.at").astimezone(TZ).date().isoformat() if due["at"] else due["date"]
            ranges = t.get("scheduled_slots", [])
            reminder = t.get("reminder_at")
            return due_day == today.isoformat() or bool(reminder and parse_datetime(reminder, field="reminder").astimezone(TZ).date() == today) or any(
                parse_datetime(r["start"], field="start").astimezone(TZ).date() <= today <=
                (parse_datetime(r["end"], field="end") - timedelta(microseconds=1)).astimezone(TZ).date() for r in ranges) or bool(start and end and
                parse_datetime(start, field="start").astimezone(TZ).date() <= today <=
                (parse_datetime(end, field="end") - timedelta(microseconds=1)).astimezone(TZ).date())
        def overdue(t):
            due = t["notice"]["due"]
            return (parse_datetime(due["at"], field="due.at") < now if due["at"] else
                bool(due["date"] and due["date"] < today.isoformat()))
        return {"pending_count": len(pending),
            "today_count": sum(occurs_today(t) for t in pending),
            "overdue_count": sum(overdue(t) for t in pending),
            "unscheduled_count": sum(t["scheduled_start"] is None for t in pending),
            "next_task": None if next_item is None else {k: next_item[k] for k in
                ("task_id", "notice", "scheduled_start", "scheduled_end", "calendar_revision")},
            "as_of": now.isoformat(timespec="seconds"), "total_count": len(tasks), "background_push": False}

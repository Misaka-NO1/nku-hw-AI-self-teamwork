"""Conservative text reader for local testing; no model or fixture substitution.

The school workflow can use the same 13-field NoticeDraft contract. This reader
only resolves explicit dates and times; users review all extracted items.
"""

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from app.core.contracts import validate_contract
from app.core.errors import AppError
from app.core.security import payload_hash
from app.domains.schedule.service import parse_datetime

TZ = timezone(timedelta(hours=8))
DATE = re.compile(r"(?:(\d{4})[-年/])?(\d{1,2})[-月/](\d{1,2})日?")
CLOCK = re.compile(r"(?<!\d)(\d{1,2})[:：](\d{2})(?!\d)")
RELATIVE = re.compile(r"明天|后天|今天|本周[一二三四五六日天]|下周[一二三四五六日天]")
ACTION = re.compile(r"参加|会议|讲座|活动|提交|完成|报名|填写|上传|阅读|交报告")
DEADLINE = re.compile(r"截止|提交|完成|报名|填写|上传|交报告")
CAUTION = re.compile(r"取消|延期|改期|作废|无需|不用|不必|更正|待定|或者|可能|原定")


def fail(message: str) -> None:
    raise AppError(422, "VALIDATION_ERROR", message)


def _day(text: str, reference_at: str | None) -> tuple[date | None, list[str]]:
    reference = parse_datetime(reference_at, field="reference_at") if reference_at else None
    matches = list(DATE.finditer(text))
    relative = list(RELATIVE.finditer(text))
    if len(matches) + len(relative) > 1:
        return None, ["multiple_dates"]
    if matches:
        match = matches[0]
        year = int(match[1]) if match[1] else reference.year if reference else None
        if year is None:
            return None, ["reference_date"]
        try:
            return date(year, int(match[2]), int(match[3])), []
        except ValueError:
            return None, ["invalid_date"]
    if relative:
        if reference is None:
            return None, ["reference_date"]
        word = relative[0][0]
        if word in {"今天", "明天", "后天"}:
            return reference.date() + timedelta(days={"今天": 0, "明天": 1, "后天": 2}[word]), []
        weekday = "一二三四五六日".find(word[-1].replace("天", "日"))
        monday = reference.date() - timedelta(days=reference.weekday())
        return monday + timedelta(days=weekday + (7 if word.startswith("下周") else 0)), []
    return None, ["date"]


def read_text(source_text: str, source_ref: str, reference_at: str | None = None,
              *, extracted_at: str | None = None) -> dict[str, Any]:
    if not source_text.strip():
        fail("通知为空，请粘贴文字")
    if len(source_text) > 20000 or not source_ref.strip() or len(source_ref) > 128:
        fail("通知最多20000字符，来源须为1至128字符")
    if reference_at:
        parse_datetime(reference_at, field="reference_at")
    extracted_at = extracted_at or datetime.now(TZ).isoformat(timespec="seconds")
    # Cover every clause. Unsupported/background clauses are explicitly retained.
    chunks = [m for m in re.finditer(r"[^\n。；;]+[。；;]?", source_text) if m[0].strip()]
    items, unclassified = [], []
    for part in chunks:
        quote = part[0].strip()
        locator = f"{source_ref}#chars={part.start()}:{part.end()}"
        if not ACTION.search(quote):
            unclassified.append({"quote": quote, "source_ref": locator})
            continue
        kind = "deadline_feasibility" if (DEADLINE.search(quote)
                or ("阅读" in quote and re.search(r"前|截止", quote))) else "event_conflict"
        day, issues = _day(quote, reference_at)
        clocks = list(CLOCK.finditer(quote))
        times = []
        for clock in clocks:
            try:
                times.append(time(int(clock[1]), int(clock[2])))
            except ValueError:
                issues.append("invalid_time")
        event = {"start": None, "end": None, "date": None, "precision": "unknown"}
        due = {"at": None, "date": None, "precision": "unknown"}
        if CAUTION.search(quote):
            issues.append("changed_or_cancelled_notice")
        # Mixed event + deadline in one clause needs manual splitting in the school workflow.
        if DEADLINE.search(quote) and re.search(r"参加|会议|讲座", quote):
            issues.append("mixed_actions")
        if day:
            if kind == "deadline_feasibility":
                due.update(date=day.isoformat(), precision="date_only")
                if len(times) == 1 and len(clocks) == 1:
                    due.update(at=datetime.combine(day, times[0], TZ).isoformat(), precision="datetime")
                elif clocks:
                    issues.append("multiple_times")
            else:
                event.update(date=day.isoformat(), precision="date_only")
                if len(times) == 2 and len(clocks) == 2:
                    start, end = [datetime.combine(day, t, TZ) for t in times]
                    if start < end:
                        event.update(start=start.isoformat(), end=end.isoformat(), precision="datetime")
                    else:
                        issues.append("event_order")
        minutes_match = re.search(r"(?:预计|耗时|用时)\s*(\d+)\s*分钟", quote)
        minutes = int(minutes_match[1]) if minutes_match else None
        if minutes is not None and not 1 <= minutes <= 10080:
            minutes = None
            issues.append("invalid_duration")
        materials_match = re.search(r"(?:材料|附件)[：:]([^。；;]+)", quote)
        materials = [materials_match[1].strip()] if materials_match else []
        notice = {
            "schema_version": "1.0.0",
            "notice_id": "text-" + payload_hash({"source": source_ref, "quote": quote,
                                                  "offset": part.start()})[:32],
            "title": quote[:120], "published_at": None, "extracted_at": extracted_at,
            "timezone": "Asia/Shanghai", "event": event, "due": due,
            "estimated_minutes": minutes, "earliest_start": None, "materials": materials,
            "source_spans": [{"field": field, "quote": quote, "source_ref": locator}
                             for field in ["title", "due" if kind == "deadline_feasibility" else "event"]
                             + (["estimated_minutes"] if minutes else [])
                             + (["materials"] if materials else [])],
            "needs_confirmation": [],
        }
        if kind == "event_conflict" and event["precision"] != "datetime":
            issues.append("event_time")
        if kind == "deadline_feasibility":
            if due["precision"] != "datetime":
                issues.append("due_time")
            if minutes is None:
                issues.append("estimated_minutes")
            issues.append("earliest_start")
        notice["needs_confirmation"] = list(dict.fromkeys(["source_review", *issues]))
        validate_contract(notice, "NoticeDraft")
        items.append({"kind": kind, "notice": notice})
    if len(items) > 50:
        fail("单批最多50项，请分批提供通知")
    return {
        "batch_version": "notice-text-pilot-v1", "items": items,
        "unclassified": unclassified,
        "coverage": {"input_kind": "text", "characters_read": len(source_text),
                     "characters_total": len(source_text), "unread_ranges": []},
        "reader": "explicit-text-v1",
        "limitations": ["仅识别明确日期和HH:MM时刻；逐项核对，不代表通用模型阅读已验收",
                        "未分类段落须核对；含取消、延期、多日期或混合事项须先拆分更正"],
    }


def confirmed_item(source_text: str, source_ref: str, reference_at: str | None,
                   item_id: str, confirmations: dict, *, extracted_at: str | None = None,
                   model_output: str | None = None, source_kind: str = "text") -> dict:
    if model_output is None:
        batch = read_text(source_text, source_ref, reference_at, extracted_at=extracted_at)
    else:
        from app.domains.tasks.notice_model_reader import read_model_output
        batch = read_model_output(source_text, source_ref, reference_at, model_output, extracted_at=extracted_at)
    if source_kind == "ocr":
        from app.domains.tasks.notice_image_reader import require_ocr_review
        batch = require_ocr_review(batch)
    item = next((i for i in batch["items"] if i["notice"]["notice_id"] == item_id), None)
    if item is None:
        fail("事项不属于本次通知")
    notice = item["notice"]
    needs = notice["needs_confirmation"]
    if confirmations.get("source_review"):
        needs.remove("source_review")
    if confirmations.get("ocr_review") and "ocr_review" in needs:
        needs.remove("ocr_review")
    updates = {
        "estimated_minutes": confirmations.get("estimated_minutes"),
        "earliest_start": confirmations.get("earliest_start"),
    }
    for field, value in updates.items():
        if value is not None:
            if field == "earliest_start":
                value = parse_datetime(value, field=field).isoformat()
            notice[field] = value
            if field in needs:
                needs.remove(field)
            notice["source_spans"].append({"field": field, "quote": str(value),
                                          "source_ref": "user-confirmation"})
    due_at = confirmations.get("due_at")
    if due_at is not None and item["kind"] == "deadline_feasibility":
        due = parse_datetime(due_at, field="due_at")
        notice["due"] = {"at": due.isoformat(), "date": due.date().isoformat(), "precision": "datetime"}
        notice["source_spans"].append({"field": "due", "quote": due_at, "source_ref": "user-confirmation"})
        needs[:] = [n for n in needs if n not in {"due_time", "date", "reference_date"}]
    start, end = confirmations.get("event_start"), confirmations.get("event_end")
    if start is not None and end is not None and item["kind"] == "event_conflict":
        begin, finish = parse_datetime(start, field="event_start"), parse_datetime(end, field="event_end")
        if begin >= finish:
            fail("活动开始必须早于结束")
        notice["event"] = {"start": begin.isoformat(), "end": finish.isoformat(),
                           "date": begin.date().isoformat(), "precision": "datetime"}
        notice["source_spans"].append({"field": "event", "quote": f"{start} — {end}",
                                      "source_ref": "user-confirmation"})
        needs[:] = [n for n in needs if n not in {"event_time", "date", "reference_date", "event_order"}]
    validate_contract(notice, "NoticeDraft")
    return item

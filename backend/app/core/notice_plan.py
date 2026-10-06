"""Deterministic notice -> B time request -> reviewable plan; storage independent."""
from copy import deepcopy
from datetime import timedelta
import json

from app.core.contracts import validate_boundary
from app.core.demo import enforce_demo_fixture
from app.core.errors import AppError
from app.core.security import payload_hash
from app.domains.schedule.service import expand_occurrences, parse_datetime
from app.domains.tasks.notice_reader import confirmed_item, fail
from app.domains.timeplan.service import check_time_plan

VERSION = "notice-text-pilot-v1"


def resources(records):
    if records.get("schedule") is None:
        raise AppError(404, "NOT_FOUND", "请先确认保存本人的课表")
    timetable = records["schedule"]["timetable"]
    enforce_demo_fixture(timetable, "schedule")
    notices, labels = [], {}
    for task in records["tasks"]:
        state = task.get("calendar_state")
        if state and state["status"] != "pending":
            continue
        stored = task["notice"]
        if stored.get("plan_version") == VERSION:
            notice = deepcopy(stored["notice"])
            validate_boundary(notice, "NoticeTextProposal")
            selected = stored["selected_slot"]
            if selected is not None and stored["kind"] == "deadline_feasibility":
                notice["event"] = {"start": selected["start"], "end": selected["end"],
                                   "date": selected["start"][:10], "precision": "datetime"}
        elif task.get("plan_kind") in {"event_conflict", "deadline_feasibility"}:
            notice = deepcopy(stored)
            validate_boundary(notice, "NoticeTextProposal")
        else:
            enforce_demo_fixture(stored, "task")
            notice = deepcopy(stored)
        if state and notice["event"]["precision"] == "unknown":
            if state["scheduled_start"] is not None:
                notice["event"] = {"start": state["scheduled_start"], "end": state["scheduled_end"],
                    "date": state["scheduled_start"][:10], "precision": "datetime"}
            else:
                notice["event"] = {"start": None, "end": None, "date": None, "precision": "unknown"}
        elif state and stored.get("kind") == "deadline_feasibility":
            notice["event"] = {"start": state["scheduled_start"], "end": state["scheduled_end"],
                "date": state["scheduled_start"][:10] if state["scheduled_start"] else None,
                "precision": "datetime" if state["scheduled_start"] else "unknown"}
        notices.append(notice)
        labels[f"task:{notice['notice_id']}"] = notice["title"]
    return timetable, notices, labels


def calculate_notice(payload, records, workspace_ref):
    validate_boundary(payload, "NoticePilotCheckRequest")
    item = confirmed_item(payload["source_text"], payload["source_ref"], payload["reference_at"],
                          payload["item_id"], payload["user_confirmations"], model_output=payload.get("model_output"), source_kind=payload.get("source_kind", "text"))
    notice = item["notice"]
    query = {"workspace_ref": workspace_ref, "kind": item["kind"], "window": payload["window"],
             "event": notice["event"], "due": notice["due"],
             "estimated_minutes": notice["estimated_minutes"], "earliest_start": notice["earliest_start"],
             "allow_split": False, "buffers": payload.get("buffers", {"before_minutes": 0, "after_minutes": 0})}
    start = parse_datetime(query["window"]["start"], field="window.start")
    end = parse_datetime(query["window"]["end"], field="window.end")
    if start >= end or end - start > timedelta(days=31):
        fail("查询范围必须递增且不超过31天")
    if item["kind"] == "event_conflict" and notice["event"]["precision"] == "datetime":
        event = notice["event"]
        if (parse_datetime(event["start"], field="event.start") < start
                or parse_datetime(event["end"], field="event.end") > end):
            fail("查询范围必须包含完整活动时间")
    windows = payload["available_windows"] or [query["window"]]
    parsed = []
    for window in windows:
        begin, finish = (parse_datetime(window[k], field="available_windows") for k in ("start", "end"))
        if not start <= begin < finish <= end:
            fail("可用区间必须完整位于查询范围内")
        parsed.append((begin, finish))
    parsed.sort()
    if any(b[0] < a[1] for a, b in zip(parsed, parsed[1:])):
        fail("可用区间不能重叠")
    timetable, tasks, labels = resources(records)
    course_events, warnings = expand_occurrences(timetable["term"], timetable["courses"], query["window"])
    course_labels = {course["course_id"]: course["title"] for course in timetable["courses"]}
    for event in course_events:
        labels[event["event_id"]] = course_labels.get(event.get("course_id"), event["event_id"])
    result = check_time_plan(timetable["term"], timetable["courses"], tasks, query)
    if item["kind"] == "deadline_feasibility" and payload["available_windows"]:
        candidates = []
        for window in windows:
            branch = check_time_plan(timetable["term"], timetable["courses"], tasks, {**query, "window": window})
            candidates.extend(branch["candidate_slots"])
        result["candidate_slots"] = sorted(candidates, key=lambda c: c["start"])
    result["needs_confirmation"] = list(dict.fromkeys(notice["needs_confirmation"] + result["needs_confirmation"]))
    # Do not suggest any schedule until required source checks have been completed.
    if result["needs_confirmation"] and "candidate_slots" in result:
        result["candidate_slots"] = []
    term_start = parse_datetime(timetable["term"]["week1_monday"] + "T00:00:00+08:00", field="term")
    term_end = term_start + timedelta(weeks=timetable["term"]["teaching_weeks"])
    result["coverage"].update(query_window=query["window"],
                              timetable_coverage=timetable["source"]["coverage"],
                              within_term=term_start <= start < end <= term_end)
    recommendations = [{"slot": slot, "candidate_index": i,
                         "reason": "在已导入课表与已确认活动范围内，优先选择最早可完成的连续区间"}
                        for i, slot in enumerate(result.get("candidate_slots", [])[:3])]
    return {"item": item, "time_request": query, "time_result": result,
            "recommendations": recommendations,
            "conflict_labels": labels, "warnings": warnings,
            "coverage_message": "结果仅覆盖已导入虚构课表与已确认活动；课表外安排未知",
            "plan": {"plan_version": VERSION, **{k: payload[k] for k in
                      ("source_text", "source_ref", "reference_at", "window", "available_windows", "user_confirmations")},
                     **{k: payload[k] for k in ("model_output", "buffers", "fictional_data_confirmed", "source_kind", "document_sha256") if k in payload},
                     "kind": item["kind"], "notice": notice, "selected_slot": None}}


def validate_notice_plan(plan, records, workspace_ref):
    validate_boundary(plan, "NoticePilotPlan")
    if len(json.dumps(plan, ensure_ascii=False).encode("utf-8")) > 262144:
        fail("完整通知计划最多262144字节，请拆分原文")
    notice = plan["notice"]
    expected = confirmed_item(plan["source_text"], plan["source_ref"], plan["reference_at"],
                              notice["notice_id"], plan["user_confirmations"],
                              extracted_at=notice["extracted_at"], model_output=plan.get("model_output"), source_kind=plan.get("source_kind", "text"))
    if expected != {"kind": plan["kind"], "notice": notice}:
        fail("提炼内容与本次原文或用户确认不一致，请重新核对")
    if any(t["notice"].get("plan_version") == VERSION and
           t["notice"]["notice"]["notice_id"] == notice["notice_id"] for t in records["tasks"]):
        raise AppError(409, "STALE_REVISION", "此事项已经保存，请从待办列表读回")
    payload = {k: plan[k] for k in ("source_text", "source_ref", "reference_at", "window",
                                  "available_windows", "user_confirmations", "model_output", "buffers", "fictional_data_confirmed", "source_kind", "document_sha256") if k in plan}
    result = calculate_notice({**payload, "item_id": notice["notice_id"]}, records, workspace_ref)["time_result"]
    if result["needs_confirmation"]:
        raise AppError(409, "CONFIRMATION_REQUIRED", "需先完成缺项与原文核对")
    if plan["kind"] == "deadline_feasibility":
        if plan["selected_slot"] not in result["candidate_slots"]:
            raise AppError(409, "STALE_REVISION", "所选时间不是本次有效候选，请重新计算选择")
    elif plan["selected_slot"] is not None:
        fail("固定活动不能另选工作时间")
    elif result["conflicts"] and not plan["user_confirmations"].get("accept_conflicts", False):
        raise AppError(409, "CONFIRMATION_REQUIRED", "活动存在冲突，需明确确认仍要保存")
    return payload_hash(plan)

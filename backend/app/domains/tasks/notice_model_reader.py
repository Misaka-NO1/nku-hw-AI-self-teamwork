"""Treat school model output as an untrusted proposal, never a save instruction."""
from copy import deepcopy
from datetime import datetime

from app.core.contracts import validate_boundary
from app.core.security import payload_hash
from app.domains.schedule.service import parse_datetime
from app.domains.tasks.notice_reader import CAUTION, RELATIVE, TZ, fail


def strict_json(raw):
    from app.core.platform_query import decode_platform_query
    result = decode_platform_query({"query_json": raw})
    pending = [result]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if set(value) & {"__proto__", "constructor", "prototype"}:
                fail("模型JSON含不允许的字段")
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return result


def read_model_output(source_text, source_ref, reference_at, model_output, *, extracted_at=None):
    validate_boundary({"source_text": source_text, "source_ref": source_ref,
                       "reference_at": reference_at, "model_output": model_output}, "NoticePilotReadRequest")
    if not source_text.strip() or not source_ref.strip():
        fail("通知原文和来源不能为空")
    if reference_at:
        parse_datetime(reference_at, field="reference_at")
    raw = strict_json(model_output)
    if not isinstance(raw, dict) or set(raw) != {"items", "unclassified"}:
        fail("模型批次只允许items与unclassified")
    if (not isinstance(raw["items"], list) or len(raw["items"]) > 50
            or not isinstance(raw["unclassified"], list) or len(raw["unclassified"]) > 200):
        fail("模型批次数量超出支持范围")
    covered = [False] * len(source_text)
    def evidence(quote):
        if not isinstance(quote, str) or not quote.strip() or quote not in source_text:
            fail("模型原文证据不存在，请重新读取")
        start = 0
        while (at := source_text.find(quote, start)) >= 0:
            covered[at:at + len(quote)] = [True] * len(quote)
            start = at + len(quote)
    items, ids = [], set()
    for index, proposal in enumerate(raw["items"]):
        if (not isinstance(proposal, dict) or set(proposal) != {"kind", "notice"}
                or proposal["kind"] not in {"event_conflict", "deadline_feasibility"}):
            fail("模型事项类型或字段不合法")
        notice = deepcopy(proposal["notice"])
        # Expanded frozen shape in API schema uses sanitized boundary diagnostics.
        validate_boundary(notice, "NoticeTextProposal")
        if notice["notice_id"] in ids or not notice["title"].strip() or len(notice["title"]) > 240:
            fail("模型事项编号重复或标题不合法")
        ids.add(notice["notice_id"])
        fields = set(notice)
        citations = {}
        for span in notice["source_spans"]:
            if span["field"] not in fields or span["source_ref"] != source_ref:
                fail("模型引用字段或来源不合法")
            evidence(span["quote"])
            citations.setdefault(span["field"], []).append(span["quote"])
        if not citations.get("title"):
            fail("模型事项缺少行动原文证据")
        for field in ("published_at", "estimated_minutes", "earliest_start"):
            if notice[field] is not None and not citations.get(field):
                fail("模型字段缺少原文证据")
        for field in ("event", "due"):
            value = notice[field]
            if value["precision"] != "unknown" and not citations.get(field):
                fail("模型时间缺少原文证据")
            if field == "event":
                if value["precision"] == "datetime":
                    if not isinstance(value["start"], str) or not isinstance(value["end"], str):
                        fail("模型活动缺少完整起止时刻")
                    start, end = [parse_datetime(value[k], field=k) for k in ("start", "end")]
                    if start >= end or (value["date"] is not None and value["date"] != start.date().isoformat()):
                        fail("模型活动时间不一致")
                elif value["start"] is not None or value["end"] is not None:
                    fail("模型活动精度与时刻不一致")
            elif value["precision"] == "datetime":
                if not isinstance(value["at"], str):
                    fail("模型截止缺少具体时刻")
                when = parse_datetime(value["at"], field="due.at")
                if value["date"] is not None and value["date"] != when.date().isoformat():
                    fail("模型截止日期与时刻不一致")
            elif value["at"] is not None:
                fail("模型截止精度与时刻不一致")
            if value["precision"] == "date_only" and value["date"] is None:
                fail("模型日期精度却没有日期")
        if (len(notice["materials"]) > 30 or any(len(m) > 512 or not any(m in q for q in citations.get("materials", []))
                                                for m in notice["materials"])):
            fail("模型材料缺少原文证据或超出范围")
        quotes = "\n".join(s["quote"] for s in notice["source_spans"])
        needs = ["source_review", *notice["needs_confirmation"]]
        if CAUTION.search(quotes):
            needs.append("changed_or_cancelled_notice")
        if RELATIVE.search(quotes) and not reference_at and not notice["published_at"]:
            needs.append("reference_date")
        if notice["event"]["precision"] != "unknown" and notice["due"]["precision"] != "unknown":
            needs.append("mixed_actions")
        # Citation existence does not prove semantic correctness. Model dates
        # and estimates require explicit field-level supplements before checking.
        needs.extend(["due_time", "estimated_minutes", "earliest_start"]
                     if proposal["kind"] == "deadline_feasibility" else ["event_time"])
        notice["needs_confirmation"] = list(dict.fromkeys(needs))
        notice["notice_id"] = "model-" + payload_hash({"source": source_ref, "text": source_text,
                                                       "spans": notice["source_spans"], "index": index})[:32]
        notice["extracted_at"] = extracted_at or datetime.now(TZ).isoformat(timespec="seconds")
        items.append({"kind": proposal["kind"], "notice": notice})
    unclassified = []
    for quote in raw["unclassified"]:
        evidence(quote)
        unclassified.append({"quote": quote, "source_ref": source_ref})
    unread = [i for i, character in enumerate(source_text) if not covered[i] and not character.isspace()]
    if unread:
        for item in items:
            item["notice"]["needs_confirmation"].append("incomplete_source_coverage")
    return {"batch_version": "notice-text-pilot-v1", "reader": "reviewed-model-proposal-v1",
            "items": items, "unclassified": unclassified,
            "coverage": {"input_kind": "text", "characters_total": len(source_text),
                         "characters_read": len(source_text) - len(unread), "unread_ranges": unread},
            "limitations": ["模型输出仅作为提炼建议；须逐字段明确确认日期、耗时和最早开始",
                            "未覆盖原文、取消或混合事项不能只勾选复核解除"]}

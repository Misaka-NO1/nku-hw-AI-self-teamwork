"""Observable business stages, built from evidence and actual B results."""
from app.core.contracts import validate_boundary
from app.core.errors import AppError
from app.core.notice_plan import calculate_notice
from app.domains.tasks.notice_model_reader import read_model_output
from app.domains.tasks.notice_reader import read_text


def extract_notice(payload):
    validate_boundary(payload, "NoticePilotReadRequest")
    if payload.get("model_output") is not None:
        batch = read_model_output(**{k: payload[k] for k in
            ("source_text", "source_ref", "reference_at", "model_output")})
    else:
        batch = read_text(**{k: payload[k] for k in
            ("source_text", "source_ref", "reference_at")})
    if payload.get("source_kind") == "ocr":
        from app.domains.tasks.notice_image_reader import require_ocr_review
        batch = require_ocr_review(batch)
    return batch


def run_notice_workflow(payload, records):
    validate_boundary(payload, "NoticeTextWorkflowRequest")
    source = payload["read"]
    batch = extract_notice(source)
    result = {"workflow_version": "notice-workflow-v1", "stage": "source_review",
        "batch": batch, "analysis": None, "saved": False,
        "steps": [{"step": "extract", "status": "review_required",
                   "item_count": len(batch["items"])},
                  {"step": "time_analysis", "status": "not_requested"},
                  {"step": "persist", "status": "requires_explicit_confirmation"}],
        "save_next": {"draft_path": "/api/v1/notice-text/drafts",
                      "confirmation_path": "/api/v1/notice-text/confirmations",
                      "commit_path": "/api/v1/notice-text/commit"}}
    selection = payload["analysis"]
    if selection is None:
        return result
    index = selection["item_index"]
    if index >= len(batch["items"]):
        raise AppError(422, "VALIDATION_ERROR", "本批事项索引不存在")
    request = {**source, **{k: v for k, v in selection.items() if k != "item_index"},
               "item_id": batch["items"][index]["notice"]["notice_id"]}
    analysis = calculate_notice(request, records, records["workspace_ref"])
    needs = analysis["time_result"]["needs_confirmation"]
    result["analysis"] = analysis
    if needs:
        result["stage"] = "clarification_required"
    elif analysis["item"]["kind"] == "event_conflict":
        result["stage"] = "confirmation_required"
    elif not analysis["time_result"].get("candidate_slots"):
        result["stage"] = "no_available_slot"
    else:
        result["stage"] = "selection_required"
    result["steps"][1] = {"step": "time_analysis",
        "status": "clarification_required" if needs else "calculated",
        "needs_confirmation": needs,
        "candidate_count": len(analysis["time_result"].get("candidate_slots", [])),
        "conflict_count": len(analysis["time_result"].get("conflicts", []))}
    return result

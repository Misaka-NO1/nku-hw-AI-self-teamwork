"""D-owned read adapters: one dispatch path shared by REST and MCP."""

import logging
from typing import Any

from app.core.config import Settings
from app.core.contracts import validate_boundary, validate_contract
from app.core.demo import FIXTURE_SET_ID, enforce_demo_fixture, load_fixture
from app.core.envelope import ApiEnvelope, EvidenceRef, WarningItem, success
from app.core.errors import AppError
from app.core.security import Principal, resolve_workspace
from app.domains.degree.audit import CALCULATION_VERSION as DEGREE_VERSION, audit_degree_progress
from app.domains.scenic import service as scenic
from app.domains.schedule import service as schedule
from app.domains.study import service as study
from app.domains.tasks.service import get_current_schedule, list_tasks
from app.domains.timeplan import service as timeplan


# This alias is a read-only public fixture, never a browser-owned workspace.
PUBLIC_DEMO_WORKSPACE_REF = "demo-workspace-01"
logger = logging.getLogger(__name__)
OPERATIONS = {
    "validate_timetable": "TimetableImport",
    "query_free_time": "FreeTimeQuery",
    "check_time_plan": "TimeCheckRequest",
    "search_scenic_spots": "ScenicQuery",
    "search_study_materials": "StudyQuery",
    "audit_degree_progress": "DegreeAuditRequest",
}


def public_principal(*, mcp: bool = False) -> Principal:
    return Principal(
        subject_id="mcp-public-demo" if mcp else "rest-public-demo",
        kind="mcp_service" if mcp else "public_reader",
        scopes=frozenset({"public:read"}),
        trusted_origin="server-integration" if mcp else "public-catalog",
    )


def _require_mode(runtime: Settings, principal: Principal) -> None:
    if runtime.auth_mode != "demo_fixture":
        raise AppError(403, "IDENTITY_NOT_VERIFIED", "Domain identity binding has not been verified")
    if not ({"public:read", "demo:read"} & principal.scopes):
        raise AppError(403, "FORBIDDEN", "Read scope required")


def _workspace(runtime: Settings, principal: Principal, workspace_ref: str) -> bool:
    """Return whether this is the public fixture, without granting service-user access."""
    if workspace_ref == PUBLIC_DEMO_WORKSPACE_REF:
        return True
    if principal.kind != "browser_user":
        raise AppError(403, "IDENTITY_NOT_VERIFIED", "Service credentials cannot access user workspaces")
    row = resolve_workspace(principal, workspace_ref, "demo:read", settings=runtime)
    if row["fixture_set_id"] != FIXTURE_SET_ID:
        raise AppError(403, "DEMO_ONLY", "Workspace is not the fixed demonstration dataset")
    return False


def _schedule_resources(runtime: Settings, principal: Principal, workspace_ref: str):
    if _workspace(runtime, principal, workspace_ref):
        timetable = load_fixture("timetable.demo.json")
        # Checked-in NoticeDraft examples are not confirmed tasks. Merely loading
        # their fixtures must not create busy time or imply a successful save.
        notices = []
    else:
        timetable = get_current_schedule(runtime, principal, workspace_ref)["timetable"]
        notices = [item["notice"] for item in list_tasks(runtime, principal, workspace_ref)]
    enforce_demo_fixture(timetable, "schedule")
    for notice in notices:
        enforce_demo_fixture(notice, "task")
    return timetable, notices


def _notice_events(notices: list[dict]) -> list[dict]:
    # Resource-shape conversion only; all interval calculations remain B's functions.
    return [{
        "event_id": f"task:{notice['notice_id']}",
        "start": notice["event"]["start"], "end": notice["event"]["end"],
    } for notice in notices if notice["event"]["precision"] == "datetime"
        and notice["event"]["start"] and notice["event"]["end"]]


def _study_evidence(items: list[dict]) -> list[EvidenceRef]:
    return [EvidenceRef(
        label=item["source_label"], source_ref=chunk["source_excerpt_ref"],
        locator=chunk["heading"],
    ) for item in items for chunk in item["evidence"]]


def execute_domain(
    operation: str, payload: Any, principal: Principal, runtime: Settings, request_id: str,
) -> ApiEnvelope:
    if operation not in OPERATIONS:
        raise AppError(404, "NOT_FOUND", "Unknown domain operation")
    validate_boundary(payload, OPERATIONS[operation])
    _require_mode(runtime, principal)
    try:
        return _dispatch_domain(operation, payload, principal, runtime, request_id)
    except AppError:
        raise
    except Exception:
        logger.error("Domain dependency failed", extra={"request_id": request_id, "tool_name": operation})
        raise AppError(503, "DEPENDENCY_UNAVAILABLE", "Domain dependency unavailable", retryable=True) from None


def _dispatch_domain(operation, payload, principal, runtime, request_id) -> ApiEnvelope:
    warnings = [WarningItem(code="DEMO_DATA", message="Fixed fictional demonstration data, not a student's live records")]
    evidence: list[EvidenceRef] = []
    version = None

    if operation == "validate_timetable":
        enforce_demo_fixture(payload, "schedule")
        data = schedule.validate_timetable(payload)
        version = schedule.CALCULATION_VERSION
    elif operation == "search_scenic_spots":
        catalog = scenic.load_catalog()
        data = scenic.search_spots(payload, catalog)
        warnings.append(WarningItem(code="NOT_REALTIME", message="Historical bloom months do not prove current bloom conditions"))
    elif operation == "search_study_materials":
        catalog = study.load_catalog()
        data = study.search_materials(payload, principal, catalog)
        evidence = _study_evidence(data)
        if any(not item["content_available"] for item in data):
            warnings.append(WarningItem(code="INDEX_ONLY", message="Index-only material cannot support a body-text answer"))
    elif operation in {"query_free_time", "check_time_plan"}:
        timetable, notices = _schedule_resources(runtime, principal, payload["workspace_ref"])
        events, calendar_warnings = schedule.expand_occurrences(timetable["term"], timetable["courses"], payload["window"])
        warnings.extend(WarningItem(**item) for item in calendar_warnings)
        if operation == "query_free_time":
            data = timeplan.find_free_slots(
                events + _notice_events(notices), payload["window"], payload["min_minutes"], payload["buffers"],
            )
        else:
            data = timeplan.check_time_plan(timetable["term"], timetable["courses"], notices, payload)
        validate_boundary(data, "TimeResult")
        version = schedule.CALCULATION_VERSION
    else:
        _workspace(runtime, principal, payload["workspace_ref"])
        plan = load_fixture("degree-plan.demo.json")
        transcript = load_fixture("transcript.demo.json")
        if payload["plan_id"] != plan["plan_id"] or payload["transcript_ref"] != transcript["transcript_id"]:
            raise AppError(404, "NOT_FOUND", "Plan or transcript not found in the authorized demo dataset")
        validate_contract(plan, "DegreePlan")
        validate_contract(transcript, "Transcript")
        data = audit_degree_progress(plan, transcript["records"])
        validate_boundary(data, "DegreeAuditResult")
        version = DEGREE_VERSION
        evidence = [EvidenceRef(label="Fictional degree-plan fixture", source_ref=plan["source_ref"], locator=plan["plan_id"])]
        warnings.append(WarningItem(code="NOT_GRADUATION_DECISION", message="Progress under supported rules, not an official graduation decision"))

    return success(data, request_id=request_id, data_version=FIXTURE_SET_ID,
                   calculation_version=version, warnings=warnings, evidence_refs=evidence)


def public_detail(kind: str, identifier: str, runtime: Settings, request_id: str) -> ApiEnvelope:
    principal = public_principal()
    _require_mode(runtime, principal)
    if kind == "scenic":
        data = scenic.get_spot(identifier, scenic.load_catalog())
    else:
        data = study.get_material(identifier, principal, study.load_catalog())
    return success(data, request_id=request_id, data_version=FIXTURE_SET_ID,
                   warnings=[WarningItem(code="DEMO_DATA", message="Fixed fictional demonstration data")],
                   evidence_refs=_study_evidence([data]) if kind == "study" else [])


def public_download(identifier: str, runtime: Settings):
    principal = public_principal()
    _require_mode(runtime, principal)
    return study.resolve_download(identifier, principal, study.load_catalog())

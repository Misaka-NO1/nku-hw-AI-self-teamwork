"""D-owned read adapters: one dispatch path shared by REST and MCP."""

import logging
from urllib.parse import urlsplit
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
from app.domains.study.library import StudyLibrary
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
        locator=" · ".join(part for part in (chunk.get("page_label"), chunk["heading"]) if part),
    ) for item in items for chunk in item["evidence"]]


def _published_links(data, runtime: Settings, field: str):
    """Only server-configured same-origin destinations, never model-supplied URLs."""
    origin = runtime.app_origin.rstrip("/")
    if not origin or runtime.public_catalog_profile != "published":
        return data
    url = urlsplit(origin)
    if (url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password
            or url.path or url.query or url.fragment
            or runtime.app_env in {"staging", "production"} and url.scheme != "https"):
        raise AppError(503, "DEPENDENCY_UNAVAILABLE", "Public content origin is misconfigured")
    for item in data if isinstance(data, list) else [data]:
        path = item[field]
        allowed = (path.startswith("/api/v1/study/materials/") and path.endswith("/download")
                   if field == "download_url" else path.startswith("/tools/"))
        if not allowed:
            raise AppError(503, "DEPENDENCY_UNAVAILABLE", "Public content link is unavailable")
        item[field] = origin + item[field]
    return data


def _scenic_catalog(runtime: Settings):
    if runtime.public_catalog_profile == "published":
        return scenic.load_catalog(scenic.CATALOG_PATH.with_name("catalog.jinnan.json"))
    return scenic.load_catalog()


def _study_result(runtime: Settings, principal: Principal, *, query=None, identifier=None, download=False):
    if runtime.public_catalog_profile == "published":
        library = StudyLibrary()
        try:
            if download:
                return library.resolve_download(identifier, principal)
            data = (library.search_materials(query, principal) if query is not None
                    else library.get_material(identifier, principal))
            items = data if isinstance(data, list) else [data]
            return data, library.data_version(), [WarningItem(**warning) for warning in
                library.extraction_warnings([item["material_id"] for item in items])]
        except ValueError:
            raise AppError(422, "VALIDATION_ERROR", "Invalid study query") from None
        except KeyError:
            raise AppError(404, "NOT_FOUND", "Material not found") from None
    catalog = study.load_catalog()
    if download:
        return study.resolve_download(identifier, principal, catalog)
    data = (study.search_materials(query, principal, catalog) if query is not None
            else study.get_material(identifier, principal, catalog))
    return data, catalog["data_version"], [WarningItem(code="DEMO_DATA", message="Fixed fictional demonstration data")]


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


def public_study_catalog(runtime: Settings, request_id: str) -> ApiEnvelope:
    """Complete public download catalog; no personal/team material or MCP schema change."""
    _require_mode(runtime, public_principal())
    if runtime.public_catalog_profile != "published":
        raise AppError(404, "NOT_FOUND", "Published study catalog unavailable")
    library = StudyLibrary()
    materials = library.list_materials()
    _published_links(materials, runtime, "material_url")
    _published_links(materials, runtime, "download_url")
    return success({"courses": library.list_courses(), "materials": materials, "total": len(materials)},
        request_id=request_id, data_version=library.data_version(),
        warnings=[WarningItem(code="HISTORICAL_MATERIALS", message="历史复习资料，不代表今年考试范围")])


def _dispatch_domain(operation, payload, principal, runtime, request_id) -> ApiEnvelope:
    warnings = [WarningItem(code="DEMO_DATA", message="Fixed fictional demonstration data, not a student's live records")]
    evidence: list[EvidenceRef] = []
    version = None
    data_version = FIXTURE_SET_ID

    if operation == "validate_timetable":
        enforce_demo_fixture(payload, "schedule")
        data = schedule.validate_timetable(payload)
        version = schedule.CALCULATION_VERSION
    elif operation == "search_scenic_spots":
        catalog = _scenic_catalog(runtime)
        data = scenic.search_spots(payload, catalog)
        _published_links(data, runtime, "map_url")
        if runtime.public_catalog_profile == "published":
            data_version = catalog["data_version"]
            warnings = [WarningItem(code="SCENIC_UNVERIFIED", message="用户录入的点位、文字和植物种类尚未逐条独立核验")]
        warnings.append(WarningItem(code="NOT_REALTIME", message="Historical bloom months do not prove current bloom conditions"))
    elif operation == "search_study_materials":
        data, data_version, warnings = _study_result(runtime, principal, query=payload)
        _published_links(data, runtime, "material_url")
        _published_links(data, runtime, "download_url")
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

    return success(data, request_id=request_id, data_version=data_version,
                   calculation_version=version, warnings=warnings, evidence_refs=evidence)


def public_detail(kind: str, identifier: str, runtime: Settings, request_id: str) -> ApiEnvelope:
    principal = public_principal()
    _require_mode(runtime, principal)
    if kind == "scenic":
        catalog = _scenic_catalog(runtime)
        data = scenic.get_spot(identifier, catalog)
        _published_links(data, runtime, "map_url")
        data_version = catalog["data_version"] if runtime.public_catalog_profile == "published" else FIXTURE_SET_ID
        warnings = ([WarningItem(code="SCENIC_UNVERIFIED", message="点位文字和植物种类尚未逐条核验"),
                     WarningItem(code="NOT_REALTIME", message="历史观赏建议不是实时花况")]
                    if runtime.public_catalog_profile == "published" else
                    [WarningItem(code="DEMO_DATA", message="Fixed fictional demonstration data")])
    else:
        data, data_version, warnings = _study_result(runtime, principal, identifier=identifier)
        _published_links(data, runtime, "material_url")
        _published_links(data, runtime, "download_url")
    return success(data, request_id=request_id, data_version=data_version,
                   warnings=warnings,
                   evidence_refs=_study_evidence([data]) if kind == "study" else [])


def public_download(identifier: str, runtime: Settings):
    principal = public_principal()
    _require_mode(runtime, principal)
    return _study_result(runtime, principal, identifier=identifier, download=True)

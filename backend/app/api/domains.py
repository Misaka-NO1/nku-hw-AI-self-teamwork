"""Frozen REST paths over the shared D-owned domain adapter."""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.contracts import validate_boundary
from app.core.domain_adapter import (
    OPERATIONS, PUBLIC_DEMO_WORKSPACE_REF, execute_domain,
    public_detail, public_download, public_principal,
)
from app.core.envelope import ApiEnvelope
from app.core.errors import AppError
from app.core.request_id import current_request_id
from app.core.security import resolve_browser_principal


router = APIRouter(prefix="/api/v1", tags=["domain-read"])


def _execute(request: Request, operation: str, payload: Any):
    validate_boundary(payload, OPERATIONS[operation])
    workspace = payload.get("workspace_ref")
    principal = (public_principal() if workspace is None or workspace == PUBLIC_DEMO_WORKSPACE_REF
                 else resolve_browser_principal(request))
    return execute_domain(operation, payload, principal, get_settings(), current_request_id(request))


def _query(request: Request, query: str) -> Any:
    if len(query) > 8192 or set(request.query_params) != {"query"} or len(request.query_params.getlist("query")) != 1:
        raise AppError(422, "VALIDATION_ERROR", "Send exactly one query parameter containing the JSON query")
    try:
        return json.loads(query)
    except (ValueError, RecursionError):
        raise AppError(422, "VALIDATION_ERROR", "query must be a valid JSON object") from None


@router.get("/scenic/spots", response_model=ApiEnvelope)
def search_scenic_route(request: Request, query: Annotated[str, Query()]):
    return _execute(request, "search_scenic_spots", _query(request, query))


@router.get("/scenic/spots/{spot_id}", response_model=ApiEnvelope)
def scenic_detail_route(spot_id: str, request: Request):
    return public_detail("scenic", spot_id, get_settings(), current_request_id(request))


@router.get("/study/materials", response_model=ApiEnvelope)
def search_study_route(request: Request, query: Annotated[str, Query()]):
    return _execute(request, "search_study_materials", _query(request, query))


@router.get("/study/materials/{material_id}", response_model=ApiEnvelope)
def study_detail_route(material_id: str, request: Request):
    return public_detail("study", material_id, get_settings(), current_request_id(request))


@router.get("/study/materials/{material_id}/download")
def study_download_route(material_id: str):
    path = public_download(material_id, get_settings())
    return FileResponse(path, filename=path.name, media_type="text/markdown; charset=utf-8")


@router.post("/schedules/validate", response_model=ApiEnvelope)
def validate_timetable_route(request: Request, payload: Annotated[Any, Body()]):
    return _execute(request, "validate_timetable", payload)


@router.post("/time/free-slots", response_model=ApiEnvelope)
def free_time_route(request: Request, payload: Annotated[Any, Body()]):
    return _execute(request, "query_free_time", payload)


@router.post("/time/check", response_model=ApiEnvelope)
def time_check_route(request: Request, payload: Annotated[Any, Body()]):
    return _execute(request, "check_time_plan", payload)


@router.post("/degree/audit", response_model=ApiEnvelope)
def degree_audit_route(request: Request, payload: Annotated[Any, Body()]):
    return _execute(request, "audit_degree_progress", payload)

from typing import Annotated, Any

from fastapi import APIRouter, Body, Header, Request, Response

from app.core.config import get_settings
from app.core.contracts import validate_boundary
from app.core.envelope import success
from app.core.errors import AppError
from app.core.notice_pilot import VERSION, check_notice, pilot_workspace, require_pilot
from app.core.request_id import current_request_id
from app.core.security import SESSION_COOKIE, require_idempotency_key, resolve_browser_principal
from app.db.database import database_connection
from app.domains.tasks.notice_reader import read_text
from app.domains.tasks.service import (create_browser_draft, create_demo_workspace,
                                      get_draft, update_draft)

router = APIRouter(prefix="/api/v1/notice-pilot", tags=["local-notice-pilot"])


def envelope(request, result):
    return success(result, request_id=current_request_id(request), data_version=VERSION)


@router.post("/workspaces")
def create_workspace(request: Request, response: Response, payload: Annotated[dict, Body()]):
    require_pilot(get_settings())
    if payload != {"fictional_data_confirmed": True}:
        raise AppError(422, "VALIDATION_ERROR", "请确认仅使用自编虚构通知和固定演示课表")
    result = create_demo_workspace(get_settings(), "demo-v1")
    with database_connection(get_settings()) as connection:
        connection.execute("UPDATE workspaces SET fixture_set_id = ? WHERE workspace_ref = ?",
                           (VERSION, result["workspace_ref"]))
        connection.commit()
    token = result.pop("session_token")
    result["fixture_set_id"] = VERSION
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", path="/",
                        max_age=get_settings().demo_workspace_ttl_hours * 3600)
    return envelope(request, result)


@router.post("/read")
def read(request: Request, payload: Annotated[dict[str, Any], Body()]):
    principal = resolve_browser_principal(request, require_csrf=True)
    pilot_workspace(get_settings(), principal)
    validate_boundary(payload, "NoticePilotReadRequest")
    if payload.get("model_output") is not None:
        from app.domains.tasks.notice_model_reader import read_model_output
        result = read_model_output(**{k: payload[k] for k in ("source_text", "source_ref", "reference_at", "model_output")})
    else:
        result = read_text(**{k: payload[k] for k in ("source_text", "source_ref", "reference_at")})
    return envelope(request, result)


@router.post("/check")
def check(request: Request, payload: Annotated[dict[str, Any], Body()]):
    principal = resolve_browser_principal(request, require_csrf=True)
    return envelope(request, check_notice(get_settings(), principal, payload))


@router.post("/drafts")
def draft(request: Request, payload: Annotated[dict[str, Any], Body()],
          idempotency_key: Annotated[str, Header(alias="Idempotency-Key")]):
    require_idempotency_key(idempotency_key)
    validate_boundary(payload, "NoticePilotDraftRequest")
    principal = resolve_browser_principal(request, require_csrf=True)
    workspace = pilot_workspace(get_settings(), principal)
    result = create_browser_draft(get_settings(), principal, workspace, "task", payload["plan"], idempotency_key)
    return envelope(request, result)


@router.post("/drafts/{draft_id}/update")
def update(draft_id: str, request: Request, payload: Annotated[dict[str, Any], Body()]):
    validate_boundary(payload, "NoticePilotUpdateRequest")
    principal = resolve_browser_principal(request, require_csrf=True)
    workspace = pilot_workspace(get_settings(), principal)
    existing = get_draft(get_settings(), principal, draft_id)
    if existing["workspace_ref"] != workspace or existing["payload"].get("plan_version") != VERSION:
        raise AppError(404, "NOT_FOUND", "试点草稿不存在")
    result = update_draft(get_settings(), principal, draft_id, payload["plan"], payload["revision"])
    return envelope(request, result)

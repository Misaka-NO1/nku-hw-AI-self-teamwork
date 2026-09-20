from typing import Annotated, Any

from fastapi import APIRouter, Body, Header, Query, Request

from app.api.tasks import CommitRequest
from app.core.config import get_settings
from app.core.envelope import ApiEnvelope, success
from app.core.errors import AppError
from app.core.request_id import current_request_id
from app.core.security import require_idempotency_key, resolve_browser_principal
from app.domains.tasks.service import (
    active_workspace_ref,
    commit_draft,
    create_browser_draft,
    create_schedule_draft_with_ticket,
    get_current_schedule,
)


router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


@router.post("/import-drafts", response_model=ApiEnvelope[dict])
def create_schedule_import_draft_route(
    request: Request,
    payload: Annotated[dict[str, Any], Body()],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ApiEnvelope[dict]:
    require_idempotency_key(idempotency_key)
    prefix = "ImportTicket "
    if authorization and authorization.startswith(prefix):
        raw_ticket = authorization.removeprefix(prefix)
        result = create_schedule_draft_with_ticket(
            get_settings(), raw_ticket, payload, idempotency_key
        )
    elif authorization:
        raise AppError(status_code=401, code="AUTH_REQUIRED", message="Import ticket is invalid")
    else:
        principal = resolve_browser_principal(request, require_csrf=True)
        workspace_ref = active_workspace_ref(get_settings(), principal)
        result = create_browser_draft(
            get_settings(),
            principal,
            workspace_ref,
            "schedule",
            payload,
            idempotency_key,
        )
    return success(result, request_id=current_request_id(request), data_version="demo-v1")


@router.post("/commit", response_model=ApiEnvelope[dict])
def commit_schedule_route(payload: CommitRequest, request: Request) -> ApiEnvelope[dict]:
    require_idempotency_key(payload.idempotency_key)
    principal = resolve_browser_principal(request, require_csrf=True)
    result = commit_draft(
        get_settings(), principal, "schedule", payload.confirmation_id, payload.idempotency_key
    )
    return success(result, request_id=current_request_id(request), data_version="demo-v1")


@router.get("/current", response_model=ApiEnvelope[dict])
def get_current_schedule_route(
    request: Request,
    workspace_ref: Annotated[str, Query(min_length=1, max_length=128)],
) -> ApiEnvelope[dict]:
    principal = resolve_browser_principal(request)
    result = get_current_schedule(get_settings(), principal, workspace_ref)
    return success(result, request_id=current_request_id(request), data_version="demo-v1")

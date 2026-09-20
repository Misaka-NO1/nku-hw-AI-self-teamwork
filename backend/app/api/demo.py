from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.envelope import ApiEnvelope, success
from app.core.request_id import current_request_id
from app.core.security import SESSION_COOKIE, require_idempotency_key, resolve_browser_principal
from app.domains.tasks.service import create_demo_workspace, create_import_ticket


router = APIRouter(prefix="/api/v1", tags=["demo"])


class CreateDemoWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixture_set_id: str = Field(min_length=1, max_length=128)


class CreateImportTicketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_ref: str = Field(min_length=1, max_length=128)
    purpose: str = Field(min_length=1, max_length=64)


@router.post("/demo/workspaces", response_model=ApiEnvelope[dict])
def create_workspace_route(
    payload: CreateDemoWorkspaceRequest,
    request: Request,
    response: Response,
) -> ApiEnvelope[dict]:
    settings = get_settings()
    result = create_demo_workspace(settings, payload.fixture_set_id)
    session_token = result.pop("session_token")
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        max_age=settings.demo_workspace_ttl_hours * 3600,
        httponly=True,
        secure=settings.app_env in {"staging", "production"},
        samesite="lax",
        path="/",
    )
    return success(result, request_id=current_request_id(request), data_version="demo-v1")


@router.post("/import-tickets", response_model=ApiEnvelope[dict])
def create_import_ticket_route(
    payload: CreateImportTicketRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> ApiEnvelope[dict]:
    require_idempotency_key(idempotency_key)
    principal = resolve_browser_principal(request, require_csrf=True)
    result = create_import_ticket(
        get_settings(), principal, payload.workspace_ref, payload.purpose, idempotency_key
    )
    return success(result, request_id=current_request_id(request), data_version="demo-v1")

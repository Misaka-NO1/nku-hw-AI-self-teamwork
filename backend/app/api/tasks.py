from typing import Annotated, Any

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.envelope import ApiEnvelope, success
from app.core.request_id import current_request_id
from app.core.security import require_idempotency_key, resolve_browser_principal
from app.domains.tasks.service import commit_draft, create_browser_draft, get_task, list_tasks


router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


class TaskDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_ref: str = Field(min_length=1, max_length=128)
    notice: dict[str, Any]


class CommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation_id: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=8, max_length=128)


@router.post("/drafts", response_model=ApiEnvelope[dict])
def create_task_draft_route(
    payload: TaskDraftRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> ApiEnvelope[dict]:
    require_idempotency_key(idempotency_key)
    principal = resolve_browser_principal(request, require_csrf=True)
    result = create_browser_draft(
        get_settings(),
        principal,
        payload.workspace_ref,
        "task",
        payload.notice,
        idempotency_key,
    )
    return success(result, request_id=current_request_id(request), data_version="demo-v1")


@router.post("/commit", response_model=ApiEnvelope[dict])
def commit_task_route(payload: CommitRequest, request: Request) -> ApiEnvelope[dict]:
    require_idempotency_key(payload.idempotency_key)
    principal = resolve_browser_principal(request, require_csrf=True)
    result = commit_draft(
        get_settings(), principal, "task", payload.confirmation_id, payload.idempotency_key
    )
    return success(result, request_id=current_request_id(request), data_version="demo-v1")


@router.get("", response_model=ApiEnvelope[list[dict]])
def list_tasks_route(
    request: Request,
    workspace_ref: Annotated[str, Query(min_length=1, max_length=128)],
) -> ApiEnvelope[list[dict]]:
    principal = resolve_browser_principal(request)
    result = list_tasks(get_settings(), principal, workspace_ref)
    return success(result, request_id=current_request_id(request), data_version="demo-v1")


@router.get("/{task_id}", response_model=ApiEnvelope[dict])
def get_task_route(task_id: str, request: Request) -> ApiEnvelope[dict]:
    principal = resolve_browser_principal(request)
    result = get_task(get_settings(), principal, task_id)
    return success(result, request_id=current_request_id(request), data_version="demo-v1")

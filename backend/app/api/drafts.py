from typing import Annotated

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.envelope import ApiEnvelope, success
from app.core.errors import AppError
from app.core.request_id import current_request_id
from app.core.security import require_idempotency_key, resolve_browser_principal
from app.domains.tasks.service import create_confirmation, get_draft


router = APIRouter(prefix="/api/v1", tags=["drafts"])


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=1)
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.get("/drafts/{draft_id}", response_model=ApiEnvelope[dict])
def get_draft_route(draft_id: str, request: Request) -> ApiEnvelope[dict]:
    principal = resolve_browser_principal(request)
    result = get_draft(get_settings(), principal, draft_id)
    return success(result, request_id=current_request_id(request), data_version="demo-v1")


@router.post("/confirmations", response_model=ApiEnvelope[dict])
def create_confirmation_route(
    payload: ConfirmationRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> ApiEnvelope[dict]:
    require_idempotency_key(idempotency_key)
    principal = resolve_browser_principal(request, require_csrf=True)
    if not payload.draft_id:
        raise AppError(status_code=422, code="VALIDATION_ERROR", message="Draft ID required")
    result = create_confirmation(
        get_settings(),
        principal,
        payload.draft_id,
        payload.revision,
        payload.payload_hash,
        idempotency_key,
    )
    return success(result, request_id=current_request_id(request), data_version="demo-v1")

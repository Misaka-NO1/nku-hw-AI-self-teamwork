"""Explicitly isolated, opt-in local fictional notice/schedule adapter."""

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import Principal, resolve_workspace

VERSION = "notice-text-pilot-v1"


def require_pilot(settings: Settings) -> None:
    if not settings.notice_text_pilot_enabled:
        raise AppError(403, "DEMO_ONLY", "本地文字试点未开启")
    settings.validate_deployment()


def pilot_workspace(settings: Settings, principal: Principal) -> str:
    require_pilot(settings)
    if principal.kind != "browser_user":
        raise AppError(403, "IDENTITY_NOT_VERIFIED", "试点仅允许本人浏览器会话")
    from app.domains.tasks.service import active_workspace_ref
    workspace_ref = active_workspace_ref(settings, principal)
    row = resolve_workspace(principal, workspace_ref, "demo:read", settings=settings)
    if row["fixture_set_id"] != VERSION:
        raise AppError(403, "DEMO_ONLY", "需要独立的文字试点工作区")
    return workspace_ref



def _records(settings, principal, workspace_ref):
    from app.domains.tasks.service import get_current_schedule, list_tasks
    return {"schedule": get_current_schedule(settings, principal, workspace_ref),
            "tasks": list_tasks(settings, principal, workspace_ref)}


def check_notice(settings: Settings, principal: Principal, payload: dict) -> dict:
    from app.core.notice_plan import calculate_notice
    workspace = pilot_workspace(settings, principal)
    return calculate_notice(payload, _records(settings, principal, workspace), workspace)


def validate_plan(settings: Settings, principal: Principal, workspace_ref: str, plan: dict) -> str:
    from app.core.notice_plan import validate_notice_plan
    if workspace_ref != pilot_workspace(settings, principal):
        raise AppError(404, "NOT_FOUND", "工作区不存在")
    return validate_notice_plan(plan, _records(settings, principal, workspace_ref), workspace_ref)

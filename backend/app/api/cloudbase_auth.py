"""Closed login pilot; deliberately does not alter the public MCP contract."""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import APIRouter, Request, Response

from app.core.cloudbase_auth import issue_pilot_session, require_pilot, verify_cloudbase_user
from app.core.config import get_settings
from app.core.envelope import success
from app.core.errors import AppError
from app.core.request_id import current_request_id
from app.core.security import SESSION_COOKIE, resolve_browser_principal, secret_hash
from app.db.database import database_connection

router = APIRouter(prefix="/api/v1/auth/cloudbase", tags=["closed-auth-pilot"])
_attempts: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def _origin_and_rate(request: Request) -> None:
    runtime = get_settings()
    if not runtime.app_origin or request.headers.get("Origin", "").rstrip("/") != runtime.app_origin.rstrip("/"):
        raise AppError(403, "FORBIDDEN", "Same-origin browser login is required")
    # Single-process pilot only. Production must replace this with a shared limiter.
    peer = request.client.host if request.client else "unknown"
    with _lock:
        now = time.monotonic()
        for key in list(_attempts):
            while _attempts[key] and _attempts[key][0] <= now - 60:
                _attempts[key].popleft()
            if not _attempts[key]:
                del _attempts[key]
        if len(_attempts[peer]) >= 10:
            raise AppError(429, "RATE_LIMITED", "Too many login attempts; try again in one minute", True)
        _attempts[peer].append(now)


@router.get("/config")
def auth_config(request: Request, response: Response):
    runtime = get_settings()
    require_pilot(runtime)
    response.headers["Cache-Control"] = "no-store"
    return success({"env_id": runtime.cloudbase_auth_env_id, "region": "ap-shanghai",
        "dataset_kind": "demo", "personal_uploads": False, "agent_paired": False},
        request_id=current_request_id(request), data_version="closed-pilot-v1")


@router.post("/session")
async def login(request: Request, response: Response):
    runtime = get_settings()
    require_pilot(runtime)
    _origin_and_rate(request)
    subject = await verify_cloudbase_user(runtime, request.headers.get("Authorization", ""))
    result = issue_pilot_session(runtime, subject, request.cookies.get(SESSION_COOKIE, ""))
    raw_session = result.pop("session_token")
    response.set_cookie(SESSION_COOKIE, raw_session, httponly=True, samesite="strict",
        secure=runtime.app_env in {"staging", "production"}, path="/",
        max_age=runtime.cloudbase_auth_session_seconds)
    response.headers["Cache-Control"] = "no-store"
    return success(result, request_id=current_request_id(request), data_version="closed-pilot-v1")


@router.post("/logout")
def logout(request: Request, response: Response):
    runtime = get_settings()
    principal = resolve_browser_principal(request, require_csrf=True)
    with database_connection(runtime) as connection:
        connection.execute("DELETE FROM browser_sessions WHERE token_hash=? AND subject_id=?",
            (secret_hash(request.cookies.get(SESSION_COOKIE, "")), principal.subject_id))
        connection.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="strict",
        secure=runtime.app_env in {"staging", "production"}, httponly=True)
    response.headers["Cache-Control"] = "no-store"
    return success({"logged_out": True}, request_id=current_request_id(request), data_version="closed-pilot-v1")

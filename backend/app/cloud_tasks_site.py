"""Isolated fictional TasksPage + CloudBase PostgreSQL RPC, never MCP 005.

No SQL, CloudBase service key, identity assertion or commit tool is exposed to an
Agent/browser. Each authenticated RPC is one PostgreSQL transaction.
"""
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from secrets import token_urlsafe
from typing import Annotated, Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
from fastapi import Body, FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.demo import CreateDemoWorkspaceRequest
from app.api.drafts import ConfirmationRequest
from app.api.tasks import CommitRequest, TaskDraftRequest
from app.core.config import get_settings
from app.core.contracts import validate_boundary
from app.core.demo import FIXTURE_SET_ID, enforce_demo_fixture
from app.core.domain_adapter import PUBLIC_DEMO_WORKSPACE_REF, execute_domain, public_principal
from app.core.envelope import ApiEnvelope, failure, success
from app.core.errors import AppError
from app.core.request_id import current_request_id, resolve_request_id
from app.core.security import SESSION_COOKIE, payload_hash, require_idempotency_key, secret_hash

ENV_ID = "sunner-wang-d8ght8niaaaea70b7"
RPC_URL = f"https://{ENV_ID}.api.tcloudbasegateway.com/v1/rdb/rest/rpc/nku_tasks_demo_v1_rpc"


class RequestBodyLimit:
    """Bound streamed/chunked input too; Content-Length alone is not a limit."""
    def __init__(self, app, notice_text_enabled=False, personal_schedules_enabled=False):
        self.app = app
        self.notice_text_enabled = notice_text_enabled
        self.personal_schedules_enabled = personal_schedules_enabled

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        events, total = [], 0
        extended = self.notice_text_enabled and (
            scope.get("path", "").startswith("/api/v1/notice-text/")
            or scope.get("path", "").startswith("/oauth/notice/"))
        image = self.notice_text_enabled and scope.get("path", "") == "/api/v1/notice-text/images/read"
        schedule_upload = self.personal_schedules_enabled and scope.get("path", "") in {
            "/api/v1/schedules/import-drafts", "/api/v1/schedules/validate"}
        limit = 3 * 1024 * 1024 if image else 1048576 if schedule_upload else 524288 if extended else 32768
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            total += len(event.get("body", b""))
            if total > limit:
                response = JSONResponse(status_code=413, content=failure(request_id=str(uuid.uuid4()),
                    code="VALIDATION_ERROR", message="Request too large").model_dump(mode="json"))
                return await response(scope, receive, send)
            events.append(event)
            if not event.get("more_body", False):
                break

        async def replay():
            return events.pop(0) if events else await receive()

        await self.app(scope, replay, send)


class CloudTasksStore:
    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None):
        if not api_key:
            raise ValueError("Configure CLOUDBASE_API_KEY in server secrets, never in frontend/Git")
        self.client = httpx.Client(transport=transport, timeout=15, follow_redirects=False)
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def call(self, op: str, args: dict) -> Any:
        try:
            response = self.client.post(RPC_URL, headers=self._headers, json={"op": op, "args": args})
            if response.status_code != 200:
                raise ValueError("Storage request failed")
            body = response.json()
            if not isinstance(body, dict) or not isinstance(body.get("ok"), bool) or (body["ok"] and "data" not in body):
                raise ValueError("Invalid storage result")
        except (httpx.HTTPError, ValueError):
            # Never disclose API keys, upstream SQL errors or submitted data.
            raise AppError(503, "INTERNAL_ERROR", "Test storage unavailable", retryable=True) from None
        if not body["ok"]:
            safe_codes = {"AUTH_REQUIRED", "FORBIDDEN", "NOT_FOUND", "TOKEN_EXPIRED",
                          "DEMO_ONLY", "RATE_LIMITED", "VALIDATION_ERROR", "STALE_REVISION", "CONFIRMATION_REQUIRED"}
            code = body.get("code")
            status = body.get("status")
            if code not in safe_codes or status not in {401, 403, 404, 409, 410, 422, 429}:
                raise AppError(503, "INTERNAL_ERROR", "Invalid storage result", retryable=True)
            raise AppError(status, code, "Test storage rejected this operation", retryable=status == 429)
        return body["data"]

    def close(self):
        self.client.close()


def _format_result(value):
    if isinstance(value, list):
        return [_format_result(item) for item in value]
    result = dict(value)
    for source, dest in (("expires_epoch", "expires_at"), ("confirmed_epoch", "confirmed_at")):
        if source in result:
            result[dest] = datetime.fromtimestamp(result.pop(source), ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    return result


def create_cloud_tasks_site(frontend_root: Path | None = None, store: CloudTasksStore | None = None) -> FastAPI:
    settings = get_settings()
    origin = urlsplit(settings.app_origin)
    if (settings.auth_mode != "demo_fixture" or settings.allow_personal_uploads
        or settings.app_env != "staging" or origin.scheme != "https" or not origin.hostname
        or origin.username or origin.password or origin.query or origin.fragment or origin.path not in {"", "/"}):
        raise ValueError("Cloud test site requires staging, HTTPS origin, demo_fixture and personal uploads disabled")
    if settings.demo_workspace_ttl_hours != 24:
        raise ValueError("Cloud test schema uses a fixed 24-hour workspace TTL")
    root = frontend_root or Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not (root / "index.html").is_file():
        raise ValueError("Build and package the frontend before deployment")
    # CloudBase Run's named-key injector uses CLOUDBASE_APIKEY. The underscored
    # alias remains available for explicit server-secret configuration.
    database = store or CloudTasksStore(
        os.environ.get("CLOUDBASE_APIKEY") or os.environ.get("CLOUDBASE_API_KEY", ""))

    @asynccontextmanager
    async def lifespan(_):
        database.call("probe", {})
        try:
            yield
        finally:
            database.close()

    site = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    site.add_middleware(RequestBodyLimit)

    @site.middleware("http")
    async def request_context(request, call_next):
        request.state.request_id = resolve_request_id(request)
        response = await call_next(request)
        response.headers["X-Request-ID"] = current_request_id(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @site.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content=failure(request_id=current_request_id(request),
            code=exc.code, message=exc.message, retryable=exc.retryable).model_dump(mode="json"))

    @site.exception_handler(RequestValidationError)
    async def validation_error(request, _):
        return await app_error(request, AppError(422, "VALIDATION_ERROR", "Request does not match the interface contract"))

    @site.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        return await app_error(request, AppError(exc.status_code, "NOT_FOUND" if exc.status_code == 404 else "VALIDATION_ERROR", "Request rejected"))

    @site.exception_handler(Exception)
    async def unexpected_error(request, _):
        return await app_error(request, AppError(500, "INTERNAL_ERROR", "Internal server error", retryable=True))

    def args_for(request: Request, write=False) -> dict:
        token = request.cookies.get(SESSION_COOKIE, "")
        if not token:
            raise AppError(401, "AUTH_REQUIRED", "Browser session required")
        # Mutations require a real same-origin browser Origin; not a shared MCP bearer.
        given_origin = request.headers.get("Origin", "")
        if (write and given_origin != settings.app_origin.rstrip("/")) or (given_origin and given_origin != settings.app_origin.rstrip("/")):
            raise AppError(403, "FORBIDDEN", "Origin is not allowed")
        csrf = request.headers.get("X-CSRF-Token", "")
        if write and not csrf:
            raise AppError(403, "FORBIDDEN", "CSRF validation failed")
        return {"session_hash": secret_hash(token), "csrf_hash": secret_hash(csrf)}

    def reply(request, value):
        return success(_format_result(value), request_id=current_request_id(request), data_version="demo-v1")

    def review(result):
        result["review_url"] = f"{settings.app_origin.rstrip('/')}/tools/tasks?draft_id={result['draft_id']}"
        return result

    @site.get("/__tcb_probe__")
    def platform_probe():
        return Response("ok", media_type="text/plain")

    @site.get("/healthz")
    def health():
        database.call("probe", {})
        return {"status": "ok", "build_id": settings.build_id, "dataset_kind": "demo", "personal_uploads": False}

    @site.post("/api/v1/demo/workspaces", response_model=ApiEnvelope)
    def create_session(payload: CreateDemoWorkspaceRequest, request: Request, response: Response):
        if request.headers.get("Origin", "") != settings.app_origin.rstrip("/"):
            raise AppError(403, "FORBIDDEN", "Origin is not allowed")
        if payload.fixture_set_id != FIXTURE_SET_ID:
            raise AppError(403, "DEMO_ONLY", "Unknown fixture set")
        token, csrf = token_urlsafe(32), token_urlsafe(32)
        result = database.call("create_session", {"token_hash": secret_hash(token), "csrf_hash": secret_hash(csrf),
            "subject_id": "demo_subject_" + token_urlsafe(18), "workspace_ref": "demo_workspace_" + token_urlsafe(18)})
        response.set_cookie(SESSION_COOKIE, token, max_age=86400, httponly=True, secure=True, samesite="lax", path="/")
        return reply(request, {**result, "fixture_set_id": FIXTURE_SET_ID, "dataset_kind": "demo", "csrf_token": csrf})

    @site.post("/api/v1/tasks/drafts", response_model=ApiEnvelope)
    def create_draft(payload: TaskDraftRequest, request: Request, key: Annotated[str, Header(alias="Idempotency-Key")]):
        args = args_for(request, True)
        require_idempotency_key(key)
        validate_boundary(payload.notice, "NoticeDraft")
        digest = enforce_demo_fixture(payload.notice, "task")
        result = database.call("create_draft", {**args, "key": key, "workspace_ref": payload.workspace_ref,
            "payload_hash": digest, "draft_id": "task_draft_" + token_urlsafe(18),
            "request_hash": payload_hash({"workspace_ref": payload.workspace_ref, "kind": "task", "payload": payload.notice})})
        return reply(request, review(result))

    @site.get("/api/v1/drafts/{draft_id}", response_model=ApiEnvelope)
    def draft(draft_id: str, request: Request):
        return reply(request, review(database.call("get_draft", {**args_for(request), "draft_id": draft_id})))

    @site.post("/api/v1/confirmations", response_model=ApiEnvelope)
    def confirm(payload: ConfirmationRequest, request: Request, key: Annotated[str, Header(alias="Idempotency-Key")]):
        args = args_for(request, True)
        require_idempotency_key(key)
        confirmation_id = "confirmation_" + token_urlsafe(18)
        return reply(request, database.call("confirm", {**args, **payload.model_dump(), "key": key,
            "confirmation_id": confirmation_id, "confirmation_hash": secret_hash(confirmation_id),
            "request_hash": payload_hash(payload.model_dump())}))

    @site.post("/api/v1/tasks/commit", response_model=ApiEnvelope)
    def commit(payload: CommitRequest, request: Request):
        args = args_for(request, True)
        require_idempotency_key(payload.idempotency_key)
        return reply(request, database.call("commit", {**args, "key": payload.idempotency_key,
            "confirmation_hash": secret_hash(payload.confirmation_id), "task_id": "task_" + token_urlsafe(18),
            "request_hash": payload_hash({"kind": "task", "confirmation_id": payload.confirmation_id})}))

    @site.get("/api/v1/tasks", response_model=ApiEnvelope)
    def tasks(request: Request, workspace_ref: Annotated[str, Query(min_length=1, max_length=128)]):
        return reply(request, database.call("list_tasks", {**args_for(request), "workspace_ref": workspace_ref}))

    @site.get("/api/v1/tasks/{task_id}", response_model=ApiEnvelope)
    def task(task_id: str, request: Request):
        return reply(request, database.call("get_task", {**args_for(request), "task_id": task_id}))

    @site.post("/api/v1/time/check", response_model=ApiEnvelope)
    def time_check(request: Request, payload: Annotated[Any, Body()]):
        validate_boundary(payload, "TimeCheckRequest")
        if payload.get("workspace_ref") != PUBLIC_DEMO_WORKSPACE_REF:
            raise AppError(403, "DEMO_ONLY", "Only the public fictional timetable is available")
        return execute_domain("check_time_plan", payload, public_principal(), settings, current_request_id(request))

    site.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @site.get("/")
    def home():
        return RedirectResponse("/tools/tasks")

    @site.get("/tools/tasks")
    def page():
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-store"})

    return site

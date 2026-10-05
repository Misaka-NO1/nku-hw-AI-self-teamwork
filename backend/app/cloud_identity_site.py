"""Closed PG-backed identity/schedule/tasks pilot; not a production entrypoint.

CloudBase login is validated online by the existing identity verifier. Only the
two approved ordinary accounts and exact fictional fixtures are accepted.
All state/ownership/confirmation/idempotency lives in isolated PostgreSQL RPC.
"""
import logging
import os
import re
import time
from collections import defaultdict,deque
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from secrets import token_urlsafe
from threading import Lock
from typing import Annotated,Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from fastapi import Body,FastAPI,Header,Query,Request,Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse,JSONResponse,RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.demo import CreateImportTicketRequest
from app.api.drafts import ConfirmationRequest
from app.api.tasks import CommitRequest,TaskDraftRequest
from app.cloud_tasks_site import ENV_ID,RequestBodyLimit
from app.core.cloudbase_auth import require_pilot,verify_cloudbase_user
from app.core.cloud_identity_store import CloudIdentityStore
from app.core.browser_session_context import CONTEXT_COOKIE,decode_context,encode_context
from app.core.config import get_settings
from app.core.contracts import validate_boundary
from app.core.demo import FIXTURE_SET_ID,enforce_demo_fixture
from app.core.envelope import WarningItem,failure,success
from app.core.errors import AppError
from app.core.owned_time import calculate_owned_time
from app.core.request_id import current_request_id,resolve_request_id
from app.core.security import SESSION_COOKIE,payload_hash,require_idempotency_key,secret_hash
from app.domains.schedule import service as schedule
from app.core.domain_adapter import execute_domain,public_principal


def require_cloud_identity(settings):
    require_pilot(settings)
    url=urlsplit(settings.app_origin)
    if (not settings.cloud_identity_pilot_enabled or settings.app_env not in {"test","staging"}
        or settings.cloudbase_auth_profile!="pg_registered" or settings.cloudbase_auth_env_id!=ENV_ID
        or len(set(settings.cloudbase_auth_pilot_user_ids))!=2 or settings.demo_workspace_ttl_hours!=24
        or settings.cloudbase_auth_session_seconds!=900
        or url.scheme!="https" or not url.hostname or url.username is not None or url.password is not None
        or url.path or url.query or url.fragment):
        raise ValueError("Closed cloud identity pilot requires HTTPS, two approved PG users and fixed fictional retention")


def format_times(value):
    if isinstance(value,list):
        return [format_times(item) for item in value]
    if not isinstance(value,dict):
        return value
    result={key:format_times(item) for key,item in value.items()}
    for source,dest in (("expires_epoch","expires_at"),("confirmed_epoch","confirmed_at")):
        if source in result:
            result[dest]=datetime.fromtimestamp(result.pop(source),ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    return result


def install_health_diagnostics(site,runtime):
    """Fixed-route arrival evidence; never log URLs, headers or exceptions.

    This does not weaken the existing health/database/authentication gates.
    Uvicorn's configured error logger reaches the container stdout collector.
    """
    logger=logging.getLogger("uvicorn.error")
    build=runtime.build_id if re.fullmatch(r"[A-Za-z0-9._-]{1,80}",runtime.build_id) else "redacted"

    @site.middleware("http")
    async def health_diagnostics(request,call_next):
        route=request.url.path
        if request.method!="GET" or route not in {"/healthz","/__tcb_probe__"}:
            return await call_next(request)
        started=time.monotonic()
        logger.info("campus_health phase=received route=%s build=%s",route,build)
        status=500
        try:
            response=await call_next(request)
            status=response.status_code
            return response
        finally:
            elapsed=max(0,int((time.monotonic()-started)*1000))
            logger.info("campus_health phase=completed route=%s build=%s status=%d elapsed_ms=%d",
                        route,build,status,elapsed)


def create_cloud_identity_site(frontend_root=None,store=None,settings=None):
    runtime=settings or get_settings()
    if runtime.cloud_oauth_competition_compat_enabled and not runtime.cloud_oauth_pilot_enabled:
        raise ValueError("Competition compatibility requires explicit OAuth activation")
    if runtime.cloud_identity_bootstrap_enabled:
        if (runtime.cloud_identity_pilot_enabled or runtime.cloud_oauth_pilot_enabled
            or runtime.app_env not in {"test","staging"} or runtime.auth_mode!="demo_fixture"
            or runtime.allow_personal_uploads):
            raise ValueError("Bootstrap must not enable identity, OAuth or personal business")
        bootstrap=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
        @bootstrap.get("/__tcb_probe__")
        def bootstrap_probe(): return Response("ok",media_type="text/plain")
        @bootstrap.get("/healthz")
        def bootstrap_health():
            return JSONResponse({"status":"configuration_pending","build_id":runtime.build_id,
                "identity_enabled":False,"oauth_enabled":False,"personal_uploads":False,
                "database_connected":False},headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
        @bootstrap.api_route("/{path:path}",methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"])
        def bootstrap_closed(path:str):
            return JSONResponse({"error":"SERVICE_NOT_CONFIGURED"},status_code=503,
                headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})
        install_health_diagnostics(bootstrap,runtime)
        return bootstrap
    require_cloud_identity(runtime)
    root=frontend_root or Path(__file__).resolve().parents[2]/"frontend/dist"
    if not (root/"index.html").is_file():
        raise ValueError("Build the frontend before packaging")
    database=store or CloudIdentityStore(os.environ.get("CLOUDBASE_APIKEY") or os.environ.get("CLOUDBASE_API_KEY",""))

    @asynccontextmanager
    async def lifespan(_):
        result=database.call("probe",{})
        if result!={"schema_version":"identity-pilot-v1"}:
            raise ValueError("Unexpected database schema version")
        if runtime.cloud_oauth_competition_compat_enabled:
            if database.competition_call("probe",{})!={"schema_version":"competition-oauth-v1"}:
                raise ValueError("Competition OAuth migration required")
        subjects=["cloudbase_pilot_"+secret_hash(runtime.cloudbase_auth_env_id+":"+uid)
                  for uid in runtime.cloudbase_auth_pilot_user_ids]
        database.call("configure_subjects",{"subjects":subjects})
        try: yield
        finally: database.close()

    site=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    site.add_middleware(RequestBodyLimit)
    attempts=defaultdict(deque); lock=Lock()

    @site.middleware("http")
    async def request_context(request,call_next):
        request.state.request_id=resolve_request_id(request)
        if not runtime.cloud_identity_pilot_enabled:
            response=JSONResponse(failure(request_id=current_request_id(request),code="FORBIDDEN",message="Pilot disabled").model_dump(mode="json"),status_code=403)
        else:
            path=request.url.path
            family="login" if path=="/api/v1/auth/cloudbase/session" else "oauth" if path.startswith("/oauth/") else "business"
            if path.startswith(("/api/","/oauth/")):
                try:
                    peer=request.client.host if request.client else "unknown"
                    database.call("rate_limit",{"bucket_hash":secret_hash(peer+":"+family),
                        "limit":10 if family=="login" else 60 if family=="oauth" else 120})
                except AppError as exc:
                    response=JSONResponse(failure(request_id=current_request_id(request),code=exc.code,message=exc.message,
                        retryable=exc.retryable).model_dump(mode="json"),status_code=exc.status_code)
                else: response=await call_next(request)
            else: response=await call_next(request)
        # Preserve the mounted consent page's same-origin form policy. The
        # parent must not overwrite it with no-referrer (Origin: null on POST).
        consent_page = (request.method == "GET" and request.url.path == "/oauth/authorize"
                        and response.status_code == 200
                        and response.headers.get("Content-Type", "").startswith("text/html"))
        response.headers.update({"X-Request-ID":current_request_id(request),"X-Content-Type-Options":"nosniff",
            "Referrer-Policy":"same-origin" if consent_page else "no-referrer","Cache-Control":"no-store"})
        return response

    @site.exception_handler(AppError)
    async def app_error(request,exc):
        return JSONResponse(failure(request_id=current_request_id(request),code=exc.code,message=exc.message,
            retryable=exc.retryable).model_dump(mode="json"),status_code=exc.status_code)

    @site.exception_handler(RequestValidationError)
    async def validation_error(request,_):
        return await app_error(request,AppError(422,"VALIDATION_ERROR","Request does not match the interface contract"))

    @site.exception_handler(StarletteHTTPException)
    async def http_error(request,exc):
        return await app_error(request,AppError(exc.status_code,"NOT_FOUND" if exc.status_code==404 else "VALIDATION_ERROR","Request rejected"))

    @site.exception_handler(Exception)
    async def unexpected_error(request,_):
        return await app_error(request,AppError(500,"INTERNAL_ERROR","Internal server error",True))

    def origin(request):
        if request.headers.get("Origin","")!=runtime.app_origin:
            raise AppError(403,"FORBIDDEN","Same-origin browser required")

    def browser_args(request,write=False):
        token=request.cookies.get(SESSION_COOKIE,"")
        if not token: raise AppError(401,"AUTH_REQUIRED","Login required")
        given=request.headers.get("Origin","")
        if (write and given!=runtime.app_origin) or (given and given!=runtime.app_origin):
            raise AppError(403,"FORBIDDEN","Origin is not allowed")
        return {"session_hash":secret_hash(token),"csrf_hash":secret_hash(request.headers.get("X-CSRF-Token",""))}

    def reply(request,data,**kwargs):
        return success(format_times(data),request_id=current_request_id(request),data_version="demo-v1",**kwargs)

    def review(result):
        path="import" if result["kind"]=="schedule" else "tasks"
        return {**result,"review_url":runtime.app_origin+f"/tools/{path}?draft_id={result['draft_id']}"}

    def create_draft(args,kind,payload,key):
        require_idempotency_key(key)
        validate_boundary(payload,"TimetableImport" if kind=="schedule" else "NoticeDraft")
        digest=enforce_demo_fixture(payload,kind)
        return review(database.call("create_draft",{**args,"kind":kind,"key":key,
            "request_hash":payload_hash({"workspace_ref":args.get("workspace_ref"),"kind":kind,"payload":payload}),
            "payload_hash":digest,"draft_id":"draft_"+token_urlsafe(18)}))

    @site.get("/__tcb_probe__")
    def probe(): return Response("ok",media_type="text/plain")

    @site.get("/healthz")
    def health():
        if database.call("probe",{})!={"schema_version":"identity-pilot-v1"}:
            raise AppError(503,"DEPENDENCY_UNAVAILABLE","Identity storage unavailable",True)
        if runtime.cloud_oauth_competition_compat_enabled:
            if database.competition_call("probe",{})!={"schema_version":"competition-oauth-v1"}:
                raise AppError(503,"DEPENDENCY_UNAVAILABLE","Competition storage unavailable",True)
        return {"status":"ok","build_id":runtime.build_id,"dataset_kind":"demo","personal_uploads":False,
                "persistent_store":"cloudbase_pg","oauth_enabled":runtime.cloud_oauth_pilot_enabled,
                "oauth_competition_compat":runtime.cloud_oauth_competition_compat_enabled}

    @site.get("/api/v1/auth/cloudbase/config")
    def config(request:Request):
        return reply(request,{"env_id":runtime.cloudbase_auth_env_id,"region":"ap-shanghai","dataset_kind":"demo",
            "personal_uploads":False,"agent_paired":False})

    @site.post("/api/v1/auth/cloudbase/session")
    async def login(request:Request,response:Response):
        origin(request)
        now=time.monotonic(); peer=request.client.host if request.client else "unknown"
        with lock:
            for key in list(attempts):
                while attempts[key] and attempts[key][0]<now-60: attempts[key].popleft()
                if not attempts[key]: del attempts[key]
            if len(attempts)>=4096 or len(attempts[peer])>=10: raise AppError(429,"RATE_LIMITED","Too many login attempts",True)
            attempts[peer].append(now)
        subject=await verify_cloudbase_user(runtime,request.headers.get("Authorization",""))
        token,csrf=token_urlsafe(32),token_urlsafe(32)
        result=database.call("login",{"subject_id":subject,"token_hash":secret_hash(token),"csrf_hash":secret_hash(csrf),
            "workspace_ref":"pilot_workspace_"+token_urlsafe(18),"previous_session_hash":secret_hash(request.cookies.get(SESSION_COOKIE,""))})
        response.set_cookie(SESSION_COOKIE,token,max_age=900,httponly=True,secure=True,samesite="strict",path="/")
        response.set_cookie(CONTEXT_COOKIE,encode_context(token,result["workspace_ref"],csrf,result["expires_epoch"]),
            max_age=900,httponly=True,secure=True,samesite="strict",path="/")
        return reply(request,{**result,"csrf_token":csrf,"dataset_kind":"demo","identity_verified_by":"cloudbase_user_me",
                              "personal_uploads":False,"agent_paired":False})

    @site.get("/api/v1/auth/cloudbase/browser-session")
    async def browser_session(request:Request):
        # Browser same-origin fetch may omit Origin (and Referrer-Policy is
        # no-referrer). Require a non-simple custom header and reject explicit
        # foreign Origin/Fetch Metadata; no CORS is enabled on this service.
        if (request.headers.get("X-Campus-Session-Read")!="1"
            or request.headers.get("Sec-Fetch-Site","same-origin")!="same-origin"):
            raise AppError(403,"FORBIDDEN","Same-origin session read required")
        if request.query_params or request.headers.get("Content-Length","0")!="0":
            raise AppError(422,"VALIDATION_ERROR","Session read accepts no owner or token parameters")
        # GET has no body. Do not buffer an arbitrarily large/chunked body;
        # reject at the first nonempty ASGI chunk before inspecting any cookie.
        async for chunk in request.stream():
            if chunk:
                raise AppError(422,"VALIDATION_ERROR","Session read accepts no request body")
        args=browser_args(request)
        context=decode_context(request.cookies.get(SESSION_COOKIE,""),request.cookies.get(CONTEXT_COOKIE,""))
        workspace=database.call("get_workspace",args)
        if workspace.get("workspace_ref")!=context["workspace_ref"]:
            raise AppError(401,"AUTH_REQUIRED","Browser session context does not match the verified owner")
        result={**context,"dataset_kind":"demo","personal_uploads":False,"agent_paired":False}
        validate_boundary(format_times(result),"CloudBrowserSession")
        return reply(request,result)

    @site.post("/api/v1/auth/cloudbase/logout")
    def logout(request:Request,response:Response):
        result=database.call("logout",browser_args(request,True))
        response.delete_cookie(SESSION_COOKIE,path="/",httponly=True,secure=True,samesite="strict")
        response.delete_cookie(CONTEXT_COOKIE,path="/",httponly=True,secure=True,samesite="strict")
        return reply(request,result)

    @site.post("/api/v1/demo/workspaces")
    def no_anonymous_workspaces():
        raise AppError(401,"AUTH_REQUIRED","Use the approved ordinary user login; anonymous workspaces are disabled")

    @site.post("/api/v1/tasks/drafts")
    def task_draft(payload:TaskDraftRequest,request:Request,key:Annotated[str,Header(alias="Idempotency-Key")]):
        return reply(request,create_draft({**browser_args(request,True),"workspace_ref":payload.workspace_ref},"task",payload.notice,key))

    @site.post("/api/v1/schedules/import-drafts")
    def import_draft(request:Request,payload:Annotated[dict[str,Any],Body()],key:Annotated[str,Header(alias="Idempotency-Key")],
                     authorization:Annotated[str|None,Header(alias="Authorization")]=None):
        if authorization:
            if not authorization.startswith("ImportTicket ") or len(authorization)>256:
                raise AppError(401,"AUTH_REQUIRED","Invalid import ticket")
            args={"principal_kind":"import_ticket","ticket_hash":secret_hash(authorization.removeprefix("ImportTicket "))}
        else:
            args=browser_args(request,True)
            args.update(database.call("get_workspace",args))
        return reply(request,create_draft(args,"schedule",payload,key))

    @site.post("/api/v1/import-tickets")
    def issue_ticket(payload:CreateImportTicketRequest,request:Request,key:Annotated[str,Header(alias="Idempotency-Key")]):
        require_idempotency_key(key)
        raw=token_urlsafe(32)
        ticket_id="ticket_"+token_urlsafe(18)
        result=database.call("import_ticket",{**browser_args(request,True),**payload.model_dump(),"key":key,
            "request_hash":payload_hash(payload.model_dump()),"ticket_hash":secret_hash(raw),"ticket_id":ticket_id})
        # Unlike ordinary write retry, a token-issuance retry cannot reconstruct
        # the original plaintext token. Fail rather than return a new invalid token.
        if result.pop("ticket_id")!=ticket_id:
            raise AppError(409,"STALE_REVISION","Ticket issuance already completed; use a new issuance key")
        return reply(request,{**result,"import_ticket":raw})

    @site.get("/api/v1/drafts/{draft_id}")
    def draft(request:Request,draft_id:str):
        return reply(request,review(database.call("get_draft",{**browser_args(request),"draft_id":draft_id})))

    @site.post("/api/v1/confirmations")
    def confirm(payload:ConfirmationRequest,request:Request,key:Annotated[str,Header(alias="Idempotency-Key")]):
        require_idempotency_key(key)
        raw="confirmation_"+token_urlsafe(18)
        return reply(request,database.call("confirm",{**browser_args(request,True),**payload.model_dump(),"key":key,
            "request_hash":payload_hash(payload.model_dump()),"confirmation_id":raw,"confirmation_hash":secret_hash(raw)}))

    def save(request,payload,kind):
        require_idempotency_key(payload.idempotency_key)
        return reply(request,database.call("commit",{**browser_args(request,True),"kind":kind,"key":payload.idempotency_key,
            "request_hash":payload_hash({"kind":kind,"confirmation_id":payload.confirmation_id}),
            "confirmation_hash":secret_hash(payload.confirmation_id),"resource_id":kind+"_"+token_urlsafe(18)}))

    @site.post("/api/v1/tasks/commit")
    def save_task(payload:CommitRequest,request:Request): return save(request,payload,"task")

    @site.post("/api/v1/schedules/commit")
    def save_schedule(payload:CommitRequest,request:Request): return save(request,payload,"schedule")

    @site.get("/api/v1/tasks")
    def tasks(request:Request,workspace_ref:Annotated[str,Query(min_length=1,max_length=128)]):
        return reply(request,database.call("list_tasks",{**browser_args(request),"workspace_ref":workspace_ref}))

    @site.get("/api/v1/tasks/{task_id}")
    def task(request:Request,task_id:str):
        return reply(request,database.call("get_task",{**browser_args(request),"task_id":task_id}))

    @site.get("/api/v1/schedules/current")
    def current(request:Request,workspace_ref:Annotated[str,Query(min_length=1,max_length=128)]):
        return reply(request,database.call("current_schedule",{**browser_args(request),"workspace_ref":workspace_ref}))

    @site.post("/api/v1/schedules/validate")
    def validate(request:Request,payload:Annotated[Any,Body()]):
        validate_boundary(payload,"TimetableImport"); enforce_demo_fixture(payload,"schedule")
        return reply(request,schedule.validate_timetable(payload))

    @site.post("/api/v1/degree/audit")
    def degree(request:Request,payload:Annotated[Any,Body()]):
        # C's existing algorithm and public fictional references only. Never
        # resolve a PG owner's grades through this public demonstration path.
        validate_boundary(payload,"DegreeAuditRequest")
        if payload["workspace_ref"]!="demo-workspace-01":
            raise AppError(403,"DEMO_ONLY","Only the fixed public degree demonstration is available")
        return execute_domain("audit_degree_progress",payload,public_principal(),runtime,current_request_id(request))

    def time_query(request,payload,operation):
        validate_boundary(payload,"FreeTimeQuery" if operation=="free" else "TimeCheckRequest")
        records=database.call("records",{**browser_args(request),"workspace_ref":payload["workspace_ref"]})
        result,warnings=calculate_owned_time(records,payload,operation)
        return reply(request,result,calculation_version=schedule.CALCULATION_VERSION,warnings=[WarningItem(**warning) for warning in warnings])

    @site.post("/api/v1/time/free-slots")
    def free(request:Request,payload:Annotated[Any,Body()]): return time_query(request,payload,"free")

    @site.post("/api/v1/time/check")
    def check(request:Request,payload:Annotated[Any,Body()]): return time_query(request,payload,"check")

    if runtime.cloud_oauth_pilot_enabled:
        from app.core.cloud_oauth_provider import CloudOAuthProvider
        from app.oauth_pilot_site import create_oauth_adapter
        provider_class=CloudOAuthProvider
        if runtime.cloud_oauth_competition_compat_enabled:
            from app.core.competition_oauth_provider import CompetitionOAuthProvider
            provider_class=CompetitionOAuthProvider
        site.mount("/oauth",create_oauth_adapter(runtime,provider_class(runtime,database)))

    site.mount("/assets",StaticFiles(directory=root/"assets"),name="assets")
    @site.get("/")
    def home(): return RedirectResponse("/tools/login")
    @site.get("/tools/{tool}")
    def tool_page(tool:str):
        if tool not in {"login","tasks","import","timetable","affairs","degree"}: raise AppError(404,"NOT_FOUND","Use the existing published public content service")
        return FileResponse(root/"index.html",headers={"Cache-Control":"no-store"})
    install_health_diagnostics(site,runtime)
    return site

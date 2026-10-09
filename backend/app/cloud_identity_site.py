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
from datetime import datetime, timedelta, timezone
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
from app.core.persistent_auth import COOKIE_MAX_AGE, UNTIL_REVOKED_EPOCH
from app.core.config import get_settings
from app.core.contracts import validate_boundary
from app.core.demo import FIXTURE_SET_ID,enforce_demo_fixture
from app.core.envelope import FieldError,WarningItem,failure,success
from app.core.errors import AppError
from app.core.owned_time import calculate_owned_time
from app.core.request_id import current_request_id,resolve_request_id
from app.core.security import SESSION_COOKIE,payload_hash,require_idempotency_key,secret_hash
from app.domains.schedule import service as schedule
from app.core.domain_adapter import execute_domain,public_principal
from app.device_login_site import install_device_login


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
            epoch=result.pop(source)
            # Windows CRT cannot fromtimestamp() year 9999; use UTC arithmetic.
            result[dest]=(datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(seconds=epoch)).astimezone(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
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
    if runtime.cloud_agent_device_binding_enabled and not (runtime.cloud_persistent_auth_enabled and runtime.cloud_oauth_competition_compat_enabled):
        raise ValueError("Agent device binding requires explicit persistent own-account OAuth")
    if runtime.cloud_persistent_auth_enabled and not (runtime.cloud_personal_tasks_enabled and runtime.cloud_oauth_competition_compat_enabled):
        raise ValueError("Persistent access requires the explicitly scoped own-calendar configuration")
    if runtime.cloud_personal_tasks_enabled and not (runtime.cloud_task_calendar_enabled and runtime.cloud_oauth_competition_compat_enabled):
        raise ValueError("Own task recording requires calendar and explicitly scoped competition OAuth")
    if runtime.cloud_task_calendar_enabled and not runtime.cloud_notice_text_pilot_enabled:
        raise ValueError("Calendar requires the explicitly enabled notice backend")
    if runtime.cloud_oauth_competition_compat_enabled and not runtime.cloud_oauth_pilot_enabled:
        raise ValueError("Competition compatibility requires explicit OAuth activation")
    if runtime.cloud_identity_bootstrap_enabled:
        if (runtime.cloud_identity_pilot_enabled or runtime.cloud_oauth_pilot_enabled or runtime.cloud_notice_text_pilot_enabled or runtime.cloud_task_calendar_enabled or runtime.cloud_personal_tasks_enabled
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
        if runtime.cloud_persistent_auth_enabled and database.call("persistent_probe",{})!={"schema_version":"persistent-auth-v1"}:
            raise ValueError("Persistent authorization migration required")
        if runtime.cloud_personal_schedules_enabled and database.call("personal_schedule_probe",{})!={"schema_version":"personal-schedules-v1"}:
            raise ValueError("Personal timetable migration required")
        if runtime.cloud_device_login_enabled and database.device_call("probe",{})!={"schema_version":"browser-device-v1"}:
            raise ValueError("Device binding migration required")
        if runtime.cloud_agent_device_binding_enabled and database.agent_device_call("probe",{})!={"schema_version":"agent-device-v1"}:
            raise ValueError("Agent device binding migration required")
        if runtime.cloud_oauth_competition_compat_enabled:
            if database.competition_call("probe",{})!={"schema_version":"competition-oauth-v1"}:
                raise ValueError("Competition OAuth migration required")
        if runtime.cloud_notice_text_pilot_enabled:
            if database.notice_call("probe", {}) != {"schema_version": "notice-text-v1"}:
                raise ValueError("Notice text migration required")
        if runtime.cloud_task_calendar_enabled:
            if database.calendar_call("probe", {}) != {"schema_version": "task-calendar-v1"}:
                raise ValueError("Calendar migration required")
        if runtime.cloud_personal_tasks_enabled:
            if database.personal_call("probe", {}) != {"schema_version": "personal-tasks-v1"}:
                raise ValueError("Own task recording migration required")
        subjects=["cloudbase_pilot_"+secret_hash(runtime.cloudbase_auth_env_id+":"+uid)
                  for uid in runtime.cloudbase_auth_pilot_user_ids]
        database.call("configure_subjects",{"subjects":subjects})
        try: yield
        finally: database.close()

    site=FastAPI(lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    site.add_middleware(RequestBodyLimit, notice_text_enabled=runtime.cloud_notice_text_pilot_enabled,
                        personal_schedules_enabled=runtime.cloud_personal_schedules_enabled)
    attempts=defaultdict(deque); lock=Lock()

    @site.middleware("http")
    async def request_context(request,call_next):
        request.state.request_id=resolve_request_id(request)
        if not runtime.cloud_identity_pilot_enabled:
            response=JSONResponse(failure(request_id=current_request_id(request),code="FORBIDDEN",message="Pilot disabled").model_dump(mode="json"),status_code=403)
        else:
            path=request.url.path
            family="device_init" if path=="/api/v1/auth/agent-device/start" else "login" if path=="/api/v1/auth/cloudbase/session" else "oauth" if path.startswith("/oauth/") else "business"
            if path.startswith(("/api/","/oauth/")):
                try:
                    peer=request.client.host if request.client else "unknown"
                    database.call("rate_limit",{"bucket_hash":secret_hash(peer+":"+family),
                        "limit":10 if family in {"login","device_init"} else 60 if family=="oauth" else 120})
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
        # Preserve actionable time-field locations without echoing private
        # inputs, parser exceptions, or arbitrary database error details.
        messages = {"datetime_format": "时间须包含完整日期、时刻与时区；日末24:00表示次日00:00",
            "invalid_field": "字段类型或结构不符合接口；notes须为字符串，无备注用空字符串"}
        time_fields = [FieldError(field=e.field, code=e.code, message=messages[e.code])
            for e in exc.field_errors if e.code in messages and
            re.fullmatch(r"content\.(?:title|kind|due_at|due_date|reminder_at|notes|reminder_minutes|scheduled_slots(?:\.[0-7](?:\.(?:start|end))?)?)", e.field)]
        return JSONResponse(failure(request_id=current_request_id(request),code=exc.code,message=exc.message,
            field_errors=time_fields,retryable=exc.retryable).model_dump(mode="json"),status_code=exc.status_code)

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

    install_device_login(site,runtime,database,browser_args)
    from app.agent_device_site import install_agent_device, RETURNS, binding_url, valid_destination, device_status
    install_agent_device(site,runtime,database)

    def review(result):
        path="import" if result["kind"]=="schedule" else "tasks"
        return {**result,"review_url":runtime.app_origin+f"/tools/{path}?draft_id={result['draft_id']}"}

    def create_draft(args,kind,payload,key):
        require_idempotency_key(key)
        validate_boundary(payload,"TimetableImport" if kind=="schedule" else "NoticeDraft")
        personal_schedule = kind=="schedule" and runtime.cloud_personal_schedules_enabled
        if personal_schedule:
            checked=schedule.validate_timetable(payload)
            payload=checked["normalized_payload"]
            if payload["dataset_kind"]=="personal" and payload["term"]["calendar_status"] not in {"user_confirmed","official_verified"}:
                raise AppError(422,"VALIDATION_ERROR","请先核对本人课表的学期校历，不能套用演示校历")
            if len(payload["courses"])>300 or len(str(payload).encode())>900000:
                raise AppError(422,"VALIDATION_ERROR","课表过大，请缩小导入范围")
            digest=payload_hash(payload)
        else:
            digest=enforce_demo_fixture(payload,kind)
        return review(database.call("create_draft",{**args,"kind":kind,"key":key,
            "request_hash":payload_hash({"workspace_ref":args.get("workspace_ref"),"kind":kind,"payload":payload}),
            "payload_hash":digest,"draft_id":"draft_"+token_urlsafe(18),
            **({"payload":payload} if personal_schedule else {})}))

    @site.get("/__tcb_probe__")
    def probe(): return Response("ok",media_type="text/plain")

    @site.get("/healthz")
    def health():
        if database.call("probe",{})!={"schema_version":"identity-pilot-v1"}:
            raise AppError(503,"DEPENDENCY_UNAVAILABLE","Identity storage unavailable",True)
        if runtime.cloud_device_login_enabled and database.device_call("probe",{})!={"schema_version":"browser-device-v1"}:
            raise AppError(503,"DEPENDENCY_UNAVAILABLE","Device binding storage unavailable",True)
        if runtime.cloud_agent_device_binding_enabled and database.agent_device_call("probe",{})!={"schema_version":"agent-device-v1"}:
            raise AppError(503,"DEPENDENCY_UNAVAILABLE","Agent device binding storage unavailable",True)
        if runtime.cloud_oauth_competition_compat_enabled:
            if database.competition_call("probe",{})!={"schema_version":"competition-oauth-v1"}:
                raise AppError(503,"DEPENDENCY_UNAVAILABLE","Competition storage unavailable",True)
        if runtime.cloud_notice_text_pilot_enabled:
            if database.notice_call("probe", {}) != {"schema_version": "notice-text-v1"}:
                raise AppError(503,"DEPENDENCY_UNAVAILABLE","Notice storage unavailable",True)
        if runtime.cloud_task_calendar_enabled:
            if database.calendar_call("probe", {}) != {"schema_version": "task-calendar-v1"}:
                raise AppError(503,"DEPENDENCY_UNAVAILABLE","Calendar storage unavailable",True)
        if runtime.cloud_personal_tasks_enabled:
            if database.personal_call("probe", {}) != {"schema_version": "personal-tasks-v1"}:
                raise AppError(503,"DEPENDENCY_UNAVAILABLE","Own task storage unavailable",True)
        return {"status":"ok","build_id":runtime.build_id,"dataset_kind":"demo","personal_uploads":False,
                "persistent_store":"cloudbase_pg","oauth_enabled":runtime.cloud_oauth_pilot_enabled,
                "oauth_competition_compat":runtime.cloud_oauth_competition_compat_enabled,
                "own_task_recording":runtime.cloud_personal_tasks_enabled,
                "persistent_authorization":runtime.cloud_persistent_auth_enabled,
                "device_login_enabled":runtime.cloud_device_login_enabled,
                "agent_device_binding_enabled":runtime.cloud_agent_device_binding_enabled}

    @site.get("/api/v1/auth/cloudbase/config")
    def config(request:Request):
        return reply(request,{"env_id":runtime.cloudbase_auth_env_id,"region":"ap-shanghai","dataset_kind":"demo",
            "personal_uploads":False,"agent_paired":False,"persistent_authorization":runtime.cloud_persistent_auth_enabled,
            "device_login_enabled":runtime.cloud_device_login_enabled,
            "agent_device_binding_enabled":runtime.cloud_agent_device_binding_enabled})

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
            "workspace_ref":"pilot_workspace_"+token_urlsafe(18),"previous_session_hash":secret_hash(request.cookies.get(SESSION_COOKIE,"")),
            **({"persistent":True} if runtime.cloud_persistent_auth_enabled else {})})
        if runtime.cloud_persistent_auth_enabled and result["expires_epoch"] != UNTIL_REVOKED_EPOCH:
            raise AppError(503,"DEPENDENCY_UNAVAILABLE","Persistent authorization migration required",True)
        cookie_age=COOKIE_MAX_AGE if runtime.cloud_persistent_auth_enabled else 900
        response.set_cookie(SESSION_COOKIE,token,max_age=cookie_age,httponly=True,secure=True,samesite="strict",path="/")
        response.set_cookie(CONTEXT_COOKIE,encode_context(token,result["workspace_ref"],csrf,result["expires_epoch"]),
            max_age=cookie_age,httponly=True,secure=True,samesite="strict",path="/")
        return reply(request,{**result,"csrf_token":csrf,"dataset_kind":"demo","identity_verified_by":"cloudbase_user_me",
                              "personal_uploads":False,"agent_paired":False})

    @site.get("/api/v1/auth/cloudbase/browser-session")
    async def browser_session(request:Request,response:Response):
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
        context=decode_context(request.cookies.get(SESSION_COOKIE,""),request.cookies.get(CONTEXT_COOKIE,""),
                               persistent=runtime.cloud_persistent_auth_enabled)
        workspace=database.call("get_workspace",args)
        if workspace.get("workspace_ref")!=context["workspace_ref"]:
            raise AppError(401,"AUTH_REQUIRED","Browser session context does not match the verified owner")
        if runtime.cloud_agent_device_binding_enabled and device_status(request,database)["status"] != "bound":
            raise AppError(401,"AUTH_REQUIRED","Bind this browser to the Agent authorized account first")
        result={**context,"dataset_kind":"demo","personal_uploads":False,"agent_paired":False}
        validate_boundary(format_times(result),"CloudBrowserSession")
        if runtime.cloud_persistent_auth_enabled and context["expires_epoch"] == UNTIL_REVOKED_EPOCH:
            # Reissue only after the DB validates the original session/owner.
            for name in (SESSION_COOKIE, CONTEXT_COOKIE):
                response.set_cookie(name,request.cookies[name],max_age=COOKIE_MAX_AGE,
                                    httponly=True,secure=True,samesite="strict",path="/")
            if runtime.cloud_agent_device_binding_enabled:
                from app.agent_device_site import COOKIE
                response.set_cookie(COOKIE,request.cookies[COOKIE],max_age=COOKIE_MAX_AGE,
                                    httponly=True,secure=True,samesite="strict",path="/")
        return reply(request,result)

    @site.post("/api/v1/auth/cloudbase/logout")
    def logout(request:Request,response:Response):
        auth=browser_args(request,True)
        if runtime.cloud_agent_device_binding_enabled:
            from app.agent_device_site import COOKIE
            from app.device_login_site import SECRET
            device_secret=request.cookies.get(COOKIE,"")
            if SECRET.fullmatch(device_secret):
                database.agent_device_call("detach",{**auth,"challenge_hash":secret_hash(device_secret)})
        result=database.call("logout",auth)
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

    if runtime.cloud_task_calendar_enabled:
        from app.api.task_calendar import install_calendar_routes
        install_calendar_routes(site,runtime,database,browser_args,format_times)
    if runtime.cloud_personal_tasks_enabled:
        from app.api.personal_tasks import install_personal_routes
        install_personal_routes(site,runtime,database,browser_args,format_times)

    @site.get("/api/v1/tasks/{task_id}")
    def task(request:Request,task_id:str):
        return reply(request,database.call("get_task",{**browser_args(request),"task_id":task_id}))

    @site.get("/api/v1/schedules/current")
    def current(request:Request,workspace_ref:Annotated[str,Query(min_length=1,max_length=128)]):
        return reply(request,database.call("current_schedule",{**browser_args(request),"workspace_ref":workspace_ref}))

    @site.post("/api/v1/schedules/validate")
    def validate(request:Request,payload:Annotated[Any,Body()]):
        validate_boundary(payload,"TimetableImport")
        if runtime.cloud_personal_schedules_enabled:
            database.call("get_workspace",browser_args(request,True))
        else:
            enforce_demo_fixture(payload,"schedule")
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
        if runtime.cloud_notice_text_pilot_enabled:
            records=database.notice_call("records",{"principal_kind":"browser",**browser_args(request)})
            if records["workspace_ref"] != payload["workspace_ref"]:
                raise AppError(404,"NOT_FOUND","Workspace not found")
        else:
            records=database.call("records",{**browser_args(request),"workspace_ref":payload["workspace_ref"]})
        if runtime.cloud_personal_tasks_enabled:
            from app.core.personal_tasks import PersonalTaskService
            records={**records,"tasks":records["tasks"]+PersonalTaskService(runtime,database).records({"principal_kind":"browser",**browser_args(request)})}
        result,warnings=calculate_owned_time(records,payload,operation,allow_notice_text=runtime.cloud_notice_text_pilot_enabled)
        return reply(request,result,calculation_version=schedule.CALCULATION_VERSION,warnings=[WarningItem(**warning) for warning in warnings])

    @site.post("/api/v1/time/free-slots")
    def free(request:Request,payload:Annotated[Any,Body()]): return time_query(request,payload,"free")

    @site.post("/api/v1/time/check")
    def check(request:Request,payload:Annotated[Any,Body()]): return time_query(request,payload,"check")

    if runtime.cloud_notice_text_pilot_enabled:
        from app.api.cloud_notice_text import install_notice_routes
        install_notice_routes(site,runtime,database,browser_args,format_times)

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
    def home(): return RedirectResponse(binding_url("/tools/timetable") if runtime.cloud_agent_device_binding_enabled else "/tools/login")
    @site.get("/tools/{tool}")
    def tool_page(tool:str,request:Request):
        if tool not in {"login","tasks","import","timetable","affairs","degree","calendar"}: raise AppError(404,"NOT_FOUND","Use the existing published public content service")
        if runtime.cloud_agent_device_binding_enabled and request.url.path in RETURNS:
            try:
                database.call("get_workspace",{"session_hash":browser_args(request)["session_hash"]})
                if device_status(request,database)["status"] != "bound": raise AppError(401,"AUTH_REQUIRED","Bind this browser to the Agent account first")
            except AppError as exc:
                if exc.code not in {"AUTH_REQUIRED","TOKEN_EXPIRED"}: raise
                destination=request.url.path + ("?"+request.url.query if request.url.query else "")
                if not valid_destination(destination): raise AppError(422,"VALIDATION_ERROR","Unsupported tool return parameters")
                return RedirectResponse(binding_url(destination),status_code=303)
        return FileResponse(root/"index.html",headers={"Cache-Control":"no-store"})
    install_health_diagnostics(site,runtime)
    return site

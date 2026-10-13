"""Opt-in loopback OAuth adapter, separate from public REST/MCP deployment."""
import base64
import binascii
import html
import json
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from threading import Lock
from urllib.parse import parse_qsl, unquote_plus
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core import agent_pairing_local as pairing, oauth_local as oauth
from app.core.config import Settings
from app.core.envelope import WarningItem, failure, success
from app.core.errors import AppError


def create_oauth_pilot(settings: Settings) -> FastAPI:
    return create_oauth_adapter(settings, LocalOAuthProvider(settings))


class LocalOAuthProvider:
    def __init__(self, settings):
        self.settings = settings
    def gate(self): return oauth.gate(self.settings)
    def initialize(self): return oauth.initialize(self.settings)
    def authenticate(self, client_id, secret): return oauth.authenticate(self.settings, client_id, secret)
    def begin(self, request, params): return oauth.begin(request, self.settings, params)
    def approve(self, request, transaction, decision): return oauth.approve(request, self.settings, transaction, decision)
    def exchange(self, params): return oauth.exchange(self.settings, params)
    def revoke(self, token): return oauth.revoke(self.settings, token)
    def records(self, request):
        return pairing.read_paired_records(self.settings, oauth.integration(self.settings), oauth.resource_token(request))
    def draft(self, request, notice, key):
        return pairing.create_paired_task_draft(self.settings, oauth.integration(self.settings), oauth.resource_token(request), notice, key)


def create_oauth_adapter(settings: Settings, provider) -> FastAPI:
    provider.gate()

    @asynccontextmanager
    async def lifespan(_):
        provider.initialize()
        yield

    site = FastAPI(title="Closed OAuth pilot", lifespan=lifespan,
                   docs_url=None, redoc_url=None, openapi_url=None)
    attempts = defaultdict(deque)
    lock = Lock()

    @site.middleware("http")
    async def secure_response(request: Request, call_next):
        # Single-process loopback test only; a cloud deployment needs a shared
        # limiter and durable transactions. Do not log URL/body/auth headers.
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with lock:
            for peer in list(attempts):
                while attempts[peer] and attempts[peer][0] < now - 60:
                    attempts[peer].popleft()
                if not attempts[peer]:
                    del attempts[peer]
            limited = len(attempts) >= 4096 or len(attempts[key]) >= 60
            if not limited:
                attempts[key].append(now)
        if limited:
            response = JSONResponse({"error": "temporarily_unavailable"}, status_code=429)
        else:
            try:
                provider.gate()  # Recheck kill switch for every resource call.
            except (oauth.OAuthError, AppError):
                response = JSONResponse({"error": "temporarily_unavailable"}, status_code=503)
            else:
                response = await call_next(request)
        # A navigation form POST under no-referrer can send Origin: null.
        # The consent endpoint must retain its exact-origin check. Allow only
        # same-origin referrers on this HTML page; cross-origin callbacks still
        # receive no Referer, and all token/resource responses remain no-referrer.
        consent_page = (request.method == "GET" and request.url.path.endswith("/authorize")
                        and response.status_code == 200
                        and response.headers.get("Content-Type", "").startswith("text/html"))
        # Chromium may apply form-action to the POST's redirect as well as
        # its initial target. This is the provider-gated, exact callback,
        # never a request-supplied redirect or an origin-wide allowlist.
        form_action = "'self'" + (" " + settings.oauth_redirect_uri
                                 if consent_page else "")
        response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache",
            "Referrer-Policy": "same-origin" if consent_page else "no-referrer", "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action " + form_action + "; frame-ancestors 'none'; base-uri 'none'"})
        return response

    @site.exception_handler(oauth.OAuthError)
    async def protocol_error(_, exc):
        headers = {"WWW-Authenticate": 'Basic realm="oauth-pilot"'} if exc.error == "invalid_client" else {}
        if exc.error == "invalid_token" and exc.status == 401:
            # RFC 6750 section 3.1: give OAuth clients an explicit invalid-token
            # challenge after logout/revoke/reset, rather than a generic
            # business error that leaves their cached token looking usable.
            headers = {"WWW-Authenticate": 'Bearer realm="campus-oauth", error="invalid_token"'}
        return JSONResponse({"error": exc.error}, status_code=exc.status, headers=headers)

    @site.exception_handler(AppError)
    async def business_error(_, exc):
        return JSONResponse(failure(request_id=str(uuid4()), code=exc.code,
            message=exc.message).model_dump(mode="json"), status_code=exc.status_code)

    @site.exception_handler(Exception)
    async def unexpected_error(_, exc):
        # Sanitized boundary: do not stringify credentials, request or exception.
        return JSONResponse({"error": "server_error"}, status_code=500)

    def pairs(items, device_binding=False):
        result = {}
        for key, value in items:
            if key in result:
                raise oauth.OAuthError()
            if device_binding and key == "confirm_binding" and type(value) is bool:
                result[key] = value
                continue
            if not isinstance(value, str) or len(value) > (16384 if settings.cloud_personal_tasks_enabled and key == "query_json" else 2048):
                raise oauth.OAuthError()
            result[key] = value
        return result

    async def body(request):
        raw = bytearray()
        notice_input = settings.cloud_notice_text_pilot_enabled and request.url.path in {"/oauth/notice/read", "/oauth/notice/check"}
        own_task_input = settings.cloud_personal_tasks_enabled and request.url.path in {
            "/oauth/tasks/entries/drafts", "/oauth/tasks/entries/commit"}
        limit = 262144 if notice_input else 32768 if own_task_input else 8192
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > limit:
                raise oauth.OAuthError()
        content_type = request.headers.get("Content-Type", "").split(";", 1)[0]
        try:
            if content_type == "application/json":
                # Preserve pairs to reject duplicate JSON keys.
                value = json.loads(raw, object_pairs_hook=lambda items: pairs(items,
                    settings.cloud_agent_device_binding_enabled and request.url.path == "/oauth/devices/bind"))
                if not isinstance(value, dict):
                    raise oauth.OAuthError()
                return value
            if content_type == "application/x-www-form-urlencoded":
                return pairs(parse_qsl(raw.decode("utf-8"), keep_blank_values=True,
                                       strict_parsing=True, max_num_fields=16))
        except (ValueError, UnicodeError):
            raise oauth.OAuthError() from None
        raise oauth.OAuthError()

    def client_auth(request, params):
        def reject(reason):
            logging.getLogger("uvicorn.error").info("campus_oauth_client rejection=%s",reason)
            raise oauth.OAuthError("invalid_client",401)
        auth = request.headers.get("Authorization", "")
        if len(auth) > 2048:
            reject("header_length")
        if auth:
            if "client_id" in params or "client_secret" in params:
                reject("multiple_methods")
            if not auth.startswith("Basic "):
                reject("header_scheme")
            try:
                raw = base64.b64decode(auth[6:], validate=True).decode("ascii")
                client_id, secret = raw.split(":", 1)
                client_id, secret = unquote_plus(client_id), unquote_plus(secret)
            except (ValueError, UnicodeError, binascii.Error):
                reject("header_format")
        else:
            client_id, secret = params.pop("client_id", ""), params.pop("client_secret", "")
        provider.authenticate(client_id, secret)

    @site.get("/authorize")
    def authorize(request: Request):
        params = pairs(request.query_params.multi_items())
        try:
            transaction, scopes = provider.begin(request, params)
        except AppError as exc:
            if exc.code != "AUTH_REQUIRED":
                raise
            login_url = getattr(provider, "login_url", None)
            if login_url is not None:
                return RedirectResponse(login_url(params), status_code=303)
            return HTMLResponse('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>先登录</title>'
                '<h1>请先登录校园助手测试账号</h1><p>仅联调虚构数据，不接真实成绩。</p>'
                '<a href="/tools/login">前往登录</a><p>登录完成后回到本页并刷新，才能继续授权。</p></html>', status_code=401)
        label = ("读取自己已保存的课表与待办" if settings.cloud_personal_schedules_enabled else "读取自己的虚构课表与待办") + ("；创建待办草稿" if "demo:draft" in scopes else "")
        personal = "tasks:read" in scopes
        if personal:
            label += "；读取自己已记录的事项、截止、备注和选定时段"
        if "tasks:write" in scopes:
            label += "；仅在你核对草稿并明确确认后记录本人待办"
        if "degree:read" in scopes:
            label += "；读取本人已确认保存的培养计划总览、分类学分及状态（不含课程成绩）"
        if "devices:bind" in scopes:
            label += "；仅当你明确发送本人浏览器的固定设备码并确认绑定时，允许该浏览器访问这个授权账号的课表与日历"
        mode_note = ('<p>参赛联调兼容模式：普通 OAuth 授权码，无 PKCE；仅两个已批准测试账号。真实教务课表和成绩上传仍未开放。</p>'
                     if settings.cloud_oauth_competition_compat_enabled else '')
        if settings.cloud_personal_schedules_enabled:
            mode_note = '<p>仅访问当前工具站身份自己的数据。课表须由本人导入并确认；不是自动识别学校账号，不代替教务登录，不接收成绩上传。</p>'
        if settings.cloud_visitor_enabled:
            mode_note += '<p>当前可用独立浏览器访客身份。允许后，Agent 关联的是这个浏览器已登录的私有空间，不是学校学号。不要在公共电脑授权。</p>'
        if "degree:read" in scopes:
            mode_note += '<p>新增 degree:read 只读权限：仅本人确认保存的分类学分报告，不含课程成绩、姓名学号；不自动登录教务、不替你上传或作毕业审核。原授权不会自动升级。</p>'
        if "degree:write" in scopes:
            mode_note += '<p>新增 degree:write：Agent 可核对你上传的分类学分 JSON，在你明确确认该草稿后保存到本人原空间。更新会替换旧学分报告，不动课表和日历；不含课程成绩、姓名学号。原授权不会自动升级。</p>'
        return HTMLResponse('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>授权校园助手</title>'
            '<style>body{max-width:640px;margin:8vh auto;padding:24px;font:20px/1.8 sans-serif;color:#274535;background:#fffdf6}'
            'button{padding:14px 24px;margin:16px 12px 0 0;font:inherit}</style>'
            '<h1>授权校园助手测试插件</h1><p>' + html.escape(label) + '</p>'
            + mode_note +
            ('<p>仅本人分类学分，退出、撤销或身份不一致即失效。</p>' if "degree:read" in scopes else '') +
            ('<p>不能查看其他账号，不自行确认或自动保存。不会代替你登录教务或上传成绩。本人长期授权；退出、撤销或移出名单即失效。</p>' if (personal or "devices:bind" in scopes or "degree:read" in scopes) and settings.cloud_persistent_auth_enabled else
             '<p>不能查看其他账号、不代确认、不自动保存。授权最多 10 分钟，退出登录即失效。</p>' if "degree:read" in scopes else
             '<p>不能查看其他账号，不自行确认或自动保存，不接入真实教务与成绩。授权最多 10 分钟，退出登录即失效。</p>' if personal else
             '<p>不能查看其他账号、不能替你确认或保存、不能接入真实个人数据。授权最多 10 分钟，退出登录即失效。</p>') +
            '<form method="post" action="/oauth/approve"><input type="hidden" name="transaction" value="' +
            html.escape(transaction, quote=True) + '"><button name="decision" value="allow">允许本次授权</button>'
            '<button name="decision" value="deny">拒绝</button></form></html>')

    @site.post("/approve")
    async def approve(request: Request):
        params = await body(request)
        if set(params) != {"transaction", "decision"}:
            raise oauth.OAuthError()
        destination = provider.approve(request, params["transaction"], params["decision"])
        return RedirectResponse(destination, status_code=303)

    @site.post("/token")
    async def token(request: Request):
        if request.url.query:
            raise oauth.OAuthError()
        params = await body(request)
        client_auth(request, params)
        return JSONResponse(provider.exchange(params))

    @site.post("/revoke")
    async def revoke(request: Request):
        if request.url.query:
            raise oauth.OAuthError()
        params = await body(request)
        client_auth(request, params)
        if set(params) != {"token"}:
            raise oauth.OAuthError()
        provider.revoke(params["token"])
        return JSONResponse({})

    @site.get("/records")
    def records(request: Request):
        result = provider.records(request)
        from app.core.schedule_read_projection import project_schedule_meetings
        return success(project_schedule_meetings(result), request_id=str(uuid4()), data_version="demo-v1")

    if settings.cloud_degree_progress_enabled and hasattr(provider,"degree_progress"):
        @site.get("/degree/progress")
        def degree_progress(request: Request):
            if request.url.query:
                raise oauth.OAuthError()
            from app.core.degree_progress import format_degree_receipt
            data=format_degree_receipt(provider.degree_progress(request))
            return success({**data,"degree_url":settings.app_origin+"/tools/degree"},
                request_id=str(uuid4()),data_version="degree-progress-v1")

    if settings.cloud_degree_agent_write_enabled and hasattr(provider,"degree_import"):
        async def degree_body(request,limit):
            def unique(items):
                result={}
                for key,value in items:
                    if key in result:
                        raise ValueError('duplicate key')
                    result[key]=value
                return result
            try:
                if request.headers.get('Content-Type','').split(';',1)[0]!='application/json':
                    raise ValueError('expected json')
                raw=bytearray()
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw)>limit:
                        raise ValueError('oversize')
                return json.loads(raw,object_pairs_hook=unique)
            except (ValueError, RecursionError):
                raise AppError(422,'VALIDATION_ERROR','Expected bounded JSON degree request without duplicate fields') from None

        @site.post("/degree/import-drafts")
        async def degree_prepare(request: Request):
            if request.url.query:
                raise oauth.OAuthError()
            arguments=await degree_body(request,300000)
            return success(provider.degree_import(request,arguments,'prepare'),
                request_id=str(uuid4()),data_version="degree-agent-v1")

        @site.post("/degree/import-confirm")
        async def degree_confirm(request: Request):
            if request.url.query:
                raise oauth.OAuthError()
            arguments=await degree_body(request,8192)
            return success(provider.degree_import(request,arguments,'confirm'),
                request_id=str(uuid4()),data_version="degree-agent-v1")

    if settings.cloud_agent_device_binding_enabled and hasattr(provider,"bind_device"):
        @site.post("/devices/bind")
        async def bind_device(request: Request):
            if request.url.query:
                raise oauth.OAuthError()
            return success(provider.bind_device(request,await body(request)),
                request_id=str(uuid4()),data_version="agent-device-v1")

    # Cloud-only adapter: the loopback provider and public MCP remain unchanged.
    if hasattr(provider, "time_query"):
        async def owned_time(request, operation):
            from app.domains.schedule.service import CALCULATION_VERSION
            result, warnings = provider.time_query(request, await body(request), operation)
            return success(result, request_id=str(uuid4()), data_version="demo-v1",
                           calculation_version=CALCULATION_VERSION,
                           warnings=[WarningItem(**warning) for warning in warnings])

        @site.post("/time/free-slots")
        async def free_time(request: Request):
            return await owned_time(request, "free")

        @site.post("/time/check")
        async def check_time(request: Request):
            return await owned_time(request, "check")

    @site.post("/task-drafts")
    async def draft(request: Request):
        params = await body(request)
        # Only known fixture identifiers, no workspace/user argument or arbitrary text.
        if set(params) != {"fixture_id", "idempotency_key"}:
            raise oauth.OAuthError()
        if params["fixture_id"] not in {"notice-event.demo.json", "notice-deadline.demo.json", "notice-ambiguous.demo.json"}:
            raise AppError(403, "DEMO_ONLY", "Checked fictional fixture required")
        from app.core.demo import load_fixture
        result = provider.draft(request, load_fixture(params["fixture_id"]), params["idempotency_key"])
        return success(result, request_id=str(uuid4()), data_version="demo-v1")

    if settings.cloud_notice_text_pilot_enabled and hasattr(provider,"notice_query"):
        @site.post("/notice/read")
        async def notice_read(request: Request):
            result=provider.notice_query(request,await body(request),"read")
            return success(result,request_id=str(uuid4()),data_version="notice-text-pilot-v1")

        @site.post("/notice/check")
        async def notice_check(request: Request):
            from app.domains.schedule.service import CALCULATION_VERSION
            result=provider.notice_query(request,await body(request),"check")
            return success(result,request_id=str(uuid4()),data_version="notice-text-pilot-v1",calculation_version=CALCULATION_VERSION)

    if settings.cloud_task_calendar_enabled and hasattr(provider,"calendar_summary"):
        @site.get("/tasks/summary")
        def task_summary(request: Request):
            if request.url.query:
                raise oauth.OAuthError()
            return success(provider.calendar_summary(request),request_id=str(uuid4()),data_version="task-calendar-v1")

    if settings.cloud_personal_tasks_enabled and hasattr(provider,"personal_query"):
        @site.get("/tasks/entries")
        def personal_records(request: Request):
            if request.url.query:
                raise oauth.OAuthError()
            from app.cloud_identity_site import format_times
            return success(format_times(provider.personal_query(request,None,"records")),request_id=str(uuid4()),data_version="personal-tasks-v1")

        @site.post("/tasks/entries/drafts")
        async def personal_draft(request: Request):
            from app.cloud_identity_site import format_times
            return success(format_times(provider.personal_query(request,await body(request),"draft")),request_id=str(uuid4()),data_version="personal-tasks-v1")

        @site.post("/tasks/entries/commit")
        async def personal_commit(request: Request):
            from app.cloud_identity_site import format_times
            return success(format_times(provider.personal_query(request,await body(request),"commit")),request_id=str(uuid4()),data_version="personal-tasks-v1")

    return site

"""Stable browser locator; only a freshly consented Agent grant supplies owner."""
import base64
import hashlib
import html
import json
import re
import time
from secrets import token_urlsafe
from urllib.parse import urlencode, urlsplit, parse_qsl

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.core.browser_session_context import CONTEXT_COOKIE, encode_context
from app.core.errors import AppError
from app.core.persistent_auth import COOKIE_MAX_AGE, UNTIL_REVOKED_EPOCH
from app.core.security import SESSION_COOKIE, secret_hash
from app.device_login_site import SECRET, _object

COOKIE = "__Host-campus_fixed_device"
PATH = "/api/v1/auth/agent-device"
CODE = re.compile(r"^DEV-[A-Z2-7]{26}$")
RETURNS = frozenset({"/tools/timetable", "/tools/calendar", "/tools/import", "/tools/tasks"})


def display_code(secret):
    # Stable opaque locator, NOT a login credential. Private secret never leaves cookie.
    return "DEV-" + base64.b32encode(hashlib.sha256(("display:" + secret).encode()).digest()[:16]).decode().rstrip("=")


def binding_url(destination):
    return "/tools/device-login?" + urlencode({"return_to": destination})


def valid_destination(value):
    if type(value) is not str or len(value) > 512 or re.search(r"[\x00-\x20\x7f\\#]", value):
        return False
    target = urlsplit(value)
    if target.scheme or target.netloc or target.path not in RETURNS:
        return False
    query = parse_qsl(target.query, keep_blank_values=True)
    if not query:
        return not target.query
    if target.path in {"/tools/import", "/tools/tasks"} and len(query) == 1:
        return query[0][0] == "draft_id" and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", query[0][1]))
    # Only an extension's public one-shot transfer locator, never owner/auth data.
    if target.path == "/tools/import" and len(query) == 2:
        values = dict(query)
        return set(values) == {"source", "transfer_id"} and values["source"] == "eamis-auto" and bool(re.fullmatch(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", values["transfer_id"]))
    return False


def device_status(request, database):
    secret, token = request.cookies.get(COOKIE, ""), request.cookies.get(SESSION_COOKIE, "")
    if not SECRET.fullmatch(secret) or not token:
        return {"status": "pending"}
    return database.agent_device_call("status", {"challenge_hash": secret_hash(secret), "session_hash": secret_hash(token)})


def install_agent_device(site, runtime, database):
    if not runtime.cloud_agent_device_binding_enabled:
        return

    async def body(request):
        if (request.query_params or request.headers.get("Origin") != runtime.app_origin
                or request.headers.get("X-Campus-Device") != "1"
                or request.headers.get("Content-Type", "").split(";", 1)[0] != "application/json"):
            raise AppError(403, "FORBIDDEN", "Same-origin browser required")
        raw = await request.body()
        try:
            if len(raw) > 1024 or json.loads(raw, object_pairs_hook=_object) != {}:
                raise ValueError
        except (ValueError, UnicodeError):
            raise AppError(422, "VALIDATION_ERROR", "No identity overrides accepted") from None

    def reply(data):
        return JSONResponse({"ok": True, "data": data}, headers={"Cache-Control": "no-store"})

    def logged_in(request):
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return False
        try:
            database.call("get_workspace", {"session_hash": secret_hash(token)})
            return True
        except AppError as exc:
            if exc.code not in {"AUTH_REQUIRED", "TOKEN_EXPIRED"}:
                raise
            return False

    @site.post(PATH + "/start")
    async def start(request: Request):
        await body(request)
        authenticated = logged_in(request)
        secret = request.cookies.get(COOKIE, "")
        if not SECRET.fullmatch(secret):
            secret = token_urlsafe(32)
        code = display_code(secret)
        database.agent_device_call("register" if authenticated else "start", {
            "challenge_hash": secret_hash(secret), "code_hash": secret_hash(code),
            **({"session_hash": secret_hash(request.cookies[SESSION_COOKIE])} if authenticated else {})})
        response = reply({"status": "pending", "device_code": code})
        response.set_cookie(COOKIE, secret, max_age=COOKIE_MAX_AGE, httponly=True, secure=True, samesite="strict", path="/")
        # Only clear invalid credentials, never silently replace a valid account.
        if not authenticated:
            for name in (SESSION_COOKIE, CONTEXT_COOKIE):
                response.delete_cookie(name, httponly=True, secure=True, samesite="strict", path="/")
        return response

    @site.post(PATH + "/claim")
    async def claim(request: Request):
        await body(request)
        if logged_in(request):
            status = device_status(request, database)
            return reply({**status,"status":"already_logged_in" if status["status"] == "bound" else "pending"})
        secret = request.cookies.get(COOKIE, "")
        if not SECRET.fullmatch(secret):
            raise AppError(401, "AUTH_REQUIRED", "Open the binding page in this browser first")
        token, csrf = token_urlsafe(32), token_urlsafe(32)
        result = database.agent_device_call("claim", {"challenge_hash": secret_hash(secret),
            "token_hash": secret_hash(token), "csrf_hash": secret_hash(csrf)})
        if result.get("status") == "pending":
            return reply(result)
        expiry = result.get("expires_epoch")
        if result.get("status") != "bound" or type(expiry) is not int or expiry <= int(time.time()):
            raise AppError(503, "DEPENDENCY_UNAVAILABLE", "Binding unavailable", True)
        if expiry == UNTIL_REVOKED_EPOCH and not runtime.cloud_persistent_auth_enabled:
            raise AppError(403, "FORBIDDEN", "Persistent access disabled")
        age = COOKIE_MAX_AGE if expiry == UNTIL_REVOKED_EPOCH else min(900, expiry - int(time.time()))
        response = reply({"status": "bound", "workspace_ref": result["workspace_ref"]})
        response.set_cookie(SESSION_COOKIE, token, max_age=age, httponly=True, secure=True, samesite="strict", path="/")
        response.set_cookie(CONTEXT_COOKIE, encode_context(token, result["workspace_ref"], csrf, expiry),
            max_age=age, httponly=True, secure=True, samesite="strict", path="/")
        return response

    @site.get("/tools/device")
    def device_details(request: Request):
        # Viewing the locator must never enroll, claim, renew or replace a device.
        if request.query_params:
            raise AppError(422, "VALIDATION_ERROR", "Device details use this browser only")
        secret = request.cookies.get(COOKIE, "")
        has_code = bool(SECRET.fullmatch(secret))
        bound = False
        if has_code and logged_in(request):
            bound = device_status(request, database)["status"] == "bound"
        code_markup = (f'<code id="device-code">{display_code(secret)}</code>'
                       '<button id="copy-code" type="button">复制设备码</button>'
                       '<p id="copy-status" role="status"></p>' if has_code else
                       '<p>当前浏览器尚未生成设备码。请先打开绑定页。</p>')
        visitor = runtime.cloud_visitor_enabled and logged_in(request) and database.call("visitor_status", {"session_hash": secret_hash(request.cookies[SESSION_COOKIE])}).get("visitor") is True
        status = "已绑定并登录" if bound else "本浏览器访客已登录；Agent 尚未完成关联授权" if visitor else "尚未完成有效登录，请前往绑定页检查"
        action = ('<a class="action" href="/tools/timetable">返回我的课表</a>' if bound or visitor else
                  '<a class="action" href="/tools/device-login">前往绑定页</a>')
        nonce = token_urlsafe(24)
        page_html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>我的设备码 · 南开校园助手</title><style nonce="NONCE">
body{background:#f5f8fa;color:#183b40;font:18px/1.8 system-ui;margin:0;padding:24px}header{max-width:1100px;margin:0 auto 32px;display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap;border-bottom:1px solid #dbe5e7;padding-bottom:20px}header strong{font-size:24px}nav{display:flex;gap:12px;flex-wrap:wrap}a{color:#176574}nav a,button,.action{padding:10px 16px;border-radius:12px;border:1px solid #bdd5d6;background:white;text-decoration:none}nav a[aria-current]{border-color:#176574;background:#eaf4f4}main{max-width:650px;margin:auto;background:white;padding:32px;border:1px solid #dbe5e7;border-radius:22px}h1{font-size:28px}code{display:block;overflow-wrap:anywhere;padding:16px;background:#eaf4f4;font-size:22px;margin-bottom:16px}button{font:inherit;cursor:pointer}.note{font-size:15px;color:#527074}.action{display:inline-block}</style>
<header><strong>南开校园助手 · 工具站</strong><nav aria-label="工具导航"><a href="/tools/timetable">课表</a><a href="/tools/calendar">待办日历</a><a href="/tools/device" aria-current="page">我的设备码</a></nav><a href="https://coze.nankai.edu.cn/product/llm/chat/db0ulft4shhbpg8v7rgg">返回 NK-GeniOS</a></header>
<main><h1>我的设备码</h1><p>这是当前浏览器的固定设备码，查看或复制不会生成新码，也不会重新绑定。</p>CODE_MARKUP
<p>当前状态：STATUS</p>ACTION
<p class="note">设备码标识这台浏览器，课表与日历归属以 Agent 的本人授权账号为准。同一账号绑定的不同浏览器会同步读取同一份数据。设备码不是密码，不能只凭它登录。</p>
<p class="note">清除本站浏览器数据或换浏览器会生成新码；退出、撤销授权或移出名单仍会失效。</p></main>
<script nonce="NONCE">const copy=document.getElementById('copy-code');if(copy)copy.onclick=async()=>{const status=document.getElementById('copy-status');try{await navigator.clipboard.writeText(document.getElementById('device-code').textContent);status.textContent='设备码已复制。';}catch{status.textContent='请选中上方设备码手动复制。';}};</script></html>'''
        page_html = (page_html.replace("NONCE", html.escape(nonce)).replace("CODE_MARKUP", code_markup)
                     .replace("STATUS", status).replace("ACTION", action))
        return HTMLResponse(page_html, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"})

    @site.get("/tools/device-login")
    def page(request: Request):
        params = list(request.query_params.multi_items())
        destination = request.query_params.get("return_to", "/tools/timetable")
        if (params and (len(params) != 1 or params[0][0] != "return_to")) or not valid_destination(destination):
            raise AppError(422, "VALIDATION_ERROR", "Choose a toolstation page")
        if logged_in(request) and device_status(request,database)["status"] == "bound":
            return RedirectResponse(destination, status_code=303)
        nonce = token_urlsafe(24)
        visitor_markup = ('<hr><h2>还没有工具站账号？</h2><p>免注册创建本浏览器独立空间，不会读取其他人的课表或日历。已有 Agent 授权时，请先使用上面的绑定请求，避免创建不同身份。</p><button id="visitor">免注册开始使用</button><p class="note">清除本站全部浏览器数据会丢失访客身份；请勿在公共电脑保存私密资料。</p>' if runtime.cloud_visitor_enabled else '')
        page_html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>绑定这台浏览器 · 南开校园助手</title><style nonce="NONCE">
body{background:#f5f8fa;color:#183b40;font:18px/1.8 system-ui;margin:0;padding:8vh 24px}main{max-width:650px;margin:auto;background:white;padding:32px;border:1px solid #dbe5e7;border-radius:22px}h1{font-size:28px}code{display:block;overflow-wrap:anywhere;padding:16px;background:#eaf4f4;font-size:22px}button,a{font:inherit}button{padding:12px 18px;border-radius:12px;border:1px solid #bdd5d6;background:white;cursor:pointer}.note{font-size:15px;color:#527074}</style>
<main><h1>绑定这台浏览器</h1><p>设备码已为当前浏览器自动生成。把下面这句话发给南开校园助手，绑定到 Agent 当前授权的账号：</p>
<code id="code">正在生成设备码…</code><p id="command"></p><button id="copy" disabled>复制绑定请求</button> <button id="check">检查绑定并进入</button>
<p id="status" role="status">等待绑定。</p><a href="AGENT" target="_blank" rel="noopener noreferrer">返回 Agent 发送绑定请求 ↗</a>VISITOR_MARKUP
<p class="note">同一浏览器的设备码不随时间轮换，不需要临时确认码。清除浏览器数据或换浏览器会生成新码。首次绑定需要插件的本人设备绑定授权；学校登录不会自动识别工具站账号。退出、撤销授权或移出名单仍会失效，课表与日历数据保留且不与他人共享。</p></main>
<script nonce="NONCE">
const status=document.getElementById('status'),copy=document.getElementById('copy');let command='',busy=false,stopped=false;
async function post(op){const r=await fetch('/api/v1/auth/agent-device/'+op,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Campus-Device':'1'},body:'{}'});const v=await r.json();if(!r.ok||!v.ok)throw Error('绑定检查失败，请重试或返回 Agent 重新授权。');return v.data;}
async function check(){if(busy||stopped)return;busy=true;try{const d=await post('claim');if(d.status==='bound'||d.status==='already_logged_in'){stopped=true;status.textContent='绑定已完成，正在进入…';location.replace(DESTINATION);}else status.textContent='等待你在 Agent 中发送绑定请求；绑定成功后自动进入。';}catch(e){stopped=true;status.textContent=e.message;}finally{busy=false;}}
copy.onclick=async()=>{try{await navigator.clipboard.writeText(command);status.textContent='已复制。请粘贴到 Agent 聊天框并发送。';}catch{status.textContent='请选中上面的绑定请求手动复制。';}};
document.getElementById('check').onclick=()=>{stopped=false;check();};
const visitor=document.getElementById('visitor');if(visitor)visitor.onclick=async()=>{if(busy)return;busy=true;stopped=true;visitor.disabled=true;try{const r=await fetch('/api/v1/auth/visitor/session',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Campus-Visitor':'1'},body:'{}'});const v=await r.json();if(!r.ok||!v.ok)throw Error('无法开始访客会话；已有绑定身份时请返回 Agent 授权，不能覆盖账号。');location.replace(DESTINATION);}catch(e){status.textContent=e.message;visitor.disabled=false;}finally{busy=false;}};
async function start(){try{const d=await post('start');if(d.status==='already_logged_in'){location.replace(DESTINATION);return;}document.getElementById('code').textContent=d.device_code;command='确认将我的这台浏览器绑定到你当前授权的账号，设备码：'+d.device_code;document.getElementById('command').textContent=command;copy.disabled=false;await check();setInterval(check,3000);}catch(e){status.textContent=e.message;}}
start();</script></html>'''
        page_html = page_html.replace("NONCE", html.escape(nonce)).replace("DESTINATION", json.dumps(destination)).replace("AGENT", "https://coze.nankai.edu.cn/product/llm/chat/db0ulft4shhbpg8v7rgg").replace("VISITOR_MARKUP", visitor_markup)
        return HTMLResponse(page_html, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"})

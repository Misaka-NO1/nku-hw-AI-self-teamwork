"""First-device explicit enrollment, not automatic GeniOS identity recognition.

Default off. Only an already authenticated original browser may approve a new
browser. Display codes/receipts are not credentials; the claim secret stays in
an HttpOnly cookie. The cloud migration and desktop acceptance are separate.
"""
import json
import re
import time
from secrets import choice, token_urlsafe

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.browser_session_context import CONTEXT_COOKIE, encode_context
from app.core.errors import AppError
from app.core.persistent_auth import COOKIE_MAX_AGE, UNTIL_REVOKED_EPOCH
from app.core.security import SESSION_COOKIE, secret_hash
from app.device_login_page import device_login_html

DEVICE_COOKIE = "campus_device_challenge"
DEVICE_PATH = "/api/v1/auth/devices"
CODE = re.compile(r"^DC-[A-Z2-7]{12}$")
SECRET = re.compile(r"^[A-Za-z0-9_-]{43}$")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def install_device_login(site, runtime, database, browser_args):
    if not runtime.cloud_device_login_enabled or runtime.cloud_agent_device_binding_enabled:
        return

    @site.get("/tools/device-login")
    def page(request: Request):
        if request.query_params:
            raise AppError(422, "VALIDATION_ERROR", "Device credentials are not accepted in URLs")
        nonce = token_urlsafe(24)
        return HTMLResponse(device_login_html(nonce), headers={"Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer", "Content-Security-Policy":
            f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"})

    async def body(request, fields):
        if (request.query_params or request.headers.get("Origin") != runtime.app_origin
                or request.headers.get("X-Campus-Device") != "1"
                or request.headers.get("Content-Type", "").split(";", 1)[0] != "application/json"):
            raise AppError(403, "FORBIDDEN", "Same-origin device confirmation required")
        raw = await request.body()
        try:
            if len(raw) > 2048:
                raise ValueError
            value = json.loads(raw, object_pairs_hook=_object)
            if type(value) is not dict or set(value) != fields:
                raise ValueError
            return value
        except (ValueError, UnicodeError):
            raise AppError(422, "VALIDATION_ERROR", "Invalid device request") from None

    def fresh_browser(request):
        # Never silently replace even an expired existing account cookie.
        if request.cookies.get(SESSION_COOKIE):
            raise AppError(409, "STALE_REVISION", "Sign out before binding a different browser account")

    def code_hash(value):
        if type(value) is not str or not CODE.fullmatch(value):
            raise AppError(422, "VALIDATION_ERROR", "Check the device code")
        return secret_hash(value)

    def reply(data):
        return JSONResponse({"ok": True, "data": data}, headers={"Cache-Control": "no-store"})

    @site.post(DEVICE_PATH + "/start")
    async def start(request: Request):
        await body(request, set())
        fresh_browser(request)
        challenge = token_urlsafe(32)
        code = "DC-" + "".join(choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567") for _ in range(12))
        result = database.device_call("start", {"challenge_hash": secret_hash(challenge), "code_hash": secret_hash(code)})
        response = reply({"user_code": code, "expires_epoch": result["expires_epoch"], "status": "confirmation_required"})
        response.set_cookie(DEVICE_COOKIE, challenge, max_age=300, httponly=True, secure=True,
                            samesite="strict", path=DEVICE_PATH)
        return response

    @site.post(DEVICE_PATH + "/review")
    async def review(request: Request):
        value = await body(request, {"user_code"})
        auth = browser_args(request, write=True)
        receipt = token_urlsafe(32)
        result = database.device_call("review", {"session_hash": auth["session_hash"], "csrf_hash": auth["csrf_hash"],
                                      "code_hash": code_hash(value["user_code"]), "receipt_hash": secret_hash(receipt)})
        return reply({**result, "review_receipt": receipt,
                      "notice": "Only confirm the code shown on your own new browser. It will access this account's timetable and calendar until the source login expires or is revoked."})

    @site.post(DEVICE_PATH + "/approve")
    async def approve(request: Request):
        value = await body(request, {"user_code", "review_receipt", "confirm_device"})
        auth = browser_args(request, write=True)
        if (value["confirm_device"] is not True or type(value["review_receipt"]) is not str
                or not SECRET.fullmatch(value["review_receipt"])):
            raise AppError(409, "CONFIRMATION_REQUIRED", "Explicit device confirmation required")
        result = database.device_call("approve", {"session_hash": auth["session_hash"], "csrf_hash": auth["csrf_hash"],
            "code_hash": code_hash(value["user_code"]), "receipt_hash": secret_hash(value["review_receipt"]), "confirm_device": True})
        return reply(result)

    @site.post(DEVICE_PATH + "/claim")
    async def claim(request: Request):
        await body(request, set())
        fresh_browser(request)
        challenge = request.cookies.get(DEVICE_COOKIE, "")
        if not SECRET.fullmatch(challenge):
            raise AppError(401, "AUTH_REQUIRED", "Start binding in this browser first")
        token, csrf = token_urlsafe(32), token_urlsafe(32)
        result = database.device_call("claim", {"challenge_hash": secret_hash(challenge),
                                                "token_hash": secret_hash(token), "csrf_hash": secret_hash(csrf)})
        if result.get("status") == "pending":
            return reply(result)
        expiry = result["expires_epoch"]
        if result.get("status") != "bound" or type(expiry) is not int or expiry <= int(time.time()):
            raise AppError(503, "DEPENDENCY_UNAVAILABLE", "Device binding unavailable", True)
        if expiry == UNTIL_REVOKED_EPOCH:
            if not runtime.cloud_persistent_auth_enabled:
                raise AppError(403, "FORBIDDEN", "Persistent access is disabled")
            age = COOKIE_MAX_AGE
        else:
            age = min(900, max(1, expiry - int(time.time())))
        response = reply({**result, "csrf_token": csrf})
        response.set_cookie(SESSION_COOKIE, token, max_age=age, httponly=True, secure=True, samesite="strict", path="/")
        response.set_cookie(CONTEXT_COOKIE, encode_context(token, result["workspace_ref"], csrf, expiry),
                            max_age=age, httponly=True, secure=True, samesite="strict", path="/")
        response.delete_cookie(DEVICE_COOKIE, path=DEVICE_PATH, httponly=True, secure=True, samesite="strict")
        return response

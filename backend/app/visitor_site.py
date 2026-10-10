"""Passwordless private browser identity, never a school identity or public data access."""
import json
from secrets import token_urlsafe

from fastapi import Request, Response

from app.agent_device_site import COOKIE, display_code
from app.device_login_site import SECRET, _object
from app.core.browser_session_context import CONTEXT_COOKIE, decode_context, encode_context
from app.core.persistent_auth import COOKIE_MAX_AGE, UNTIL_REVOKED_EPOCH
from app.core.security import SESSION_COOKIE, secret_hash
from app.core.errors import AppError
from app.core.contracts import validate_boundary


def install_visitor(site, runtime, database, reply):
    if not runtime.cloud_visitor_enabled:
        return

    @site.post("/api/v1/auth/visitor/session")
    async def begin(request: Request, response: Response):
        if (request.query_params or request.headers.get("Origin") != runtime.app_origin
            or request.headers.get("X-Campus-Visitor") != "1"
            or request.headers.get("Sec-Fetch-Site", "same-origin") != "same-origin"
            or request.headers.get("Content-Type", "").split(";", 1)[0] != "application/json"):
            raise AppError(403, "FORBIDDEN", "Same-origin visitor setup required")
        raw = await request.body()
        try:
            if len(raw) > 1024:
                raise ValueError
            payload = json.loads(raw, object_pairs_hook=_object)
        except (ValueError, UnicodeError):
            raise AppError(422, "VALIDATION_ERROR", "No account or device-code overrides accepted") from None
        validate_boundary(payload, "BrowserVisitorStartRequest")
        # Never turn a valid legacy owner's session into a new visitor account.
        token = request.cookies.get(SESSION_COOKIE, "")
        if token:
            try:
                workspace = database.call("get_workspace", {"session_hash": secret_hash(token)})
            except AppError as exc:
                if exc.code not in {"AUTH_REQUIRED", "TOKEN_EXPIRED"}:
                    raise
            else:
                context = decode_context(token, request.cookies.get(CONTEXT_COOKIE, ""), persistent=True)
                if context["workspace_ref"] != workspace["workspace_ref"]:
                    raise AppError(401, "AUTH_REQUIRED", "Invalid browser session context")
                return reply(request, {**context, "dataset_kind": "demo", "personal_uploads": False, "agent_paired": False})
        # Private HttpOnly proof, not the public DEV code, preserves the visitor.
        secret = request.cookies.get(COOKIE, "")
        if not SECRET.fullmatch(secret):
            secret = token_urlsafe(32)
        code = display_code(secret)
        token, csrf = token_urlsafe(32), token_urlsafe(32)
        result = database.call("visitor_begin", {
            "challenge_hash": secret_hash(secret), "code_hash": secret_hash(code),
            "subject_id": "visitor_" + secret_hash(token_urlsafe(32)),
            "token_hash": secret_hash(token), "csrf_hash": secret_hash(csrf),
            "workspace_ref": "pilot_workspace_" + token_urlsafe(18),
        })
        if result.get("expires_epoch") != UNTIL_REVOKED_EPOCH:
            raise AppError(503, "DEPENDENCY_UNAVAILABLE", "Visitor storage unavailable", True)
        for name, value in ((SESSION_COOKIE, token), (COOKIE, secret),
            (CONTEXT_COOKIE, encode_context(token, result["workspace_ref"], csrf, result["expires_epoch"]))):
            response.set_cookie(name, value, max_age=COOKIE_MAX_AGE, httponly=True, secure=True, samesite="strict", path="/")
        return reply(request, {**result, "csrf_token": csrf, "dataset_kind": "demo",
            "personal_uploads": False, "agent_paired": False})

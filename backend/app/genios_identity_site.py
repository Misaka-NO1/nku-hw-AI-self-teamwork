"""Private REST platform attestation + same-origin, private-cookie browser claim.

The public DEV code locates a browser; it never supplies a school principal or
browser login. A legacy account must be adopted using its real original OAuth.
"""
import json
from secrets import token_urlsafe

from fastapi import Request
from fastapi.responses import JSONResponse

from app.agent_device_site import COOKIE
from app.device_login_site import SECRET, _object
from app.core.browser_session_context import CONTEXT_COOKIE, encode_context
from app.core.envelope import success
from app.core.errors import AppError
from app.core.genios_identity import verify_native_request, verify_native_headers, issue_native_attestation, KEY, ATTESTATION_SECONDS
from app.core.oauth_local import resource_token
from app.core.persistent_auth import COOKIE_MAX_AGE, UNTIL_REVOKED_EPOCH
from app.core.request_id import current_request_id
from app.core.security import SESSION_COOKIE, secret_hash

PATH = "/api/v1/auth/genios"


def native_configuration(runtime, database_key=""):
    if not runtime.cloud_genios_native_identity_enabled:
        return
    key = runtime.genios_native_integration_key.get_secret_value()
    if (not runtime.cloud_visitor_enabled or not runtime.cloud_agent_device_binding_enabled
            or not KEY.fullmatch(key) or key in {database_key, runtime.mcp_service_token.get_secret_value()}
            or secret_hash(key) == runtime.oauth_client_secret_hash.get_secret_value()):
        raise ValueError("Native identity requires an independent private integration credential and private visitor gates")


def install_genios_identity(site, runtime, database):
    if not runtime.cloud_genios_native_identity_enabled:
        return
    key = runtime.genios_native_integration_key.get_secret_value()

    def reply(request, data):
        return JSONResponse(success(data, request_id=current_request_id(request),
            data_version="native-identity-v1").model_dump(mode="json"), headers={"Cache-Control": "no-store"})

    def public_result(data):
        # Never expose raw UID/hash/subject or a session credential to the Agent.
        return {k: v for k, v in data.items() if k in {"status", "has_space", "created"}} | {
            "space_label": "SPACE-" + secret_hash(data["workspace_ref"])[:12].upper() if data.get("workspace_ref") else None}

    async def native(request, credential_header="authorization"):
        if request.query_params:
            raise AppError(422, "VALIDATION_ERROR", "Identity parameters must not be in URLs")
        principal = verify_native_request(request.headers, await request.body(), key,
            (runtime.mcp_service_token.get_secret_value(),), credential_header=credential_header)
        return principal

    @site.post(PATH + "/attest")
    async def attest(request: Request):
        raw = await request.body()
        try:
            # Some REST tool transports serialize a parameterless POST as {}.
            # Both transports are read-only; no identity or owner body accepted.
            if (request.query_params or len(raw) > 1024 or (raw and (
                    request.headers.get("content-type", "").split(";", 1)[0] != "application/json"
                    or json.loads(raw, object_pairs_hook=_object) != {}))):
                raise ValueError
        except (ValueError, TypeError, UnicodeError):
            raise AppError(422, "VALIDATION_ERROR", "No attestation body or URL parameters accepted")
        identity_hash = verify_native_headers(request.headers, key,
            (runtime.mcp_service_token.get_secret_value(),))
        return reply(request, {"platform_attestation":issue_native_attestation(identity_hash, key),
            "expires_in":ATTESTATION_SECONDS})

    @site.post(PATH + "/onboard")
    async def onboard(request: Request):
        principal = await native(request)
        common = {"identity_hash": principal.identity_hash, "code_hash": secret_hash(principal.device_code)}
        if principal.intent == "lookup":
            result = database.native_identity_call("identify", common)
        else:
            result = database.native_identity_call("enroll", {**common, "intent": principal.intent,
                "confirmed": principal.confirmed, "workspace_ref": "pilot_workspace_" + token_urlsafe(18)})
        return reply(request, public_result(result))

    @site.post(PATH + "/associate")
    async def associate(request: Request):
        # OAuth supplies the original owner. Independent private key + fixed
        # platform header supplies the GeniOS principal, NOT model parameters.
        principal = await native(request, "x-campus-native-key")
        if principal.intent != "bind" or len(request.headers.getlist("authorization")) != 1:
            raise AppError(422, "VALIDATION_ERROR", "Explicit original-account binding required")
        grant = resource_token(request).get_secret_value()
        result = database.native_identity_call("adopt_bind", {"identity_hash": principal.identity_hash,
            "code_hash": secret_hash(principal.device_code), "grant_hash": secret_hash(grant),
            "audience": runtime.oauth_client_id, "confirmed": principal.confirmed})
        return reply(request, public_result(result))

    async def browser(request):
        if (request.query_params or request.headers.get("Origin") != runtime.app_origin
                or request.headers.get("X-Campus-Native") != "1"
                or request.headers.get("Sec-Fetch-Site", "same-origin") != "same-origin"
                or request.headers.get("Content-Type", "").split(";", 1)[0] != "application/json"):
            raise AppError(403, "FORBIDDEN", "Same-origin native browser required")
        raw = await request.body()
        try:
            if len(raw) > 1024 or json.loads(raw, object_pairs_hook=_object) != {}:
                raise ValueError
        except (ValueError, UnicodeError):
            raise AppError(422, "VALIDATION_ERROR", "No browser identity overrides accepted") from None
        secret = request.cookies.get(COOKIE, "")
        if not SECRET.fullmatch(secret):
            raise AppError(401, "AUTH_REQUIRED", "Open this browser's binding page first")
        return {"challenge_hash": secret_hash(secret),
            "session_hash": secret_hash(request.cookies.get(SESSION_COOKIE, ""))}

    @site.post(PATH + "/state")
    async def state(request: Request):
        return reply(request, public_result(database.native_identity_call("state", await browser(request))))

    @site.post(PATH + "/claim")
    async def claim(request: Request):
        args = await browser(request)
        token, csrf = token_urlsafe(32), token_urlsafe(32)
        result = database.native_identity_call("claim", {**args, "token_hash": secret_hash(token), "csrf_hash": secret_hash(csrf)})
        response = reply(request, public_result(result))
        if result.get("status") == "already_logged_in":
            return response  # Never replace a valid cookie or silently switch owner.
        if result.get("status") != "bound":
            return response
        if result.get("expires_epoch") != UNTIL_REVOKED_EPOCH:
            raise AppError(503, "DEPENDENCY_UNAVAILABLE", "Native browser storage unavailable", True)
        response.set_cookie(SESSION_COOKIE, token, max_age=COOKIE_MAX_AGE, httponly=True, secure=True, samesite="strict", path="/")
        response.set_cookie(CONTEXT_COOKIE, encode_context(token, result["workspace_ref"], csrf, result["expires_epoch"]),
            max_age=COOKIE_MAX_AGE, httponly=True, secure=True, samesite="strict", path="/")
        return response

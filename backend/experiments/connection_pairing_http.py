"""Loopback TestClient-only transport experiment; no production registration."""
import base64
import binascii
import json
import re
from urllib.parse import parse_qsl, unquote_plus
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.core.envelope import failure, success
from experiments.connection_pairing import PairingError


ORIGIN = "http://127.0.0.1:8014"


def create_offline_http(engine, *, enabled=False):
    if not enabled:
        raise PairingError("prototype_disabled")
    app = FastAPI(title="OFFLINE connection pairing experiment", docs_url=None,
                  redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def secure(request, call_next):
        # No forwarded-host trust, CORS, cookies-as-bearer, or Internet host.
        if request.headers.get("Host") != "127.0.0.1:8014":
            response = JSONResponse({"error": "offline_only"}, status_code=403)
        else:
            response = await call_next(request)
        response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache",
                                 "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"})
        return response

    @app.exception_handler(PairingError)
    async def rejected(request, exc):
        status = {"invalid_client": 401, "invalid_token": 401, "auth_required": 401,
                  "forbidden": 403, "rate_limited": 429,
                  "dependency_unavailable": 503, "temporarily_unavailable": 503}.get(exc.code, 400)
        if request.url.path in {"/experiment/authorize", "/experiment/token", "/experiment/revoke"}:
            return JSONResponse({"error": exc.code}, status_code=status)
        return JSONResponse(failure(request_id=str(uuid4()), code=exc.code.upper(),
                                    message="Offline pairing operation rejected").model_dump(mode="json"), status_code=status)

    @app.exception_handler(Exception)
    async def unexpected(_, exc):
        return JSONResponse({"error": "server_error"}, status_code=500)

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result or not isinstance(value, str) or len(value) > 2048:
                raise PairingError("invalid_request")
            result[key] = value
        return result

    async def body(request, *, scalar_strings=True):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>8192:
                raise PairingError("invalid_request")
        media = request.headers.get("Content-Type", "").split(";", 1)[0]
        try:
            if media == "application/x-www-form-urlencoded" and scalar_strings:
                return pairs(parse_qsl(raw.decode("utf-8"), keep_blank_values=True,
                                       strict_parsing=True, max_num_fields=16))
            if media == "application/json":
                def json_pairs(items):
                    result = {}
                    for key, value in items:
                        if key in result:
                            raise PairingError("invalid_request")
                        result[key] = value
                    return result
                result = json.loads(raw, object_pairs_hook=json_pairs)
                if not isinstance(result, dict):
                    raise PairingError("invalid_request")
                return pairs(result.items()) if scalar_strings else result
        except (UnicodeError, ValueError):
            raise PairingError("invalid_request") from None
        raise PairingError("invalid_request")

    def client(request, values):
        auth = request.headers.get("Authorization", "")
        if auth:
            if (not auth.startswith("Basic ") or len(auth)>2048
                    or "client_id" in values or "client_secret" in values):
                raise PairingError("invalid_client")
            try:
                decoded = base64.b64decode(auth[6:], validate=True).decode("ascii")
                client_id, secret = decoded.split(":", 1)
                client_id, secret = unquote_plus(client_id), unquote_plus(secret)
            except (ValueError, UnicodeError, binascii.Error):
                raise PairingError("invalid_client") from None
        else:
            client_id, secret = values.pop("client_id", ""), values.pop("client_secret", "")
        engine.authenticate(client_id, secret)
        return client_id, secret

    def browser(request):
        return {"cookie": request.cookies.get("campus_session", ""),
                "csrf": request.headers.get("X-CSRF-Token", ""),
                "origin": request.headers.get("Origin", "")}

    def no_query(request):
        if request.url.query:
            raise PairingError("invalid_request")

    @app.get("/experiment/authorize")
    def authorize(request: Request):
        return RedirectResponse(engine.bootstrap(pairs(request.query_params.multi_items())), status_code=303)

    @app.post("/experiment/token")
    async def token(request: Request):
        no_query(request)
        values = await body(request)
        client_id, secret = client(request, values)
        return engine.exchange(client_id, secret, values)

    @app.get("/experiment/records")
    def records(request: Request):
        no_query(request)
        value = request.headers.get("Authorization", "")
        if not re.fullmatch(r"Bearer [A-Za-z0-9_-]{43}", value):
            raise PairingError("invalid_token")
        # Cookies/SYS_USERID cannot override or authenticate this request.
        data = engine.records(value[7:])
        return success(data, request_id=str(uuid4()), data_version="offline-prototype-v1")

    @app.post("/experiment/pair/review")
    async def review(request: Request):
        no_query(request)
        values = await body(request)
        if set(values) != {"user_code"}:
            raise PairingError("invalid_request")
        return success(engine.review(values["user_code"], **browser(request)),
                       request_id=str(uuid4()), data_version="offline-prototype-v1")

    @app.post("/experiment/pair/approve")
    async def approve(request: Request):
        no_query(request)
        values = await body(request, scalar_strings=False)
        if set(values) != {"review_receipt", "checked_code", "confirm_same_agent", "confirm_read"}:
            raise PairingError("invalid_request")
        if not isinstance(values["review_receipt"], str) or len(values["review_receipt"])>256:
            raise PairingError("invalid_request")
        data = engine.approve(values["review_receipt"], values["checked_code"], **browser(request),
                              confirm_same_agent=values["confirm_same_agent"], confirm_read=values["confirm_read"])
        return success(data, request_id=str(uuid4()), data_version="offline-prototype-v1")

    @app.post("/experiment/revoke")
    async def revoke(request: Request):
        no_query(request)
        values = await body(request)
        client_id, secret = client(request, values)
        if set(values) != {"token"}:
            raise PairingError("invalid_request")
        engine.revoke(client_id, secret, values["token"])
        return {}

    return app

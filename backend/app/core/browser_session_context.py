"""Bound, short-lived browser resume metadata; never an independent credential.

The MAC key is the original random HttpOnly session token. PostgreSQL still
validates that session/owner on every resume; this cookie cannot create a
session, rotate CSRF, extend retention or serve as an Agent bearer.
"""
import base64
import hashlib
import hmac
import json
import re
import time

from app.core.errors import AppError
from app.core.persistent_auth import UNTIL_REVOKED_EPOCH

CONTEXT_COOKIE = "campus_browser_context"
_SAFE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CSRF = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_DOMAIN = b"campus-browser-context-v1\x00"


def _mac(token: str, encoded: str) -> str:
    return hmac.new(token.encode("utf-8"), _DOMAIN + encoded.encode("ascii"), hashlib.sha256).hexdigest()


def encode_context(token: str, workspace_ref: str, csrf_token: str, expires_epoch: int) -> str:
    body = json.dumps({"workspace_ref": workspace_ref, "csrf_token": csrf_token,
        "expires_epoch": expires_epoch}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
    return encoded + "." + _mac(token, encoded)


def decode_context(token: str, value: str, now: int | None = None, *, persistent: bool = False) -> dict:
    """Reject malformed/old/different-session context before returning any data."""
    try:
        if not token or len(token) > 128 or not value or len(value) > 2048:
            raise ValueError
        encoded, signature = value.split(".")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", encoded) or not re.fullmatch(r"[0-9a-f]{64}", signature):
            raise ValueError
        if not hmac.compare_digest(signature, _mac(token, encoded)):
            raise ValueError
        body = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if not isinstance(body, dict) or set(body) != {"workspace_ref", "csrf_token", "expires_epoch"}:
            raise ValueError
        if (not isinstance(body["workspace_ref"], str) or not _SAFE.fullmatch(body["workspace_ref"])
            or not isinstance(body["csrf_token"], str) or not _CSRF.fullmatch(body["csrf_token"])
            or type(body["expires_epoch"]) is not int):
            raise ValueError
        current = int(time.time()) if now is None else now
        # PG issues the original 900-second expiry. Allow small clock skew at
        # issuance, not a refreshed expiry; the PG session gate remains exact.
        durable = persistent and body["expires_epoch"] == UNTIL_REVOKED_EPOCH
        if not current < body["expires_epoch"] or (not durable and body["expires_epoch"] > current + 930):
            raise ValueError
        return body
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        raise AppError(401, "AUTH_REQUIRED", "Login required to resume this browser session") from None

"""Online identity verification for a closed, fictional-data-only login pilot.

Never accept SYS_USERID, a supplied uid, decoded-but-unverified JWT claims,
service-role keys, or a shared MCP token as the owner of a workspace.
See https://docs.cloudbase.net/http-api/auth/user-me .
"""
import logging
import re
import time
from secrets import token_urlsafe

import httpx
import jwt

from app.core.config import Settings
from app.core.demo import FIXTURE_SET_ID
from app.core.errors import AppError
from app.core.security import secret_hash
from app.db.database import database_connection
from app.domains.tasks.service import _timestamp_text

logger = logging.getLogger(__name__)


def _upstream_json(response: httpx.Response) -> dict:
    if response.status_code in {401, 403}:
        raise AppError(401, "AUTH_REQUIRED", "CloudBase user login is invalid or expired")
    if response.status_code != 200 or len(response.content) > 65536:
        raise AppError(503, "DEPENDENCY_UNAVAILABLE", "CloudBase identity could not be verified", True)
    value = response.json()
    if not isinstance(value, dict):
        raise AppError(401, "AUTH_REQUIRED", "Invalid CloudBase identity response")
    return value


def _pg_claims_after_online_validation(raw: str, introspected: dict, env: str) -> dict:
    """Never trust JWT parsing alone: CloudBase must validate this exact token first.

    Online introspection delegates signature/revocation checks to CloudBase over
    pinned-origin TLS. No client-selected keys/URLs, fallback, or cached acceptance.
    See /http-api/auth/auth-token-introspect and /authentication-v2/auth/auth-pg.
    """
    if (introspected.get("token_type") != "Bearer" or introspected.get("client_id") != env
            or not isinstance(introspected.get("sub"), str) or not introspected["sub"]):
        raise AppError(401, "AUTH_REQUIRED", "CloudBase did not validate this user credential")
    try:
        header = jwt.get_unverified_header(raw)
        if header.get("alg") not in {"RS256", "ES256", "HS256"}:
            raise ValueError("unsupported signature")
        # The same complete raw bytes have just been accepted by online
        # introspection. This step extracts claims; it is NOT signature validation.
        claims = jwt.decode(raw, options={"verify_signature": False})
    except (jwt.PyJWTError, ValueError):
        raise AppError(401, "AUTH_REQUIRED", "Invalid CloudBase user credential") from None
    checks = {
        "validated_subject": claims.get("sub") == introspected["sub"],
        # Issuer authenticity is established by the fixed environment's online
        # validator, NOT by guessing that an issuer equals the API request URL.
        "audience": claims.get("aud") == env and claims.get("project_id") == env,
        "expiry": type(claims.get("exp")) in {int, float} and claims["exp"] > time.time(),
        "user_role": claims.get("role") == "authenticated",
        "user_kind": claims.get("user_type") == "external" and claims.get("client_type") == "client_user",
        "not_admin": claims.get("is_system_admin") is False,
        # PG's positive authenticated role + external/client_user + live profile
        # establish a registered identity. An omitted optional anonymous flag is
        # not an anonymous identity. Explicit true or malformed flags still deny.
        "not_anonymous": claims.get("is_anonymous") is None or claims.get("is_anonymous") is False,
    }
    if not all(checks.values()):
        logger.warning("CloudBase PG credential rejected; failed_checks=%s",
            ",".join(name for name, passed in checks.items() if not passed))
        raise AppError(403, "FORBIDDEN", "Only validated ordinary PG users may enter this pilot")
    return claims


def require_pilot(settings: Settings) -> None:
    if (not settings.cloudbase_auth_pilot_enabled
            or settings.auth_mode != "demo_fixture" or settings.allow_personal_uploads
            or not re.fullmatch(r"[a-zA-Z0-9-]{8,100}", settings.cloudbase_auth_env_id)
            or not settings.cloudbase_auth_pilot_user_ids):
        raise AppError(403, "FORBIDDEN", "CloudBase fictional-data login pilot is disabled")


async def verify_cloudbase_user(settings: Settings, authorization: str) -> str:
    require_pilot(settings)
    match = re.fullmatch(r"Bearer ([A-Za-z0-9._~-]{16,8192})", authorization)
    if not match:
        raise AppError(401, "AUTH_REQUIRED", "A CloudBase user access token is required")
    # Fixed HTTPS host derived ONLY from server configuration. Never redirect
    # credentials to a client-supplied URL, proxy, or unverified issuer.
    base = f"https://{settings.cloudbase_auth_env_id}.api.tcloudbasegateway.com/auth/v1"
    headers = {"Authorization": authorization, "client_id": settings.cloudbase_auth_env_id}
    claims = None
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
            if settings.cloudbase_auth_profile == "pg_registered":
                introspected = _upstream_json(await client.get(base + "/token/introspect", headers=headers))
                claims = _pg_claims_after_online_validation(match[1], introspected,
                    settings.cloudbase_auth_env_id)
            profile = _upstream_json(await client.get(base + "/user/me", headers=headers))
    except (httpx.HTTPError, ValueError):
        # Do not return upstream profiles, URLs containing tokens, or exceptions.
        raise AppError(503, "DEPENDENCY_UNAVAILABLE", "CloudBase identity could not be verified", True) from None
    if not isinstance(profile, dict):
        raise AppError(401, "AUTH_REQUIRED", "Invalid CloudBase user profile")
    uid = profile.get("sub")
    groups = profile.get("groups")
    checks = {
        "approved_uid": isinstance(uid, str) and uid in settings.cloudbase_auth_pilot_user_ids,
        "matching_uid": isinstance(uid, str) and profile.get("user_id") == uid,
        "active": profile.get("status") == "ACTIVE",
        "external_user": profile.get("type") == "external",
        "not_anonymous": profile.get("is_anonymous") is not True,
    }
    if claims is None:
        checks.update({"ordinary_user": profile.get("internal_user_type") == "generalUser",
            "ordinary_groups": isinstance(groups, list) and bool(groups)
                and all(isinstance(group, dict) and group.get("id") == "user" for group in groups)})
    else:
        # PG uses validated authenticated/anon/service_role, not legacy groups.
        # Bind live profile to the exact online-validated credential subject.
        checks.update({"validated_profile": uid == claims["sub"],
            "not_privileged_profile": profile.get("is_system_admin") is not True
                and profile.get("internal_user_type") != "adminUser"})
    if not all(checks.values()):
        # Only fixed policy names: never profile values, UIDs, passwords,
        # request headers, tokens, group IDs or user contact details.
        logger.warning("CloudBase pilot rejected identity; failed_checks=%s",
            ",".join(name for name, passed in checks.items() if not passed))
        raise AppError(403, "FORBIDDEN", "Only approved ordinary test users may enter this pilot")
    # Store an environment-namespaced digest, not the private CloudBase UID.
    return "cloudbase_pilot_" + secret_hash(settings.cloudbase_auth_env_id + ":" + uid)


def issue_pilot_session(settings: Settings, subject_id: str, previous_token: str = "") -> dict:
    require_pilot(settings)
    now = int(time.time())
    expires = now + settings.cloudbase_auth_session_seconds
    workspace_expires = now + settings.demo_workspace_ttl_hours * 3600
    session_token, csrf = token_urlsafe(32), token_urlsafe(32)
    with database_connection(settings) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("""SELECT w.workspace_ref, w.expires_at
            FROM cloudbase_pilot_workspaces p JOIN workspaces w ON w.workspace_ref=p.workspace_ref
            WHERE p.subject_id=? AND w.owner_subject_id=?""", (subject_id, subject_id)).fetchone()
        if row and row["expires_at"] > now:
            workspace_ref = row["workspace_ref"]
        else:
            # Expired data is not silently resurrected. Replace only the pilot
            # pointer; ordinary demo cleanup retains its existing retention policy.
            workspace_ref = "pilot_workspace_" + token_urlsafe(18)
            connection.execute("INSERT INTO workspaces VALUES (?, ?, ?, ?, ?)",
                (workspace_ref, subject_id, FIXTURE_SET_ID, now, workspace_expires))
            connection.execute("INSERT OR REPLACE INTO cloudbase_pilot_workspaces VALUES (?, ?)",
                (subject_id, workspace_ref))
        if previous_token:
            connection.execute("DELETE FROM browser_sessions WHERE token_hash=?", (secret_hash(previous_token),))
        connection.execute("INSERT INTO browser_sessions VALUES (?, ?, ?, ?, ?)",
            (secret_hash(session_token), subject_id, secret_hash(csrf), now, expires))
        connection.commit()
    return {"workspace_ref": workspace_ref, "csrf_token": csrf, "expires_at": _timestamp_text(expires),
        "session_token": session_token, "dataset_kind": "demo", "identity_verified_by": "cloudbase_user_me",
        "personal_uploads": False, "agent_paired": False}

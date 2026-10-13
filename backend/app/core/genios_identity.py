"""Native GeniOS intake boundary. Routes require a separately enabled gate.

SYS_USERID is trusted only when a private, dedicated integration authenticates
the call AND the platform hides/fixes that parameter. Neither a browser cookie,
the public MCP token, a display name, nor a DEV locator supplies this principal.
Activation needs a separate credential and accepted platform configuration.
"""
from dataclasses import dataclass
import hashlib
import hmac
import base64
import json
import re
import time
from secrets import compare_digest, token_urlsafe

from app.core.errors import AppError

ISSUER = "nankai-genios-campus-agent-v1"
UID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
DEVICE = re.compile(r"^DEV-[A-Z2-7]{26}$")
KEY = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
IDENTITY_HEADERS = ("platform-user-id", "platform_user_id")
ATTESTATION_HEADER = "platform-attestation"
ATTESTATION_HEADERS = (ATTESTATION_HEADER, "platform_attestation")
ATTESTATION_SECONDS = 600


def _header_values(headers, names):
    # Standard hyphenated names survive gateways which reject underscores.
    # Legacy aliases remain supported, but sending both is ambiguous and denied.
    return [value for name in names for value in headers.getlist(name)]


def _fixed_identity(headers):
    identities = _header_values(headers, IDENTITY_HEADERS)
    if len(identities) != 1:
        raise AppError(401, "AUTH_REQUIRED", "Fixed platform identity header required")
    if headers.get("origin") or headers.get("sec-fetch-site") or headers.get("cookie"):
        raise AppError(403, "FORBIDDEN", "Browser cannot attest platform identity")
    uid = identities[0]
    if not UID.fullmatch(uid) or uid in {"SYS_USERID", "null", "undefined"}:
        raise AppError(422, "VALIDATION_ERROR", "Invalid fixed platform identity")
    return hashlib.sha256((ISSUER + "\0" + uid).encode()).hexdigest()


def issue_native_attestation(identity_hash, dedicated_key, *, now=None):
    """Short-lived server proof, never the private key or an OAuth access token.

    Bridges the platform's mutually exclusive OAuth/Bearer plugin settings.
    Only a separately authenticated, fixed SYS_USERID call may mint this proof.
    Private resource access still requires the real OAuth grant and owner match.
    """
    if not KEY.fullmatch(dedicated_key) or not re.fullmatch(r"[a-f0-9]{64}", identity_hash):
        raise ValueError("Verified native integration required")
    issued = int(time.time()) if now is None else now
    payload = json.dumps({"identity":identity_hash,"iat":issued,
        "exp":issued + ATTESTATION_SECONDS,"nonce":token_urlsafe(24)}, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(dedicated_key.encode(), ("NAT1." + encoded).encode(), hashlib.sha256).hexdigest()
    return "NAT1." + encoded + "." + signature


def _verify_attestation(proof, identity_hash, dedicated_key, *, now=None):
    try:
        if len(proof) > 512:
            raise ValueError
        version, encoded, signature = proof.split(".")
        if version != "NAT1" or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded) or not re.fullmatch(r"[a-f0-9]{64}", signature):
            raise ValueError
        expected = hmac.new(dedicated_key.encode(), ("NAT1." + encoded).encode(), hashlib.sha256).hexdigest()
        if not compare_digest(signature, expected):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)), object_pairs_hook=_unique_object)
        current = int(time.time()) if now is None else now
        if (type(data) is not dict or set(data) != {"identity", "iat", "exp", "nonce"}
                or data["identity"] != identity_hash or type(data["iat"]) is not int or type(data["exp"]) is not int
                or data["exp"] - data["iat"] != ATTESTATION_SECONDS
                or data["iat"] > current + 5 or data["exp"] <= current
                or type(data["nonce"]) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{32}", data["nonce"])):
            raise ValueError
    except (ValueError, TypeError, UnicodeError):
        raise AppError(401, "AUTH_REQUIRED", "Fresh platform attestation required") from None


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedNativeRequest:
    identity_hash: str
    device_code: str
    intent: str
    confirmed: bool


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate property")
        result[name] = value
    return result


def verify_native_headers(headers, dedicated_key: str, other_keys=(), *, credential_header="authorization"):
    """Attest a hidden fixed platform identity with an independent private key."""
    if (not KEY.fullmatch(dedicated_key)
            or any(key and compare_digest(dedicated_key, key) for key in other_keys)):
        raise ValueError("Dedicated native integration credential required")
    # Headers must be a multi-valued mapping (e.g. Starlette Headers). Reject
    # duplicates even if an intermediary otherwise joins or selects a value.
    if credential_header not in {"authorization", "x-campus-native-key"}:
        raise ValueError("Unsupported integration credential header")
    identity_hash = _fixed_identity(headers)
    attestations = _header_values(headers, ATTESTATION_HEADERS)
    if attestations:
        if (credential_header != "x-campus-native-key" or len(attestations) != 1
                or headers.getlist("x-campus-native-key")):
            raise AppError(401, "AUTH_REQUIRED", "Unambiguous platform attestation required")
        _verify_attestation(attestations[0], identity_hash, dedicated_key)
        return identity_hash
    if len(headers.getlist(credential_header)) != 1:
        raise AppError(401, "AUTH_REQUIRED", "Dedicated integration credential header required")
    authorization = headers.get(credential_header, "")
    expected = "Bearer " + dedicated_key if credential_header == "authorization" else dedicated_key
    # Compare fixed-length digests, including unexpected Unicode/header lengths.
    if not compare_digest(hashlib.sha256(authorization.encode()).digest(),
                          hashlib.sha256(expected.encode()).digest()):
        raise AppError(401, "AUTH_REQUIRED", "Dedicated integration credential rejected")
    return identity_hash


def verify_native_request(headers, raw: bytes, dedicated_key: str, other_keys=(), *, credential_header="authorization"):
    """Reject identity/body overrides and require explicit mutation confirmation."""
    identity_hash = verify_native_headers(headers, dedicated_key, other_keys, credential_header=credential_header)
    if (len(headers.getlist("content-type")) != 1
            or headers.get("content-type", "").split(";", 1)[0] != "application/json"):
        raise AppError(422, "VALIDATION_ERROR", "Invalid native content type")
    try:
        if len(raw) > 1024:
            raise ValueError
        body = json.loads(raw, object_pairs_hook=_unique_object)
        if (type(body) is not dict or set(body) != {"device_code", "intent", "confirmed"}
                or type(body["device_code"]) is not str or not DEVICE.fullmatch(body["device_code"])
                or body["intent"] not in {"lookup", "create", "bind"}
                or type(body["confirmed"]) is not bool):
            raise ValueError
    except (ValueError, TypeError, UnicodeError):
        raise AppError(422, "VALIDATION_ERROR", "Invalid native onboarding request") from None
    if body["intent"] != "lookup" and not body["confirmed"]:
        raise AppError(409, "CONFIRMATION_REQUIRED", "Explicit onboarding confirmation required")
    # Independent of the integration key so safe credential rotation cannot
    # change the identity or allocate another account. Never normalize case.
    return VerifiedNativeRequest(identity_hash, **body)


def guard_native_oauth_owner(request, runtime, database):
    """Every private Agent call checks fixed platform identity AND OAuth owner.

    When enabled, old MCP calls lacking the attested headers fail closed. Deploy
    only after the REST OAuth tool replacements are configured and tested.
    """
    if not runtime.cloud_genios_native_identity_enabled:
        return
    from app.core.oauth_local import resource_token
    from app.core.security import secret_hash
    if len(request.headers.getlist("authorization")) != 1:
        raise AppError(401, "AUTH_REQUIRED", "Original account OAuth required")
    identity_hash = verify_native_headers(request.headers, runtime.genios_native_integration_key.get_secret_value(),
        (runtime.mcp_service_token.get_secret_value(),), credential_header="x-campus-native-key")
    try:
        result = database.native_identity_call("verify_grant", {"identity_hash":identity_hash,
            "grant_hash":secret_hash(resource_token(request).get_secret_value()),"audience":runtime.oauth_client_id})
    except AppError as exc:
        if exc.status_code == 401 and exc.code == "AUTH_REQUIRED":
            # The fixed identity/proof above was already verified. A missing,
            # revoked, expired or reset grant is an OAuth token failure, not a
            # new browser-binding request. Let the OAuth client renew consent.
            from app.core.oauth_local import OAuthError
            raise OAuthError("invalid_token", 401) from None
        raise
    if result != {"owner_consistent":True}:
        raise AppError(403, "FORBIDDEN", "Platform account and tool account differ")


def onboarding_decision(principal, mapped_owner, verified_legacy_owner=None):
    """One decision for first use, browser changes and legacy account adoption.

    Both owners MUST come from server-verified storage/authentication, not input.
    A mapping miss is not proof that a historical tool account never existed.
    Existing verified legacy identity is adopted instead of creating a new one.
    """
    if mapped_owner and verified_legacy_owner and mapped_owner != verified_legacy_owner:
        raise AppError(403, "FORBIDDEN", "Account and existing browser space differ")
    if principal.intent == "lookup":
        return "existing_space" if mapped_owner else "confirm_existing_space" if verified_legacy_owner else "confirm_first_use"
    if mapped_owner:
        return "reuse_and_bind" if principal.confirmed else "existing_space"
    if verified_legacy_owner:
        return "adopt_existing_and_bind" if principal.confirmed else "confirm_existing_space"
    if principal.intent == "create" and principal.confirmed:
        return "create_once_and_bind"
    # No silent creation when the user just requested lookup or device binding.
    return "confirm_first_use"

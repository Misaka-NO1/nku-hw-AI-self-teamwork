import json
import pytest
from starlette.datastructures import Headers

from app.core.errors import AppError
from app.core.genios_identity import verify_native_request, onboarding_decision, verify_native_headers, issue_native_attestation

KEY = "fictional_native_integration_key_" + "A" * 32
CODE = "DEV-" + "A" * 26


def verify(body=None, uid="fictional-platform-a", key=KEY, extra=(), raw=None):
    pairs = [("authorization", "Bearer " + key), ("platform_user_id", uid),
             ("content-type", "application/json"), *extra]
    headers = Headers(raw=[(name.encode(), value.encode()) for name, value in pairs])
    return verify_native_request(headers, raw if raw is not None else json.dumps(body or {
        "device_code": CODE, "intent": "lookup", "confirmed": False}).encode(), KEY)


def test_fixed_identity_does_not_depend_on_browser_or_credential_rotation():
    one = verify()
    other = verify({"device_code": "DEV-" + "B" * 26, "intent": "lookup", "confirmed": False})
    assert one.identity_hash == other.identity_hash
    rotated = "fictional_rotated_native_key_" + "B" * 32
    headers = Headers({"authorization": "Bearer " + rotated, "platform_user_id": "fictional-platform-a",
                       "content-type": "application/json"})
    assert verify_native_request(headers, json.dumps({"device_code": CODE, "intent": "lookup",
                                "confirmed": False}).encode(), rotated).identity_hash == one.identity_hash
    assert one.identity_hash != verify(uid="fictional-platform-b").identity_hash
    assert "fictional-platform-a" not in repr(one)


@pytest.mark.parametrize("extra", [[("origin", "https://example.test")],
    [("cookie", "fictional")], [("sec-fetch-site", "same-origin")],
    [("authorization", "Bearer duplicate")], [("platform_user_id", "duplicate")]])
def test_browser_and_duplicate_identity_headers_rejected(extra):
    with pytest.raises(AppError):
        verify(extra=extra)


def test_wrong_service_key_cannot_assert_another_owner():
    with pytest.raises(AppError) as caught:
        verify(uid="fictional-other", key="fictional-other-key")
    assert caught.value.code == "AUTH_REQUIRED"


@pytest.mark.parametrize("uid", ["", "SYS_USERID", "null", "undefined", " user ", "{{SYS_USERID}}", "a" * 129])
def test_unresolved_or_unbounded_user_id_rejected(uid):
    with pytest.raises(AppError):
        verify(uid=uid)


@pytest.mark.parametrize("change", [{"owner": "someone"}, {"user_id": "someone"},
    {"workspace_ref": "space"}, {"confirmed": "true"}, {"intent": ["create"]},
    {"device_code": "public-not-a-dev-code"}])
def test_body_cannot_override_identity_or_consent(change):
    with pytest.raises(AppError):
        verify({"device_code": CODE, "intent": "lookup", "confirmed": False, **change})


def test_duplicate_json_fields_and_oversized_body_rejected():
    for raw in [b'{"confirmed":true,"confirmed":false}', b" " * 1025]:
        with pytest.raises(AppError):
            verify(raw=raw)


def test_dedicated_key_is_required_and_cannot_reuse_existing_keys():
    for key, others in [("", ()), (KEY, (KEY,))]:
        with pytest.raises(ValueError):
            verify_native_request(Headers(), b"{}", key, others)


@pytest.mark.parametrize("intent", ["create", "bind"])
def test_creation_and_binding_require_explicit_confirmation(intent):
    with pytest.raises(AppError) as caught:
        verify({"device_code": CODE, "intent": intent, "confirmed": False})
    assert caught.value.code == "CONFIRMATION_REQUIRED"


def test_existing_account_reuses_space_even_when_new_browser_requests_create():
    request = verify({"device_code": CODE, "intent": "create", "confirmed": True})
    assert onboarding_decision(request, "verified-existing-owner") == "reuse_and_bind"
    assert onboarding_decision(request, None, "verified-existing-owner") == "adopt_existing_and_bind"
    assert onboarding_decision(request, None) == "create_once_and_bind"
    assert onboarding_decision(verify(), None) == "confirm_first_use"
    assert onboarding_decision(verify(), "verified-existing-owner") == "existing_space"
    with pytest.raises(AppError):
        onboarding_decision(request, "owner-a", "owner-b")


def test_signed_attestation_is_scoped_to_fixed_identity_and_not_a_service_login():
    identity = verify().identity_hash
    proof = issue_native_attestation(identity, KEY)
    headers = Headers({"platform_user_id":"fictional-platform-a", "platform_attestation":proof})
    assert verify_native_headers(headers, KEY, credential_header="x-campus-native-key") == identity
    assert KEY not in proof and "fictional-platform-a" not in proof
    with pytest.raises(AppError):
        verify_native_headers(headers, KEY)  # Cannot use proof to mint another proof or enroll.


@pytest.mark.parametrize("change", ["signature", "identity", "key", "duplicate", "both", "browser", "malformed", "too_long"])
def test_attestation_tampering_and_confusion_rejected(change):
    proof = issue_native_attestation(verify().identity_hash, KEY)
    pairs = [("platform_user_id", "fictional-platform-a"), ("platform_attestation", proof)]
    key = KEY
    if change == "signature": pairs[-1] = ("platform_attestation", proof[:-1] + ("0" if proof[-1] != "0" else "1"))
    if change == "identity": pairs[0] = ("platform_user_id", "fictional-platform-b")
    if change == "key": key = "fictional_rotated_native_key_" + "B" * 32
    if change == "duplicate": pairs.append(("platform_attestation", proof))
    if change == "both": pairs.append(("x-campus-native-key", KEY))
    if change == "browser": pairs.append(("origin", "https://example.test"))
    if change == "malformed": pairs[-1] = ("platform_attestation", "NAT1.not.valid")
    if change == "too_long": pairs[-1] = ("platform_attestation", "a" * 513)
    with pytest.raises(AppError):
        verify_native_headers(Headers(raw=[(n.encode(), v.encode()) for n,v in pairs]), key,
                              credential_header="x-campus-native-key")


@pytest.mark.parametrize("issued", [999400, 1000010])
def test_expired_or_future_attestation_rejected(monkeypatch, issued):
    monkeypatch.setattr("app.core.genios_identity.time.time", lambda: 1000000)
    headers = Headers({"platform_user_id":"fictional-platform-a", "platform_attestation":
                       issue_native_attestation(verify().identity_hash, KEY, now=issued)})
    with pytest.raises(AppError):
        verify_native_headers(headers, KEY, credential_header="x-campus-native-key")

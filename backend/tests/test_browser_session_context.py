import base64
import hashlib
import hmac
import json

import pytest

from app.core.browser_session_context import decode_context,encode_context
from app.core.errors import AppError
from app.core.contracts import validate_boundary
from pathlib import Path

TOKEN = "fictional-session-cookie-" + "a" * 32
CSRF = "fictional-csrf-" + "c" * 32


def test_context_is_bound_to_original_cookie_and_exact_expiry():
    value=encode_context(TOKEN,"pilot_workspace_a",CSRF,1900)
    assert decode_context(TOKEN,value,now=1000)=={
        "workspace_ref":"pilot_workspace_a","csrf_token":CSRF,"expires_epoch":1900}
    assert decode_context(TOKEN,value,now=1899)["expires_epoch"]==1900
    with pytest.raises(AppError): decode_context(TOKEN,value,now=1900)
    with pytest.raises(AppError): decode_context(TOKEN+"other",value,now=1000)
    with pytest.raises(AppError): decode_context(TOKEN,value[:-1]+("a" if value[-1]!="a" else "b"),now=1000)


@pytest.mark.parametrize("value",["", ".", "a.b", "x"*2049, "é."+"a"*64, "!!!!."+"a"*64])
def test_context_malformed_cookie_fails_without_disclosing_values(value):
    with pytest.raises(AppError) as error: decode_context(TOKEN,value,now=1000)
    assert error.value.status_code==401 and error.value.code=="AUTH_REQUIRED"
    assert TOKEN not in str(error.value) and CSRF not in str(error.value)


@pytest.mark.parametrize("changes",[
    {"expires_epoch":True}, {"expires_epoch":1931}, {"expires_epoch":999},
    {"workspace_ref":"https://foreign.invalid"}, {"csrf_token":"short"}, {"extra":"owner"},
])
def test_context_invalid_signed_fields_are_not_trusted(changes):
    body={"workspace_ref":"pilot_workspace_a","csrf_token":CSRF,"expires_epoch":1900,**changes}
    encoded=base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    signature=hmac.new(TOKEN.encode(),b"campus-browser-context-v1\x00"+encoded.encode(),hashlib.sha256).hexdigest()
    with pytest.raises(AppError): decode_context(TOKEN,encoded+"."+signature,now=1000)


def test_context_allows_small_pg_app_clock_skew_without_extending_original_expiry():
    value=encode_context(TOKEN,"pilot_workspace_a",CSRF,1905)
    assert decode_context(TOKEN,value,now=1000)["expires_epoch"]==1905
    with pytest.raises(AppError): decode_context(TOKEN,value,now=1905)


def test_browser_session_public_contract_examples():
    fixture=json.loads((Path(__file__).parents[2]/"fixtures/browser-session.demo.json").read_text(encoding="utf-8"))
    validate_boundary(fixture["valid"],"CloudBrowserSession")
    for override in fixture["invalid_overrides"]:
        with pytest.raises(AppError): validate_boundary({**fixture["valid"],**override},"CloudBrowserSession")

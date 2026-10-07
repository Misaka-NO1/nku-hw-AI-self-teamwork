"""Recorded school request *shape*, fake credentials/identity; no live traffic."""
import base64
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from experiments.connection_pairing import CLIENT, digest
from experiments.connection_pairing_http import ORIGIN, create_offline_http
from test_connection_pairing_experiment import FAKE_SECRET, harness, params


@pytest.fixture
def http(harness):
    engine, now, sessions, reads, path, config = harness
    with TestClient(create_offline_http(engine, enabled=True), base_url=ORIGIN) as client:
        yield engine, client, now, sessions, reads


def token(client, *, basic=False, form=False):
    response = client.get("/experiment/authorize", params=params(), follow_redirects=False)
    assert response.status_code == 303
    code = parse_qs(urlsplit(response.headers["Location"]).query)["code"][0]
    values = {"grant_type": "authorization_code", "code": code, "redirect_uri": params()["redirect_uri"]}
    headers = {}
    if basic:
        headers["Authorization"] = "Basic "+base64.b64encode((CLIENT+":"+FAKE_SECRET).encode()).decode()
    else:
        values.update(client_id=CLIENT, client_secret=FAKE_SECRET)
    response = client.post("/experiment/token", **({"data": values} if form else {"json": values}), headers=headers)
    assert response.status_code == 200
    return response.json()["access_token"]


def bearer(raw):
    return {"Authorization": "Bearer "+raw}


@pytest.mark.parametrize("basic,form", [(False, False), (False, True), (True, False), (True, True)])
def test_school_legacy_shape_only_gets_pending_connection(http, basic, form):
    _, client, _, _, reads = http
    raw = token(client, basic=basic, form=form)
    result = client.get("/experiment/records", headers=bearer(raw))
    assert result.status_code == 200
    assert result.json()["data"]["status"] == "pairing_required"
    assert "owner" not in result.text and "records" not in result.json()["data"]
    assert not reads
    assert result.headers["Cache-Control"] == "no-store"


def test_browser_explicit_review_pair_then_agent_owned_read(http):
    _, client, _, sessions, _ = http
    raw = token(client)
    user_code = client.get("/experiment/records", headers=bearer(raw)).json()["data"]["user_code"]
    client.cookies.set("campus_session", "fake-browser-a")
    browser_headers = {"Origin": ORIGIN, "X-CSRF-Token": "fake-csrf"}
    response = client.post("/experiment/pair/review", json={"user_code": user_code}, headers=browser_headers)
    assert response.status_code == 200
    receipt = response.json()["data"]["review_receipt"]
    assert client.get("/experiment/records", headers=bearer(raw)).json()["data"]["status"] == "pairing_required"
    response = client.post("/experiment/pair/approve", json={"review_receipt": receipt, "checked_code": user_code,
                           "confirm_same_agent": True, "confirm_read": True}, headers=browser_headers)
    assert response.status_code == 200
    client.cookies.set("campus_session", "fake-browser-b")
    result = client.get("/experiment/records", headers=bearer(raw))
    assert result.json()["data"]["records"]["fixture"] == "a"
    sessions.pop("fake-browser-a")
    result = client.get("/experiment/records", headers=bearer(raw))
    assert result.status_code == 401 and result.json()["data"] is None


@pytest.mark.parametrize("extra", ["owner", "workspace_ref", "SYS_USERID", "user_id", "token"])
def test_resource_identity_override_parameters_rejected(http, extra):
    _, client, *_ = http
    result = client.get("/experiment/records", params={extra: "fictional"}, headers=bearer(token(client)))
    assert result.status_code == 400 and result.json()["data"] is None


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer wrong", "Bearer "+"a"*43+" extra"])
def test_cookie_cannot_replace_bearer(http, header):
    _, client, *_ = http
    client.cookies.set("campus_session", "fake-browser-a")
    result = client.get("/experiment/records", headers={"Authorization": header} if header else {})
    assert result.status_code == 401


@pytest.mark.parametrize("kwargs", [
    {"content": '{"user_code":"AAAA-BBBB","user_code":"CCCC-DDDD"}', "headers": {"Content-Type":"application/json"}},
    {"json": {"user_code":"AAAA-BBBB", "owner":"fixture-owner-a"}},
    {"content": '{"user_code":', "headers": {"Content-Type":"application/json"}},
    {"content": "x"*8193, "headers": {"Content-Type":"application/json"}},
])
def test_duplicate_extra_malformed_and_oversize_body_rejected(http, kwargs):
    _, client, *_ = http
    result = client.post("/experiment/pair/review", **kwargs)
    assert result.status_code == 400


def test_authorize_duplicate_query_and_writes_without_csrf_rejected(http):
    _, client, *_ = http
    result = client.get("/experiment/authorize", params=list(params().items())+[("state", "anotherstate")], follow_redirects=False)
    assert result.status_code == 400 and "Location" not in result.headers
    user_code = client.get("/experiment/records", headers=bearer(token(client))).json()["data"]["user_code"]
    client.cookies.set("campus_session", "fake-browser-a")
    assert client.post("/experiment/pair/review", json={"user_code": user_code}).status_code == 403


def test_no_refresh_commit_draft_or_public_http_registration(http):
    engine, client, *_ = http
    assert client.post("/experiment/commit", json={}).status_code == 404
    assert client.post("/experiment/task-drafts", json={}).status_code == 404
    assert client.post("/experiment/token", json={"client_id":CLIENT, "client_secret":FAKE_SECRET,
                       "grant_type":"refresh_token", "refresh_token":"fictional"}).status_code == 400
    assert client.get("/experiment/authorize", params=params(), headers={"Host":"public.invalid"}).status_code == 403
    assert client.post("/experiment/token?client_secret=fictional", json={}).status_code == 400


def test_basic_and_body_client_credentials_cannot_mix(http):
    _, client, *_ = http
    auth = "Basic "+base64.b64encode((CLIENT+":"+FAKE_SECRET).encode()).decode()
    result = client.post("/experiment/token", json={"client_id":CLIENT, "client_secret":FAKE_SECRET}, headers={"Authorization":auth})
    assert result.status_code == 401

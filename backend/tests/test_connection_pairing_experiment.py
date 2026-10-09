"""Offline invariant tests, not school/CloudBase acceptance or a public API."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

import pytest

from experiments.connection_pairing import (
    CALLBACK, CLIENT, SCOPE, OfflineConnectionPairing, PairingError,
    VerifiedSession, digest,
)


FAKE_SECRET = "offline-only-fake-client-secret-not-a-credential-12345"


@pytest.fixture
def harness(tmp_path):
    now = [1_800_000_000]
    sessions = {
        "fake-browser-a": VerifiedSession(digest("fake-browser-a"), "fixture-owner-a", "workspace-a", now[0]+900, "nku-demo-a"),
        "fake-browser-b": VerifiedSession(digest("fake-browser-b"), "fixture-owner-b", "workspace-b", now[0]+900, "nku-demo-b"),
    }
    reads = []

    def verify(cookie, csrf, origin):
        if csrf != "fake-csrf" or origin != "http://127.0.0.1:8014":
            raise PairingError("forbidden")
        return sessions.get(cookie)

    def lookup(value):
        return next((s for s in sessions.values() if s.session_hash == value), None)

    def reader(owner, workspace):
        reads.append((owner, workspace))
        return {"dataset_kind": "demo", "fixture": "a" if owner.endswith("a") else "b"}

    config = dict(enabled=True, client_secret_hash=digest(FAKE_SECRET),
                  allowed_owners={"fixture-owner-a", "fixture-owner-b"},
                  verify_browser=verify, lookup_session=lookup, read_records=reader, clock=lambda: now[0])
    path = tmp_path / "offline-pairing.sqlite3"
    engine = OfflineConnectionPairing(path, **config)
    return engine, now, sessions, reads, path, config


def params(**changes):
    return {"client_id": CLIENT, "redirect_uri": CALLBACK, "response_type": "code",
            "scope": SCOPE, "state": "state12345", **changes}


def code(engine):
    url = engine.bootstrap(params())
    assert urlsplit(url).scheme == "https"
    assert parse_qs(urlsplit(url).query)["state"] == ["state12345"]
    return parse_qs(urlsplit(url).query)["code"][0]


def exchange(engine, raw_code=None):
    return engine.exchange(CLIENT, FAKE_SECRET, {"grant_type": "authorization_code",
                           "code": raw_code or code(engine), "redirect_uri": CALLBACK})["access_token"]


def browser(account="a", **changes):
    return {"cookie": "fake-browser-"+account, "csrf": "fake-csrf",
            "origin": "http://127.0.0.1:8014", **changes}


def bind(engine, token, account="a"):
    user_code = engine.records(token)["user_code"]
    review = engine.review(user_code, **browser(account))
    assert review["account_label"] == "nku-demo-"+account
    engine.approve(review["review_receipt"], user_code, **browser(account),
                   confirm_same_agent=True, confirm_read=True)
    return user_code, review


def test_default_disabled_does_not_create_database(harness):
    *_, path, config = harness
    target = path.parent / "disabled.sqlite3"
    with pytest.raises(PairingError, match="prototype_disabled"):
        OfflineConnectionPairing(target, **{**config, "enabled": False})
    assert not target.exists()


@pytest.mark.parametrize("changes", [
    {"scope": "demo:read"}, {"scope": "connection:pair demo:draft"},
    {"owner": "fixture-owner-a"}, {"SYS_USERID": "fixture-owner-a"},
    {"workspace_ref": "workspace-a"}, {"redirect_uri": CALLBACK+"/other"},
    {"redirect_uri": "https://attacker.invalid/callback"},
    {"client_id": "unknown-client"}, {"state": "short"}, {"state": "x\n"*10},
    {"state": 123}, {"response_type": "token"},
])
def test_bootstrap_rejects_identity_data_scopes_and_invalid_callback(harness, changes):
    engine, *_ = harness
    with pytest.raises(PairingError, match="invalid_request"):
        engine.bootstrap(params(**changes))


@pytest.mark.parametrize("client,secret", [("unknown", FAKE_SECRET), (CLIENT, "wrong"*10)])
def test_confidential_exchange_requires_correct_client(harness, client, secret):
    engine, *_ = harness
    with pytest.raises(PairingError, match="invalid_client"):
        engine.exchange(client, secret, {"grant_type": "authorization_code", "code": code(engine), "redirect_uri": CALLBACK})


def test_pending_connection_never_calls_records_reader(harness):
    engine, _, _, reads, *_ = harness
    token = exchange(engine)
    result = engine.records(token)
    assert set(result) == {"status", "user_code", "verification_path", "expires_epoch"}
    assert result["status"] == "pairing_required"
    assert reads == []


def test_code_replay_and_two_connection_race_have_only_one_winner(harness):
    engine, _, _, _, path, config = harness
    another = OfflineConnectionPairing(path, **config)
    raw_code = code(engine)

    def run(instance):
        try:
            return exchange(instance, raw_code)
        except PairingError as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(run, [engine, another]))
    assert results.count("invalid_grant") == 1
    assert len({r for r in results if r != "invalid_grant"}) == 1
    with pytest.raises(PairingError, match="invalid_grant"):
        exchange(engine, raw_code)


def test_injected_anonymous_code_carries_no_other_user_identity(harness):
    engine, _, _, reads, *_ = harness
    attacker_code = code(engine)  # No attacker owner can be encoded here.
    token_at_victim_client = exchange(engine, attacker_code)
    assert engine.records(token_at_victim_client)["status"] == "pairing_required"
    assert reads == []
    with pytest.raises(PairingError, match="invalid_grant"):
        exchange(engine, attacker_code)
    bind(engine, token_at_victim_client, "a")
    assert engine.records(token_at_victim_client)["records"]["fixture"] == "a"


def test_pairing_reads_only_authenticated_owner_and_cannot_rebind(harness):
    engine, *_ = harness
    token_a, token_b = exchange(engine), exchange(engine)
    code_a, _ = bind(engine, token_a, "a")
    bind(engine, token_b, "b")
    assert engine.records(token_a)["records"]["fixture"] == "a"
    assert engine.records(token_b)["records"]["fixture"] == "b"
    with pytest.raises(PairingError, match="invalid_pairing"):
        engine.review(code_a, **browser("b"))
    assert engine.records(token_a)["records"]["fixture"] == "a"


@pytest.mark.parametrize("changes,error", [
    ({"csrf": "wrong"}, "forbidden"), ({"origin": "https://attacker.invalid"}, "forbidden"),
    ({"cookie": "unknown"}, "auth_required"),
])
def test_review_requires_verified_browser_and_csrf(harness, changes, error):
    engine, *_ = harness
    user_code = engine.records(exchange(engine))["user_code"]
    with pytest.raises(PairingError, match=error):
        engine.review(user_code, **browser(**changes))


def test_review_does_not_authorize_and_receipt_cannot_cross_browser(harness):
    engine, _, _, reads, *_ = harness
    token = exchange(engine)
    user_code = engine.records(token)["user_code"]
    review = engine.review(user_code, **browser())
    assert engine.records(token)["status"] == "pairing_required" and not reads
    with pytest.raises(PairingError, match="invalid_review"):
        engine.approve(review["review_receipt"], user_code, **browser("b"), confirm_same_agent=True, confirm_read=True)


@pytest.mark.parametrize("same,read", [(False, True), (True, False), ("true", True), (True, 1)])
def test_explicit_pairing_and_read_consent_required(harness, same, read):
    engine, *_ = harness
    token = exchange(engine)
    user_code = engine.records(token)["user_code"]
    review = engine.review(user_code, **browser())
    with pytest.raises(PairingError, match="consent_required"):
        engine.approve(review["review_receipt"], user_code, **browser(), confirm_same_agent=same, confirm_read=read)
    assert engine.records(token)["status"] == "pairing_required"


def test_receipt_replay_and_wrong_displayed_code_rejected(harness):
    engine, *_ = harness
    token = exchange(engine)
    user_code = engine.records(token)["user_code"]
    review = engine.review(user_code, **browser())
    with pytest.raises(PairingError, match="invalid_pairing"):
        engine.approve(review["review_receipt"], "AAAA-BBBB", **browser(), confirm_same_agent=True, confirm_read=True)
    engine.approve(review["review_receipt"], user_code, **browser(), confirm_same_agent=True, confirm_read=True)
    with pytest.raises(PairingError, match="invalid_review"):
        engine.approve(review["review_receipt"], user_code, **browser(), confirm_same_agent=True, confirm_read=True)


def test_two_review_connections_cannot_bind_same_token_to_two_owners(harness):
    engine, _, _, _, path, config = harness
    token = exchange(engine)
    user_code = engine.records(token)["user_code"]
    a, b = engine.review(user_code, **browser()), engine.review(user_code, **browser("b"))
    another = OfflineConnectionPairing(path, **config)

    def run(args):
        instance, review, account = args
        try:
            instance.approve(review["review_receipt"], user_code, **browser(account), confirm_same_agent=True, confirm_read=True)
            return account
        except PairingError as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(run, [(engine, a, "a"), (another, b, "b")]))
    assert results.count("invalid_pairing") == 1
    assert engine.records(token)["records"]["fixture"] == next(x for x in results if x != "invalid_pairing")


def test_guess_attempts_survive_rollback_and_session_rotation(harness):
    engine, _, sessions, *_ = harness
    for _ in range(5):
        with pytest.raises(PairingError, match="invalid_pairing"):
            engine.review("AAAA-BBBB", **browser())
    old = sessions["fake-browser-a"]
    sessions["fake-browser-a"] = VerifiedSession(digest("rotated-a"), old.owner, old.workspace, old.expires, old.label)
    with pytest.raises(PairingError, match="rate_limited"):
        engine.review("AAAA-BBBB", **browser())


def test_expiry_bootstrap_pairing_review_and_active_grant(harness):
    engine, now, *_ = harness
    expired_code = code(engine)
    now[0] += 90
    with pytest.raises(PairingError, match="invalid_grant"):
        exchange(engine, expired_code)
    token = exchange(engine)
    user_code = engine.records(token)["user_code"]
    review = engine.review(user_code, **browser())
    now[0] += 60
    with pytest.raises(PairingError, match="invalid_review"):
        engine.approve(review["review_receipt"], user_code, **browser(), confirm_same_agent=True, confirm_read=True)
    now[0] += 240
    with pytest.raises(PairingError, match="pairing_expired"):
        engine.records(token)
    token = exchange(engine)
    bind(engine, token)
    now[0] += 600
    with pytest.raises(PairingError, match="invalid_token"):
        engine.records(token)


def test_logout_kills_reads_and_other_browser_cannot_switch_token_owner(harness):
    engine, _, sessions, *_ = harness
    token = exchange(engine)
    bind(engine, token)
    sessions.pop("fake-browser-a")
    with pytest.raises(PairingError, match="auth_required"):
        engine.records(token)


def test_restart_persists_binding_and_revoke(harness):
    engine, _, _, _, path, config = harness
    token = exchange(engine)
    bind(engine, token)
    another = OfflineConnectionPairing(path, **config)
    assert another.records(token)["records"]["fixture"] == "a"
    another.revoke(CLIENT, FAKE_SECRET, token)
    with pytest.raises(PairingError, match="invalid_token"):
        engine.records(token)


def test_plaintext_connection_secrets_not_stored(harness):
    engine, _, _, _, path, _ = harness
    raw_code = code(engine)
    token = exchange(engine, raw_code)
    user_code, review = bind(engine, token)
    with sqlite3.connect(path) as db:
        dump = "\n".join(db.iterdump())
    for raw in [raw_code, token, user_code.replace("-", ""), review["review_receipt"], FAKE_SECRET, "fake-csrf"]:
        assert raw not in dump


def test_dependency_failure_never_falls_back_to_demo_or_leaks_error(harness):
    engine, *_ = harness
    token = exchange(engine)
    bind(engine, token)

    def failed(_):
        raise RuntimeError("pretend-secret-should-not-be-exposed")

    engine.lookup_session = failed
    with pytest.raises(PairingError, match="^dependency_unavailable$"):
        engine.records(token)

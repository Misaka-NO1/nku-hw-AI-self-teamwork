"""OFFLINE ONLY: anonymous connection bootstrap, followed by browser pairing.

This is not an OAuth replacement or a cloud deployment. No HTTP routes are
registered. Existing PKCE providers remain untouched. SQLite only models the
transaction invariants; CloudBase PG, shared abuse control and platform token
storage still require separate implementation and actual acceptance.
"""
import base64
import hashlib
import re
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode


CALLBACK = "https://coze.nankai.edu.cn/product/llm/info/oauth"
CLIENT = "offline-connection-pairing-test"
SCOPE = "connection:pair"


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def display_code(token):
    raw = hashlib.sha256(("offline-pair-code-v1:" + token).encode()).digest()
    code = base64.b32encode(raw).decode("ascii")[:8]
    return code[:4] + "-" + code[4:]


def normalize_code(code):
    if not isinstance(code, str) or not re.fullmatch(r"[A-Z2-7]{4}-?[A-Z2-7]{4}", code):
        raise PairingError("invalid_pairing")
    return code.replace("-", "")


class PairingError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)  # Never include input, credentials or owner data.


@dataclass(frozen=True)
class VerifiedSession:
    """Must come from a trusted verifier, never request JSON/SYS_USERID."""
    session_hash: str
    owner: str
    workspace: str
    expires: int
    label: str


class OfflineConnectionPairing:
    def __init__(self, database: Path, *, enabled=False, client_secret_hash,
                 allowed_owners, verify_browser, lookup_session, read_records, clock):
        if not enabled:
            raise PairingError("prototype_disabled")
        if len(allowed_owners) != 2 or not re.fullmatch(r"[a-f0-9]{64}", client_secret_hash):
            raise PairingError("invalid_configuration")
        self.database = database
        self.client_secret_hash = client_secret_hash
        self.allowed_owners = frozenset(allowed_owners)
        self.verify_browser = verify_browser
        self.lookup_session = lookup_session
        self.read_records = read_records
        self.clock = clock
        with self.tx() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS bootstrap_codes (
                    code_hash TEXT PRIMARY KEY, expires INTEGER NOT NULL,
                    consumed INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS connections (
                    token_hash TEXT PRIMARY KEY, user_code_hash TEXT UNIQUE NOT NULL,
                    expires INTEGER NOT NULL, pairing_expires INTEGER NOT NULL,
                    owner TEXT, session_hash TEXT, active_expires INTEGER,
                    revoked INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS reviews (
                    receipt_hash TEXT PRIMARY KEY, token_hash TEXT NOT NULL,
                    session_hash TEXT NOT NULL, owner TEXT NOT NULL,
                    expires INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS attempts (
                    session_hash TEXT PRIMARY KEY, started INTEGER NOT NULL,
                    count INTEGER NOT NULL);
            """)

    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.database, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            if db.in_transaction:
                db.commit()
        except Exception:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def authenticate(self, client_id, secret):
        if (client_id != CLIENT or not isinstance(secret, str) or not 40 <= len(secret) <= 256
                or not secrets.compare_digest(digest(secret), self.client_secret_hash)):
            raise PairingError("invalid_client")

    def bootstrap(self, params):
        # Deliberately NO user/cookie/owner argument and no personal-data scope.
        # A short school state is echoed, not treated as proof of user identity.
        if (not isinstance(params, dict) or any(not isinstance(v, str) or len(v)>2048 for v in params.values())
                or set(params) != {"client_id", "redirect_uri", "response_type", "scope", "state"}
                or params["client_id"] != CLIENT or params["redirect_uri"] != CALLBACK
                or params["response_type"] != "code" or params["scope"] != SCOPE
                or not re.fullmatch(r"[A-Za-z0-9._~-]{8,256}", params["state"])):
            raise PairingError("invalid_request")
        code = secrets.token_urlsafe(32)
        with self.tx() as db:
            if db.execute("SELECT COUNT(*) FROM bootstrap_codes WHERE consumed=0 AND expires>?",
                          (self.clock(),)).fetchone()[0] >= 100:
                raise PairingError("temporarily_unavailable")
            db.execute("INSERT INTO bootstrap_codes VALUES (?,?,0)", (digest(code), self.clock()+90))
        return CALLBACK + "?" + urlencode({"code": code, "state": params["state"]})

    def exchange(self, client_id, secret, params):
        self.authenticate(client_id, secret)
        if (not isinstance(params, dict) or any(not isinstance(v, str) or len(v)>2048 for v in params.values())
                or set(params) != {"grant_type", "code", "redirect_uri"}
                or params["grant_type"] != "authorization_code"
                or params["redirect_uri"] != CALLBACK):
            raise PairingError("invalid_request")
        now = self.clock()
        token = secrets.token_urlsafe(32)
        with self.tx() as db:
            row = db.execute("SELECT * FROM bootstrap_codes WHERE code_hash=?", (digest(params["code"]),)).fetchone()
            if row is None or row["consumed"] or row["expires"] <= now:
                raise PairingError("invalid_grant")
            db.execute("UPDATE bootstrap_codes SET consumed=1 WHERE code_hash=?", (digest(params["code"]),))
            db.execute("INSERT INTO connections(token_hash,user_code_hash,expires,pairing_expires) VALUES (?,?,?,?)",
                       (digest(token), digest(normalize_code(display_code(token))), now+600, now+300))
        # Pending connection only: no owner, no data, no refresh token.
        return {"access_token": token, "token_type": "Bearer", "expires_in": 600, "scope": SCOPE}

    def connection(self, db, token):
        row = db.execute("SELECT * FROM connections WHERE token_hash=?", (digest(token),)).fetchone()
        if row is None or row["revoked"] or row["expires"] <= self.clock():
            raise PairingError("invalid_token")
        return row

    def trusted(self, session):
        if (not isinstance(session, VerifiedSession) or session.owner not in self.allowed_owners
                or session.expires <= self.clock() or not re.fullmatch(r"[a-f0-9]{64}", session.session_hash)):
            raise PairingError("auth_required")
        return session

    def browser(self, cookie, csrf, origin):
        try:
            return self.trusted(self.verify_browser(cookie, csrf, origin))
        except PairingError:
            raise
        except Exception:
            raise PairingError("dependency_unavailable") from None

    def limit_review(self, session):
        # Commit attempts separately so invalid guesses cannot roll back them.
        now = self.clock()
        bucket = digest("review-owner:" + session.owner)
        with self.tx() as db:
            row = db.execute("SELECT * FROM attempts WHERE session_hash=?", (bucket,)).fetchone()
            if row is not None and row["started"]+300 > now and row["count"] >= 5:
                raise PairingError("rate_limited")
            started, count = (row["started"], row["count"]+1) if row is not None and row["started"]+300 > now else (now, 1)
            db.execute("INSERT INTO attempts VALUES (?,?,?) ON CONFLICT(session_hash) DO UPDATE SET started=excluded.started,count=excluded.count",
                       (bucket, started, count))

    def review(self, user_code, *, cookie, csrf, origin):
        session = self.browser(cookie, csrf, origin)
        self.limit_review(session)
        code = normalize_code(user_code)
        now = self.clock()
        receipt = secrets.token_urlsafe(32)
        with self.tx() as db:
            row = db.execute("SELECT * FROM connections WHERE user_code_hash=?", (digest(code),)).fetchone()
            if row is None or row["owner"] is not None or row["revoked"] or row["pairing_expires"] <= now or row["expires"] <= now:
                raise PairingError("invalid_pairing")
            expiry = min(now+60, session.expires, row["pairing_expires"])
            db.execute("INSERT INTO reviews VALUES (?,?,?,?,?,0)",
                       (digest(receipt), row["token_hash"], session.session_hash, session.owner, expiry))
        return {"review_receipt": receipt, "user_code": display_code_from_normalized(code),
                "account_label": session.label, "permission": "read_own_fixed_demo_records",
                "expires_epoch": expiry, "warning": "Only enter the code shown in your own current Agent session; never a code sent by another person."}

    def approve(self, receipt, checked_code, *, cookie, csrf, origin, confirm_same_agent, confirm_read):
        session = self.browser(cookie, csrf, origin)
        if confirm_same_agent is not True or confirm_read is not True:
            raise PairingError("consent_required")
        code = normalize_code(checked_code)
        now = self.clock()
        with self.tx() as db:
            review = db.execute("SELECT * FROM reviews WHERE receipt_hash=?", (digest(receipt),)).fetchone()
            if (review is None or review["used"] or review["expires"] <= now
                    or review["session_hash"] != session.session_hash or review["owner"] != session.owner):
                raise PairingError("invalid_review")
            row = db.execute("SELECT * FROM connections WHERE token_hash=?", (review["token_hash"],)).fetchone()
            if (row is None or row["owner"] is not None or row["revoked"] or row["expires"] <= now
                    or row["pairing_expires"] <= now or row["user_code_hash"] != digest(code)):
                raise PairingError("invalid_pairing")
            expiry = min(row["expires"], now+600, session.expires)
            db.execute("UPDATE connections SET owner=?,session_hash=?,active_expires=? WHERE token_hash=?",
                       (session.owner, session.session_hash, expiry, row["token_hash"]))
            db.execute("UPDATE reviews SET used=1 WHERE receipt_hash=?", (digest(receipt),))
        return {"status": "paired", "permission": "read_own_fixed_demo_records", "expires_epoch": expiry}

    def records(self, token):
        with self.tx() as db:
            row = self.connection(db, token)
            if row["owner"] is None:
                if row["pairing_expires"] <= self.clock():
                    raise PairingError("pairing_expired")
                return {"status": "pairing_required", "user_code": display_code(token),
                        "verification_path": "/tools/connection-pair", "expires_epoch": row["pairing_expires"]}
            if row["active_expires"] <= self.clock():
                raise PairingError("invalid_token")
            try:
                session = self.trusted(self.lookup_session(row["session_hash"]))
            except PairingError:
                raise
            except Exception:
                raise PairingError("dependency_unavailable") from None
            if session.owner != row["owner"] or session.session_hash != row["session_hash"]:
                raise PairingError("auth_required")
            try:
                result = self.read_records(session.owner, session.workspace)
            except Exception:
                raise PairingError("dependency_unavailable") from None
            return {"status": "ready", "records": result}

    def revoke(self, client_id, secret, token):
        self.authenticate(client_id, secret)
        with self.tx() as db:
            db.execute("UPDATE connections SET revoked=1 WHERE token_hash=?", (digest(token),))


def display_code_from_normalized(code):
    return code[:4] + "-" + code[4:]

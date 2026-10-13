"""Read one observed school JSON attachment, without browser/session credentials.

Standalone stdlib-only workflow code. Nothing here confirms or saves a report.
The injected downloader is for local tests, not a model-provided parameter.
"""
import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal


MAX_BYTES = 131072
SOCKET_TIMEOUT_SECONDS = 5
TOTAL_TIMEOUT_SECONDS = 15
HOST = "coze.nankai.edu.cn"
QUERY_FIELDS = {"Action", "Filename", "Key", "Path"}
REPORT_FIELDS = {"schema_version", "kind", "program", "cohort", "summary", "modules", "has_in_progress_courses"}
SUMMARY_FIELDS = {"required_credits", "completed_credits", "actual_credits", "reported_result", "reviewed_at", "note"}
MODULE_REQUIRED = {"title", "required_credits", "school_actual_credits", "school_status", "school_note"}
MODULE_OPTIONAL = {"school_in_progress_credits", "school_direct_in_progress_credits"}
ERROR_CODES = {"INVALID_ATTACHMENT_URL", "ATTACHMENT_UNAVAILABLE", "INVALID_ATTACHMENT_RESPONSE",
               "ATTACHMENT_TOO_LARGE", "ATTACHMENT_TIMEOUT", "INVALID_DEGREE_REPORT",
               "INVALID_DEGREE_JSON", "INVALID_ATTACHMENT_INPUT"}


class AttachmentReadError(ValueError):
    """Only fixed, public error codes; never include URL, key, or file contents."""

    def __init__(self, code):
        super().__init__(code if code in ERROR_CODES else "ATTACHMENT_UNAVAILABLE")


def _fail(code):
    raise AttachmentReadError(code) from None


def _unsafe_characters(value):
    return "\\" in value or any(unicodedata.category(c) in {"Cc", "Cf"} for c in value)


def validate_attachment_url(value):
    if (type(value) is not str or not value or len(value) > 8192 or _unsafe_characters(value)
            or any(c.isspace() for c in value) or "#" in value
            or re.search(r"%(?![0-9a-fA-F]{2})", value)):
        _fail("INVALID_ATTACHMENT_URL")
    try:
        parsed = urllib.parse.urlsplit(value)
        if (parsed.scheme != "https" or parsed.hostname != HOST or parsed.port not in (None, 443)
                or parsed.username is not None or parsed.password is not None
                or parsed.path != "/api/proxy/down" or parsed.fragment):
            _fail("INVALID_ATTACHMENT_URL")
        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True,
                                       encoding="utf-8", errors="strict")
        if len(pairs) != 4 or {key for key, _ in pairs} != QUERY_FIELDS:
            _fail("INVALID_ATTACHMENT_URL")
        query = dict(pairs)
        if any(not item or _unsafe_characters(item) for item in query.values()):
            _fail("INVALID_ATTACHMENT_URL")
        filename = query["Filename"]
        if (query["Action"] != "DownloadForPresign" or not filename.endswith(".json")
                or not 6 <= len(filename) <= 255 or "/" in filename or filename.startswith(".")
                or len(query["Key"]) > 4096
                or not re.fullmatch(r"upload/full/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{60}", query["Path"])):
            _fail("INVALID_ATTACHMENT_URL")
        return value
    except (ValueError, UnicodeError):
        _fail("INVALID_ATTACHMENT_URL")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download_attachment(url):
    """Bounded HTTPS GET; school login/redirects fail rather than borrow cookies."""
    validate_attachment_url(url)
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    # Disable environment proxy credentials; do not install cookie/auth handlers.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    started = time.monotonic()
    try:
        with opener.open(request, timeout=SOCKET_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                _fail("ATTACHMENT_UNAVAILABLE")
            if response.headers.get("Content-Encoding", "identity").strip().lower() not in ("", "identity"):
                _fail("INVALID_ATTACHMENT_RESPONSE")
            length = response.headers.get("Content-Length")
            if length is not None:
                if not re.fullmatch(r"[0-9]{1,12}", length):
                    _fail("INVALID_ATTACHMENT_RESPONSE")
                if int(length) > MAX_BYTES:
                    _fail("ATTACHMENT_TOO_LARGE")
            body = bytearray()
            # HTTPResponse.read1 performs at most one underlying read, so the
            # overall deadline can be checked even when bytes trickle in.
            read = response.read1
            while True:
                if time.monotonic() - started >= TOTAL_TIMEOUT_SECONDS:
                    _fail("ATTACHMENT_TIMEOUT")
                chunk = read(min(4096, MAX_BYTES + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    _fail("ATTACHMENT_TOO_LARGE")
            if time.monotonic() - started >= TOTAL_TIMEOUT_SECONDS:
                _fail("ATTACHMENT_TIMEOUT")
            if length is not None and len(body) != int(length):
                _fail("INVALID_ATTACHMENT_RESPONSE")
            return bytes(body)
    except AttachmentReadError:
        raise
    except TimeoutError:
        _fail("ATTACHMENT_TIMEOUT")
    except urllib.error.HTTPError as error:
        error.close()
        _fail("ATTACHMENT_UNAVAILABLE")
    except Exception:
        # HTTPError (including 302/401/403), TLS and transport errors contain
        # request URLs in their messages. Never return or log those messages.
        _fail("ATTACHMENT_UNAVAILABLE")


def _text(value, nullable=False):
    return value is None and nullable or type(value) is str and 1 <= len(value) <= 300


def _credit(value, nullable=False):
    return value is None and nullable or (type(value) is str
        and re.fullmatch(r"(?:0|[1-9]\d{0,2})(?:\.\d{1,2})?", value) is not None and Decimal(value) <= 300)


def _validate_report(report):
    if (type(report) is not dict or set(report) != REPORT_FIELDS
            or report["schema_version"] != "1.0.0" or report["kind"] != "degree_credit_progress"
            or not _text(report["program"], True) or not _text(report["cohort"], True)
            or type(report["has_in_progress_courses"]) is not bool):
        _fail("INVALID_DEGREE_REPORT")
    summary = report["summary"]
    if type(summary) is not dict or set(summary) != SUMMARY_FIELDS:
        _fail("INVALID_DEGREE_REPORT")
    if (any(not _credit(summary[key], True) for key in ("required_credits", "completed_credits", "actual_credits"))
            or any(not _text(summary[key], True) for key in ("reported_result", "reviewed_at", "note"))):
        _fail("INVALID_DEGREE_REPORT")
    modules = report["modules"]
    if type(modules) is not list or not 1 <= len(modules) <= 200:
        _fail("INVALID_DEGREE_REPORT")
    for item in modules:
        if (type(item) is not dict or not MODULE_REQUIRED <= set(item)
                or set(item) - MODULE_REQUIRED - MODULE_OPTIONAL
                or not _text(item["title"])
                or any(not _credit(item[key]) for key in ("required_credits", "school_actual_credits"))
                or any(not _text(item[key], True) for key in ("school_status", "school_note"))
                or any(not _credit(item.get(key), True) for key in MODULE_OPTIONAL)):
            _fail("INVALID_DEGREE_REPORT")
        total, direct = item.get("school_in_progress_credits"), item.get("school_direct_in_progress_credits")
        if (total is not None and Decimal(total) > Decimal(item["school_actual_credits"])) or (
                direct is not None and (total is None or Decimal(direct) > Decimal(total))):
            _fail("INVALID_DEGREE_REPORT")


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("INVALID_DEGREE_JSON")
        result[key] = value
    return result


def _no_constants(_value):
    _fail("INVALID_DEGREE_JSON")


def read_degree_attachment(attachment_url, downloader=None):
    url = validate_attachment_url(attachment_url)
    try:
        body = (downloader or download_attachment)(url)
    except AttachmentReadError:
        raise
    except Exception:
        _fail("ATTACHMENT_UNAVAILABLE")
    if type(body) is not bytes:
        _fail("INVALID_ATTACHMENT_RESPONSE")
    if len(body) > MAX_BYTES:
        _fail("ATTACHMENT_TOO_LARGE")
    try:
        text = body.decode("utf-8", errors="strict")
        # Preserve the original text exactly. Do not unwrap fences, strip BOM,
        # summarize, splice multiple files or reconstruct truncated content.
        report = json.loads(text, object_pairs_hook=_unique_pairs, parse_constant=_no_constants)
        _validate_report(report)
        canonical = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return {"report_json": text, "module_count": len(report["modules"]), "payload_hash": digest}
    except AttachmentReadError:
        raise
    except (ValueError, TypeError, RecursionError):
        _fail("INVALID_DEGREE_JSON")


def handler(params):
    """School Python node: one attachment_url input and one result string output."""
    try:
        if type(params) is not dict or set(params) != {"attachment_url"}:
            _fail("INVALID_ATTACHMENT_INPUT")
        result = {"ok": True, **read_degree_attachment(params["attachment_url"]), "error": None}
    except AttachmentReadError as error:
        result = {"ok": False, "report_json": None, "module_count": 0,
                  "payload_hash": None, "error": str(error)}
    except Exception:
        result = {"ok": False, "report_json": None, "module_count": 0,
                  "payload_hash": None, "error": "ATTACHMENT_UNAVAILABLE"}
    return {"result": json.dumps(result, ensure_ascii=False, separators=(",", ":"))}

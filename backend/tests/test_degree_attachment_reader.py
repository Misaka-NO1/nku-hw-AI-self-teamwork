"""Offline-only school reader tests; every response and URL key is synthetic."""
import importlib.util
import json
from pathlib import Path
import urllib.error
from urllib.parse import urlencode

import pytest

from app.core.degree_progress import agent_report
from app.core.security import payload_hash


ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "deploy/genios-workflows/degree_attachment_reader.py"
SPEC = importlib.util.spec_from_file_location("degree_attachment_reader", FILE)
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)
BODY = (ROOT / "fixtures/degree/degree-progress-attachment.demo.json").read_bytes()
EXPECTED_HASH = "2d1c9647b57ccb9a951278ad663ba9661f8fe0e0c657ef6b674e4fe10f03abcc"
QUERY = {"Action": "DownloadForPresign", "Filename": "degree-progress-attachment.demo.json",
         "Key": "synthetic-opaque-key", "Path": "upload/full/04/a1/b0a452e3900c6700c9d644995d75bb34915018f78658e2ea73845ea152e5"}
BASE = "https://coze.nankai.edu.cn/api/proxy/down"


def url(**changes):
    return BASE + "?" + urlencode({**QUERY, **changes})


def test_full_attachment_is_preserved_and_hash_matches_backend():
    called = []
    result = reader.read_degree_attachment(url(), downloader=lambda value: called.append(value) or BODY)
    assert called == [url()]
    assert result["report_json"] == BODY.decode("utf-8")
    assert result["module_count"] == 31
    assert result["payload_hash"] == EXPECTED_HASH
    assert result["payload_hash"] == payload_hash(agent_report({"report_json": result["report_json"]}))
    assert set(result) == {"report_json", "module_count", "payload_hash"}


def test_optional_absent_fields_and_json_spacing_match_backend_normalization():
    source = json.loads(BODY)
    for item in source["modules"]:
        item.pop("school_in_progress_credits")
        item.pop("school_direct_in_progress_credits")
    raw = json.dumps(source, ensure_ascii=True, sort_keys=True).encode("utf-8")
    result = reader.read_degree_attachment(url(), downloader=lambda _: raw)
    assert result["report_json"] == raw.decode("utf-8")
    assert result["payload_hash"] == payload_hash(agent_report({"report_json": result["report_json"]}))


@pytest.mark.parametrize("value", [
    None, "", " " + url(), url() + "\n", url() + "#", url() + "#section",
    url().replace("https:", "http:"), url().replace("coze.nankai.edu.cn", "evil.invalid"),
    url().replace("coze.nankai.edu.cn", "coze.nankai.edu.cn.evil.invalid"),
    url().replace("coze.nankai.edu.cn", "coze.nankai.edu.cn."),
    url().replace("coze.nankai.edu.cn", "user@coze.nankai.edu.cn"),
    url().replace("coze.nankai.edu.cn", "coze.nankai.edu.cn:444"),
    url().replace("/api/proxy/down", "/api/proxy/other"),
    url().replace("/api/proxy/down", "/api/proxy/down/"),
    url() + "&Action=DownloadForPresign", url() + "&Other=extra", url(Key=""),
    url(Action="Other"), url(Filename="../report.json"), url(Filename="report.txt"),
    url(Filename="report\\file.json"), url(Filename="report\n.json"), url(Key="secret\r\ncookie"),
    url(Path="upload/full/04/a1/" + "a" * 64), url(Path="upload/full/04/a1/" + "G" * 60),
    url().replace("Filename=", "Filename=%GG"), url() + "&Filename=x.json",
    url().replace("Path=", "Path=%FF"), url(Key="x" * 9000),
])
def test_invalid_urls_are_rejected_before_any_download(value):
    def no_download(_):
        pytest.fail("Invalid URL reached downloader")
    with pytest.raises(reader.AttachmentReadError) as error:
        reader.read_degree_attachment(value, downloader=no_download)
    assert str(error.value) == "INVALID_ATTACHMENT_URL"


def test_exact_host_default_port_and_encoded_chinese_filename_are_allowed():
    value = url(Filename="学分报告 (6).json").replace("coze.nankai.edu.cn/", "coze.nankai.edu.cn:443/")
    assert reader.validate_attachment_url(value) == value


class Response:
    def __init__(self, body=BODY, status=200, headers=None):
        self.body, self.status, self.offset = body, status, 0
        self.headers = {} if headers is None else headers
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def read1(self, amount):
        value = self.body[self.offset:self.offset + amount]
        self.offset += len(value)
        return value


def mock_transport(monkeypatch, response=None, exception=None):
    calls = {}

    class Opener:
        def open(self, request, timeout):
            calls.update(request=request, timeout=timeout)
            if exception:
                raise exception
            return response

    def build(*handlers):
        calls["handlers"] = handlers
        return Opener()

    monkeypatch.setattr(reader.urllib.request, "build_opener", build)
    return calls


def test_stdlib_transport_has_no_credentials_proxy_or_redirects(monkeypatch):
    response = Response(headers={"Content-Length": str(len(BODY))})
    calls = mock_transport(monkeypatch, response)
    assert reader.download_attachment(url()) == BODY
    assert response.closed
    assert calls["timeout"] == 5
    assert calls["request"].get_method() == "GET"
    assert dict(calls["request"].header_items()) == {"Accept": "application/json"}
    proxy, redirect = calls["handlers"]
    assert proxy.proxies == {}
    assert redirect.redirect_request(None, None, 302, "", {}, "https://evil.invalid") is None


@pytest.mark.parametrize("exception", [
    urllib.error.HTTPError(url(), 302, "login redirect with synthetic key", {}, None),
    urllib.error.HTTPError(url(), 401, "school session required", {}, None),
    urllib.error.HTTPError(url(), 403, "expired attachment", {}, None),
    urllib.error.URLError("transport error exposing " + url()),
])
def test_login_redirect_or_expired_link_fails_without_cookie_recovery(monkeypatch, exception, capsys):
    mock_transport(monkeypatch, exception=exception)
    result = json.loads(reader.handler({"attachment_url": url()})["result"])
    assert result == {"ok": False, "report_json": None, "module_count": 0,
                      "payload_hash": None, "error": "ATTACHMENT_UNAVAILABLE"}
    assert "synthetic-opaque-key" not in json.dumps(result)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("response, expected", [
    (Response(status=302), "ATTACHMENT_UNAVAILABLE"),
    (Response(headers={"Content-Encoding": "gzip"}), "INVALID_ATTACHMENT_RESPONSE"),
    (Response(headers={"Content-Length": "unknown"}), "INVALID_ATTACHMENT_RESPONSE"),
    (Response(headers={"Content-Length": str(len(BODY) + 1)}), "INVALID_ATTACHMENT_RESPONSE"),
    (Response(headers={"Content-Length": str(reader.MAX_BYTES + 1)}), "ATTACHMENT_TOO_LARGE"),
    (Response(b" " * (reader.MAX_BYTES + 1)), "ATTACHMENT_TOO_LARGE"),
])
def test_transport_limits_are_applied_without_truncating_a_report(monkeypatch, response, expected):
    mock_transport(monkeypatch, response)
    with pytest.raises(reader.AttachmentReadError, match=expected):
        reader.download_attachment(url())
    assert response.closed


def test_overall_and_socket_timeout_have_static_errors(monkeypatch):
    response = Response()
    mock_transport(monkeypatch, response)
    ticks = iter([0, 0, 16])
    monkeypatch.setattr(reader.time, "monotonic", lambda: next(ticks))
    with pytest.raises(reader.AttachmentReadError, match="ATTACHMENT_TIMEOUT"):
        reader.download_attachment(url())
    assert response.closed
    monkeypatch.setattr(reader.time, "monotonic", lambda: 0)
    mock_transport(monkeypatch, exception=TimeoutError("request " + url()))
    with pytest.raises(reader.AttachmentReadError, match="ATTACHMENT_TIMEOUT"):
        reader.download_attachment(url())


@pytest.mark.parametrize("body", [
    b"", b"<html>school login</html>", b"\xff", b"\xef\xbb\xbf" + BODY,
    BODY[:500], b"```json\n" + BODY + b"\n```", json.dumps(BODY.decode()).encode(),
    BODY.replace(b'"schema_version":', b'"schema_version":"1.0.0","schema_version":', 1),
    BODY.replace(b'"cohort": "2025"', b'"cohort": NaN'),
    BODY.replace(b'"cohort": "2025"', b'"cohort": Infinity'),
    b"[" * 10000,
])
def test_invalid_utf8_json_or_unavailable_full_text_is_not_reconstructed(body):
    with pytest.raises(reader.AttachmentReadError, match="INVALID_DEGREE_(JSON|REPORT)"):
        reader.read_degree_attachment(url(), downloader=lambda _: body)


@pytest.mark.parametrize("change", [
    lambda x: x.update(kind="degree_completion_snapshot"), lambda x: x.update(schema_version="2.0.0"),
    lambda x: x.update(modules=[]), lambda x: x.update(modules=x["modules"] * 7),
    lambda x: x.update(owner_id="untrusted"), lambda x: x.update(courses=[]),
    lambda x: x["modules"][0].update(grade="85"),
    lambda x: x["modules"][0].update(required_credits=4),
    lambda x: x["modules"][0].update(school_in_progress_credits="301"),
    lambda x: x["modules"][0].update(school_direct_in_progress_credits="2"),
    lambda x: x.update(has_in_progress_courses="true"),
])
def test_report_shape_rejects_private_fields_and_incompatible_values(change):
    report = json.loads(BODY)
    change(report)
    with pytest.raises(reader.AttachmentReadError, match="INVALID_DEGREE_REPORT"):
        reader.read_degree_attachment(url(), downloader=lambda _: json.dumps(report).encode())


def test_injected_downloader_cannot_bypass_byte_limit():
    padded = BODY + b" " * (reader.MAX_BYTES - len(BODY))
    assert reader.read_degree_attachment(url(), downloader=lambda _: padded)["payload_hash"] == EXPECTED_HASH
    with pytest.raises(reader.AttachmentReadError, match="ATTACHMENT_TOO_LARGE"):
        reader.read_degree_attachment(url(), downloader=lambda _: padded + b" ")


def test_handler_has_one_json_string_output_and_never_confirms_or_saves(monkeypatch):
    monkeypatch.setattr(reader, "download_attachment", lambda _: BODY)
    result = reader.handler({"attachment_url": url()})
    assert set(result) == {"result"}
    value = json.loads(result["result"])
    assert value["ok"] is True and value["error"] is None
    assert value["payload_hash"] == EXPECTED_HASH and value["module_count"] == 31
    assert value["report_json"] == BODY.decode("utf-8")
    assert not {"confirmed", "saved", "draft_id", "owner", "workspace_ref"} & value.keys()
    assert json.loads(reader.handler({"input": url()})["result"])["error"] == "INVALID_ATTACHMENT_INPUT"

import asyncio
import json
from types import SimpleNamespace

import pytest

from scripts import probe_mcp_url as probe


def result(**changes):
    data = {"nonce": "sample", "build_id": "expected", "server_time": "2026-09-27T12:00:00+08:00"}
    data.update(changes)
    return SimpleNamespace(is_error=False, structured_content=data)


def test_valid_probe_result():
    assert probe.validate_result(result(), "sample", "expected")["build_id"] == "expected"


@pytest.mark.parametrize("changes", [
    {"nonce": "wrong"}, {"build_id": "old-build"}, {"server_time": "not-a-date"},
    {"server_time": "2026-09-27T12:00:00"}, {"server_time": "2026-09-27T12:00:00Z"},
    {"server_time": None}, {"unexpected": "value"},
])
def test_probe_rejects_invalid_payload(changes):
    with pytest.raises(probe.ProbeFailure):
        probe.validate_result(result(**changes), "sample", "expected")


@pytest.mark.parametrize("is_error,data", [(True, {}), (False, None), (False, {}), (False, [])])
def test_probe_rejects_error_or_missing_structure(is_error, data):
    with pytest.raises(probe.ProbeFailure):
        probe.validate_result(SimpleNamespace(is_error=is_error, structured_content=data), "sample", "expected")


@pytest.mark.parametrize("url", [
    "http://api.example.test/mcp", "https:///mcp", "https://user:secret@api.example.test/mcp",
    "https://api.example.test/mcp?token=secret", "https://api.example.test/mcp#secret",
    "file:///mcp", "https://api.example.test/",
])
def test_probe_rejects_unsafe_target(url):
    with pytest.raises(probe.ProbeFailure):
        probe.validate_target(url)


def test_probe_accepts_https_and_loopback():
    assert probe.validate_target("http://127.0.0.1:8001/mcp") is True
    assert probe.validate_target("https://api.example.test/mcp") is False


def test_probe_requires_expected_build_before_network():
    with pytest.raises(probe.ProbeFailure, match="EXPECTED_BUILD_ID"):
        asyncio.run(probe.probe_endpoint("http://localhost:8001/mcp", "", ""))


def test_probe_cli_failure_returns_nonzero_without_secrets(monkeypatch, capsys):
    async def failed(*args):
        raise RuntimeError("Authorization: Bearer do-not-print")
    monkeypatch.setattr(probe, "probe_endpoint", failed)
    assert probe.main() == 1
    output = capsys.readouterr().out
    assert json.loads(output)["ok"] is False
    assert "do-not-print" not in output


def test_probe_cli_success_returns_zero(monkeypatch, capsys):
    async def succeeded(*args):
        return {"ok": True}
    monkeypatch.setattr(probe, "probe_endpoint", succeeded)
    assert probe.main() == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

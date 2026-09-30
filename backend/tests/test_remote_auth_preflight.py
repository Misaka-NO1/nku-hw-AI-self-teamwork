import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from preflight_mcp_auth import preflight


def run(handler):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await preflight(client, "https://campus.example.invalid/mcp")
    return asyncio.run(scenario())


def test_preflight_passes_only_readiness_and_both_bearer_rejections():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/__tcb_probe__":
            return httpx.Response(200, text="ok")
        return httpx.Response(401, headers={"WWW-Authenticate": "Bearer"})

    report = run(handler)
    assert report["ok"] is True
    assert report["valid_token_tested"] is False
    assert report["platform_verified"] is False
    assert all(item["started_at"].endswith("+08:00") for item in report["checks"])
    assert [request.method for request in seen] == ["GET", "POST", "POST"]
    assert "authorization" not in seen[1].headers
    assert seen[2].headers["authorization"].startswith("Bearer invalid-")


@pytest.mark.parametrize("status,headers", [(200, {}), (302, {"Location": "/login"}), (503, {}), (401, {})])
def test_preflight_fails_when_rejection_is_not_bearer_401(status, headers):
    def handler(request):
        if request.url.path == "/__tcb_probe__":
            return httpx.Response(200, text="ok")
        return httpx.Response(status, headers=headers, text="must-not-appear-in-report")

    report = run(handler)
    assert report["ok"] is False
    assert "must-not-appear-in-report" not in str(report)


def test_readiness_failure_stops_before_mcp_calls():
    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(503, text="internal-details")

    report = run(handler)
    assert report["ok"] is False
    assert seen == ["/__tcb_probe__"]
    assert "internal-details" not in str(report)


@pytest.mark.parametrize("error_type,category", [(httpx.ConnectError, "connect_error"), (httpx.ReadTimeout, "timeout")])
def test_transport_error_is_sanitized(error_type, category):
    def handler(request):
        raise error_type("private transport details", request=request)

    report = run(handler)
    assert report["ok"] is False
    assert report["checks"][0]["status"] is None
    assert report["checks"][0]["error_category"] == category
    assert "private transport details" not in str(report)

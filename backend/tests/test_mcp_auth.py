from pydantic import SecretStr
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.mcp.http import StaticBearerAuthMiddleware, create_http_app
from app.core.config import Settings
import pytest


async def endpoint(_):
    return Response(status_code=204)


def test_mcp_bearer_auth_rejects_missing_and_wrong_token() -> None:
    protected = StaticBearerAuthMiddleware(
        Starlette(routes=[Route("/mcp", endpoint, methods=["POST"])]),
        SecretStr("expected-secret"),
    )
    with TestClient(protected) as client:
        missing = client.post("/mcp")
        wrong = client.post("/mcp", headers={"Authorization": "Bearer wrong-secret"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    assert "expected-secret" not in missing.text


def test_mcp_bearer_auth_accepts_matching_token() -> None:
    protected = StaticBearerAuthMiddleware(
        Starlette(routes=[Route("/mcp", endpoint, methods=["POST"])]),
        SecretStr("expected-secret"),
    )
    with TestClient(protected) as client:
        response = client.post(
            "/mcp",
            headers={"Authorization": "Bearer expected-secret"},
        )

    assert response.status_code == 204


@pytest.mark.parametrize("overrides,expected_error", [
    ({}, "HTTPS"),
    ({"mcp_public_url": "https://campus.example.invalid/mcp"}, "MCP_REQUIRE_AUTH"),
    ({"mcp_public_url": "https://campus.example.invalid/mcp", "mcp_require_auth": True},
     "MCP_SERVICE_TOKEN"),
])
def test_cloud_listener_cannot_start_without_https_and_bearer_even_if_development(overrides, expected_error):
    runtime = Settings(app_env="development", mcp_host="0.0.0.0", **overrides)

    with pytest.raises(ValueError, match=expected_error):
        create_http_app(runtime)


@pytest.mark.parametrize("host,origin,status", [
    ("campus.example.invalid", None, 200),
    ("campus.example.invalid", "https://campus.example.invalid", 200),
    ("campus.example.invalid", "https://untrusted.example.invalid", 403),
    ("untrusted.example.invalid", None, 421),
])
def test_mcp_proxy_host_and_origin_allowlist(host, origin, status):
    runtime = Settings(app_env="staging", mcp_public_url="https://campus.example.invalid/mcp",
        mcp_require_auth=True, mcp_service_token="proxy-test-secret", mcp_host="0.0.0.0")
    headers = {"Authorization": "Bearer proxy-test-secret", "Host": host,
               "Accept": "application/json, text/event-stream"}
    if origin:
        headers["Origin"] = origin
    with TestClient(create_http_app(runtime)) as client:
        response = client.post("/mcp", headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                       "clientInfo": {"name": "proxy-check", "version": "1.0"}},
        })
    assert response.status_code == status


def test_cloudbase_probe_is_public_but_only_exact_get_path():
    runtime = Settings(app_env="staging", mcp_public_url="https://campus.example.invalid/mcp",
        mcp_require_auth=True, mcp_service_token="proxy-test-secret", mcp_host="0.0.0.0")
    with TestClient(create_http_app(runtime)) as client:
        health = client.get("/__tcb_probe__")
        wrong_method = client.post("/__tcb_probe__")
        wrong_path = client.get("/__tcb_probe__/extra")
        mcp = client.post("/mcp")
    assert health.status_code == 200
    assert health.text == "ok"
    assert health.headers["cache-control"] == "no-store"
    assert wrong_method.status_code == 401
    assert wrong_path.status_code == 401
    assert mcp.status_code == 401

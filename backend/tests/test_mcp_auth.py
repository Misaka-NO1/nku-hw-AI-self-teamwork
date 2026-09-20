from pydantic import SecretStr
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.mcp.http import StaticBearerAuthMiddleware


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

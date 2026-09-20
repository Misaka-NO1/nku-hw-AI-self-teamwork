import secrets
from collections.abc import Awaitable, Callable
from typing import Any

import uvicorn
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.mcp.server import mcp


AsgiApp = Callable[[dict[str, Any], Callable[..., Awaitable[Any]], Callable[..., Awaitable[Any]]], Awaitable[None]]


class StaticBearerAuthMiddleware:
    """Protect a service-to-service MCP endpoint with one deployment secret."""

    def __init__(self, app: AsgiApp, token: SecretStr) -> None:
        self.app = app
        self._token = token

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        supplied = headers.get(b"authorization", b"").decode("latin-1")
        expected = f"Bearer {self._token.get_secret_value()}"
        if not secrets.compare_digest(supplied, expected):
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"www-authenticate", b"Bearer"),
                        (b"cache-control", b"no-store"),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error":"AUTH_REQUIRED"}',
                }
            )
            return
        await self.app(scope, receive, send)


def create_http_app(settings: Settings | None = None) -> AsgiApp:
    runtime = settings or get_settings()
    runtime.validate_deployment()
    base_app = mcp.streamable_http_app(
        streamable_http_path=runtime.mcp_path,
        host=runtime.mcp_host,
    )
    if not runtime.mcp_require_auth:
        return base_app
    if not runtime.mcp_service_token.get_secret_value():
        raise ValueError("MCP_SERVICE_TOKEN is required when MCP authentication is enabled")
    return StaticBearerAuthMiddleware(base_app, runtime.mcp_service_token)


app = create_http_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.mcp_host, port=settings.mcp_port)

import secrets
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

import uvicorn
from pydantic import SecretStr
from mcp.server.transport_security import TransportSecuritySettings

from app.core.config import Settings, get_settings
from app.mcp.server import create_mcp_server


AsgiApp = Callable[[dict[str, Any], Callable[..., Awaitable[Any]], Callable[..., Awaitable[Any]]], Awaitable[None]]


class CloudBaseReadinessMiddleware:
    """Answer the container's exact health path without granting MCP access."""

    def __init__(self, app: AsgiApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http" and scope["path"] == "/__tcb_probe__" and scope["method"] == "GET":
            await send({
                "type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"text/plain; charset=utf-8"), (b"cache-control", b"no-store")],
            })
            await send({"type": "http.response.body", "body": b"ok"})
            return
        await self.app(scope, receive, send)


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
    allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    allowed_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    if runtime.mcp_public_url:
        public = urlsplit(runtime.mcp_public_url)
        # Proxy preserves external Host; permit only the configured public authority.
        allowed_hosts.append(public.netloc)
        allowed_origins.append(f"{public.scheme}://{public.netloc}")
    base_app = create_mcp_server(runtime).streamable_http_app(
        streamable_http_path=runtime.mcp_path,
        host=runtime.mcp_host,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        ),
    )
    if runtime.mcp_require_auth:
        if not runtime.mcp_service_token.get_secret_value():
            raise ValueError("MCP_SERVICE_TOKEN is required when MCP authentication is enabled")
        base_app = StaticBearerAuthMiddleware(base_app, runtime.mcp_service_token)
    return CloudBaseReadinessMiddleware(base_app)


app = create_http_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.mcp_host, port=settings.mcp_port)

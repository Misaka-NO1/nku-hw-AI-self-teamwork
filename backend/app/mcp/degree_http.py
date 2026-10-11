"""Opt-in authenticated HTTP transport for supplied curriculum observations.

No default tool registration or deployment. Reuses established MCP transport
authentication and DNS rebinding protection without changing existing tools.
"""
from app.core.config import Settings, get_settings
from app.mcp.degree import create_degree_mcp_server
from app.mcp.http import create_http_app


def create_degree_http_app(settings: Settings | None = None):
    runtime = settings or get_settings()
    if not runtime.mcp_require_auth or not runtime.mcp_service_token.get_secret_value():
        raise ValueError("Degree HTTP analysis requires configured service authentication")
    return create_http_app(runtime, server_factory=lambda _: create_degree_mcp_server(),
                           max_request_body_size=1_048_576)


if __name__ == "__main__":
    import uvicorn
    runtime = get_settings()
    uvicorn.run(create_degree_http_app(runtime), host=runtime.mcp_host,
                port=runtime.mcp_port, access_log=False)

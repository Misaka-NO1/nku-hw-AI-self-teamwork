from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from mcp.server import MCPServer
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.mcp.audit import McpAuditLoggingMiddleware


class HealthProbeResult(BaseModel):
    nonce: str
    build_id: str
    server_time: str


settings = get_settings()
configure_logging(settings.log_level)
def create_mcp_server(runtime: Settings) -> MCPServer:
    if runtime.mcp_enable_platform_compat_tools and not runtime.mcp_enable_domain_tools:
        raise ValueError("MCP_ENABLE_PLATFORM_COMPAT_TOOLS requires MCP_ENABLE_DOMAIN_TOOLS")
    server_type = MCPServer
    kwargs = {}
    if runtime.mcp_enable_domain_tools:
        from app.core.domain_bundle import verify_domain_bundle
        verify_domain_bundle(runtime)
        # Lazy import keeps the existing cloud probe independent of business assets.
        from app.mcp.domains import DomainMCPServer
        server_type = DomainMCPServer
        kwargs["runtime"] = runtime
    server = server_type(
        name="campus-tools",
        instructions=("Read-only fictional demo tools; no personal identity binding or writes."
                      if runtime.mcp_enable_domain_tools else "Non-sensitive health probe only."),
        version=runtime.build_id,
        middleware=[McpAuditLoggingMiddleware()],
        **kwargs,
    )

    @server.tool()
    def health_probe(nonce: Annotated[str, Field(min_length=1, max_length=128)]) -> HealthProbeResult:
        """Return the caller nonce with build and server time for connectivity checks."""
        return HealthProbeResult(
            nonce=nonce, build_id=runtime.build_id,
            server_time=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        )

    return server


mcp = create_mcp_server(settings)

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from mcp.server import MCPServer
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.mcp.audit import McpAuditLoggingMiddleware


class HealthProbeResult(BaseModel):
    nonce: str
    build_id: str
    server_time: str


settings = get_settings()
configure_logging(settings.log_level)
mcp = MCPServer(
    "campus-tools",
    instructions="NKU campus assistant tools. Current milestone exposes a non-sensitive health probe only.",
    version=settings.build_id,
    middleware=[McpAuditLoggingMiddleware()],
)


@mcp.tool()
def health_probe(
    nonce: Annotated[str, Field(min_length=1, max_length=128)],
) -> HealthProbeResult:
    """Return the caller nonce with build and server time for connectivity checks."""
    return HealthProbeResult(
        nonce=nonce,
        build_id=settings.build_id,
        server_time=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    )

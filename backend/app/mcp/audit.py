import logging
from time import perf_counter
from typing import Any

from mcp.server.context import CallNext, HandlerResult, ServerMiddleware, ServerRequestContext


logger = logging.getLogger("app.mcp.audit")


class McpAuditLoggingMiddleware(ServerMiddleware[Any]):
    """Log MCP routing metadata without request parameters or credentials."""

    async def __call__(
        self,
        ctx: ServerRequestContext[Any, Any],
        call_next: CallNext,
    ) -> HandlerResult:
        started = perf_counter()
        tool_name = None
        if ctx.method == "tools/call" and ctx.params:
            candidate = ctx.params.get("name")
            tool_name = candidate if isinstance(candidate, str) else None
        try:
            result = await call_next(ctx)
        except Exception:
            self._write(ctx, started, tool_name, "error")
            raise
        self._write(ctx, started, tool_name, "ok")
        return result

    @staticmethod
    def _write(
        ctx: ServerRequestContext[Any, Any],
        started: float,
        tool_name: str | None,
        outcome: str,
    ) -> None:
        logger.info(
            "mcp_request",
            extra={
                "request_id": str(ctx.request_id) if ctx.request_id is not None else "notification",
                "method": ctx.method,
                "protocol_version": ctx.protocol_version,
                "tool_name": tool_name,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
                "outcome": outcome,
            },
        )

import asyncio
import logging
from types import SimpleNamespace

import pytest
from mcp import Client
from mcp_types import CallToolResult

from app.core.config import Settings
from app.mcp.audit import McpAuditLoggingMiddleware
from app.mcp.server import create_mcp_server


def context():
    return SimpleNamespace(method="tools/call", params={"name": "platform_search_scenic_spots"},
                           request_id=12, protocol_version="2025-06-18")


@pytest.mark.parametrize("result,outcome", [
    ({"isError": True, "content": []}, "error"),
    ({"isError": False, "content": []}, "ok"),
    ({}, "ok"), (None, "ok"),
    (CallToolResult(content=[], is_error=True), "error"),
    (CallToolResult(content=[], is_error=False), "ok"),
])
def test_audit_accepts_both_sdk_model_and_wire_dict(caplog, result, outcome):
    caplog.set_level(logging.INFO, logger="app.mcp.audit")
    async def next_handler(ctx):
        return result
    returned = asyncio.run(McpAuditLoggingMiddleware()(context(), next_handler))
    assert returned is result
    assert caplog.records[-1].outcome == outcome
    assert caplog.records[-1].tool_name == "platform_search_scenic_spots"


def test_audit_exception_is_error_without_exception_text(caplog):
    caplog.set_level(logging.INFO, logger="app.mcp.audit")
    async def next_handler(ctx):
        raise RuntimeError("SECRET-internal-detail")
    with pytest.raises(RuntimeError):
        asyncio.run(McpAuditLoggingMiddleware()(context(), next_handler))
    assert caplog.records[-1].outcome == "error"
    assert "SECRET" not in caplog.text


def test_real_sdk_business_failure_has_error_audit(caplog):
    caplog.set_level(logging.INFO, logger="app.mcp.audit")
    server = create_mcp_server(Settings(_env_file=None, app_env="test", mcp_enable_domain_tools=True,
                                        mcp_enable_platform_compat_tools=True))
    async def scenario():
        async with Client(server) as client:
            return await client.call_tool("platform_search_scenic_spots", {"query_json": "[]"})
    result = asyncio.run(scenario())
    assert result.is_error
    records = [record for record in caplog.records if record.name == "app.mcp.audit"
               and getattr(record, "method", None) == "tools/call"]
    assert records and records[-1].outcome == "error"

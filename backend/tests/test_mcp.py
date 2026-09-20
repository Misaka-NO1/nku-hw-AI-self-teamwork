import asyncio

from mcp import Client

from app.mcp.server import mcp


def test_health_probe_can_be_discovered_and_called() -> None:
    async def scenario():
        async with Client(mcp) as client:
            tools = (await client.list_tools()).tools
            result = await client.call_tool("health_probe", {"nonce": "probe-123"})
        return tools, result

    tools, result = asyncio.run(scenario())

    assert [tool.name for tool in tools] == ["health_probe"]
    assert result.is_error is False
    assert result.structured_content["nonce"] == "probe-123"
    assert result.structured_content["build_id"] == "test-build"
    assert "+08:00" in result.structured_content["server_time"]


def test_health_probe_rejects_empty_nonce() -> None:
    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("health_probe", {"nonce": ""})

    result = asyncio.run(scenario())
    assert result.is_error is True

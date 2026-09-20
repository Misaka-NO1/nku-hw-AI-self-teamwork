"""Probe a running Streamable HTTP MCP endpoint with the official SDK client."""

import asyncio
import json
import os
from secrets import token_urlsafe

import httpx2
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    url = os.environ.get("MCP_PROBE_URL", "http://127.0.0.1:8001/mcp")
    service_token = os.environ.get("MCP_PROBE_TOKEN", "")
    headers = {"Authorization": f"Bearer {service_token}"} if service_token else {}
    nonce = token_urlsafe(16)

    async with httpx2.AsyncClient(headers=headers) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                tools = (await session.list_tools()).tools
                result = await session.call_tool("health_probe", {"nonce": nonce})

    payload = {
        "url": url,
        "protocol_version": initialized.protocol_version,
        "tools": [tool.name for tool in tools],
        "nonce_matches": result.structured_content.get("nonce") == nonce,
        "result": result.model_dump(mode="json"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

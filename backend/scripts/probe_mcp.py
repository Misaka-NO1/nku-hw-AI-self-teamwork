"""Run the official MCP client against the in-process server."""

import asyncio
import json

from mcp import Client

from app.mcp.server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        result = await client.call_tool("health_probe", {"nonce": "local-probe"})
        print(
            json.dumps(
                {
                    "tools": [tool.name for tool in tools.tools],
                    "result": result.model_dump(mode="json"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())

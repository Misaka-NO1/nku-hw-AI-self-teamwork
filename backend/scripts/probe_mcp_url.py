"""Strict, read-only Streamable HTTP acceptance probe using the locked official SDK."""

import asyncio
from datetime import datetime, timedelta
import json
import logging
import os
from secrets import token_urlsafe
from urllib.parse import urlsplit

import httpx2
from mcp import types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


class ProbeFailure(RuntimeError):
    """Only fixed, non-sensitive messages should be used here."""


def validate_target(url: str) -> bool:
    """Allow plain HTTP only on literal loopback targets; never put secrets in URLs."""
    parsed = urlsplit(url)
    local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if not parsed.hostname or parsed.scheme not in {"http", "https"}:
        raise ProbeFailure("MCP_PROBE_URL must be an HTTP(S) endpoint")
    if parsed.scheme == "http" and not local:
        raise ProbeFailure("Non-loopback probes require HTTPS")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ProbeFailure("MCP_PROBE_URL must not contain credentials, query or fragment")
    if not parsed.path or parsed.path == "/":
        raise ProbeFailure("MCP_PROBE_URL must include the MCP path")
    _ = parsed.port
    return local


def validate_result(result, nonce: str, expected_build_id: str) -> dict:
    if result.is_error:
        raise ProbeFailure("health_probe returned a tool error")
    data = result.structured_content
    if not isinstance(data, dict) or set(data) != {"nonce", "build_id", "server_time"}:
        raise ProbeFailure("health_probe returned an invalid result structure")
    if data["nonce"] != nonce:
        raise ProbeFailure("health_probe nonce mismatch")
    if data["build_id"] != expected_build_id:
        raise ProbeFailure("health_probe build_id mismatch")
    try:
        stamp = datetime.fromisoformat(data["server_time"])
        if stamp.utcoffset() != timedelta(hours=8):
            raise ValueError
    except (TypeError, ValueError):
        raise ProbeFailure("health_probe server_time must include +08:00") from None
    return data


async def probe_endpoint(url: str, token: str, expected_build_id: str, timeout: float = 30) -> dict:
    local = validate_target(url)
    if not expected_build_id:
        raise ProbeFailure("MCP_PROBE_EXPECTED_BUILD_ID is required")
    if not local and not token:
        raise ProbeFailure("Non-loopback probes require MCP_PROBE_TOKEN")
    if not 0 < timeout <= 120:
        raise ProbeFailure("Probe timeout must be between 0 and 120 seconds")
    nonce = token_urlsafe(16)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    auth_checks = None
    async with asyncio.timeout(timeout):
        async with httpx2.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            if token:
                auth_checks = {}
                for name, auth in (("missing_token", {}), ("wrong_token", {"Authorization": f"Bearer {token_urlsafe(32)}"})):
                    rejected = await client.post(url, headers=auth, json={})
                    if rejected.status_code != 401:
                        raise ProbeFailure("MCP must reject missing and wrong Bearer tokens with HTTP 401")
                    auth_checks[name] = rejected.status_code
        async with httpx2.AsyncClient(headers=headers, timeout=timeout, follow_redirects=False) as http_client:
            async with streamable_http_client(url, http_client=http_client) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timeout) as session:
                    initialized = await session.initialize()
                    names, cursors = [], set()
                    cursor = None
                    for _ in range(20):
                        listing = await session.list_tools(
                            params=types.PaginatedRequestParams(cursor=cursor) if cursor else None
                        )
                        names.extend(tool.name for tool in listing.tools)
                        cursor = listing.next_cursor
                        if cursor is None:
                            break
                        if cursor in cursors:
                            raise ProbeFailure("tools/list returned a repeated cursor")
                        cursors.add(cursor)
                    else:
                        raise ProbeFailure("tools/list exceeded pagination limit")
                    if "health_probe" not in names:
                        raise ProbeFailure("health_probe was not discovered")
                    result = await session.call_tool("health_probe", {"nonce": nonce})
                    data = validate_result(result, nonce, expected_build_id)
                    invalid = await session.call_tool("health_probe", {"nonce": ""})
                    if not invalid.is_error:
                        raise ProbeFailure("health_probe accepted an empty nonce")
    return {
        "ok": True,
        "url": url,
        "protocol_version": initialized.protocol_version,
        "tools": names,
        "nonce_matches": True,
        "build_id_matches": True,
        "auth_checks": auth_checks,
        "empty_nonce_rejected": True,
        "result": data,
    }


def main() -> int:
    # Transport exceptions may contain remote bodies/headers. Emit only our safe report.
    previous_logging_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        report = asyncio.run(probe_endpoint(
            os.environ.get("MCP_PROBE_URL", "http://127.0.0.1:8001/mcp"),
            os.environ.get("MCP_PROBE_TOKEN", ""),
            os.environ.get("MCP_PROBE_EXPECTED_BUILD_ID", ""),
        ))
    except Exception as exc:
        report = {"ok": False, "error": str(exc) if isinstance(exc, ProbeFailure) else "Transport or protocol failure; check endpoint and server logs"}
    finally:
        logging.disable(previous_logging_level)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

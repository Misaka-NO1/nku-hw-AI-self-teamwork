"""D06: real disposable REST + authenticated Streamable HTTP parity checks."""

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory

import httpx
import httpx2
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from check_local_stack import BACKEND, ROOT, require, service, unused_ports, wait_ready
from preflight_mcp_auth import preflight
from probe_mcp_url import ProbeFailure


CASES = [
    ("validate_timetable", "/api/v1/schedules/validate", "timetable.demo.json", False),
    ("query_free_time", "/api/v1/time/free-slots", "time-free-query.demo.json", False),
    ("check_time_plan", "/api/v1/time/check", "time-event-query.demo.json", False),
    ("check_time_plan", "/api/v1/time/check", "time-deadline-query.demo.json", False),
    ("search_scenic_spots", "/api/v1/scenic/spots", "scenic-query.demo.json", True),
    ("search_study_materials", "/api/v1/study/materials", "study-query.demo.json", True),
    ("audit_degree_progress", "/api/v1/degree/audit", "degree-query.demo.json", False),
]


def comparable(body):
    value = deepcopy(body)
    del value["meta"]["request_id"]
    return value


@asynccontextmanager
async def authenticated_mcp(url, token):
    async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + token}, timeout=10, follow_redirects=False) as transport:
        async with streamable_http_client(url, http_client=transport) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=10) as session:
                await session.initialize()
                yield session


async def compare(api_url, mcp_url, token, build_id):
    async with httpx.AsyncClient(timeout=10, trust_env=False) as http:
        auth = await preflight(http, mcp_url)
        require(auth["ok"], "Local domain authentication preflight failed")
        async with authenticated_mcp(mcp_url, token) as mcp:
            tools = [tool.name for tool in (await mcp.list_tools()).tools]
            require(tools == ["health_probe", *dict.fromkeys(case[0] for case in CASES)], "Domain tool discovery mismatch")
            nonce = secrets.token_hex(16)
            probe = await mcp.call_tool("health_probe", {"nonce": nonce})
            require(not probe.is_error and probe.structured_content["nonce"] == nonce, "Local nonce mismatch")
            require(probe.structured_content["build_id"] == build_id, "Local build mismatch")
            for name, path, fixture, is_get in CASES:
                payload = json.loads((ROOT / "fixtures" / fixture).read_text(encoding="utf-8"))
                response = (await http.get(api_url + path, params={"query": json.dumps(payload, ensure_ascii=False)})
                            if is_get else await http.post(api_url + path, json=payload))
                result = await mcp.call_tool(name, payload)
                require(response.status_code == 200 and not result.is_error, "Domain operation failed: " + name)
                require(comparable(response.json()) == comparable(result.structured_content), "REST/MCP mismatch: " + name)
            invalid = {"campus_id": None, "tags": [], "month": None, "limit": 21}
            response = await http.get(api_url + "/api/v1/scenic/spots", params={"query": json.dumps(invalid)})
            result = await mcp.call_tool("search_scenic_spots", invalid)
            require(response.status_code == 422 and result.is_error, "Invalid query was not rejected")
            require(comparable(response.json()) == comparable(result.structured_content), "Failure envelope mismatch")
    return {"tools": tools, "success_parity_cases": len(CASES), "failure_parity_cases": 1,
            "missing_and_wrong_bearer_rejected": True, "nonce_and_build_verified": True}


def run_checks():
    logging.disable(logging.CRITICAL)
    api_port, mcp_port = unused_ports()
    api_url, mcp_url = f"http://127.0.0.1:{api_port}", f"http://127.0.0.1:{mcp_port}/mcp"
    token, build_id = secrets.token_urlsafe(32), "local-d06-" + secrets.token_hex(6)
    with TemporaryDirectory(prefix="nku-d06-check-") as scratch:
        directory = Path(scratch)
        env = {**os.environ, "PYTHONPATH": str(BACKEND), "PYTHONUTF8": "1",
               "APP_ENV": "test", "AUTH_MODE": "demo_fixture", "ALLOW_PERSONAL_UPLOADS": "false",
               "APP_ORIGIN": api_url, "GENIOS_AGENT_URL": "", "MCP_PUBLIC_URL": "",
               "BUILD_ID": build_id, "LOG_LEVEL": "WARNING",
               "API_HOST": "127.0.0.1", "API_PORT": str(api_port),
               "MCP_HOST": "127.0.0.1", "MCP_PORT": str(mcp_port), "MCP_PATH": "/mcp",
               "MCP_REQUIRE_AUTH": "true", "MCP_SERVICE_TOKEN": token, "MCP_ENABLE_DOMAIN_TOOLS": "true",
               "DOMAIN_BUNDLE_MANIFEST_PATH": "",
               "DATABASE_URL": "sqlite:///" + (directory / "campus.db").as_posix()}
        with httpx.Client(timeout=3, trust_env=False) as http:
            with service("app.mcp.http", env, directory) as mcp_process:
                wait_ready(http, mcp_process, mcp_url, 401, method="POST")
                with service("app.main", env, directory) as api_process:
                    wait_ready(http, api_process, api_url + "/readyz", 200)
                    report = asyncio.run(compare(api_url, mcp_url, token, build_id))
    return {"ok": True, "scope": "local_only", "auth_mode": "demo_fixture",
            "platform_verified": False, "personal_uploads": False, **report}


def main():
    try:
        report = run_checks()
    except Exception as exc:
        report = {"ok": False, "error": str(exc) if isinstance(exc, ProbeFailure) else "Local D06 check failed; run adapter tests for diagnostics"}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

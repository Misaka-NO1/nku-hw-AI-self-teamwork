"""Check public readiness and Bearer rejection without reading a service token."""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
from secrets import token_urlsafe
from time import perf_counter
from urllib.parse import urlsplit

import httpx

from probe_mcp_url import ProbeFailure, validate_target


async def preflight(client: httpx.AsyncClient, url: str) -> dict:
    validate_target(url)
    health_url = urlsplit(url)._replace(path="/__tcb_probe__").geturl()

    async def request(name: str, target: str, *, authorization: str | None = None) -> dict:
        started = perf_counter()
        started_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
        try:
            if name == "readiness":
                response = await client.get(target, follow_redirects=False)
                passed = response.status_code == 200 and response.text == "ok"
            else:
                headers = {"Authorization": authorization} if authorization else {}
                response = await client.post(target, headers=headers, json={}, follow_redirects=False)
                passed = (
                    response.status_code == 401
                    and response.headers.get("WWW-Authenticate", "").lower() == "bearer"
                )
            return {
                "check": name,
                "started_at": started_at,
                "passed": passed,
                "status": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            }
        except httpx.HTTPError as exc:
            if isinstance(exc, httpx.TimeoutException):
                category = "timeout"
            elif isinstance(exc, httpx.ConnectError):
                category = "connect_error"
            else:
                category = "transport_error"
            return {
                "check": name,
                "started_at": started_at,
                "passed": False,
                "status": None,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
                "error": "Transport failure; check endpoint and server logs",
                "error_category": category,
            }

    readiness = await request("readiness", health_url)
    checks = [readiness]
    if readiness["passed"]:
        checks.extend(await asyncio.gather(
            request("missing_token", url),
            request("wrong_token", url, authorization="Bearer invalid-" + token_urlsafe(32)),
        ))
    return {
        "ok": len(checks) == 3 and all(item["passed"] for item in checks),
        "url": url,
        "checks": checks,
        "valid_token_tested": False,
        "platform_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="HTTPS MCP endpoint, without credentials or query parameters")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)

    async def run() -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            return await preflight(client, args.url)

    try:
        report = asyncio.run(run())
    except Exception as exc:
        report = {"ok": False, "error": str(exc) if isinstance(exc, ProbeFailure) else "Preflight failed"}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

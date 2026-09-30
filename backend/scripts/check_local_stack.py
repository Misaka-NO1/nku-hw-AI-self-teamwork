"""Start disposable REST/MCP processes, verify them, then stop only our processes.

Uses an isolated temporary SQLite file and random in-memory service token. No cloud
resources, user .env files or existing databases are changed. Run from any directory.
"""

import asyncio
from contextlib import closing, contextmanager
import json
import logging
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

import httpx

from probe_mcp_url import ProbeFailure, probe_endpoint


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbeFailure(message)


def unused_ports() -> tuple[int, int]:
    # Hold both reservations together; never terminate an existing port owner.
    with socket.socket() as first, socket.socket() as second:
        first.bind(("127.0.0.1", 0))
        second.bind(("127.0.0.1", 0))
        return first.getsockname()[1], second.getsockname()[1]


@contextmanager
def service(module: str, env: dict, cwd: Path):
    process = subprocess.Popen(
        [sys.executable, "-m", module], env=env, cwd=cwd,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def wait_ready(client: httpx.Client, process, url: str, status: int, *, method: str = "GET") -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ProbeFailure("Local service exited before readiness; run its entrypoint for diagnostics")
        try:
            response = client.request(method, url, timeout=1)
            if response.status_code == status:
                return
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    raise ProbeFailure("Local service readiness timed out")


def body(response: httpx.Response) -> dict | list:
    require(response.status_code == 200, "REST request failed")
    envelope = response.json()
    require(envelope.get("ok") is True and envelope.get("error") is None, "REST success envelope invalid")
    require(envelope["meta"]["schema_version"] == "1.0.0", "REST schema version mismatch")
    require(bool(envelope["meta"]["request_id"]), "REST request_id missing")
    return envelope["data"]


def seed_confirmed_task(client: httpx.Client, base: str) -> tuple[str, dict]:
    workspace = body(client.post(base + "/api/v1/demo/workspaces", json={"fixture_set_id": "demo-v1"}))
    headers = {"X-CSRF-Token": workspace["csrf_token"]}
    notice = json.loads((ROOT / "fixtures/notice-event.demo.json").read_text(encoding="utf-8"))
    draft = body(client.post(base + "/api/v1/tasks/drafts",
        headers={**headers, "Idempotency-Key": "local-smoke-draft"},
        json={"workspace_ref": workspace["workspace_ref"], "notice": notice}))
    confirmation = body(client.post(base + "/api/v1/confirmations",
        headers={**headers, "Idempotency-Key": "local-smoke-confirm"},
        json={key: draft[key] for key in ("draft_id", "revision", "payload_hash")}))
    payload = {"confirmation_id": confirmation["confirmation_id"], "idempotency_key": "local-smoke-commit"}
    committed = body(client.post(base + "/api/v1/tasks/commit", headers=headers, json=payload))
    retried = body(client.post(base + "/api/v1/tasks/commit", headers=headers, json=payload))
    require(committed == retried, "Idempotent task commit mismatch")
    require(bool(committed.get("task_id")), "Task commit did not return task_id")
    return workspace["workspace_ref"], committed


def run_checks() -> dict:
    logging.disable(logging.CRITICAL)
    api_port, mcp_port = unused_ports()
    api_url = f"http://127.0.0.1:{api_port}"
    mcp_url = f"http://127.0.0.1:{mcp_port}/mcp"
    build_id = "local-check-" + secrets.token_hex(6)
    token = secrets.token_urlsafe(32)
    with TemporaryDirectory(prefix="nku-local-check-") as scratch:
        directory = Path(scratch)
        database = directory / "campus.db"
        env = {
            **os.environ,
            "PYTHONPATH": str(BACKEND), "PYTHONUTF8": "1",
            "APP_ENV": "test", "BUILD_ID": build_id, "LOG_LEVEL": "WARNING",
            "AUTH_MODE": "demo_fixture", "ALLOW_PERSONAL_UPLOADS": "false",
            "DOMAIN_BUNDLE_MANIFEST_PATH": "",
            "APP_ORIGIN": api_url, "GENIOS_AGENT_URL": "", "MCP_PUBLIC_URL": "",
            "API_HOST": "127.0.0.1", "API_PORT": str(api_port),
            "MCP_HOST": "127.0.0.1", "MCP_PORT": str(mcp_port), "MCP_PATH": "/mcp",
            "MCP_REQUIRE_AUTH": "true", "MCP_SERVICE_TOKEN": token,
            "MCP_ENABLE_DOMAIN_TOOLS": "false",
            "MCP_ENABLE_PLATFORM_COMPAT_TOOLS": "false",
            "DATABASE_URL": "sqlite:///" + database.as_posix(),
        }
        # Empty cwd avoids loading the user's backend/.env. Both processes share one absolute DB path.
        with httpx.Client(timeout=3, trust_env=False) as client:
            with service("app.mcp.http", env, directory) as mcp_process:
                wait_ready(client, mcp_process, mcp_url, 401, method="POST")
                with service("app.main", env, directory) as api_process:
                    wait_ready(client, api_process, api_url + "/readyz", 200)
                    for path in ("/healthz", "/readyz"):
                        require(body(client.get(api_url + path))["build_id"] == build_id, "REST build mismatch")
                    mcp_report = asyncio.run(probe_endpoint(mcp_url, token, build_id))
                    require(mcp_report["tools"] == ["health_probe"], "Unexpected tools in first-stage deployment")
                    wrong_build = subprocess.run(
                        [sys.executable, str(BACKEND / "scripts/probe_mcp_url.py")],
                        env={**env, "MCP_PROBE_URL": mcp_url, "MCP_PROBE_TOKEN": token,
                             "MCP_PROBE_EXPECTED_BUILD_ID": "deliberately-wrong-build"},
                        cwd=directory, capture_output=True, timeout=40,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                    require(wrong_build.returncode == 1, "Probe CLI did not fail for wrong build")
                    require(json.loads(wrong_build.stdout)["ok"] is False, "Probe CLI failure report invalid")
                    workspace_ref, committed = seed_confirmed_task(client, api_url)
                # Real process restart, keeping its SQLite file and browser session.
                with service("app.main", env, directory) as restarted:
                    wait_ready(client, restarted, api_url + "/readyz", 200)
                    tasks = body(client.get(api_url + "/api/v1/tasks", params={"workspace_ref": workspace_ref}))
                    require(len(tasks) == 1 and tasks[0]["task_id"] == committed["task_id"], "Confirmed task lost/duplicated after restart")
                with closing(sqlite3.connect(database)) as connection:
                    require(connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity check failed")
        return {
            "ok": True, "scope": "local_only", "build_id": build_id,
            "rest_health_and_readiness": True, "mcp": mcp_report,
            "confirmed_task_survives_restart": True, "idempotent_commit": True,
            "sqlite_integrity": "ok", "auth_mode": "demo_fixture",
            "wrong_build_cli_rejected": True,
            "personal_uploads": False, "platform_verified": False,
        }


def main() -> int:
    try:
        report = run_checks()
    except Exception as exc:
        report = {"ok": False, "error": str(exc) if isinstance(exc, ProbeFailure) else "Local integration check failed; run unit tests and service entrypoints for diagnostics"}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

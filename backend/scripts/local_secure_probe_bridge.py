"""One-time loopback form for checking the CloudBase MCP endpoint without logging the token."""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from threading import Thread
from urllib.parse import parse_qs

from scripts.probe_mcp_url import ProbeFailure, probe_endpoint


TARGET_URL = "https://nku-campus-mcp-probe-308235-6-1467707525.sh.run.tcloudbase.com/mcp"
EXPECTED_BUILD_ID = "cloudbase-probe-20260928-b7f3bae-secure"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _reply(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; form-action 'self'")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/":
            self._reply(404, b"Not found", "text/plain")
            return
        body = ("<!doctype html><meta charset=utf-8><title>Local MCP probe</title>"
                "<form method=post action=/run><label>CloudBase MCP token "
                "<input type=password name=token autocomplete=off required></label>"
                "<button type=submit>Run one-time probe</button></form>").encode()
        self._reply(200, body, "text/html; charset=utf-8")

    def do_POST(self):
        allowed_origin = f"http://127.0.0.1:{self.server.server_port}"
        if (self.path != "/run" or self.headers.get("Origin") != allowed_origin
                or self.headers.get("Content-Type", "").split(";", 1)[0] != "application/x-www-form-urlencoded"):
            self._reply(403, b"Forbidden", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= 4096:
            self._reply(400, b"Invalid length", "text/plain")
            return
        try:
            fields = parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True)
            token = fields.get("token", [""])[0]
        except (UnicodeDecodeError, ValueError):
            token = ""
        if not token:
            self._reply(400, b"Missing token", "text/plain")
            return
        previous_level = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            report = asyncio.run(probe_endpoint(TARGET_URL, token, EXPECTED_BUILD_ID, timeout=120))
        except Exception as exc:
            report = {"ok": False, "error": str(exc) if isinstance(exc, ProbeFailure)
                      else "Transport or protocol failure; check endpoint and server logs"}
        finally:
            logging.disable(previous_level)
        result = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
        self._reply(200 if report["ok"] else 502, result, "application/json; charset=utf-8")
        Thread(target=self.server.shutdown, daemon=True).start()


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    print(f"LOCAL_PROBE_URL=http://127.0.0.1:{server.server_port}/", flush=True)
    server.serve_forever()

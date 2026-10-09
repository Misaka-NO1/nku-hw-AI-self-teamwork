"""Local browser integration against real isolated PG, never cloud authentication.

Run only from this repository with test dependencies. The loopback bridge adapts
HTTP to the HTTPS TestClient and removes Secure only from synthetic test cookies.
It is excluded from deployment. Production Origin/Cookie checks are unchanged.
Calendar clock is Sep 21 to exercise the unmodified historical timetable.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "backend/tests")]

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from app.cloud_identity_site import create_cloud_identity_site
from test_cloud_identity_site import environment, login, save, ORIGIN
from test_task_calendar import new_task, NOW


def run(port, name):
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name):
        raise ValueError("Use a fresh probe name")
    web = ROOT / "frontend/dist-identity"
    if not (web / "index.html").is_file():
        raise ValueError("Build the identity frontend first")
    data = ROOT / ".local-notice-pilot-data" / name
    data.mkdir(parents=True, exist_ok=False)
    patch = MonkeyPatch()
    source = environment.__wrapped__(data, patch)
    settings, root, db, _ = next(source)
    shutil.copytree(web, root, dirs_exist_ok=True)
    runtime = settings.model_copy(update={"cloud_notice_text_pilot_enabled": True, "cloud_task_calendar_enabled": True})
    patch.setattr("app.core.task_calendar.calendar_now", lambda: NOW)
    db.call("__test_calendar_clock__", {"epoch": int(NOW.timestamp())})
    captures = []
    evidence = ROOT / "docs/evidence/platform/D15-calendar-browser-readback-2026-10-06.json"
    try:
        with TestClient(create_cloud_identity_site(root, db, runtime), base_url=ORIGIN) as client:
            cookies = {}
            for name in ("a", "b"):
                owner = login(client, "fictional-" + name)
                save(client, owner, "schedule", "timetable.demo.json")
                if name == "a":
                    new_task(client, owner)
                cookies[name] = [f"{k}={v}; Path=/; HttpOnly; SameSite=Strict" for k, v in client.cookies.items()]

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass  # Never log request URLs, Cookie or CSRF headers.

                def do_GET(self):
                    self.handle_request()

                def do_POST(self):
                    self.handle_request()

                def handle_request(self):
                    if self.command == "GET" and self.path in ("/__probe__/owner-a", "/__probe__/owner-b"):
                        self.send_response(302)
                        for cookie in cookies[self.path[-1]]:
                            self.send_header("Set-Cookie", cookie)
                        self.send_header("Location", "/tools/calendar")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    size = int(self.headers.get("Content-Length", "0"))
                    if size > 131072:
                        self.send_error(413)
                        return
                    payload = self.rfile.read(size) if size else None
                    headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "origin", "content-length", "connection", "accept-encoding")}
                    if self.headers.get("Origin"):
                        headers["Origin"] = ORIGIN  # Synthetic loopback probe ONLY.
                    response = client.request(self.command, self.path, headers=headers, content=payload, follow_redirects=False)
                    if self.path.startswith("/api/v1/tasks/"):
                        try:
                            entry = {"method": self.command, "path": self.path, "status": response.status_code, "response": response.json()}
                            if payload:
                                entry["body"] = json.loads(payload)
                            captures.append(entry)
                            evidence.write_text(json.dumps({"mode":"local_loopback_bridge_real_pg_mocked_fictional_identity",
                                "calendar_clock": NOW.isoformat(), "cloud_deployed":False,
                                "https_cookie_origin_production_tested_separately":True,
                                "requests":captures},ensure_ascii=False,indent=2),encoding="utf-8")
                        except (ValueError, OSError):
                            pass
                    self.send_response(response.status_code)
                    for key, value in response.headers.items():
                        if key.lower() not in ("content-length", "transfer-encoding", "content-encoding", "set-cookie"):
                            self.send_header(key, value)
                    for cookie in response.headers.get_list("set-cookie"):
                        self.send_header("Set-Cookie", cookie.replace("; Secure", ""))
                    self.send_header("Content-Length", str(len(response.content)))
                    self.end_headers()
                    self.wfile.write(response.content)

            server = HTTPServer(("127.0.0.1", port), Handler)
            print(json.dumps({"ready": True, "url": f"http://127.0.0.1:{port}/__probe__/owner-a",
                "calendar_clock": NOW.isoformat(), "cloud_connected":False}),flush=True)
            try:
                server.serve_forever()
            finally:
                server.server_close()
    finally:
        try:
            next(source)
        except StopIteration:
            pass
        patch.undo()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--name", required=True)
    options = parser.parse_args()
    run(options.port, options.name)

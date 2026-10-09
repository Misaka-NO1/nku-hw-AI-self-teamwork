"""Run only on loopback, without reading the repository's .env or existing DB."""
import argparse
import os
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8012)
    parser.add_argument("--auth-profile", choices=["legacy", "pg_registered"], default="legacy")
    parser.add_argument("--auth-pilot-config", type=Path, help="Private JSON config (outside Git): env_id and allowed_user_ids; never passwords/keys")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024–65535")
    pilot_config_path = args.auth_pilot_config.resolve() if args.auth_pilot_config else None
    runtime = ROOT / "dist" / "demo-runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    os.chdir(runtime)  # Settings .env loading cannot pick up a user's real deployment file.
    origin = f"http://127.0.0.1:{args.port}"
    os.environ.update({
        "APP_ENV": "development", "AUTH_MODE": "demo_fixture", "ALLOW_PERSONAL_UPLOADS": "false",
        "DATABASE_URL": f"sqlite:///{(BACKEND / 'data' / 'interactive-demo.db').as_posix()}",
        "APP_ORIGIN": origin, "BUILD_ID": "local-tasks-demo-20261002",
        "MCP_HOST": "127.0.0.1", "MCP_REQUIRE_AUTH": "false",
        "MCP_ENABLE_DOMAIN_TOOLS": "false", "MCP_ENABLE_PLATFORM_COMPAT_TOOLS": "false",
        "DOMAIN_BUNDLE_MANIFEST_PATH": "",
        "OAUTH_LOCAL_ENABLED": "false", "AGENT_PAIRING_LOCAL_ENABLED": "false",
    })
    if pilot_config_path:
        import json
        config = json.loads(pilot_config_path.read_text(encoding="utf-8-sig"))
        if set(config) != {"env_id", "allowed_user_ids"} or not isinstance(config["allowed_user_ids"], list):
            parser.error("pilot config must contain only env_id and allowed_user_ids")
        os.environ.update({"CLOUDBASE_AUTH_PILOT_ENABLED": "true",
            "CLOUDBASE_AUTH_ENV_ID": config["env_id"],
            "CLOUDBASE_AUTH_PROFILE": args.auth_profile,
            "CLOUDBASE_AUTH_PILOT_USER_IDS": json.dumps(config["allowed_user_ids"])})
    else:
        os.environ["CLOUDBASE_AUTH_PILOT_ENABLED"] = "false"
    import uvicorn
    from app.demo_site import create_demo_site
    print(f"Local fictional demo: {origin}/tools/tasks", flush=True)
    print("No personal data or cloud changes. SQLite: backend/data/interactive-demo.db (24h demo workspaces).", flush=True)
    uvicorn.run(create_demo_site(), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()

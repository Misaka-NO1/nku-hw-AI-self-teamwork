"""Local, same-origin demo UI + REST. Never a production/cloud entrypoint."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.main import app as api_app

TOOLS = frozenset({"tasks", "import", "timetable", "map", "study", "affairs", "degree", "login", "calendar"})


def create_demo_site(frontend_root: Path | None = None) -> FastAPI:
    settings = get_settings()
    if settings.app_env not in {"development", "test"} or settings.auth_mode != "demo_fixture" or settings.allow_personal_uploads:
        raise ValueError("The local demo site requires development/test, demo_fixture and personal uploads disabled")
    root = frontend_root or Path(__file__).resolve().parents[2] / "frontend" / "dist-demo"
    if not (root / "index.html").is_file():
        raise ValueError("Build the frontend first using deploy/Start-Demo.ps1")

    @asynccontextmanager
    async def lifespan(_):
        async with api_app.router.lifespan_context(api_app):
            if settings.oauth_local_enabled:
                from app.core.oauth_local import initialize
                initialize(settings)
            yield

    site = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    if settings.oauth_local_enabled:
        from app.oauth_pilot_site import create_oauth_pilot
        site.mount("/oauth", create_oauth_pilot(settings))
    site.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @site.get("/")
    def home():
        return RedirectResponse("/tools/tasks")

    @site.get("/tools/{tool}")
    def tool_page(tool: str):
        if tool not in TOOLS:
            raise HTTPException(status_code=404, detail="Unknown tool page")
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-store"})

    # REST keeps its /api/v1 routes; unknown API requests must not return SPA HTML.
    site.mount("/", api_app)
    return site

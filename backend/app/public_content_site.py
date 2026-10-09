"""Read-only Agent tools plus their controlled map/PDF destinations.

No writable sessions, task commits, DB service-role key or personal uploads.
The MCP endpoint is authenticated separately from public licensed content.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings
from starlette.exceptions import HTTPException

from app.api.domains import router
from app.core.config import get_settings
from app.core.contracts import REPOSITORY_ROOT
from app.core.domain_adapter import _scenic_catalog
from app.core.envelope import failure
from app.core.errors import AppError
from app.core.public_content_bundle import verify_public_content_bundle
from app.core.request_id import current_request_id, resolve_request_id
from app.domains.study.library import StudyLibrary
from app.mcp.http import StaticBearerAuthMiddleware
from app.mcp.server import create_mcp_server


def create_public_content_site(root: Path | None = None) -> FastAPI:
    settings = get_settings()
    root = root or REPOSITORY_ROOT
    if settings.public_catalog_profile != "published" or settings.allow_personal_uploads or settings.auth_mode != "demo_fixture":
        raise ValueError("Public catalogs require published profile with personal uploads disabled")
    settings.validate_deployment()
    if settings.domain_bundle_manifest_path:
        verify_public_content_bundle(settings, root=root)
    elif settings.app_env in {"staging", "production"}:
        raise ValueError("Cloud content service requires the integrity manifest")
    server = create_mcp_server(settings)
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    if settings.mcp_public_url:
        parsed = urlsplit(settings.mcp_public_url)
        hosts.append(parsed.netloc); origins.append(f"{parsed.scheme}://{parsed.netloc}")
    mcp_app = server.streamable_http_app(streamable_http_path="/mcp", stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins))
    @asynccontextmanager
    async def lifespan(_):
        async with mcp_app.router.lifespan_context(mcp_app):
            yield
    site = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    @site.middleware("http")
    async def context(request, call_next):
        request.state.request_id = resolve_request_id(request)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    @site.exception_handler(AppError)
    async def app_error(request, error):
        return JSONResponse(status_code=error.status_code, content=failure(request_id=current_request_id(request),
            code=error.code, message=error.message, field_errors=error.field_errors, retryable=error.retryable).model_dump(mode="json"))
    @site.exception_handler(HTTPException)
    @site.exception_handler(RequestValidationError)
    async def bad_request(request, error):
        status = getattr(error, "status_code", 422)
        return JSONResponse(status_code=status, content=failure(request_id=current_request_id(request),
            code="NOT_FOUND" if status == 404 else "VALIDATION_ERROR", message="Unknown path or invalid request").model_dump(mode="json"))
    @site.exception_handler(Exception)
    async def dependency_error(request, _):
        return JSONResponse(status_code=503, content=failure(request_id=current_request_id(request),
            code="DEPENDENCY_UNAVAILABLE", message="Public catalog dependency unavailable", retryable=True).model_dump(mode="json"))
    @site.get("/__tcb_probe__")
    def probe():
        return {"status": "ok"}
    @site.get("/healthz")
    def health():
        return {"status": "ok", "build_id": settings.build_id, "personal_uploads": False,
            "scenic_data_version": _scenic_catalog(settings)["data_version"], "study_data_version": StudyLibrary().data_version()}
    site.include_router(router)
    site.mount("/assets", StaticFiles(directory=root / "frontend/dist/assets"))
    # Only package-approved files, never the editable data/ directory or server modules.
    site.mount("/campus-map", StaticFiles(directory=root / "campus-map", html=True))
    site.mount("/media/scenic", StaticFiles(directory=root / "frontend/dist/assets/scenic"))
    @site.get("/")
    def home():
        return RedirectResponse("/tools/map")
    @site.get("/tools/{tool}")
    def page(tool: str):
        if tool not in {"map", "study"}:
            raise HTTPException(404)
        return FileResponse(root / "frontend/dist/index.html", headers={"Cache-Control": "no-store"})
    @site.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def unknown_api(path: str):
        raise HTTPException(404)
    # Root mounting preserves the SDK's exact /mcp path and lifespan.
    site.mount("/", StaticBearerAuthMiddleware(mcp_app, settings.mcp_service_token) if settings.mcp_require_auth else mcp_app)
    return site

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import router as health_router
from app.api.demo import router as demo_router
from app.api.drafts import router as drafts_router
from app.api.schedules import router as schedules_router
from app.api.tasks import router as tasks_router
from app.core.config import get_settings
from app.core.envelope import FieldError, failure
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.core.request_id import current_request_id, resolve_request_id
from app.db.database import initialize_database


settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_database(get_settings())
    yield


app = FastAPI(title="NKU Campus Assistant API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = resolve_request_id(request)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    body = failure(
        request_id=current_request_id(request),
        code=exc.code,
        message=exc.message,
        field_errors=exc.field_errors,
        retryable=exc.retryable,
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    field_errors = [
        FieldError(
            field=".".join(str(part) for part in error["loc"]),
            code=error["type"],
            message=error["msg"],
        )
        for error in exc.errors()
    ]
    body = failure(
        request_id=current_request_id(request),
        code="VALIDATION_ERROR",
        message="Request validation failed",
        field_errors=field_errors,
    )
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codes = {401: "AUTH_REQUIRED", 403: "FORBIDDEN", 404: "NOT_FOUND", 429: "RATE_LIMITED"}
    body = failure(
        request_id=current_request_id(request),
        code=codes.get(exc.status_code, "INTERNAL_ERROR"),
        message=str(exc.detail),
        retryable=exc.status_code >= 500,
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error", extra={"request_id": current_request_id(request)})
    body = failure(
        request_id=current_request_id(request),
        code="INTERNAL_ERROR",
        message="Internal server error",
        retryable=True,
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))


app.include_router(health_router)
app.include_router(demo_router)
app.include_router(drafts_router)
app.include_router(schedules_router)
app.include_router(tasks_router)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port, reload=False)

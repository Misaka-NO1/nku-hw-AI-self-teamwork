import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.envelope import ApiEnvelope, success
from app.core.errors import AppError
from app.core.request_id import current_request_id
from app.db.database import probe_database


router = APIRouter(tags=["system"])


class HealthData(BaseModel):
    status: str
    build_id: str
    server_time: str


class ReadyData(HealthData):
    dependencies: dict[str, str]


def _server_time() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


@router.get("/healthz", response_model=ApiEnvelope[HealthData])
def healthz(request: Request) -> ApiEnvelope[HealthData]:
    settings = get_settings()
    return success(
        HealthData(status="ok", build_id=settings.build_id, server_time=_server_time()),
        request_id=current_request_id(request),
    )


@router.get("/readyz", response_model=ApiEnvelope[ReadyData])
def readyz(request: Request) -> ApiEnvelope[ReadyData]:
    settings = get_settings()
    try:
        probe_database(settings)
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise AppError(
            status_code=503,
            code="DEPENDENCY_UNAVAILABLE",
            message="Database readiness check failed",
            retryable=True,
        ) from exc
    return success(
        ReadyData(
            status="ready",
            build_id=settings.build_id,
            server_time=_server_time(),
            dependencies={"database": "ready"},
        ),
        request_id=current_request_id(request),
    )

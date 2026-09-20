from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


SCHEMA_VERSION = "1.0.0"
T = TypeVar("T")


class FieldError(BaseModel):
    field: str
    code: str
    message: str


class WarningItem(BaseModel):
    code: str
    message: str


class EvidenceRef(BaseModel):
    label: str
    source_ref: str
    locator: str


class Meta(BaseModel):
    schema_version: str = SCHEMA_VERSION
    request_id: str
    data_version: str | None = None
    calculation_version: str | None = None
    warnings: list[WarningItem] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ApiError(BaseModel):
    code: str
    message: str
    field_errors: list[FieldError] = Field(default_factory=list)
    retryable: bool = False


class ApiEnvelope(BaseModel, Generic[T]):
    ok: bool
    data: T | None
    error: ApiError | None
    meta: Meta


def success(
    data: T,
    *,
    request_id: str,
    data_version: str | None = None,
    calculation_version: str | None = None,
    warnings: list[WarningItem] | None = None,
    evidence_refs: list[EvidenceRef] | None = None,
) -> ApiEnvelope[T]:
    return ApiEnvelope[T](
        ok=True,
        data=data,
        error=None,
        meta=Meta(
            request_id=request_id,
            data_version=data_version,
            calculation_version=calculation_version,
            warnings=warnings or [],
            evidence_refs=evidence_refs or [],
        ),
    )


def failure(
    *,
    request_id: str,
    code: str,
    message: str,
    field_errors: list[FieldError] | None = None,
    retryable: bool = False,
) -> ApiEnvelope[Any]:
    return ApiEnvelope[Any](
        ok=False,
        data=None,
        error=ApiError(
            code=code,
            message=message,
            field_errors=field_errors or [],
            retryable=retryable,
        ),
        meta=Meta(request_id=request_id),
    )

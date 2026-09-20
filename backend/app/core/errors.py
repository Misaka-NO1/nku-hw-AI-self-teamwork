from dataclasses import dataclass, field

from app.core.envelope import FieldError


@dataclass(slots=True)
class AppError(Exception):
    status_code: int
    code: str
    message: str
    retryable: bool = False
    field_errors: list[FieldError] = field(default_factory=list)

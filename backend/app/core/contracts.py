import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from app.core.envelope import FieldError
from app.core.errors import AppError


REPOSITORY_ROOT = Path(__file__).parents[3]
CORE_SCHEMA_PATH = REPOSITORY_ROOT / "contracts" / "core.schema.json"


@lru_cache
def _core_schema() -> dict[str, Any]:
    return json.loads(CORE_SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache
def core_validator(definition: str) -> Draft202012Validator:
    schema = _core_schema()
    return Draft202012Validator(
        {
            "$schema": schema["$schema"],
            "$ref": f"#/$defs/{definition}",
            "$defs": schema["$defs"],
        },
        format_checker=FormatChecker(),
    )


def validate_contract(payload: dict[str, Any], definition: str) -> None:
    errors = sorted(core_validator(definition).iter_errors(payload), key=lambda item: list(item.path))
    if not errors:
        return
    field_errors = [
        FieldError(
            field=".".join(str(part) for part in error.absolute_path) or "$",
            code=error.validator or "schema",
            message=error.message,
        )
        for error in errors[:20]
    ]
    raise AppError(
        status_code=422,
        code="VALIDATION_ERROR",
        message=f"Payload does not match {definition}",
        field_errors=field_errors,
    )

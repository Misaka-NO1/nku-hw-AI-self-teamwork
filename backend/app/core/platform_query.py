"""Opt-in platform transport only; business schemas and algorithms stay frozen."""

import json
import math

from app.core.envelope import FieldError
from app.core.errors import AppError


PLATFORM_OPERATIONS = {
    "platform_validate_timetable": "validate_timetable",
    "platform_query_free_time": "query_free_time",
    "platform_check_time_plan": "check_time_plan",
    "platform_search_scenic_spots": "search_scenic_spots",
    "platform_search_study_materials": "search_study_materials",
    "platform_audit_degree_progress": "audit_degree_progress",
}
MAX_QUERY_BYTES = 131_072
MAX_QUERY_DEPTH = 64


def platform_input_schema() -> dict:
    return {
        "type": "object", "additionalProperties": False, "required": ["query_json"],
        "properties": {"query_json": {
            "type": "string", "minLength": 1, "maxLength": MAX_QUERY_BYTES,
            "description": ("Complete original request as JSON object text, at most 131072 UTF-8 bytes. "
                            "Keep null unquoted, arrays intact and all required fields; do not double-encode. "
                            "Do not replace null with the string null, omit fields or add defaults."),
        }},
    }


def _invalid() -> AppError:
    # Never expose submitted text, duplicate key names or parser exceptions.
    return AppError(status_code=422, code="VALIDATION_ERROR",
                    message="query_json must be one bounded, unambiguous JSON object",
                    field_errors=[FieldError(field="query_json", code="invalid_json",
                                             message="Provide a complete valid JSON object")])


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Non-finite JSON number")
    return number


def _reject_constant(value):
    raise ValueError("Non-JSON constant")


def decode_platform_query(arguments) -> dict:
    if (not isinstance(arguments, dict) or set(arguments) != {"query_json"}
            or not isinstance(arguments["query_json"], str)):
        raise _invalid()
    text = arguments["query_json"]
    try:
        if not text or len(text) > MAX_QUERY_BYTES or len(text.encode("utf-8")) > MAX_QUERY_BYTES:
            raise _invalid()
        payload = json.loads(text, object_pairs_hook=_unique_object,
                             parse_float=_finite_float, parse_constant=_reject_constant)
        if not isinstance(payload, dict):
            raise _invalid()
        pending = [(payload, 1)]
        while pending:
            value, depth = pending.pop()
            if depth > MAX_QUERY_DEPTH:
                raise _invalid()
            if isinstance(value, dict):
                for key, child in value.items():
                    key.encode("utf-8")  # Reject unpaired escaped surrogates too.
                    pending.append((child, depth + 1))
            elif isinstance(value, list):
                pending.extend((child, depth + 1) for child in value)
            elif isinstance(value, str):
                value.encode("utf-8")
    except (ValueError, UnicodeError, RecursionError):
        raise _invalid() from None
    return payload  # No type coercion, default filling or business interpretation.

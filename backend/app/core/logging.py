import json
import logging
import re
from collections.abc import Mapping
from typing import Any


REDACTED = "[REDACTED]"
SENSITIVE_KEYS = ("authorization", "cookie", "password", "secret", "token")
TEXT_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)([^,;\s]+(?:\s+[^,;\s]+)?)"),
    re.compile(r'(?i)(["\']?(?:password|secret|token)["\']?\s*[:=]\s*["\']?)([^"\',;\s}]+)'),
)


def _is_sensitive(key: Any) -> bool:
    normalized = str(key).casefold()
    return any(fragment in normalized for fragment in SENSITIVE_KEYS)


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: REDACTED if _is_sensitive(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        sanitized = value
        for pattern in TEXT_PATTERNS:
            sanitized = pattern.sub(rf"\1{REDACTED}", sanitized)
        return sanitized
    return value


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.msg)
        if record.args:
            record.args = redact(record.args)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        for field in ("method", "protocol_version", "tool_name", "duration_ms", "outcome"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

import logging

from app.core.logging import REDACTED, RedactingFilter, redact


def test_redact_removes_nested_secrets() -> None:
    value = {
        "user": "student",
        "authorization": "Bearer private-value",
        "nested": {"service_token": "private-token"},
    }

    assert redact(value) == {
        "user": "student",
        "authorization": REDACTED,
        "nested": {"service_token": REDACTED},
    }


def test_filter_redacts_text_log() -> None:
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "Authorization: Bearer secret", (), None
    )
    RedactingFilter().filter(record)
    assert "secret" not in record.getMessage()
    assert REDACTED in record.getMessage()

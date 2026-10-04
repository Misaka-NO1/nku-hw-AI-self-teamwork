"""Canonical B-schema transport tests; no live cloud/platform acceptance."""
import json
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.core.owned_time import decode_owned_time

EXAMPLES = json.loads((Path(__file__).parents[2] / "fixtures/oauth-pilot.demo.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("operation,key", [("free", "owned_free_time"), ("check", "owned_time_check")])
def test_owned_time_preserves_canonical_fields_and_null(operation, key):
    payload = EXAMPLES[key]
    assert decode_owned_time({"query_json": json.dumps(payload)}, operation) == payload


@pytest.mark.parametrize("arguments", [
    {}, {"query_json": {}}, {"query_json": "x" * 2049},
    {"query_json": "{}", "workspace_ref": "foreign-workspace"},
    {"query_json": '{"min_minutes":20,"min_minutes":30}'},
    {"query_json": '{"min_minutes":NaN}'},
    {"query_json": '{"min_minutes":1e999}'},
    {"query_json": '[]'},
])
def test_owned_time_rejects_ambiguous_transport_and_overrides(arguments):
    with pytest.raises(AppError) as result:
        decode_owned_time(arguments, "free")
    assert result.value.status_code == 422
    assert "foreign-workspace" not in result.value.message

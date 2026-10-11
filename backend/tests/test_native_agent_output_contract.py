"""Local synthetic checks for the platform's non-null success output projection.

Keep the browser API envelope unchanged; OpenAPI `nullable` is not JSON Schema
and may be ignored by a platform output validator. Never relax identity checks.
"""
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, ValidationError

from app.core.envelope import success


def schema():
    spec = json.loads((Path(__file__).resolve().parents[2] /
        "deploy/genios-workflows/native-onboarding-tools.openapi.json").read_text(encoding="utf-8"))
    return spec["components"]["schemas"]["OnboardingEnvelope"]


@pytest.mark.parametrize("kind,has_space,label", [
    ("first_use_confirmation", False, None),
    ("legacy_authorization_required", False, None),
    ("existing_space", True, "SPACE-FICTIONAL"),
    ("browser_authorized", True, "SPACE-FICTIONAL"),
])
def test_original_envelope_validates_nonnull_success_projection(kind, has_space, label):
    body = success({"status": kind, "has_space": has_space, "created": False,
        "space_label": label}, request_id="synthetic-request", data_version="native-identity-v1").model_dump(mode="json")
    assert body["error"] is None
    assert body["data"]["space_label"] == label
    Draft7Validator(schema()).validate(body)


def test_old_nullable_object_reproduces_platform_error():
    # OpenAPI 3.0 nullable does not change Draft7's required value type.
    old = {"type": "object", "properties": {"error": {"type": "object", "nullable": True}}}
    with pytest.raises(ValidationError, match="None is not of type 'object'"):
        Draft7Validator(old).validate({"error": None})


def test_projection_does_not_accept_missing_or_invalid_business_state():
    contract = schema()
    assert "error" not in contract["properties"]
    assert "space_label" not in contract["properties"]["data"]["properties"]
    for value in (None, {}, {"ok": True, "data": None, "meta": {}},
                  {"ok": True, "data": {"status": "bound", "has_space": "true", "created": False}, "meta": {}}):
        with pytest.raises(ValidationError):
            Draft7Validator(contract).validate(value)

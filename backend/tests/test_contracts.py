import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from app.main import app


CONTRACT_PATH = Path(__file__).parents[2] / "contracts" / "api.schema.json"
CORE_CONTRACT_PATH = Path(__file__).parents[2] / "contracts" / "core.schema.json"
FIXTURES_PATH = Path(__file__).parents[2] / "fixtures"


def test_api_contract_is_valid_and_accepts_health_response() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    envelope_schema = {
        "$schema": schema["$schema"],
        "$ref": "#/$defs/ApiEnvelope",
        "$defs": schema["$defs"],
    }

    with TestClient(app) as client:
        payload = client.get("/healthz").json()

    Draft202012Validator(
        envelope_schema,
        format_checker=FormatChecker(),
    ).validate(payload)


def test_d_owned_notice_fixtures_match_shared_core_contract() -> None:
    schema = json.loads(CORE_CONTRACT_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    notice_schema = {
        "$schema": schema["$schema"],
        "$ref": "#/$defs/NoticeDraft",
        "$defs": schema["$defs"],
    }
    validator = Draft202012Validator(notice_schema, format_checker=FormatChecker())

    fixtures = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURES_PATH.glob("notice-*.demo.json"))
    ]
    assert len(fixtures) == 3
    for fixture in fixtures:
        validator.validate(fixture)

    invalid = deepcopy(fixtures[0])
    invalid["timezone"] = "UTC"
    with pytest.raises(ValidationError):
        validator.validate(invalid)


def test_demo_timetable_matches_shared_core_contract() -> None:
    schema = json.loads(CORE_CONTRACT_PATH.read_text(encoding="utf-8"))
    timetable_schema = {
        "$schema": schema["$schema"],
        "$ref": "#/$defs/TimetableImport",
        "$defs": schema["$defs"],
    }
    payload = json.loads((FIXTURES_PATH / "timetable.demo.json").read_text(encoding="utf-8"))
    Draft202012Validator(timetable_schema, format_checker=FormatChecker()).validate(payload)

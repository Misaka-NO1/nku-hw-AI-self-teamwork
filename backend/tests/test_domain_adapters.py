import asyncio
import copy
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from mcp import Client

from app.core.config import Settings, get_settings
from app.core.contracts import boundary_schema
from app.core.demo import load_fixture
from app.core.domain_adapter import OPERATIONS, PUBLIC_DEMO_WORKSPACE_REF
from app.core import domain_adapter
from app.main import app
from app.mcp.server import create_mcp_server


SCENIC = {"campus_id": "demo-campus", "tags": ["flower"], "month": 3, "limit": 5}
STUDY = {"course_id": "demo-CS101", "topic": None, "limit": 5}
DEGREE = {"workspace_ref": PUBLIC_DEMO_WORKSPACE_REF, "plan_id": "demo-cs-plan-v1", "transcript_ref": "demo-transcript-01"}
CASES = [
    ("validate_timetable", "/api/v1/schedules/validate", "timetable.demo.json"),
    ("query_free_time", "/api/v1/time/free-slots", "time-free-query.demo.json"),
    ("check_time_plan", "/api/v1/time/check", "time-event-query.demo.json"),
    ("check_time_plan", "/api/v1/time/check", "time-deadline-query.demo.json"),
    ("search_scenic_spots", "/api/v1/scenic/spots", SCENIC),
    ("search_study_materials", "/api/v1/study/materials", STUDY),
    ("audit_degree_progress", "/api/v1/degree/audit", DEGREE),
]


@pytest.fixture
def rest(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'domains.db').as_posix()}")
    monkeypatch.setenv("AUTH_MODE", "demo_fixture")
    get_settings.cache_clear()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def mcp_call(name, payload, runtime=None):
    server = create_mcp_server(runtime or Settings(app_env="test", mcp_enable_domain_tools=True))
    async def scenario():
        async with Client(server) as client:
            return await client.call_tool(name, payload)
    return asyncio.run(scenario())


def http_call(client, path, payload):
    if path in {"/api/v1/scenic/spots", "/api/v1/study/materials"}:
        return client.get(path, params={"query": json.dumps(payload, ensure_ascii=False)})
    return client.post(path, json=payload)


def comparable(body):
    result = copy.deepcopy(body)
    del result["meta"]["request_id"]
    return result


def assert_envelope(body):
    Draft202012Validator(boundary_schema("ApiEnvelope"), format_checker=FormatChecker()).validate(body)
    assert body["meta"]["request_id"]


@pytest.mark.parametrize("name,path,source", CASES)
def test_d06_rest_mcp_same_fixture_same_result(rest, name, path, source):
    payload = load_fixture(source) if isinstance(source, str) else copy.deepcopy(source)
    response = http_call(rest, path, payload)
    result = mcp_call(name, payload)
    assert response.status_code == 200, response.text
    assert result.is_error is False
    assert_envelope(response.json())
    assert_envelope(result.structured_content)
    assert comparable(response.json()) == comparable(result.structured_content)
    assert response.json()["meta"]["schema_version"] == "1.0.0"
    assert response.json()["meta"]["data_version"] == "demo-v1"
    assert "DEMO_DATA" in {item["code"] for item in response.json()["meta"]["warnings"]}


def test_tool_discovery_is_opt_in_and_exactly_the_frozen_schemas():
    async def scenario():
        async with Client(create_mcp_server(Settings(app_env="test"))) as client:
            baseline = (await client.list_tools()).tools
        async with Client(create_mcp_server(Settings(app_env="test", mcp_enable_domain_tools=True))) as client:
            tools = (await client.list_tools()).tools
        return baseline, tools
    baseline, tools = asyncio.run(scenario())
    assert [tool.name for tool in baseline] == ["health_probe"]
    assert [tool.name for tool in tools] == ["health_probe", *OPERATIONS]
    for tool in tools[1:]:
        assert tool.input_schema == boundary_schema(OPERATIONS[tool.name])
        assert tool.output_schema == boundary_schema("ApiEnvelope")
        assert tool.annotations.read_only_hint is True
        assert tool.input_schema["additionalProperties"] is False
    assert not {"commit_task", "commit_schedule", "save_todo", "create_task_draft", "get_task_status"} & {tool.name for tool in tools}


@pytest.mark.parametrize("mutation", [
    {"limit": 21}, {"limit": True}, {"limit": "5"}, {"month": 13},
    {"tags": ["flower", "flower"]}, {"user_id": "a-different-user"},
])
def test_bad_query_is_rejected_consistently_without_coercion(rest, mutation):
    payload = {**SCENIC, **mutation}
    response = http_call(rest, "/api/v1/scenic/spots", payload)
    result = mcp_call("search_scenic_spots", payload)
    assert response.status_code == 422
    assert result.is_error is True
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert comparable(response.json()) == comparable(result.structured_content)


@pytest.mark.parametrize("payload", [
    {"tags": [], "month": None, "limit": 5},
    {"campus_id": None, "tags": [], "limit": 5},
    {"campus_id": None, "tags": [], "month": None},
    [],
])
def test_missing_explicit_nullable_fields_or_wrong_root_is_rejected(rest, payload):
    response = http_call(rest, "/api/v1/scenic/spots", payload)
    result = mcp_call("search_scenic_spots", payload) if isinstance(payload, dict) else None
    assert response.status_code == 422
    if result:
        assert result.is_error is True
        assert comparable(response.json()) == comparable(result.structured_content)


def test_query_encoding_unicode_null_and_empty_tags(rest):
    payload = {"campus_id": None, "tags": [], "month": None, "limit": 20}
    assert comparable(http_call(rest, "/api/v1/scenic/spots", payload).json()) == comparable(mcp_call("search_scenic_spots", payload).structured_content)
    payload = {**STUDY, "topic": "递归"}
    assert comparable(http_call(rest, "/api/v1/study/materials", payload).json()) == comparable(mcp_call("search_study_materials", payload).structured_content)


@pytest.mark.parametrize("params", [{}, {"query": "not-json"}, {"query": "{}", "limit": "5"}, [("query", "{}"), ("query", "{}")]])
def test_get_only_accepts_one_complete_query_json(rest, params):
    assert rest.get("/api/v1/scenic/spots", params=params).status_code == 422


def test_degree_demo_expected_credits_and_no_graduation_claim(rest):
    data = http_call(rest, "/api/v1/degree/audit", DEGREE).json()["data"]
    assert data["data_coverage"]["total_earned_credits"] == "5.0"
    assert data["data_coverage"]["total_remaining_credits"] == "7.0"
    assert data["data_coverage"]["not_graduation_decision"] is True
    assert data["status"] == "incomplete"


def test_time_expected_free_slot_and_due_is_not_busy_block(rest):
    payload = load_fixture("time-free-query.demo.json")
    data = http_call(rest, "/api/v1/time/free-slots", payload).json()["data"]
    # demo 校历为 14 节新时刻（B 模块 d5ca61a 起）：周一第 1-4 节连续排到 11:40，
    # 窗口 08:00-12:45 内 ≥30 分钟的空档只剩午后一段。
    assert data["slots"] == [{"start": "2026-09-21T11:40:00+08:00", "end": "2026-09-21T12:45:00+08:00", "duration_minutes": 65}]
    payload = copy.deepcopy(load_fixture("time-deadline-query.demo.json"))
    payload["estimated_minutes"] = None
    response = http_call(rest, "/api/v1/time/check", payload)
    result = mcp_call("check_time_plan", payload)
    assert comparable(response.json()) == comparable(result.structured_content)
    assert "estimated_minutes" in response.json()["data"]["needs_confirmation"]


def test_non_fixture_timetable_even_labeled_demo_is_rejected(rest):
    payload = copy.deepcopy(load_fixture("timetable.demo.json"))
    payload["courses"][0]["title"] = "Private course label that must not be returned"
    response = http_call(rest, "/api/v1/schedules/validate", payload)
    result = mcp_call("validate_timetable", payload)
    assert response.status_code == 403
    assert result.is_error is True
    assert response.json()["error"]["code"] == "DEMO_ONLY"
    assert comparable(response.json()) == comparable(result.structured_content)
    assert "Private course" not in str(response.json()) + str(result.structured_content)


def test_mcp_service_cannot_use_a_browser_workspace_even_with_its_reference(rest):
    workspace = rest.post("/api/v1/demo/workspaces", json={"fixture_set_id": "demo-v1"}).json()["data"]
    payload = {**load_fixture("time-free-query.demo.json"), "workspace_ref": workspace["workspace_ref"]}
    result = mcp_call("query_free_time", payload)
    assert result.is_error is True
    assert result.structured_content["error"]["code"] == "IDENTITY_NOT_VERIFIED"
    # Browser ownership alone is not a saved timetable: no silent fixture fallback.
    response = http_call(rest, "/api/v1/time/free-slots", payload)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    other = {**payload, "workspace_ref": "another-person-workspace"}
    assert http_call(rest, "/api/v1/time/free-slots", other).status_code == 404
    rest.cookies.clear()
    assert http_call(rest, "/api/v1/time/free-slots", payload).status_code == 401


@pytest.mark.parametrize("change", [{"plan_id": "private-plan"}, {"transcript_ref": "../private-file"}, {"records": []}])
def test_degree_only_resolves_server_fixed_resources(rest, change):
    payload = {**DEGREE, **change}
    response = http_call(rest, "/api/v1/degree/audit", payload)
    result = mcp_call("audit_degree_progress", payload)
    assert response.status_code in {404, 422}
    assert result.is_error is True
    assert comparable(response.json()) == comparable(result.structured_content)


def test_public_details_download_and_no_private_or_index_body(rest):
    spot = rest.get("/api/v1/scenic/spots/demo-spot-01")
    assert spot.status_code == 200
    assert "暂无经核验的当前花况" in spot.json()["data"]["bloom_note"]
    assert rest.get("/api/v1/scenic/spots/missing").status_code == 404
    assert rest.get("/api/v1/study/materials/demo-note-01").json()["data"]["content_available"] is True
    index = rest.get("/api/v1/study/materials/demo-index-02").json()["data"]
    assert index["content_available"] is False and index["evidence"] == []
    download = rest.get("/api/v1/study/materials/demo-note-01/download")
    assert download.status_code == 200
    assert "终止条件" in download.text
    assert "attachment" in download.headers["content-disposition"]
    for identifier in ("demo-private-03", "demo-pending-04", "demo-index-02", str(uuid4())):
        assert rest.get(f"/api/v1/study/materials/{identifier}/download").status_code == 404
    for identifier in ("demo-private-03", "demo-pending-04"):
        assert rest.get(f"/api/v1/study/materials/{identifier}").status_code == 404


def test_unverified_binding_mode_fails_closed(rest, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "trusted_binding")
    get_settings.cache_clear()
    response = http_call(rest, "/api/v1/degree/audit", DEGREE)
    result = mcp_call("audit_degree_progress", DEGREE, Settings(app_env="test", auth_mode="trusted_binding", mcp_enable_domain_tools=True))
    assert response.status_code == 403
    assert result.structured_content["error"]["code"] == "IDENTITY_NOT_VERIFIED"
    assert comparable(response.json()) == comparable(result.structured_content)


def test_failed_dependency_returns_same_sanitized_failure(rest, monkeypatch):
    def broken_catalog():
        raise OSError("sensitive internal path or credential must not escape")
    monkeypatch.setattr(domain_adapter.scenic, "load_catalog", broken_catalog)
    response = http_call(rest, "/api/v1/scenic/spots", SCENIC)
    result = mcp_call("search_scenic_spots", SCENIC)
    assert response.status_code == 503
    assert result.is_error is True
    assert response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert comparable(response.json()) == comparable(result.structured_content)
    assert "sensitive internal" not in str(response.json()) + str(result.structured_content)


def test_browser_confirmed_schedule_and_task_are_read_but_drafts_are_not(rest):
    workspace = rest.post("/api/v1/demo/workspaces", json={"fixture_set_id": "demo-v1"}).json()["data"]
    csrf = {"X-CSRF-Token": workspace["csrf_token"]}

    def confirm_and_commit(draft, kind):
        confirmation = rest.post("/api/v1/confirmations", headers={**csrf, "Idempotency-Key": f"confirm-{kind}-001"},
                                 json={key: draft[key] for key in ("draft_id", "revision", "payload_hash")})
        assert confirmation.status_code == 200
        committed = rest.post(f"/api/v1/{kind}/commit", headers=csrf,
                              json={"confirmation_id": confirmation.json()["data"]["confirmation_id"], "idempotency_key": f"commit-{kind}-001"})
        assert committed.status_code == 200

    schedule_draft = rest.post("/api/v1/schedules/import-drafts", headers={**csrf, "Idempotency-Key": "schedule-draft-001"},
                               json=load_fixture("timetable.demo.json"))
    assert schedule_draft.status_code == 200
    confirm_and_commit(schedule_draft.json()["data"], "schedules")
    query = {**load_fixture("time-free-query.demo.json"), "workspace_ref": workspace["workspace_ref"]}
    assert http_call(rest, "/api/v1/time/free-slots", query).json()["data"]["slots"]
    task_draft = rest.post("/api/v1/tasks/drafts", headers={**csrf, "Idempotency-Key": "task-draft-001"},
                          json={"workspace_ref": workspace["workspace_ref"], "notice": load_fixture("notice-event.demo.json")})
    assert task_draft.status_code == 200
    assert http_call(rest, "/api/v1/time/free-slots", query).json()["data"]["slots"]
    # 14 节新时刻下课间空档（09:40-10:00）只有 20 分钟，用 min_minutes=15 观察任务占用；
    # 草稿提交前该空档仍应可见。
    fine = {**query, "min_minutes": 15}
    assert len(http_call(rest, "/api/v1/time/free-slots", fine).json()["data"]["slots"]) == 2
    confirm_and_commit(task_draft.json()["data"], "tasks")
    # 已确认任务（09:20-10:20）消耗了课间空档，剩余空档只剩午后一段。
    assert http_call(rest, "/api/v1/time/free-slots", fine).json()["data"]["slots"] == [
        {"start": "2026-09-21T11:40:00+08:00", "end": "2026-09-21T12:45:00+08:00", "duration_minutes": 65}
    ]
    # Shared service credentials still cannot read this browser-owned workspace.
    assert mcp_call("query_free_time", query).structured_content["error"]["code"] == "IDENTITY_NOT_VERIFIED"

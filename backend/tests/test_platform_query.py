import asyncio
import copy
import json

import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from app.core import domain_adapter
from app.core.config import Settings
from app.core.contracts import boundary_schema
from app.core.demo import load_fixture
from app.core.domain_adapter import OPERATIONS
from app.core.errors import AppError
from app.core.platform_query import MAX_QUERY_BYTES, PLATFORM_OPERATIONS, decode_platform_query, platform_input_schema
from app.mcp.server import create_mcp_server
from test_domain_adapters import CASES, SCENIC, STUDY, assert_envelope, comparable, http_call, rest


def runtime():
    return Settings(_env_file=None, app_env="test", mcp_enable_domain_tools=True,
                    mcp_enable_platform_compat_tools=True)


def call(name, arguments):
    async def scenario():
        async with Client(create_mcp_server(runtime())) as client:
            return await client.call_tool(name, arguments)
    return asyncio.run(scenario())


def compat_call(name, payload):
    return call("platform_" + name, {"query_json": json.dumps(payload, ensure_ascii=False, allow_nan=False)})


def test_opt_in_discovery_preserves_original_schemas_and_annotations():
    async def scenario():
        async with Client(create_mcp_server(runtime())) as client:
            return (await client.list_tools()).tools
    tools = asyncio.run(scenario())
    assert list(PLATFORM_OPERATIONS.values()) == list(OPERATIONS)
    assert [tool.name for tool in tools] == ["health_probe", *OPERATIONS, *PLATFORM_OPERATIONS]
    for tool in tools[1:]:
        assert tool.input_schema == (platform_input_schema() if tool.name in PLATFORM_OPERATIONS
                                     else boundary_schema(OPERATIONS[tool.name]))
        assert tool.output_schema == boundary_schema("ApiEnvelope")
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
    assert Settings(_env_file=None).mcp_enable_platform_compat_tools is False


def test_compat_cannot_be_enabled_without_domains():
    config = Settings(_env_file=None, mcp_enable_platform_compat_tools=True)
    with pytest.raises(ValueError, match="requires"):
        config.validate_deployment()
    with pytest.raises(ValueError, match="requires"):
        create_mcp_server(config)


def test_compat_name_is_not_executable_when_disabled():
    server = create_mcp_server(Settings(_env_file=None, app_env="test", mcp_enable_domain_tools=True))
    with pytest.raises(ToolError):
        asyncio.run(server.call_tool("platform_search_study_materials", {"query_json": json.dumps(STUDY)}))


@pytest.mark.parametrize("name,path,source", CASES)
def test_compat_rest_and_original_mcp_fixture_parity(rest, name, path, source):
    payload = load_fixture(source) if isinstance(source, str) else copy.deepcopy(source)
    http = http_call(rest, path, payload)
    original = call(name, payload)
    compat = compat_call(name, payload)
    assert http.status_code == 200 and not original.is_error and not compat.is_error
    assert_envelope(compat.structured_content)
    assert comparable(http.json()) == comparable(original.structured_content) == comparable(compat.structured_content)


@pytest.mark.parametrize("payload", [
    {"campus_id": None, "tags": [], "month": None, "limit": 5},
    {"course_id": "demo-CS101", "topic": None, "limit": 5},
    {"course_id": "demo-CS101", "topic": "递归", "limit": 5},
    {"course_id": "demo-CS101", "topic": "null", "limit": 5},
    {"course_id": "demo-CS101", "topic": "", "limit": 5},
])
def test_null_empty_array_unicode_and_literal_strings_keep_original_meaning(rest, payload):
    study = "course_id" in payload
    name = "search_study_materials" if study else "search_scenic_spots"
    path = "/api/v1/study/materials" if study else "/api/v1/scenic/spots"
    assert decode_platform_query({"query_json": json.dumps(payload, ensure_ascii=False)}) == payload
    result = compat_call(name, payload)
    assert comparable(result.structured_content) == comparable(http_call(rest, path, payload).json())
    if study and payload["topic"] is None:
        assert {item["material_id"] for item in result.structured_content["data"]} == {"demo-note-01", "demo-index-02"}
    if study and payload["topic"] == "null":
        assert result.structured_content["data"] == []  # Must NOT turn a literal string into null.


@pytest.mark.parametrize("payload", [
    {**SCENIC, "limit": True}, {**SCENIC, "limit": "5"}, {**SCENIC, "limit": 0},
    {**SCENIC, "month": "null"}, {**SCENIC, "tags": "[]"}, {**SCENIC, "user_id": "extra"},
    {"tags": [], "month": None, "limit": 5},
])
def test_business_validation_remains_strict(rest, payload):
    result = compat_call("search_scenic_spots", payload)
    original = call("search_scenic_spots", payload)
    http = http_call(rest, "/api/v1/scenic/spots", payload)
    assert result.is_error and http.status_code == 422
    assert comparable(result.structured_content) == comparable(original.structured_content) == comparable(http.json())


@pytest.mark.parametrize("arguments", [
    {}, {"query_json": None}, {"query_json": 1}, {"query_json": {}},
    {"query_json": "{}", "operation": "save_todo"}, {"query_json": ""},
    {"query_json": "SECRET-not-json"}, {"query_json": "[]"}, {"query_json": "null"},
    {"query_json": '"{}"'}, {"query_json": '{"SECRET":1,"SECRET":2}'},
    {"query_json": '{"outer":{"SECRET":1,"SECRET":2}}'},
    {"query_json": '{"x":NaN}'}, {"query_json": '{"x":Infinity}'},
    {"query_json": '{"x":-Infinity}'}, {"query_json": '{"x":1e999}'},
    {"query_json": '{"x":"\\ud800"}'}, {"query_json": '{"\\ud800":1}'},
    {"query_json": '{"x":"' + "中" * (MAX_QUERY_BYTES // 3) + '"}'},
    {"query_json": " " * (MAX_QUERY_BYTES + 1)},
    {"query_json": '{"x":' + "[" * 65 + "0" + "]" * 65 + "}"},
    {"query_json": '{"x":' + "[" * 1100 + "0" + "]" * 1100 + "}"},
])
def test_malformed_transport_returns_sanitized_business_envelope(arguments, caplog):
    # Call the SDK public extension directly so invalid outer arguments also
    # exercise our envelope handling, independently of client-side validation.
    result = asyncio.run(create_mcp_server(runtime()).call_tool("platform_search_study_materials", arguments))
    assert result.is_error and result.structured_content["error"]["code"] == "VALIDATION_ERROR"
    assert result.structured_content["data"] is None
    assert_envelope(result.structured_content)
    assert "SECRET" not in str(result.structured_content) + caplog.text


def test_transport_byte_limit_boundary():
    query = '{"x":""}'
    text = query + " " * (MAX_QUERY_BYTES - len(query))
    assert decode_platform_query({"query_json": text}) == {"x": ""}
    with pytest.raises(AppError):
        decode_platform_query({"query_json": text + " "})


@pytest.mark.parametrize("name,source,change,code", [
    ("query_free_time", "time-free-query.demo.json", {"workspace_ref": "demo-unbound-test"}, "IDENTITY_NOT_VERIFIED"),
    ("audit_degree_progress", "degree-query.demo.json", {"plan_id": "demo-missing-plan"}, "NOT_FOUND"),
    ("audit_degree_progress", "degree-query.demo.json", {"transcript_ref": "../private-file"}, "NOT_FOUND"),
])
def test_fixed_resource_and_identity_checks_are_not_bypassed(name, source, change, code):
    payload = {**load_fixture(source), **change}
    result = compat_call(name, payload)
    assert result.is_error and result.structured_content["error"]["code"] == code
    assert comparable(result.structured_content) == comparable(call(name, payload).structured_content)


def test_compat_cannot_read_browser_workspace(rest):
    workspace = rest.post("/api/v1/demo/workspaces", json={"fixture_set_id": "demo-v1"}).json()["data"]
    payload = {**load_fixture("time-free-query.demo.json"), "workspace_ref": workspace["workspace_ref"]}
    assert compat_call("query_free_time", payload).structured_content["error"]["code"] == "IDENTITY_NOT_VERIFIED"


def test_compat_rejects_non_fixture_timetable():
    payload = copy.deepcopy(load_fixture("timetable.demo.json"))
    payload["courses"][0]["title"] = "SECRET-nonfixture"
    result = compat_call("validate_timetable", payload)
    assert result.is_error and result.structured_content["error"]["code"] == "DEMO_ONLY"
    assert "SECRET" not in str(result.structured_content)


def test_compat_dependency_error_does_not_leak_input_or_exception(monkeypatch, caplog):
    def broken():
        raise OSError("SECRET-path-or-credential")
    monkeypatch.setattr(domain_adapter.scenic, "load_catalog", broken)
    result = compat_call("search_scenic_spots", SCENIC)
    assert result.is_error and result.structured_content["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert "SECRET" not in str(result.structured_content) + caplog.text

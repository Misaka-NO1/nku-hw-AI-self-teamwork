import asyncio
import json
from pathlib import Path
from mcp import Client
from app.mcp.degree import create_degree_mcp_server, TOOL_NAME


def call(arguments, *, raw=False):
    async def scenario():
        async with Client(create_degree_mcp_server()) as client:
            tools = (await client.list_tools()).tools
            result = await client.call_tool(TOOL_NAME, arguments if raw else {"query_json": json.dumps(arguments, ensure_ascii=False)})
        return tools, result
    return asyncio.run(scenario())


def test_isolated_degree_tool_computes_supplied_data_without_demo_fallback():
    observation = {"kind": "degree-table-observation", "source": {
        "url": "https://eamis.nankai.edu.cn/eams/myPlanCompl.action", "captured_at": "2026-01-01T00:00:00Z", "coverage": "unknown", "adapter_verified": False},
        "headers": ["序号", "课程序号", "课程名称", "要求学分", "实修学分", "成绩", "是否通过", "备注"],
        "rows": [{"locator": "table-row:2", "cells": ["1 虚构模块", "4", "2", "", "缺2学分缺1门", ""]}]}
    tools, result = call({"observation": observation})
    assert [tool.name for tool in tools] == [TOOL_NAME]
    assert tools[0].input_schema["required"] == ["query_json"]
    assert tools[0].input_schema["properties"]["query_json"]["type"] == "string"
    assert result.is_error is False
    assert result.structured_content["data"]["modules"][0]["gap_credits"] == "2"
    assert result.structured_content["data"]["can_decide_complete"] is False


def test_tool_rejects_owner_reference_and_does_not_echo_private_input():
    _, result = call({"workspace_ref": "PRIVATE_MARKER"})
    assert result.is_error is True
    assert "PRIVATE_MARKER" not in str(result)
    _, result = call({"observation": {"private": "PRIVATE_MARKER"}})
    assert result.is_error is True
    assert "PRIVATE_MARKER" not in str(result)


def test_school_anonymous_acceptance_fixture_keeps_hierarchy_and_optional_branches():
    arguments = json.loads((Path(__file__).parents[2] / "fixtures/degree-page-anonymous-acceptance.json").read_text(encoding="utf-8"))
    tools, result = call(arguments)
    assert [tool.name for tool in tools] == [TOOL_NAME]
    assert result.is_error is False
    data = result.structured_content["data"]
    assert data["can_decide_complete"] is False
    summaries = {item["locator"]: item for item in data["module_summaries"]}
    for locator in ("table-row:2", "table-row:3"):
        assert summaries[locator]["observed_passed_credits"] == "2"
        assert summaries[locator]["observed_in_progress_credits"] == "2"
    assert summaries["table-row:3"]["discrepancies"]
    assert [course["name"] for course in summaries["table-row:6"]["missing_required_courses"]] == ["虚构实践课程"]
    assert summaries["table-row:9"]["optional_branch"] is True
    assert summaries["table-row:11"]["optional_branch"] is True
    assert not any(item["evidence"]["locator"] in {"table-row:9", "table-row:11"} for item in data["priority_suggestions"])


def test_transport_rejects_malformed_double_encoded_and_mutated_input():
    for arguments in ({"query_json": "not JSON PRIVATE_MARKER"},
                      {"query_json": json.dumps("PRIVATE_MARKER")},
                      {"query_json": {}}, {"observation": {}},
                      {"query_json": "{}", "owner": "PRIVATE_MARKER"}):
        _, result = call(arguments, raw=True)
        assert result.is_error is True
        assert "PRIVATE_MARKER" not in str(result)
    arguments = json.loads((Path(__file__).parents[2] / "fixtures/degree-page-anonymous-acceptance.json").read_text(encoding="utf-8"))
    arguments["observation"]["source"]["adapter_verified"] = "false"
    _, result = call(arguments)
    assert result.is_error is True

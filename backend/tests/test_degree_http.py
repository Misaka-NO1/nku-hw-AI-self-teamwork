import json
import pytest
from starlette.testclient import TestClient
from pydantic import SecretStr
from app.core.config import Settings
from app.mcp.degree_http import create_degree_http_app
from app.mcp.http import create_http_app


def settings(**changes):
    return Settings(_env_file=None, app_env="test", mcp_require_auth=True,
                    mcp_service_token=SecretStr("fictional-local-degree-test"), **changes)


HEADERS = {"Authorization": "Bearer fictional-local-degree-test",
           "Accept": "application/json, text/event-stream"}


def result(response):
    assert response.status_code == 200
    if response.headers["content-type"].startswith("application/json"):
        return response.json()
    return json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith("data: ")))


def initialize(client):
    response = client.post("/mcp", headers=HEADERS, json={"jsonrpc": "2.0", "id": 1,
        "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "anonymous-degree-qa", "version": "1"}}})
    assert "result" in result(response)
    headers = {**HEADERS, "Mcp-Session-Id": response.headers["mcp-session-id"]}
    assert client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    return headers


def test_degree_http_requires_auth_and_exposes_only_independent_tool():
    with TestClient(create_degree_http_app(settings()), base_url="http://localhost:8011") as client:
        assert client.get("/__tcb_probe__").status_code == 200
        assert client.post("/mcp", json={}).status_code == 401
        assert client.post("/mcp", headers={"Authorization": "Bearer wrong"}, json={}).status_code == 401
        headers = initialize(client)
        tools = result(client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2,
            "method": "tools/list", "params": {}}))
        assert [tool["name"] for tool in tools["result"]["tools"]] == ["analyze_supplied_degree_page"]
        observation = {"kind": "degree-table-observation", "source": {
            "url": "https://eamis.nankai.edu.cn/eams/myPlanCompl.action", "captured_at": "2026-01-01T00:00:00Z",
            "coverage": "unknown", "adapter_verified": False},
            "headers": ["序号", "课程序号", "课程名称", "要求学分", "实修学分", "成绩", "是否通过", "备注"],
            "rows": [{"locator": "table-row:2", "cells": ["1 虚构可选模块，非必须选择", "2", "0", "", "缺2学分", ""]}]}
        analyzed = result(client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 3,
            "method": "tools/call", "params": {"name": "analyze_supplied_degree_page", "arguments": {"query_json": json.dumps({"observation": observation}, ensure_ascii=False)}}}))
        data = analyzed["result"]["structuredContent"]
        assert data["ok"] is True
        assert data["data"]["module_summaries"][0]["optional_branch"] is True
        assert data["data"]["priority_suggestions"] == []
        assert data["data"]["can_decide_complete"] is False
        assert client.post("/mcp", headers=headers, content=b" " * 1_048_577).status_code == 413


def test_degree_http_refuses_auth_disabled_configuration():
    with pytest.raises(ValueError, match="requires configured service authentication"):
        create_degree_http_app(Settings(_env_file=None, app_env="test", mcp_require_auth=False))


def test_original_default_mcp_tool_list_stays_unchanged():
    with TestClient(create_http_app(settings()), base_url="http://localhost:8011") as client:
        headers = initialize(client)
        tools = result(client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2,
            "method": "tools/list", "params": {}}))
        assert [tool["name"] for tool in tools["result"]["tools"]] == ["health_probe"]

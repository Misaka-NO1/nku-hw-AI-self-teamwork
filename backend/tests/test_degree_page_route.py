from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
from app.api.degree_page import install_degree_page_routes
from app.core.errors import AppError


def client():
    app = FastAPI()
    @app.exception_handler(AppError)
    async def error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})
    def authorize(request):
        if request.headers.get("X-Test-Authorization") != "anonymous-fixture":
            raise AppError(401, "AUTH_REQUIRED", "授权缺失")
    install_degree_page_routes(app, authorize)
    return TestClient(app)


def test_analysis_requires_host_authorization_and_rejects_owner_override():
    c = client()
    assert c.post("/api/v1/degree/page/analyze", json={}).status_code == 401
    assert c.post("/api/v1/degree/page/analyze", json={"user_id": "other"}, headers={"X-Test-Authorization": "anonymous-fixture"}).status_code == 422


def test_route_preserves_unknown_and_does_not_echo_invalid_private_values():
    c = client()
    headers = {"X-Test-Authorization": "anonymous-fixture"}
    snapshot = {"plan_version": None, "source_coverage": "partial", "modules": [], "courses": []}
    r = c.post("/api/v1/degree/page/analyze", json=snapshot, headers=headers)
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "needs_verification"
    snapshot["modules"] = [{"module_id": "PRIVATE_TEST_VALUE", "parent_id": "missing"}]
    r = c.post("/api/v1/degree/page/analyze", json=snapshot, headers=headers)
    assert r.status_code == 422
    assert "PRIVATE_TEST_VALUE" not in r.text


def test_observation_route_preserves_reported_gap_and_in_progress():
    c = client()
    headers = {"X-Test-Authorization": "anonymous-fixture"}
    payload = {"kind": "degree-table-observation", "source": {
        "url": "https://eamis.nankai.edu.cn/eams/myPlanCompl.action", "captured_at": "2026-01-01T00:00:00Z",
        "coverage": "unknown", "adapter_verified": False},
        "headers": ["序号", "课程序号", "课程名称", "要求学分", "实修学分", "成绩", "是否通过", "备注"],
        "rows": [{"locator": "table-row:2", "cells": ["1 虚构模块（所有子项满足）", "4", "2", "", "缺2学分缺1门", ""]},
                 {"locator": "table-row:3", "cells": ["1", "ANON1", "虚构在读课", "2", "2", "--", "是", "在读"]}]}
    path = "/api/v1/degree/page/observation"
    assert c.post(path, json=payload).status_code == 401
    response = c.post(path, json=payload, headers=headers)
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["modules"][0]["gap_credits"] == "2"
    assert result["courses"][0]["state"] == "in_progress"
    assert result["can_decide_complete"] is False
    assert c.post(path + "?owner=other", json=payload, headers=headers).status_code == 422
    payload["rows"][0]["cells"][0] = "姓名：PRIVATE_TEST_VALUE"
    response = c.post(path, json=payload, headers=headers)
    assert response.status_code == 422
    assert "PRIVATE_TEST_VALUE" not in response.text

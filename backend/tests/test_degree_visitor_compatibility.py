"""Module 6 uses the merged private visitor owner, never a new identity."""
import pytest
from test_browser_visitor import visitors, begin
from test_cloud_identity_site import environment, headers, login


@pytest.mark.parametrize("route", ["observation", "analyze"])
def test_degree_visitor_session_csrf_logout_and_owner_context(visitors, route):
    _, _, _, a, b = visitors
    owner = begin(a).json()["data"]
    other = begin(b).json()["data"]
    path = "/api/v1/degree/page/" + route
    payload = ({"kind": "degree-table-observation", "source": {
        "url": "https://eamis.nankai.edu.cn/eams/myPlanCompl.action",
        "captured_at": "2026-10-10T00:00:00Z", "coverage": "unknown", "adapter_verified": False},
        "headers": ["序号", "课程序号", "课程名称", "要求学分", "实修学分", "成绩", "是否通过", "备注"],
        "rows": [{"locator": "table-row:2", "cells": ["1 虚构模块", "4", "0", "", "缺4学分", ""]}]}
        if route == "observation" else {"plan_version": None, "source_coverage": "partial", "modules": [], "courses": []})
    assert a.post(path, json=payload, headers=headers(owner)).status_code == 200
    assert b.post(path, json=payload, headers=headers(other)).status_code == 200
    assert b.post(path, json=payload, headers=headers(owner)).status_code == 403
    assert a.post(path, json=payload, headers={"Origin": "https://evil.invalid"}).status_code == 403
    assert a.post(path, json=payload).status_code == 403
    assert a.post(path + "?owner=other", json=payload, headers=headers(owner)).status_code == 422
    assert a.get("/tools/degree?degree_transfer_id=12345678-1234-1234-1234-123456789abc", follow_redirects=False).status_code == 200
    assert a.post("/api/v1/auth/cloudbase/logout", headers=headers(owner)).status_code == 200
    assert a.post(path, json=payload, headers=headers(owner)).status_code == 401
    assert b.post(path, json=payload, headers=headers(other)).status_code == 200


def test_degree_registered_owner_still_requires_existing_binding(visitors):
    _, _, _, a, _ = visitors
    owner = login(a)
    payload = {"plan_version": None, "source_coverage": "partial", "modules": [], "courses": []}
    assert a.post("/api/v1/degree/page/analyze", json=payload, headers=headers(owner)).status_code == 401

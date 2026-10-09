import asyncio
import copy
import json

import pytest
from fastapi.testclient import TestClient
from mcp import Client

from app.core.config import Settings, get_settings
from app.core.contracts import validate_boundary
from app.core.domain_adapter import execute_domain, public_principal
from app.core.errors import AppError
from app.main import app
from app.mcp.server import create_mcp_server


QUERY = {"course_id": "y1-s2-programming", "topic": "构造函数", "limit": 5}
SCENIC = {"campus_id": "nku-jinnan", "tags": [], "month": None, "limit": 20}


def runtime(**kwargs):
    return Settings(app_env="test", public_catalog_profile="published", mcp_enable_domain_tools=True,
                    mcp_enable_platform_compat_tools=True, **kwargs)


def tool(name, query):
    async def call():
        async with Client(create_mcp_server(runtime())) as client:
            return await client.call_tool(name, query)
    return asyncio.run(call())


@pytest.fixture
def rest(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_CATALOG_PROFILE", "published")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("AUTH_MODE", "demo_fixture")
    monkeypatch.setenv("ALLOW_PERSONAL_UPLOADS", "false")
    get_settings.cache_clear()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def comparable(body):
    body = copy.deepcopy(body)
    body["meta"].pop("request_id")
    return body


def test_real_study_rest_mcp_platform_same_source(rest):
    response = rest.get("/api/v1/study/materials", params={"query": json.dumps(QUERY)})
    result = tool("search_study_materials", QUERY)
    platform = tool("platform_search_study_materials", {"query_json": json.dumps(QUERY)})
    assert response.status_code == 200
    assert comparable(response.json()) == comparable(result.structured_content) == comparable(platform.structured_content)
    body = response.json()
    validate_boundary(body, "ApiEnvelope")
    assert body["meta"]["data_version"] == "y1-070600fb47f92e70"
    assert body["data"] and all(item["course_id"] == QUERY["course_id"] for item in body["data"])
    assert all("PDF 第" in ref["locator"] for ref in body["meta"]["evidence_refs"])
    assert "STUDY_TEXT_UNREVIEWED" in {item["code"] for item in body["meta"]["warnings"]}
    assert "DEMO_DATA" not in {item["code"] for item in body["meta"]["warnings"]}


def test_real_scenic_version_and_no_live_bloom_claim(rest):
    query = {**SCENIC, "campus_id": None}
    response = rest.get("/api/v1/scenic/spots", params={"query": json.dumps(query)})
    result = tool("search_scenic_spots", query)
    assert response.status_code == 200
    assert comparable(response.json()) == comparable(result.structured_content)
    body = response.json()
    assert len(body["data"]) == 20
    assert body["meta"]["data_version"] != "demo-v1"
    assert all(item["observation"] is None for item in body["data"])
    assert {"SCENIC_UNVERIFIED", "NOT_REALTIME"} <= {item["code"] for item in body["meta"]["warnings"]}
    spot = rest.get("/api/v1/scenic/spots/" + body["data"][0]["spot_id"])
    assert spot.json()["meta"]["data_version"] == body["meta"]["data_version"]


def test_generic_flower_query_covers_multiple_species_without_assumed_month(rest):
    query = {**SCENIC, "tags": ["flower"], "month": None, "limit": 20}
    result = rest.get("/api/v1/scenic/spots", params={"query": json.dumps(query)}).json()
    assert len(result["data"]) == 20
    species = {tag for spot in result["data"] for tag in spot["tags"]
               if ":" not in tag and tag not in {"flower", "architecture", "waterside", "landscape"}}
    assert species == {"海棠", "梨花", "芙蓉葵", "山桃", "樱花", "红叶李", "油菜花",
                       "榆叶梅", "格桑花", "二月兰", "菊花桃", "碧桃", "杏花", "丁香", "美人梅"}
    assert all(spot["observation"] is None for spot in result["data"])


def test_scenic_category_menus_and_species_selection_cover_the_catalog(rest):
    all_spots = {}
    for category, expected_count in (("flower", 20), ("architecture", 8), ("foliage", 5),
                                     ("waterside", 3), ("landscape", 1)):
        query = {**SCENIC, "tags": [category], "month": None, "limit": 20}
        body = rest.get("/api/v1/scenic/spots", params={"query": json.dumps(query)}).json()
        assert len(body["data"]) == expected_count
        assert all(category in spot["tags"] for spot in body["data"])
        all_spots.update({spot["spot_id"]: spot for spot in body["data"]})
    assert len(all_spots) == 34
    query = {**SCENIC, "tags": ["樱花"], "month": None, "limit": 20}
    selected = rest.get("/api/v1/scenic/spots", params={"query": json.dumps(query)}).json()["data"]
    assert {spot["name"] for spot in selected} == {"樱花树", "重瓣樱花"}
    assert all(spot["map_url"].startswith("/tools/map?") for spot in selected)


def test_purpose_classification_covers_every_spot_and_preserves_originals():
    from app.domains.scenic.service import CATALOG_PATH, load_catalog

    catalog = load_catalog(CATALOG_PATH.with_name("catalog.jinnan.json"))
    assert len(catalog["spots"]) == 34
    assert sum(len(spot["photos"]) for spot in catalog["spots"]) == 91
    assert all(any(tag.startswith("activity:") for tag in spot["tags"])
               for spot in catalog["spots"])
    grass = next(spot for spot in catalog["spots"] if spot["name"] == "津南大草原")
    assert "architecture" not in grass["tags"]
    assert {"landscape", "scene:grassland", "activity:picnic"} <= set(grass["tags"])


@pytest.mark.parametrize("tag", ["activity:walk", "activity:date"])
def test_couple_walk_can_find_bridge_and_grassland(rest, tag):
    query = {**SCENIC, "tags": [tag]}
    response = rest.get("/api/v1/scenic/spots", params={"query": json.dumps(query)})
    result = response.json()["data"]
    assert {"津南大草原", "绝美廊桥"} <= {spot["name"] for spot in result}
    assert all(spot["map_url"].startswith("/tools/map?") for spot in result)
    assert comparable(response.json()) == comparable(tool("platform_search_scenic_spots", {
        "query_json": json.dumps(query),
    }).structured_content)


def test_purpose_and_physical_tags_still_match_conjunction(rest):
    query = {**SCENIC, "tags": ["waterside", "activity:walk"]}
    result = rest.get("/api/v1/scenic/spots", params={"query": json.dumps(query)}).json()["data"]
    assert {spot["name"] for spot in result} == {"马蹄湖观景亭", "山桃"}
    query["tags"] = ["activity:picnic"]
    result = rest.get("/api/v1/scenic/spots", params={"query": json.dumps(query)}).json()["data"]
    assert [spot["name"] for spot in result] == ["津南大草原"]


def test_study_query_returns_direct_original_pdf_link(rest):
    query = {"course_id": "y1-s2-programming", "topic": "构造函数", "limit": 3}
    result = rest.get("/api/v1/study/materials", params={"query": json.dumps(query)}).json()
    assert result["data"]
    for material in result["data"]:
        assert material["file_format"] == "pdf"
        assert material["file_name"] == material["title"] + ".pdf"
        assert material["download_url"] == f"/api/v1/study/materials/{material['material_id']}/download"
        response = rest.get(material["download_url"])
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")


def test_original_pdf_download_and_private_unknown_not_exposed(rest):
    mid = "study-s2-programming-cd29346f86e832fa"
    response = rest.get(f"/api/v1/study/materials/{mid}/download")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-type"] == "application/pdf"
    assert rest.get(f"/api/v1/study/materials/{mid}").json()["meta"]["evidence_refs"]
    for identifier in ("study-s1-programming-7267a3cd0b2e11aa", "demo-note-01", "unknown"):
        for suffix in ("", "/download"):
            response = rest.get(f"/api/v1/study/materials/{identifier}{suffix}")
            assert response.status_code == 404
            assert "7267a3cd" not in response.text


def test_too_long_topic_does_not_become_dependency_failure(rest):
    query = {**QUERY, "topic": "x" * 501}
    response = rest.get("/api/v1/study/materials", params={"query": json.dumps(query)})
    assert response.status_code == 422
    assert tool("search_study_materials", query).structured_content["error"]["code"] == "VALIDATION_ERROR"


def test_ambiguous_or_missing_course_does_not_fall_back(rest):
    for course in ("高数", "y1-s2-probability", "missing"):
        query = {**QUERY, "course_id": course}
        assert rest.get("/api/v1/study/materials", params={"query": json.dumps(query)}).json()["data"] == []


def test_published_catalog_is_not_a_personal_identity_bypass():
    with pytest.raises(AppError) as error:
        execute_domain("search_study_materials", QUERY, public_principal(),
                       runtime(auth_mode="trusted_binding"), "test")
    assert error.value.code == "IDENTITY_NOT_VERIFIED"
    result = tool("query_free_time", {
        "workspace_ref": "someone-else", "window": {"start": "2026-09-21T09:00:00+08:00", "end": "2026-09-21T11:00:00+08:00"},
        "min_minutes": 30, "buffers": {"before_minutes": 0, "after_minutes": 0},
    })
    assert result.structured_content["error"]["code"] == "IDENTITY_NOT_VERIFIED"

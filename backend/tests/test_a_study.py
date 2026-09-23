import copy
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.core.security import Principal
from app.domains.study.export import build_public_knowledge, clean_excerpt
from app.domains.study.service import get_material, load_catalog, resolve_download, search_materials


@pytest.fixture
def principal():
    return Principal("demo-subject", "browser_user", frozenset({"demo:read"}), "test")


@pytest.fixture
def catalog():
    return load_catalog()


def query(course_id="demo-CS101", topic=None):
    return {"course_id": course_id, "topic": topic, "limit": 5}


def test_study_01_full_text_recursion_and_real_heading(principal, catalog):
    items = search_materials(query(topic="递归推进"), principal, catalog)
    assert [item["material_id"] for item in items] == ["demo-note-01"]
    assert [e["heading"] for e in items[0]["evidence"]] == ["递归的两个必要部分"]
    assert items[0]["evidence"][0]["page_label"] is None


def test_study_02_index_cannot_support_body_answer(principal, catalog):
    items = search_materials(query(topic="排序"), principal, catalog)
    assert [item["material_id"] for item in items] == ["demo-index-02"]
    assert items[0]["content_available"] is False
    assert items[0]["evidence"] == []
    with pytest.raises(AppError) as exc:
        resolve_download("demo-index-02", principal, catalog)
    assert exc.value.status_code == 404


def test_study_03_wrong_course_or_unknown_topic(principal, catalog):
    assert search_materials(query(course_id="demo-OTHER", topic="递归"), principal, catalog) == []
    assert search_materials(query(topic="量子计算"), principal, catalog) == []


def test_study_04_private_pending_and_unknown_are_hidden(principal, catalog):
    ids = {item["material_id"] for item in search_materials(query(), principal, catalog)}
    assert ids == {"demo-note-01", "demo-index-02"}
    for material_id in ["demo-private-03", "demo-pending-04", "missing"]:
        with pytest.raises(AppError) as exc:
            get_material(material_id, principal, catalog)
        assert exc.value.status_code == 404
        with pytest.raises(AppError):
            resolve_download(material_id, principal, catalog)


def test_study_05_download_allowlist_and_no_fabricated_page(principal, catalog):
    path = resolve_download("demo-note-01", principal, catalog)
    assert path.is_file() and path.name == "demo-note-01.md"
    assert "page_label: 无页码" in build_public_knowledge(catalog)
    assert "demo-private-03" not in build_public_knowledge(catalog)
    assert "demo-index-02" not in build_public_knowledge(catalog)
    changed = copy.deepcopy(catalog)
    changed["materials"][0]["file_ref"] = "knowledge/study/sources/../../secret.md"
    with pytest.raises(AppError):
        resolve_download("demo-note-01", principal, changed)
    changed["materials"][0]["file_ref"] = "javascript:alert(1)"
    with pytest.raises(AppError):
        resolve_download("demo-note-01", principal, changed)


def test_study_export_uses_real_sections_and_cleaning(catalog):
    result = build_public_knowledge(catalog)
    assert "chunk_id: demo-note-01-c1" in result
    assert "终止条件" in result
    assert "自创夹具" in result
    assert clean_excerpt("<script>remove</script>  a\t b") == "remove a b"

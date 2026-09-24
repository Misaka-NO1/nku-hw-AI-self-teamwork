import copy

import pytest

from app.core.errors import AppError
from app.domains.scenic.service import get_spot, load_catalog, search_spots


@pytest.fixture
def catalog():
    return load_catalog()


def test_map_02_known_and_unknown_deep_links(catalog):
    spot = get_spot("demo-spot-01", catalog)
    assert spot["map_url"] == "/tools/map?spot_id=demo-spot-01"
    with pytest.raises(AppError) as exc:
        get_spot("missing", catalog)
    assert exc.value.status_code == 404
    assert exc.value.code == "NOT_FOUND"


def test_map_04_historical_bloom_is_not_realtime(catalog):
    results = search_spots({"campus_id": "demo-campus", "tags": ["flower"], "month": 3, "limit": 5}, catalog)
    assert [item["spot_id"] for item in results] == ["demo-spot-01"]
    assert "历史上" in results[0]["bloom_note"]
    assert "暂无经核验的当前花况" in results[0]["bloom_note"]


def test_map_invalid_query_and_duplicate_spot(catalog):
    with pytest.raises(AppError) as exc:
        search_spots({"campus_id": None, "tags": [], "month": None, "limit": 21}, catalog)
    assert exc.value.code == "VALIDATION_ERROR"
    duplicate = copy.deepcopy(catalog)
    duplicate["spots"].append(duplicate["spots"][0])
    with pytest.raises(AppError) as exc:
        search_spots({"campus_id": None, "tags": [], "month": None, "limit": 5}, duplicate)
    assert exc.value.code == "VALIDATION_ERROR"


def test_map_unpublished_spot_never_leaks(catalog):
    changed = copy.deepcopy(catalog)
    changed["spots"][0]["rights_status"] = "pending"
    results = search_spots({"campus_id": None, "tags": [], "month": None, "limit": 20}, changed)
    assert "demo-spot-01" not in {item["spot_id"] for item in results}
    with pytest.raises(AppError):
        get_spot("demo-spot-01", changed)


def test_map_05_script_and_traversal_asset_paths_rejected(catalog):
    for path in ("javascript:alert(1)", "assets/../private.png"):
        changed = copy.deepcopy(catalog)
        changed["maps"][0]["asset_path"] = path
        with pytest.raises(AppError) as exc:
            search_spots({"campus_id": None, "tags": [], "month": None, "limit": 5}, changed)
        assert exc.value.code == "VALIDATION_ERROR"

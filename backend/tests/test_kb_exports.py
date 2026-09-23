"""KB 导出发布过滤测试（PR #3 审核意见 P1 回归）。

仅「已获投稿同意且审核通过」的经验卡可进入 KB_Course 导出；
pending / rejected / consent=false 一律不得导出。
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "knowledge" / "scripts" / "build_exports.py"

_spec = importlib.util.spec_from_file_location("build_exports", SCRIPT)
assert _spec and _spec.loader
build_exports = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("build_exports", build_exports)
_spec.loader.exec_module(build_exports)


def _card(
    experience_id: str, consent: bool, review_status: str, sample_count: int = 1
) -> dict:
    return {
        "experience_id": experience_id,
        "course_id": "demo-CS101",
        "offering_id": None,
        "term_id": "demo-term-2026A",
        "source_type": "student_experience",
        "sample_count": sample_count,
        "consent": consent,
        "review_status": review_status,
        "summary": "测试卡",
        "rating_aggregate": None,
    }


def _experiences(cards: list[dict]) -> dict:
    return {"dataset_kind": "demo", "cards": cards}


def test_pending_card_not_exported() -> None:
    cards = build_exports.publishable_experience_cards(
        _experiences([_card("e1", True, "pending")])
    )
    assert cards == []


def test_rejected_card_not_exported() -> None:
    cards = build_exports.publishable_experience_cards(
        _experiences([_card("e2", True, "rejected")])
    )
    assert cards == []


def test_no_consent_card_not_exported() -> None:
    cards = build_exports.publishable_experience_cards(
        _experiences([_card("e3", False, "approved")])
    )
    assert cards == []


def test_approved_with_consent_exported() -> None:
    cards = build_exports.publishable_experience_cards(
        _experiences([_card("e4", True, "approved")])
    )
    assert [c["experience_id"] for c in cards] == ["e4"]


def test_kb_course_export_filters_mixed_cards() -> None:
    catalog = {"dataset_kind": "demo", "data_version": "v1", "courses": []}
    experiences = _experiences(
        [
            _card("keep", True, "approved"),
            _card("drop-pending", True, "pending"),
            _card("drop-rejected", True, "rejected"),
            _card("drop-no-consent", False, "approved"),
        ]
    )
    kb = build_exports.build_kb_course(catalog, experiences)
    exported_ids = [c["experience_id"] for c in kb["experience_cards"]]
    assert exported_ids == ["keep"]


def test_kb_campus_keeps_verification_status() -> None:
    affairs = {
        "dataset_kind": "demo",
        "data_version": "v1",
        "entries": [
            {
                "entry_id": "x1",
                "kind": "entry",
                "title": "示例",
                "category": "academic",
                "campus_scope": [],
                "audience": [],
                "official_url": None,
                "login_required": "unknown",
                "campus_network_required": "unknown",
                "steps": [],
                "required_materials": [],
                "source_refs": [],
                "verified_at": None,
                "valid_until": None,
                "status": "needs_verification",
            }
        ],
    }
    kb = build_exports.build_kb_campus(affairs)
    assert kb["items"][0]["status"] == "needs_verification"
    assert "不得表述为学校规定" in kb["items"][0]["answer_constraint"]

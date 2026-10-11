"""第6模块页面进度分析内核的独立测试。

全部数据为匿名虚构值：不读取 fixtures、不联网、不依赖 audit 演示契约，
也不修改任何既有接口。测试锚定 ``analyze_page_progress`` 的规则边界：

* 有限非负学分与合法模块树的严格校验；
* 已通过 / 在读 / 缺必修 / 待核实 / 建议 的分类；
* 父子不双计、``any`` 不被 0/0 节点判完成、未知认定不计入；
* 重复记录与学分冲突不按输入顺序取第一条；
* 缺页 / 版本未知时不给出整体完成判断；
* 建议不含学期或开课信息。
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal

import pytest

from app.domains.degree.page_progress import (
    CALCULATION_VERSION,
    PageProgressValidationError,
    analyze_page_progress,
)

_FORBIDDEN_KEYS = {
    "semester",
    "semesters",
    "term",
    "terms",
    "academic_term",
    "offering",
    "offerings",
    "course_offering",
    "schedule",
    "course_time",
    "recommended_semester",
}
_FORBIDDEN_MESSAGE_TOKENS = ("学期", "开课", "选课", "上课时间")


def _snapshot(**overrides):
    base = {
        "plan_version": "anon-plan-v1",
        "source_coverage": "complete",
        "missing_pages": [],
        "repeat_policy": None,
        "evidence": {"page": "anonymous"},
        "courses": [],
        "modules": [],
    }
    base.update(overrides)
    return base


def _course(course_id, credits="3.0", state="passed", **extra):
    data = {
        "course_id": course_id,
        "code": f"CODE-{course_id}",
        "name": f"匿名课程{course_id}",
        "credits": credits,
        "state": state,
    }
    data.update(extra)
    return data


def _module(module_id, **overrides):
    data = {
        "module_id": module_id,
        "name": f"匿名模块{module_id}",
        "parent_id": None,
        "requirement": "credits",
        "required_credits": "3.0",
        "reported_earned_credits": None,
        "reported_remaining_credits": None,
        "reported_satisfied": None,
        "course_ids": [],
        "required_course_ids": [],
    }
    data.update(overrides)
    return data


def _find_module(result, module_id):
    return next(item for item in result["modules"] if item["module_id"] == module_id)


def _iter_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _iter_keys(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _iter_keys(item)


def _iter_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _iter_strings(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _iter_strings(item)


# ---------------------------------------------------------------------------
# 正常核算
# ---------------------------------------------------------------------------


def test_complete_module_is_counted_and_reports_complete():
    snapshot = _snapshot(
        courses=[_course("c1", credits="3.0", state="passed")],
        modules=[_module("m1", required_credits="3.0", course_ids=["c1"])],
    )
    result = analyze_page_progress(snapshot)

    module = result["modules"][0]
    assert module["module_id"] == "m1"
    assert module["id"] == "m1"
    assert Decimal(module["calculation"]["earned_credits"]) == Decimal("3.0")
    assert Decimal(module["calculation"]["remaining_credits"]) == Decimal("0")
    assert module["calculation"]["satisfied"] is True
    assert result["status"] == "complete_under_supported_rules"
    assert result["can_decide_complete"] is True
    assert result["calculation_version"] == CALCULATION_VERSION
    assert result["not_graduation_decision"] is True
    assert [item["course_id"] for item in result["passed_courses"]] == ["c1"]
    assert result["pending_verification"] == []


def test_decimal_credits_are_exact():
    snapshot = _snapshot(
        courses=[_course("c1", credits="0.1"), _course("c2", credits="0.2")],
        modules=[
            _module(
                "m1",
                requirement="credits",
                required_credits="0.3",
                course_ids=["c1", "c2"],
            )
        ],
    )
    result = analyze_page_progress(snapshot)
    calculation = result["modules"][0]["calculation"]
    assert Decimal(calculation["earned_credits"]) == Decimal("0.3")
    assert calculation["satisfied"] is True


def test_in_progress_is_not_counted_and_keeps_undetermined():
    snapshot = _snapshot(
        courses=[_course("c1", state="passed"), _course("c2", state="in_progress")],
        modules=[
            _module(
                "m1",
                requirement="all",
                required_credits="6.0",
                course_ids=["c1", "c2"],
            )
        ],
    )
    result = analyze_page_progress(snapshot)
    calculation = result["modules"][0]["calculation"]

    assert Decimal(calculation["earned_credits"]) == Decimal("3.0")
    assert calculation["satisfied"] is None
    assert calculation["in_progress_course_ids"] == ["c2"]
    assert [item["course_id"] for item in result["in_progress_courses"]] == ["c2"]
    assert result["status"] == "needs_verification"
    assert result["can_decide_complete"] is False


def test_parent_and_child_do_not_double_count_shared_course():
    snapshot = _snapshot(
        courses=[_course("c1", credits="3.0")],
        modules=[
            _module("root", required_credits="3.0", course_ids=["c1"], parent_id=None),
            _module("child", required_credits="3.0", course_ids=["c1"], parent_id="root"),
        ],
    )
    result = analyze_page_progress(snapshot)
    root = _find_module(result, "root")
    child = _find_module(result, "child")

    assert child["calculation"]["own_counted_course_ids"] == ["c1"]
    assert Decimal(child["calculation"]["earned_credits"]) == Decimal("3.0")
    assert root["calculation"]["own_counted_course_ids"] == []
    assert Decimal(root["calculation"]["earned_credits"]) == Decimal("0")
    assert Decimal(root["calculation"]["subtree_earned_credits"]) == Decimal("3.0")
    assert Decimal(result["independent_calculation"]["counted_credits"]) == Decimal("3.0")
    assert result["independent_calculation"]["counted_course_count"] == 1
    assert root["calculation"]["satisfied"] is True


def test_credits_met_but_required_course_missing_is_a_gap():
    snapshot = _snapshot(
        courses=[
            _course("c1", credits="3.0", state="passed"),
            _course("c2", credits="3.0", state="failed"),
        ],
        modules=[
            _module(
                "m1",
                requirement="credits",
                required_credits="3.0",
                course_ids=["c1", "c2"],
                required_course_ids=["c2"],
            )
        ],
    )
    result = analyze_page_progress(snapshot)
    calculation = result["modules"][0]["calculation"]

    assert Decimal(calculation["earned_credits"]) == Decimal("3.0")
    assert Decimal(calculation["remaining_credits"]) == Decimal("0")
    assert calculation["missing_required_course_ids"] == ["c2"]
    assert calculation["satisfied"] is False
    assert result["status"] == "incomplete"
    assert [
        (item["module_id"], item["course_id"])
        for item in result["missing_required_courses"]
    ] == [("m1", "c2")]


# ---------------------------------------------------------------------------
# all / any 与 0/0 陷阱
# ---------------------------------------------------------------------------


def test_any_is_not_satisfied_by_zero_requirement_child():
    snapshot = _snapshot(
        courses=[_course("c1", state="in_progress")],
        modules=[
            _module("root", requirement="any", required_credits=None),
            _module(
                "empty",
                requirement="credits",
                required_credits="0",
                parent_id="root",
            ),
            _module(
                "waiting",
                requirement="credits",
                required_credits="3.0",
                course_ids=["c1"],
                parent_id="root",
            ),
        ],
    )
    result = analyze_page_progress(snapshot)
    root = _find_module(result, "root")

    assert root["calculation"]["satisfied"] is None
    assert result["can_decide_complete"] is False
    assert result["status"] == "needs_verification"
    assert any(
        item["code"] == "zero_requirement_no_evidence"
        for item in result["pending_verification"]
    )


def test_zero_requirement_module_cannot_be_complete_on_0_over_0():
    snapshot = _snapshot(
        modules=[_module("m1", requirement="credits", required_credits="0", course_ids=[])]
    )
    result = analyze_page_progress(snapshot)

    assert result["modules"][0]["calculation"]["satisfied"] is None
    assert result["status"] == "needs_verification"
    assert result["can_decide_complete"] is False
    assert any(
        item["code"] == "zero_requirement_no_evidence"
        for item in result["pending_verification"]
    )
    assert any(
        item["code"] == "clarify_module_requirement" for item in result["suggestions"]
    )


def test_any_module_can_be_satisfied_by_completed_child():
    snapshot = _snapshot(
        courses=[_course("c1", credits="3.0")],
        modules=[
            _module("root", requirement="any", required_credits=None),
            _module(
                "a",
                requirement="credits",
                required_credits="3.0",
                course_ids=["c1"],
                parent_id="root",
            ),
            _module(
                "b",
                requirement="credits",
                required_credits="9.0",
                course_ids=[],
                parent_id="root",
            ),
        ],
    )
    result = analyze_page_progress(snapshot)
    root = _find_module(result, "root")

    assert root["calculation"]["satisfied"] is True
    assert result["can_decide_complete"] is True
    assert result["status"] == "complete_under_supported_rules"


def test_structural_all_parent_completes_without_direct_courses():
    snapshot = _snapshot(courses=[_course("c1", credits="3.0")], modules=[
        _module("root", requirement="all", required_credits=None),
        _module("child", parent_id="root", requirement="credits", required_credits="3.0", course_ids=["c1"]),
    ])
    assert analyze_page_progress(snapshot)["status"] == "complete_under_supported_rules"


def test_all_combination_does_not_ignore_credit_minimum():
    snapshot = _snapshot(courses=[_course("c1", credits="3.0")], modules=[
        _module("root", requirement="all", required_credits="5.0", course_ids=["c1"]),
    ])
    result = analyze_page_progress(snapshot)
    assert result["status"] == "incomplete"
    assert _find_module(result, "root")["calculation"]["satisfied"] is False


def test_all_module_requires_every_child():
    snapshot = _snapshot(
        courses=[_course("c1", credits="3.0")],
        modules=[
            _module(
                "root",
                requirement="all",
                required_credits=None,
                course_ids=["c1"],
            ),
            _module(
                "child",
                requirement="credits",
                required_credits="3.0",
                course_ids=[],
                parent_id="root",
            ),
        ],
    )
    result = analyze_page_progress(snapshot)
    root = _find_module(result, "root")

    assert root["calculation"]["satisfied"] is False
    assert result["status"] == "incomplete"
    assert result["can_decide_complete"] is False


# ---------------------------------------------------------------------------
# 未知认定 / 待核实
# ---------------------------------------------------------------------------


def test_unknown_and_pending_recognition_are_never_counted():
    snapshot = _snapshot(
        courses=[
            _course("c1", credits="3.0", state="pending_recognition"),
            _course("c2", credits="3.0", state="unknown"),
        ],
        modules=[_module("m1", required_credits="3.0", course_ids=["c1"])],
    )
    result = analyze_page_progress(snapshot)

    assert Decimal(result["modules"][0]["calculation"]["earned_credits"]) == Decimal("0")
    assert result["modules"][0]["calculation"]["satisfied"] is False
    assert result["can_decide_complete"] is False
    codes = {item["code"] for item in result["pending_verification"]}
    assert "needs_recognition" in codes
    assert result["courses"]
    assert all(item["counted"] is False for item in result["courses"])
    assert all(
        item["verification_required"] is True for item in result["courses"]
    )
    assert {item["course_id"] for item in result["pending_recognition_courses"]} == {
        "c1",
        "c2",
    }


def test_credits_requirement_without_value_is_pending():
    snapshot = _snapshot(
        courses=[_course("c1")],
        modules=[
            _module("m1", requirement="credits", required_credits=None, course_ids=["c1"])
        ],
    )
    result = analyze_page_progress(snapshot)

    assert result["modules"][0]["calculation"]["satisfied"] is None
    assert any(
        item["code"] == "required_credits_unknown"
        for item in result["pending_verification"]
    )
    assert result["can_decide_complete"] is False


def test_unrecognized_course_state_and_unsupported_policy_are_pending():
    snapshot = _snapshot(
        courses=[
            _course("c1", state="exempted"),
            _course("c2", state="passed"),
            _course("c2", state="passed"),
        ],
        repeat_policy="best_grade",
    )
    result = analyze_page_progress(snapshot)
    codes = {item["code"] for item in result["pending_verification"]}

    assert "unrecognized_course_state" in codes
    assert "unsupported_repeat_policy" in codes
    entry = next(item for item in result["courses"] if item["course_id"] == "c1")
    assert entry["state"] == "unknown"
    assert entry["counted"] is False
    assert result["can_decide_complete"] is False


# ---------------------------------------------------------------------------
# 重复记录：绝不按输入顺序选择
# ---------------------------------------------------------------------------


def test_duplicate_records_without_policy_stay_unresolved():
    first = _course("c1", credits="3.0")
    second = _course("c1", credits="3.0")
    for courses in ([first, second], [second, first]):
        snapshot = _snapshot(
            courses=courses,
            modules=[_module("m1", required_credits="3.0", course_ids=["c1"])],
        )
        result = analyze_page_progress(snapshot)
        entry = result["courses"][0]

        assert entry["counted"] is False
        assert entry["verification_required"] is True
        assert entry["record_count"] == 2
        assert any(
            item["code"] == "repeat_policy_missing"
            for item in result["pending_verification"]
        )
        assert Decimal(result["modules"][0]["calculation"]["earned_credits"]) == Decimal("0")
        assert result["can_decide_complete"] is False


def test_duplicate_credits_conflict_never_uses_input_order():
    low = _course("c1", credits="1.0")
    high = _course("c1", credits="3.0")
    for courses in ([low, high], [high, low]):
        snapshot = _snapshot(
            courses=courses,
            repeat_policy="once_per_course",
            modules=[_module("m1", required_credits="3.0", course_ids=["c1"])],
        )
        result = analyze_page_progress(snapshot)
        entry = result["courses"][0]

        assert entry["credits"] is None
        assert entry["credit_candidates"] == ["1.0", "3.0"]
        assert entry["counted"] is False
        assert any(
            item["code"] == "repeat_credits_conflict"
            for item in result["pending_verification"]
        )
        assert Decimal(result["modules"][0]["calculation"]["earned_credits"]) == Decimal("0")
        assert result["can_decide_complete"] is False


def test_duplicate_same_credits_counted_once_under_explicit_policy():
    first = _course("c1", credits="3.0")
    second = _course("c1", credits="3.00")
    snapshot = _snapshot(
        courses=[first, second],
        repeat_policy="once_per_course",
        modules=[_module("m1", required_credits="3.0", course_ids=["c1"])],
    )
    result = analyze_page_progress(snapshot)
    entry = result["courses"][0]

    assert entry["counted"] is True
    assert entry["record_count"] == 2
    assert Decimal(result["modules"][0]["calculation"]["earned_credits"]) == Decimal("3.0")
    assert result["can_decide_complete"] is True


# ---------------------------------------------------------------------------
# 分配：父子不双计、无规则待核实
# ---------------------------------------------------------------------------


def test_passed_course_without_module_rule_is_pending():
    snapshot = _snapshot(
        courses=[_course("c1"), _course("ghost")],
        modules=[_module("m1", required_credits="3.0", course_ids=["c1"])],
    )
    result = analyze_page_progress(snapshot)

    assert "ghost" in result["unallocated_courses"]
    assert any(
        item["code"] == "no_allocation_rule" and item["course_id"] == "ghost"
        for item in result["pending_verification"]
    )
    assert result["can_decide_complete"] is False
    assert Decimal(result["independent_calculation"]["counted_credits"]) == Decimal("3.0")


def test_same_depth_allocation_tie_is_pending():
    snapshot = _snapshot(
        courses=[_course("c1", credits="2.0")],
        modules=[
            _module("root", requirement="all", required_credits=None),
            _module(
                "m1",
                requirement="credits",
                required_credits="2.0",
                course_ids=["c1"],
                parent_id="root",
            ),
            _module(
                "m2",
                requirement="credits",
                required_credits="2.0",
                course_ids=["c1"],
                parent_id="root",
            ),
        ],
    )
    result = analyze_page_progress(snapshot)

    assert "c1" in result["unallocated_courses"]
    assert any(
        item["code"] == "allocation_rule_missing"
        for item in result["pending_verification"]
    )
    assert Decimal(result["independent_calculation"]["counted_credits"]) == Decimal("0")
    assert result["can_decide_complete"] is False


# ---------------------------------------------------------------------------
# 页面显示与独立核算分离
# ---------------------------------------------------------------------------


def test_page_display_gap_is_separated_from_calculation():
    snapshot = _snapshot(
        courses=[_course("c1", credits="3.0")],
        modules=[
            _module(
                "m1",
                requirement="credits",
                required_credits="6.0",
                course_ids=["c1"],
                reported_earned_credits="6.0",
                reported_remaining_credits="0.0",
                reported_satisfied=True,
            )
        ],
    )
    result = analyze_page_progress(snapshot)
    module = result["modules"][0]

    assert module["page"]["earned_credits"] == "6.0"
    assert module["page"]["satisfied"] is True
    assert Decimal(module["calculation"]["subtree_earned_credits"]) == Decimal("3.0")
    assert module["calculation"]["satisfied"] is False
    assert {
        item["code"] for item in module["discrepancies"]
    } == {
        "page_earned_credits_mismatch",
        "page_remaining_credits_mismatch",
        "page_satisfied_mismatch",
    }
    assert module["page_vs_calculation"]["agrees"] is False
    assert result["page_display"]["root_satisfied"] is True
    assert result["independent_calculation"]["root_satisfied"] is False
    assert any(
        item["code"] == "verify_page_display" for item in result["suggestions"]
    )


# ---------------------------------------------------------------------------
# 缺页 / 版本未知：不给整体完成判断
# ---------------------------------------------------------------------------


def test_missing_pages_and_unknown_version_block_complete_judgement():
    snapshot = _snapshot(
        plan_version=None,
        source_coverage="partial",
        missing_pages=["p2"],
        courses=[_course("c1")],
        modules=[_module("m1", required_credits="3.0", course_ids=["c1"])],
    )
    result = analyze_page_progress(snapshot)

    assert result["modules"][0]["calculation"]["satisfied"] is True
    assert result["can_decide_complete"] is False
    assert result["status"] == "needs_verification"
    assert result["plan_version"] is None
    assert result["plan_version_known"] is False
    assert result["source_coverage"] == "partial"
    assert result["missing_pages"] == ["p2"]
    codes = {item["code"] for item in result["pending_verification"]}
    assert {"source_coverage_incomplete", "plan_version_unknown"} <= codes


def test_unknown_coverage_token_is_normalized_to_unknown():
    snapshot = _snapshot(source_coverage="mystery", modules=[_module("m1")])
    result = analyze_page_progress(snapshot)

    assert result["source_coverage"] == "unknown"
    assert result["can_decide_complete"] is False
    assert any(
        item["code"] == "source_coverage_incomplete"
        for item in result["pending_verification"]
    )


# ---------------------------------------------------------------------------
# 严格校验
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_credits", ["-1.0", "NaN", "inf", "abc", "1,5", ""])
def test_invalid_credits_are_rejected(bad_credits):
    snapshot = _snapshot(courses=[_course("c1", credits=bad_credits)], modules=[])
    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(snapshot)
    assert excinfo.value.code == "invalid_credits"


def test_non_finite_float_credits_are_rejected():
    snapshot = _snapshot(courses=[_course("c1", credits=float("inf"))], modules=[])
    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(snapshot)
    assert excinfo.value.code == "invalid_credits"


def test_invalid_structures_are_rejected():
    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress([])
    assert excinfo.value.code == "invalid_snapshot"

    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(_snapshot(modules={"m1": {}}))
    assert excinfo.value.code == "invalid_structure"

    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(_snapshot(courses="c1"))
    assert excinfo.value.code == "invalid_structure"

    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(_snapshot(modules=[{"name": "缺少 id"}]))
    assert excinfo.value.code == "invalid_module_id"

    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(_snapshot(courses=[{"credits": "3.0", "state": "passed"}]))
    assert excinfo.value.code == "invalid_course_id"


def test_invalid_module_tree_is_rejected():
    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(_snapshot(modules=[_module("a"), _module("a")]))
    assert excinfo.value.code == "duplicate_module_id"

    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(_snapshot(modules=[_module("a", parent_id="ghost")]))
    assert excinfo.value.code == "unknown_parent"

    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(_snapshot(modules=[_module("a", parent_id="b"), _module("b", parent_id="a")]))
    assert excinfo.value.code == "module_tree_cycle"

    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(_snapshot(modules=[_module("a", parent_id="a")]))
    assert excinfo.value.code == "module_tree_cycle"

    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(_snapshot(modules=[_module("a"), _module("b")]))
    assert excinfo.value.code == "invalid_module_tree"


def test_invalid_reported_fields_are_rejected():
    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(
            _snapshot(modules=[_module("m1", reported_satisfied="yes")])
        )
    assert excinfo.value.code == "invalid_reported_satisfied"

    with pytest.raises(PageProgressValidationError) as excinfo:
        analyze_page_progress(_snapshot(plan_version=123, modules=[_module("m1")]))
    assert excinfo.value.code == "invalid_plan_version"


# ---------------------------------------------------------------------------
# 证据保留 / 输入不变 / 建议边界
# ---------------------------------------------------------------------------


def test_evidence_and_alias_fields_are_preserved():
    snapshot = _snapshot(
        evidence={"captured_at": "anon"},
        coverage_evidence={"pages": ["p1"]},
        courses=[
            {
                "id": "c1",
                "code": "A1",
                "name": "匿名课程",
                "credits": "3.0",
                "state": "passed",
                "evidence": {"row": 3},
            }
        ],
        modules=[
            {
                "id": "m1",
                "name": "匿名模块",
                "parent_id": None,
                "requirement": "credits",
                "min_credits": "3.0",
                "course_ids": ["c1"],
                "evidence": {"page": "p1"},
            }
        ],
    )
    result = analyze_page_progress(snapshot)
    module = result["modules"][0]
    course = result["courses"][0]

    assert module["id"] == module["module_id"] == "m1"
    assert module["evidence"] == {"page": "p1"}
    assert course["id"] == course["course_id"] == "c1"
    assert course["evidence"] == {"row": 3}
    assert result["evidence"] == {"captured_at": "anon"}
    assert result["coverage_evidence"] == {"pages": ["p1"]}
    assert result["passed_courses"][0]["evidence"] == {"row": 3}


def test_input_snapshot_is_not_mutated():
    snapshot = _snapshot(
        courses=[_course("c1", evidence={"row": 1})],
        modules=[_module("m1", course_ids=["c1"], evidence={"page": "p1"})],
        evidence={"k": [1, 2]},
    )
    before = copy.deepcopy(snapshot)
    analyze_page_progress(snapshot)
    assert snapshot == before


def test_module_order_does_not_change_result():
    modules = [
        _module("root", requirement="all", required_credits=None, course_ids=["c1"]),
        _module(
            "child",
            requirement="credits",
            required_credits="3.0",
            course_ids=["c1"],
            parent_id="root",
        ),
    ]
    courses = [_course("c1", credits="3.0")]
    forward = analyze_page_progress(_snapshot(modules=modules, courses=courses))
    backward = analyze_page_progress(
        _snapshot(modules=list(reversed(modules)), courses=courses)
    )
    assert forward["modules"] == backward["modules"]
    assert forward["status"] == backward["status"]
    assert forward["pending_verification"] == backward["pending_verification"]


def test_suggestions_never_recommend_semester_or_offering():
    snapshot = _snapshot(
        courses=[_course("c1", state="failed")],
        modules=[
            _module(
                "m1",
                requirement="required_courses",
                required_credits="3.0",
                required_course_ids=["c1"],
            )
        ],
    )
    result = analyze_page_progress(snapshot)

    assert result["suggestions"]
    for item in result["suggestions"]:
        assert set(item) <= {"code", "message", "module_id", "course_ids", "evidence"}
    for key in _iter_keys(result):
        assert key.lower() not in _FORBIDDEN_KEYS
    for text in _iter_strings(result):
        for token in _FORBIDDEN_MESSAGE_TOKENS:
            assert token not in text
    blob = json.dumps(result, ensure_ascii=False, default=str).lower()
    for token in ("semester", "offering", "schedule"):
        assert token not in blob

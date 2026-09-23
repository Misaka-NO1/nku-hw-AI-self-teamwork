"""C 的固定测试：DEGREE-01 ~ DEGREE-06 及夹具结构校验。

夹具来自仓库根目录 fixtures/，与前端/扩展共用同一组 JSON；
结果结构按 contracts/api.schema.json 的 DegreeAuditResult 校验。
"""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from app.domains.degree import audit_degree_progress

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "fixtures"
API_SCHEMA = json.loads(
    (ROOT / "contracts" / "api.schema.json").read_text(encoding="utf-8")
)
CORE_SCHEMA = json.loads(
    (ROOT / "contracts" / "core.schema.json").read_text(encoding="utf-8")
)


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _validator(defs: dict, ref: str) -> Draft202012Validator:
    schema = {
        "$schema": CORE_SCHEMA["$schema"],
        "$ref": ref,
        "$defs": defs,
    }
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.fixture()
def plan() -> dict:
    return _load("degree-plan.demo.json")


@pytest.fixture()
def records() -> list[dict]:
    return _load("transcript.demo.json")["records"]


def _module(result: dict, module_id: str) -> dict:
    return next(m for m in result["modules"] if m["module_id"] == module_id)


def test_fixtures_validate_against_core_schema() -> None:
    plan = _load("degree-plan.demo.json")
    transcript = _load("transcript.demo.json")
    _validator(CORE_SCHEMA["$defs"], "#/$defs/DegreePlan").validate(plan)
    _validator(CORE_SCHEMA["$defs"], "#/$defs/Transcript").validate(transcript)


def test_result_matches_api_schema(plan: dict, records: list[dict]) -> None:
    result = audit_degree_progress(plan, records)
    _validator(API_SCHEMA["$defs"], "#/$defs/DegreeAuditResult").validate(result)


def test_degree_01_duplicate_passed_counted_once(plan: dict, records: list[dict]) -> None:
    result = audit_degree_progress(plan, records)
    core = _module(result, "core")
    assert core["earned_credits"] == "3.0"
    assert core["counted_attempts"] == ["a1"]
    assert "a2" in core["excluded_attempts"]


def test_degree_02_failed_and_in_progress_not_counted(
    plan: dict, records: list[dict]
) -> None:
    result = audit_degree_progress(plan, records)
    core = _module(result, "core")
    assert "a3" in core["excluded_attempts"]  # failed
    assert "a4" in core["excluded_attempts"]  # in_progress
    assert core["earned_credits"] == "3.0"


def test_degree_03_credits_enough_but_missing_required_still_gap() -> None:
    plan = {
        "schema_version": "1.0.0",
        "dataset_kind": "demo",
        "plan_id": "demo-plan-gap",
        "program": "虚构专业",
        "cohort": "demo-cohort",
        "version": "demo-v1",
        "status": "demo",
        "source_ref": "自创测试规则",
        "repeat_policy": "once_per_course",
        "modules": [
            {
                "module_id": "core",
                "required_course_ids": ["demo-CS102"],
                "eligible_course_ids": ["demo-CS101", "demo-CS102"],
                "min_credits": "3.0",
                "allocation_priority": 1,
            }
        ],
    }
    records = [
        {
            "attempt_id": "b1",
            "course_id": "demo-CS101",
            "credits": "3.0",
            "result": "passed",
        }
    ]
    result = audit_degree_progress(plan, records)
    core = _module(result, "core")
    assert core["earned_credits"] == "3.0"
    assert core["remaining_credits"] == "0.0"
    assert core["missing_required_courses"] == ["demo-CS102"]
    assert result["status"] == "incomplete"


def test_degree_04_ambiguous_module_allocation_returns_needs_policy() -> None:
    plan = {
        "schema_version": "1.0.0",
        "dataset_kind": "demo",
        "plan_id": "demo-plan-ambiguous",
        "program": "虚构专业",
        "cohort": "demo-cohort",
        "version": "demo-v1",
        "status": "demo",
        "source_ref": "自创测试规则",
        "repeat_policy": "once_per_course",
        "modules": [
            {
                "module_id": "m1",
                "required_course_ids": [],
                "eligible_course_ids": ["demo-EL201"],
                "min_credits": "2.0",
                "allocation_priority": 1,
            },
            {
                "module_id": "m2",
                "required_course_ids": [],
                "eligible_course_ids": ["demo-EL201"],
                "min_credits": "2.0",
                "allocation_priority": 1,
            },
        ],
    }
    records = [
        {
            "attempt_id": "c1",
            "course_id": "demo-EL201",
            "credits": "2.0",
            "result": "passed",
        }
    ]
    result = audit_degree_progress(plan, records)
    assert result["status"] == "needs_policy"
    assert result["unallocated_courses"] == ["demo-EL201"]
    assert any("allocation_rule_missing" in r for r in result["unresolved_rules"])
    total_counted = sum(len(m["counted_attempts"]) for m in result["modules"])
    assert total_counted == 0  # 不重复计


def test_degree_05a_unverified_plan_refuses_hard_calculation(
    plan: dict, records: list[dict]
) -> None:
    broken = deepcopy(plan)
    broken["status"] = "needs_verification"
    result = audit_degree_progress(broken, records)
    assert result["status"] == "needs_policy"
    assert any(
        "plan_source_needs_verification" in r for r in result["unresolved_rules"]
    )


def test_degree_05b_unknown_substitution_kept_unresolved(
    plan: dict, records: list[dict]
) -> None:
    extra = records + [
        {
            "attempt_id": "a9",
            "course_id": "demo-XX999",
            "credits": "2.0",
            "result": "passed",
        }
    ]
    result = audit_degree_progress(plan, extra)
    assert "demo-XX999" in result["unallocated_courses"]
    assert result["status"] == "needs_policy"
    assert result["status"] != "complete_under_supported_rules"


def test_repeat_policy_missing_with_duplicates_suspends_course(
    plan: dict, records: list[dict]
) -> None:
    broken = deepcopy(plan)
    broken["repeat_policy"] = None
    result = audit_degree_progress(broken, records)
    assert result["status"] == "needs_policy"
    core = _module(result, "core")
    assert core["counted_attempts"] == []  # CS101 重复且无政策，停止该课程核算
    assert any("repeat_policy_missing" in r for r in result["unresolved_rules"])


def test_repeat_credits_conflict_needs_policy_regardless_of_order() -> None:
    """PR #3 审核意见：学分不一致的重复通过记录不得按输入顺序决定结论。"""
    plan = {
        "schema_version": "1.0.0",
        "dataset_kind": "demo",
        "plan_id": "demo-plan-conflict",
        "program": "虚构专业",
        "cohort": "demo-cohort",
        "version": "demo-v1",
        "status": "demo",
        "source_ref": "自创测试规则",
        "repeat_policy": "once_per_course",
        "modules": [
            {
                "module_id": "core",
                "required_course_ids": [],
                "eligible_course_ids": ["demo-CS101"],
                "min_credits": "3.0",
                "allocation_priority": 1,
            }
        ],
    }
    low = {"attempt_id": "r1", "course_id": "demo-CS101", "credits": "1.0", "result": "passed"}
    high = {"attempt_id": "r2", "course_id": "demo-CS101", "credits": "3.0", "result": "passed"}

    for records in ([low, high], [high, low]):
        result = audit_degree_progress(plan, records)
        assert result["status"] == "needs_policy"
        assert any(
            "repeat_credits_conflict" in r for r in result["unresolved_rules"]
        )
        core = _module(result, "core")
        assert core["counted_attempts"] == []
        assert core["earned_credits"] == "0"


def test_repeat_same_credits_counts_once_order_independent() -> None:
    """同学分的重复通过记录按 once_per_course 只计一次，与顺序无关。"""
    plan = {
        "schema_version": "1.0.0",
        "dataset_kind": "demo",
        "plan_id": "demo-plan-same",
        "program": "虚构专业",
        "cohort": "demo-cohort",
        "version": "demo-v1",
        "status": "demo",
        "source_ref": "自创测试规则",
        "repeat_policy": "once_per_course",
        "modules": [
            {
                "module_id": "core",
                "required_course_ids": [],
                "eligible_course_ids": ["demo-CS101"],
                "min_credits": "3.0",
                "allocation_priority": 1,
            }
        ],
    }
    first = {"attempt_id": "s1", "course_id": "demo-CS101", "credits": "3.0", "result": "passed"}
    second = {"attempt_id": "s2", "course_id": "demo-CS101", "credits": "3.0", "result": "passed"}

    results = [audit_degree_progress(plan, rs) for rs in ([first, second], [second, first])]
    for result in results:
        assert result["status"] == "complete_under_supported_rules"
        core = _module(result, "core")
        assert core["earned_credits"] == "3.0"
        assert len(core["counted_attempts"]) == 1
        assert len(core["excluded_attempts"]) == 1


def test_degree_06_demo_fixture_matches_expected_results(
    plan: dict, records: list[dict]
) -> None:
    expected = _load("expected-results.demo.json")["degree"]
    result = audit_degree_progress(plan, records)
    core = _module(result, "core")
    elective = _module(result, "elective")
    assert core["earned_credits"] == expected["core_earned"]
    assert core["remaining_credits"] == expected["core_remaining"]
    assert elective["earned_credits"] == expected["elective_earned"]
    assert elective["remaining_credits"] == expected["elective_remaining"]
    coverage = result["data_coverage"]
    assert coverage["total_earned_credits"] == expected["total_earned"]
    assert coverage["total_remaining_credits"] == expected["total_remaining"]
    assert core["missing_required_courses"] == expected["missing_required_courses"]
    assert coverage["not_graduation_decision"] is True
    assert result["status"] == "incomplete"

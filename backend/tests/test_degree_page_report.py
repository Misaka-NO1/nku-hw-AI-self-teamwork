from app.domains.degree.page_report import analyze_page_report


def observation(rows):
    return {"kind": "degree-table-observation", "source": {"url": "https://eamis.nankai.edu.cn/eams/myPlanCompl.action",
        "captured_at": "2026-01-01T00:00:00Z", "coverage": "unknown", "adapter_verified": False},
        "headers": ["序号", "课程序号", "课程名称", "要求学分", "实修学分", "成绩", "是否通过", "备注"],
        "rows": [{"cells": cells, "locator": f"table-row:{index+2}"} for index, cells in enumerate(rows)]}


def test_optional_branch_gap_is_retained_without_mandatory_priority():
    result = analyze_page_report(observation([
        ["一 专业选修课（所有子项至少一项满足要求）", "6", "0", "", "缺6学分", ""],
        ["(一) 虚构可选组，非必须选择", "2", "0", "", "缺2学分 缺1门", ""],
        ["1 虚构可选子组", "2", "0", "", "缺2学分", ""],
        ["1", "ANON1", "虚构候选课程", "2", "0", "--", "否", ""],
    ]))
    assert result["modules"][1]["gap_credits"] == "2"
    assert result["modules"][2]["gap_credits"] == "2"
    for summary in result["module_summaries"][1:]:
        assert summary["optional_branch"] is True
        assert "不代表必须补修本组" in summary["next_step"]
        assert summary["required_category_pending_courses"] == []
    assert len(result["priority_suggestions"]) == 1
    assert result["module_summaries"][0]["optional_branch"] is False
    assert result["priority_suggestions"][0]["module_name"].startswith("专业选修课")
    assert result["can_decide_complete"] is False


def test_explicit_required_course_in_optional_group_still_needs_verification():
    result = analyze_page_report(observation([
        ["1 虚构可选组，非必须选择", "2", "0", "", "缺2学分", ""],
        ["1", "ANON1", "虚构明确要求课程", "2", "0", "--", "否", "必修"],
    ]))
    assert result["module_summaries"][0]["missing_required_courses"]
    assert result["priority_suggestions"][0]["priority"] == 1
    assert "核对必修" in result["priority_suggestions"][0]["message"]


def test_required_category_pending_courses_have_evidence_and_exclude_choice_branch():
    result = analyze_page_report(observation([
        ["一 虚构主章（所有子项满足）", "6", "0", "", "缺6学分", ""],
        ["二 专业必修课", "4", "0", "", "缺4学分", ""],
        ["1", "ANON1", "虚构必修在读课", "2", "0", "--", "是", "在读"],
        ["2", "ANON2", "虚构未完成课", "2", "0", "--", "否", ""],
        ["1 虚构选修模块（多选一）", "2", "0", "", "缺2学分", ""],
        ["1", "ANON3", "虚构候选课", "2", "0", "--", "否", ""],
    ]))
    required = result["module_summaries"][1]
    assert len(required["required_category_pending_courses"]) == 2
    assert required["required_category_pending_courses"][0]["category_evidence"]
    assert "核对补修或替代要求" in required["next_step"]
    assert result["module_summaries"][2]["required_category_pending_courses"] == []
    assert result["can_decide_complete"] is False


def test_report_prioritizes_required_course_without_counting_in_progress_as_passed():
    result = analyze_page_report(observation([
        ["1 虚构模块（所有子项满足）", "4", "4", "", "是", ""],
        ["1", "ANON1", "虚构通过课", "2", "2", "88", "是", "必修"],
        ["2", "ANON2", "虚构在读课", "2", "2", "--", "是", "在读 必修"],
    ]))
    summary = result["module_summaries"][0]
    assert summary["observed_passed_credits"] == "2"
    assert summary["observed_in_progress_credits"] == "2"
    assert summary["missing_required_courses"][0]["name"] == "虚构在读课"
    assert summary["discrepancies"]
    assert result["priority_suggestions"][0]["priority"] == 1
    assert "虚构在读课" in result["priority_suggestions"][0]["message"]
    assert result["can_decide_complete"] is False


def test_duplicate_course_requires_verification_before_credit_statistics():
    result = analyze_page_report(observation([
        ["1 虚构模块（所有子项满足）", "4", "4", "", "是", ""],
        ["1", "ANON1", "虚构课程", "2", "2", "88", "是", "非必修"],
        ["2", "ANON1", "虚构课程", "2", "2", "88", "是", "非必修"],
    ]))
    summary = result["module_summaries"][0]
    assert summary["observed_passed_credits"] is None
    assert summary["missing_required_courses"] == []
    assert result["priority_suggestions"][0]["priority"] == 0


def test_page_module_gaps_are_not_summed_and_unknown_hierarchy_is_retained():
    result = analyze_page_report(observation([
        ["(二)虚构另一模块（所有子项满足）", "4", "2", "", "缺2学分", ""],
        ["（一）虚构子模块", "4", "2", "", "缺2学分", ""],
    ]))
    assert result["page_progress"] is None
    assert len(result["module_summaries"]) == 2
    assert "total_remaining" not in result
    assert all(item["evidence"]["locator"] for item in result["priority_suggestions"])


def test_explicit_parent_reports_subtree_credits_and_pending_rules():
    result = analyze_page_report(observation([
        ["1 虚构总模块（所有子项满足）", "4", "2", "", "缺2学分", ""],
        ["1.1 虚构子模块（所有子项满足）", "4", "2", "", "缺2学分", ""],
        ["1", "ANON1", "虚构通过课", "2", "2", "88", "是", "必修"],
        ["2", "ANON2", "虚构在读课", "2", "0", "--", "是", "在读 必修"],
    ]))
    parent = result["module_summaries"][0]
    assert parent["observed_passed_credits"] == "2"
    assert parent["observed_in_progress_credits"] == "2"
    assert "子模块" in parent["statistics_scope"]
    assert result["pending_verification"]
    assert any(item["code"] == "plan_version_unknown" for item in result["pending_verification"])
    assert all("module-1" not in item["detail"] for item in result["pending_verification"])
    assert all("raw_detail" in item for item in result["pending_verification"])

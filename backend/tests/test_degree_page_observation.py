"""培养计划原表格观察值解析的独立测试。

全部数据为匿名虚构值：不读取 fixtures、不联网、不依赖 audit 演示契约。
测试锚定 ``analyze_page_observation`` 的保守边界：

* 独立 ``degree-table-observation`` 契约校验（精确来源、时间、覆盖、
  ``adapter_verified=false``、已知表头、未知字段拒绝、身份文本拒绝、上限）；
* 原始 6 格模块行与 8 格课程行、7 列表头变体；
* 明确的点分编号（1 / 1.1 / 1.2）才建立父子；中文编号层级报告未知；
* ``all`` / ``any`` / ``unknown`` 模块规则与「缺口 / 要求学分」分离；
* 在读优先且不计为 ``passed``、``--``+「是」为 ``pending_recognition``；
* 模块总值不当作独立已通过；
* 无法确定层级时**不构造快照、不补演示数据**，``can_decide_complete`` 恒为
  ``False``。
"""

from __future__ import annotations

import copy

import pytest

from app.domains.degree.page_observation import (
    CANONICAL_URL,
    MAX_CELL_CHARS,
    MAX_CELLS_PER_ROW,
    MAX_OBSERVATION_BYTES,
    MAX_ROWS,
    OBSERVATION_VERSION,
    PageObservationValidationError,
    analyze_page_observation,
)

HEADERS = [
    "序号",
    "课程序号",
    "课程名称",
    "要求学分",
    "实修学分",
    "成绩",
    "是否通过",
    "备注",
]
HEADERS_WITHOUT_SEQUENCE = HEADERS[1:]


# ---------------------------------------------------------------------------
# 构造器（匿名虚构）
# ---------------------------------------------------------------------------


def _source(**overrides):
    base = {
        "url": CANONICAL_URL,
        "captured_at": "2024-01-01T00:00:00Z",
        "coverage": "partial",
        "adapter_verified": False,
    }
    base.update(overrides)
    return base


def _observation(rows, *, headers=None, source=None, **overrides):
    base = {
        "kind": "degree-table-observation",
        "source": _source() if source is None else source,
        "headers": list(HEADERS if headers is None else headers),
        "rows": list(rows),
    }
    base.update(overrides)
    return base


def _course_row(locator, seq, code, name, required="", earned="", grade="", passed="", remark=""):
    return {
        "cells": [seq, code, name, required, earned, grade, passed, remark],
        "locator": locator,
    }


def _module_row(locator, label, required="", earned="", grade="", gap="", remark=""):
    return {"cells": [label, required, earned, grade, gap, remark], "locator": locator}


def _pending_codes(result):
    return {item["code"] for item in result["pending_verification"]}


def test_chapter_scoped_repeated_numbers_build_unique_modules_and_preserve_unknown_root():
    result = analyze_page_observation(_observation([
        _module_row("table-row:2", "一\u00a0虚构主章（所有子项满足）", "4", "2", gap="缺2学分"),
        _module_row("table-row:3", "(一)\u00a0虚构子章甲", "2", "2", gap="是"),
        _module_row("table-row:4", "1\u00a0虚构局部模块甲", "2", "2", gap="是"),
        _course_row("table-row:5", "1", "ANON1", "虚构通过课", "2", "2", "88", "是"),
        _module_row("table-row:6", "(二)\u00a0虚构子章乙", "2", "0", gap="缺2学分"),
        _module_row("table-row:7", "1\u00a0虚构局部模块乙", "2", "0", gap="缺2学分"),
        _course_row("table-row:8", "1", "ANON2", "虚构在读课", "2", "0", "--", "是", "在读"),
        _module_row("table-row:9", "二\u00a0另一虚构主章（必须通过的子组数量4）", "0", "0", gap="是"),
    ]))
    assert result["snapshot_status"] == "built"
    modules = result["snapshot"]["modules"]
    assert len({module["module_id"] for module in modules}) == len(modules)
    assert modules[-1]["requirement"] == "unknown"
    assert modules[-1]["evidence"]["row_role"] == "synthetic_group"
    assert result["modules"][2]["parent_locator"] == "table-row:3"
    assert result["modules"][4]["parent_locator"] == "table-row:6"
    assert result["modules"][5]["requirement"] == "unknown"
    assert result["can_decide_complete"] is False


def test_observed_chinese_major_and_satisfied_child_are_retained_without_guessed_rules():
    result = analyze_page_observation(_observation([
        _module_row("table-row:2", "一\u00a0虚构必修主章（所有子项满足）", "4", "4", gap="是"),
        _module_row("table-row:3", "(一)\u00a0虚构子章", "4", "4", gap="是"),
        _module_row("table-row:4", "1\u00a0虚构子模块", "0", "0", gap="是"),
    ]))
    assert len(result["modules"]) == 3
    assert result["modules"][0]["name"].startswith("虚构必修主章")
    assert result["modules"][1]["requirement"] == "unknown"
    assert result["can_decide_complete"] is False


def test_unclassified_section_does_not_assign_courses_to_previous_module():
    result = analyze_page_observation(_observation([
        _module_row("table-row:2", "1 虚构模块甲（所有子项满足）", "3", "0", gap="缺3学分"),
        _module_row("table-row:3", "结构未知的另一模块", "3", "0"),
        _course_row("table-row:4", "1", "ANON1", "虚构课程", "3", "3", "88", "是"),
    ]))
    assert result["courses"][0]["module_locator"] is None
    assert result["snapshot"]["modules"][0]["course_ids"] == []


def test_unrecognized_grade_is_pending_even_with_affirmative_flag():
    result = analyze_page_observation(_observation([
        _course_row("table-row:2", "1", "ANON1", "虚构课程", "3", "3", "暂缓认定", "是"),
    ]))
    assert result["courses"][0]["state"] == "pending_recognition"


# ---------------------------------------------------------------------------
# 契约：正常解析
# ---------------------------------------------------------------------------


def test_exact_source_contract_is_accepted_and_echoed():
    result = analyze_page_observation(
        _observation([_course_row("table-row:2", "1", "A1", "匿名课程甲", "3.0", "3.0", "88", "是")])
    )
    assert result["observation_version"] == OBSERVATION_VERSION
    assert result["kind"] == "degree-table-observation"
    assert result["source"]["url"] == CANONICAL_URL
    assert result["source"]["coverage"] == "partial"
    assert result["source"]["adapter_verified"] is False
    assert result["adapter_verified"] is False
    assert result["not_graduation_decision"] is True


def test_unknown_coverage_is_accepted():
    result = analyze_page_observation(
        _observation([], source=_source(coverage="unknown"))
    )
    assert result["source"]["coverage"] == "unknown"


def test_six_cell_module_row_and_eight_cell_course_row_preserve_raw_values():
    rows = [
        _module_row(
            "table-row:2",
            "（一）理想与信念教育类",
            "18",
            "8.5",
            "",
            "缺9.5学分缺4门",
        ),
        _course_row("table-row:3", "1", "A1", "匿名课程甲", "3.0", "3.0", "88", "是"),
    ]
    result = analyze_page_observation(_observation(rows=rows))

    module = result["modules"][0]
    assert module["label"] == "（一）理想与信念教育类"
    assert module["name"] == "理想与信念教育类"
    assert module["required_credits"] == "18"
    assert module["page_earned_credits"] == "8.5"
    assert module["gap_text"] == "缺9.5学分缺4门"
    assert module["gap_credits"] == "9.5"
    assert module["gap_course_count"] == 4
    assert module["raw_cells"] == ["（一）理想与信念教育类", "18", "8.5", "", "缺9.5学分缺4门", ""]
    assert module["evidence"]["locator"] == "table-row:2"

    course = result["courses"][0]
    assert course["raw_cells"] == ["1", "A1", "匿名课程甲", "3.0", "3.0", "88", "是", ""]
    assert course["state"] == "passed"
    assert course["evidence"]["locator"] == "table-row:3"


def test_seven_column_header_variant_is_supported():
    rows = [
        _module_row("table-row:2", "1 通识（所有子项均应满足要求）", "3.0", "", "", ""),
        {"cells": ["A1", "匿名课程甲", "3.0", "3.0", "88", "是", ""], "locator": "table-row:3"},
    ]
    result = analyze_page_observation(
        _observation(rows=rows, headers=HEADERS_WITHOUT_SEQUENCE)
    )
    assert result["modules"][0]["name"] == "通识（所有子项均应满足要求）"
    assert result["modules"][0]["required_credits"] == "3.0"
    assert result["courses"][0]["name"] == "匿名课程甲"
    assert result["courses"][0]["state"] == "passed"


# ---------------------------------------------------------------------------
# 父子层级：只有明确编号才建立
# ---------------------------------------------------------------------------


def test_explicit_nested_numbering_builds_parent_child_tree():
    rows = [
        _module_row("table-row:2", "1 通识教育", "6.0", gap="缺6.0学分缺2门"),
        _course_row("table-row:3", "1", "A1", "匿名课程甲", "3.0", "3.0", "88", "是"),
        _module_row("table-row:4", "1.1 数学", "3.0", gap="缺3.0学分缺1门"),
        _course_row("table-row:5", "2", "A2", "匿名课程乙", "3.0", "3.0", "90", "是"),
        _module_row("table-row:6", "1.2 物理", "3.0", gap="缺3.0学分缺1门"),
    ]
    result = analyze_page_observation(_observation(rows=rows))

    assert result["snapshot_status"] == "built"
    assert result["snapshot"] is not None
    assert result["page_progress"] is not None
    assert "module_hierarchy_unknown" not in _pending_codes(result)

    snapshot_modules = {item["module_id"]: item for item in result["snapshot"]["modules"]}
    assert snapshot_modules["module-1"]["parent_id"] is None
    assert snapshot_modules["module-1.1"]["parent_id"] == "module-1"
    assert snapshot_modules["module-1.2"]["parent_id"] == "module-1"

    progress_modules = {item["module_id"]: item for item in result["page_progress"]["modules"]}
    assert progress_modules["module-1.1"]["parent_id"] == "module-1"
    assert progress_modules["module-1.1"]["depth"] == 1


def test_chinese_numbering_reports_unknown_hierarchy_without_snapshot():
    rows = [
        _module_row("table-row:2", "（一）理想与信念教育类", "18", "8.5", "", "缺9.5学分缺4门"),
        _module_row("table-row:3", "（二）专业教育类（所有子项均应满足要求）", "20", "20", "", ""),
    ]
    result = analyze_page_observation(_observation(rows=rows))

    assert result["snapshot_status"] == "not_built"
    assert result["snapshot"] is None
    assert result["page_progress"] is None
    assert result["can_decide_complete"] is False
    assert len(result["modules"]) == 2
    assert all(module["numerical_id"] is None for module in result["modules"])
    assert "module_hierarchy_unknown" in _pending_codes(result)


def test_multiple_roots_without_common_parent_do_not_build_snapshot():
    rows = [
        _module_row("table-row:2", "10 甲类", "3.0", gap="缺3.0学分缺1门"),
        _module_row("table-row:3", "20 乙类", "3.0", gap="缺3.0学分缺1门"),
    ]
    result = analyze_page_observation(_observation(rows=rows))

    assert result["snapshot_status"] == "not_built"
    assert result["snapshot"] is None
    assert result["page_progress"] is None
    assert "multiple_roots_without_common_parent" in _pending_codes(result)


def test_duplicate_module_number_blocks_snapshot():
    rows = [
        _module_row("table-row:2", "1 甲类", "3.0", gap="缺3.0学分缺1门"),
        _module_row("table-row:3", "1 乙类", "3.0", gap="缺3.0学分缺1门"),
    ]
    result = analyze_page_observation(_observation(rows=rows))

    assert result["snapshot_status"] == "not_built"
    assert "duplicate_module_number" in _pending_codes(result)


# ---------------------------------------------------------------------------
# 形状不决定语义
# ---------------------------------------------------------------------------


def test_leading_span_row_without_number_is_unclassified_not_guessed():
    rows = [_module_row("table-row:2", "理想与信念教育类", "18", "8.5", "", "缺9.5学分缺4门")]
    result = analyze_page_observation(_observation(rows=rows))

    assert result["modules"] == []
    assert result["unclassified_rows"][0]["reason"] == "unclassified_leading_span_row"
    assert result["unclassified_rows"][0]["raw_cells"][0] == "理想与信念教育类"


def test_numbered_module_with_page_credits_is_retained_with_unknown_rule():
    rows = [_module_row("table-row:2", "1 通识教育", "6.0", "", "", "")]
    result = analyze_page_observation(_observation(rows=rows))

    assert result["modules"][0]["required_credits"] == "6.0"
    assert result["modules"][0]["requirement"] == "unknown"
    assert result["can_decide_complete"] is False


def test_unsupported_row_shape_and_empty_row_are_reported():
    rows = [
        {"cells": ["a", "b", "c", "d"], "locator": "table-row:2"},
        {"cells": ["", "", "", "", "", "", "", ""], "locator": "table-row:3"},
    ]
    result = analyze_page_observation(_observation(rows=rows))
    reasons = [row["reason"] for row in result["unclassified_rows"]]
    assert "unsupported_row_shape" in reasons
    assert "empty_row" in reasons


# ---------------------------------------------------------------------------
# 模块规则：all / any / unknown
# ---------------------------------------------------------------------------


def test_module_requirement_rules_all_any_unknown():
    rows = [
        _module_row("table-row:2", "1 通识（所有子项均应满足要求）", "6.0", "", "", ""),
        _module_row("table-row:3", "2 选修（至少一项）", "4.0", "", "", ""),
        _module_row("table-row:4", "3 其他（按说明执行）", "", "", "", "缺2.0学分缺1门"),
    ]
    result = analyze_page_observation(_observation(rows=rows))
    modules = {module["numerical_id"]: module for module in result["modules"]}

    assert modules["1"]["requirement"] == "all"
    assert modules["1"]["requirement_rule_text"] == "所有子项均应满足要求"
    assert modules["2"]["requirement"] == "any"
    assert modules["2"]["requirement_rule_text"] == "至少一项"
    assert modules["3"]["requirement"] == "unknown"
    assert modules["3"]["requirement_rule_text"] is None


def test_all_rule_with_substring_所有子项满足_is_recognized():
    rows = [_module_row("table-row:2", "1 甲（所有子项满足）", "3.0", "", "", "")]
    result = analyze_page_observation(_observation(rows=rows))
    assert result["modules"][0]["requirement"] == "all"


def test_gap_and_required_credits_are_kept_separate():
    rows = [
        _module_row("table-row:2", "1 通识（所有子项均应满足要求）", "18", "8.5", "", "缺9.5学分缺4门")
    ]
    result = analyze_page_observation(_observation(rows=rows))
    module = result["modules"][0]

    assert module["required_credits"] == "18"
    assert module["page_earned_credits"] == "8.5"
    assert module["gap_credits"] == "9.5"
    assert module["gap_course_count"] == 4
    assert module["required_credits"] != module["gap_credits"]
    assert module["reported_satisfied"] is False
    # 页面总值（18/8.5）不应直接给出独立结论。
    assert result["snapshot"]["modules"][0]["reported_earned_credits"] == "8.5"
    assert result["page_progress"]["can_decide_complete"] is False


def test_required_course_marker_is_separate_from_gap():
    rows = [
        _module_row("table-row:2", "1 通识（所有子项均应满足要求）", "6.0", "3.0", "", "缺3.0学分缺1门"),
        _course_row("table-row:3", "1", "A1", "匿名课程甲", "3.0", "3.0", "88", "是", "必修"),
        _course_row("table-row:4", "2", "A2", "匿名课程乙", "3.0", "", "在修", "", "选修"),
    ]
    result = analyze_page_observation(_observation(rows=rows))
    module = result["modules"][0]
    snapshot_module = result["snapshot"]["modules"][0]

    # 页面缺口与「要求学分」是两个字段。
    assert module["required_credits"] == "6.0"
    assert module["gap_credits"] == "3.0"
    assert module["gap_course_count"] == 1
    # 必修标记来自备注文本，与缺口无关。
    assert snapshot_module["course_ids"] == ["A1", "A2"]
    assert snapshot_module["required_course_ids"] == ["A1"]
    assert [item["code"] for item in result["in_progress_courses"]] == ["A2"]


# ---------------------------------------------------------------------------
# 课程状态
# ---------------------------------------------------------------------------


def test_in_progress_takes_priority_over_pass_flag():
    rows = [
        _module_row("table-row:2", "1 通识（所有子项均应满足要求）", "3.0", "", "", ""),
        _course_row("table-row:3", "1", "A1", "匿名课程甲", "3.0", "", "88", "是", "在读"),
    ]
    result = analyze_page_observation(_observation(rows=rows))
    course = result["courses"][0]

    assert course["state"] == "in_progress"
    assert course["in_progress"] is True
    assert [item["code"] for item in result["in_progress_courses"]] == ["A1"]
    assert result["page_progress"]["courses"][0]["state"] == "in_progress"
    assert result["page_progress"]["courses"][0]["counted"] is False
    assert result["can_decide_complete"] is False


def test_dash_grade_with_pass_flag_is_pending_recognition():
    rows = [
        _module_row("table-row:2", "1 通识（所有子项均应满足要求）", "3.0", "", "", ""),
        _course_row("table-row:3", "1", "A1", "匿名课程甲", "3.0", "", "--", "是", ""),
    ]
    result = analyze_page_observation(_observation(rows=rows))
    course = result["courses"][0]

    assert course["state"] == "pending_recognition"
    assert result["page_progress"]["courses"][0]["state"] == "pending_recognition"
    assert result["page_progress"]["courses"][0]["counted"] is False
    assert [
        item["course_id"] for item in result["page_progress"]["pending_recognition_courses"]
    ] == ["A1"]


def test_explicit_grade_with_pass_flag_is_passed():
    rows = [
        _module_row("table-row:2", "1 通识（所有子项均应满足要求）", "3.0", "", "", ""),
        _course_row("table-row:3", "1", "A1", "匿名课程甲", "3.0", "3.0", "92.5", "是", ""),
    ]
    result = analyze_page_observation(_observation(rows=rows))
    assert result["courses"][0]["state"] == "passed"
    assert result["page_progress"]["courses"][0]["counted"] is True


def test_grade_without_pass_flag_is_not_passed():
    rows = [_course_row("table-row:2", "1", "A1", "匿名课程甲", "3.0", "3.0", "88", "", "")]
    result = analyze_page_observation(_observation(rows=rows))
    assert result["courses"][0]["state"] == "unknown"


def test_negative_pass_flag_is_failed():
    rows = [_course_row("table-row:2", "1", "A1", "匿名课程甲", "3.0", "0", "50", "否", "")]
    result = analyze_page_observation(_observation(rows=rows))
    assert result["courses"][0]["state"] == "failed"


def test_module_total_is_not_treated_as_independent_pass():
    rows = [
        _module_row("table-row:2", "1 通识（所有子项均应满足要求）", "18", "18", "", ""),
        _course_row("table-row:3", "1", "A1", "匿名课程甲", "3.0", "3.0", "88", "是", ""),
    ]
    result = analyze_page_observation(_observation(rows=rows))
    progress_module = result["page_progress"]["modules"][0]

    assert progress_module["page"]["earned_credits"] == "18"
    assert progress_module["calculation"]["subtree_earned_credits"] == "3.0"
    assert progress_module["calculation"]["satisfied"] is False
    assert "page_earned_credits_mismatch" in progress_module["page_vs_calculation"]["discrepancy_codes"]
    assert result["can_decide_complete"] is False


# ---------------------------------------------------------------------------
# 快照与独立核算
# ---------------------------------------------------------------------------


def test_page_progress_never_decides_complete_under_partial_coverage():
    rows = [
        _module_row("table-row:2", "1 通识（所有子项均应满足要求）", "3.0", "", "", ""),
        _course_row("table-row:3", "1", "A1", "匿名课程甲", "3.0", "3.0", "88", "是", ""),
    ]
    result = analyze_page_observation(_observation(rows=rows))
    progress = result["page_progress"]

    assert progress is not None
    assert progress["can_decide_complete"] is False
    assert progress["plan_version_known"] is False
    assert progress["source_coverage"] == "partial"
    assert result["can_decide_complete"] is False
    assert result["status"] == "needs_verification"


def test_course_without_preceding_module_is_pending_not_fabricated():
    rows = [
        _course_row("table-row:2", "1", "A1", "匿名课程甲", "3.0", "3.0", "88", "是", ""),
        _module_row("table-row:3", "1 通识（所有子项均应满足要求）", "3.0", "", "", ""),
    ]
    result = analyze_page_observation(_observation(rows=rows))
    assert result["courses"][0]["module_row_index"] is None
    assert "course_without_module" in _pending_codes(result)


def test_course_without_parseable_credits_is_excluded_and_pending():
    rows = [
        _module_row("table-row:2", "1 通识（所有子项均应满足要求）", "", "", "", ""),
        _course_row("table-row:3", "1", "A1", "匿名课程甲", "", "", "88", "是", ""),
    ]
    result = analyze_page_observation(_observation(rows=rows))
    assert "course_credits_unknown" in _pending_codes(result)
    assert result["snapshot"]["courses"] == []


def test_failure_does_not_inject_demo_data():
    rows = [
        _module_row("table-row:2", "（一）甲类", "3.0", gap="缺3.0学分缺1门"),
        _module_row("table-row:3", "（二）乙类", "3.0", gap="缺3.0学分缺1门"),
    ]
    result = analyze_page_observation(_observation(rows=rows))
    assert result["page_progress"] is None
    assert result["snapshot"] is None
    assert result["snapshot_status"] == "not_built"
    assert result["snapshot_error"] is None
    assert result["can_decide_complete"] is False
    assert [module["label"] for module in result["modules"]] == ["（一）甲类", "（二）乙类"]


# ---------------------------------------------------------------------------
# 拒绝：身份 / 来源 / 时间 / 覆盖 / adapter / 未知字段
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "identity_cell",
    ["学号：20230001", "姓名：张三", "验证码", "身份证", "考生号", "手机号"],
)
def test_identity_text_is_rejected(identity_cell):
    rows = [_course_row("table-row:2", "1", "A1", identity_cell, "3.0", "3.0", "88", "是", "")]
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation(rows=rows))
    assert excinfo.value.code == "identity_text_rejected"


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://example.com/eams/myPlanCompl.action",
        "http://eamis.nankai.edu.cn/eams/myPlanCompl.action",
        CANONICAL_URL + "?studentId=1",
        "https://eamis.nankai.edu.cn/eams/other.action",
        "",
    ],
)
def test_unsupported_source_url_is_rejected(bad_url):
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], source=_source(url=bad_url)))
    assert excinfo.value.code == "unsupported_source_url"


@pytest.mark.parametrize("bad_time", ["not-a-time", "", 123, "2024-13-45T00:00:00"])
def test_invalid_capture_time_is_rejected(bad_time):
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], source=_source(captured_at=bad_time)))
    assert excinfo.value.code == "invalid_captured_at"


@pytest.mark.parametrize("bad_coverage", ["complete", "missing", "", 123])
def test_unsupported_coverage_is_rejected(bad_coverage):
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], source=_source(coverage=bad_coverage)))
    assert excinfo.value.code == "unsupported_coverage"


def test_adapter_verified_true_is_rejected():
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], source=_source(adapter_verified=True)))
    assert excinfo.value.code == "adapter_verified_unsupported"


@pytest.mark.parametrize("bad_flag", ["false", None, 0])
def test_non_boolean_adapter_verified_is_rejected(bad_flag):
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], source=_source(adapter_verified=bad_flag)))
    assert excinfo.value.code == "invalid_adapter_verified"


def test_unknown_fields_are_rejected_everywhere():
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], notes="x"))
    assert excinfo.value.code == "unknown_field"

    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], source=_source(extra=1)))
    assert excinfo.value.code == "unknown_field"

    rows = [{"cells": ["a"], "locator": "table-row:2", "extra": 1}]
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation(rows))
    assert excinfo.value.code == "unknown_field"


# ---------------------------------------------------------------------------
# 拒绝：表头 / 结构
# ---------------------------------------------------------------------------


def test_unknown_or_missing_or_duplicate_headers_are_rejected():
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], headers=HEADERS[:-1] + ["学期"]))
    assert excinfo.value.code == "unsupported_headers"

    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], headers=HEADERS[:-1]))
    assert excinfo.value.code == "unsupported_headers"

    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], headers=["序号", "序号", *HEADERS[2:]]))
    assert excinfo.value.code == "unsupported_headers"


def test_invalid_structures_are_rejected():
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation([])
    assert excinfo.value.code == "invalid_observation"

    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], kind="other"))
    assert excinfo.value.code == "invalid_kind"

    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([], source=[]))
    assert excinfo.value.code == "invalid_source"

    bad_rows = _observation([])
    bad_rows["rows"] = {"a": 1}
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(bad_rows)
    assert excinfo.value.code == "invalid_rows"

    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([{"cells": "x", "locator": "r"}]))
    assert excinfo.value.code == "invalid_cells"

    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation([{"cells": ["a"]}]))
    assert excinfo.value.code == "invalid_locator"


# ---------------------------------------------------------------------------
# 上限
# ---------------------------------------------------------------------------


def test_row_count_limit_is_enforced():
    rows = [
        {"cells": ["", "", "", "", "", "", "", ""], "locator": f"table-row:{index}"}
        for index in range(MAX_ROWS + 1)
    ]
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation(rows))
    assert excinfo.value.code == "too_many_rows"


def test_cells_per_row_limit_is_enforced():
    rows = [{"cells": ["x"] * (MAX_CELLS_PER_ROW + 1), "locator": "table-row:2"}]
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation(rows))
    assert excinfo.value.code == "too_many_cells"


def test_cell_length_limit_is_enforced():
    rows = [{"cells": ["x" * (MAX_CELL_CHARS + 1)], "locator": "table-row:2"}]
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation(rows))
    assert excinfo.value.code == "cell_too_large"


def test_total_payload_limit_is_enforced():
    rows = [
        {
            "cells": ["x" * 4000] * 8,
            "locator": f"table-row:{index}",
        }
        for index in range(40)
    ]
    assert 40 * 8 * 4000 > MAX_OBSERVATION_BYTES
    with pytest.raises(PageObservationValidationError) as excinfo:
        analyze_page_observation(_observation(rows))
    assert excinfo.value.code == "observation_too_large"


# ---------------------------------------------------------------------------
# 输入不变
# ---------------------------------------------------------------------------


def test_input_observation_is_not_mutated():
    rows = [
        _module_row("table-row:2", "1 通识（所有子项均应满足要求）", "3.0", "", "", ""),
        _course_row("table-row:3", "1", "A1", "匿名课程甲", "3.0", "3.0", "88", "是", ""),
    ]
    observation = _observation(rows=rows)
    before = copy.deepcopy(observation)
    analyze_page_observation(observation)
    assert observation == before

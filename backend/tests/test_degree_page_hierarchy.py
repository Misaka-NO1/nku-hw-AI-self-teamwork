"""培养计划 DOM 章节层级推断的独立测试。

全部标签、行号与 locator 均为匿名虚构值：不读 fixtures、不联网、不依赖既有
解析器。测试锚定 ``infer_degree_hierarchy`` 的保守边界：

* NBSP / 全角空格，全角 ``（）`` 与半角 ``()`` 括号；
* 「主章 → 括号子章 → 数字子模块 → 点分细项」以及四级 / 更深点分；
* 局部编号不是全局 ID：跨主章 / 跨子章重复数字合法，同域重复非法；
* 点分编号必须能找到同一局部范围内明确存在的直接父编号；
* 缺主章 → ``profile == "unsupported"``，交回既有纯数字解析；
* 来源顺序（重复 / 逆序的 ``row_index``）与无法识别 marker；
* 纯函数：不修改输入，输出只有约定字段。
"""

from __future__ import annotations

import copy

import pytest

from app.domains.degree.page_hierarchy import (
    PROFILE_CHINESE_CHAPTERED,
    PROFILE_UNSUPPORTED,
    infer_degree_hierarchy,
)

NBSP = "\u00a0"


# ---------------------------------------------------------------------------
# 构造器（匿名虚构）
# ---------------------------------------------------------------------------


def _module(row_index, label, locator=None):
    return {
        "row_index": row_index,
        "label": label,
        "locator": locator if locator is not None else f"dom-row:{row_index}",
    }


def _modules(*labels):
    return [_module(index, label) for index, label in enumerate(labels)]


def _codes(result):
    return [item["code"] for item in result["pending"]]


# ---------------------------------------------------------------------------
# 正常层级
# ---------------------------------------------------------------------------


def test_canonical_chaptered_dom_builds_local_scopes():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章(所有子项均应满足要求)",
        f"(一){NBSP}虚构子章",
        f"1{NBSP}虚构子模块",
        f"1.1{NBSP}虚构细项",
        f"(二){NBSP}另一子章",
        f"1{NBSP}虚构子模块",
        f"二{NBSP}第二主章",
        f"(一){NBSP}虚构子章",
        f"1{NBSP}虚构子模块",
    ))

    assert result["known"] is True
    assert result["profile"] == PROFILE_CHINESE_CHAPTERED
    assert result["pending"] == []
    assert result["root_rows"] == [0, 6]
    assert result["parent_by_row"] == {
        0: None,
        1: 0,
        2: 1,
        3: 2,
        4: 0,
        5: 4,
        6: None,
        7: 6,
        8: 7,
    }


def test_nbsp_and_bracket_width_variants_are_recognized():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章",
        f"（一）{NBSP}全角括号子章",
        f"1{NBSP}虚构子模块",
        f"(二)\u3000半角括号加全角空格子章",
        f"1{NBSP}虚构子模块",
    ))

    assert result["known"] is True
    assert result["parent_by_row"] == {0: None, 1: 0, 2: 1, 3: 0, 4: 3}


def test_main_chapter_with_chinese_separator_is_recognized():
    result = infer_degree_hierarchy(_modules(
        "一、虚构主章",
        f"(一){NBSP}虚构子章",
        f"1{NBSP}虚构子模块",
    ))

    assert result["known"] is True
    assert result["parent_by_row"] == {0: None, 1: 0, 2: 1}


def test_numeric_separator_variants_are_recognized():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章",
        "1、虚构子模块",
        "2\u3000虚构子模块",
        "3 虚构子模块",
    ))

    assert result["known"] is True
    assert result["parent_by_row"] == {0: None, 1: 0, 2: 0, 3: 0}


def test_numeric_module_may_sit_directly_under_main_chapter():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章",
        f"1{NBSP}虚构子模块",
        f"1.1{NBSP}虚构细项",
        f"2{NBSP}虚构子模块",
    ))

    assert result["known"] is True
    assert result["parent_by_row"] == {0: None, 1: 0, 2: 1, 3: 0}


def test_four_level_and_deeper_dotted_numbering():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章",
        f"1{NBSP}虚构子模块",
        f"1.1{NBSP}虚构细项",
        f"1.1.1{NBSP}更深细项",
        f"1.1.1.1{NBSP}最深细项",
        f"1.2{NBSP}同级细项",
    ))

    assert result["known"] is True
    assert result["parent_by_row"] == {0: None, 1: 0, 2: 1, 3: 2, 4: 3, 5: 1}


def test_same_number_under_different_parents_is_legal():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章",
        f"(一){NBSP}虚构子章",
        f"1{NBSP}虚构子模块",
        f"1.1{NBSP}虚构细项",
        f"(二){NBSP}另一子章",
        f"1{NBSP}虚构子模块",
        f"1.1{NBSP}虚构细项",
        f"二{NBSP}第二主章",
        f"1{NBSP}虚构子模块",
    ))

    assert result["known"] is True
    assert result["pending"] == []
    assert result["root_rows"] == [0, 7]
    assert result["parent_by_row"] == {
        0: None,
        1: 0,
        2: 1,
        3: 2,
        4: 0,
        5: 4,
        6: 5,
        7: None,
        8: 7,
    }


def test_extra_module_fields_are_ignored_and_not_treated_as_evidence():
    modules = [
        {
            "row_index": 0,
            "label": f"一{NBSP}虚构主章",
            "locator": "dom-row:0",
            "required_credits": "18",
            "requirement": "all",
            "raw_cells": ["一 虚构主章"],
        },
        {
            "row_index": 1,
            "label": f"1{NBSP}虚构子模块",
            "locator": "dom-row:1",
            "page_earned_credits": "3.0",
        },
    ]
    result = infer_degree_hierarchy(modules)

    assert result["known"] is True
    assert result["parent_by_row"] == {0: None, 1: 0}


def test_rule_text_is_not_treated_as_instruction():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章(所有子项均应满足要求)",
        f"1{NBSP}虚构子模块(至少一项)",
    ))

    assert result["known"] is True
    assert result["parent_by_row"] == {0: None, 1: 0}
    assert set(result) == {"known", "profile", "parent_by_row", "root_rows", "pending"}


# ---------------------------------------------------------------------------
# 重复与缺父
# ---------------------------------------------------------------------------


def test_duplicate_local_number_in_same_scope_is_rejected():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章",
        f"(一){NBSP}虚构子章",
        f"1{NBSP}虚构子模块",
        f"1{NBSP}重复的虚构子模块",
    ))

    assert result["known"] is False
    assert "duplicate_local_number" in _codes(result)
    assert result["root_rows"] == [0]


def test_duplicate_main_chapter_number_is_rejected():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章甲",
        f"一{NBSP}虚构主章乙",
    ))

    assert result["known"] is False
    assert "duplicate_local_number" in _codes(result)


def test_dotted_number_without_direct_parent_is_pending():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章",
        f"1{NBSP}虚构子模块",
        f"1.1.1{NBSP}跳跃的虚构细项",
    ))

    assert result["known"] is False
    assert "dotted_parent_missing" in _codes(result)
    assert 2 not in result["parent_by_row"]


def test_dotted_parent_in_other_scope_is_not_accepted():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章",
        f"1{NBSP}虚构子模块",
        f"(一){NBSP}虚构子章",
        f"1.1{NBSP}虚构细项",
    ))

    assert result["known"] is False
    assert "dotted_parent_missing" in _codes(result)
    assert 3 not in result["parent_by_row"]


# ---------------------------------------------------------------------------
# 缺主章 / 未识别 marker
# ---------------------------------------------------------------------------


def test_missing_main_chapter_returns_unsupported_profile():
    result = infer_degree_hierarchy(_modules(
        f"1{NBSP}虚构子模块",
        f"1.1{NBSP}虚构细项",
    ))

    assert result["known"] is False
    assert result["profile"] == PROFILE_UNSUPPORTED
    assert result["parent_by_row"] == {}
    assert result["root_rows"] == []
    assert _codes(result) == ["missing_main_chapter"]


def test_bracket_subchapter_without_main_chapter_is_pending():
    result = infer_degree_hierarchy(_modules(f"(一){NBSP}虚构子章"))

    assert result["known"] is False
    assert result["profile"] == PROFILE_UNSUPPORTED
    assert set(_codes(result)) == {
        "missing_main_chapter",
        "subchapter_without_main_chapter",
    }
    assert result["parent_by_row"] == {}
    assert result["root_rows"] == []


def test_numeric_module_before_first_main_chapter_is_pending():
    result = infer_degree_hierarchy(_modules(
        f"1{NBSP}虚构子模块",
        f"一{NBSP}虚构主章",
        f"1{NBSP}虚构子模块",
    ))

    assert result["known"] is False
    assert result["profile"] == PROFILE_CHINESE_CHAPTERED
    assert "module_without_main_chapter" in _codes(result)
    assert result["root_rows"] == [1]
    assert result["parent_by_row"] == {1: None, 2: 1}


def test_chinese_numeral_without_separator_is_not_a_main_chapter():
    result = infer_degree_hierarchy(_modules("一虚构主章"))

    assert result["known"] is False
    assert result["profile"] == PROFILE_UNSUPPORTED
    assert set(_codes(result)) == {"missing_main_chapter", "unrecognized_marker"}
    assert result["root_rows"] == []


def test_unrecognized_marker_is_pending_and_not_guessed():
    result = infer_degree_hierarchy(_modules(
        f"一{NBSP}虚构主章",
        "第1章 虚构章节",
    ))

    assert result["known"] is False
    assert "unrecognized_marker" in _codes(result)
    assert 1 not in result["parent_by_row"]


# ---------------------------------------------------------------------------
# 来源顺序与输入形状
# ---------------------------------------------------------------------------


def test_duplicate_row_index_is_rejected():
    result = infer_degree_hierarchy([
        _module(0, f"一{NBSP}虚构主章甲"),
        _module(0, f"二{NBSP}虚构主章乙"),
    ])

    assert result["known"] is False
    assert "duplicate_row_index" in _codes(result)


def test_out_of_order_row_index_is_rejected():
    result = infer_degree_hierarchy([
        _module(3, f"一{NBSP}虚构主章甲"),
        _module(2, f"二{NBSP}虚构主章乙"),
    ])

    assert result["known"] is False
    assert "row_index_out_of_order" in _codes(result)


@pytest.mark.parametrize("bad_input", [None, "一 虚构主章", {"row_index": 0}, 7])
def test_non_array_input_is_unsupported(bad_input):
    result = infer_degree_hierarchy(bad_input)

    assert result["known"] is False
    assert result["profile"] == PROFILE_UNSUPPORTED
    assert result["parent_by_row"] == {}
    assert result["root_rows"] == []
    assert _codes(result) == ["invalid_modules_input"]


def test_invalid_module_report_is_pending():
    result = infer_degree_hierarchy([
        {"row_index": 0, "locator": "dom-row:0"},
        {"row_index": "1", "label": f"一{NBSP}虚构主章", "locator": "dom-row:1"},
        {"row_index": 2, "label": f"二{NBSP}虚构主章", "locator": ""},
    ])

    assert result["known"] is False
    assert set(_codes(result)) == {"invalid_module_report"}
    assert len(result["pending"]) == 3


def test_empty_modules_is_unsupported_without_noise():
    assert infer_degree_hierarchy([]) == {
        "known": False,
        "profile": PROFILE_UNSUPPORTED,
        "parent_by_row": {},
        "root_rows": [],
        "pending": [],
    }


# ---------------------------------------------------------------------------
# 纯函数约束
# ---------------------------------------------------------------------------


def test_input_modules_are_not_mutated():
    modules = _modules(
        f"一{NBSP}虚构主章",
        f"(一){NBSP}虚构子章",
        f"1{NBSP}虚构子模块",
        f"1.1{NBSP}虚构细项",
    )
    before = copy.deepcopy(modules)
    infer_degree_hierarchy(modules)

    assert modules == before


def test_output_shape_is_stable():
    result = infer_degree_hierarchy(_modules(f"一{NBSP}虚构主章"))
    assert set(result) == {"known", "profile", "parent_by_row", "root_rows", "pending"}
    assert result["pending"] == []

    bad = infer_degree_hierarchy(_modules("无法识别的虚构标签"))
    assert bad["pending"]
    for item in bad["pending"]:
        assert set(item) == {"code", "detail", "locator"}

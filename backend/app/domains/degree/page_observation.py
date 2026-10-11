"""培养计划原表格观察值（degree-table-observation）的保守解析。

定位
----
``analyze_page_observation(observation)`` 消费 ``packages/import-core/src/degree-page.ts``
中 ``DegreeTableObservation`` 的**独立契约**：只读取调用方选定的培养计划表格，
不做身份识别、不访问 HTTP / MCP / 数据库、不修改 ``analyze_page_progress`` 或
``audit_degree_progress``。它负责「把教务页面表格读成可解释的原值报告」，并在
**模块层级有明确证据**时构造 page_progress 快照交给 ``analyze_page_progress``
做独立核算。

契约（顶层 / source / row 的未知字段一律拒绝）::

    {
      "kind": "degree-table-observation",
      "source": {
        "url": "https://eamis.nankai.edu.cn/eams/myPlanCompl.action",
        "captured_at": "<合法 ISO 时间>",
        "coverage": "partial" | "unknown",
        "adapter_verified": false
      },
      "headers": ["序号", "课程序号", "课程名称", "要求学分",
                  "实修学分", "成绩", "是否通过", "备注"],
      "rows": [{"cells": ["..."], "locator": "table-row:3"}]
    }

目标表格形状
------------
* 表头固定为上述已知列；``序号`` 可省略（此时按 7 列处理），其余 7 列必需。
* **课程行**是整行（``序号`` 存在时 8 格），逐列取值。
* **模块行**首格横跨前 ``lead_span`` 列（含 ``序号`` 时为 3 列），因此只有
  ``len(headers) - lead_span + 1`` 格。例如原始 6 格模块行::

      ["（一）理想与信念教育类", "18", "8.5", "", "缺9.5学分缺4门", ""]

  依次对应：模块标签 / 要求学分 / 实修学分 / 成绩 / 是否通过（缺口）/ 备注。
* 模块行**不能只靠形状**判定：必须同时具备模块编号与规则文本或缺口语义。

校验与上限
----------
仅允许精确来源 ``https://eamis.nankai.edu.cn/eams/myPlanCompl.action``、合法
ISO 时间、``partial`` / ``unknown`` 覆盖、``adapter_verified`` 为 ``false``、
已知表头；拒绝身份文本与未知字段。上限：整体 1 MiB、2000 行、每行 64 格、
每格 4096 字符。校验顺序为：结构 → 行数 / 格数 / 格长 → 整体字节 → 身份文本。

保守规则
--------
* 父子关系只由明确的点分编号（``1`` / ``1.1`` / ``1.2``）建立；中文
  ``一`` / ``（一）`` 层级无法完全确定时只报告未知，不猜。
* 模块文字含「所有子项满足」「所有子项均应满足要求」判为 ``all``；
  「至少一项」判为 ``any``；其余保留 ``unknown``。
* 在读优先于「是否通过＝是」且不计为 ``passed``；成绩 ``--`` 且「是」但无
  在读标识时，页面报通过但独立状态为 ``pending_recognition``；只有明确数值
  成绩或通过文本且「是」才判 ``passed``。
* 页面模块总值只作为页面显示（``reported_earned_credits``），绝不当作独立
  已通过。
* 未知版本 / 未知覆盖 / 任有待核实项 / 快照未构造或独立核算失败时
  ``can_decide_complete`` 恒为 ``False``；失败不补演示数据。

返回结构（节选）
----------------
``status``（镜像独立核算结论）、``parse_status``（结构是否完全读懂）、
``can_decide_complete``、``reports``（原值报告分组）与同名快捷键 ``modules``
（含可读 ``name``、``required_credits``、``page_earned_credits``、``gap_text``）、
``courses``、``in_progress_courses``、``unclassified_rows``、
``pending_verification``、``snapshot_status`` / ``snapshot`` / ``snapshot_error``、
``page_progress``。每条报告都保留 ``raw_cells`` 与 ``evidence.locator``。
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.domains.degree.page_progress import (
    PageProgressValidationError,
    analyze_page_progress,
)

OBSERVATION_VERSION = "degree-page-observation-v1"
KIND = "degree-table-observation"
CANONICAL_URL = "https://eamis.nankai.edu.cn/eams/myPlanCompl.action"

MAX_OBSERVATION_BYTES = 1024 * 1024  # 1 MiB
MAX_ROWS = 2000
MAX_CELLS_PER_ROW = 64
MAX_CELL_CHARS = 4096

_TOP_LEVEL_FIELDS = frozenset({"kind", "source", "headers", "rows"})
_SOURCE_FIELDS = frozenset({"url", "captured_at", "coverage", "adapter_verified"})
_ROW_FIELDS = frozenset({"cells", "locator"})
_COVERAGE_VALUES = ("partial", "unknown")

_REQUIRED_HEADERS = ("课程序号", "课程名称", "要求学分", "实修学分", "成绩", "是否通过", "备注")
_OPTIONAL_HEADERS = ("序号",)
_KNOWN_HEADERS = frozenset(_OPTIONAL_HEADERS + _REQUIRED_HEADERS)

_FULL = "full"
_LEAD_SPAN = "lead_span"

# ---------------------------------------------------------------------------
# 文本语义（全部作用在已 trim 的页面原值上）
# ---------------------------------------------------------------------------

_IDENTITY_RE = re.compile(
    r"(?:学号|姓名)\s*[:：]"
    r"|验证码"
    r"|密码(?![学])"
    r"|身份证"
    r"|考生号"
    r"|学籍号"
    r"|准考证"
    r"|联系电话"
    r"|手机号"
)

# 模块编号：点分阿拉伯数字（1 / 1.1 / 1.2.3）是唯一可用于建立父子关系的证据。
_DOTTED_RE = re.compile(r"(\d+(?:\.\d+)+)")
_PLAIN_BRACKET_RE = re.compile(r"[（(【\[]\s*(\d+)\s*[)）】\]]\s*")
_PLAIN_SEP_RE = re.compile(r"(\d+)\s*[、.．,，:：]\s*")
_PLAIN_SPACE_RE = re.compile(r"(\d+)\s+(?=\S)")
# 中文编号（一 / （一） / 一、）能识别编号，但层级无法完全确定。
_CHINESE_RE = re.compile(
    r"(?:[（(【\[]\s*([一二三四五六七八九十]+)\s*[)）】\]]"
    r"|([一二三四五六七八九十]+)\s*[、.．])"
)
_CHINESE_MAJOR_RE = re.compile(r"([一二三四五六七八九十]+)\s+(?=\S)")

_ALL_RULES = (
    "所有子项均应满足要求",
    "所有子项均应满足",
    "所有子项均需满足",
    "所有子项满足",
    "所有子项均",
    "全部子项满足",
    "全部子项均",
    "均应满足",
)
_ANY_RULES = ("至少满足一项", "至少一项", "任一子项", "任一项", "任选一项")

_GAP_TOKEN_RE = re.compile(r"[缺差]")
_GAP_CREDIT_RE = re.compile(r"[缺差]\s*([0-9]+(?:\.[0-9]+)?)\s*学分")
_GAP_COUNT_RE = re.compile(r"[缺差]\s*([0-9]+)\s*门")

_SATISFIED_TOKENS = ("已满足", "已完成", "已达标", "达标")

_IN_PROGRESS_TOKENS = ("在读", "在修", "修读中", "正在修")

_AFFIRMATIVE_FLAGS = frozenset({"是", "通过", "已通过", "合格", "及格", "y", "yes", "true", "√", "✓"})
_NEGATIVE_FLAGS = frozenset({"否", "未通过", "不合格", "不及格", "n", "no", "false", "×", "✗"})
_INDEFINITE_GRADES = frozenset({"", "--", "—", "－", "-", "/", "无", "暂无", "null", "none", "n/a", "na", "待定"})

_CREDIT_RE = re.compile(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(?:学分)?$")


class PageObservationValidationError(ValueError):
    """观察值契约无法安全解析时抛出；``code`` 稳定，可用于断言。"""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _fail(code: str, detail: str) -> None:
    raise PageObservationValidationError(code, detail)


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _require_text(value: Any, *, code: str, field: str) -> str:
    if not isinstance(value, str):
        _fail(code, f"{field} 必须是字符串")
    text = value.strip()
    if not text:
        _fail(code, f"{field} 不能为空")
    return text


def _reject_unknown_fields(node: Mapping[str, Any], allowed: frozenset[str], *, context: str) -> None:
    extra = sorted(str(key) for key in node if key not in allowed)
    if extra:
        _fail("unknown_field", f"{context} 含未知字段 {extra}")


def _as_list(value: Any, *, code: str, field: str) -> list[Any]:
    if isinstance(value, (str, bytes, bytearray)) or isinstance(value, Mapping):
        _fail(code, f"{field} 必须是列表")
    if not isinstance(value, Sequence):
        _fail(code, f"{field} 必须是列表")
    return list(value)


def _fmt(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _parse_captured_at(value: Any) -> str:
    text = _require_text(value, code="invalid_captured_at", field="source.captured_at")
    candidate = text
    if candidate.endswith(("Z", "z")):
        candidate = candidate[:-1] + "+00:00"
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        _fail("invalid_captured_at", f"source.captured_at 不是合法 ISO 时间: {text!r}")
    return text


def _parse_credits(value: Any) -> Decimal | None:
    text = _text(value)
    if text is None:
        return None
    match = _CREDIT_RE.match(text)
    if not match:
        return None
    dec = Decimal(match.group(1))
    if not dec.is_finite() or dec < 0:
        return None
    return dec


def _is_definite_grade(value: Any) -> bool:
    text = _text(value)
    if text is None:
        return False
    if text.lower() in _INDEFINITE_GRADES:
        return False
    if text in {"通过", "合格", "及格", "优秀", "良好", "中等"}:
        return True
    try:
        number = Decimal(text)
        return number.is_finite() and number >= 0
    except Exception:
        return False


def _normalize_flag(value: Any) -> bool | None:
    text = _text(value)
    if text is None:
        return None
    lowered = text.lower()
    if lowered in _AFFIRMATIVE_FLAGS:
        return True
    if lowered in _NEGATIVE_FLAGS:
        return False
    return None


def _pending(
    code: str,
    detail: str,
    *,
    locator: str | None = None,
    row_index: int | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "detail": detail,
        "locator": locator,
        "row_index": row_index,
    }


def _dedup_pending(items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = (item["code"], item["locator"] or "", item["detail"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    result.sort(key=lambda item: (item["code"], item["locator"] or "", item["detail"]))
    return result


# ---------------------------------------------------------------------------
# 契约校验
# ---------------------------------------------------------------------------


def _validate_headers(value: Any) -> list[str]:
    raw = _as_list(value, code="invalid_headers", field="headers")
    if not raw:
        _fail("unsupported_headers", "headers 不能为空")
    headers: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str):
            _fail("invalid_headers", f"headers[{index}] 必须是字符串")
        headers.append(item.strip())
    seen: set[str] = set()
    for header in headers:
        if header not in _KNOWN_HEADERS:
            _fail("unsupported_headers", f"headers 含未知列 {header!r}")
        if header in seen:
            _fail("unsupported_headers", f"headers 含重复列 {header!r}")
        seen.add(header)
    missing = [header for header in _REQUIRED_HEADERS if header not in seen]
    if missing:
        _fail("unsupported_headers", f"headers 缺少必需列 {missing}")
    return headers


def _validate_rows(value: Any) -> list[dict[str, Any]]:
    raw = _as_list(value, code="invalid_rows", field="rows")
    if len(raw) > MAX_ROWS:
        _fail("too_many_rows", f"rows 超过 {MAX_ROWS} 行上限")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            _fail("invalid_rows", f"rows[{index}] 必须是对象")
        context = f"rows[{index}]"
        _reject_unknown_fields(item, _ROW_FIELDS, context=context)
        cells_raw = _as_list(item.get("cells"), code="invalid_cells", field=f"{context}.cells")
        if len(cells_raw) > MAX_CELLS_PER_ROW:
            _fail("too_many_cells", f"{context}.cells 超过 {MAX_CELLS_PER_ROW} 格上限")
        cells: list[str] = []
        for cell_index, cell in enumerate(cells_raw):
            if not isinstance(cell, str):
                _fail("invalid_cells", f"{context}.cells[{cell_index}] 必须是字符串")
            text = cell.strip()
            if len(text) > MAX_CELL_CHARS:
                _fail(
                    "cell_too_large",
                    f"{context}.cells[{cell_index}] 超过 {MAX_CELL_CHARS} 字符上限",
                )
            cells.append(text)
        locator = _text(item.get("locator"))
        if locator is None:
            _fail("invalid_locator", f"{context}.locator 必须是非空字符串")
        rows.append({"cells": cells, "locator": locator})
    return rows


def _enforce_payload_size(headers: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    blob = json.dumps(
        {"headers": list(headers), "rows": [dict(row) for row in rows]},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if len(blob.encode("utf-8")) > MAX_OBSERVATION_BYTES:
        _fail("observation_too_large", f"观察值超过 {MAX_OBSERVATION_BYTES} 字节上限")


def _reject_identity(headers: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    for header in headers:
        if _IDENTITY_RE.search(header):
            _fail("identity_text_rejected", f"表头含身份文本: {header!r}")
    for row in rows:
        for cell in row["cells"]:
            if _IDENTITY_RE.search(cell):
                _fail(
                    "identity_text_rejected",
                    f"{row['locator']} 含身份文本: {cell!r}",
                )


# ---------------------------------------------------------------------------
# 行解析
# ---------------------------------------------------------------------------


def _row_binding(cells_len: int, headers_len: int, lead_span: int) -> str | None:
    if cells_len == headers_len:
        return _FULL
    if cells_len == headers_len - lead_span + 1:
        return _LEAD_SPAN
    return None


def _cell_for(
    cells: Sequence[str],
    header_index: Mapping[str, int],
    header: str,
    binding: str,
    lead_span: int,
) -> str:
    index = header_index.get(header)
    if index is None:
        # 可省略列（如 7 列表头的 ``序号``）视为空值，不猜。
        return ""
    if binding == _FULL:
        return cells[index]
    if index < lead_span:
        return cells[0]
    return cells[index - lead_span + 1]


def _module_marker(label: str) -> dict[str, Any] | None:
    text = label.lstrip()
    major = _CHINESE_MAJOR_RE.match(text)
    if major:
        return {"raw": major.group(0).strip(), "number": major.group(1), "kind": "chinese", "numerical_id": None, "end": major.end()}
    dotted = _DOTTED_RE.match(text)
    if dotted:
        number = dotted.group(1)
        return {"raw": dotted.group(0), "number": number, "kind": "arabic", "numerical_id": number, "end": dotted.end()}
    bracket = _PLAIN_BRACKET_RE.match(text)
    if bracket:
        number = bracket.group(1)
        return {"raw": bracket.group(0).strip(), "number": number, "kind": "arabic", "numerical_id": number, "end": bracket.end()}
    separated = _PLAIN_SEP_RE.match(text)
    if separated:
        number = separated.group(1)
        return {"raw": separated.group(0).strip(), "number": number, "kind": "arabic", "numerical_id": number, "end": separated.end()}
    spaced = _PLAIN_SPACE_RE.match(text)
    if spaced:
        number = spaced.group(1)
        return {"raw": spaced.group(0).strip(), "number": number, "kind": "arabic", "numerical_id": number, "end": spaced.end()}
    chinese = _CHINESE_RE.match(text)
    if chinese:
        number = chinese.group(1) or chinese.group(2)
        return {"raw": chinese.group(0).strip(), "number": number, "kind": "chinese", "numerical_id": None, "end": chinese.end()}
    return None


def _module_name(label: str, end: int) -> str | None:
    remainder = label.lstrip()[end:]
    # 只去掉编号后的分隔符；括号属于模块名/规则文本本身，不能剥掉。
    name = remainder.strip(" \t、,，.．:：;；-—")
    return name or None


def _dotted_prefixes(value: str) -> list[str]:
    parts = value.split(".")
    return [".".join(parts[:size]) for size in range(len(parts) - 1, 0, -1)]


def _requirement_rule(text: str) -> tuple[str, str | None]:
    for token in _ALL_RULES:
        if token in text:
            return "all", token
    for token in _ANY_RULES:
        if token in text:
            return "any", token
    return "unknown", None


def _gap_text(*candidates: str) -> str | None:
    for candidate in candidates:
        if candidate and _GAP_TOKEN_RE.search(candidate):
            return candidate
    return None


def _parse_gap(text: str | None) -> tuple[Decimal | None, int | None]:
    if not text:
        return None, None
    credits: Decimal | None = None
    count: int | None = None
    credit_match = _GAP_CREDIT_RE.search(text)
    if credit_match:
        credits = Decimal(credit_match.group(1))
    count_match = _GAP_COUNT_RE.search(text)
    if count_match:
        count = int(count_match.group(1))
    return credits, count


def _course_page_state(grade: str, pass_text: str, remark: str) -> str:
    combined = " ".join(part for part in (grade, pass_text, remark) if part)
    if any(token in combined for token in _IN_PROGRESS_TOKENS):
        return "in_progress"
    flag = _normalize_flag(pass_text)
    if flag is True:
        if _is_definite_grade(grade):
            return "passed"
        return "pending_recognition"
    if flag is False:
        return "failed"
    return "unknown"


def _module_reported_satisfied(pass_text: str, remark: str, gap: str | None) -> bool | None:
    if gap is not None:
        return False
    combined = f"{pass_text} {remark}"
    if any(token in combined for token in _SATISFIED_TOKENS):
        return True
    return None


def _evidence(locator: str, role: str, cells: Sequence[str]) -> dict[str, Any]:
    return {"locator": locator, "row_role": role, "cells": list(cells)}


# ---------------------------------------------------------------------------
# 快照构造（仅在层级证据充分时）
# ---------------------------------------------------------------------------


def _plan_snapshot(module_reports: Sequence[Mapping[str, Any]]) -> tuple[bool, list[str]]:
    if not module_reports:
        return True, []
    numerical_ids = [module["numerical_id"] for module in module_reports]
    if all(value is not None for value in numerical_ids):
        if len(set(numerical_ids)) != len(numerical_ids):
            return False, ["duplicate_module_number"]
        id_set = set(numerical_ids)
        parents: dict[str, str | None] = {}
        for value in numerical_ids:
            parents[value] = next(
                (prefix for prefix in _dotted_prefixes(value) if prefix in id_set),
                None,
            )
        roots = [value for value in numerical_ids if parents[value] is None]
        if len(roots) != 1:
            return False, ["multiple_roots_without_common_parent"]
        return True, []
    if len(module_reports) == 1:
        # 只有一个模块时不需要推断任何父子关系。
        return True, []
    return False, ["module_hierarchy_unknown"]


def _assemble_snapshot(
    *,
    url: str,
    captured_at: str,
    coverage: str,
    course_reports: Sequence[Mapping[str, Any]],
    module_reports: Sequence[Mapping[str, Any]],
    course_meta: Mapping[int, Mapping[str, Any]],
    hierarchy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    numerical_ids = {
        module["numerical_id"]
        for module in module_reports
        if module["numerical_id"] is not None
    }

    module_id_by_row: dict[int, str] = {}
    for module in module_reports:
        row_index = module["row_index"]
        if hierarchy is not None:
            module_id_by_row[row_index] = f"module-row-{row_index}"
        elif module["numerical_id"] is not None:
            module_id_by_row[row_index] = f"module-{module['numerical_id']}"
        else:
            module_id_by_row[row_index] = f"module-row-{row_index}"

    course_id_by_row: dict[int, str] = {}
    snapshot_courses: list[dict[str, Any]] = []
    for course in course_reports:
        row_index = course["row_index"]
        meta = course_meta.get(row_index, {})
        credits = meta.get("earned") if course["state"] == "passed" else meta.get("required")
        if credits is None:
            credits = meta.get("required") if course["state"] == "passed" else meta.get("earned")
        if credits is None:
            # 没有可核对的学分时，不猜、不补，直接不进入快照。
            continue
        course_id = course["code"] or f"row-{course['locator']}"
        course_id_by_row[row_index] = course_id
        snapshot_courses.append(
            {
                "course_id": course_id,
                "code": course["code"],
                "name": course["name"],
                "credits": str(credits),
                "state": course["state"],
                "evidence": copy.deepcopy(course["evidence"]),
            }
        )

    courses_by_module: dict[int, list[str]] = {}
    required_by_module: dict[int, list[str]] = {}
    for course in course_reports:
        row_index = course["row_index"]
        module_row = course["module_row_index"]
        course_id = course_id_by_row.get(row_index)
        if module_row is None or course_id is None:
            continue
        courses_by_module.setdefault(module_row, []).append(course_id)
        if re.search(r"(?<!非)必修", course.get("remark") or ""):
            required_by_module.setdefault(module_row, []).append(course_id)

    snapshot_modules: list[dict[str, Any]] = []
    for module in module_reports:
        row_index = module["row_index"]
        parent_id: str | None = None
        if hierarchy is not None:
            parent_row = hierarchy["parent_by_row"][row_index]
            parent_id = module_id_by_row[parent_row] if parent_row is not None else "observed-table-root"
        elif module["numerical_id"] is not None:
            parent_number = next(
                (prefix for prefix in _dotted_prefixes(module["numerical_id"]) if prefix in numerical_ids),
                None,
            )
            if parent_number is not None:
                parent_id = f"module-{parent_number}"
        snapshot_modules.append(
            {
                "module_id": module_id_by_row[row_index],
                "name": module["name"],
                "parent_id": parent_id,
                "requirement": module["requirement"],
                "required_credits": module["required_credits"],
                "reported_earned_credits": module["page_earned_credits"],
                "reported_remaining_credits": module["gap_credits"],
                "reported_satisfied": module["reported_satisfied"],
                "course_ids": sorted(set(courses_by_module.get(row_index, []))),
                "required_course_ids": sorted(set(required_by_module.get(row_index, []))),
                "evidence": copy.deepcopy(module["evidence"]),
            }
        )

    if hierarchy is not None:
        snapshot_modules.append({"module_id": "observed-table-root", "name": "本次读取的顶层模块",
            "parent_id": None, "requirement": "unknown", "required_credits": None,
            "course_ids": [], "required_course_ids": [],
            "evidence": {"locator": "observed-table-root", "row_role": "synthetic_group", "cells": []}})

    return {
        "plan_version": None,  # 页面不提供版本：未知版本不得判完成。
        "source_coverage": coverage,
        "missing_pages": [],
        "repeat_policy": None,
        "evidence": {"url": url, "captured_at": captured_at, "adapter_verified": False},
        "coverage_evidence": {"url": url, "coverage": coverage},
        "courses": snapshot_courses,
        "modules": snapshot_modules,
    }


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def analyze_page_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    """解析一份培养计划原表格观察值，并在可能时独立核算。

    参数
    ----
    observation: ``degree-table-observation`` 契约对象（见模块 docstring）。
        函数不修改输入。

    返回
    ----
    dict，包含（节选）：

    * ``modules`` / ``courses``：页面原值报告，保留 ``raw_cells`` 与
      ``evidence.locator``；模块含可读 ``name``、``required_credits``、
      ``page_earned_credits``、``gap_text`` / ``gap_credits`` /
      ``gap_course_count``、``requirement``。
    * ``in_progress_courses`` / ``unclassified_rows`` / ``pending_verification``。
    * ``snapshot_status`` / ``snapshot`` / ``snapshot_error``：只有在模块层级
      有明确编号证据时才构造快照；否则 ``snapshot`` 为 ``None``，不补演示。
    * ``page_progress``：``analyze_page_progress`` 的结果，失败时为 ``None``。
    * ``can_decide_complete``：仅当独立核算确实给出完成结论时为 ``True``；
      未知版本 / 未知覆盖 / 任何未知结构都会使其为 ``False``。

    异常
    ----
    ``PageObservationValidationError``：``code`` 稳定，取值包括
    ``invalid_observation`` / ``unknown_field`` / ``invalid_kind`` /
    ``invalid_source`` / ``unsupported_source_url`` / ``invalid_captured_at`` /
    ``unsupported_coverage`` / ``invalid_adapter_verified`` /
    ``adapter_verified_unsupported`` / ``invalid_headers`` /
    ``unsupported_headers`` / ``invalid_rows`` / ``invalid_cells`` /
    ``invalid_locator`` / ``too_many_rows`` / ``too_many_cells`` /
    ``cell_too_large`` / ``observation_too_large`` / ``identity_text_rejected``。
    """
    if not isinstance(observation, Mapping):
        _fail("invalid_observation", "observation 必须是对象")
    _reject_unknown_fields(observation, _TOP_LEVEL_FIELDS, context="observation")

    kind = observation.get("kind")
    if kind != KIND:
        _fail("invalid_kind", f"kind 必须是 {KIND!r}，得到 {kind!r}")

    source = observation.get("source")
    if not isinstance(source, Mapping):
        _fail("invalid_source", "source 必须是对象")
    _reject_unknown_fields(source, _SOURCE_FIELDS, context="source")

    url = _require_text(source.get("url"), code="unsupported_source_url", field="source.url")
    if url != CANONICAL_URL:
        _fail("unsupported_source_url", f"source.url 必须是 {CANONICAL_URL}，得到 {url!r}")

    captured_at = _parse_captured_at(source.get("captured_at"))

    coverage = _require_text(
        source.get("coverage"), code="unsupported_coverage", field="source.coverage"
    ).lower()
    if coverage not in _COVERAGE_VALUES:
        _fail(
            "unsupported_coverage",
            f"source.coverage 只能是 partial 或 unknown，得到 {coverage!r}",
        )

    adapter_verified = source.get("adapter_verified")
    if adapter_verified is not False:
        if adapter_verified is True:
            _fail("adapter_verified_unsupported", "adapter_verified 必须为 false：适配器尚未验证")
        _fail("invalid_adapter_verified", "adapter_verified 必须是布尔 false")

    headers = _validate_headers(observation.get("headers"))
    rows = _validate_rows(observation.get("rows"))
    _enforce_payload_size(headers, rows)
    _reject_identity(headers, rows)

    header_index = {name: index for index, name in enumerate(headers)}
    lead_span = 3 if "序号" in header_index else 2

    pending: list[dict[str, Any]] = []
    module_reports: list[dict[str, Any]] = []
    course_reports: list[dict[str, Any]] = []
    unclassified_rows: list[dict[str, Any]] = []
    row_kinds: list[tuple[str, int]] = []
    course_meta: dict[int, dict[str, Any]] = {}

    for row_index, row in enumerate(rows):
        cells = row["cells"]
        locator = row["locator"]
        binding = _row_binding(len(cells), len(headers), lead_span)

        def value(header: str, *, _cells: Sequence[str] = cells, _binding: str = binding) -> str:
            return _cell_for(_cells, header_index, header, _binding, lead_span)

        if binding == _FULL:
            code = value("课程序号")
            name = value("课程名称")
            if not code and not name:
                unclassified_rows.append(
                    {
                        "row_index": row_index,
                        "locator": locator,
                        "reason": "empty_row",
                        "raw_cells": list(cells),
                        "evidence": _evidence(locator, "unclassified", cells),
                    }
                )
                row_kinds.append(("unclassified", len(unclassified_rows) - 1))
                continue

            required_raw = value("要求学分")
            earned_raw = value("实修学分")
            grade_raw = value("成绩")
            pass_raw = value("是否通过")
            remark_raw = value("备注")
            required = _parse_credits(required_raw)
            earned = _parse_credits(earned_raw)
            state = _course_page_state(grade_raw, pass_raw, remark_raw)
            course_reports.append(
                {
                    "row_index": row_index,
                    "locator": locator,
                    "sequence": _text(value("序号")),
                    "code": code or None,
                    "name": name or None,
                    "required_credits": _fmt(required),
                    "page_earned_credits": _fmt(earned),
                    "grade": grade_raw or None,
                    "pass_text": pass_raw or None,
                    "remark": remark_raw or None,
                    "state": state,
                    "in_progress": state == "in_progress",
                    "module_row_index": None,
                    "module_locator": None,
                    "raw_cells": list(cells),
                    "evidence": _evidence(locator, "course", cells),
                }
            )
            course_meta[row_index] = {
                "required": required,
                "earned": earned,
                "remark": remark_raw,
            }
            row_kinds.append(("course", len(course_reports) - 1))
            continue

        if binding == _LEAD_SPAN:
            label = cells[0]
            marker = _module_marker(label)
            required_raw = value("要求学分")
            earned_raw = value("实修学分")
            grade_raw = value("成绩")
            pass_raw = value("是否通过")
            remark_raw = value("备注")
            rule_text_source = " ".join(part for part in (label, grade_raw, pass_raw, remark_raw) if part)
            requirement, rule_token = _requirement_rule(rule_text_source)
            gap = _gap_text(pass_raw, remark_raw)
            has_page_values = _parse_credits(required_raw) is not None or _parse_credits(earned_raw) is not None or _normalize_flag(pass_raw) is not None
            if marker is None or (requirement == "unknown" and gap is None and not has_page_values):
                reason = (
                    "module_marker_without_rule_or_gap"
                    if marker is not None
                    else "unclassified_leading_span_row"
                )
                unclassified_rows.append(
                    {
                        "row_index": row_index,
                        "locator": locator,
                        "reason": reason,
                        "raw_cells": list(cells),
                        "evidence": _evidence(locator, "unclassified", cells),
                    }
                )
                row_kinds.append(("unclassified", len(unclassified_rows) - 1))
                continue

            required = _parse_credits(required_raw)
            earned = _parse_credits(earned_raw)
            gap_credits, gap_count = _parse_gap(gap)
            module_reports.append(
                {
                    "row_index": row_index,
                    "locator": locator,
                    "label": label,
                    "module_number": marker["raw"] if marker else None,
                    "number_kind": marker["kind"] if marker else None,
                    "numerical_id": marker["numerical_id"] if marker else None,
                    "name": _module_name(label, marker["end"]) if marker else (_text(label) or None),
                    "required_credits": _fmt(required),
                    "page_earned_credits": _fmt(earned),
                    "grade": grade_raw or None,
                    "pass_text": pass_raw or None,
                    "gap_text": gap,
                    "gap_credits": _fmt(gap_credits),
                    "gap_course_count": gap_count,
                    "remark": remark_raw or None,
                    "requirement": requirement,
                    "requirement_rule_text": rule_token,
                    "reported_satisfied": _module_reported_satisfied(pass_raw, remark_raw, gap),
                    "raw_cells": list(cells),
                    "evidence": _evidence(locator, "module", cells),
                }
            )
            row_kinds.append(("module", len(module_reports) - 1))
            continue

        unclassified_rows.append(
            {
                "row_index": row_index,
                "locator": locator,
                "reason": "unsupported_row_shape",
                "raw_cells": list(cells),
                "evidence": _evidence(locator, "unclassified", cells),
            }
        )
        row_kinds.append(("unclassified", len(unclassified_rows) - 1))

    # 缺口 / 未识别学分 / 未识别结构：全部进入待核实。
    for row in unclassified_rows:
        pending.append(
            _pending(
                row["reason"],
                f"{row['locator']} 无法归类为课程行或模块行，保留原值待核实",
                locator=row["locator"],
                row_index=row["row_index"],
            )
        )
    for course in course_reports:
        meta = course_meta.get(course["row_index"], {})
        if meta.get("earned") is None and meta.get("required") is None:
            pending.append(
                _pending(
                    "course_credits_unknown",
                    f"{course['locator']} 缺少可解析学分，不进入独立核算",
                    locator=course["locator"],
                    row_index=course["row_index"],
                )
            )
    from app.domains.degree.page_hierarchy import infer_degree_hierarchy, PROFILE_CHINESE_CHAPTERED
    hierarchy = infer_degree_hierarchy(module_reports)
    chaptered = hierarchy["profile"] == PROFILE_CHINESE_CHAPTERED
    if chaptered:
        for entry in hierarchy["pending"]:
            pending.append(_pending(entry["code"], entry["detail"], locator=entry["locator"]))
    by_row = {module["row_index"]: module for module in module_reports}
    for module in module_reports:
        parent_row = hierarchy["parent_by_row"].get(module["row_index"]) if hierarchy["known"] else None
        module["parent_locator"] = by_row[parent_row]["locator"] if parent_row is not None else None
        module["hierarchy_basis"] = "chapter_numbering" if hierarchy["known"] else "unverified"
        if module["number_kind"] == "chinese" and not hierarchy["known"]:
            pending.append(
                _pending(
                    "module_hierarchy_unknown",
                    f"{module['locator']} 使用中文编号 {module['module_number']!r}，"
                    "层级无法完全确定，不建立父子关系",
                    locator=module["locator"],
                    row_index=module["row_index"],
                )
            )

    # 课程按文档顺序归入最近的模块；只用于快照分组，不据此推断模块父子。
    module_by_row = {module["row_index"]: module for module in module_reports}
    current_module_row: int | None = None
    for kind_tag, ref in row_kinds:
        if kind_tag == "module":
            current_module_row = module_reports[ref]["row_index"]
        elif kind_tag == "unclassified":
            # An unrecognized section may start a different module. Never
            # carry the preceding module across this unresolved boundary.
            current_module_row = None
        elif kind_tag == "course":
            course = course_reports[ref]
            course["module_row_index"] = current_module_row
            if current_module_row is not None:
                course["module_locator"] = module_by_row[current_module_row]["locator"]
            elif module_reports:
                pending.append(
                    _pending(
                        "course_without_module",
                        f"{course['locator']} 之前没有模块行，无法归入任何模块",
                        locator=course["locator"],
                        row_index=course["row_index"],
                    )
                )

    snapshot_ok, snapshot_reasons = _plan_snapshot(module_reports)
    if chaptered:
        snapshot_ok = hierarchy["known"]
        snapshot_reasons = [] if snapshot_ok else ["module_hierarchy_unknown"]
    snapshot: dict[str, Any] | None = None
    page_progress: dict[str, Any] | None = None
    snapshot_error: dict[str, Any] | None = None
    snapshot_status = "not_built"

    if snapshot_ok:
        snapshot = _assemble_snapshot(
            url=url,
            captured_at=captured_at,
            coverage=coverage,
            course_reports=course_reports,
            module_reports=module_reports,
            course_meta=course_meta,
            hierarchy=hierarchy if chaptered and hierarchy["known"] else None,
        )
        try:
            page_progress = analyze_page_progress(snapshot)
            snapshot_status = "built"
        except PageProgressValidationError as exc:
            snapshot = None
            page_progress = None
            snapshot_status = "error"
            snapshot_error = {"code": exc.code, "detail": exc.detail}
            pending.append(
                _pending(
                    "snapshot_analysis_failed",
                    f"独立核算失败（{exc.code}），不补演示数据",
                )
            )
    else:
        for reason in snapshot_reasons:
            pending.append(
                _pending(
                    reason,
                    "模块层级缺少明确编号证据，未构造独立核算快照",
                )
            )

    in_progress_courses = [
        {
            "row_index": course["row_index"],
            "locator": course["locator"],
            "code": course["code"],
            "name": course["name"],
            "grade": course["grade"],
            "pass_text": course["pass_text"],
            "remark": course["remark"],
            "state": course["state"],
            "evidence": copy.deepcopy(course["evidence"]),
        }
        for course in course_reports
        if course["state"] == "in_progress"
    ]

    pending_sorted = _dedup_pending(pending)
    # parse_status 只描述页面结构是否被完全读懂；status 镜像独立核算的结论。
    parse_status = (
        "needs_verification"
        if pending_sorted or unclassified_rows or snapshot_status != "built"
        else "parsed"
    )
    status = page_progress["status"] if page_progress is not None else "needs_verification"

    return {
        "observation_version": OBSERVATION_VERSION,
        "kind": KIND,
        "source": {
            "url": url,
            "captured_at": captured_at,
            "coverage": coverage,
            "adapter_verified": False,
        },
        "headers": list(headers),
        "limits": {
            "max_bytes": MAX_OBSERVATION_BYTES,
            "max_rows": MAX_ROWS,
            "max_cells_per_row": MAX_CELLS_PER_ROW,
            "max_cell_chars": MAX_CELL_CHARS,
        },
        "status": status,
        "parse_status": parse_status,
        "can_decide_complete": bool(page_progress and page_progress["can_decide_complete"]),
        "reports": {
            "modules": module_reports,
            "courses": course_reports,
            "unclassified_rows": unclassified_rows,
            "in_progress_courses": in_progress_courses,
        },
        "modules": module_reports,
        "courses": course_reports,
        "in_progress_courses": in_progress_courses,
        "unclassified_rows": unclassified_rows,
        "pending_verification": pending_sorted,
        "snapshot_status": snapshot_status,
        "snapshot": snapshot,
        "snapshot_error": snapshot_error,
        "page_progress": page_progress,
        "not_graduation_decision": True,
        "adapter_verified": False,
    }

"""培养计划页面进度分析内核（第6模块）。

定位
----
``analyze_page_progress(snapshot)`` 是独立纯函数：只消费页面观察值快照，
不访问 HTTP / MCP / 数据库 / 身份，也不修改 ``audit_degree_progress`` 的
演示契约。本模块的输出是**内部观察值契约**，不是对外冻结接口；字段以
本文件为准。

快照形状（未知字段忽略，``evidence`` 原样保留）::

    {
      "plan_version": "anon-v1" | None,               # 兼容 "version"
      "source_coverage": "complete|partial|unknown",  # 兼容 "coverage"
      "missing_pages": ["p2"],
      "repeat_policy": "once_per_course" | None | "<其他>",
      "evidence": {...},
      "coverage_evidence": {...},
      "courses": [
        {"course_id": "c1", "code": "A1", "name": "匿名课程",
         "credits": "3.0",
         "state": "passed|in_progress|failed|unknown|pending_recognition",
         "evidence": {...}}
      ],
      "modules": [
        {"module_id": "m1", "name": "匿名模块", "parent_id": None,
         "requirement": "all|any|credits|required_courses|unknown",
         "required_credits": "3.0",           # 兼容 "min_credits"
         "reported_earned_credits": "3.0",    # 兼容 "earned_credits"
         "reported_remaining_credits": "0.0", # 兼容 "remaining_credits"
         "reported_satisfied": True,          # 兼容 "satisfied"
         "course_ids": ["c1"], "required_course_ids": ["c1"],
         "evidence": {...}}
      ]
    }

核算规则（保守，不编造默认政策）
--------------------------------
* 学分一律走 ``Decimal``；输入学分必须有限且非负，否则抛
  ``PageProgressValidationError``。
* 模块树必须恰好一个根、无环、无重复 id、parent 必须存在，否则拒绝。
* 只有 ``passed`` 且不存在待核实冲突的课程计入已获得学分；
  ``in_progress`` / ``failed`` / ``unknown`` / ``pending_recognition``
  一律不计入。
* 同一课程同时出现在父子模块时只归入最深的模块（同层多归属视为待核实），
  因此父子不会双计；上级用「子树去重学分」判断学分要求。
* ``any`` 规则只有在确实出现已通过课程或已完成子模块时才成立；0 学分且
  没有课程/子模块证据的节点返回未知，不会把 ``any`` 判成完成。
* 重复课程记录必须由明确的 ``repeat_policy`` 解释：``once_per_course``
  且学分一致时只计一次；学分冲突或缺政策时标待核实，绝不按输入顺序
  选择第一条。
* ``source_coverage != "complete"``、``plan_version`` 未知、存在任何待核实
  项或根模块结论未知时，``can_decide_complete`` 为 ``False``。
* 建议只指向模块 / 课程 / 证据，不推荐学期或开课信息。
"""

from __future__ import annotations

import copy
import math
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

CALCULATION_VERSION = "degree-page-v1"

_COURSE_STATES = ("passed", "in_progress", "failed", "unknown", "pending_recognition")
_REQUIREMENT_VALUES = ("all", "any", "credits", "required_courses", "unknown")
_COVERAGE_VALUES = ("complete", "partial", "unknown")
_UNKNOWN_TOKENS = {
    "",
    "unknown",
    "none",
    "null",
    "n/a",
    "na",
    "未知",
    "unverified",
    "unknown_version",
}
_REPEAT_ONCE = "once_per_course"
_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


class PageProgressValidationError(ValueError):
    """输入结构无法安全解析时抛出；``code`` 稳定，可用于断言。"""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _fail(code: str, detail: str) -> None:
    raise PageProgressValidationError(code, detail)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _as_sequence(value: Any, *, field: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray)) or isinstance(value, Mapping):
        _fail("invalid_structure", f"{field} 必须是列表，得到 {type(value).__name__}")
    if not isinstance(value, Sequence):
        _fail("invalid_structure", f"{field} 必须是列表，得到 {type(value).__name__}")
    return list(value)


def _string_list(value: Any, *, field: str, context: str) -> list[str]:
    if isinstance(value, str):
        items: list[Any] = [value]
    else:
        items = _as_sequence(value, field=f"{context}.{field}")
    result: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, str):
            _fail(
                "invalid_structure",
                f"{context}.{field}[{index}] 必须是字符串",
            )
        text = item.strip()
        if text:
            result.append(text)
    return result


def _decimal(value: Any, *, field: str, context: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        _fail("invalid_credits", f"{context}.{field} 缺少有限非负学分")
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, int):
        dec = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            _fail("invalid_credits", f"{context}.{field} 不是有限数值")
        dec = Decimal(str(value))
    elif isinstance(value, str):
        text = value.strip()
        if not _DECIMAL_RE.match(text):
            _fail("invalid_credits", f"{context}.{field} 不是合法十进制学分")
        dec = Decimal(text)
    else:
        _fail("invalid_credits", f"{context}.{field} 学分类型不受支持")
    if not dec.is_finite():
        _fail("invalid_credits", f"{context}.{field} 不是有限数值")
    if dec < 0:
        _fail("invalid_credits", f"{context}.{field} 学分不能为负")
    return dec


def _optional_decimal(value: Any, *, field: str, context: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return _decimal(value, field=field, context=context)


def _bool_or_none(value: Any, *, field: str, context: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    _fail("invalid_reported_satisfied", f"{context}.{field} 必须是布尔值或 null")


def _fmt(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _plan_version(snapshot: Mapping[str, Any]) -> tuple[str | None, bool]:
    raw = snapshot.get("plan_version", snapshot.get("version"))
    if raw is None:
        return None, False
    if not isinstance(raw, str):
        _fail("invalid_plan_version", "plan_version 必须是字符串或 null")
    text = raw.strip()
    if text.lower() in _UNKNOWN_TOKENS:
        return None, False
    return text, True


def _source_coverage(snapshot: Mapping[str, Any]) -> tuple[str, Any]:
    raw = snapshot.get("source_coverage")
    evidence = snapshot.get("coverage_evidence")
    if raw is None:
        raw = snapshot.get("coverage")
    if isinstance(raw, Mapping):
        if evidence is None:
            evidence = raw.get("evidence")
        raw = raw.get("source_coverage", raw.get("status"))
    text = _text(raw)
    if text is None:
        return "unknown", evidence
    lowered = text.lower()
    if lowered in _COVERAGE_VALUES:
        return lowered, evidence
    return "unknown", evidence


def _normalize_requirement(value: Any) -> tuple[str, bool]:
    text = _text(value)
    if text is None:
        return "unknown", False
    lowered = text.lower()
    if lowered in _REQUIREMENT_VALUES:
        return lowered, False
    return "unknown", True


def _pending(
    code: str,
    detail: str,
    *,
    module_id: str | None = None,
    course_id: str | None = None,
    evidence: Any = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "detail": detail,
        "module_id": module_id,
        "course_id": course_id,
        "evidence": copy.deepcopy(evidence),
    }


def _represent_state(states: set[str]) -> str:
    for candidate in ("passed", "in_progress", "pending_recognition", "unknown", "failed"):
        if candidate in states:
            return candidate
    return "unknown"


def _combine(states: Sequence[bool | None], *, mode: str) -> tuple[bool | None, str | None]:
    values = list(states)
    if not values:
        return None, "no_evidence"
    if mode == "any":
        if any(value is True for value in values):
            return True, None
        if any(value is None for value in values):
            return None, "undetermined"
        return False, None
    if any(value is False for value in values):
        return False, None
    if any(value is None for value in values):
        return None, "undetermined"
    return True, None


def _credits_requirement(
    required: Decimal | None,
    subtree_credits: Decimal,
    required_subset: set[str],
    truth: Any,
    *,
    has_scope: bool,
    has_children: bool,
) -> tuple[bool | None, str | None]:
    if required is None:
        return None, "required_credits_unknown"
    if required == 0 and not required_subset and not has_scope and not has_children:
        return None, "zero_requirement_no_evidence"
    required_truths = [truth(course_id) for course_id in sorted(required_subset)]
    if not required_truths:
        required_ok: bool | None = True
    elif any(value is False for value in required_truths):
        required_ok = False
    elif any(value is None for value in required_truths):
        required_ok = None
    else:
        required_ok = True
    if subtree_credits < required:
        return False, None
    if required_ok is True:
        return True, None
    if required_ok is False:
        return False, None
    return None, "undetermined"


def _normalize_courses(
    snapshot: Mapping[str, Any],
    repeat_policy: str | None,
    pending: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    raw_courses = _as_sequence(snapshot.get("courses"), field="courses")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for index, item in enumerate(raw_courses):
        if not isinstance(item, Mapping):
            _fail("invalid_courses", f"courses[{index}] 必须是对象")
        context = f"courses[{index}]"
        course_id = _text(item.get("course_id")) or _text(item.get("id"))
        if course_id is None:
            _fail("invalid_course_id", f"{context} 缺少 course_id")
        credits = _decimal(item.get("credits"), field="credits", context=context)
        raw_state = _text(item.get("state"))
        normalized_state = raw_state.lower() if raw_state is not None else "unknown"
        unrecognized_state = normalized_state not in _COURSE_STATES
        if unrecognized_state:
            normalized_state = "unknown"
        grouped.setdefault(course_id, []).append(
            {
                "course_id": course_id,
                "code": _text(item.get("code")),
                "name": _text(item.get("name")),
                "credits": credits,
                "state": normalized_state,
                "raw_state": raw_state,
                "unrecognized_state": unrecognized_state,
                "evidence": copy.deepcopy(item.get("evidence")),
            }
        )

    resolved: dict[str, dict[str, Any]] = {}
    for course_id in sorted(grouped):
        records = grouped[course_id]
        first = records[0]
        states = {record["state"] for record in records}
        credit_values = {record["credits"] for record in records}
        entry: dict[str, Any] = {
            "course_id": course_id,
            "code": first["code"],
            "name": first["name"],
            "credits": first["credits"] if len(credit_values) == 1 else None,
            "credit_candidates": None,
            "state": _represent_state(states),
            "counted": False,
            "verification_required": False,
            "verification_codes": [],
            "record_count": len(records),
            "observed_states": sorted(states),
            "evidence": first["evidence"],
        }
        if len(credit_values) > 1:
            entry["credit_candidates"] = sorted(str(value) for value in credit_values)

        reasons: list[tuple[str, str]] = []
        if any(record["unrecognized_state"] for record in records):
            raw_states = sorted(
                {str(record["raw_state"]) for record in records if record["unrecognized_state"]}
            )
            reasons.append(
                ("unrecognized_course_state", f"课程 {course_id} 出现未识别状态 {raw_states}")
            )
        if len(records) > 1:
            if repeat_policy is None:
                reasons.append(
                    (
                        "repeat_policy_missing",
                        f"课程 {course_id} 有 {len(records)} 条重复记录但缺少明确 repeat 政策，暂不核算",
                    )
                )
                if len(credit_values) > 1:
                    reasons.append(
                        (
                            "repeat_credits_conflict",
                            f"课程 {course_id} 重复记录学分不一致，不按输入顺序选择",
                        )
                    )
            elif repeat_policy != _REPEAT_ONCE:
                reasons.append(
                    (
                        "unsupported_repeat_policy",
                        f"重复修读政策 {repeat_policy!r} 不受支持，暂不核算",
                    )
                )
                if len(credit_values) > 1:
                    reasons.append(
                        (
                            "repeat_credits_conflict",
                            f"课程 {course_id} 重复记录学分不一致，不按输入顺序选择",
                        )
                    )
            elif len(credit_values) > 1:
                reasons.append(
                    (
                        "repeat_credits_conflict",
                        f"课程 {course_id} 重复记录学分不一致，不按输入顺序选择",
                    )
                )
            elif states & {"unknown", "pending_recognition"}:
                reasons.append(
                    (
                        "repeat_unrecognized_state",
                        f"课程 {course_id} 重复记录含未认定状态，暂不核算",
                    )
                )
        if entry["state"] in ("unknown", "pending_recognition"):
            reasons.append(
                (
                    "needs_recognition",
                    f"课程 {course_id} 状态为 {entry['state']}，未认定前不计入已获得学分",
                )
            )

        entry["verification_required"] = bool(reasons)
        entry["verification_codes"] = sorted({code for code, _ in reasons})
        entry["counted"] = entry["state"] == "passed" and not entry["verification_required"]
        for code, detail in reasons:
            pending.append(
                _pending(code, detail, course_id=course_id, evidence=first["evidence"])
            )
        resolved[course_id] = entry
    return resolved


def _normalize_modules(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_modules = _as_sequence(snapshot.get("modules"), field="modules")
    modules: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw_modules):
        if not isinstance(item, Mapping):
            _fail("invalid_modules", f"modules[{index}] 必须是对象")
        context = f"modules[{index}]"
        module_id = _text(item.get("module_id")) or _text(item.get("id"))
        if module_id is None:
            _fail("invalid_module_id", f"{context} 缺少 module_id")
        if module_id in seen_ids:
            _fail("duplicate_module_id", f"模块 id 重复: {module_id}")
        seen_ids.add(module_id)
        requirement, requirement_unrecognized = _normalize_requirement(
            item.get("requirement")
        )
        modules.append(
            {
                "module_id": module_id,
                "name": _text(item.get("name")),
                "parent_id": _text(item.get("parent_id")),
                "requirement": requirement,
                "requirement_unrecognized": requirement_unrecognized,
                "required_credits": _optional_decimal(
                    item.get("required_credits", item.get("min_credits")),
                    field="required_credits",
                    context=context,
                ),
                "reported_earned_credits": _optional_decimal(
                    item.get("reported_earned_credits", item.get("earned_credits")),
                    field="reported_earned_credits",
                    context=context,
                ),
                "reported_remaining_credits": _optional_decimal(
                    item.get("reported_remaining_credits", item.get("remaining_credits")),
                    field="reported_remaining_credits",
                    context=context,
                ),
                "reported_satisfied": _bool_or_none(
                    item.get("reported_satisfied", item.get("satisfied")),
                    field="reported_satisfied",
                    context=context,
                ),
                "course_ids": sorted(
                    set(_string_list(item.get("course_ids"), field="course_ids", context=context))
                ),
                "required_course_ids": sorted(
                    set(
                        _string_list(
                            item.get("required_course_ids"),
                            field="required_course_ids",
                            context=context,
                        )
                    )
                ),
                "evidence": copy.deepcopy(item.get("evidence")),
            }
        )
    return modules


def _validate_tree(modules: Sequence[Mapping[str, Any]]) -> None:
    by_id = {module["module_id"]: module for module in modules}
    for module in modules:
        parent_id = module["parent_id"]
        if parent_id is None:
            continue
        if parent_id == module["module_id"]:
            _fail("module_tree_cycle", f"模块 {module['module_id']} 的 parent_id 指向自身")
        if parent_id not in by_id:
            _fail(
                "unknown_parent",
                f"模块 {module['module_id']} 的 parent_id {parent_id} 不存在",
            )
    for module in modules:
        seen: set[str] = set()
        cursor: str | None = module["module_id"]
        while cursor is not None:
            if cursor in seen:
                _fail("module_tree_cycle", f"模块树存在环: {module['module_id']}")
            seen.add(cursor)
            cursor = by_id[cursor]["parent_id"]
    roots = sorted(module["module_id"] for module in modules if module["parent_id"] is None)
    if modules and len(roots) != 1:
        _fail("invalid_module_tree", f"模块树必须恰好一个根，得到 {len(roots)} 个: {roots}")


def _path(module_id: str, by_id: Mapping[str, Mapping[str, Any]]) -> list[str]:
    chain = [module_id]
    parent_id = by_id[module_id]["parent_id"]
    while parent_id is not None:
        chain.append(parent_id)
        parent_id = by_id[parent_id]["parent_id"]
    chain.reverse()
    return chain


def _depth(module_id: str, by_id: Mapping[str, Mapping[str, Any]]) -> int:
    return len(_path(module_id, by_id)) - 1


def _dedup_pending(items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = (
            item["code"],
            item["module_id"] or "",
            item["course_id"] or "",
            item["detail"],
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    result.sort(
        key=lambda item: (
            item["code"],
            item["module_id"] or "",
            item["course_id"] or "",
            item["detail"],
        )
    )
    return result


def _public_course(entry: Mapping[str, Any]) -> dict[str, Any]:
    course_id = entry["course_id"]
    return {
        "id": course_id,
        "course_id": course_id,
        "code": entry["code"],
        "name": entry["name"],
        "credits": _fmt(entry["credits"]),
        "credit_candidates": entry["credit_candidates"],
        "state": entry["state"],
        "counted": entry["counted"],
        "verification_required": entry["verification_required"],
        "verification_codes": list(entry["verification_codes"]),
        "record_count": entry["record_count"],
        "observed_states": list(entry["observed_states"]),
        "evidence": entry["evidence"],
    }


def analyze_page_progress(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """分析一份培养计划页面观察值快照。

    参数
    ----
    snapshot: 页面观察值映射（结构见模块 docstring）。函数不修改输入。

    返回
    ----
    dict，包含（节选）：

    * ``status`` / ``can_decide_complete``：整体结论；缺页、版本未知、
      存在待核实项或根模块未知时不会给出完成判断。
    * ``page_display`` 与 ``independent_calculation``：页面显示与独立核算分离。
    * ``modules[i].page`` / ``modules[i].calculation``：逐模块保留页面值
      与独立核算值；``discrepancies`` 列出不一致。
    * ``courses`` / ``passed_courses`` / ``in_progress_courses`` /
      ``missing_required_courses`` / ``pending_recognition_courses``：
      已通过、在读、缺必修、待核实分类。
    * ``pending_verification`` 与 ``suggestions``：待核实原因与建议
      （不含学期、开课信息）。

    异常
    ----
    ``PageProgressValidationError``：学分非有限/为负、模块树非法
    （重复 id、缺父、环、多根）、结构类型错误等。
    """
    if not isinstance(snapshot, Mapping):
        _fail("invalid_snapshot", "snapshot 必须是对象")

    pending: list[dict[str, Any]] = []

    plan_version, plan_version_known = _plan_version(snapshot)
    source_coverage, coverage_evidence = _source_coverage(snapshot)
    repeat_policy = _text(snapshot.get("repeat_policy"))
    if repeat_policy is not None:
        repeat_policy = repeat_policy.lower()
        if repeat_policy in _UNKNOWN_TOKENS:
            repeat_policy = None
    missing_pages = sorted(
        set(
            _string_list(
                snapshot.get("missing_pages"), field="missing_pages", context="snapshot"
            )
        )
    )

    courses = _normalize_courses(snapshot, repeat_policy, pending)
    modules = _normalize_modules(snapshot)
    _validate_tree(modules)

    if source_coverage != "complete":
        pending.append(
            _pending(
                "source_coverage_incomplete",
                f"页面来源覆盖为 {source_coverage}，缺少页面 {missing_pages or '未标注'}，"
                "不能据此给出整体完成结论",
                evidence=coverage_evidence,
            )
        )
    if not plan_version_known:
        pending.append(
            _pending("plan_version_unknown", "培养方案版本未知，不能给出整体完成判断")
        )
    if not modules:
        pending.append(_pending("no_modules", "页面未提供模块树，无法独立核算"))

    for module in modules:
        module_id = module["module_id"]
        if module["requirement_unrecognized"]:
            pending.append(
                _pending(
                    "unsupported_requirement_rule",
                    f"模块 {module_id} 的要求类型无法识别，按 unknown 处理",
                    module_id=module_id,
                    evidence=module["evidence"],
                )
            )
        elif module["requirement"] == "unknown":
            pending.append(
                _pending(
                    "unknown_requirement_rule",
                    f"模块 {module_id} 的要求类型为 unknown，无法判断是否完成",
                    module_id=module_id,
                    evidence=module["evidence"],
                )
            )
        scope = set(module["course_ids"]) | set(module["required_course_ids"])
        for course_id in sorted(scope):
            if course_id not in courses:
                pending.append(
                    _pending(
                        "unknown_course_reference",
                        f"模块 {module_id} 引用了没有课程证据的 {course_id}",
                        module_id=module_id,
                        course_id=course_id,
                        evidence=module["evidence"],
                    )
                )

    by_id = {module["module_id"]: module for module in modules}
    children_map: dict[str, list[str]] = {module["module_id"]: [] for module in modules}
    for module in modules:
        if module["parent_id"] is not None:
            children_map[module["parent_id"]].append(module["module_id"])
    for child_list in children_map.values():
        child_list.sort()

    depth = {module_id: _depth(module_id, by_id) for module_id in by_id}
    order = sorted(by_id, key=lambda module_id: (-depth[module_id], _path(module_id, by_id)))

    module_courses = {
        module["module_id"]: set(module["course_ids"]) | set(module["required_course_ids"])
        for module in modules
    }

    passed_ids = {course_id for course_id, entry in courses.items() if entry["counted"]}
    in_progress_ids = {
        course_id
        for course_id, entry in courses.items()
        if entry["state"] == "in_progress" and not entry["verification_required"]
    }
    failed_ids = {
        course_id
        for course_id, entry in courses.items()
        if entry["state"] == "failed" and not entry["verification_required"]
    }
    verification_ids = {
        course_id for course_id, entry in courses.items() if entry["verification_required"]
    }

    allocation: dict[str, str] = {}
    unallocated: list[str] = []
    for course_id in sorted(passed_ids):
        owners = [
            module_id
            for module_id, scope in module_courses.items()
            if course_id in scope
        ]
        if not owners:
            unallocated.append(course_id)
            pending.append(
                _pending(
                    "no_allocation_rule",
                    f"已通过课程 {course_id} 不属于任何模块候选范围，暂不计入模块学分",
                    course_id=course_id,
                    evidence=courses[course_id]["evidence"],
                )
            )
            continue
        best_depth = max(depth[module_id] for module_id in owners)
        deepest = sorted(module_id for module_id in owners if depth[module_id] == best_depth)
        if len(deepest) > 1:
            unallocated.append(course_id)
            pending.append(
                _pending(
                    "allocation_rule_missing",
                    f"已通过课程 {course_id} 同层归属多个模块 {deepest}，缺少明确规则，不重复计",
                    course_id=course_id,
                    evidence=courses[course_id]["evidence"],
                )
            )
            continue
        allocation[course_id] = deepest[0]

    def course_truth(course_id: str) -> bool | None:
        if course_id in passed_ids:
            return True
        if course_id in in_progress_ids:
            return None
        if course_id in failed_ids:
            return False
        return None

    results: dict[str, dict[str, Any]] = {}
    subtree_ids: dict[str, set[str]] = {}
    zero_evidence_modules: list[str] = []

    for module_id in order:
        module = by_id[module_id]
        children = children_map[module_id]
        child_states = [results[child]["calculation"]["satisfied"] for child in children]
        requirement = module["requirement"]
        required = module["required_credits"]
        scope = module_courses[module_id]
        explicit_required = set(module["required_course_ids"])
        if requirement == "all":
            required_subset = set(module["course_ids"]) | explicit_required
        elif requirement == "required_courses":
            required_subset = explicit_required or set(module["course_ids"])
        else:
            required_subset = explicit_required

        own_ids = sorted(
            course_id for course_id in passed_ids if allocation.get(course_id) == module_id
        )
        own_credits = sum(
            (courses[course_id]["credits"] for course_id in own_ids), Decimal("0")
        )
        subtree_ids_set = set(own_ids)
        for child in children:
            subtree_ids_set |= subtree_ids[child]
        subtree_credits = sum(
            (courses[course_id]["credits"] for course_id in sorted(subtree_ids_set)),
            Decimal("0"),
        )

        if requirement == "any":
            self_satisfied, self_reason = _combine(
                [course_truth(course_id) for course_id in sorted(scope)], mode="any"
            )
        elif requirement in ("all", "required_courses"):
            self_satisfied, self_reason = _combine(
                [course_truth(course_id) for course_id in sorted(required_subset)],
                mode="all",
            )
            if not required_subset and children:
                self_satisfied, self_reason = True, None
        elif requirement == "credits":
            self_satisfied, self_reason = _credits_requirement(
                required,
                subtree_credits,
                required_subset,
                course_truth,
                has_scope=bool(scope),
                has_children=bool(children),
            )
        elif requirement == "unknown":
            self_satisfied, self_reason = None, "unknown_rule"
        else:  # pragma: no cover - 归一化后不可达
            self_satisfied, self_reason = None, "unsupported_rule"

        mode = "any" if requirement == "any" else "all"
        satisfied, _satisfied_reason = _combine(
            [self_satisfied] + child_states, mode=mode
        )
        # Combination rules and a stated credit minimum are conjunctive.
        if requirement != "unknown" and required is not None and required > 0 and satisfied is not None:
            satisfied, _satisfied_reason = _combine(
                [satisfied, subtree_credits >= required], mode="all"
            )

        if (
            self_satisfied is None
            and not child_states
            and self_reason in ("no_evidence", "zero_requirement_no_evidence")
        ):
            zero_evidence_modules.append(module_id)
            pending.append(
                _pending(
                    "zero_requirement_no_evidence",
                    f"模块 {module_id} 没有课程或子模块证据，0/0 不足以判定完成",
                    module_id=module_id,
                    evidence=module["evidence"],
                )
            )
        if requirement == "credits" and required is None:
            pending.append(
                _pending(
                    "required_credits_unknown",
                    f"模块 {module_id} 缺少 required_credits，无法核算学分缺口",
                    module_id=module_id,
                    evidence=module["evidence"],
                )
            )

        if requirement in ("any", "unknown"):
            missing_required: list[str] = []
        else:
            missing_required = sorted(
                course_id for course_id in required_subset if course_id not in passed_ids
            )

        if required is None:
            remaining: Decimal | None = None
        else:
            remaining = required - subtree_credits
            if remaining < 0:
                remaining = Decimal("0")

        in_progress_in_scope = sorted(
            course_id for course_id in scope if course_id in in_progress_ids
        )
        pending_in_scope = sorted(
            course_id for course_id in scope if course_id in verification_ids
        )
        scope_unallocated = sorted(
            course_id
            for course_id in scope
            if course_id in passed_ids and course_id not in allocation
        )

        discrepancies: list[dict[str, Any]] = []
        page_earned = module["reported_earned_credits"]
        if page_earned is not None and page_earned != subtree_credits:
            discrepancies.append(
                {
                    "code": "page_earned_credits_mismatch",
                    "page": _fmt(page_earned),
                    "calculated_subtree": _fmt(subtree_credits),
                    "calculated_own": _fmt(own_credits),
                }
            )
        page_remaining = module["reported_remaining_credits"]
        if page_remaining is not None and remaining is not None and page_remaining != remaining:
            discrepancies.append(
                {
                    "code": "page_remaining_credits_mismatch",
                    "page": _fmt(page_remaining),
                    "calculated": _fmt(remaining),
                }
            )
        page_satisfied = module["reported_satisfied"]
        if page_satisfied is not None and satisfied is not None and page_satisfied != satisfied:
            discrepancies.append(
                {
                    "code": "page_satisfied_mismatch",
                    "page": page_satisfied,
                    "calculated": satisfied,
                }
            )
        comparable = any(
            value is not None
            for value in (page_earned, page_remaining, page_satisfied)
        )

        subtree_ids[module_id] = subtree_ids_set
        results[module_id] = {
            "module_id": module_id,
            "id": module_id,
            "name": module["name"],
            "parent_id": module["parent_id"],
            "requirement": requirement,
            "depth": depth[module_id],
            "path": _path(module_id, by_id),
            "required_credits": _fmt(required),
            "reported_earned_credits": _fmt(page_earned),
            "reported_remaining_credits": _fmt(page_remaining),
            "reported_satisfied": page_satisfied,
            "course_ids": list(module["course_ids"]),
            "required_course_ids": list(module["required_course_ids"]),
            "page": {
                "required_credits": _fmt(required),
                "earned_credits": _fmt(page_earned),
                "remaining_credits": _fmt(page_remaining),
                "satisfied": page_satisfied,
            },
            "calculation": {
                "required_credits": _fmt(required),
                "earned_credits": _fmt(own_credits),
                "subtree_earned_credits": _fmt(subtree_credits),
                "remaining_credits": _fmt(remaining),
                "satisfied": satisfied,
                "requirement_satisfied": self_satisfied,
                "children_satisfied": {
                    child: results[child]["calculation"]["satisfied"]
                    for child in children
                },
                "missing_required_course_ids": missing_required,
                "in_progress_course_ids": in_progress_in_scope,
                "pending_recognition_course_ids": pending_in_scope,
                "own_counted_course_ids": own_ids,
                "counted_course_ids": sorted(subtree_ids_set),
                "unallocated_course_ids": scope_unallocated,
            },
            "page_vs_calculation": {
                "comparable": comparable,
                "agrees": (not discrepancies) if comparable else None,
                "discrepancy_codes": [item["code"] for item in discrepancies],
            },
            "discrepancies": discrepancies,
            "evidence": module["evidence"],
        }

    allocated_passed = sorted(
        course_id for course_id in passed_ids if course_id in allocation
    )
    total_counted = sum(
        (courses[course_id]["credits"] for course_id in allocated_passed), Decimal("0")
    )

    root_ids = sorted(
        module["module_id"] for module in modules if module["parent_id"] is None
    )
    root_id = root_ids[0] if len(root_ids) == 1 else None
    root_satisfied = results[root_id]["calculation"]["satisfied"] if root_id else None
    root_page_satisfied = by_id[root_id]["reported_satisfied"] if root_id else None

    pending_sorted = _dedup_pending(pending)

    if (
        not modules
        or source_coverage != "complete"
        or not plan_version_known
        or pending_sorted
        or root_satisfied is None
    ):
        status = "needs_verification"
    elif root_satisfied is False:
        status = "incomplete"
    else:
        status = "complete_under_supported_rules"
    can_decide_complete = status == "complete_under_supported_rules"

    passed_courses: list[dict[str, Any]] = []
    for course_id in sorted(passed_ids):
        entry = courses[course_id]
        passed_courses.append(
            {
                "course_id": course_id,
                "id": course_id,
                "code": entry["code"],
                "name": entry["name"],
                "credits": _fmt(entry["credits"]),
                "module_id": allocation.get(course_id),
                "evidence": entry["evidence"],
            }
        )

    in_progress_courses: list[dict[str, Any]] = []
    for course_id in sorted(in_progress_ids):
        entry = courses[course_id]
        in_progress_courses.append(
            {
                "course_id": course_id,
                "id": course_id,
                "code": entry["code"],
                "name": entry["name"],
                "credits": _fmt(entry["credits"]),
                "evidence": entry["evidence"],
            }
        )

    missing_required_entries: list[dict[str, Any]] = []
    for module_id in sorted(results):
        module = by_id[module_id]
        for course_id in results[module_id]["calculation"]["missing_required_course_ids"]:
            entry = courses.get(course_id)
            missing_required_entries.append(
                {
                    "module_id": module_id,
                    "course_id": course_id,
                    "code": entry["code"] if entry else None,
                    "name": entry["name"] if entry else None,
                    "evidence": entry["evidence"] if entry else module["evidence"],
                }
            )

    pending_recognition_courses: list[dict[str, Any]] = []
    for course_id in sorted(verification_ids):
        entry = courses[course_id]
        pending_recognition_courses.append(
            {
                "course_id": course_id,
                "id": course_id,
                "code": entry["code"],
                "name": entry["name"],
                "state": entry["state"],
                "counted": entry["counted"],
                "verification_codes": list(entry["verification_codes"]),
                "evidence": entry["evidence"],
            }
        )

    suggestions: list[dict[str, Any]] = []
    for module_id in sorted(results):
        module = by_id[module_id]
        for course_id in results[module_id]["calculation"]["missing_required_course_ids"]:
            entry = courses.get(course_id)
            suggestions.append(
                {
                    "code": "complete_missing_required_course",
                    "message": (
                        f"模块 {module['name'] or module_id} 的必修课程 {course_id} 尚未通过，"
                        "需补齐后再核对"
                    ),
                    "module_id": module_id,
                    "course_ids": [course_id],
                    "evidence": entry["evidence"] if entry else module["evidence"],
                }
            )
    for course_id in sorted(in_progress_ids):
        suggestions.append(
            {
                "code": "track_in_progress_course",
                "message": f"课程 {course_id} 仍在读，独立核算未计入已获得学分",
                "module_id": None,
                "course_ids": [course_id],
                "evidence": courses[course_id]["evidence"],
            }
        )
    for course_id in sorted(verification_ids):
        entry = courses[course_id]
        suggestions.append(
            {
                "code": "confirm_course_recognition",
                "message": (
                    f"课程 {course_id} 记录需核实（{'/'.join(entry['verification_codes'])}），"
                    "核实前不计入"
                ),
                "module_id": None,
                "course_ids": [course_id],
                "evidence": entry["evidence"],
            }
        )
    for course_id in sorted(set(unallocated)):
        suggestions.append(
            {
                "code": "confirm_course_allocation",
                "message": (
                    f"已通过课程 {course_id} 缺少明确的模块归属规则，暂不计入模块学分"
                ),
                "module_id": None,
                "course_ids": [course_id],
                "evidence": courses[course_id]["evidence"],
            }
        )
    for module_id in sorted(zero_evidence_modules):
        suggestions.append(
            {
                "code": "clarify_module_requirement",
                "message": (
                    f"模块 {module_id} 没有课程或子模块证据，需要补充页面信息才能判断完成情况"
                ),
                "module_id": module_id,
                "course_ids": [],
                "evidence": by_id[module_id]["evidence"],
            }
        )
    for module_id in sorted(
        module_id for module_id, item in results.items() if item["discrepancies"]
    ):
        suggestions.append(
            {
                "code": "verify_page_display",
                "message": f"模块 {module_id} 页面显示与独立核算不一致，请核对页面来源",
                "module_id": module_id,
                "course_ids": [],
                "evidence": by_id[module_id]["evidence"],
            }
        )
    if source_coverage != "complete":
        suggestions.append(
            {
                "code": "obtain_missing_pages",
                "message": (
                    f"页面覆盖不完整（{source_coverage}），补全页面后才能给出整体完成结论"
                ),
                "module_id": None,
                "course_ids": [],
                "evidence": coverage_evidence,
            }
        )
    if not plan_version_known:
        suggestions.append(
            {
                "code": "confirm_plan_version",
                "message": "培养方案版本未知，需确认版本后再判断完成情况",
                "module_id": None,
                "course_ids": [],
                "evidence": None,
            }
        )
    suggestions.sort(
        key=lambda item: (item["code"], item["module_id"] or "", tuple(item["course_ids"]))
    )

    return {
        "calculation_version": CALCULATION_VERSION,
        "status": status,
        "can_decide_complete": can_decide_complete,
        "plan_version": plan_version,
        "plan_version_known": plan_version_known,
        "source_coverage": source_coverage,
        "coverage_evidence": copy.deepcopy(coverage_evidence),
        "missing_pages": missing_pages,
        "repeat_policy": repeat_policy,
        "page_display": {
            "root_module_id": root_id,
            "root_satisfied": root_page_satisfied,
            "modules_with_page_values": sorted(
                module["module_id"]
                for module in modules
                if module["reported_earned_credits"] is not None
                or module["reported_remaining_credits"] is not None
                or module["reported_satisfied"] is not None
            ),
        },
        "independent_calculation": {
            "root_module_id": root_id,
            "root_satisfied": root_satisfied,
            "counted_course_count": len(allocated_passed),
            "counted_credits": _fmt(total_counted),
            "calculation_version": CALCULATION_VERSION,
            "not_graduation_decision": True,
        },
        "modules": [results[module_id] for module_id in order],
        "courses": [_public_course(courses[course_id]) for course_id in sorted(courses)],
        "passed_courses": passed_courses,
        "in_progress_courses": in_progress_courses,
        "missing_required_courses": missing_required_entries,
        "pending_recognition_courses": pending_recognition_courses,
        "pending_verification": pending_sorted,
        "suggestions": suggestions,
        "unallocated_courses": sorted(set(unallocated)),
        "evidence": copy.deepcopy(snapshot.get("evidence")),
        "not_graduation_decision": True,
    }

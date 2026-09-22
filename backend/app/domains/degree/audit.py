"""培养方案进度审计纯函数（C07）。

`audit_degree_progress(plan, records)` 不处理 HTTP、MCP、数据库或身份；
D 的薄适配层负责把 `transcript_ref` 解析为已授权的 records 后调用本函数。

首版仅支持：指定必修集合 + 模块最少学分 + 明确 allocation_priority 的
跨模块归属 + 有正式依据的 repeat_policy 去重。其余规则一律返回
needs_policy / unresolved_rules，不编造默认政策。

输出语义：所选规则下的学习进度，不是学校毕业资格结论。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Sequence

CALCULATION_VERSION = "degree-v1"

_STATUS_COMPLETE = "complete_under_supported_rules"
_STATUS_INCOMPLETE = "incomplete"
_STATUS_NEEDS_POLICY = "needs_policy"

_PASSED = "passed"
_NON_FINISHED = {"failed", "in_progress", "unknown"}


def _credits(value: Any) -> Decimal:
    """学分统一走 Decimal，不使用二进制浮点。"""
    return Decimal(str(value))


def _fmt(value: Decimal) -> str:
    return str(value)


def audit_degree_progress(
    plan: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """按 DegreePlan 规则审计 records，返回契约 §6 的统一结果结构。

    plan: 已解析的 DegreePlan 字典（含 modules/repeat_policy/status 等）。
    records: 已授权的成绩记录列表（attempt_id/course_id/credits/result）。
    """
    modules: list[Mapping[str, Any]] = list(plan.get("modules", []))
    repeat_policy = plan.get("repeat_policy")
    unresolved: list[str] = []

    # 1. 校验计划/规则来源状态。版本或来源未核验时不硬算。
    if plan.get("status") not in ("demo", "official_verified"):
        unresolved.append(
            "plan_source_needs_verification: 培养方案来源或版本未核验，拒绝硬算"
        )
    if not modules:
        unresolved.append("no_modules: 培养方案缺少模块归属规则")

    # 模块候选范围：required ∪ eligible；priority 缺失时记录。
    module_scopes: list[tuple[Mapping[str, Any], set[str], Any]] = []
    for module in modules:
        scope = set(module.get("required_course_ids", [])) | set(
            module.get("eligible_course_ids", [])
        )
        priority = module.get("allocation_priority")
        module_scopes.append((module, scope, priority))

    # 2. 规范记录：仅 passed 计入完成候选；failed/in_progress/unknown 排除。
    passed_attempts: list[Mapping[str, Any]] = []
    # course_id -> 排除原因，按模块归属时填入模块 excluded_attempts
    excluded_by_course: dict[str, list[tuple[str, str]]] = {}
    for record in records:
        attempt_id = str(record.get("attempt_id"))
        course_id = str(record.get("course_id"))
        result = record.get("result")
        if result == _PASSED:
            passed_attempts.append(record)
        elif result in _NON_FINISHED:
            excluded_by_course.setdefault(course_id, []).append(
                (attempt_id, f"result_{result}")
            )
        else:
            excluded_by_course.setdefault(course_id, []).append(
                (attempt_id, "result_unrecognized")
            )
            unresolved.append(
                f"unrecognized_result:{attempt_id}: 未识别的成绩状态，不计入完成"
            )

    # 3. 依据明确 repeat_policy 去重；无政策且出现重复时停止该课程核算。
    counted_by_course: dict[str, Mapping[str, Any]] = {}
    duplicates_suspended: set[str] = set()
    for record in passed_attempts:
        course_id = str(record.get("course_id"))
        attempt_id = str(record.get("attempt_id"))
        if course_id in counted_by_course:
            if repeat_policy == "once_per_course":
                excluded_by_course.setdefault(course_id, []).append(
                    (attempt_id, "duplicate_once_per_course")
                )
                continue
            if repeat_policy is None:
                duplicates_suspended.add(course_id)
                continue
            unresolved.append(
                f"unsupported_repeat_policy:{repeat_policy}: 不支持的重复修读规则"
            )
            excluded_by_course.setdefault(course_id, []).append(
                (attempt_id, "unsupported_repeat_policy")
            )
            continue
        counted_by_course[course_id] = record
    for course_id in sorted(duplicates_suspended):
        first = counted_by_course[course_id]
        excluded_by_course.setdefault(course_id, []).append(
            (str(first.get("attempt_id")), "repeat_policy_missing")
        )
        del counted_by_course[course_id]
        unresolved.append(
            f"repeat_policy_missing:{course_id}: 存在重复通过记录但未提供去重规则，"
            "该课程暂不核算"
        )

    # 4. 分配课程到模块：只按候选范围和 allocation_priority；同分只计一次。
    allocated: dict[str, str] = {}  # course_id -> module_id
    unallocated: list[str] = []
    for course_id in sorted(counted_by_course):
        candidates = [
            (module, priority)
            for module, scope, priority in module_scopes
            if course_id in scope
        ]
        if not candidates:
            unallocated.append(course_id)
            unresolved.append(
                f"no_allocation_rule:{course_id}: 已通过但不在任何模块候选范围，"
                "可能是未知替代课程，保留待规则确认"
            )
            continue
        if len(candidates) == 1:
            allocated[course_id] = str(candidates[0][0].get("module_id"))
            continue
        priorities = [p for _, p in candidates]
        if any(p is None for p in priorities) or len(set(priorities)) != len(
            priorities
        ):
            unallocated.append(course_id)
            unresolved.append(
                f"allocation_rule_missing:{course_id}: 可计入多个模块且无明确"
                "归属优先级，不重复计"
            )
            continue
        best = min(candidates, key=lambda item: item[1])
        allocated[course_id] = str(best[0].get("module_id"))

    # 5. Decimal 计算每模块学分，列出未完成必修；两者独立。
    result_modules: list[dict[str, Any]] = []
    total_earned = Decimal("0")
    total_remaining = Decimal("0")
    any_gap = False
    for module, scope, _priority in module_scopes:
        module_id = str(module.get("module_id"))
        earned = Decimal("0")
        counted_attempts: list[str] = []
        excluded_attempts: list[str] = []
        counted_courses: set[str] = set()
        for course_id in sorted(counted_by_course):
            if allocated.get(course_id) != module_id:
                continue
            earned += _credits(counted_by_course[course_id].get("credits"))
            counted_attempts.append(str(counted_by_course[course_id].get("attempt_id")))
            counted_courses.add(course_id)
        for course_id in sorted(excluded_by_course):
            if course_id not in scope:
                continue
            for attempt_id, _reason in excluded_by_course[course_id]:
                excluded_attempts.append(attempt_id)
        required = _credits(module.get("min_credits"))
        remaining = required - earned
        if remaining < 0:
            remaining = Decimal("0")
        missing_required = [
            course_id
            for course_id in module.get("required_course_ids", [])
            if course_id not in counted_courses
        ]
        if remaining > 0 or missing_required:
            any_gap = True
        total_earned += earned
        total_remaining += remaining
        result_modules.append(
            {
                "module_id": module_id,
                "earned_credits": _fmt(earned),
                "required_credits": _fmt(required),
                "remaining_credits": _fmt(remaining),
                "missing_required_courses": list(missing_required),
                "counted_attempts": counted_attempts,
                "excluded_attempts": excluded_attempts,
            }
        )

    # 6/7. 状态判定与覆盖说明；结果不表述为“保证毕业”。
    if unresolved:
        status = _STATUS_NEEDS_POLICY
    elif any_gap:
        status = _STATUS_INCOMPLETE
    else:
        status = _STATUS_COMPLETE

    return {
        "plan_id": str(plan.get("plan_id")),
        "plan_version": str(plan.get("version")),
        "source_ref": str(plan.get("source_ref")),
        "modules": result_modules,
        "unallocated_courses": unallocated,
        "unresolved_rules": unresolved,
        "data_coverage": {
            "dataset_kind": plan.get("dataset_kind"),
            "transcript_records": len(records),
            "counted_attempts": sum(
                len(m["counted_attempts"]) for m in result_modules
            ),
            "excluded_attempts": sum(
                len(m["excluded_attempts"]) for m in result_modules
            ),
            "unallocated_courses": len(unallocated),
            "total_earned_credits": _fmt(total_earned),
            "total_remaining_credits": _fmt(total_remaining),
            "calculation_version": CALCULATION_VERSION,
            "not_graduation_decision": True,
            "note": "仅基于提供的记录和已支持规则的学习进度，不替代学校审核",
        },
        "status": status,
    }

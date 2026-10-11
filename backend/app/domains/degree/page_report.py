"""Evidence-backed display and priorities for validated page observations."""
from collections import Counter
from decimal import Decimal
import re

from app.domains.degree.page_observation import analyze_page_observation


def analyze_page_report(observation):
    result = analyze_page_observation(observation)
    courses = result["courses"]
    repeats = Counter(course["code"] for course in courses if course["code"])
    progress = result["page_progress"]
    calculations = {item["evidence"]["locator"]: item for item in progress["modules"]} if progress else {}
    progress_courses = {course["course_id"]: course for course in progress["courses"]} if progress else {}
    modules_by_id = {item["module_id"]: item for item in progress["modules"]} if progress else {}
    if progress:
        result["pending_verification"] += progress["pending_verification"]
    substitutions = {"pending_recognition": "待认定", "in_progress": "在读", "unknown": "未知", "required_credits": "要求学分"}
    identifiers = {key: value["name"] or key for key, value in modules_by_id.items()}
    identifiers.update({key: value["name"] or value["code"] or key for key, value in progress_courses.items()})
    pending_display = []
    for item in result["pending_verification"]:
        detail = item["detail"]
        for raw, readable in substitutions.items():
            detail = detail.replace(raw, readable)
        for key in sorted(identifiers, key=len, reverse=True):
            detail = re.sub(r"(?<![\w-])" + re.escape(key) + r"(?![\w-])", lambda match, key=key: identifiers[key], detail)
        pending_display.append({**item, "detail": detail, "raw_detail": item["detail"]})
    result["pending_verification"] = pending_display
    priorities = []
    summaries = []
    report_modules = {module["locator"]: module for module in result["modules"]}
    for module in result["modules"]:
        direct = [course for course in courses if course["module_locator"] == module["locator"]]
        passed = [course for course in direct if course["state"] == "passed"]
        reading = [course for course in direct if course["state"] == "in_progress"]
        missing = [course for course in direct if re.search(r"(?<!非)必修", course["remark"] or "")
                   and course["state"] != "passed"]
        category_path = []
        ancestor = module
        while ancestor:
            category_path.append(ancestor)
            ancestor = report_modules.get(ancestor.get("parent_locator"))
        required_category = any(re.match(r"^(专业|通识)必修课(?:$|[（(])", item["name"] or "") for item in category_path)
        choice_branch = any(re.search(r"选修|任选|多选一|非必须|至少一项", item["label"]) for item in category_path)
        optional_branch = any(re.search(r"非必须选择|非必选|非必修|不必选择|无需选择", item["label"]) for item in category_path)
        category_missing = [course for course in direct if course["state"] != "passed"] if required_category and not choice_branch else []
        uncertain = [course for course in direct if course["state"] in {"unknown", "pending_recognition"}]
        duplicate = any(repeats[course["code"]] > 1 for course in direct if course["code"])
        def credits(records, field):
            if duplicate or any(course[field] is None for course in records):
                return None
            return str(sum((Decimal(course[field]) for course in records), Decimal("0")))
        calculated = calculations.get(module["locator"])
        calculation = calculated["calculation"] if calculated else None
        passed_credits = credits(passed, "page_earned_credits")
        reading_credits = credits(reading, "required_credits")
        if calculation and not duplicate:
            passed_credits = calculation["subtree_earned_credits"]
            reading_ids = set()
            for candidate in modules_by_id.values():
                ancestor = candidate
                while ancestor:
                    if ancestor["module_id"] == calculated["module_id"]:
                        reading_ids.update(candidate["calculation"]["in_progress_course_ids"])
                        break
                    ancestor = modules_by_id.get(ancestor["parent_id"])
            scoped_reading = [progress_courses[course_id] for course_id in sorted(reading_ids)]
            reading_credits = None if any(course["verification_required"] for course in scoped_reading) else str(sum((Decimal(course["credits"]) for course in scoped_reading), Decimal("0")))
            passed_names = [progress_courses[course_id]["name"] or progress_courses[course_id]["code"] for course_id in calculation["counted_course_ids"]]
            reading_names = [course["name"] or course["code"] for course in scoped_reading]
        else:
            passed_names = [course["name"] or course["code"] for course in passed]
            reading_names = [course["name"] or course["code"] for course in reading]
        discrepancies = calculated["discrepancies"] if calculated else []
        if missing:
            names = "、".join(course["name"] or course["code"] or "未命名课程" for course in missing)
            action = f"优先核对必修：{names}；在读课程先跟进成绩，待认定课程先核实认定"
            priority = 1
        elif optional_branch:
            action = "页面注明此分支可选；显示缺口不代表必须补修本组，需核对所属模块总学分与组合要求"
            priority = 3
        elif category_missing:
            names = "、".join(course["name"] or course["code"] or "未命名课程" for course in category_missing)
            action = f"必修模块中尚未通过：{names}；先跟进在读与认定，再核对补修或替代要求"
            priority = 1
        elif module["gap_credits"] is not None and Decimal(module["gap_credits"]) > 0:
            action = f"教务显示仍缺{module['gap_credits']}学分；核对在读及模块选修条件后补修"
            priority = 2
        elif module["gap_course_count"]:
            action = f"教务显示仍缺{module['gap_course_count']}门；核对课程要求后补修"
            priority = 2
        else:
            action = "核对必修、子模块组合条件和认定规则；未显示缺口不等于已经完成"
            priority = 3
        if duplicate:
            action = "先核实重复课程及重修计分规则，再决定补修"
            priority = 0
        summary = {
            "locator": module["locator"], "name": (module["name"] or module["label"]).strip(),
            "observed_passed_credits": passed_credits,
            "observed_in_progress_credits": reading_credits,
            "passed_course_names": passed_names,
            "in_progress_course_names": reading_names,
            "statistics_scope": "已识别模块及有明确层级的子模块；覆盖和规则仍待核实" if calculation else "仅当前识别到的直接课程；不含未知子模块或未读取记录",
            "missing_required_courses": [{"name": c["name"], "code": c["code"], "state": c["state"], "evidence": c["evidence"]} for c in missing],
            "required_category_pending_courses": [{"name": c["name"], "code": c["code"], "state": c["state"], "evidence": c["evidence"],
                "category_evidence": [item["evidence"] for item in category_path]} for c in category_missing],
            "required_course_coverage": "仅页面明确标记必修的记录，其他要求仍待核实",
            "pending_courses": [{"name": c["name"], "code": c["code"], "state": c["state"]} for c in uncertain],
            "duplicate_records": duplicate, "calculation": calculation,
            "discrepancies": discrepancies, "next_step": action,
            "optional_branch": optional_branch,
            "evidence": module["evidence"],
        }
        summaries.append(summary)
        if priority < 3:
            priorities.append({"priority": priority, "module_name": summary["name"], "message": action,
                               "evidence": module["evidence"]})
    priorities.sort(key=lambda item: item["priority"])
    result["module_summaries"] = summaries
    result["priority_suggestions"] = priorities
    result["recommendation_limits"] = [
        "方案版本及页面覆盖尚未核实，不能判断整体完成。",
        "父子模块缺口不能简单相加；教务实修可能包含在读。",
        "缺少开课、先修和选课条件依据，不推荐具体课程或学期。",
        "替代、互斥、重修及认定须有学校规则依据，未知规则待核实。",
    ]
    return result

import { describe, expect, it } from "vitest";
import { degreeProgressForQuestions, degreeProgressForStorage, isGeneralElectiveModule, GENERAL_ELECTIVE_POLICY } from "../src/degree-progress";
import type { DegreePlanImport, DegreePlanModule } from "../src/degree";
const module = (title: string, required = "14", actual = "10"): DegreePlanModule => ({
  kind: "module", title, required_credits: required, actual_credits: actual, reported_status: "缺学分", note: null,
});
const plan = (rows: DegreePlanImport["rows"]): DegreePlanImport => ({
  schema_version: "1.0.0", kind: "degree_completion_snapshot", program: "虚构专业", cohort: "2025",
  source: {kind: "file", origin: null, pathname: null},
  summary: {required_credits: "150", completed_credits: "12.5", actual_credits: "15", reported_result: "预审", reviewed_at: null, note: "不作为最终审核结果"}, rows,
});
describe("credit questions preserve C general elective policy", () => {
  it("Agent file exports only original module credits; no courses, grades, identity or derived gap",()=>{
    const value=degreeProgressForStorage(plan([module('通识选修课'),{kind:'course',course_code:'SECRET001',title:'虚构课程',
      required_credits:'2',actual_credits:'2',grade:'85',reported_pass:'是',note:'在读'}]));
    expect(Object.keys(value).sort()).toEqual(['schema_version','kind','program','cohort','summary','modules','has_in_progress_courses'].sort());
    expect(value.modules[0]).toEqual({title:'通识选修课',required_credits:'14',school_actual_credits:'10',school_status:'缺学分',school_note:null,
      school_in_progress_credits:'2',school_direct_in_progress_credits:'2'});
    expect(value.has_in_progress_courses).toBe(true);
    expect(JSON.stringify(value)).not.toMatch(/SECRET001|grade|course_code|source_index|credit_gap|policy_id/);
  });
  it("retains six-select-four, arts-only condition and source without issuing a passed verdict", () => {
    const result = degreeProgressForQuestions(plan([module("二 通识选修课(至少满足部分子项)")]));
    expect(result.policies[0]).toMatchObject({minimum_modules: 4, minimum_credits_per_selected_module: "2", verification_status: "needs_policy"});
    expect(result.policies[0].module_names).toHaveLength(6);
    expect(result.policies[0].art_requirement).toEqual({cohort_from: 2023, minimum_credits: "2", course_kind: "艺术类课程"});
    expect(result.modules[0].policy_id).toBe(GENERAL_ELECTIVE_POLICY.id);
    expect(result.policies[0].repository_source).toContain("plan-rules.md");
    expect(result.policies[0].checks.join(" ")).toContain("不是六个模块都必须修满");
  });
  it("uses the imported requirements, not the 14-credit reference for every major", () => {
    const result = degreeProgressForQuestions(plan([module("通识选修课", "12", "10")]));
    expect(result.modules[0]).toMatchObject({required_credits: "12", provisional_credit_gap: "2"});
  });
  it("keeps parent and child order and statuses without totaling overlapping credits", () => {
    const result = degreeProgressForQuestions(plan([module("通识选修课"), module("(一) 艺术审美与文化思辨", "2", "2")]));
    expect(result.modules.map(row => row.source_index)).toEqual([0,1]);
    expect(result.modules[1].policy_id).toBeNull();
    expect(result).not.toHaveProperty("module_total");
    expect(result.modules[1].school_status).toBe("缺学分");
    expect(result.policies[0].verification_status).toBe("needs_policy");
  });
  it("does not confuse actual/pre-audit/in-progress with completed or export grades", () => {
    const result = degreeProgressForQuestions(plan([module("通识选修课"), {
      kind: "course", course_code: "TEST001", title: "私人课程", required_credits: "2", actual_credits: "2",
      grade: "PRIVATE-GRADE", reported_pass: "是", note: "在读",
    }]));
    expect(result.summary.credit_gap).toBe("137.5");
    expect(result.has_in_progress_courses).toBe(true);
    expect(JSON.stringify(result)).not.toContain("PRIVATE-GRADE");
    expect(JSON.stringify(result)).not.toContain("私人课程");
    expect(result).not.toHaveProperty("courses");
  });
  it("keeps unknown totals unknown, clips excess credit difference, and avoids floating point error", () => {
    const input = plan([module("虚构模块", "2.3", "2.1"),module("另一模块", "2", "3")]);
    input.summary.completed_credits = null;
    const result = degreeProgressForQuestions(input);
    expect(result.summary.credit_gap).toBeNull();
    expect(result.modules.map(row => row.provisional_credit_gap)).toEqual(["0.2","0"]);
  });
  it("matches category titles only and does not attach a different module's policy", () => {
    for (const title of ["通识选修课","二、通识选修课（至少四项）","(一) 通识教育选修课程"])
      expect(isGeneralElectiveModule(title)).toBe(true);
    for (const title of ["非通识选修课","专业选修课","跨学院通识选修课","通识选修课程介绍"])
      expect(isGeneralElectiveModule(title)).toBe(false);
    expect(degreeProgressForQuestions(plan([module("专业选修课")])).policies).toEqual([]);
  });
  it("does not infer modules from course-only files or accept injected owner fields", () => {
    expect(() => degreeProgressForQuestions(plan([]))).toThrow();
    expect(() => degreeProgressForQuestions({...plan([module("虚构模块")]), owner_id:"other"} as DegreePlanImport)).toThrow();
  });
  it("retains aggregate and direct in-progress credits without assigning parent courses to a child", () => {
    const course = (code: string, actual: string, note: string | null) => ({kind:'course' as const,
      course_code:code,title:'私密课程',required_credits:actual,actual_credits:actual,grade:'PRIVATE',reported_pass:'是',note});
    const input=plan([module('二 通识选修课','14','7'),course('TEST001','2','在读'),course('TEST002','1','在读'),
      module('(一) 科学精神与健康生活','0','2'),course('TEST003','2',null),
      module('(二) 世界文明与国际视野','0','2'),course('TEST004','2',null),module('三 大类基础课','18','18')]);
    const result=degreeProgressForStorage(input);
    expect(result.modules[0]).toMatchObject({school_actual_credits:'7',school_in_progress_credits:'3',school_direct_in_progress_credits:'3'});
    expect(result.modules[1]).toMatchObject({school_in_progress_credits:'0',school_direct_in_progress_credits:'0'});
    expect(JSON.stringify(result)).not.toMatch(/TEST00|PRIVATE|私密课程|grade|course_code/);
  });
  it("does not double count duplicate allocations or invent a group when hierarchy is unknown", () => {
    const course={kind:'course' as const,course_code:'TEST001',title:'虚构课程',required_credits:'2',actual_credits:'2',grade:null,reported_pass:'是',note:'在读'};
    for(const rows of [[module('一 父项'),course,{...course}], [module('父项'),course,module('未编号子项')]]) {
      expect(degreeProgressForStorage(plan(rows)).modules[0].school_in_progress_credits).toBeNull();
    }
  });
});

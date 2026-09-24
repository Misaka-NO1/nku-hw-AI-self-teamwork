/**
 * 开发模式演示数据：后端未接入 /api/v1/degree/audit 时，
 * 用带 demo 标签的夹具预期结果展示页面结构。
 * 生产模式（import.meta.env.PROD）不得使用本文件兜底。
 */
import expected from "../../../../fixtures/expected-results.demo.json";
import plan from "../../../../fixtures/degree-plan.demo.json";
import type { DegreeAuditResult } from "./types";

export const DEMO_PLAN_ID = plan.plan_id;
export const DEMO_PLAN_VERSION = plan.version;

export function demoAuditResult(): DegreeAuditResult {
  const deg = expected.degree;
  return {
    planId: plan.plan_id,
    planVersion: plan.version,
    sourceRef: plan.source_ref,
    modules: [
      {
        moduleId: "core",
        earnedCredits: deg.core_earned,
        requiredCredits: "8.0",
        remainingCredits: deg.core_remaining,
        missingRequiredCourses: deg.missing_required_courses,
        countedAttempts: ["a1"],
        excludedAttempts: ["a2", "a3", "a4"],
      },
      {
        moduleId: "elective",
        earnedCredits: deg.elective_earned,
        requiredCredits: "4.0",
        remainingCredits: deg.elective_remaining,
        missingRequiredCourses: [],
        countedAttempts: ["a5"],
        excludedAttempts: [],
      },
    ],
    unallocatedCourses: [],
    unresolvedRules: [],
    dataCoverage: {
      datasetKind: "demo",
      totalEarnedCredits: deg.total_earned,
      totalRemainingCredits: deg.total_remaining,
      notGraduationDecision: deg.not_graduation_decision,
      note: "夹具预期结果演示，不是实际审计输出",
    },
    status: "incomplete",
  };
}

/** 培养方案审计结果（前端内部 camelCase，由 API client 转换）。 */

export interface DegreeModuleResult {
  moduleId: string;
  earnedCredits: string;
  requiredCredits: string;
  remainingCredits: string;
  missingRequiredCourses: string[];
  countedAttempts: string[];
  excludedAttempts: string[];
}

export interface DegreeAuditResult {
  planId: string;
  planVersion: string;
  sourceRef: string;
  modules: DegreeModuleResult[];
  unallocatedCourses: string[];
  unresolvedRules: string[];
  dataCoverage: {
    datasetKind?: string;
    totalEarnedCredits?: string;
    totalRemainingCredits?: string;
    notGraduationDecision?: boolean;
    note?: string;
    [key: string]: unknown;
  };
  status: "complete_under_supported_rules" | "incomplete" | "needs_policy";
}

export const STATUS_LABELS: Record<DegreeAuditResult["status"], string> = {
  complete_under_supported_rules: "在所支持规则下已满足",
  incomplete: "尚有缺口",
  needs_policy: "缺少规则，暂不能核算",
};

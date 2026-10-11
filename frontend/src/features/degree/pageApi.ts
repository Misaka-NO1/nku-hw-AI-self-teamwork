import { apiClient } from "../../shared/api/client";
import type { DemoSession } from "../tasks/api";

export interface PageCourse {
  locator: string;
  moduleLocator: string | null;
  code: string | null;
  name: string | null;
  requiredCredits: string | null;
  pageEarnedCredits: string | null;
  state: "passed" | "in_progress" | "failed" | "pending_recognition" | "unknown";
}
export interface PageModule {
  locator: string;
  name: string | null;
  label: string;
  requiredCredits: string | null;
  pageEarnedCredits: string | null;
  gapCredits: string | null;
  gapCourseCount: number | null;
  gapText: string | null;
  requirement: string;
  parentLocator?: string | null;
  hierarchyBasis?: string;
}
export interface PageReport {
  source: { capturedAt: string; coverage: string };
  modules: PageModule[];
  courses: PageCourse[];
  pendingVerification: { code: string; detail: string }[];
  pageProgress: unknown;
  canDecideComplete: boolean;
  moduleSummaries?: {
    locator: string; observedPassedCredits: string | null; observedInProgressCredits: string | null;
    statisticsScope: string; requiredCourseCoverage: string; nextStep: string;
    optionalBranch?: boolean;
    passedCourseNames?: string[]; inProgressCourseNames?: string[];
    missingRequiredCourses: { name: string | null; code: string | null; state: string }[];
    requiredCategoryPendingCourses?: { name: string | null; code: string | null; state: string }[];
    pendingCourses: { name: string | null; code: string | null; state: string }[];
    calculation: { subtreeEarnedCredits: string; remainingCredits: string | null } | null;
    discrepancies: { code: string; page?: string | boolean; calculated?: string | boolean; calculatedSubtree?: string }[];
  }[];
  prioritySuggestions?: { moduleName: string; message: string; evidence: { locator: string } }[];
  recommendationLimits?: string[];
}

export function analyzePageObservation(observation: unknown, session: DemoSession, signal: AbortSignal) {
  return apiClient.post<PageReport>("/api/v1/degree/page/observation", observation, {
    signal, headers: { "X-CSRF-Token": session.csrfToken },
  });
}

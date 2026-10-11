// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DegreeReadPreview } from "./DegreeReadPreview";
import { degreeApi, saveConfirmedDegree } from "./connectedApi";
import { ApiError } from "../../shared/api/client";
vi.mock("../auth/useBrowserSession", () => ({ useBrowserSession: () => ({ session: {
  workspaceRef: "fictional-owner", csrfToken: "fictional-csrf", expiresAt: "2099-01-01T00:00:00Z",
}, checking: false, rejectExpiredSession: vi.fn() }) }));
vi.mock("./connectedApi", () => ({ degreeApi: { current: vi.fn(), createDraft: vi.fn() }, saveConfirmedDegree: vi.fn() }));
const observation = { kind: "degree-table-observation", source: {
  url: "https://eamis.nankai.edu.cn/eams/myPlanCompl.action", captured_at: "2026-01-01T00:00:00Z",
  coverage: "unknown", adapter_verified: false }, headers: ["课程名称"],
  rows: [{ cells: ["虚构模块"], locator: "table-row:2" }] };

describe("培养计划主动核对分析", () => {
  afterEach(() => { vi.resetAllMocks(); vi.unstubAllGlobals(); });
  it("接收不自动提交，核对生成草稿后再明确保存和读回，无须复制 JSON", async () => {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    const host = document.createElement("div"); document.body.append(host);
    const root = createRoot(host);
    vi.mocked(degreeApi.current).mockRejectedValueOnce(new ApiError({ code: "NOT_FOUND", message: "empty", status: 404, requestId: "test" }));
    const draftMeta = { draftId: "degree-test", kind: "degree" as const, workspaceRef: "fictional-owner", revision: 1,
      payloadHash: "test-hash", status: "draft" as const, expiresAt: "2099-01-01T00:00:00Z", payload: observation };
    try {
      await act(async () => root.render(createElement(DegreeReadPreview)));
      await act(async () => window.dispatchEvent(new CustomEvent("campus:degree-observation", { detail: observation })));
      expect(degreeApi.createDraft).not.toHaveBeenCalled();
      expect(saveConfirmedDegree).not.toHaveBeenCalled();
      expect(writeText).not.toHaveBeenCalled();
      vi.mocked(degreeApi.createDraft).mockResolvedValueOnce({ ...draftMeta, report: { source: { capturedAt: "2026-01-01", coverage: "unknown" },
        modules: [{ locator: "m1", name: "虚构模块甲", label: "虚构模块甲", requiredCredits: "4", pageEarnedCredits: "2",
          gapCredits: "2", gapCourseCount: 1, gapText: "缺2学分缺1门", requirement: "unknown" },
          { locator: "m2", name: "虚构可选组", label: "虚构可选组，非必须选择", requiredCredits: "2", pageEarnedCredits: "0",
            gapCredits: "2", gapCourseCount: 1, gapText: "缺2学分", requirement: "unknown" }],
        courses: [{ locator: "c1", moduleLocator: "m1", code: "TEST1", name: "虚构在读课程", requiredCredits: "2", pageEarnedCredits: "2", state: "in_progress" }],
        moduleSummaries: [{ locator: "m1", observedPassedCredits: "0", observedInProgressCredits: "2",
          statisticsScope: "仅当前直接课程", requiredCourseCoverage: "仅明确必修", nextStep: "优先核对虚构在读课程的必修状态",
          missingRequiredCourses: [{ name: "虚构在读课程", code: "TEST1", state: "in_progress" }], pendingCourses: [],
          calculation: { subtreeEarnedCredits: "0", remainingCredits: "4" },
          discrepancies: [{ code: "page_earned_credits_mismatch", page: "2", calculatedSubtree: "0" }] },
          { locator: "m2", optionalBranch: true, observedPassedCredits: "0", observedInProgressCredits: "0",
            statisticsScope: "仅当前直接课程", requiredCourseCoverage: "仅明确必修", nextStep: "页面注明此分支可选",
            missingRequiredCourses: [], pendingCourses: [], calculation: { subtreeEarnedCredits: "0", remainingCredits: "2" }, discrepancies: [] }],
        prioritySuggestions: [{ moduleName: "虚构模块甲", message: "优先核对必修", evidence: { locator: "m1" } }],
        pendingVerification: [{ code: "unknown", detail: "方案版本待核实" }], canDecideComplete: false, pageProgress: null } });
      await act(async () => host.querySelector<HTMLButtonElement>("button")!.click());
      expect(host.textContent).toContain("虚构模块甲");
      expect(host.textContent).toContain("虚构在读课程");
      expect(host.textContent).toContain("未识别到已通过记录");
      expect(host.textContent).toContain("缺2学分缺1门");
      expect(host.textContent).toContain("实修学分：教务显示 2，独立核算 0");
      expect(host.textContent).toContain("优先核对必修");
      expect(host.textContent).toContain("此分支可选，页面缺口不代表必须补修本组");
      expect(host.textContent).toContain("以下核算只描述本分支");
      expect(host.textContent).not.toContain("page_earned_credits_mismatch");
      expect(saveConfirmedDegree).not.toHaveBeenCalled();
      expect(host.textContent).not.toContain("复制已核对");
      const report = (await vi.mocked(degreeApi.createDraft).mock.results[0].value).report;
      vi.mocked(saveConfirmedDegree).mockResolvedValueOnce({ degreeId: "saved-degree", revision: 1 });
      vi.mocked(degreeApi.current).mockResolvedValueOnce({ degreeId: "saved-degree", workspaceRef: "fictional-owner", revision: 1,
        confirmedAt: "2026-10-10", observation, report });
      const save = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find(button => button.textContent?.includes("确认替换"))!;
      await act(async () => save.click());
      expect(saveConfirmedDegree).toHaveBeenCalledOnce();
      expect(host.textContent).toContain("已从数据库读回本人培养计划");
      expect(host.textContent).toContain("无需复制表格");
      expect(writeText).not.toHaveBeenCalled();
      vi.mocked(degreeApi.createDraft).mockRejectedValueOnce(new Error("unavailable"));
      await act(async () => host.querySelector<HTMLButtonElement>("button")!.click());
      expect(host.textContent).toContain("生成草稿未成功");
      expect(host.textContent).not.toContain("虚构模块甲");
      expect(host.textContent).not.toContain("复制已核对");
      await act(async () => window.dispatchEvent(new Event("campus:degree-read-error")));
      expect(host.textContent).toContain("培养计划没有成功转交");
      expect(host.textContent).not.toContain("虚构模块");
    } finally { await act(async () => root.unmount()); host.remove(); }
  });
});

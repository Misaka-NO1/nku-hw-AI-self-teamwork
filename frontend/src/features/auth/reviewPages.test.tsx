import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../shared/api/client";
import TasksPage from "../tasks/TasksPage";
import ConnectedImportPage from "../import/ConnectedImportPage";
import CloudbaseLoginPage from "./CloudbaseLoginPage";
import ConnectedTimetablePage from "../timetable/ConnectedTimetablePage";
import { useBrowserSession } from "./useBrowserSession";

vi.mock("./useBrowserSession", () => ({ useBrowserSession: vi.fn() }));
const state = (overrides: Partial<ReturnType<typeof useBrowserSession>> = {}): ReturnType<typeof useBrowserSession> => ({
  session: null, setSession: vi.fn(), checking: true, needsLogin: false, recoveryError: null,
  rejectExpiredSession: vi.fn(), retryRecovery: vi.fn(), ...overrides,
});
describe("identity review page recovery states", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_IDENTITY_PILOT", "true");
    vi.stubGlobal("sessionStorage", { getItem: () => null });
    vi.stubGlobal("window", { location: new URL("https://pilot.example.invalid/tools/tasks?draft_id=draft_123") });
    vi.mocked(useBrowserSession).mockReturnValue(state());
  });
  afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
  it.each([TasksPage, ConnectedImportPage])("waits for the server check with no anonymous create button", Page => {
    const markup = renderToStaticMarkup(createElement(Page));
    expect(markup).toContain("正在核验当前浏览器会话");
    expect(markup).not.toContain("开始虚构数据测试"); expect(markup).not.toContain("创建虚构测试工作区");
    expect(markup).not.toContain("新建虚构工作区");
    expect(markup).toMatch(/<button[^>]*disabled=""[^>]*>.*生成.*草稿/);
  });
  it.each([TasksPage, ConnectedImportPage])("offers a controlled review login after an expired check", Page => {
    const path = Page === TasksPage ? "/tools/tasks" : "/tools/import";
    vi.stubGlobal("window", { location: new URL("https://pilot.example.invalid" + path + "?draft_id=draft_123") });
    vi.mocked(useBrowserSession).mockReturnValue(state({ checking: false, needsLogin: true,
      recoveryError: new ApiError({ code: "AUTH_REQUIRED", status: 401, message: "Login required", requestId: "request-401" }) }));
    const markup = renderToStaticMarkup(createElement(Page));
    expect(markup).toContain("/tools/login?return_to=" + encodeURIComponent(path + "?draft_id=draft_123"));
    expect(markup).toContain("不会自动保存"); expect(markup).not.toContain("新建虚构工作区");
  });
  it.each([TasksPage, ConnectedImportPage])("reports a failed dependency and keeps writes disabled", Page => {
    vi.mocked(useBrowserSession).mockReturnValue(state({ checking: false,
      recoveryError: new ApiError({ code: "DEPENDENCY_UNAVAILABLE", status: 503, message: "Dependency failed", requestId: "request-503" }) }));
    const markup = renderToStaticMarkup(createElement(Page));
    expect(markup).toContain("Dependency failed"); expect(markup).toContain("request-503");
    expect(markup).toContain("重新核验浏览器会话"); expect(markup).not.toContain("登录测试账号后返回");
    expect(markup).toMatch(/<button[^>]*disabled=""[^>]*>.*生成.*草稿/);
  });
  it("offers the original review after a valid Cookie recovery on the login page", () => {
    vi.stubGlobal("window", { location: new URL("https://pilot.example.invalid/tools/login?" + new URLSearchParams({ return_to: "/tools/tasks?draft_id=draft_123" })) });
    vi.mocked(useBrowserSession).mockReturnValue(state({ checking: false, session: {
      workspaceRef: "pilot_workspace_A", csrfToken: "fictional-csrf", expiresAt: "2099-01-01T00:00:00Z" } }));
    const markup = renderToStaticMarkup(createElement(CloudbaseLoginPage));
    expect(markup).toContain('href="/tools/tasks?draft_id=draft_123"');
    expect(markup).toContain("仍须你核对并明确确认，不会自动保存");
  });
  it("does not read a timetable or show free-time controls while identity is being checked", () => {
    const markup = renderToStaticMarkup(createElement(ConnectedTimetablePage));
    expect(markup).toContain("正在核验当前浏览器会话");
    expect(markup).not.toContain("尚未创建工作区");
    expect(markup).not.toContain("查询已保存课表的空档");
    expect(useBrowserSession).toHaveBeenCalledWith(true);
  });
  it("requires login for an expired timetable session without rendering stale records", () => {
    vi.mocked(useBrowserSession).mockReturnValue(state({ checking: false, needsLogin: true,
      recoveryError: new ApiError({ code: "AUTH_REQUIRED", status: 401, message: "Login required", requestId: "request-401" }) }));
    const markup = renderToStaticMarkup(createElement(ConnectedTimetablePage));
    expect(markup).toContain('href="/tools/login"');
    expect(markup).toContain("不会自动保存");
    expect(markup).not.toContain("数据库记录");
    expect(markup).not.toContain("查询已保存课表的空档");
  });
  it("keeps timetable reads closed on a failed session dependency", () => {
    vi.mocked(useBrowserSession).mockReturnValue(state({ checking: false,
      recoveryError: new ApiError({ code: "DEPENDENCY_UNAVAILABLE", status: 503, message: "Dependency failed", requestId: "request-503" }) }));
    const markup = renderToStaticMarkup(createElement(ConnectedTimetablePage));
    expect(markup).toContain("重新核验浏览器会话");
    expect(markup).toContain("request-503");
    expect(markup).not.toContain("我的课表");
    expect(markup).not.toContain("尚未创建工作区");
  });
});

// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import CalendarPage from "./CalendarPage";
import { useBrowserSession } from "../auth/useBrowserSession";
import { loadCalendar } from "./api";
import { READ_ONLY } from "./model";
import { ApiError } from "../../shared/api/client";

vi.mock("../auth/useBrowserSession", () => ({ useBrowserSession: vi.fn() }));
vi.mock("./api", () => ({ loadCalendar: vi.fn(), loadCandidates: vi.fn(), updateCalendar: vi.fn() }));

describe("calendar contains only verified owner records, without frontend demo controls", () => {
  it.each([false, true])("renders no demo entry or memory fallback (logged in: %s)", async (loggedIn) => {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    vi.mocked(useBrowserSession).mockReturnValue({
      session: loggedIn ? { workspaceRef: "verified-owner", csrfToken: "csrf-test", expiresAt: "2099-01-01T00:00:00Z" } : null,
      checking: false, needsLogin: !loggedIn, setSession: vi.fn(),
      recoveryError: null, rejectExpiredSession: vi.fn(), retryRecovery: vi.fn(),
    } as ReturnType<typeof useBrowserSession>);
    vi.mocked(loadCalendar).mockResolvedValue({ items: [], capabilities: READ_ONLY });
    const host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    try {
      await act(async () => root.render(createElement(CalendarPage)));
      const actions = [...host.querySelectorAll(".calendar-heading button")].map(button => button.textContent);
      expect(actions).toEqual(["回到今天", "刷新记录"]);
      expect(host.textContent).not.toMatch(/查看前端演示|重置演示|退出演示|前端交互演示|演示候选/);
      if (loggedIn) {
        expect(loadCalendar).toHaveBeenCalledOnce();
        expect(host.textContent).toContain("当前没有未完成事项。");
      } else {
        expect(loadCalendar).not.toHaveBeenCalled();
        expect(host.textContent).toContain("登录后返回日历");
        expect(host.querySelector(".calendar-stats")).toBeNull();
      }
    } finally {
      await act(async () => root.unmount());
      host.remove();
      vi.unstubAllGlobals();
      vi.resetAllMocks();
    }
  });

  it.each(["checking", "dependency", "expired"])("keeps owner data hidden when %s", (condition) => {
    vi.mocked(useBrowserSession).mockReturnValue({
      session: condition === "expired" ? { workspaceRef: "expired-owner", csrfToken: "csrf-test", expiresAt: "2000-01-01T00:00:00Z" } : null,
      checking: condition === "checking", needsLogin: condition !== "checking", setSession: vi.fn(),
      recoveryError: condition === "dependency" ? new ApiError({ status: 503, code: "DEPENDENCY_UNAVAILABLE", message: "Dependency unavailable", requestId: "test-503" }) : null,
      rejectExpiredSession: vi.fn(), retryRecovery: vi.fn(),
    });
    try {
      const html = renderToStaticMarkup(createElement(CalendarPage));
      expect(html).not.toContain("calendar-task-card");
      expect(html).not.toContain("calendar-stats");
      expect(html).not.toMatch(/查看前端演示|重置演示|退出演示/);
      if (condition === "checking") expect(html).toContain("正在核验当前浏览器会话");
      if (condition === "expired") expect(html).toContain("登录后返回日历");
      if (condition === "dependency") {
        expect(html).toContain("test-503");
        expect(html).toContain("重新核验浏览器会话");
      }
    } finally { vi.resetAllMocks(); }
  });
});

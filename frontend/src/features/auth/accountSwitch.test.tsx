// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { useBrowserSession } from "./useBrowserSession";
import { restoreBrowserSession } from "../tasks/sessionCache";
vi.mock("../tasks/sessionCache", () => ({ restoreBrowserSession: vi.fn(),
  readDemoSession: vi.fn(), sessionExpired: vi.fn(), rejectUnauthenticatedBrowserSession: vi.fn() }));

describe("already-open tabs follow the verified current owner", () => {
  it("hides A immediately on focus, then displays only the reverified B owner", async () => {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    const a = { workspaceRef: "owner-A", csrfToken: "csrf-A", expiresAt: "2099-01-01T00:00:00Z" };
    const b = { ...a, workspaceRef: "owner-B", csrfToken: "csrf-B" };
    let finish!: (value: typeof a) => void;
    vi.mocked(restoreBrowserSession).mockResolvedValueOnce(a).mockImplementationOnce(
      () => new Promise(resolve => { finish = resolve; }));
    const host = document.createElement("div"); document.body.append(host);
    const root = createRoot(host);
    function Page() {
      const auth = useBrowserSession(true);
      return createElement("div", null, auth.checking ? "verifying" : auth.session?.workspaceRef ?? "no owner");
    }
    try {
      await act(async () => { root.render(createElement(Page)); });
      expect(host.textContent).toBe("owner-A");
      await act(async () => { window.dispatchEvent(new Event("focus")); });
      expect(host.textContent).toBe("verifying");
      expect(host.textContent).not.toContain("owner-A");
      await act(async () => { finish(b); });
      expect(host.textContent).toBe("owner-B");
    } finally {
      await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); vi.resetAllMocks();
    }
  });
});

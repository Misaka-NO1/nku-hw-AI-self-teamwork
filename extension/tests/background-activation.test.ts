import { afterEach, describe, expect, it, vi } from "vitest";

describe("extension icon routes degree activation separately", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });
  async function activate(url: string, id: number | undefined = 7) {
    let listener: (tab: { id?: number; url: string }) => Promise<void>;
    const api = {
      action: { onClicked: { addListener: vi.fn(fn => { listener = fn; }) } },
      scripting: { executeScript: vi.fn().mockResolvedValue([]) },
      tabs: { sendMessage: vi.fn() },
      runtime: { id: "fictional-extension", onMessage: { addListener: vi.fn() } },
    };
    vi.stubGlobal("chrome", api);
    await import("../src/background");
    await listener!({ id, url });
    return api;
  }
  it("mounts only the degree button without reading or messaging timetable", async () => {
    const api = await activate("https://eamis.nankai.edu.cn/eams/myPlanCompl.action");
    expect(api.scripting.executeScript).toHaveBeenCalledExactlyOnceWith({ target: { tabId: 7 }, files: ["dist/degree-content.js"] });
    expect(api.tabs.sendMessage).not.toHaveBeenCalled();
  });
  it("preserves original timetable icon behavior", async () => {
    const api = await activate("https://eamis.nankai.edu.cn/eams/courseTableForStd!courseTable.action");
    expect(api.scripting.executeScript).toHaveBeenCalledExactlyOnceWith({ target: { tabId: 7 }, files: ["dist/content.js"] });
    expect(api.tabs.sendMessage).toHaveBeenCalledExactlyOnceWith(7, { type: "extract-visible-schedule", payload: null });
  });
  it.each(["https://example.invalid/eams/myPlanCompl.action", "https://eamis.nankai.edu.cn/eams/home.action"])("does not inject outside permitted page: %s", async url => {
    const api = await activate(url);
    expect(api.scripting.executeScript).not.toHaveBeenCalled();
    expect(api.tabs.sendMessage).not.toHaveBeenCalled();
  });
});

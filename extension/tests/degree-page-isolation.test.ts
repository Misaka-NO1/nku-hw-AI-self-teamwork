// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { mountImportButton } from "../src/content";

describe("degree page does not mount timetable action", () => {
  it("rejects the plan URL even if an injected document contains the timetable grid", () => {
    document.body.innerHTML = '<table id="manualArrangeCourseTable"></table>';
    const api = { runtime: { sendMessage: vi.fn() } } as unknown as typeof chrome;
    mountImportButton(api, document, "https://eamis.nankai.edu.cn/eams/myPlanCompl.action");
    expect(document.getElementById("campus-schedule-import-host")).toBeNull();
    expect(api.runtime.sendMessage).not.toHaveBeenCalled();
  });
  it("preserves the timetable URL button", () => {
    document.body.innerHTML = '<table id="manualArrangeCourseTable"></table>';
    const api = { runtime: { sendMessage: vi.fn() } } as unknown as typeof chrome;
    mountImportButton(api, document, "https://eamis.nankai.edu.cn/eams/courseTableForStd!courseTable.action");
    expect(document.getElementById("campus-schedule-import-host")).not.toBeNull();
    expect(api.runtime.sendMessage).not.toHaveBeenCalled();
  });
});
